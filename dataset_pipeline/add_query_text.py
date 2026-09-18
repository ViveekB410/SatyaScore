"""
Adds the original question text to the pilot CSV — the export left this
out (only source_query_id was included, e.g. "healthcare_en_03", not the
actual question), which makes claims hard to judge without context.

WHERE THIS GOES: dataset_pipeline/add_query_text.py

Run:
    python -m dataset_pipeline.add_query_text
"""

import csv
from pathlib import Path

from dataset_pipeline.query_bank import get_seed_queries

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = PROJECT_ROOT / "dataset_pipeline" / "output" / "pilot_annotation_BLIND.csv"
OUTPUT_CSV = PROJECT_ROOT / "dataset_pipeline" / "output" / "pilot_annotation_BLIND.csv"  # overwrite in place

# query_id -> question text, e.g. "healthcare_en_03" -> "What causes Type 2 diabetes?"
query_lookup = {q.query_id: q.text for q in get_seed_queries()}

with open(INPUT_CSV, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

missing = 0
for row in rows:
    question = query_lookup.get(row["source_query_id"])
    if question is None:
        missing += 1
        question = "(question text not found — check source_query_id)"
    row["source_query_text"] = question

# Insert the new column right after source_query_id, not at the end, so
# annotators see the question before the claim while scanning left to right.
new_fieldnames = []
for name in fieldnames:
    new_fieldnames.append(name)
    if name == "source_query_id":
        new_fieldnames.append("source_query_text")

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=new_fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Added source_query_text to {len(rows)} rows -> {OUTPUT_CSV}")
if missing:
    print(f"WARNING: {missing} rows had no matching question (check for typos in query_id)")
