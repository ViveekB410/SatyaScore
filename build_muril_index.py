"""
build_muril_index.py -- FR-02: MuRIL-embedded copy of a corpus, so transliterated
(Latin-script) Hindi queries embedded with MuRIL are searched against MuRIL
vectors, never across vector spaces.

    python build_muril_index.py            # demo corpus (the live API's)
    python build_muril_index.py --corpus experiment

Writes corpus_vectors_demo_muril.npy / corpus_vectors_muril.npy, row-aligned
with corpus_passages_demo.json / corpus_passages.json.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np

from member1_model.embeddings import CrossLingualEmbedder

ROOT = Path(__file__).resolve().parent
CORPORA = {"demo": ("corpus_passages_demo.json", "corpus_vectors_demo_muril.npy"),
           "experiment": ("corpus_passages.json", "corpus_vectors_muril.npy")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=list(CORPORA), default="demo")
    args = ap.parse_args()
    src, out = CORPORA[args.corpus]
    texts = [p["text"] for p in json.loads((ROOT / src).read_text(encoding="utf-8"))]
    e = CrossLingualEmbedder()
    v = e._normalise(e._batched_encode(e.muril, texts))
    np.save(ROOT / out, v.astype(np.float32))
    print(f"wrote {out}: {v.shape} from {src}")


if __name__ == "__main__":
    main()
