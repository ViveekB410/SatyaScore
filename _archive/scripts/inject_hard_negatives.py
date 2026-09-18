"""
inject_hard_negatives.py — Generate synthetic hallucinated claims by
perturbing verified claims with factual errors.

Perturbation strategies:
  1. Number swap (years, counts, percentages)
  2. Entity swap (cities, people, organizations)
  3. Negation insertion
  4. Attribute swap (largest↔smallest, first↔last, etc.)

Output: synthetic_hallucinations.csv with the same schema as the gold CSV,
        gold_verdict=Hallucinated, gold_source=synthetic_perturbation.

These claims MUST be re-scored through the pipeline (sem_sim, nli_prob)
before use in training — this script only generates the text.
"""

from __future__ import annotations

import csv
import hashlib
import random
import re
from pathlib import Path

random.seed(42)

INPUT_CSV = Path("SatyaScore_final_gold_456claims_v2.csv")
OUTPUT_CSV = Path("synthetic_hallucinations.csv")

# ── Perturbation helpers ────────────────────────────────────────────────

def _perturb_number(text: str) -> tuple[str, str] | None:
    """Find a number in the text and change it to a plausibly-wrong value."""
    # Match years (4-digit starting with 1 or 2)
    year_match = re.search(r'\b(1[5-9]\d{2}|20[0-2]\d)\b', text)
    if year_match:
        original = int(year_match.group())
        # Shift by 2-5 years (enough to be wrong, not absurdly so)
        delta = random.choice([-5, -3, -2, 2, 3, 5])
        replacement = str(original + delta)
        new_text = text[:year_match.start()] + replacement + text[year_match.end():]
        return new_text, f"year {original}->{replacement}"

    # Match other numbers (integers)
    num_matches = list(re.finditer(r'\b(\d+)\b', text))
    # Filter out very small numbers (1, 2) and things that look like IDs
    candidates = [m for m in num_matches if 2 < int(m.group()) < 10000 and len(m.group()) <= 4]
    if candidates:
        match = random.choice(candidates)
        original = int(match.group())
        # For small numbers, change by 1-3; for larger, change by 10-30%
        if original < 20:
            delta = random.choice([-3, -2, -1, 2, 3])
            replacement = max(1, original + delta)
        else:
            factor = random.choice([0.7, 0.8, 1.2, 1.5])
            replacement = max(1, int(original * factor))
        new_text = text[:match.start()] + str(replacement) + text[match.end():]
        return new_text, f"number {original}->{replacement}"

    return None


ENTITY_SWAPS = {
    # People
    "Mahatma Gandhi": "Subhas Chandra Bose",
    "Gandhi": "Bose",
    "Jawaharlal Nehru": "Sardar Patel",
    "Nehru": "Patel",
    "Narendra Modi": "Rahul Gandhi",
    "Shivaji": "Aurangzeb",
    # Places
    "England": "Australia",
    "India": "Pakistan",
    "Delhi": "Mumbai",
    "New Delhi": "Kolkata",
    # Orgs
    "Lok Sabha": "Rajya Sabha",
    "Rajya Sabha": "Lok Sabha",
    "BCCI": "ICC",
    "WHO": "UNESCO",
    "RBI": "SEBI",
}

def _perturb_entity(text: str) -> tuple[str, str] | None:
    """Swap a named entity for a plausible-but-wrong alternative."""
    # Try longest matches first to avoid partial replacements
    for original, replacement in sorted(ENTITY_SWAPS.items(), key=lambda x: len(x[0]), reverse=True):
        if original in text:
            new_text = text.replace(original, replacement, 1)
            return new_text, f"entity '{original}'->'{replacement}'"
    return None


ATTRIBUTE_SWAPS = [
    ("largest", "smallest"),
    ("smallest", "largest"),
    ("first", "last"),
    ("last", "first"),
    ("highest", "lowest"),
    ("lowest", "highest"),
    ("maximum", "minimum"),
    ("minimum", "maximum"),
    ("most", "least"),
    ("least", "most"),
    ("increased", "decreased"),
    ("decreased", "increased"),
    ("directly", "indirectly"),
    ("indirectly", "directly"),
    ("positive", "negative"),
    ("negative", "positive"),
]

def _perturb_attribute(text: str) -> tuple[str, str] | None:
    """Swap superlatives/comparatives/directional words."""
    lowered = text.lower()
    for original, replacement in ATTRIBUTE_SWAPS:
        if original in lowered:
            # Case-preserving replacement
            idx = lowered.find(original)
            actual = text[idx:idx+len(original)]
            if actual[0].isupper():
                replacement = replacement.capitalize()
            new_text = text[:idx] + replacement + text[idx+len(original):]
            return new_text, f"attribute '{actual}'->'{replacement}'"
    return None


NEGATION_TARGETS = [
    (r'\bis\b', 'is not'),
    (r'\bwas\b', 'was not'),
    (r'\bcan\b', 'cannot'),
    (r'\bhas\b', 'does not have'),
    (r'\bhave\b', 'do not have'),
    (r'\bare\b', 'are not'),
    (r'\bwere\b', 'were not'),
    (r'\bplays\b', 'does not play'),
]

