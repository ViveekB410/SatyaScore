"""
llm_verifier_eval.py -- does an LLM verifier beat the NLI model?

Same claims and the SAME evidence as the live system and nli_model_search.py
(demo corpus, top-3 passages, relevance cut). For each claim the LLM
(member1_model/llm_verifier.py) returns a verdict and P(true); the current NLI
score (mDeBERTa-base-xnli, net) is computed alongside.

DECISION RULE (fixed before running):
  - Chosen on the TRAIN split, English and Hindi pooled (Hindi alone has 7
    Hallucinated claims, below the 10-positive floor).
  - A mode replaces NLI only if its pooled train ROC-AUC beats NLI with a paired
    bootstrap 95% CI entirely above 0; if both modes do, the higher train AUC wins.
  - It is then used for Hindi too, unless its Hindi train AUC is below NLI's.
  - Test and round 3 are reported only, never used to choose.

Run in YOUR PowerShell (the key stays in your shell; nothing prints it):
    $env:GROQ_API_KEY = "gsk_..."
    .venv/Scripts/python.exe llm_verifier_eval.py
Resumable: answers are cached in results/_llm_cache/ (git-ignored). If Groq's
daily limit is reached the run stops cleanly; run the same command later.
Writes results/llm_verifier.md and results/llm_verifier.csv.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from member1_model.llm_verifier import (DEFAULT_MODEL, LLMQuotaExhausted, LLMVerifier,
                                        LLMVerifierError)
from nli_model_search import claim_scores, evidence, load_sets, probs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "results" / "_llm_cache"
SET_ORDER = ("round3", "test", "train")  # small sets first: early insight if a quota stops the run
N_BOOT, SEED = 2000, 42
LOW, HIGH = 0.35, 0.65


def _key(model: str, mode: str, claim: str, passages: list[str]) -> str:
    return hashlib.sha1(json.dumps([model, mode, claim, passages], ensure_ascii=False).encode()).hexdigest()


def load_cache(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                out[rec["key"]] = rec
    return out


def run_llm(model: str, mode: str, sets: dict, ev: dict) -> tuple[dict, bool]:
    """Fill the cache for every claim; returns (cache, finished)."""
    path = CACHE / f"{model.replace('/', '_')}_{mode}.jsonl"
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = load_cache(path)
    verifier = LLMVerifier(model=model, mode=mode)
    todo = [(name, c, e) for name in SET_ORDER for c, e in zip(sets[name].claim_text, ev[name])
            if _key(model, mode, c, e) not in cache]
    print(f"[{mode}] {len(cache)} cached, {len(todo)} to ask", flush=True)
    with path.open("a", encoding="utf-8") as f:
        for i, (name, claim, passages) in enumerate(todo, 1):
            try:
                j = verifier.verify(claim, passages)
            except LLMQuotaExhausted as e:
                print(f"\n[{mode}] stopped: {e} Progress is saved; run the same command later.", flush=True)
                return cache, False
            rec = {"key": _key(model, mode, claim, passages), "verdict": j.verdict, "p_true": j.p_true,
                   "reason": j.reason}
            cache[rec["key"]] = rec
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0 or i == len(todo):
                print(f"[{mode}] {i}/{len(todo)} ({name}); tokens so far {verifier.tokens_used}", flush=True)
    return cache, True


def tier(s: np.ndarray) -> np.ndarray:
    return np.where(s < LOW, "Hallucinated", np.where(s > HIGH, "Verified", "Uncertain"))


def paired_auc(y, a, b):
    rng = np.random.default_rng(SEED)
    d = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if len(set(y[i])) == 2:
            d.append(roc_auc_score(y[i], b[i]) - roc_auc_score(y[i], a[i]))
    lo, hi = np.percentile(d, [2.5, 97.5])
    return roc_auc_score(y, b) - roc_auc_score(y, a), lo, hi


def accuracy(gold: np.ndarray, verdicts: np.ndarray) -> str:
    right = int((verdicts == gold).sum())
    unc = int((verdicts == "Uncertain").sum())
    committed = len(gold) - unc
    return (f"{right}/{len(gold)} ({right / len(gold):.0%}) · Uncertain {unc} · "
            f"when it commits {right}/{committed} ({right / max(committed, 1):.0%})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--modes", nargs="+", default=["grounded", "open"], choices=["grounded", "open"])
    args = ap.parse_args()

    sets = load_sets()
    ev = {name: evidence(df) for name, df in sets.items()}
    # current NLI score on the same evidence (cached by nli_model_search.probs)
    nli = {}
    for name, df in sets.items():
        prem = [p for e in ev[name] for p in e]
        hyp = [c for c, e in zip(df.claim_text, ev[name]) for _ in e]
        nli[name] = claim_scores(ev[name], probs("mdeberta_base_xnli", prem, hyp))["net"]

    llm, finished = {}, {}
    for mode in args.modes:
        try:
            llm[mode], finished[mode] = run_llm(args.model, mode, sets, ev)
        except LLMVerifierError as e:
            sys.exit(f"Stopping: {e}")

    kg3 = pd.read_csv(ROOT / "round3" / "signals_round3_kgfix.csv").set_index("claim_id").kg_conf
    rows, L = [], [f"# LLM verifier vs NLI ({args.model})\n",
                   "Same claims and evidence as the live system (demo corpus, top-3 passages). "
                   "Verdict accuracy counts Uncertain as not correct. **Decision rule (fixed before "
                   "running):** pooled EN+HI TRAIN AUC; a mode replaces NLI only if ΔAUC vs NLI has a "
                   "95% CI entirely above 0. Test and round 3 are reported only.\n"]
    decision_rows = {}
    for name in SET_ORDER:
        df = sets[name]
        y = (df.gold_verdict == "Verified").astype(int).to_numpy()
        gold = df.gold_verdict.to_numpy()
        L += [f"## {name} (n = {len(df)}, Hallucinated {int((y == 0).sum())})", ""]
        L.append(f"- NLI (current): AUC {roc_auc_score(y, nli[name]):.3f}; verdicts {accuracy(gold, tier(nli[name]))}")
        for mode, cache in llm.items():
            recs = [cache.get(_key(args.model, mode, c, e)) for c, e in zip(df.claim_text, ev[name])]
            if any(r is None for r in recs):
                L.append(f"- LLM {mode}: incomplete ({sum(r is not None for r in recs)}/{len(recs)} answered)")
                continue
            p = np.array([r["p_true"] if r["p_true"] is not None else 0.5 for r in recs])
            v = np.array([r["verdict"] or "Uncertain" for r in recs])
            d, lo, hi = paired_auc(y, nli[name], p)
            L.append(f"- LLM {mode}: AUC {roc_auc_score(y, p):.3f} (Δ vs NLI {d:+.3f} [{lo:+.3f}, {hi:+.3f}]); "
                     f"verdicts {accuracy(gold, v)}; unparsable {sum(r['verdict'] is None for r in recs)}")
            for lang in ("en", "hi"):
                m = (df.language == lang).to_numpy()
                if m.any() and len(set(y[m])) == 2:
                    rows.append({"set": name, "mode": mode, "lang": lang, "n": int(m.sum()),
                                 "n_hallu": int((y[m] == 0).sum()), "auc_llm": roc_auc_score(y[m], p[m]),
                                 "auc_nli": roc_auc_score(y[m], nli[name][m])})
            if name == "train":
                decision_rows[mode] = (d, lo, hi, roc_auc_score(y, p))
            if name == "round3":  # the live system: KG decides when it answers, else the judge
                kg = kg3.reindex(df.claim_id).to_numpy(dtype=float)
                has = ~np.isnan(kg)
                cur = np.where(has, tier(np.nan_to_num(kg)), tier(nli[name]))
                new = np.where(has, tier(np.nan_to_num(kg)), v)
                L += [f"  - system with KG: current (KG else NLI) {accuracy(gold, cur)}",
                      f"  - system with KG: new (KG else LLM {mode}) {accuracy(gold, new)}"]
        L.append("")
    pd.DataFrame(rows).to_csv(ROOT / "results" / "llm_verifier.csv", index=False)

    L.append("## Decision")
    if len(decision_rows) < len(args.modes) or not all(finished.values()):
        L.append("- **Pending:** the train split is not complete for every mode (quota); re-run the "
                 "same command to finish. No change to the live system.")
    else:
        passing = {m: r for m, r in decision_rows.items() if r[1] > 0}
        if not passing:
            L.append("- **Not adopted:** no mode beats NLI on train with a CI above 0.")
        else:
            best = max(passing, key=lambda m: passing[m][3])
            d, lo, hi, a = passing[best]
            L.append(f"- **Adopt LLM {best}** (train ΔAUC {d:+.3f} [{lo:+.3f}, {hi:+.3f}]).")
            hi_row = [r for r in rows if r["set"] == "train" and r["mode"] == best and r["lang"] == "hi"]
            if hi_row and hi_row[0]["auc_llm"] < hi_row[0]["auc_nli"]:
                L.append("- Hindi keeps NLI (its Hindi train AUC is below NLI's).")
            else:
                L.append("- Used for Hindi too (Hindi train AUC not below NLI's).")
    out = ROOT / "results" / "llm_verifier.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
