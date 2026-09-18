# SatyaScore — Problem Summary (for an outside reviewer)

This assumes ML/NLP background but nothing about our project.

## What we're building
A **claim-level, multilingual (English + Hindi) LLM hallucination detector** (B.Tech
capstone). We take an LLM's answer, split it into atomic claims, and label each claim
**Verified / Uncertain / Hallucinated**.

## The scoring method (CMHSA)
Each claim gets a fused score:

```
HalluScore = alpha*SemSim + beta*NLI_prob + gamma*KG_conf     (alpha+beta+gamma = 1, learned per language)
Verdict:  <0.35 -> Hallucinated | 0.35-0.65 -> Uncertain | >0.65 -> Verified
```

The three signals:
- **SemSim** — cosine similarity between the claim and the best-matching evidence
  passage (FAISS retrieval over a Wikipedia-built corpus).
- **NLI_prob** — entailment between retrieved evidence and the claim (multilingual NLI
  model, mDeBERTa-mnli-xnli).
- **KG_conf** — Wikidata triple check via entity linking.

Weights alpha, beta, gamma are trained with BCE against gold labels
(Hallucinated=0, Uncertain=0.5, Verified=1).

## The data
456 human-gold-labeled claims (en=266, hi=190). Class balance is skewed:
**356 Verified / 56 Hallucinated / 44 Uncertain**. We use a stratified 80/20
train/test split (seed 42).

## The core problem
**The trained detector catches essentially zero hallucinations on held-out data.**
Ablation on the test set:

| Config | EN acc / macro-F1 / **Hallucinated-F1** | HI acc / macro-F1 / **Hallucinated-F1** |
|---|---|---|
| Full (SemSim+NLI+KG) | 0.415 / 0.256 / **0.000** | 0.590 / 0.338 / **0.000** |
| SemSim only | 0.415 / 0.256 / **0.000** | 0.590 / 0.338 / **0.000** |
| SemSim + NLI | 0.415 / 0.256 / **0.000** | 0.590 / 0.338 / **0.000** |
| NLI only | 0.302 / 0.214 / 0.176 | 0.385 / 0.240 / 0.167 |

The "full" model is **identical** to "SemSim only" — NLI and KG contribute nothing once
SemSim is present. Learned weights: **alpha~0.92, beta~0.005, gamma~0.07** for both
languages (training drives NLI's weight to ~0).

## Why (our diagnostics, over all 456 claims)
**Neither SemSim nor NLI separates true claims from false ones on this data:**

- **SemSim** mean by class: Hallucinated **0.637**, Verified **0.656** -> nearly
  identical (Cohen's d ~ 0.15, ~94% distribution overlap). *No threshold can fix this.*
  Root cause: SemSim measures **topical relevance, not truth** — a false claim about
  Nehru retrieves Nehru evidence just as strongly as a true one.
- **NLI_prob** (as originally computed): correlation with "is hallucinated" = **-0.02**
  (essentially zero); class means within 0.05 of each other.
- **KG_conf** is populated on **0 of 456 claims** — entity linking almost never resolves
  2 entities + a known relation, so this signal has never contributed.

So the fusion collapses to SemSim-only, and SemSim can't discriminate factuality -> 0%
hallucination detection. **This means our headline thesis ("multi-signal fusion beats
its parts") is currently not supported by the data.**

## What we've tried and ruled out
1. **Recalibrate the 0.35/0.65 thresholds** — ruled out by the ~94% distribution overlap.
2. **Deepen the evidence corpus** — replaced 44 short Wikipedia lead-summaries with
   full-article text chunked into ~400-char passages (44 -> ~4,800 passages).
   **beta still didn't move.** So "evidence too shallow" was not the (sole) cause.
3. **Is the NLI model itself broken?** No. Direct sanity check on our real IPL "8 teams"
   hallucination: the model correctly returns entailment=0.11, **contradiction=0.83**.
   The model works; the bug was in how we *used* its output.

## The bug we found + the fix (applied, NOT yet re-tested)
- **Bug:** the pipeline set `nli_prob = max(entailment_prob)` over the top-3 retrieved
  passages and **discarded the contradiction probability entirely**. So a
  strongly-contradicted (false) claim and an unaddressed (neutral) claim both looked
  like "low entailment" — indistinguishable. And taking the max over 3 passages let one
  loosely-matching passage spuriously inflate a false claim.
- **Fix:** score each passage as `0.5 + 0.5*(entailment - contradiction)` (0 =
  contradicted, 1 = entailed, 0.5 = neutral) and keep the **most decisive** passage
  (farthest from 0.5).
- **Status:** the fix is in the code, but we **haven't re-run** the corpus regen ->
  retrain -> re-ablation yet, so we don't know if beta recovers.

## The questions we'd love your take on
1. Do you expect the **contradiction-aware NLI fix** to actually make NLI separate
   hallucinations here — or is there a deeper issue?
2. **Retrieval bottleneck:** even a perfect NLI only fires if retrieval surfaces the
   passage with the *competing fact*. With embedding-similarity retrieval + 400-char
   chunks, is the decisive sentence actually being retrieved? Should we retrieve more
   passages / use a reranker / sentence-level evidence?
3. Since **SemSim provably measures topicality, not truth**, is putting it in the fusion
   at all a design mistake? Should the model lean on NLI + KG and treat SemSim only as a
   relevance gate?
4. **KG_conf is 0% covered.** Worth investing in better entity linking (it's the only
   signal that checks a specific fact), or a dead end on a capstone timeline?
5. **Class imbalance** (356 V / 56 H / 44 U): is this hurting training toward the
   majority class? Should we reweight the BCE loss or resample?

---

## Appendix — exact numbers (raw evidence)

**Learned weights (trained on the current data):**
- en: alpha=0.9236, beta=0.005446, gamma=0.07092
- hi: alpha=0.9253, beta=0.005219, gamma=0.06949

**Signal distributions by gold verdict (all 456 claims, dataset v2):**

| signal | Hallucinated (n=56) | Uncertain (n=44) | Verified (n=356) | range | coverage |
|---|---|---|---|---|---|
| sem_sim  | mean 0.637 | 0.623 | 0.656 | 0.307-0.928 | 456/456 |
| nli_prob | mean 0.370 | 0.416 | 0.391 | 0.0006-0.9985 | 456/456 |
| kg_conf  | —          | —     | —     | —           | **0/456** |

- corr(nli_prob, is_hallucinated) = **-0.0199**; spread between class means = 0.047.
- Cohen's d (sem_sim, Hallucinated vs Verified) ~ 0.15 (near-total overlap).

**Test / train split (stratified 80/20, seed 42):**
- Train (364): en 154 V / 38 H / 21 U ; hi 130 V / 7 H / 14 U
- Test (92):   en  39 V /  9 H /  5 U ; hi  33 V / 2 H /  4 U

**Caveat:** the nli_prob numbers above are from the ORIGINAL entailment-only computation
(`max(entailment)`), which is what produced the -0.02 correlation. The contradiction-aware
fix (`0.5 + 0.5*(entailment - contradiction)`, most-decisive passage) is now in the code
but has NOT been re-measured — regenerating signals + retraining + re-ablation is the
pending next step. Also note the test-set minority counts are tiny (HI Hallucinated = 2),
so the per-class test-set F1 is fragile; the signal-separation stats above are over all
456 rows and are not.
