"""
Cross-check verdict (Version 2; SATYASCORE_VERDICT_MODE=crosscheck). Chosen by the project owner after seeing
that "no source found = Hallucinated" would flag ~41% of true claims (plan: v2, Phase 2.3).

Order of decision for one claim:
1. A structured source (official statistics, Wikidata) or a matching published fact-check decided it:
   that decision stands (exactly as in v1).
2. Otherwise the passage evidence (evidence-rule score s) and an LLM judgement are cross-checked:
   - Verified      only if a passage supports the claim (s > 0.65) AND the LLM says it is true;
   - Hallucinated  if an on-topic passage contradicts it (s < 0.35) and the LLM does not say it is true,
                   OR no passage supports it AND the LLM says it is false;
   - Uncertain     otherwise (including when the passages and the LLM disagree).
3. If the LLM gave no usable answer (no key, quota, unparsable), the v1 verdict is kept.
4. When the v1 number guard is on (SATYASCORE_NUMBER_GUARD; off by default, it was not adopted in v1) and it
   found a claim's number missing from the deciding passage, the passages do not count as support. The guard
   only looks at claims v1 had Verified from a supporting passage, so this is not a promise that a claim with a
   number missing from the evidence is never Verified.
5. With flag_needs_llm (the final version, v4a), a passage contradiction alone never flags a claim.

Symmetric (the default since 2026-10-12, chosen by the project owner on the dev sample, before any test
run): disagreement gives Uncertain in both directions. With symmetric=False a passage contradiction decides
alone (the rule as first chosen); on dev the passage model's "contradictions" were often wrong where the LLM
was right ("Humans have 28 finger bones"): false alarms 11% -> 7%, caught 60% -> 59% (gpt-oss-20b).
"""
from __future__ import annotations

import re

SUPPORT, CONTRADICT = 0.65, 0.35  # the v1 verdict tiers, applied to the evidence-rule score

# No-evidence filter (fix round, results/v2_data_PROTOCOL.md): an LLM "Hallucinated" whose reason only says the
# evidence is missing counts as Uncertain. On held-out data 7 of 10 new false alarms had such reasons
# ("No evidence supports Omar Epps winning that award").
NO_EVIDENCE = re.compile(
    r"\b(no (?:evidence|passage|information|mention|source)|not (?:supported|mentioned|stated|found|confirmed|verified)|"
    r"unsupported|does not (?:mention|support|state|confirm)|do not (?:mention|support)|cannot be (?:verified|confirmed)|"
    r"lack of evidence|insufficient)\b", re.I)


def second_reading_candidate(evidence_score: float | None, llm_used: str | None, number_missing: bool) -> bool:
    """Second reading (last round, results/v2_data_PROTOCOL.md): a claim the cross-check leaves Uncertain although
    one side leans true -- the LLM says true while the passages are not clearly supportive, or the passages support
    it while the LLM is unsure. Never when the LLM (after the no-evidence filter) says false or a number is missing."""
    if number_missing or llm_used not in ("Verified", "Uncertain"):
        return False
    supported = evidence_score is not None and evidence_score > SUPPORT
    return (llm_used == "Verified" and not supported) or (llm_used == "Uncertain" and supported)


def llm_verdict_used(verdict: str | None, reason: str | None) -> str | None:
    """The LLM's verdict as the cross-check uses it: 'Hallucinated' only for a reason other than missing evidence."""
    if verdict == "Hallucinated" and NO_EVIDENCE.search(reason or ""):
        return "Uncertain"
    return verdict


def crosscheck_verdict(v1_verdict: str, decided_by_source: bool, evidence_score: float | None,
                       llm_verdict: str | None, number_missing: bool = False, symmetric: bool = True,
                       flag_needs_llm: bool = False) -> str:
    """The cross-check verdict for one claim (see the module docstring)."""
    if decided_by_source or llm_verdict not in ("Verified", "Hallucinated", "Uncertain"):
        return v1_verdict
    supported = evidence_score is not None and evidence_score > SUPPORT and not number_missing
    contradicted = evidence_score is not None and evidence_score < CONTRADICT
    # flag_needs_llm (v4a, results/v2_data_PROTOCOL.md "Large final test"): a passage contradiction alone never
    # flags a claim; only the LLM saying false (with no passage support) does.
    if contradicted and not flag_needs_llm and not (symmetric and llm_verdict == "Verified"):
        return "Hallucinated"
    if supported and llm_verdict == "Verified":
        return "Verified"
    if not supported and llm_verdict == "Hallucinated":
        return "Hallucinated"
    return "Uncertain"
