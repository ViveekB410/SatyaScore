# Ablation and Limitations

Draft prose for the results chapter. Every figure quoted here is reproducible
by running `python honest_eval.py`, `python honest_ablation.py`,
`python kg_coverage.py` and `python make_figures.py` against
`gold_train_v3.csv` and `gold_test_v3.csv`. Figures R1 to R3 are
`figures/fig_roc_synthetic_vs_human.png`,
`figures/fig_score_distributions.png` and
`figures/fig_threshold_sweep.png`. The per-configuration table is
`ablation_table.md`. Numbers describe the current
English-only evidence corpus and must be regenerated once the bilingual
corpus is built.

## Ablation results

The ablation study evaluated seven signal combinations against a held-out test
set of 116 claims, 72 English and 44 Hindi. Cut-points were fitted separately
for each configuration on the training split, because removing a signal changes
the scale of the fused score and a single shared set of cut-points would
penalise a configuration for its calibration rather than its discriminative
power. Each configuration is reported twice, once over the whole test split and
once over the human-annotated claims alone.

Four configurations produce identical predictions in both languages: the full
three-signal model, NLI alone, SemSim with NLI, and NLI with KG. Two others,
SemSim alone and SemSim with KG, are likewise identical to each other. This is
arithmetic rather than coincidence. The knowledge-graph confidence score is
absent for all 576 claims, so its weight renormalises away, and the learned
weight on semantic similarity is zero, so any configuration containing the NLI
signal reduces to the NLI probability and any configuration without it reduces
to raw semantic similarity. The seventh configuration, KG alone, cannot be
scored at all. The table therefore contains two systems rather than seven, and
one empty cell.

The comparison that survives is between those two systems, and it does not
favour the model that training selected. On the full English test split the
NLI-based configurations reach accuracy 0.653 and Hallucinated-F1 0.560,
against 0.417 and 0.195 for semantic similarity alone. Restricted to
human-annotated claims, the ordering on hallucination detection reverses:
semantic similarity alone reaches Hallucinated-F1 0.200 while every NLI-based
configuration reaches 0.000. The NLI signal is better at the synthetic
perturbations, which dominate the hallucinated class in the test split, and no
configuration detects human-annotated hallucinations at a useful rate. Both
figures rest on nine human-annotated hallucinated claims and should be quoted
with that count attached.

Neither system beats the always-verified baseline by a comfortable margin. That
baseline scores 0.542 accuracy in English and 0.750 in Hindi, against 0.653 and
0.769 for the best configuration. In Hindi the margin is under two points, and
for the reasons given in the Hindi section below it should not be treated as a
result at all.

## Weight learning and the behaviour of semantic similarity

Training the softmax-constrained weight model on the training split assigned
a weight of approximately zero to semantic similarity and approximately 0.50
to the NLI probability in both languages. The residual 0.50 on the
knowledge-graph term is the softmax initialisation rather than a learned
value, because no gradient ever reached a parameter whose input was missing
for every row.

The collapse of the semantic similarity weight is a genuine training outcome
and deserves to be reported rather than corrected. On the English training
split, mean semantic similarity is higher for hallucinated claims, at 0.610,
than for verified claims, at 0.558. The Hindi split shows the same ordering,
at 0.621 against 0.571. A claim that is topically close to retrieved evidence
is not more likely to be true, and in this dataset the relationship runs
mildly in the opposite direction. Retrieval similarity measures what a claim
is about, not whether it is correct, and a fusion model that is free to
discover this will discard the signal.

## Knowledge-graph coverage

The knowledge-graph path contributed nothing to any result. Investigation of
why it contributed nothing produced a cleaner finding than the zero itself.
The entity linker recognises a relation only when the claim text contains one
of 27 hand-curated relation phrases, such as "is the capital of" or "was born
in". Across all 576 claims, the number containing any of these phrases is
zero. The ceiling on knowledge-graph coverage under the current design is
therefore not low, it is nil, and no amount of additional Wikidata querying
would change it.

The reason is a mismatch between the design and the claim population. Triple
verification assumes claims state a binary relation between two named
entities. The claims in this dataset are predominantly descriptive: symptom
lists, process descriptions, procedural statements and definitions, produced
by asking language models open questions in five subject domains. A sentence
such as "Common symptoms of dengue fever include high fever and severe
headache" has no subject, predicate and object that Wikidata can be asked
about. Knowledge-graph verification is a reasonable component for a system
whose input is factoid assertions about entities, and it is close to
inapplicable to free-form explanatory text.

## Verdict thresholds

The shipped verdict cut-points of 0.35 and 0.65 were chosen for a fused score
that combined three signals. Once the composite score reduces to the NLI
probability, whose mean for verified English claims is 0.491, those cut-points
place most correct claims in the uncertain band and accuracy suffers for a
reason that has nothing to do with the model's discriminative ability.

