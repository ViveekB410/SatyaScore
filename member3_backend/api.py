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

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from member1_model.calibration import load_table, lookup
from member1_model.cmhsa import CMHSAScorer, aggregate_document
from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member2_data.entity_linker import EntityLinker
from member2_data.wikidata_connector import WikidataConnector
from member3_backend.claim_extractor import ClaimExtractor
from member3_backend.faiss_retriever import FAISSRetriever
from member3_backend.pipeline import DetectionPipeline

# --- Auth & rate limiting (dev-grade in-memory implementation) --------------
# NOTE: intentionally simple (hardcoded keys, in-memory rate limit state)
# for local dev/demo. Before deployment, swap VALID_API_KEYS for a real
# store, and the rate limiter for something that survives a restart and
# works across multiple worker processes (e.g. Redis).
VALID_API_KEYS = {"dev-key-satyascore-2026"}
RATE_LIMIT_PER_MINUTE = 100
_request_log: dict[str, list[float]] = defaultdict(list)


def require_api_key(x_api_key: str = Header(..., description="API key for authentication")) -> str:
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    now = time.time()
    window_start = now - 60
    _request_log[x_api_key] = [t for t in _request_log[x_api_key] if t > window_start]

    if len(_request_log[x_api_key]) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {RATE_LIMIT_PER_MINUTE} requests/minute",
        )

    _request_log[x_api_key].append(now)
    return x_api_key


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


class DocumentResult(BaseModel):
    """Whole-text verdict: judged by the worst claim (any Hallucinated claim ->
    Hallucinated; else any Uncertain -> Uncertain; else Verified)."""
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model/index objects are created once at startup and reused across requests.
# NLIScorer and EntityLinker/WikidataConnector are cheap to construct (they
# lazy-load their actual model/network resources on first real use), so
# it's safe to always include them here rather than making them optional.
_embedder = CrossLingualEmbedder()
_retriever = FAISSRetriever(n_clusters=1)  # exact search: the corpus (~2.7k) is far below IVF's useful scale
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
    nli_top_k=3,  # top-3 for accuracy — batched NLI (one forward pass) keeps it fast
)
@app.on_event("startup")
def load_starter_corpus():
    import numpy as np
    base = _Path(__file__).resolve().parent.parent
    # Prefer the bigger demo corpus if built; else the experiment corpus.
    demo_p, demo_v = base / "corpus_passages_demo.json", base / "corpus_vectors_demo.npy"
    if demo_p.exists() and demo_v.exists():
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
                    _retriever_muril.build_index([p["id"] for p in passages],
                                                 [p["text"] for p in passages], mv)
                    _pipeline.retriever_muril = _retriever_muril
                    print(f"[api] MuRIL fallback index loaded ({muril_v.name})")
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
def detect(request: DetectRequest, api_key: str = Depends(require_api_key)) -> DetectResponse:
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
        c = lookup(score.hallu_score, table)
        return {"p_verified": c.p_verified, "p_verified_ci95": list(c.ci95), "calibration_n": c.n}

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
        )
        for claim, score in zip(result.claims, result.scores)
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
    if request.include_timings:
        # Opt-in only, so the default response is byte-identical for existing consumers.
        return JSONResponse(content={**response.model_dump(), "timings_ms": result.timings_ms})
    return response


MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...), api_key: str = Depends(require_api_key)) -> dict:
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
