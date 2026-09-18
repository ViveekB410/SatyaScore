"""
STEP 2 of 2: Build a starter evidence corpus + generate the annotation CSV.

Run this AFTER collect_responses.py has produced raw_responses.json.

WHY A "STARTER" CORPUS: the PRD's real evidence source (Section 11.1) is
the full multilingual Wikipedia dump — that's a genuinely large download
and indexing job, out of scope to do automatically here. Instead, this
script fetches real (not fake) Wikipedia summary paragraphs for ~40
topics that match the seed query bank's subject matter, via Wikipedia's
public REST API. This is enough for SemSim to have something real to
compare against — but it is NOT the full corpus. Expect many claims to
retrieve weak or irrelevant evidence simply because the topic isn't in
this small starter set. Swap in the full pipeline once you build the real
corpus (Section 11.1).

Run:
    python generate_dataset.py
"""

import json
import re
import time
from pathlib import Path

import requests

from dataset_pipeline.dataset_builder import DatasetBuilder
from dataset_pipeline.response_collector import LLMResponse
from member1_model.cmhsa import CMHSAScorer
from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member2_data.entity_linker import EntityLinker
from member2_data.wikidata_connector import WikidataConnector
from member3_backend.claim_extractor import ClaimExtractor
from member3_backend.faiss_retriever import FAISSRetriever
from member3_backend.pipeline import DetectionPipeline

RAW_RESPONSES_PATH = Path("raw_responses.json")
OUTPUT_CSV_PATH = Path("unannotated_dataset.csv")

# Real Wikipedia article titles matching the seed query bank's topics
# across all 5 domains. English titles — Wikipedia's REST API also
# supports hi.wikipedia.org for Hindi if you want to extend this later.
STARTER_TOPICS_EN = [
    # healthcare
    "Dengue_fever", "Immune_system", "Paracetamol", "Type_2_diabetes",
    "Tuberculosis", "Vaccination", "Hypertension", "Insulin",
    # history
    "Indian_independence_movement", "Jawaharlal_Nehru", "World_War_I",
    "Constitution_of_India", "Mughal_Empire", "Dandi_March",
    "Battle_of_Plassey", "Shivaji", "Non-cooperation_movement", "United_Nations",
    # science
    "Water", "Photosynthesis", "Season", "Speed_of_light", "Vaccine",
    "Mass_versus_weight", "Greenhouse_effect", "Plate_tectonics",
    "Black_hole", "DNA",
    # government
    "President_of_India", "Fundamental_rights_in_India", "Lok_Sabha",
    "Election_Commission_of_India", "Rajya_Sabha", "Chief_Minister_(India)",
    "Reserve_Bank_of_India", "Governor_(India)", "Article_370",
    # sports
    "Cricket", "Cricket_World_Cup", "India_men's_national_field_hockey_team",
    "Offside_(association_football)", "Indian_Premier_League",
    "Ranji_Trophy", "Formula_One",
]


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
MAX_CHUNK_CHARS = 400   # keeps chunks well within NLI's 256-token limit,
                        # leaving room for the claim (hypothesis) too
MIN_CHUNK_CHARS = 40    # drops near-empty fragments (bare section headers etc.)


def _chunk_article_text(text: str) -> list[str]:
    """Splits full article plain text into paragraph-sized chunks, further
    splitting any paragraph that's too long by regrouping sentences up to
    MAX_CHUNK_CHARS. Near-empty fragments (stray headers, table-of-contents
    leftovers) are dropped rather than indexed as noise passages."""
    chunks = []
    for para in _PARAGRAPH_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= MAX_CHUNK_CHARS:
            if len(para) >= MIN_CHUNK_CHARS:
                chunks.append(para)
            continue
        sentences = _SENTENCE_SPLIT.split(para)
        current = ""
        for sent in sentences:
            candidate = f"{current} {sent}".strip()
            if len(candidate) <= MAX_CHUNK_CHARS:
                current = candidate
            else:
                if len(current) >= MIN_CHUNK_CHARS:
                    chunks.append(current)
                current = sent
        if len(current) >= MIN_CHUNK_CHARS:
            chunks.append(current)
    return chunks


