# Why SatyaScore misses hallucinations, and what can realistically fix it

A study of the problem (from our own measurements) and of published work (literature and tools,
checked against their reported numbers). Written 2026-10-06. Strict: no claim here goes beyond the
evidence cited.

---

## 1. The problem, precisely

SatyaScore checks a claim in one of two ways:

1. **A structured source decides** (Wikidata, World Bank / WHO, professional fact-checks). Measured
   error: close to zero (11/13 KG decisions right in the pre-registered round-3 run, 12/12 after the exploratory linking fix, English; 137/137 false statistics caught with 0
   true claims contradicted; 0 wrong fact-check decisions).
2. **Otherwise, Wikipedia passages are retrieved and an NLI model (mDeBERTa-v3-base-mnli-xnli) judges
   each passage** as supporting, contradicting or neither.

Almost all errors come from path 2. On real chatbot answers (train, live rule; results/evidence_rule_eval.md):
when the system gives a verdict it is wrong about 1 in 5 times; "Verified" is right ~84% of the time,
"Hallucinated" only ~36% (5 of 14).

The failures split into **four distinct sub-problems** (results/missed_hallucinations_analysis.md,
results/evidence_rule_eval.md):

| # | Sub-problem | Evidence | Example |
|---|---|---|---|
| P1 | **The judge confuses "about the same topic" with "supports"** | 8 of 14 genuine train hallucinations Verified; 9 of 9 false common-sense statements Verified | "Viral infections tend to be more easily spread" Verified by a Hindi herpes passage; "Human can breath naturally underwater" by a scuba passage ("the diver can inhale and exhale naturally") |
| P2 | **The refuting evidence is not written anywhere retrievable** | common-sense claims: Wikipedia does not state "humans cannot breathe underwater" as such | "Snakes have legs", "Humans have three lungs" |
| P3 | **The error is a subtle misconception or over-generalisation**, not a wrong name/date/number | all ~14 genuine train hallucinations | "a Chief Minister's term is 5 years under the Constitution"; "mass depends on location" |
| P4 | **The evaluation data is noisy** | ~31 of 45 train "hallucinations" are artifacts of the old claim extractor, not chatbot errors | "India roles include…" (pronoun swapped by the old extractor) |

P1 is a property of the judge. P2 and P3 are properties of the claims and the evidence: no judge can
find support or contradiction that the evidence does not contain. P4 is a measurement problem.

Already tested and ruled out (rules fixed before each run): bigger and FEVER-trained NLI models
(results/nli_model_search.md), stricter support rules and capped scores (results/strict_support_eval.md,
results/evidence_rule_eval.md), number guards, MedlinePlus as extra evidence. Each either did not help
or removed Verified from too many true claims.

---

## 2. What the field knows

