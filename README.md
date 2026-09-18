# SatyaScore — Full Pipeline (Members 1, 2 & 3)

Cross-lingual embeddings + CMHSA fusion scoring (Member 1), the annotation
pipeline, Wikidata KG connector, and entity linker (Member 2), and the
FastAPI backend + FAISS retrieval + Streamlit dashboard (Member 3) — plus
the Claim Extractor (FR-01, shared infrastructure, not owned by one member
per the PRD's Phase 1 plan). All three CMHSA signals (SemSim, NLI, KG) are
now real and wired together end-to-end.

## What's here

```
satyascore/
├── claim_extractor... (see member3_backend/claim_extractor.py)
├── member1_model/            # ML / Model Lead
│   ├── embeddings.py         # XLM-R primary / MuRIL fallback embedder (FR-02)
│   ├── cmhsa.py               # CMHSA fusion scorer, softmax-constrained weights (7.2, FR-04)
│   ├── nli_scorer.py         # NLI_prob signal — pretrained multilingual model (see honesty note)
│   └── train_weights.py      # Trains per-language alpha/beta/gamma from annotated CSV
├── member2_data/              # Data & Annotation Lead
│   ├── annotation_schema.py  # Claim/Annotation dataclasses, majority-vote adjudication (11.2)
│   ├── iaa.py                  # Cohen's Kappa inter-annotator agreement (11.2, 5.2)
│   ├── wikidata_connector.py # KG_conf signal: Wikidata SPARQL + English-label fallback (FR-03)
│   └── entity_linker.py      # Text -> Wikidata QID/PID resolution (unblocks kg_conf)
├── member3_backend/           # Backend / Systems Engineer
│   ├── claim_extractor.py    # FR-01: dependency-parse decomposition + coreference (English),
│   │                          #   sentence-level (Hindi/Marathi) — see file docstring for scope
│   ├── faiss_retriever.py    # FAISS IVF index, incremental indexing, top-k retrieval (FR-03)
│   ├── pipeline.py             # Orchestrates all 3 signals end to end (Section 7.1)
│   ├── api.py                   # FastAPI /detect endpoint, auth, rate limiting (FR-05)
│   └── dashboard.py           # Streamlit demo UI (FR-06)
├── tests/                     # 65 tests, all passing
└── requirements.txt
```

## One-time setup after `pip install -r requirements.txt`

spaCy's English model doesn't come with the `spacy` package — download it separately:
```
python -m spacy download en_core_web_sm
```
If that fails (some Windows/network setups block it), install directly instead:
```
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
```

## Reproducing the current results (honest bilingual pipeline)

The project's committed result is an honest evaluation on real English+Hindi data.
Full run order (needs internet for the corpus fetch; models are cached after first use):

```bash
# 0. Build the canonical gold dataset from the annotator export (intact Devanagari)
python build_gold_final.py            # -> gold_final.csv  (+ annotation_provenance.py proves it)

# 1. Build the bilingual evidence corpus (EN + langlink-resolved HI Wikipedia)
python build_corpus.py                # -> evidence_corpus_cache.json, corpus_passages.json

# 2. Recompute sem_sim / nli_prob on real bilingual evidence.
#    SLOW on CPU (~30-45 min) — it is NOT hung; process metrics here are unreliable. GPU ~1 min.
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false python recompute_signals.py
#    -> gold_final_scored.csv, corpus_vectors.npy

# 3. Flag broken extraction artifacts, then build the clean train/test split
python flag_quality.py                # -> claim_quality.csv
python make_clean_split.py            # -> gold_train_clean.csv, gold_test_clean.csv

# 4. Train per-language CMHSA weights (add --semsim-vote for the full-fusion variant)
python -m member1_model.train_weights --csv gold_train_clean.csv --languages en hi

# 5. Core experiment: the ablation + the results summary
python honest_ablation.py --train gold_train_clean.csv --test gold_test_clean.csv \
    --out results/ablation_clean_no_semsim.json --table ablation_clean_no_semsim.md
python generate_results_summary.py    # -> RESULTS_SUMMARY.md

# (optional) inter-annotator agreement pilot
python make_iaa_set.py                 # -> iaa/  (two annotators fill iaa_annotator_A/B.xlsx)
python compute_iaa.py                  # -> Cohen's kappa

# 6. Serve the API (loads trained weights + cached bilingual corpus at startup)
uvicorn member3_backend.api:app --reload      # http://localhost:8000/docs
#   or one-command container:  docker compose up --build
```

Read `RESULTS_SUMMARY.md` for the headline numbers and limitations, `ablation_clean_*.md`
for the full ablation, and `ANNOTATION_PROVENANCE.md` for the dataset provenance proof.

## PyCharm setup

1. **Open the project**: File → Open → select the `satyascore/` folder.
2. **Create a venv interpreter**: PyCharm will usually prompt you automatically.
   If not: Settings → Project → Python Interpreter → Add Interpreter →
   Add Local Interpreter → Virtualenv Environment → New, Python 3.10+.
3. **Install dependencies**: open the Terminal tab in PyCharm (bottom bar) and run:
   ```
   pip install -r requirements.txt
   ```
4. **Mark `satyascore/` as Sources Root** if PyCharm doesn't auto-detect the
   `member1_model` package: right-click the `satyascore` folder → Mark
   Directory as → Sources Root. This is what makes
   `from member1_model.cmhsa import ...` resolve inside the IDE.
5. **Run tests**: right-click `tests/test_cmhsa.py` → Run 'pytest in
   test_cmhsa.py'. Or from terminal: `pytest tests/ -v`.

## Quick sanity check without any model downloads

`cmhsa.py` has no heavy dependencies (just `torch` for the tiny 3-parameter
softmax model) and is fully testable offline — that's why `test_cmhsa.py`
passes without touching `embeddings.py` at all. `embeddings.py` needs to
actually download XLM-R/MuRIL weights the first time you run it, so expect
that to be slower and to need network access.

```python
from member1_model.cmhsa import CMHSAScorer, ClaimSubScores

scorer = CMHSAScorer()
scorer.load_weights("en", alpha=0.4, beta=0.4, gamma=0.2)

claim = ClaimSubScores(claim_id="c1", sem_sim=0.82, nli_prob=0.75, kg_conf=0.9)
result = scorer.score_claim(claim, "en")
print(result.hallu_score, result.verdict)
```

## Training weights (once Member 2's annotated data exists)

```
python -m member1_model.train_weights --csv path/to/annotated.csv --languages en hi
```

Expects columns: `claim_id, language, sem_sim, nli_prob, kg_conf, gold_verdict`.

## Next for Member 1

- [ ] Wire `embeddings.py` output into Member 3's FAISS retrieval call
- [ ] Swap the placeholder XLM-R checkpoint for the fine-tuned NLI-DeBERTa
      once Member 2's IndicXNLI fine-tune is ready (`NLI_prob` currently
      has to come from elsewhere — this file only does embeddings)
