# IAA Labeling Task — 56 claims

You are one of **two** people labeling the SAME 56 claims, **independently**.
Do NOT discuss or compare until both files are submitted — that is the whole point.

Open **your .xlsx** in Excel (Hindi displays correctly):
- Annotator A -> `iaa_annotator_A.xlsx`
- Annotator B -> `iaa_annotator_B.xlsx`

## Each row gives you
- **source_question** — the question the AI was asked (context)
- **claim_text** — the ONE atomic claim you must judge
- **full_response** — the AI's whole answer, to understand fragment claims

## Fill the `verdict` column (dropdown) with one of:
| Verdict | Meaning |
|---|---|
| **Verified** | Factually correct; clear supporting evidence. |
| **Hallucinated** | Factually wrong, fabricated, or contradicted by evidence. |
| **Uncertain** | Can't confirm or deny — real ambiguity, opinion, or missing/conflicting evidence. (NOT "didn't check".) |

**If the claim bundles several facts (common in Hindi):** judge it by its WORST part —
any part false -> Hallucinated; else any part unverifiable -> Uncertain; else Verified.
Note the offending part in `notes`.

- Judge **only the `claim_text`**, using the question/response for context. Judge factual truth, not writing quality.
- Put your best source in `evidence_url` (blank OK for Uncertain-no-evidence).
- Hindi rows: an English source confirming/denying the same fact is fine.
- ~2-3 min per claim.

## When done
Save and send both completed .xlsx files back. Kappa is computed with
`compute_iaa.py`; target >= 0.65 (PRD 5.2). A low number means we tighten the
guideline and relabel — the normal pilot outcome, not a failure.
