"""
v2data/make_test_sample.py -- the fixed held-out test sample (results/v2_data_PROTOCOL.md, "Held-out test
sample"): up to 12 true and 12 false items per (set, language), each cell with its own seed. Mu-SHROOM: labelled
claims. Writes v2data/sets/<set>_testS.csv (same columns as the test split).
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

import sys

SETS = Path(__file__).resolve().parent / "sets"
SEED, PER_CELL = 20261012, 12
# --name testS2: a second sample that excludes every testS item (protocol: "Fix round")
TAG = sys.argv[sys.argv.index("--name") + 1] if "--name" in sys.argv else "testS"
SEED_TAG = {"testS": "test", "testS2": "test2", "testS3": "test3", "testL": "testL"}[TAG]
EARLIER = {"testS": [], "testS2": ["testS"], "testS3": ["testS", "testS2"],
           "testL": ["testS", "testS2", "testS3"]}[TAG]  # samples already used
if TAG == "testL":  # the large final sample (protocol: "Large final test")
    PER_CELL = 60

for path in sorted(SETS.glob("*_test.csv")):
    name = path.stem[:-5]
    d = pd.read_csv(path, encoding="utf-8", dtype=str)
    for e in EARLIER:
        if not (SETS / f"{name}_{e}.csv").exists():
            continue
        used = set(pd.read_csv(SETS / f"{name}_{e}.csv", encoding="utf-8", dtype=str).item_id)
        d = d[~d.item_id.isin(used)]
    parts = []
    for (lang, label), g in sorted(d.groupby(["language", "label"])):
        ids = sorted(g.item_id)
        random.Random(f"{SEED}-{SEED_TAG}-{name}-{lang}-{label}").shuffle(ids)
        parts.append(g[g.item_id.isin(ids[:PER_CELL])])
    if not parts:  # every item of this set was used by an earlier sample
        print(f"{name}_{TAG}: none left")
        continue
    out = pd.concat(parts).sort_values("item_id")
    out.to_csv(SETS / f"{name}_{TAG}.csv", index=False, encoding="utf-8")
    print(f"{name}_{TAG}: {len(out)} items", out.groupby(["language", "label"]).size().to_dict())
