"""
Decisive sanity check: does the NLI model get OBVIOUS cases right?

This directly tests member1_model/nli_scorer.py against hand-crafted,
unambiguous premise/hypothesis pairs -- including one modeled exactly on
the real IPL "8 teams" hallucination found earlier in this project. If the
model gets these wrong, there's a real bug (or the model is fundamentally
unsuited to this task). If it gets these right but still shows ~0
correlation on the real 456-claim dataset, that means the model can do
easy, obvious entailment/contradiction but isn't precise enough on the
project's actual claims -- a genuine model-capability limit, not a bug.

Usage:
    python sanity_check_nli.py
"""

from member1_model.nli_scorer import NLIScorer

scorer = NLIScorer()

CASES = [
    {
        "name": "Clear entailment (near-paraphrase)",
        "premise": "The Reserve Bank of India was established on 1 April 1935.",
        "hypothesis": "The RBI was founded in 1935.",
        "expect": "entailment_prob should be HIGH (>0.7)",
    },
    {
        "name": "Clear contradiction (direct factual conflict)",
        "premise": "The Reserve Bank of India was established on 1 April 1935.",
        "hypothesis": "The Reserve Bank of India was established in 1990.",
        "expect": "contradiction_prob should be HIGH (>0.7), entailment LOW",
    },
    {
        "name": "Clear neutral (unrelated topic)",
        "premise": "The Reserve Bank of India was established on 1 April 1935.",
        "hypothesis": "Cricket is played with a bat and ball.",
        "expect": "neutral_prob should be HIGH, entailment and contradiction both LOW",
    },
    {
        "name": "REAL PROJECT CASE: IPL team count (this is the actual hallucination we need to catch)",
        "premise": (
            "As of the 2022 season, the Indian Premier League features 10 teams "
            "competing in a group-stage format followed by playoffs, with 74 total "
            "matches played including the playoff stage."
        ),
        "hypothesis": "Eight teams play each other twice in the IPL, resulting in a total of 56 matches.",
        "expect": "contradiction_prob should be HIGH, entailment LOW -- this is a real false claim from the dataset",
    },
    {
        "name": "REAL PROJECT CASE: correct IPL claim for comparison",
        "premise": (
            "As of the 2022 season, the Indian Premier League features 10 teams "
            "competing in a group-stage format followed by playoffs, with 74 total "
            "matches played including the playoff stage."
        ),
        "hypothesis": "The IPL currently has 10 teams.",
        "expect": "entailment_prob should be HIGH -- this is a real true claim",
    },
]

print(f"{'='*70}\nNLI SANITY CHECK -- {len(CASES)} hand-crafted unambiguous cases\n{'='*70}\n")

for case in CASES:
    result = scorer.score(claim_id="test", premise=case["premise"], hypothesis=case["hypothesis"])
    print(f"--- {case['name']} ---")
    print(f"  Premise:    {case['premise'][:90]}")
    print(f"  Hypothesis: {case['hypothesis']}")
    print(f"  Expected:   {case['expect']}")
    print(f"  ACTUAL -> entailment={result.entailment_prob:.3f}  "
          f"contradiction={result.contradiction_prob:.3f}  neutral={result.neutral_prob:.3f}")
    print()

print(f"{'='*70}")
print("READ THIS:")
print("- If the first 3 (simple) cases look right but the IPL cases don't,")
print("  the model struggles with the SPECIFIC kind of numeric/factual")
print("  precision this project needs -- a real capability limit, not a bug.")
print("- If even the first 3 simple cases look wrong/reversed, there's a")
print("  real bug somewhere in the model loading or scoring path.")
print(f"{'='*70}")
