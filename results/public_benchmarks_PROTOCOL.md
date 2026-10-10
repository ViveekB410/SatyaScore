# Public-benchmark evaluation: protocol (fixed 2026-10-10, BEFORE any run)

Purpose: report how the live system performs on two public, human-labelled benchmarks, so that results can
be compared with other work. **Reported only**: nothing in the system is changed on the basis of these runs
(no threshold, rule or model is tuned on them). Script: `public_benchmark_eval.py`.

## System under test
The live configuration of the web app, unchanged: gated evidence rule, on-demand Wikipedia expansion, official
statistics + Wikidata (deciding when they answer), published fact-checks (Google Fact Check Tools API; key read
from the shell). From the same run, an **NLI-only** verdict is also derived for every claim (the evidence-rule
score alone, ignoring statistics, Wikidata and fact-checks), to show what the structured sources add.
Verdict tiers as in the app: score < 0.35 Hallucinated, > 0.65 Verified, otherwise Uncertain; a missing score
is Uncertain.

## 1. FEVER (English; Thorne et al., NAACL 2018), `paper_dev` split
- Data: `benchmarks/data/fever_paper_dev.jsonl` (https://fever.ai/download/fever/paper_dev.jsonl, CC BY-SA 3.0).
- Sample: 150 SUPPORTS + 150 REFUTES claims drawn at random with seed 20261010. NOT ENOUGH INFO is excluded
  (it has no true/false gold label).
- Each claim is sent to the system as one text (English). If the extractor splits it into several claims, the
  whole-text verdict is used (as in `factcheck_eval.py`).
- Measures, each with a 95% Wilson interval: SUPPORTS -> Verified (correct), Hallucinated (false alarm),
  Uncertain; REFUTES -> Hallucinated (caught), Verified (missed), Uncertain; accuracy over decided claims;
  share of claims decided.
- Caveat stated in the report: FEVER labels refer to Wikipedia of 2017; the system reads today's Wikipedia and
  Wikidata.

## 2. Mu-SHROOM (SemEval-2025 Task 3; Vázquez et al.), test split, Hindi and English
- Data: `benchmarks/data/mushroom_{hi,en}_test.parquet` (Helsinki-NLP/mu-shroom on Hugging Face, CC BY 4.0):
  150 Hindi and 154 English model answers with character spans marked as hallucinated by annotators.
- Each `model_output_text` is sent to the system in its language. Predicted hallucinated characters = the union
  of the character spans of the claims the system marks Hallucinated.
- Official task measure: **IoU** of predicted and gold (`hard_labels`) character sets per answer, averaged over
  answers (an answer with no gold and no predicted span scores 1). Also reported: the **Spearman correlation**
  between per-character predicted probabilities (1 - claim score inside a claim, 0 outside) and the gold
  `soft_labels` probabilities, averaged over answers (task convention: constant vectors give 0 unless both are
  constant).
- Baselines on the same data, computed by the same code: **mark-all** (every character hallucinated) and
  **mark-none**.
- Also reported: share of answers with at least one claim flagged; precision of flagged claims (share whose span
  overlaps a gold span).

## What will not be done
No re-runs with changed settings to obtain better numbers. If a run fails part-way (network), it is resumed
from its cache and the failure is recorded in the report.
