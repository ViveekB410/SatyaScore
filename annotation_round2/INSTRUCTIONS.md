# Round-2 Annotation — Instructions

Thank you for helping label these claims. Please read this page fully before you start.
It takes about **2–3 minutes per claim**.

## What you are doing

You are judging whether each **claim** is factually true, based on evidence — not on

grammar or writing style. Two people label the **same** claims separately, so we can
measure how much independent annotators agree.

## Step 1 — Calibration first (do this together, once)

Before the real set, everyone labels **`calibration_10.xlsx`** (10 claims). Then the team
meets, compares answers, and agrees on how to handle the tricky cases. Write those agreed
decisions into a short **calibration decisions** note and keep it beside these files.
This shared understanding is what makes the real round consistent.

## Step 2 — Label your own file, alone

- Annotator A → open **`round2_annotator_A.xlsx`**
- Annotator B → open **`round2_annotator_B.xlsx`**

Open it in Excel (Hindi text displays correctly there). For each row, use the
**`verdict`** dropdown to choose exactly one label:

| Label | Use it when… |
|---|---|
| **Verified** | The claim is factually correct and you can find clear supporting evidence. |
| **Hallucinated** | The claim is factually wrong, made up, or contradicted by evidence. |
| **Uncertain** | You genuinely cannot confirm or deny it — real ambiguity, opinion, or missing/conflicting evidence. |

**All three labels are required where they apply.** "Uncertain" is **not** optional and it
is **not** a way to skip a claim — use it whenever the evidence is genuinely unclear. If you
find yourself never using one of the labels, stop and re-read the guideline: a real set of
claims will contain all three.

Also fill:
- **`evidence_url`** — your best supporting source (you may leave it blank only for an
  Uncertain claim where no evidence exists).
- **`notes`** — optional; if a claim bundles several facts, note which part decided your label.

**Judging bundled claims:** judge the claim by its **worst** part — if any part is false it is
Hallucinated; otherwise if any part is unverifiable it is Uncertain; otherwise Verified.

## Rules that matter

- **Work alone.** Do **not** discuss the claims or compare answers with the other annotator
  until **both** files have been returned. Independent labels are the whole point.
- **Follow `ANNOTATION_GUIDELINE.md`** (the shared labelling guideline) together with the
  calibration decisions note the team wrote in Step 1. If the two ever seem to conflict, the
  calibration note wins for these claims.
- Judge the **claim_text** only; use `source_question` and `full_response` for context.
- For a Hindi claim, an English source that confirms or denies the same fact is fine.

## When you are done

Save your `.xlsx` (keep the filename) and send it back. Do not edit the other columns.
Agreement is computed with `compute_round2.py`.
