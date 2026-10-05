# Why most hallucinations in the train set are not caught

All 45 gold-Hallucinated train claims (gold_train_clean.csv; 38 English, 7 Hindi) were run through the
live pipeline on 2026-10-05 (knowledge graph, official statistics, fact-checks, Wikipedia evidence with
expansion): **4 Hallucinated, 16 Uncertain, 25 Verified**.

Each claim was then read against the annotators' notes and sorted by type. **The categories are the
analyst's judgement, not annotator labels.**

| Type | Count | Example | Hallucinated now |
|---|---|---|---|
| Extraction artifact: the claim text was mangled by the claim extractor of the time; the chatbot's own sentence was correct | ~31 | "Its roles…" → "India roles include…"; "it" → "CH4"; "Rights are are enforceable"; commas stripped from a correct sentence | 2 |
| …of which: a pronoun replaced by the wrong name (the old "nearest entity" rule, since replaced, results/coref_eval.md) | ~14 | "Parliament is sent back to the President"; "Eligible voters cast Candidate ballots" | |
| Genuine chatbot hallucination: misconception, over-generalisation, legal nuance | ~14 | "Viral infections tend to be more easily spread"; "mass and weight both depend on location"; "a Chief Minister's term is 5 years under the Constitution"; "greenhouse gases trap the sun's rays" | 2 (WHO water intake; greenhouse gases) |

## Findings

1. **About two-thirds of the "hallucinations" are artifacts of the old claim extractor**, not chatbot
   errors. The labels were given to the old extractor's output; the current extractor would not produce
   many of these strings. So the train "hallucinations caught" figure partly measures an extractor that
   has since been fixed. Measuring today's system properly needs the original chatbot answers re-extracted
   and **newly labelled by people**.
2. **The genuine hallucinations are reasoning errors, not lookup errors**: none is a date, place, number or
   name that Wikidata or the World Bank could check.
3. **8 of the 14 genuine hallucinations were Verified by loosely related passages**: "viral infections
   spread more easily" by a Hindi herpes passage; "the candidate with most votes becomes President" by an
   article on simple-majority voting; the Chief Minister's term by "State governments of India". This led
   to the strict-support test (strict_support_eval.py).
