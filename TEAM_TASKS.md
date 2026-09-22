# SatyaScore — Team Tasks

This is the work only people can do. The code is done; what's left is making sure our **labels** can be trusted.

---

## Why we're doing this

When someone asks *"How do you know your labels are right?"*, we currently have a weak answer:

- **79% of our labels were reviewed while the AI's answer was visible.** The annotator checked every one and only wrote a verdict where they disagreed — but seeing an answer first pulls anyone toward agreeing with it. This is called *anchoring*, and it happens to everyone. When two people judged 56 claims *without* seeing the AI's answer, they matched our labels only 73% and 36% of the time.
- In our agreement test, **one annotator never used "Uncertain" at all** while the other used it for 38 of 56 claims. We were following different rules, so our agreement score doesn't mean much.
- Our test set has only **9 English and 2 Hindi** hallucinated claims — too few to say anything confident, especially about Hindi.

None of this means anyone did careless work. It means we need to show our labels hold up when judged blind. The tasks below do that, and help with the small test set.

---

## Who does what

| Task | Who | Time |
|---|---|---|
| 1. Calibration meeting | Annotator A, Annotator B, and Vivek to run it | 1 hour, together |
| 2. Label 50 claims alone | Annotator A and Annotator B, separately | 2–3 hours each |
| 3. Paper wording check | Paper writer | 1–2 hours |
| 4. More Hindi claims (optional) | Anyone with time | 6–8 hours |

**Annotator A and B should be two different people** — ideally the same two from the first round. Neither of them should be the person who made the original gold labels, if possible.

Claude Code prepares all the files first. **Don't start until you have them** — they'll be in the `annotation_round2/` folder.

---

## Task 1 — Calibration meeting (together, 1 hour)

**Goal:** agree on what each label means, *before* labelling alone. Last time we skipped this, and it's why the two annotators ended up using different rules.

**File:** `annotation_round2/calibration_10.xlsx` — 10 claims.

**How to run it:**

1. Before the meeting, both annotators read `ANNOTATION_GUIDELINE.md` once.
2. In the meeting, go through the 10 claims **one at a time**:
   - each person decides a label silently and writes it down;
   - then both say their answer out loud;
   - if you disagree, talk it through until you agree *why*.
3. Pay special attention to **Uncertain**. Agree on concrete rules, for example:
   - *"If I search for 3 minutes and find nothing either way, it's Uncertain."*
   - *"If the claim is an opinion, it's Uncertain."*
   - *"If one part of the claim is false, the whole claim is Hallucinated."*
4. Write down every rule you agree on in a short file: `annotation_round2/CALIBRATION_DECISIONS.md`. Five to ten bullet points is enough.

**Deliverable:** `CALIBRATION_DECISIONS.md`. The 10 calibration claims do **not** count toward the agreement score — they're practice.

---

## Task 2 — Label 50 claims alone (2–3 hours each)

**Goal:** a trustworthy agreement score between two people, **and** a check on whether our existing labels hold up when the AI's answer is hidden. One piece of work answers both questions.

**Files:**
- Annotator A → `annotation_round2/round2_annotator_A.xlsx`
- Annotator B → `annotation_round2/round2_annotator_B.xlsx`

Both files contain the **same 50 claims**: 30 English, 20 Hindi.

### How to label each claim

1. Open your file in **Excel**. Hindi displays correctly in Excel; Google Sheets sometimes breaks it.
2. For each row, read:
   - **source_question** — what the AI was asked;
   - **claim_text** — the one fact you must judge;
   - **full_response** — the AI's whole answer, for context.
3. Search for the truth. Good sources: Wikipedia, government websites, WHO/CDC for health, reputable news. For Hindi claims, an English source is fine.
4. In the **verdict** column, pick one option from the dropdown:

| Choose | When |
|---|---|
| **Verified** | The claim is correct and you found a source that confirms it. |
| **Hallucinated** | The claim is wrong, made up, or a source contradicts it. |
| **Uncertain** | You genuinely can't tell — no clear evidence, sources disagree, or it's an opinion. |

5. Paste the best source link into **evidence_url**. You can leave it blank if the verdict is Uncertain because nothing was found.
6. Write anything unusual in **notes**.

