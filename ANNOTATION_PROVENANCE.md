# Annotation Provenance — proof that gold_final.csv is human-annotated

Source of record: `final annotator file(Sheet1) (1).csv` (clean UTF-8 export of the annotator's sheet).
Derived gold: `gold_final.csv` (456 claims).

## 0. Review protocol
- Review was **full, not sampled**: the annotator reviewed every one of the AI-suggested verdicts in the sheet.
- The annotator wrote a verdict only when they **disagreed** with the AI. A blank annotator field (or 'ok') therefore means **"reviewed and agreed"**, not "not reviewed".
- Limitation: review happened with the AI verdict visible, which biases toward agreement (anchoring). The blind round-2 re-labelling (`results/label_audit.md`) measures this directly.

## 1. Traceability
- Gold claims: 456 | Source claims: 456
- Gold claims with NO matching source row (should be 0): **0**
- Source claims missing from gold (should be 0): **0**

## 2. Label fidelity (gold == independently recomputed human rule)
- Claims cross-checked: 456
- Verdict mismatches (should be 0): **0**

## 3. How much is genuine human judgement?
- Total claims: 456
- **Actively human-judged** (annotator wrote a verdict): **96**
- Agreed-with-AI by leaving blank / 'ok': 360
- Per language (size = total, sum = actively human-judged):
          size  sum
language           
en         266   71
hi         190   25

## 4. Gold verdict distribution
language  gold_verdict
en        Hallucinated     47
          Uncertain        26
          Verified        193
hi        Hallucinated      9
          Uncertain        18
          Verified        163

- Hindi gold rows with intact Devanagari: 190/190

## Verdict: PROVEN
Every gold label is reproducible from the human annotator file by a fixed, documented rule; no label is invented. The honest caveat: 96 labels are human overrides/confirmations and 360 are reviewed-and-agreed with the AI suggestion, reviewed with the AI verdict visible (anchoring) by a single annotator. Two blind inter-annotator rounds check this: round 1 (`iaa/`) and round 2 (`results/label_audit.md`).