def _perturb_negate(text: str) -> tuple[str, str] | None:
    """Insert a negation to flip the meaning."""
    for pattern, replacement in NEGATION_TARGETS:
        match = re.search(pattern, text)
        if match:
            # Don't negate if already negated
            preceding = text[max(0, match.start()-5):match.start()].lower()
            if 'not' in preceding or "n't" in preceding:
                continue
            new_text = text[:match.start()] + replacement + text[match.end():]
            return new_text, f"negation '{match.group()}'->'{replacement}'"
    return None


# ── Hindi perturbation helpers ──────────────────────────────────────────

HINDI_NUMBER_WORDS = {
    "पहला": "आखिरी",  # first → last
    "आखिरी": "पहला",  # last → first
    "सबसे बड़ा": "सबसे छोटा",  # largest → smallest
    "सबसे छोटा": "सबसे बड़ा",
    "प्रमुख": "गौण",  # major → minor
}

def _perturb_hindi(text: str) -> tuple[str, str] | None:
    """Try number perturbation on Hindi text, or Hindi word swaps."""
    # Numbers in Hindi text are often in ASCII digits
    result = _perturb_number(text)
    if result:
        return result
    # Try Hindi word swaps
    for original, replacement in HINDI_NUMBER_WORDS.items():
        if original in text:
            new_text = text.replace(original, replacement, 1)
            return new_text, f"hindi_swap '{original}'->'{replacement}'"
    return None


# ── Main generation logic ───────────────────────────────────────────────

def generate_perturbation(text: str, language: str) -> tuple[str, str] | None:
    """Try each perturbation strategy in priority order.
    Returns (perturbed_text, perturbation_description) or None."""
    strategies = []
    if language == "hi":
        strategies = [_perturb_hindi, _perturb_negate]
    else:
        strategies = [_perturb_number, _perturb_entity, _perturb_attribute, _perturb_negate]

    for strategy in strategies:
        result = strategy(text)
        if result:
            perturbed, desc = result
            # Sanity: perturbation must actually change the text
            if perturbed != text and len(perturbed) > 10:
                return perturbed, desc
    return None


def main():
    rows = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row["gold_verdict"] == "Verified":
                rows.append(row)

    print(f"Loaded {len(rows)} Verified claims from {INPUT_CSV}")

    # Sort by sem_sim descending — prioritize claims with good evidence
    rows.sort(key=lambda r: float(r.get("sem_sim") or 0), reverse=True)

    synthetics = []
    seen_texts = set()

    for row in rows:
        if len(synthetics) >= 120:  # generate up to 120, aim for ~100 after dedup
            break

        result = generate_perturbation(row["claim_text"], row["language"])
        if result is None:
            continue

        perturbed_text, perturbation_desc = result

        # Deduplicate
        if perturbed_text in seen_texts:
            continue
        seen_texts.add(perturbed_text)

        # Create synthetic claim ID
        text_hash = hashlib.md5(perturbed_text.encode()).hexdigest()[:8]
        synthetic_id = f"synth_{row['language']}_{text_hash}"

        synthetic_row = {
            "claim_id": synthetic_id,
            "source_query_id": row["source_query_id"],
            "domain": row["domain"],
            "language": row["language"],
            "source_llm": "synthetic_perturbation",
            "claim_text": perturbed_text,
            "sem_sim": "",  # to be filled by pipeline scoring
            "nli_prob": "",  # to be filled by pipeline scoring
            "kg_conf": "",
            "gold_verdict": "Hallucinated",
            "gold_reasoning": f"Synthetic perturbation of {row['claim_id']}: {perturbation_desc}",
            "evidence_url": row.get("evidence_url", ""),
            "gold_source": "synthetic_perturbation",
        }

        # Keep old columns if they exist in the schema
        for col in (fieldnames or []):
            if col not in synthetic_row:
                synthetic_row[col] = ""

        synthetics.append(synthetic_row)

    # Write output
    out_fields = [
        "claim_id", "source_query_id", "domain", "language", "source_llm",
        "claim_text", "sem_sim", "nli_prob", "kg_conf", "gold_verdict",
        "gold_reasoning", "evidence_url", "gold_source",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(synthetics)

    # Summary
    by_lang = {}
    by_strategy = {}
    for s in synthetics:
        lang = s["language"]
        by_lang[lang] = by_lang.get(lang, 0) + 1
        # Extract strategy from gold_reasoning
        desc = s["gold_reasoning"]
        if "year" in desc: key = "number_year"
        elif "number" in desc: key = "number_other"
        elif "entity" in desc: key = "entity_swap"
        elif "attribute" in desc: key = "attribute_swap"
        elif "negation" in desc: key = "negation"
        elif "hindi_swap" in desc: key = "hindi_swap"
        else: key = "other"
        by_strategy[key] = by_strategy.get(key, 0) + 1

    print(f"\nGenerated {len(synthetics)} synthetic hallucinations -> {OUTPUT_CSV}")
    print(f"  By language: {by_lang}")
    print(f"  By strategy: {by_strategy}")
    print(f"\n  Sample perturbations:")
    for s in synthetics[:8]:
        print(f"    [{s['language']}] {s['claim_text'][:90]}...")
        print(f"         {s['gold_reasoning']}")


if __name__ == "__main__":
    main()
