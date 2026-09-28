"""
REST API for SatyaScore.

PRD ref: FR-05.
    - POST /detect accepting {text, language, threshold (optional)}
    - Returns {claims, scores, verdicts, overall_score, processing_time_ms}
    - API key authentication and rate limiting (100 req/min per key)
    - Swagger/OpenAPI docs at /docs (FastAPI provides this automatically)
    - HTTP 422 with descriptive error for invalid inputs (FastAPI/Pydantic
      does this automatically for malformed request bodies)

Run locally:
    uvicorn member3_backend.api:app --reload
Then visit http://localhost:8000/docs

NOTE ON STARTUP COST: the NLI model (member1_model/nli_scorer.py) is
~500MB and lazy-loads on first request that needs it, not at server
startup — so the first /detect call after starting the server will be
noticeably slower than subsequent ones. This is expected.
"""

from __future__ import annotations

import time
import re
import requests
from collections import defaultdict
from typing import Literal

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from member1_model.calibration import load_table, lookup
from member1_model.cmhsa import KG_NOTE, CMHSAScorer, aggregate_document
from member3_backend.factcheck_rules import FC_NOTE_PREFIX
from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member2_data.entity_linker import EntityLinker
from member2_data.wikidata_connector import WikidataConnector
from member3_backend import auth
from member3_backend.claim_extractor import ClaimExtractor
from member3_backend.evidence_rules import SubjectIndex, passage_source
from member3_backend.faiss_retriever import FAISSRetriever
from member3_backend.pipeline import DetectionPipeline

# --- Access & rate limiting -------------------------------------------------
# Three kinds of caller:
#   - scripts / tests: X-API-Key header (never sent by the web app);
#   - signed-in web users: session cookie (member3_backend/auth.py); their
#     analyses are saved to their own history;
#   - anonymous web users: no key, no cookie; allowed, with a lower per-IP limit.
# Rate-limit state is in-memory (one process). A multi-worker deployment needs a
# shared store (e.g. Redis) instead.
VALID_API_KEYS = {"dev-key-satyascore-2026"}
RATE_LIMIT_PER_MINUTE = 100          # per API key or per signed-in user
ANON_RATE_LIMIT_PER_MINUTE = 20      # per IP, anonymous
_request_log: dict[str, list[float]] = defaultdict(list)


def _rate_limit(key: str, limit: int) -> None:
    now = time.time()
    _request_log[key] = [t for t in _request_log[key] if t > now - 60]
    if len(_request_log[key]) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} requests/minute",
        )
    _request_log[key].append(now)


def require_api_key(x_api_key: str = Header(..., description="API key for authentication")) -> str:
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    _rate_limit(x_api_key, RATE_LIMIT_PER_MINUTE)
    return x_api_key


def resolve_caller(
    request: Request,
    x_api_key: str | None = Header(None, description="Optional API key (scripts); browsers use the session"),
) -> dict | None:
    """Returns the signed-in user, or None for an API-key or anonymous caller."""
    if x_api_key is not None:
        require_api_key(x_api_key)
        return None
    user = auth.current_user(request)
    if user is not None:
        _rate_limit(f"user:{user['id']}", RATE_LIMIT_PER_MINUTE)
    else:
        _rate_limit(f"ip:{auth.client_ip(request)}", ANON_RATE_LIMIT_PER_MINUTE)
    return user


# --- Request / response schemas ---------------------------------------------

class DetectRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000, description="LLM-generated text to check")
    language: Literal["en", "hi", "mr"] = Field(..., description="Language of the text")
    threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Optional custom Hallucinated/Verified threshold override"
    )
    active_signals: list[Literal["semsim", "nli", "kg"]] | None = Field(
        None, description="Ablation mode: restrict scoring to these signals only"
    )
    include_timings: bool = Field(
        False, description="If true, include per-stage timings_ms in the response (default off)"
    )


class SourceRef(BaseModel):
    """A reference a claim was checked against. role: "supports" / "contradicts" (it
    decided the verdict), "knowledge graph" (Wikidata decided it), "fact-check" (a
    professional fact-check of the same claim decided it; title is the publisher,
    rating its own wording) or "checked"."""
    title: str
    language: str
    url: str
    role: Literal["supports", "contradicts", "knowledge graph", "fact-check", "checked"]
    rating: str | None = None


