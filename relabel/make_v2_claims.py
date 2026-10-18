"""
relabel/make_v2_claims.py -- Version 2 data, step 1a: re-extract claims from the 100 original chatbot
answers (raw_responses.json; Llama 3.3 70B, 50 English + 50 Hindi questions, five domains) with the
CURRENT claim extractor. The old 456-claim set was extracted by an earlier extractor, and about 31 of its
45 training "hallucinations" were artefacts of that extractor (results/hallucination_detection_study.md).

No label is created or copied here: the claims are labelled blind by the four authors later
(relabel/assign.py). Writes relabel/claims_v2_original.csv.

    .venv/Scripts/python.exe relabel/make_v2_claims.py
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from member3_backend.claim_extractor import ClaimExtractor  # noqa: E402

RAW = ROOT / "raw_responses.json"
OUT = ROOT / "relabel" / "claims_v2_original.csv"


def responses(entry: dict) -> list[dict]:
    r = entry["responses"]
    return ast.literal_eval(r) if isinstance(r, str) else r


def main() -> None:
    data = json.loads(RAW.read_text(encoding="utf-8"))
    extractor = ClaimExtractor()
    rows = []
    for qid, entry in data.items():
        for resp in responses(entry):
            text = resp["response_text"]
            try:
                claims = extractor.extract(text, entry["language"])
            except ValueError:
                claims = []
            for n, c in enumerate(claims):
                rows.append({"claim_id": f"v2_{qid}_c{n:02d}", "source_query_id": qid, "set": "original",
                             "language": entry["language"], "domain": entry["domain"],
                             "source_llm": resp.get("source_llm", ""), "source_question": entry["query_text"],
                             "claim_text": c.text, "start_char": c.start_char, "end_char": c.end_char,
                             "extraction_method": c.extraction_method,
                             "needs_context": bool(c.had_unresolved_pronoun), "full_response": text})
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"{len(df)} claims from {df.source_query_id.nunique()} answers -> {OUT.relative_to(ROOT)}")
    print(df.groupby(["language", "domain"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
