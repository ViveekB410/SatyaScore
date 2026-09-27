"""
nli_model_search.py -- which NLI model should judge claims against evidence?

Candidates are scored exactly as the live system does (demo corpus, XLM-R top-3
passages, relevance >= MIN_RELEVANCE_THRESHOLD, the most decisive passage's net
score 0.5 + 0.5*(P(entail) - P(contradict))).

SELECTION RULE (fixed before running): per language, the model (and score
variant) with the highest ROC-AUC on the TRAIN split (gold_train_clean.csv) is
chosen. The test split (gold_test_clean.csv) and round 3 are reported only, never
used to choose. An English-only model is a candidate for English only.

Probabilities are cached per model in results/_nli_cache/ (git-ignored).
    .venv/Scripts/python.exe nli_model_search.py [--models key ...]
Writes results/nli_model_search.md.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from compute_round2 import _norm1
from member3_backend.pipeline import MIN_RELEVANCE_THRESHOLD, NLI_EVIDENCE_TOP_K
from retrieval_eval import corpus_vectors, encode

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "results" / "_nli_cache"
MAXLEN, BS = 256, 8
N_BOOT, SEED = 2000, 42

MODELS = {  # key -> (hub id, languages it may judge)
    "mdeberta_base_xnli": ("MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", ("en", "hi")),  # current
    "mdeberta_base_2mil7": ("MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7", ("en", "hi")),
    "xlmr_large_xnli": ("joeddav/xlm-roberta-large-xnli", ("en", "hi")),
    "deberta_large_fever": ("MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli", ("en",)),
}
CURRENT = "mdeberta_base_xnli"


def load_sets() -> dict[str, pd.DataFrame]:
    cols = ["claim_id", "language", "claim_text", "gold_verdict"]
    sets = {name: pd.read_csv(ROOT / f"gold_{name}_clean.csv", encoding="utf-8")[cols]
            for name in ("train", "test")}
    r3 = pd.read_csv(ROOT / "round3" / "claims_round3.csv", encoding="utf-8").set_index("claim_id")
    A = pd.read_excel(ROOT / "round3" / "round3_annotator_A.xlsx").set_index("claim_id")
    B = pd.read_excel(ROOT / "round3" / "round3_annotator_B.xlsx").set_index("claim_id")
    d = pd.DataFrame({"a": A.verdict.map(_norm1), "b": B.verdict.map(_norm1)}).dropna()
    d = d[(d.a == d.b) & d.a.isin(["Verified", "Hallucinated"])]
    sets["round3"] = pd.DataFrame({"claim_id": d.index, "language": "en",
                                   "claim_text": r3.loc[d.index, "claim_text"].to_numpy(),
                                   "gold_verdict": d.a.to_numpy()})
    for df in sets.values():
        df.drop(df[~df.gold_verdict.isin(["Verified", "Hallucinated"])].index, inplace=True)
    return sets


def evidence(claims: pd.DataFrame) -> list[list[str]]:
    """Top-3 demo-corpus passages above the relevance threshold, per claim (as live)."""
    passages = json.loads((ROOT / "corpus_passages_demo.json").read_text(encoding="utf-8"))
    texts = [p["text"] for p in passages]
    S = encode("xlmr", claims.claim_text.tolist(), passage=False) @ corpus_vectors("xlmr", texts, "demo").T
    order = np.argsort(-S, axis=1)[:, :NLI_EVIDENCE_TOP_K]
    return [[texts[j] for j in row if S[i, j] >= MIN_RELEVANCE_THRESHOLD] for i, row in enumerate(order)]


def probs(key: str, premises: list[str], hypotheses: list[str]) -> np.ndarray:
    """(n, 3) [entail, neutral, contradict] for each pair; cached."""
    h = hashlib.sha1(json.dumps([premises, hypotheses], ensure_ascii=False).encode()).hexdigest()[:16]
    path = CACHE / f"{key}_{h}.npy"
    if path.exists():
        return np.load(path)
    hub, _ = MODELS[key]
    tok = AutoTokenizer.from_pretrained(hub)
    model = AutoModelForSequenceClassification.from_pretrained(hub).eval()
    lab = {v.lower(): k for k, v in model.config.id2label.items()}
    order = [lab["entailment"], lab["neutral"], lab["contradiction"]]
    out = []
    for i in range(0, len(premises), BS):
        enc = tok(premises[i:i + BS], hypotheses[i:i + BS], return_tensors="pt",
                  truncation="only_first", max_length=MAXLEN, padding=True)
        with torch.no_grad():
            p = torch.softmax(model(**enc).logits, dim=-1).numpy()
        out.append(p[:, order])
        if (i // BS) % 25 == 0:
            print(f"  {key}: {min(i + BS, len(premises))}/{len(premises)}", flush=True)
    arr = np.concatenate(out) if out else np.zeros((0, 3))
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return arr


def claim_scores(ev: list[list[str]], P: np.ndarray) -> dict[str, np.ndarray]:
    """Two score variants per claim (0.5 when no evidence, as live):
    net      most decisive passage of 0.5 + 0.5*(e - c)            (current)
    support  0.5 + 0.5*(max_e - max_c) over the passages"""
    net, sup, k = [], [], 0
    for prem in ev:
        rows = P[k:k + len(prem)]
        k += len(prem)
        if len(rows) == 0:
            net.append(0.5)
            sup.append(0.5)
            continue
        n = 0.5 + 0.5 * (rows[:, 0] - rows[:, 2])
        net.append(float(n[np.argmax(np.abs(n - 0.5))]))
        sup.append(float(0.5 + 0.5 * (rows[:, 0].max() - rows[:, 2].max())))
    return {"net": np.array(net), "support": np.array(sup)}


def auc_ci(y: np.ndarray, s: np.ndarray) -> tuple[float, float, float]:
    rng = np.random.default_rng(SEED)
    boots = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if len(set(y[i])) == 2:
            boots.append(roc_auc_score(y[i], s[i]))
    return roc_auc_score(y, s), *np.percentile(boots, [2.5, 97.5])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=list(MODELS))
    args = ap.parse_args()
    sets = load_sets()
    ev = {name: evidence(df) for name, df in sets.items()}
    rows = []
    for key in args.models:
        langs = MODELS[key][1]
        for name, df in sets.items():
            keep = df.language.isin(langs).to_numpy()
            sub, sub_ev = df[keep], [e for e, k in zip(ev[name], keep) if k]
            prem = [p for e in sub_ev for p in e]
            hyp = [c for c, e in zip(sub.claim_text, sub_ev) for _ in e]
            sc = claim_scores(sub_ev, probs(key, prem, hyp))
            for lang in langs:
                m = (sub.language == lang).to_numpy()
                y = (sub.gold_verdict[m] == "Verified").astype(int).to_numpy()
                if len(set(y)) < 2:
                    continue
                for variant, s in sc.items():
                    a, lo, hi = auc_ci(y, s[m])
                    rows.append({"model": key, "variant": variant, "set": name, "lang": lang,
                                 "n": len(y), "n_hallu": int((y == 0).sum()), "auc": a, "lo": lo, "hi": hi})
    res = pd.DataFrame(rows)
    res.to_csv(ROOT / "results" / "nli_model_search.csv", index=False)

    L = ["# NLI model search\n",
         "Scored as the live system does (demo corpus, top-3 passages, relevance ≥ "
         f"{MIN_RELEVANCE_THRESHOLD}). ROC-AUC with 95% bootstrap CI (0.5 = chance). "
         "**Selection rule (fixed before running): per language, highest TRAIN AUC wins; test and "
         "round 3 are reported only.**\n"]
    for lang in ("en", "hi"):
        r = res[res.lang == lang]
        piv = r.pivot_table(index=["model", "variant"], columns="set", values="auc")
        best = r[r.set == "train"].sort_values("auc", ascending=False).iloc[0]
        L += [f"## {lang.upper()}", "| model | variant | train AUC | test AUC [95% CI] | round-3 AUC |",
              "| --- | --- | --- | --- | --- |"]
        for (model, variant), row in piv.iterrows():
            t = r[(r.model == model) & (r.variant == variant) & (r.set == "test")]
            test = f"{t.auc.iloc[0]:.3f} [{t.lo.iloc[0]:.3f}, {t.hi.iloc[0]:.3f}]" if len(t) else "—"
            r3 = f"{row['round3']:.3f}" if "round3" in row and not np.isnan(row["round3"]) else "—"
            mark = " **←**" if (model, variant) == (best.model, best.variant) else ""
            L.append(f"| {model}{mark} | {variant} | {row['train']:.3f} | {test} | {r3} |")
        n = r[(r.set == "train")].iloc[0]
        L += ["", f"- Chosen for {lang.upper()} (train n = {n.n}, Hallucinated {n.n_hallu}): "
                  f"**{best.model} / {best.variant}**.", ""]
    out = ROOT / "results" / "nli_model_search.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
