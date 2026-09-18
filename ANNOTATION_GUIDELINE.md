# SatyaScore Pilot Annotation Guideline (v1)

**File to annotate:** `pilot_annotation_BLIND.csv` (59 claims)
**Annotators needed:** all 2-3 annotators label **every one of the 59 rows** —
do NOT split the file between annotators. IAA cannot be computed without full
overlap (see `iaa.py`).
**Target agreement:** mean pairwise Cohen's Kappa ≥ 0.65 (stretch: ≥ 0.75).

---

## 1. What you're judging

Each row is one **atomic claim** extracted from an LLM's answer to a question.
You are NOT judging whether the claim is well-written or relevant — only
whether it is **factually true**, based on evidence you can find.

For each row, assign exactly one verdict:

| Verdict | Meaning |
|---|---|
| **Verified** | The claim is factually correct and you found clear supporting evidence. |
| **Hallucinated** | The claim is factually wrong, fabricated, or contradicted by evidence. |
| **Uncertain** | You could not find enough evidence either way, OR the claim is a matter of interpretation/opinion, OR evidence conflicts. |

Do not use "Uncertain" as a default for claims you didn't bother researching —
it should reflect genuine evidential ambiguity, not annotator effort.

## 2. Step-by-step process per claim

1. Read `claim_text`. Identify the specific factual assertion (a claim may
   look like a sentence fragment — that's expected, it's the output of
   automatic decomposition, not a full sentence).
2. Search for evidence (Wikipedia, government sites, reputable news, domain
   sources — e.g. WHO/CDC for healthcare claims, ECI/PIB for Indian
   government claims).
3. Decide the verdict using the table above.
4. Fill in `evidence_url` with the single best source you used. If verdict is
   Uncertain due to lack of evidence, leave `evidence_url` blank.
5. Move to the next claim.

**Time budget guidance:** aim for ~2-3 minutes per claim. If you're spending
much longer, it's likely an Uncertain case — don't rabbit-hole.

## 3. About this file

You're annotating `pilot_annotation_BLIND.csv` — this copy has had SatyaScore's
own automated signal columns (its own guesses) removed on purpose, so your
judgment stays independent and isn't biased by seeing the model's own answer
before you form yours. You don't need to do anything else to protect against
this — just annotate the file as given.

## 4. Edge cases (read before you start)

- **Multi-part claims that got merged instead of split**: if `claim_text`
  bundles two facts (a known limitation of the extractor for compound
  sentences), judge the claim as a whole — if any part is false, it's
  Hallucinated.
- **Numeric claims with rounding** ("about 30%" vs actual 28%): treat as
  Verified if within a reasonable margin a reader would consider "about"
  correct; use judgment, don't require exact match.
- **Outdated-but-was-true-at-training-time claims** (e.g. a stat that changed
  since the LLM's training cutoff): mark Hallucinated if currently false,
  regardless of whether it was once true — SatyaScore is judging the claim
  against current reality, not the model's excuse.
- **Opinion/subjective claims** ("X is the most important festival in India"):
  Uncertain — these aren't factually verifiable.
- **Hindi (`hi`) claims**: if you can't find a Hindi-language source but find
  a solid English one confirming/denying the same fact, that's fine — use it,
  note the source is in English.

## 5. Why this matters (context, not required reading to annotate)

Your annotations feed directly into:
- `iaa.py` — computes agreement between all annotator pairs; if mean κ < 0.65
  after this pilot, the guideline gets revised BEFORE the remaining 450 claims
  are touched (that's the whole point of doing a pilot first).
- `annotation_schema.py`'s `Adjudicator` — ties (e.g. 1-1-1 split across all
  three verdicts, or one annotator vs one annotator with no majority) get
  flagged as `needs_manual_adjudication=True` rather than auto-resolved, so
  expect some claims to come back to you for a group discussion.
- The target dataset balance is ~40% Hallucinated / 30% Uncertain / 30%
  Verified (per `dataset_balance_check`) — you don't need to force this
  balance yourself, just label honestly; it's a sanity check applied after.

## 6. After all annotators finish the 59 claims

Send your completed CSV back to the annotation lead. Once all 2-3 annotators
have submitted, the lead runs the combined results through `iaa.py`. If mean
κ ≥ 0.65: the remaining 450 claims get annotated next using this same
guideline. If κ < 0.65: the group reviews the specific claims with
disagreement, the guideline gets revised, and a fresh pilot round happens
before continuing.