class ClaimResult(BaseModel):
    claim_id: str
    text: str
    hallu_score: float
    verdict: str
    active_signals: list[str]
    note: str | None = None
    start_char: int          # offset into the original input text (for in-place highlighting)
    end_char: int
    extraction_method: str
    # FR-04 confidence interval: P(Verified) for claims with this score, with a
    # 95% Wilson interval, from the train-split calibration table. None if no
    # table exists for the language (see member1_model/calibration.py).
    p_verified: float | None = None
    p_verified_ci95: list[float] | None = None
    calibration_n: int | None = None
    # Where the claim was checked (Wikipedia articles, Wikidata), deciding one first.
    sources: list[SourceRef] = []


class DocumentResult(BaseModel):
    """Whole-text verdict by share (member1_model/cmhsa.aggregate_document):
    >= 1/3 of claims Hallucinated -> Hallucinated; else any Hallucinated or
    Uncertain claim -> Uncertain; else Verified."""
    verdict: str
    n_claims: int
    n_verified: int
    n_uncertain: int
    n_hallucinated: int
    supported_fraction: float


class DetectResponse(BaseModel):
    claims: list[ClaimResult]
    document: DocumentResult
    overall_score: float  # mean per-claim score; kept for backward compatibility
    processing_time_ms: float

STARTER_TOPICS_EN = [
    # healthcare
    "Dengue_fever", "Immune_system", "Paracetamol", "Type_2_diabetes",
    "Tuberculosis", "Vaccination", "Hypertension", "Insulin",
    "Daily_consumption_of_drinking_water",
    # history
    "Indian_independence_movement", "Jawaharlal_Nehru", "World_War_I",
    "Constitution_of_India", "Mughal_Empire", "Dandi_March",
    "Battle_of_Plassey", "Shivaji", "Non-cooperation_movement", "United_Nations",
    # science
    "Water", "Photosynthesis", "Season", "Speed_of_light", "Vaccine",
    "Mass_versus_weight", "Greenhouse_effect", "Plate_tectonics",
    "Black_hole", "DNA",
    # government
    "Narendra_Modi", "Prime_Minister_of_India",
    "President_of_India", "Fundamental_rights_in_India", "Lok_Sabha",
    "Election_Commission_of_India", "Rajya_Sabha", "Chief_Minister_(India)",
    "Reserve_Bank_of_India", "Governor_(India)", "Article_370",
    # sports
    "Cricket", "Cricket_World_Cup", "India_men's_national_field_hockey_team",
    "Offside_(association_football)", "Indian_Premier_League",
    "Ranji_Trophy", "Formula_One",
]
# NOTE: kept in sync with generate_dataset.py's copy by hand -- the two
# files serve different purposes (live API startup vs. offline dataset
# generation) so sharing a single source of truth would need a small
# shared module; worth doing if this list changes again.


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
MAX_CHUNK_CHARS = 400
MIN_CHUNK_CHARS = 40


def _chunk_article_text(text: str) -> list[str]:
    """Kept identical to generate_dataset.py's copy -- see that file's
    docstring for why full-text chunking replaced short-summary fetching
    (shallow single-summary evidence was root-caused as the reason NLI
    showed near-zero correlation with hallucination and SemSim's class
    distributions overlapped ~94%)."""
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