def fetch_wikipedia_fulltext(title: str, max_retries: int = 4) -> str | None:
    """Fetches the FULL article plain text (not just the 2-3 sentence lead
    summary the REST API's page/summary endpoint returns), via the older
    MediaWiki Action API's `extracts` prop with explaintext=1.

    WHY THIS MATTERS (root-caused via this project's ablation study): a
    short lead summary rarely contains the SPECIFIC fact a claim is about
    (a date, a number, a name). This was diagnosed as the reason NLI showed
    near-zero correlation with actual hallucination (~0.03-0.06) and why
    SemSim's class-conditional distributions for Hallucinated vs. Verified
    overlapped ~94% (Cohen's d ~0.14) -- a topically-relevant-but-wrong
    claim looks the same to a shallow single-summary corpus as a correct
    one. Full article text, chunked into many small passages, gives both
    signals actual granular content to work with instead of one short,
    generic paragraph per topic."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query", "prop": "extracts", "explaintext": 1,
        "titles": title, "format": "json", "redirects": 1,
    }
    for attempt in range(max_retries):
        try:
            # 30s (not 15s): a few very large articles (Cricket, World War I,
            # ...) render slowly server-side. Capping the response with
            # exchars=20000 was tried and REVERTED -- the anonymous exchars
            # limit is far below 20000 in practice and gutted the corpus to
            # ~130 passages. A longer timeout is the correct fix for a
            # slow-render problem; a length cap is not.
            response = requests.get(url, params=params, headers={"User-Agent": "SatyaScore/1.0"}, timeout=30)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
            for page in pages.values():
                if "missing" in page:
                    return None  # genuinely doesn't exist -- not a rate limit
                extract = page.get("extract")
                if extract:
                    return extract
            return None
        except requests.RequestException:
            if attempt == max_retries - 1:
                return None
            time.sleep(2 ** attempt)
    return None


def fetch_wikipedia_summary(title: str, max_retries: int = 4) -> str | None:
    """Real Wikipedia REST API call — no auth needed.

    Retries with exponential backoff on rate-limiting (HTTP 429) or
    transient server errors (5xx), which is what actually caused the
    ~15-of-44 fetch failures seen in practice — firing 44 requests
    back-to-back with zero delay reliably triggers Wikipedia's
    unauthenticated-client throttle partway through the loop, and it
    doesn't recover on its own within the same run. A plain title-not-
    found (404) is NOT retried — that's a real dead title, not a
    rate limit, and retrying it would just waste time.
    """
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers={"User-Agent": "SatyaScore/1.0"}, timeout=10)
            if response.status_code == 404:
                return None  # real dead/renamed title — retrying won't help
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s
                continue
            response.raise_for_status()
            return response.json().get("extract")
        except requests.RequestException:
            if attempt == max_retries - 1:
                return None
            time.sleep(2 ** attempt)
    return None


def build_starter_corpus(embedder: CrossLingualEmbedder, retriever: FAISSRetriever) -> None:
    print(f"Fetching {len(STARTER_TOPICS_EN)} full Wikipedia articles for the starter evidence corpus...")
    passage_ids, texts = [], []
    for i, title in enumerate(STARTER_TOPICS_EN):
        fulltext = fetch_wikipedia_fulltext(title)
        if fulltext:
            chunks = _chunk_article_text(fulltext)
            for j, chunk in enumerate(chunks):
                passage_ids.append(f"{title}__chunk{j}")
                texts.append(chunk)
            print(f"  {title}: {len(chunks)} chunks")
        else:
            print(f"  (skipped {title} — fetch failed after retries)")
        if i < len(STARTER_TOPICS_EN) - 1:
            time.sleep(0.3)  # courtesy delay, avoids triggering rate-limiting

    print(f"\nEmbedding {len(texts)} passages and building FAISS index...")
    result = embedder.embed(passage_ids, texts, ["en"] * len(texts))
    retriever.build_index(passage_ids, texts, result.vectors)
    print(f"Starter corpus ready: {len(retriever)} passages indexed "
          f"(was 44 single-summary passages before this fix).\n")


def main():
    if not RAW_RESPONSES_PATH.exists():
        raise SystemExit(f"{RAW_RESPONSES_PATH} not found — run collect_responses.py first.")

    with open(RAW_RESPONSES_PATH, encoding="utf-8") as f:
        raw_data = json.load(f)

    # Rebuild the pipeline (same components api.py uses).
    embedder = CrossLingualEmbedder()
    retriever = FAISSRetriever()
    scorer = CMHSAScorer()
    for lang in ("en", "hi", "mr"):
        scorer.load_weights(lang, alpha=0.5, beta=0.3, gamma=0.2)
    claim_extractor = ClaimExtractor()
    nli_scorer = NLIScorer()
    entity_linker = EntityLinker()
    wikidata = WikidataConnector()

    build_starter_corpus(embedder, retriever)

    pipeline = DetectionPipeline(
        embedder=embedder, retriever=retriever, scorer=scorer,
        claim_extractor=claim_extractor, nli_scorer=nli_scorer,
        entity_linker=entity_linker, wikidata=wikidata,
    )
    builder = DatasetBuilder(pipeline)

    # Convert raw_responses.json back into LLMResponse objects + lang/domain maps.
    responses, lang_map, domain_map = [], {}, {}
    for query_id, entry in raw_data.items():
        lang_map[query_id] = entry["language"]
        domain_map[query_id] = entry["domain"]
        for r in entry["responses"]:
            responses.append(
                LLMResponse(
                    query_id=query_id,
                    query_text=entry["query_text"],
                    response_text=r["response_text"],
                    source_llm=r["source_llm"],
                    latency_ms=0.0,
                )
            )

    print(f"Decomposing {len(responses)} responses into claims and scoring signals...")
    print("(First claim will be slow — NLI model downloads on first use, ~500MB.)")
    print("(Wikidata KG lookups are also slow on first pass, up to 10s per unmatched")
    print(" claim — this is normal, not stuck. Progress prints below.)\n")

    all_rows = []
    for i, response in enumerate(responses):
        lang = lang_map.get(response.query_id, "en")
        domain = domain_map.get(response.query_id, "unknown")
        print(f"[{i+1}/{len(responses)}] {response.query_id} ({response.source_llm})...", end=" ", flush=True)
        rows = builder.build_rows_from_response(response, lang, domain)
        all_rows.extend(rows)
        print(f"{len(rows)} claims")

        # Save progress every 10 responses, not just at the very end — if
        # this gets interrupted, you don't lose everything already scored.
        if (i + 1) % 10 == 0:
            builder.export_csv(all_rows, OUTPUT_CSV_PATH)

    builder.export_csv(all_rows, OUTPUT_CSV_PATH)
    rows = all_rows

    print(f"\nDone. {len(rows)} claims written to {OUTPUT_CSV_PATH}")
    print("Next: open this CSV, fill in gold_verdict + evidence_url per claim")
    print("(Verified/Uncertain/Hallucinated), then run:")
    print('  DatasetBuilder.to_training_csv("unannotated_dataset.csv", "training_ready.csv")')


if __name__ == "__main__":
    main()