### Rules — please follow strictly

- **Work completely alone.** Don't discuss claims, compare answers, or look at each other's file until **both** files are handed in. If you talk, the agreement score becomes meaningless.
- **Use all three labels when they fit.** Last time one person never chose Uncertain. If a claim is genuinely unclear, Uncertain is the correct answer — not a failure.
- **Don't use Uncertain to skip work.** Research first. Uncertain means "I looked, and it's unclear", not "I didn't check".
- **Follow `CALIBRATION_DECISIONS.md`** from Task 1.
- **Don't look for the AI's answer.** It's hidden from you on purpose, so you judge independently.
- **Aim for 2–3 minutes per claim.** If you're stuck past 5 minutes, it's probably Uncertain — note why and move on.
- **Fill every row.** Blank rows can't be used.

**Deliverable:** your completed `.xlsx`, sent to Vivek.

---

## Task 3 — Paper wording check (paper writer)

**Goal:** make sure the paper only claims what we can defend.

Wait until Claude Code has regenerated `RESULTS_SUMMARY.md`, then check the paper against these lists.

### Safe to claim

- The full system is built: bilingual (English + Hindi), claim-level, with a working API, frontend, and 114 automated tests.
- **Speed, on GPU:** 104 ms median per claim; 2.4 seconds for a 10-claim document. Both meet the targets. Always say "on GPU, median".
- The detector performs near chance on real hallucinations, and no setting beats simply answering "Verified" every time.
- The knowledge-graph check found **0 usable matches out of 576 claims** — it doesn't work for descriptive claims.
- Similarity between claim and evidence measures *topic*, not *truth*.
- Our test of shorter evidence (sentence-level) made **no significant difference**, with confidence interval reported.
- Our labelling protocol: every AI verdict was reviewed, with changes written only where the annotator disagreed — plus the anchoring limitation, the mismatch in the first agreement test, and the round-2 results once they're in.

### Do NOT claim

- "Real-time" on its own — always "on GPU, median".
- "Substantial agreement", or κ = 0.61 as the headline. Use **0.53**, and explain it.
- That the detector fails *because of* the dataset. Say it's the **leading hypothesis**.
- Any Hindi result as proven — it rests on only 9 hallucinated claims.
- "GPU gives under 1 second" — that was an old guess. Use the measured numbers.
- "The neutral rate increased" as a finding — the comparison isn't fair.
- A hallucination F1 score without saying how many hallucinated claims it came from.

**Deliverable:** a paper draft where every number matches `RESULTS_SUMMARY.md`.

---

## Task 4 — More Hindi hallucinated claims (optional, if time allows)

**Goal:** we have only 9 hallucinated Hindi claims. Around 30–40 would let us say something real about Hindi.

**Be realistic about the effort.** Only about 1 in 20 Hindi claims turns out hallucinated, so collecting 30 more means labelling roughly 200–300 claims. Harder questions help.

### How

1. **Write 40 hard questions in Hindi**, the kind AI models often get wrong:
   - specific dates ("किस वर्ष…"), numbers, and statistics;
   - lesser-known people, places, and events;
   - regional Indian history, government schemes, and local facts.

   Avoid famous facts like "capital of India" — the AI gets those right.
2. Send the list to Vivek. Claude Code generates the AI answers and splits them into claims.
3. Label the resulting sheet the same way as Task 2.

### Important

- **Never edit a claim** to make it wrong. Our whole finding is about *naturally occurring* mistakes; a made-up error ruins that.
- Record in the paper that these questions were deliberately chosen to be hard, since that changes how the set was built.

---

## Order and timeline

1. Claude Code prepares the files. *(Vivek triggers it.)*
2. **Task 1**, calibration meeting — one sitting.
3. **Task 2**, both annotators label alone — within 2–3 days.
4. Vivek sends both sheets back to Claude Code, which computes the new scores.
5. **Task 3**, the paper writer updates wording against the new results.
6. **Task 4** only if there's time left.

Tasks 1 and 2 matter most. Together they give us a real answer to *"How do you know your labels are right?"* — the hardest question we'll face.