def _fetch_wikipedia_fulltext(title: str, max_retries: int = 4) -> str | None:
    """Kept identical to generate_dataset.py's fetch_wikipedia_fulltext --
    fetches full article plain text via the Action API instead of the
    REST API's short lead-summary endpoint."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query", "prop": "extracts", "explaintext": 1,
        "titles": title, "format": "json", "redirects": 1,
    }
    for attempt in range(max_retries):
        try:
            # 30s: matches generate_dataset.py. exchars length-cap reverted
            # (anonymous limit far below 20000, collapsed the corpus).
            response = requests.get(url, params=params, headers={"User-Agent": "SatyaScore/1.0"}, timeout=30)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
            for page in pages.values():
                if "missing" in page:
                    return None
                extract = page.get("extract")
                if extract:
                    return extract
            return None
        except requests.RequestException:
            if attempt == max_retries - 1:
                return None
            time.sleep(2 ** attempt)
    return None


# --- App setup ---------------------------------------------------------------

app = FastAPI(
    title="SatyaScore API",
    description="Claim-level, multilingual hallucination detection and scoring.",
    version="0.1.0",
)
# Browser origins allowed to call the API. Default: the local Vite dev server.
# Add others (e.g. a Lovable app) without code changes:
#   $env:SATYASCORE_CORS_ORIGINS = "http://localhost:5173,https://your-app.lovable.app"
import os as _os_cors


def parse_cors_origins(value: str | None) -> list[str]:
    """Comma-separated origins -> list; empty/unset -> the local Vite dev server."""
    origins = [o.strip() for o in (value or "").split(",") if o.strip()]
    return origins or ["http://localhost:5173"]


_CORS_ORIGINS = parse_cors_origins(_os_cors.environ.get("SATYASCORE_CORS_ORIGINS"))
# Accounts, sessions, per-user history, CSRF guard and security headers. Installed
# before CORS so CORS stays the outermost layer (error responses keep CORS headers).
auth.install(app, _CORS_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model/index objects are created once at startup and reused across requests.
# NLIScorer and EntityLinker/WikidataConnector are cheap to construct (they
# lazy-load their actual model/network resources on first real use), so
# it's safe to always include them here rather than making them optional.
_embedder = CrossLingualEmbedder()
# PRD FR-03 IVF index, sized ~sqrt(N) clusters at load time (load_starter_corpus).
# Measured on the demo corpus: identical source recall to exact search, ~7x
# faster per query (results/ivf_vs_flat.md).
_retriever = FAISSRetriever(n_clusters=1)
_retriever_muril = FAISSRetriever(n_clusters=1)  # FR-02 MuRIL fallback index (loaded if built)
_scorer = CMHSAScorer()
_claim_extractor = ClaimExtractor()
_nli_scorer = NLIScorer()
_entity_linker = EntityLinker()
_wikidata = WikidataConnector()

# Load per-language weights trained by member1_model/train_weights.py
# (weights_<lang>.json). Falls back to neutral placeholders for any language
# without a trained file (e.g. Marathi, which is out of committed scope).
import json as _json
from pathlib import Path as _Path

for lang in ("en", "hi", "mr"):
    _wf = _Path(__file__).resolve().parent.parent / f"weights_{lang}.json"
    if _wf.exists():
        _w = _json.loads(_wf.read_text(encoding="utf-8"))
        _scorer.load_weights(lang, alpha=_w["alpha"], beta=_w["beta"], gamma=_w["gamma"])
        print(f"[api] loaded trained weights for {lang}: "
              f"alpha={_w['alpha']:.3f} beta={_w['beta']:.3f} gamma={_w['gamma']:.3f}")
    else:
        _scorer.load_weights(lang, alpha=0.5, beta=0.3, gamma=0.2)
        print(f"[api] no weights_{lang}.json — using placeholder 0.5/0.3/0.2 for {lang}")

# FR-04 calibration tables (build_calibration.py -> calibration_<lang>.json).
_calibration = {lang: t for lang in ("en", "hi", "mr")
                if (t := load_table(_Path(__file__).resolve().parent.parent / f"calibration_{lang}.json"))}

_pipeline = DetectionPipeline(
    embedder=_embedder,
    retriever=_retriever,
    scorer=_scorer,
    claim_extractor=_claim_extractor,
    nli_scorer=_nli_scorer,
    entity_linker=_entity_linker,
    wikidata=_wikidata,
    # Passages NLI reads per claim. 10 on the 102,069-passage index: a recorded product
    # choice (results/topk_eval.md): train correct 130 -> 170 of 303, false alarms 8 -> 11.
    nli_top_k=int(_os_cors.environ.get("SATYASCORE_NLI_TOP_K", "10")),
    # Evidence aggregation (member3_backend/evidence_rules.py): SATYASCORE_AGGREGATION
    # = gated | legacy. Default "gated" is a PRODUCT choice recorded in
    # results/aggregation_eval.md: it cut false alarms on fresh true statements
    # 33 -> 8 of 99 but failed the pre-fixed non-inferiority check (c) and catches
    # far fewer real hallucinations (train 11 -> 3 of 45). "legacy" restores the old rule.
    aggregation=_os_cors.environ.get("SATYASCORE_AGGREGATION", "gated"),
    subjects=SubjectIndex.from_cache(_Path(__file__).resolve().parent.parent / "evidence_corpus_cache.json",
                                     strict=True),  # results/topk_eval.md
)
@app.on_event("startup")
def load_starter_corpus():
    import numpy as np
    base = _Path(__file__).resolve().parent.parent
    # Prefer the largest corpus that is built: expanded (build_corpus_expanded.py:
    # demo + downloaded articles + Wikipedia Vital Articles) > demo > experiment.
    exp_p, exp_v = base / "corpus_passages_expanded.json", base / "corpus_vectors_expanded.npy"
    demo_p, demo_v = base / "corpus_passages_demo.json", base / "corpus_vectors_demo.npy"
    if exp_p.exists() and exp_v.exists():
        passages_path, vectors_path = exp_p, exp_v
    elif demo_p.exists() and demo_v.exists():
        passages_path, vectors_path = demo_p, demo_v
    else:
        passages_path = base / "corpus_passages.json"
        vectors_path = base / "corpus_vectors.npy"

    # Preferred: the cached bilingual (EN+HI) corpus built by build_corpus.py +
    # recompute_signals.py (XLM-R vectors, matching how claims are embedded).
    # Instant, offline, reproducible — no Wikipedia fetch at startup.
    if passages_path.exists() and vectors_path.exists():
        passages = _json.loads(passages_path.read_text(encoding="utf-8"))
        vectors = np.load(vectors_path)
        if len(passages) == vectors.shape[0]:
            import math as _math
            _retriever.n_clusters = max(1, round(_math.sqrt(len(passages))))
            _retriever.build_index([p["id"] for p in passages],
                                   [p["text"] for p in passages], vectors)
            langs: dict[str, int] = {}
            for p in passages:
                langs[p.get("lang", "?")] = langs.get(p.get("lang", "?"), 0) + 1
            print(f"[api] loaded cached bilingual corpus: {len(_retriever)} passages {langs}")
            # FR-02: MuRIL fallback index for transliterated Hindi (built by
            # build_muril_index.py). OFF unless SATYASCORE_MURIL_FALLBACK=true:
            # measured, mean-pooled MuRIL retrieves the source article far less
            # often than XLM-R (Hindi R@3 0.575 vs 0.873; overall -0.194,
            # results/retrieval_comparison.md), so enabling it degrades answers.
            import os as _os
            muril_v = vectors_path.with_name(vectors_path.stem + "_muril.npy")
            if _os.environ.get("SATYASCORE_MURIL_FALLBACK", "false").lower() in ("1", "true", "yes") \
                    and muril_v.exists():
                mv = np.load(muril_v)
                if mv.shape[0] == len(passages):
                    _retriever_muril.n_clusters = _retriever.n_clusters
                    _retriever_muril.build_index([p["id"] for p in passages],
                                                 [p["text"] for p in passages], mv)
                    _pipeline.retriever_muril = _retriever_muril
                    print(f"[api] MuRIL fallback index loaded ({muril_v.name})")
            # On-demand Wikipedia expansion (FR-03 incremental indexing). ON by default:
            # with the gated evidence rule it met its fixed adoption rule
            # (results/unseen_eval.md: train correct 110 -> 125 of 303, false alarms 8 -> 8,
            # hallucinations caught 3 -> 3). SATYASCORE_WIKI_EXPANSION=false turns it off.
            # Needs internet; a failed lookup is skipped. Articles cached in instance/wiki_cache.
            if _os.environ.get("SATYASCORE_WIKI_EXPANSION", "true").lower() in ("1", "true", "yes"):
                from member3_backend.wiki_expander import (WikiExpander, indexed_titles_from_cache,
                                                           indexed_titles_from_passages)
                _pipeline.expander = WikiExpander(
                    _embedder, _retriever, base / "instance" / "wiki_cache",
                    # articles already in the loaded corpus are never added twice
                    indexed=indexed_titles_from_cache(base / "evidence_corpus_cache.json")
                    | indexed_titles_from_passages(passages))
                print("[api] on-demand Wikipedia expansion ON", flush=True)
            # Optional LLM judge (SATYASCORE_LLM_VERIFIER = grounded | open). OFF by
            # default: adopted only if llm_verifier_eval.py meets its fixed rule. Needs
            # GROQ_API_KEY in the server's environment (never logged).
            llm_mode = _os.environ.get("SATYASCORE_LLM_VERIFIER", "").lower()
            if llm_mode in ("grounded", "open"):
                from member1_model.llm_verifier import LLMVerifier
                _pipeline.llm_verifier = LLMVerifier(
                    mode=llm_mode, min_interval_s=float(_os.environ.get("SATYASCORE_LLM_MIN_INTERVAL", "2.2")))
                has_key = bool(_os.environ.get("GROQ_API_KEY"))
                print(f"[api] LLM judge ON ({llm_mode}); GROQ_API_KEY "
                      f"{'set' if has_key else 'MISSING: claims will fall back to NLI'}", flush=True)
            # Professional fact-checks (Google Fact Check Tools API). ON by default: met
            # its fixed adoption rule (results/factcheck_eval.md: 0 wrong decisions on all
            # sets; rumours caught 3 -> 10 of 25; true claims marked Hallucinated 1 -> 1 of
            # 15). SATYASCORE_FACTCHECK=false turns it off. Needs GOOGLE_FACTCHECK_KEY in
            # the server's environment (never logged); without it no fact-check is found.
            if _os.environ.get("SATYASCORE_FACTCHECK", "true").lower() in ("1", "true", "yes"):
                from member2_data.factcheck import FactChecker
                _pipeline.fact_checker = FactChecker(cache_dir=base / "instance" / "factcheck_cache")
                print(f"[api] fact-checks ON; GOOGLE_FACTCHECK_KEY "
                      f"{'set' if FactChecker.available() else 'MISSING: no fact-checks will be found'}",
                      flush=True)
            return
        print("[api] corpus cache size mismatch — falling back to Wikipedia fetch")

    # Fallback (only if the cache is absent): small English starter corpus.
    print("[api] no corpus cache — fetching English starter corpus from Wikipedia...")
    passage_ids, texts = [], []
    for i, title in enumerate(STARTER_TOPICS_EN):
        fulltext = _fetch_wikipedia_fulltext(title)
        if fulltext:
            for j, chunk in enumerate(_chunk_article_text(fulltext)):
                passage_ids.append(f"{title}__chunk{j}")
                texts.append(chunk)
        if i < len(STARTER_TOPICS_EN) - 1:
            time.sleep(0.3)
    if texts:
        result = _embedder.embed(passage_ids, texts, ["en"] * len(texts))
        _retriever.build_index(passage_ids, texts, result.vectors)
        print(f"[api] starter corpus ready: {len(_retriever)} passages indexed.")
    else:
        print("[api] WARNING: corpus failed to load — /detect will return 503.")


@app.on_event("startup")
def _warmup_models() -> None:
    """Task 3: force the NLI model + embedder to load at startup so the first
    /detect request doesn't pay the lazy ~500MB load. Registered after the
    corpus-loading hook, so it runs once the corpus is ready."""
    import time as _t
    t0 = _t.perf_counter()
    _nli_scorer._ensure_loaded()
    print(f"[api] NLI model warmed ({_nli_scorer.device}) in {_t.perf_counter()-t0:.1f}s", flush=True)
    t1 = _t.perf_counter()
    _embedder.embed(["_warmup"], ["warmup"], ["en"])
    print(f"[api] embedder warmed ({_embedder.device}) in {_t.perf_counter()-t1:.1f}s", flush=True)


@app.post("/detect", response_model=DetectResponse)
def detect(request: DetectRequest, user: dict | None = Depends(resolve_caller)) -> DetectResponse:
    if _retriever._index is None or len(_retriever) == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FAISS index is not yet built — no evidence corpus loaded. "
            "Call build_index() on startup with a real passage corpus.",
        )

    active_signals = set(request.active_signals) if request.active_signals else None

    try:
        result = _pipeline.run(request.text, request.language, active_signals=active_signals)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    def _verdict(score) -> str:
        # FR-04: custom threshold override. When provided, it's the single
        # decision boundary — score >= threshold -> Verified, else Hallucinated.
        if request.threshold is not None:
            return "Verified" if score.hallu_score >= request.threshold else "Hallucinated"
        return score.verdict.value

    table = _calibration.get(request.language)

    def _calib(score):
        if table is None or not score.active_signals:  # no evidence -> no calibrated reading
            return {}
        # The table is fitted on NLI-rule scores. A score set by the KG (1.0 / 0.0) or by
        # the LLM judge is on a different scale: looking it up would show e.g. a KG-caught
        # hallucination with "P(Verified) 0.73". No calibrated reading for those.
        if score.note and (score.note == KG_NOTE or score.note.startswith(("judged by LLM", FC_NOTE_PREFIX))):
            return {}
        c = lookup(score.hallu_score, table)
        return {"p_verified": c.p_verified, "p_verified_ci95": list(c.ci95), "calibration_n": c.n}

    hi_titles = _pipeline.subjects.hi_titles

    def _sources(i: int, score) -> list[SourceRef]:
        ev = result.evidence[i] if i < len(result.evidence) else {"passage_ids": [], "deciding": None}
        refs, seen = [], set()
        fc = ev.get("fact_check")
        if fc and (score.note or "").startswith(FC_NOTE_PREFIX):
            refs.append(SourceRef(title=fc["publisher"] or "Fact-check", language=request.language,
                                  url=fc["url"], role="fact-check", rating=fc["rating"]))
        if score.note == KG_NOTE:
            refs.append(SourceRef(title="Wikidata", language="mul", url="https://www.wikidata.org/",
                                  role="knowledge graph"))
        # the NLI's deciding passage is only "the" source when NLI made the verdict
        nli_decided = score.note != KG_NOTE and not (score.note or "").startswith(("judged by LLM", FC_NOTE_PREFIX))
        deciding = ev.get("deciding") if nli_decided else None
        order = ([deciding[0]] if deciding else []) + list(ev.get("passage_ids", []))
        for pid in order:
            title, lang, url = passage_source(pid, hi_titles)
            if (lang, title) in seen:
                continue
            seen.add((lang, title))
            role = deciding[1] if deciding and pid == deciding[0] else "checked"
            refs.append(SourceRef(title=title, language=lang, url=url, role=role))
        return refs

    claims = [
        ClaimResult(
            claim_id=score.claim_id,
            text=claim.text,
            hallu_score=score.hallu_score,
            verdict=_verdict(score),
            active_signals=score.active_signals,
            note=score.note,
            start_char=claim.start_char,
            end_char=claim.end_char,
            extraction_method=claim.extraction_method,
            **_calib(score),
            sources=_sources(i, score),
        )
        for i, (claim, score) in enumerate(zip(result.claims, result.scores))
    ]

    # Aggregate from the FINAL per-claim verdicts (after any threshold override),
    # so the document verdict always agrees with the claims shown.
    doc = aggregate_document([c.verdict for c in claims])
    response = DetectResponse(
        claims=claims,
        document=DocumentResult(
            verdict=doc.document_verdict.value, n_claims=doc.n_claims,
            n_verified=doc.n_verified, n_uncertain=doc.n_uncertain,
            n_hallucinated=doc.n_hallucinated, supported_fraction=doc.supported_fraction,
        ),
        overall_score=result.overall_score,
        processing_time_ms=result.processing_time_ms,
    )
    extra: dict = {}
    if user is not None:
        # Signed-in web user: save to their history (server-side, owner-only).
        extra["analysis_id"] = auth.save_analysis(user["id"], request.text, request.language,
                                                  response.model_dump())
    if request.include_timings:
        extra["timings_ms"] = result.timings_ms
    if extra:
        # Only then: the default API-key response stays byte-identical for existing consumers.
        return JSONResponse(content={**response.model_dump(), **extra})
    return response


MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...), user: dict | None = Depends(resolve_caller)) -> dict:
    """FR-06 file upload: return the plain text of an uploaded .txt or .pdf so
    the dashboard can analyse it. PDF needs pdfminer.six in the API's Python."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB).")
    name = (file.filename or "").lower()
    if name.endswith(".txt"):
        text = data.decode("utf-8", errors="replace")
    elif name.endswith(".pdf"):
        try:
            from io import BytesIO
            from pdfminer.high_level import extract_text as pdf_text
        except ImportError:
            raise HTTPException(status_code=501, detail="PDF upload needs pdfminer.six installed "
                                "in the API's Python environment (pip install pdfminer.six).")
        try:
            text = pdf_text(BytesIO(data))
        except Exception:
            raise HTTPException(status_code=422, detail="Could not read text from this PDF.")
    else:
        raise HTTPException(status_code=415, detail="Only .txt and .pdf files are supported.")
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="The file contains no extractable text.")
    return {"filename": file.filename, "text": text[:20000], "truncated": len(text) > 20000}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "index_size": len(_retriever)}