Refitting the cut-points on the training split alone, by grid search on
macro-F1, gives 0.18 and 0.23 for English and 0.01 and 0.21 for Hindi. Test
accuracy rises from 0.444 to 0.653 in English and from 0.282 to 0.769 in
Hindi, without retraining anything.

Figure R3 sweeps the lower cut-point across its whole range and plots overall
accuracy against recall on both hallucination populations. Accuracy peaks near
0.71 while recall on human-annotated hallucinations is still at or below 0.222,
and recall on that population only becomes substantial beyond a cut-point of
0.5, where accuracy has fallen to roughly 0.48. The two quantities cannot be
improved together on the current score.

That improvement should be reported together with what it costs. The
recalibrated cut-points gain accuracy almost entirely by classifying verified
claims correctly, and in doing so they reduce recall on human-annotated
hallucinations in the English test set from 0.222 to 0.000. An evaluation that
reports only overall accuracy would present this as progress. For a system
whose purpose is to flag hallucinations, it is a worse operating point on the
axis that matters, and it indicates that no threshold on the current score
separates real hallucinations from verified claims in either direction.

## Evaluation validity: synthetic perturbations against human annotations

The test set mixes two populations of hallucinated claims. Nineteen of the 28
English hallucinated test claims are synthetic perturbations, generated by
corrupting a verified claim and re-scored against an evidence corpus rebuilt
from the same source topics. The remaining nine are hallucinations identified
by human annotators in real model output.

Under the shipped cut-points, recall on the synthetic claims is 0.895 and
recall on the human-annotated claims in the same test set, under the same
model and the same thresholds, is 0.222. English Hallucinated-F1 falls from
0.679 over the mixed set to 0.200 over the human-annotated subset, and to
0.000 once the cut-points are recalibrated.

A threshold-free measurement isolates the effect. Holding the positive class
fixed as the human-annotated verified claims, the composite score separates
synthetic perturbations with an AUC of 0.820 and human-annotated
hallucinations with an AUC of 0.545. Both comparisons use the same score and
the same positive examples, so the difference of 0.275 is attributable
entirely to how the negative examples were produced.

Figure R1 plots both curves. Figure R2 shows why they differ: the synthetic
perturbations occupy a distinct low-scoring mode, while the human-annotated
hallucinations sit inside the distribution of verified claims.

This is the most transferable result in the study. Perturbation-based hard
negatives are widely used to enlarge hallucination detection datasets, and
they are attractive because they are cheap and their labels are certain. The
measurement above indicates that a detector can score well on them while
having close to no ability to detect the phenomenon they stand in for. A
perturbed claim carries the trace of its own construction, and an entailment
model is good at finding a contradiction that was deliberately inserted
against a passage that is known to be in the index. A hallucination produced
naturally by a language model is fluent, plausible and frequently about
something the corpus covers only partially. Any evaluation that reports a
single hallucination detection figure over a mixed test set should be read as
a statement about the proportion of synthetic examples it contains.

## Hindi results

The Hindi figures in this report are not yet interpretable and are included
for completeness rather than as evidence. The evidence corpus was built
exclusively from English Wikipedia articles, and every passage was embedded
under a hardcoded English language tag. Hindi claims consequently retrieved
little above the relevance floor, five of the 44 Hindi test claims were
dropped before scoring for want of any retrieved passage, and the reported
Hindi Hallucinated-F1 rests on two human-annotated hallucinated test claims.
A metric computed over two examples carries no information about the system.

The corpus construction has since been rewritten to fetch articles in both
languages, to resolve Hindi article titles through the MediaWiki language
link API rather than by transliteration or guesswork, to embed each passage
under its own language, and to index the specific articles that annotators
cited as evidence rather than a fixed list of topics. Hindi results will be
reported after the dataset is regenerated against that corpus. Until then the
honest statement is that the bilingual claim of the method has not been
tested.

## What this study supports

Three claims are defensible on the current evidence.

Multi-signal fusion, as specified in the method, does not improve on natural
language inference alone for this task and this data. Two of the three signals
contribute nothing: one because the claim population does not admit
knowledge-graph verification at all, and the other because retrieval
similarity tracks topicality rather than truth.

Detection performance on human-annotated hallucinations is weak, and the
ranking of signals depends on which population is measured. Semantic
similarity, which the weight model discarded, is the only configuration with
non-zero Hallucinated-F1 on human-annotated English claims, and it separates
that population slightly better than the composite score does, at an AUC of
0.591 against 0.545. The training objective optimised for the synthetic
majority of the hallucinated class. The composite
score separates them from verified claims at an AUC of 0.545 in English, which
is close to chance, and at no threshold does it recover useful recall without
sacrificing accuracy elsewhere. The system should be presented as a
calibrated uncertainty flag rather than as a hallucination detector.

Evaluation on perturbation-based synthetic hallucinations substantially
overstates detection performance, by a measured 0.275 AUC on this dataset.
This finding is independent of the specifics of the architecture and applies
to any detector benchmarked the same way.
