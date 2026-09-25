# Round 3 — Annotation Rules

You will label **45 short factual claims** about people, places and organisations. Each claim
comes from an AI chatbot's answer. Your job: decide whether the claim is **true**, using
reliable sources. Please read this whole page before you start. It takes about **2 minutes per
claim** (about 1.5–2 hours in total).

---

## 1. The three labels

| Label | Use it when |
|---|---|
| **Verified** | Every fact in the claim is confirmed by a reliable source. |
| **Hallucinated** | At least one fact in the claim is **contradicted** by a reliable source. |
| **Uncertain** | Nothing is contradicted, but at least one fact **cannot be confirmed** after a reasonable search (about 3 minutes), or reliable sources **disagree**, or the claim has **no clear meaning**. |

"Uncertain" is a real answer, not a way to skip. Use it whenever the rules below say so.

---

## 2. The decision procedure (follow it in this order, every time)

1. **Read the claim literally.** Can you tell what it asserts? If not → **Uncertain**.
2. **Break it into its facts.** Example: *"X was born in Pune on 3 January 1831"* contains two
   facts: the place (Pune) and the date (3 January 1831).
3. **Check each fact** against the allowed sources (section 4).
4. **Any fact contradicted** → **Hallucinated**. Stop.
5. **Otherwise, any fact not confirmable**, or sources disagree → **Uncertain**.
6. **Otherwise** (every fact confirmed) → **Verified**.

A claim is only as good as its **worst** fact. One wrong detail makes the whole claim
Hallucinated, even if the rest is correct.

---

## 3. Rules for the tricky cases

**Places ("born in", "died in", "located in", "headquartered in", "capital of")**
- The place in the claim must **be** the true place or **contain** it. *"Born in Maharashtra"* is
  Verified if the person was born in Pune. *"Born in Pune"* is Hallucinated if they were born in
  Nashik.
- **"In" means inside the official boundary.** A place **near** a city is not **in** it. If the
  person died in a town next to a city, *"died in [the city]"* is **Hallucinated**. If you truly
  cannot tell whether the place lies inside the boundary → **Uncertain**.
- **Old and new names of the same place are equal**: Bombay = Mumbai, Madras = Chennai,
  Calcutta = Kolkata, Bangalore = Bengaluru, Orissa = Odisha, Seringapatam = Srirangapatna.
- If the claim names **several** places ("in X, in the state of Y, India"), **every** one must be
  correct.

**Dates and numbers**
- A date in the claim is a fact and must match **as stated** (day, month and year if all are
  given). If reliable sources give different dates → **Uncertain**.

**"Founded by"**
- Verified if the named person is recorded as a founder or co-founder.
- Hallucinated if the named person is not among the founders.
- A vague but accurate description (*"founded by a group of reformers"*) is **Verified** if
  sources agree with it.

**"Member of"**
- Verified if the membership is confirmed.
- A vague but true statement (*"X is a member of several international organizations"*) is
  **Verified**.

**Extra details**
- Every detail counts, including districts, years, "the first", and "the main office". A wrong
  extra detail → **Hallucinated**. An extra detail you cannot confirm, with everything else true
  → **Uncertain**.

**Oddly worded or broken claims**
- Some claims were produced by a computer and read strangely. **Judge the sentence literally, as
  written.** Do not repair it into what you think was meant.
- If the literal sentence is clearly false → **Hallucinated**. If it has no clear literal
  meaning → **Uncertain**.

**Context**
- Use the question and the full answer **only** to understand what the claim refers to (for
  example, what "the city" means). Do not add facts from the answer into the claim.

**Time**
- Judge the claim as true **today**, unless it states a past time. A historical fact
  (a birthplace, a founding) does not change.

---

## 4. Allowed sources

**Use (in this order of preference):**
1. The subject's **English Wikipedia article** (the article text and the references it cites).
2. **Official websites** (the organisation's own site, government sites).
3. **Encyclopaedias** such as Britannica, and reputable news or academic sources.

**Do NOT use:**
- **Wikidata** (wikidata.org) — the system being tested uses Wikidata, so labels based on it
  would not be independent.
- **Any AI tool**: ChatGPT, Gemini, Copilot, Google's AI overview, AI answers in search results.
  Search normally, then open and read the actual source page.
- The SatyaScore app or demo.
- The other annotator.

---

## 5. Filling in the sheet

- **`verdict`**: choose from the dropdown — Verified, Uncertain or Hallucinated. **Never leave it
  blank.**
- **`evidence_url`**: paste the link of the source that decided your label. **Required for every
  claim.**
- **`notes`**: **required for Hallucinated and Uncertain.** Say which fact is wrong or unconfirmed,
  and what the source says (for example: "source says born in Nashik, not Pune").
- **Do not** sort, filter, delete, add, reorder or rename rows or columns. Do not change any
  column except these three.
- Save as the same `.xlsx` file with the same name.

---

## 6. Working rules

- **Work alone.** Do not discuss any claim with anyone until **both** sheets are returned.
  Independent labels are the whole point.
- Do not look at the other annotator's sheet.
- If a rule here does not settle a case, choose the label the rules come closest to, and explain
  your reasoning in `notes`. Do not ask the other annotator.

---

## 7. Worked examples (these claims are NOT in your sheet)

| Claim | Label | Why |
|---|---|---|
| "Paris is the capital of France." | Verified | Confirmed by the France article. |
| "Albert Einstein was born in Munich." | Hallucinated | He was born in Ulm; Munich does not contain Ulm. |
| "Albert Einstein was born in Germany." | Verified | Ulm is in Germany; the claim's place contains the true place. |
| "Rabindranath Tagore was born in Calcutta on 7 May 1861." | Verified | Place (old name of Kolkata) and date both confirmed. |
| "Rabindranath Tagore was born in Calcutta on 7 May 1871." | Hallucinated | The year is wrong: one wrong fact is enough. |
| "The museum was founded by a local collector in the village of X." (no source mentions this) | Uncertain | Nothing contradicted, but not confirmable. |
| "Specifically Germany is situated in the town of Ulm." | Hallucinated | Judged literally: Germany is not situated in Ulm. |
| "Its main office is located in sector 1 of the country." | Uncertain | No clear literal meaning. |
