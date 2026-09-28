"""
When does a professional fact-check decide a claim? (member2_data/factcheck.py finds them.)

Google returns fact-checks for claims that merely SHARE WORDS with ours. Using one
about a different claim would repeat the cricket bug (evidence about something else
deciding the verdict), and one about the NEGATION would flip a true claim: a
fact-check rating "Hot water cures COVID" False says nothing bad about "Hot water
does not cure COVID". So a fact-check decides only when logic carries its rating
over to our claim, as judged by the NLI model:

  rated FALSE: our claim must ENTAIL the checked claim (if ours implies a false
               statement, ours is false)          -> Hallucinated
  rated TRUE:  the checked claim must ENTAIL ours  -> Verified

with entailment >= FC_MIN_ENTAIL, and in addition
  - NEITHER direction may read as contradiction (> FC_MAX_CONTRA): a guard against
    an NLI slip on negations (measured: a Hindi negation pair got 0.72 entailment
    one way but was contradicted the other way);
  - XLM-R cosine >= FC_MIN_SIM, a coarse same-topic guard only (measured on design
    pairs: paraphrases 0.60-0.89 and different claims 0.67-0.79, so similarity
    cannot tell them apart; the NLI conditions do).

Mixed ratings ("Misleading", "Partly false", "Missing context", "Mostly true") and
unreadable ones never decide. Matching fact-checks that disagree decide nothing.
Thresholds were set on hand-written design pairs, before any evaluation run
(factcheck_eval.py; its decision rule is fixed in that file).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FC_MIN_SIM = 0.50
FC_MIN_ENTAIL = 0.70
FC_MAX_CONTRA = 0.20
FC_FALSE_SCORE = 0.05   # hallu_score when a matching fact-check rates the claim false
FC_TRUE_SCORE = 0.95
FC_NOTE_PREFIX = "fact-checked by"


@dataclass
class FactCheckMatch:
    check: object                 # member2_data.factcheck.FactCheck
    similarity: float
    entail_claim_to_check: float  # NLI(premise = our claim, hypothesis = checked claim)
    entail_check_to_claim: float
    contra: float = 0.0           # max contradiction over both directions

    @property
    def applies(self) -> bool:
        """Does the fact-check's clear rating carry over to our claim?"""
        if self.similarity < FC_MIN_SIM or self.contra > FC_MAX_CONTRA:
            return False
        if self.check.verdict == "false":
            return self.entail_claim_to_check >= FC_MIN_ENTAIL
        if self.check.verdict == "true":
            return self.entail_check_to_claim >= FC_MIN_ENTAIL
        return False


def match(claim: str, language: str, checks: list, embedder, nli) -> list[FactCheckMatch]:
    """Scores every fact-check against the claim (all of them, applicable or not)."""
    checks = [c for c in checks if c.claim_text.strip()]
    if not checks:
        return []
    texts = [claim] + [c.claim_text for c in checks]
    vecs = embedder.embed([f"fc{i}" for i in range(len(texts))], texts, [language] * len(texts),
                          use_muril=False).vectors
    sims = (vecs[1:] @ vecs[0]).astype(float)
    n = len(checks)
    res = nli.score_batch(claim_ids=[f"fc{i}" for i in range(2 * n)],
                          premises=[claim] * n + [c.claim_text for c in checks],
                          hypotheses=[c.claim_text for c in checks] + [claim] * n)
    return [FactCheckMatch(c, float(np.clip(s, -1, 1)), res[i].entailment_prob, res[n + i].entailment_prob,
                           max(res[i].contradiction_prob, res[n + i].contradiction_prob))
            for i, (c, s) in enumerate(zip(checks, sims))]


def decide(matches: list[FactCheckMatch]) -> FactCheckMatch | None:
    """The fact-check that decides the claim, or None (none applies, or the
    applicable ones disagree)."""
    ok = [m for m in matches if m.applies]
    if not ok or len({m.check.verdict for m in ok}) > 1:
        return None
    return max(ok, key=lambda m: m.similarity)
