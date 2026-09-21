# SatyaScore — Project Status

**As of:** 2026-09-22 · **Overall PRD completion: ~60–65%**

Claim-level, bilingual (English + Hindi) LLM hallucination detector using the CMHSA
score (`HalluScore = α·SemSim + β·NLI + γ·KG`, per-language softmax weights; verdicts
Hallucinated / Uncertain / Verified). B.Tech capstone, 4 members.

---

## Headline

The **system is built and tested; the scientific result is an honest negative one.** The
detector's signals sit near chance because of the **dataset**, not the code — and the PRD
pre-registered this outcome (§15) as acceptable. The defensible capstone is the working
system + rigorous methodology + documented findings, all largely in place. The single
highest-leverage lever left is **more annotated hallucinated claims, especially Hindi.**

---

## Status by workstream

| Workstream | Owner | Done | Notes |
| --- | --- | --- | --- |
| **Backend / model** | Vivek (M1+M3) | **~92%** | Feature-complete, 114 tests green |
| **Frontend** | teammate | **~85%** | Working React SPA; not yet deployed |
| **Paper / patent** | teammate | — | Owner to report status |
| **Dataset / annotation** | shared | see below | The real ceiling on results quality |

---

## Backend — what's done (~92%)

- CMHSA pipeline + `/detect` API on trained per-language weights; FR-04 threshold param.
- Cross-claim **NLI batching**, stage timings, startup warm-up, and **fixed-size NLI
  chunking** (bounds GPU memory — fixed a T4 OOM and a matching production risk).
- FAISS retrieval; two separate corpora (experiment 2,674 passages / demo 9,351).
- Bilingual signals recomputed in one XLM-R vector space; honest eval + ablation.
- **IAA pilot**, provenance proof, data-quality flagging, Phase 3 retrieval diagnostic.
- **C2-lite (sentence-level NLI premises)** evaluated on GPU and closed as a documented
  negative result (see Findings).
- Docker + docker-compose; Colab GPU runbook (secure token-header push); full README.

**Remaining (~8%, all non-blocking):** GPU deployment for the PRD latency target
(<500ms/claim — code is ready, CPU is the only bottleneck); a few skipped items (fp16
serving, env-driven CORS, KG on/off toggle); and the PRD's *fine-tuned* DeBERTa-on-IndicXNLI
was never trained — we run a strong pretrained multilingual stand-in (one-line model swap
when a checkpoint exists).

---

## Key findings (the story of the project)

- **Signals are near chance.** ROC-AUC ≈ 0.56–0.58 (EN), ≈ 0.42–0.51 (HI). No fusion
  configuration beats an always-"Verified" baseline; fusion collapses to NLI; KG is
  inapplicable (0% coverage on this data).
- **C2-lite did not help.** Sentence-level premises: EN ΔAUC −0.012, paired-bootstrap 95%
  CI [−0.121, +0.094] (straddles 0). Neutral rate even rose 0.67 → 0.80. Kept behind an
  off-by-default switch as a recorded negative result.
- **Extraction quality is itself a finding.** Rule-based English decomposition produces 44
  broken fragments (17% of EN); Hindi (sentence-level) is clean. Report on the well-formed
  412-claim subset.

---

## Dataset / annotation — the ceiling

- 456 gold claims: **EN** 193 Verified / 47 Hallucinated / 26 Uncertain; **HI** 163 / 9 / 18.
- **Single annotator.** IAA pilot: binary "hallucination vs not" κ = **0.61** (well-formed)
  — substantial and near the PRD target; 3-class κ = 0.15 (Verified/Uncertain boundary).
- **Severe class imbalance — only 9 Hindi hallucinated claims.** This, more than anything,
  caps how good the results can look.

---

## Risks & blockers

1. **Results quality is data-bound, not code-bound.** More backend work will not move the
   accuracy numbers.
2. **Paper/patent status is unknown to the backend lane** — needs an owner update.
3. **Nothing is deployed live** (frontend + API) — a demo needs a GPU host.

## Highest-leverage next steps (in order)

1. **Annotate more hallucinated claims, especially Hindi** (the one lever that moves results).
2. Write the paper around the **honest methodology + negative result** (already defensible).
3. GPU-host the API + frontend for a live demo.

---

_Numbers trace to: `gold_final.csv`, `RESULTS_SUMMARY.md`, `results/c2_lite_comparison.md`,
`iaa/`, `ANNOTATION_PROVENANCE.md`, and the 114-test suite. Backend is reproducible from the
README run-order._