- [ ] Implement the 5-baseline comparison (Section 4.3) — SelfCheckGPT,
      FActScore-style, TRUE-style, FactKG-style KG-only, MultiHal-style
- [ ] Ablation-mode wiring into the FastAPI layer (Member 3 owns the
      endpoint, but the renormalisation logic already lives in
      `CMHSAScorer.score_claim` and is tested)

---

## Member 2 — Data & Annotation Lead

### Adjudicating multiple annotators into a gold label

```python
from member2_data import Adjudicator, Annotation, Verdict

annotations = [
    Annotation(claim_id="c1", annotator_id="alice", verdict=Verdict.VERIFIED),
    Annotation(claim_id="c1", annotator_id="bob", verdict=Verdict.VERIFIED),
]
result = Adjudicator().resolve("c1", annotations)
print(result.gold_verdict, result.method)  # Verdict.VERIFIED unanimous
```

Ties (e.g. 1 annotator says Verified, the other says Hallucinated) are
flagged with `needs_manual_adjudication=True` rather than silently picked
— per Section 11.2 Step 6, ties need a human adjudicator, not a coin flip.

### Checking inter-annotator agreement (pilot round)

```python
from member2_data import build_iaa_report

report = build_iaa_report(annotations_by_claim)  # dict[claim_id, list[Annotation]]
print(report.mean_kappa, report.recommendation)
```

This flags whether you're still in the 50–100 claim pilot round (Section
11.2 Step 5 / Section 3) and tells you plainly whether to keep annotating,
refine guidelines, or proceed to full-scale annotation, based on the
kappa target (0.65 minimum, 0.75 stretch — Section 5.2).

### Wikidata KG_conf lookups

```python
from member2_data.wikidata_connector import WikidataConnector

wd = WikidataConnector()  # real network call — needs internet, not imported by __init__.py
result = wd.verify_triple(
    subject_qid="Q1058",     # Narendra Modi
    property_pid="P39",      # position held
    expected_value="Q14212", # Prime Minister of India
    language="hi",
)
print(result.confidence, result.used_fallback_label)
```

Results are cached in memory for 24h per FR-03. `used_fallback_label=True`
means the check only succeeded via the English label because Wikidata had
no Hindi label for that entity — worth logging/aggregating across your
dataset to quantify the Hindi coverage gap the PRD calls out (Section 7.2,
16).

