# SatyaScore — Guide Review Brief

**A claim-level, bilingual (English + Hindi) hallucination detector for LLM output.**
Given any AI-generated answer, it splits it into atomic factual claims, checks each against
a retrieved evidence corpus, and flags the ones not supported — highlighted in place.

---

## 1. It works — live demo (lead with this)

Backend + frontend run locally:

```
# terminal 1 (backend)
python -m uvicorn member3_backend.api:app --port 8000
# terminal 2 (frontend)
cd frontend && npm run dev      # http://localhost:5173
```

**Demo script (30 seconds):**
1. Open http://localhost:5173 — the app connects to the backend automatically.
2. Click the **"Capital of Japan (wrong)"** example → *"The capital of Japan is Beijing."*
3. Press **Analyse**. The false claim is underlined in red and listed under *Flagged claims*
   as **NOT SUPPORTED BY EVIDENCE**.
4. Try a true one ("Capital of France") → passes. Try the Hindi chips → bilingual.

Evidence corpus: **9,351 passages**. No raw scores shown to the user — just the verdict,
by design.

---

## 2. What is built (all real, all in the repo)

- End-to-end pipeline: claim extraction → cross-lingual retrieval (FAISS) → NLI +
  semantic-similarity + knowledge-graph signals → CMHSA fusion → verdict.
- FastAPI backend (`/detect`, `/health`), React + Vite frontend, Docker.
- **114 automated tests passing.**
- Reproducible evaluation + tooling: honest ablation, ROC-AUC, latency benchmark (GPU),
  retrieval diagnostic, inter-annotator-agreement pipeline, provenance audit.

---

## 3. Results — stated honestly

**Data reliability (the headline positive).** A blind round-2 re-annotation (two annotators,
50 `ai_agreed` claims, AI verdict hidden) reproduced the existing gold labels **98%** of the
time where the two annotators agreed (EN 96%, HI 100%), with **92% raw human agreement**.
This is direct evidence the labels are trustworthy without the AI anchor.

- *Why the kappa looks low (0.30) even so:* the sample is ~96% one class ("Verified"), so
  chance agreement is high and Cohen's kappa has almost nothing to discriminate — a known
  base-rate artifact. Raw agreement + the reproduction rate are the meaningful numbers, and
  we report the kappa with its (wide) confidence interval rather than hiding it.

**Detector performance (the honest finding).** On the current data the fused signals sit near
chance (ROC-AUC ≈ 0.56 EN). We **pre-registered** this possibility and report it plainly. The
diagnosis is concrete: the dataset is small and class-imbalanced (only 9 Hindi hallucinated
claims), which caps how well any detector can score — not a bug in the method. A controlled
follow-up (C2-lite, sentence-level premises) was tested with a paired-bootstrap CI and
**correctly rejected** (ΔAUC −0.012, 95% CI crosses 0) — i.e., we don't ship changes that
aren't supported.

**Latency (target met on GPU).** Median **104 ms/claim** on a T4 (PRD target < 500 ms met).

---

## 4. Limitations (stated up front — this is a strength)

- Single primary annotator for the full set; round-2 blind re-annotation validates it but is
  pilot-sized (n = 50).
- Class imbalance, especially Hindi hallucinated claims (n = 9).
- Detector accuracy is data-bound; scaling annotation is the main lever.
- Uses a strong pretrained multilingual NLI model as a stand-in for the PRD's fine-tuned one.

---

## 5. Likely questions — and honest answers

**"Does it actually detect hallucinations?"** — Yes on clear in-corpus cases (live demo). On
the held-out eval the signals are near chance, which we attribute to dataset scale/imbalance
and show with the ablation and diagnostics. The *system* works; the *scores* need more data.

**"Your kappa is only 0.3 — isn't your labeling unreliable?"** — Raw agreement is 92% and blind
re-annotation reproduces gold 98%. The 0.3 is a base-rate artifact of a near-single-class
sample; we report it with its CI rather than a misleading headline.

**"Only one annotator?"** — Yes for the full set; the round-2 blind study is the check on that,
and it came back strongly (98% reproduction). Next step is a larger, verdict-balanced round.

**"What would you do next?"** — Scale annotation (especially Hindi hallucinated claims) and a
verdict-balanced IAA round; the engineering is done and reproducible.

---

_Every number here traces to a committed artifact: `results/label_audit.md`,
`results/c2_lite_comparison.md`, `results/latency_benchmark.md`, `RESULTS_SUMMARY.md`,
`ANNOTATION_PROVENANCE.md`, and the 114-test suite._
