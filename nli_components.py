"""
nli_components.py -- IMPROVEMENT_PLAN.md Phase 3.3: is NLI's CONTRADICTION
probability a better hallucination signal than the current net score?

The stored signal (gold_final_scored.csv nli_prob) is net = 0.5 + 0.5*(entail -
contradict) on each claim's top-1 passage; the three components were not kept.
This recomputes them exactly as recompute_signals.py did (XLM-R top-1 passage
from the experiment corpus, 192-token cap, batches of 16) and FIRST checks that
the recomputed net reproduces the stored nli_prob.

DECISION RULE (fixed before running): contradiction becomes a separate signal
only if its English AUC beats the net score with a paired-bootstrap 95% CI
(2,000 resamples) entirely above 0.

Writes results/nli_components.csv and results/contradiction_signal.md.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score

from member1_model.nli_scorer import NLIScorer
from retrieval_eval import corpus_vectors, encode

ROOT = Path(__file__).resolve().parent
MAXLEN, BS = 192, 16  # identical to recompute_signals.py
N_BOOT, SEED = 2000, 42


def components(premises, hypotheses):
    s = NLIScorer()
    s._ensure_loaded()
    idx = {v.lower(): k for k, v in s._model.config.id2label.items()}
    out = []
    for i in range(0, len(premises), BS):
        enc = s._tokenizer(premises[i:i + BS], hypotheses[i:i + BS], return_tensors="pt",
                           truncation=True, max_length=MAXLEN, padding=True).to(s.device)
        with torch.no_grad():
            p = torch.softmax(s._model(**enc).logits, dim=-1).cpu().numpy()
        out += [(r[idx["entailment"]], r[idx["neutral"]], r[idx["contradiction"]]) for r in p]
        print(f"  nli {min(i + BS, len(premises))}/{len(premises)}", flush=True)
    return np.array(out)


def paired(y, a, b):
    """AUC(b) - AUC(a) with a paired bootstrap 95% CI."""
    rng = np.random.default_rng(SEED)
    d = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if len(set(y[i])) == 2:
            d.append(roc_auc_score(y[i], b[i]) - roc_auc_score(y[i], a[i]))
    lo, hi = np.percentile(d, [2.5, 97.5])
    return roc_auc_score(y, b) - roc_auc_score(y, a), lo, hi


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true",
                    help="rebuild the report from results/nli_components.csv (no NLI rerun)")
    args = ap.parse_args()
    comp_csv = ROOT / "results" / "nli_components.csv"

    if args.reuse:
        df = pd.read_csv(comp_csv, encoding="utf-8")
    else:
        passages = json.loads((ROOT / "corpus_passages.json").read_text(encoding="utf-8"))
        texts = [p["text"] for p in passages]
        df = pd.read_csv(ROOT / "gold_final_scored.csv", encoding="utf-8")
        S = encode("xlmr", df.claim_text.tolist(), passage=False) @ corpus_vectors("xlmr", texts).T
        top1 = S.argmax(axis=1)
        print(f"retrieved top-1 for {len(df)} claims; scoring NLI...", flush=True)
        C = components([texts[j] for j in top1], df.claim_text.tolist())
        df["p_entail"], df["p_neutral"], df["p_contra"] = C[:, 0], C[:, 1], C[:, 2]
        df["net_recomputed"] = 0.5 + 0.5 * (df.p_entail - df.p_contra)
        df[["claim_id", "language", "gold_verdict", "nli_prob", "net_recomputed",
            "p_entail", "p_neutral", "p_contra"]].to_csv(comp_csv, index=False, encoding="utf-8")
    diff = (df.net_recomputed - df.nli_prob).abs()

    q = pd.read_csv(ROOT / "claim_quality.csv")[["claim_id", "quality_flag"]]
    ev = df.merge(q, on="claim_id")
    ev = ev[(ev.quality_flag == "ok") & ev.gold_verdict.isin(["Verified", "Hallucinated"])]

    L = ["# Contradiction as a hallucination signal (Phase 3.3)\n",
         "NLI components recomputed exactly as `recompute_signals.py` did (top-1 XLM-R passage, "
         "experiment corpus, 192-token cap). **Reproduction check** — recomputed net vs stored "
         f"`nli_prob`: max |diff| = **{diff.max():.4f}**, median {diff.median():.4f} "
         f"(fp16 noise is ~1e-3).\n",
         "**Decision rule (fixed before running):** adopt contradiction as a separate signal only "
         "if its English AUC beats the net score with a paired-bootstrap 95% CI entirely above 0.\n",
         "AUC = how well the score ranks Verified above Hallucinated (0.5 = chance); for "
         "contradiction the score is 1 − P(contradiction). Well-formed claims.\n",
         "| Lang | n V / H | net (current) | 1 − P(contra) | P(entail) | ΔAUC contra − net [95% CI] |",
         "| --- | --- | --- | --- | --- | --- |"]
    verdicts, points = {}, {}
    for lang in ("en", "hi"):
        d = ev[ev.language == lang]
        y = (d.gold_verdict == "Verified").astype(int).to_numpy()
        net, con, ent = d.nli_prob.to_numpy(), 1 - d.p_contra.to_numpy(), d.p_entail.to_numpy()
        dlt, lo, hi = paired(y, net, con)
        verdicts[lang], points[lang] = lo, (dlt, hi, roc_auc_score(y, ent))
        L.append(f"| {lang.upper()} | {y.sum()} / {(1 - y).sum()} | {roc_auc_score(y, net):.3f} | "
                 f"{roc_auc_score(y, con):.3f} | {roc_auc_score(y, ent):.3f} | "
                 f"{dlt:+.3f} [{lo:+.3f}, {hi:+.3f}] |")
    en_d, en_hi, en_ent = points["en"]
    if verdicts["en"] > 0:
        decision = "- **Adopt**: contradiction beats the net score on English (CI entirely above 0)."
    elif en_d > 0:
        decision = (f"- **Not adopted, but suggestive.** English ΔAUC is {en_d:+.3f}, and its CI "
                    f"crosses 0 (lower bound {verdicts['en']:+.3f}), so the gain is not established "
                    f"at this sample size. Entailment alone is at chance (AUC {en_ent:.3f}), which fits "
                    f"the net score diluting the contradiction probability with entailment noise. "
                    f"Re-test with the same fixed rule once more Hallucinated claims are annotated.")
    else:
        decision = ("- **Not adopted**: on English, contradiction does not beat the net score.")
    L += ["", "## Decision", decision,
          "- Hindi has 9 Hallucinated claims; its row is noise and does not decide anything.",
          "- KG (γ): 0 of 456 claims get a KG signal. The PRD requires the three-signal formula "
          "(FR-04), so γ stays in the formula and is reported as non-functional on these "
          "descriptive claims, not silently dropped.\n"]
    out = ROOT / "results" / "contradiction_signal.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