**P1 is a known, documented failure of NLI models.** NLI models rely on lexical overlap between premise and
hypothesis and associate overlap with entailment; in claim verification this produces "support" from
passages that share keywords without stating the fact
([Emergent Mind: NLI](https://www.emergentmind.com/topics/natural-language-inference-nli);
[Falsesum, NAACL 2022](https://arxiv.org/pdf/2205.06009)). Our 9/9 common-sense result is this effect.

**Purpose-built "grounding checkers" target exactly P1.** They are trained on synthetic hard negatives:
documents on the same topic that do *not* support the claim.

| Model | Size | LLM-AggreFact balanced accuracy | Licence | Notes |
|---|---|---|---|---|
| Bespoke-MiniCheck-7B | 7B | 77.4 | commercial use: ask vendor | too large for a 6 GB laptop GPU in full precision |
| GPT-4o (reference) | — | 75.9 | API | |
| **FactCG-DeBERTa-L** | **0.4B** | **75.6** | public code and checkpoint; licence not checked | checkpoint needs the authors' code |
| **MiniCheck-Flan-T5-L** | **0.8B** | **75.0** | Apache-2.0 (repository) | |
| MiniCheck-DeBERTa-v3-L | ~0.4B | not in the leaderboard extract read for this study | MIT (model card) | loads with standard `transformers` |
| AlignScore | 0.36B | 70.4 (as reported in the MiniCheck paper) | not checked | previous best small checker |

Sources: [LLM-AggreFact leaderboard](https://llm-aggrefact.github.io/);
[MiniCheck, EMNLP 2024](https://aclanthology.org/2024.emnlp-main.499/) ([code](https://github.com/Liyan06/MiniCheck));
[FactCG, NAACL 2025](https://aclanthology.org/2025.naacl-long.258/) ([code](https://github.com/derenlei/FactCG));
[AlignScore, ACL 2023](https://aclanthology.org/2023.acl-long.634/).
Vectara's open HHEM-2.1 (DeBERTa-v3-base) is a similar checker, English only; its multilingual version
is commercial ([Vectara](https://www.vectara.com/blog/hhem-v2-a-new-and-improved-factual-consistency-scoring-model)).

**Strict reading of those numbers:**
- ~75% balanced accuracy means roughly **1 in 4 judgements is still wrong**, even for the best small models.
- The benchmark gives the checker the right document. In our setting the document comes from
  retrieval and may simply not contain the fact (P2); a checker then says "not supported", which we
  must show as Uncertain, not Hallucinated.
- **All of these are English-only.** Hindi would need the claim translated first, e.g. with IndicTrans2
  (AI4Bharat, 1B parameters, MIT licence, quality at par with commercial systems:
  [model](https://huggingface.co/ai4bharat/indictrans2-indic-en-1B), [paper](https://arxiv.org/pdf/2305.16307)).

**P2 and P3 are not solved by small models anywhere in the literature.**
- Real-world claim verification is hard even for the best systems: the AVeriTeC 2024 shared task winner
  scored 63%, using GPT-4 with web search
  ([AVeriTeC, FEVER 2024](https://aclanthology.org/2024.fever-1.1/)).
- Google DeepMind's SAFE (an LLM agent with Google Search) agrees with human annotators 72% of the time
  ([Wei et al., 2024](https://arxiv.org/abs/2403.18802)).
- In the multilingual hallucination task Mu-SHROOM (SemEval-2025), the top Hindi system used a very large
  LLM, DeepSeek-V3 ([CCNU](https://arxiv.org/html/2505.11965)).
- On X-FACT, real-world multilingual fact-checking (including Hindi) is far from solved
  ([X-FACT](https://aclanthology.org/2021.acl-short.86/)).

The methods that do address P2/P3 all use a large LLM's world knowledge, as our own LLM test did:
it caught many more hallucinations, but marked about 1 in 7 true claims false
(results/llm_verifier_expanded.md).

---

## 3. Conclusions

1. **No method, published or ours, reliably detects all LLM hallucinations.** The best systems in the
   literature are right on roughly 63–75% of real claims, and those use GPT-4-class models.
2. **P1 (topic mistaken for support) has a credible, local, free fix: a purpose-built grounding checker**
   (FactCG-DeBERTa-L or MiniCheck) in place of the NLI model for the "does this passage support the claim"
   decision. It runs on our GPU (0.4–0.8B parameters), needs no API, and has permissive licences.
   **Expected effect:** fewer hallucinations wrongly Verified. **Not expected:** many more hallucinations
   caught. "Not supported" can only become Uncertain without contradicting evidence.
3. **P2 and P3 cannot be fixed without an LLM's world knowledge**, and an LLM brings false alarms (ours:
   about 4x). This is a limit of the approach, not a bug.
4. **P4 must be fixed to measure anything honestly:** new labels for claims from the current extractor.

## 4. The most suitable solution for SatyaScore

**Keep:** structured sources first (Wikidata, World Bank / WHO, fact-checks). They are the reliable part.

**Change (to be tested, rule fixed before running):** use a grounding checker (MiniCheck-DeBERTa-v3-L first:
MIT, loads with standard `transformers`; FactCG-DeBERTa-L as the stronger alternative) to decide support
for English claims; translate Hindi claims with IndicTrans2 before checking against English passages.

**Decision rule to fix before the test:** adopt only if, on fresh unseen data and on the annotated
claims, hallucinations wrongly Verified fall, false alarms do not rise, and true claims Verified fall by
at most 10%.

**What to tell the guide:** this would make "Verified" more trustworthy. It would not make the system
catch most hallucinations; that needs world knowledge, which in the literature only large LLMs supply,
at a cost in false alarms that we measured.

**Not recommended (tested or ruled out):** other NLI models, threshold tuning, fine-tuning on our 303
claims, an LLM as the main judge.

**Update:** the design probe was run (section 5): MiniCheck did not fix false support of common-sense
falsehoods, so the change is not pursued.

---

## 5. Design probe: MiniCheck-DeBERTa-v3-L vs the current NLI model (2026-10-06)

Same retrieved passages for both; "supports" = the best passage scores >= 0.5. A design probe to
understand the problem, not a decision test. English only below (MiniCheck is English-only; its
Hindi results are meaningless without translation).

| Group (English) | n | NLI supports | MiniCheck supports |
|---|---|---|---|
| true chatbot claims (train sample, seed 19) | 16 | 11 | 11 |
| fresh true Wikipedia sentences (seed 19) | 29 | 22 | **29** |
| genuine train hallucinations (should not be supported) | 7 | 3 | 2 |
| false common-sense statements (should not be supported) | 9 | 7 | **7** |

MiniCheck still confidently supported "Humans have three lungs" (0.97, Lung article), "Spiders are
insects" (0.97), "The Moon produces its own light" (0.99) and "Humans can breathe naturally underwater"
(0.69).

**Conclusion of the probe:** a grounding checker recognises genuine support better in English but does
**not** fix false support of common-sense falsehoods, the failure that matters most; Hindi would need a
translation model as well. **Not pursued.** The remaining errors need world knowledge, which only large
LLMs supply, at a measured cost in false alarms (section 2).
