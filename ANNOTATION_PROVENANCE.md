# Annotation Provenance — proof that gold_final.csv is human-annotated

Source of record: `final annotator file(Sheet1) (1).csv` (clean UTF-8 export of the annotator's sheet).
Derived gold: `gold_final.csv` (456 claims).

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
Every gold label is reproducible from the human annotator file by a fixed, documented rule; no label is invented. The honest caveat: only the 96 actively-judged claims carry strong human signal; the other 360 are agreement-by-silence with the AI suggestion (single annotator, no second reviewer / IAA yet).
