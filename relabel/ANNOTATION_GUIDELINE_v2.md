# Satya-Score Version 2: Annotation Guideline

**Who:** the four authors, annotators A–D. **How:** blind. You never see the system's verdict or anyone
else's label. Every claim is labelled by **two** of you, independently. Do not discuss claims until the
adjudication meeting.

**Your files:**
- `calibration_20.xlsx`: everyone labels the same 20 claims **first**, then the four of you meet once to
  compare. These 20 are practice and are not used for evaluation.
- `annotator_<X>.xlsx`: your own claims, about 320.

## 1. What you judge
Each row is one claim taken from a chatbot's answer to `source_question`. The whole answer is in
`full_response`. Read it whenever the claim says "it", "this", "यह", "इस", etc. (`needs_context` = TRUE
marks those). Judge only whether the claim is **factually true today**, using evidence you find. Do not
judge whether it is well written or relevant.

| Label | Use it when |
|---|---|
| **Verified** | Every fact in the claim is correct, and you found clear supporting evidence. |
| **Hallucinated** | At least one fact in the claim is wrong, invented, or contradicted by reliable evidence. A partly right, partly wrong claim is **Hallucinated**. |
| **Uncertain** | After a real search you cannot establish it either way, the evidence conflicts, or it is opinion or interpretation. |
| **Not a claim** | The text is broken (garbled, two things glued together, a heading) or contains nothing checkable (advice, a definition-less label). |

"Uncertain" is not a shortcut for claims you didn't research. "Not a claim" is not a shortcut for
claims that are hard to judge.

## 2. Per claim
1. Find the specific factual statement(s) in `claim_text`.
2. Search for reliable sources: Wikipedia, government sites (PIB, ECI, RBI, MoHFW), WHO/CDC, official
   sports bodies, standard textbooks. For Hindi claims an English source is fine.
3. Choose the label. Put the single best source in `evidence_url` (blank for Uncertain or Not a claim),
   and anything useful in `notes`.

**Time:** about 1–3 minutes per claim. If you're at 5 minutes, it is probably Uncertain.

## 3. Edge cases
- **Several facts in one claim:** if any one is false, it is Hallucinated.
- **Rounded numbers** ("about 1.4 billion"): Verified if a reader would accept "about".
- **Facts that changed** (an office-holder, a record): judge against today. If it was true once but is
  false now, it is Hallucinated.
- **Opinion** ("the most important festival"): Uncertain.
- **"Label: description" claims** ("Imperialism: competition for colonies and resources."): judge the
  description as said about the label, in the context of the question.
- **Table rows** ("Battle: First Panipat; Year: 1526; Sides: …"): every cell is a fact. If any is wrong,
  it is Hallucinated.

## 4. Afterwards
Send your sheet back unchanged except for the `verdict`, `evidence_url` and `notes` columns. The merge
script computes agreement between each pair before the adjudication meeting. At the meeting, every
disagreement is resolved together, and the record keeps both original labels.