**Important — entity linking is NOT included.** This connector assumes you
already know the QID (e.g. `Q1058`) and property PID (e.g. `P39`) for a
claim. Turning free text like "Narendra Modi is the PM of India" into
those IDs is a separate step (entity linking / NER), not yet built — see
todo list below.

## Next for Member 2

- [ ] Build the entity-linking step that turns claim text into
      QID/PID/value triples for `wikidata_connector.py` to check — this is
      the biggest missing piece; without it, `verify_triple` has nothing
      to call it with
- [ ] Implement `get_label_qid_by_string` properly (currently a stub) using
      Wikidata's search API (`wbsearchentities`)
- [ ] Build the pilot-round annotation CLI/interface (Label Studio per
      Section 10.1, or a lightweight custom tool)
- [ ] Recruit the Marathi-fluent annotator (Phase 1 priority per Section 6.2)
- [ ] Wire `dataset_balance_check` into a running dashboard so the ~40/30/30
      Hallucinated/Uncertain/Verified target (FR-07) is visible as
      annotation progresses, not just checked at the end

---

## Member 3 — Backend / Systems Engineer

### Current pipeline status — all 3 CMHSA signals are now wired in

`pipeline.py` now genuinely produces SemSim + NLI + KG_conf, not just
SemSim. Honest caveats on each:

- **SemSim**: fully real — FAISS top-1 retrieval score.
- **NLI_prob**: real, but uses a pretrained public multilingual NLI model
  (`mDeBERTa-v3-base-mnli-xnli`) as a stand-in for the PRD's own
  DeBERTa-v3 + IndicXNLI fine-tune (which needs Member 2's annotated
  dataset to exist first). Swapping in the real fine-tuned checkpoint
  later is a one-line change in `member1_model/nli_scorer.py`.
- **KG_conf**: real, but shallow — only resolves when (a) the claim
  extractor finds >=2 named entities in the claim AND (b) the claim's
  relation phrase matches `entity_linker.py`'s small hand-built lookup
  table (currently ~10 common relations like "is the capital of", "was
  born in"). Claims outside that table get `kg_conf=None`, which
  `CMHSAScorer` already handles correctly via renormalisation. Expanding
  relation coverage is real, scoped, incremental work — not a rewrite.
- **Claim extraction**: real dependency-parse-based decomposition and
  rule-based coreference for English (see `claim_extractor.py`'s
  docstring for exactly what it handles and its documented failure
  modes). Hindi/Marathi are sentence-level only.

### Running the API

```
uvicorn member3_backend.api:app --reload
```
Visit `http://localhost:8000/docs` for interactive Swagger docs. First
request will be slow (NLI model downloads + loads, ~500MB) — subsequent
requests are fast since everything's cached in memory after that.

**`/detect` returns 503 until a FAISS index is built** — there's no
evidence corpus loaded yet (Section 11 dataset work). Try locally with:
```python
from member3_backend.api import _retriever, _embedder
result = _embedder.embed(["p0"], ["The Ganga originates in Gangotri."], ["en"])
_retriever.build_index(["p0"], ["The Ganga originates in Gangotri."], result.vectors)
```
Dev API key: `dev-key-satyascore-2026` (send via `X-API-Key` header).

### Running the dashboard

```
streamlit run member3_backend/dashboard.py
```
Needs the API running separately — it's just a UI calling `/detect`.

### Ablation mode

Pass `"active_signals": ["semsim"]` (or any subset) in the request body,
or use the dashboard's sidebar checkboxes — reproduces Section 5.1's
ablation study directly, per FR-04.

## Next for Member 3 / overall project

- [ ] Load a real evidence corpus into `FAISSRetriever` on startup
      (Section 11.1 — Multilingual Wikipedia) instead of manual index building
- [ ] Docker containerization (Section 10) — not yet built
- [ ] File upload support (.txt, .pdf) in the dashboard (FR-06) — not yet built
- [ ] GitHub CI/CD — not yet built
- [ ] Swap in-memory rate limiter/API key store for something durable
      before real deployment (see comment in `api.py`)
- [ ] Fine-tune the real DeBERTa-v3 + IndicXNLI model once Member 2's
      annotated dataset exists (swaps into `nli_scorer.py`)
- [ ] Expand `entity_linker.py`'s relation coverage beyond the current
      ~10 hand-built relation phrases
- [ ] Real dataset generation (Section 11.2) — the actual 3,000+ claim
      benchmark dataset doesn't exist yet; everything's been tested
      against small synthetic/toy examples so far
- [ ] 5-baseline comparison (Section 4.3) — SelfCheckGPT, FActScore-style,
      TRUE-style, FactKG-style KG-only, MultiHal-style — not yet built
