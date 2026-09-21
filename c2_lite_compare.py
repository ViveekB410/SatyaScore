"""
c2_lite_compare.py  --  TASK C2-lite comparison.

Measures whether sentence-level NLI premises (the C2-lite change in
member3_backend/pipeline.py) actually make NLI better at telling Hallucinated
from Verified claims. It runs the SAME claim selection and experiment corpus as
diagnose_retrieval.py, retrieves once, and then scores NLI TWICE:

    switch OFF -> whole retrieved passage is the premise   (pre-C2-lite baseline)
    switch ON  -> each passage split into sentences         (C2-lite)

using the shared `passage_to_premises` helper the live pipeline uses, so the
comparison measures exactly what ships. For each mode it reports, per language
and overall:

    * neutral rate  -- fraction of claim-premise NLI units landing in neutral
    * NLI AUC       -- how well the per-claim net score separates Verified (1)
                       from Hallucinated (0); this, not the neutral rate, is the
                       metric that decides whether the change is worth keeping.

The per-claim net score uses the pipeline's own rule unchanged: net =
0.5 + 0.5*(entail - contradict), and the MOST DECISIVE unit per claim
(max |net - 0.5|). Retrieval, MIN_RELEVANCE_THRESHOLD, NLI_EVIDENCE_TOP_K,
weights and cut-points are all untouched -- premise granularity is the only
variable.

Because ~100 claims makes a single ΔAUC point estimate noisy, the deciding
number is a PAIRED bootstrap 95% CI on ΔAUC = AUC(on) - AUC(off): N_BOOT
resamples of claims, each scored both ways. DECISION RULE: the default flips on
only if the English CI lower bound is above 0 (a significant improvement, not
just a positive point estimate). The CI is written next to the point estimates.

Writes results/c2_lite_comparison.md. Reads only; regenerates nothing else.

    python c2_lite_compare.py            # full (slow on CPU; real numbers need a GPU)
    python c2_lite_compare.py --limit 8  # quick smoke test
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member3_backend.faiss_retriever import FAISSRetriever
from member3_backend.pipeline import (
    MIN_RELEVANCE_THRESHOLD,
    NLI_EVIDENCE_TOP_K,
    MAX_SENTENCES_PER_PASSAGE,
    passage_to_premises,
)

ROOT = Path(__file__).resolve().parent
SEED = 42

# NLI AUC before this change, from RESULTS_SUMMARY.md (the number we compare against).
BASELINE_AUC = {"en": 0.558, "hi": 0.510}

# Paired bootstrap: resample claims (with replacement) and recompute the SAME
# resample both ways, so the ΔAUC keeps its pairing. ~100 claims makes a single
# ΔAUC point estimate noisy; the 95% CI is what actually decides the change.
N_BOOT = 2000


def _net(res) -> float:
    """Pipeline's net score: 1.0 entailed, 0.0 contradicted, 0.5 neutral."""
    return 0.5 + 0.5 * (res.entailment_prob - res.contradiction_prob)


def _is_neutral(res) -> bool:
    probs = {"entailment": res.entailment_prob, "neutral": res.neutral_prob,
             "contradiction": res.contradiction_prob}
    return max(probs, key=probs.get) == "neutral"


def select_claims(gold: pd.DataFrame, limit: int) -> pd.DataFrame:
    """All Hallucinated + a matched per-language sample of Verified -- identical
    to diagnose_retrieval.py so the two diagnostics look at the same claims."""
    parts = []
    for lang in ("en", "hi"):
        hall = gold[(gold.language == lang) & (gold.gold_verdict == "Hallucinated")]
        ver = gold[(gold.language == lang) & (gold.gold_verdict == "Verified")]
        ver_s = ver.sample(n=min(len(hall), len(ver)), random_state=SEED) if len(ver) else ver
        parts.append(hall)
        parts.append(ver_s)
    sel = pd.concat(parts).reset_index(drop=True)
    if limit:
        sel = sel.groupby("gold_verdict", group_keys=False).head(max(1, limit // 2)).head(limit)
    return sel


def score_mode(sel, retrieved, nli, sentence_level: bool):
    """For one switch state, return per-claim rows with net score + neutral flags.
    `retrieved` is the shared top-k retrieval per claim (built once, reused)."""
    # Build one flattened batch across ALL claims (mirrors the pipeline's Phase B).
    idx, premises, hyps = [], [], []
    for i, passages in enumerate(retrieved):
        claim_text = sel.iloc[i]["claim_text"]
        for p in passages:  # already filtered by MIN_RELEVANCE_THRESHOLD
            for u in passage_to_premises(p.text, sentence_level=sentence_level):
                idx.append(i)
                premises.append(u)
                hyps.append(claim_text)

    results = nli.score_batch(
        claim_ids=[sel.iloc[i]["claim_id"] for i in idx],
        premises=premises, hypotheses=hyps,
    ) if premises else []

    grouped = defaultdict(list)
    for i, res in zip(idx, results):
        grouped[i].append(res)

    rows = []
    n_units_total = 0
    n_units_neutral = 0
    for i in range(len(sel)):
        res_list = grouped.get(i, [])
        n_units_total += len(res_list)
        n_units_neutral += sum(1 for r in res_list if _is_neutral(r))
        if res_list:
            nets = [_net(r) for r in res_list]
            net = max(nets, key=lambda s: abs(s - 0.5))  # most decisive -- unchanged rule
        else:
            net = 0.5  # no relevant evidence -> pipeline surfaces Uncertain (0.5)
        rows.append({
            "language": sel.iloc[i]["language"],
            "label": sel.iloc[i]["gold_verdict"],
            "y": 1 if sel.iloc[i]["gold_verdict"] == "Verified" else 0,
            "net": net,
            "n_units": len(res_list),
        })
    df = pd.DataFrame(rows)
    neutral_rate = (n_units_neutral / n_units_total) if n_units_total else float("nan")
    return df, neutral_rate, n_units_total


def auc_for(df: pd.DataFrame) -> float:
    y = df["y"].to_numpy()
    if len(set(y.tolist())) < 2:
        return float("nan")  # need both classes
    # higher net = more "verified"; roc_auc_score(y, score) with Verified=1
    return float(roc_auc_score(y, df["net"].to_numpy()))


def bootstrap_delta_ci(sub: pd.DataFrame, n_boot: int = N_BOOT, seed: int = SEED):
    """Paired bootstrap of ΔAUC = AUC(on) − AUC(off).

    `sub` has columns y, net_off, net_on, one row per claim (off and on scored on
    the SAME claim, so the pairing is preserved). Each resample draws claims with
    replacement and scores that identical resample both ways, then takes the
    difference -- this cancels the shared claim-sampling noise, which an
    unpaired CI would leave in. Resamples that lose a class (AUC undefined) are
    skipped and counted. Returns (delta_point, ci_low, ci_high, n_valid, n_boot).
    """
    y = sub["y"].to_numpy()
    off = sub["net_off"].to_numpy()
    on = sub["net_on"].to_numpy()
    if len(set(y.tolist())) < 2:
        return (float("nan"), float("nan"), float("nan"), 0, n_boot)
    point = float(roc_auc_score(y, on) - roc_auc_score(y, off))
    rng = np.random.default_rng(seed)
    n = len(y)
    deltas = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)  # sample claims with replacement
        yb = y[idx]
        if len(set(yb.tolist())) < 2:
            continue  # AUC undefined on a single-class resample
        deltas.append(roc_auc_score(yb, on[idx]) - roc_auc_score(yb, off[idx]))
    if not deltas:
        return (point, float("nan"), float("nan"), 0, n_boot)
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    return (point, float(lo), float(hi), len(deltas), n_boot)


def _fmt(x) -> str:
    return f"{x:.3f}" if isinstance(x, float) and x == x else "n/a"


def write_off_partial(off_df, off_neutral, off_units, n_claims, n_passages, device) -> Path:
    """Persist the switch-OFF results the moment they finish, BEFORE the ON pass.
    The ON pass is the larger, riskier one (it OOMed the T4 before chunking); if it
    ever fails again, the expensive OFF work is already on disk and not lost. A
    completed full run supersedes this with results/c2_lite_comparison.md."""
    en = auc_for(off_df[off_df.language == "en"])
    hi = auc_for(off_df[off_df.language == "hi"])
    ov = auc_for(off_df)
    lines = [
        "# C2-lite — switch-OFF partial (whole-passage baseline)", "",
        "_Written as soon as the switch-OFF pass finished, before the switch-ON pass, so "
        "an ON-run failure cannot lose the OFF work again. A full run supersedes this file "
        "with `c2_lite_comparison.md`._", "",
        f"- Claims: {n_claims}, experiment corpus ({n_passages} passages), device: {device}.",
        f"- NLI premise units scored (off): {off_units}. Neutral rate (off): {_fmt(off_neutral)}.",
        "", "| Group | NLI AUC (switch OFF) |", "| --- | --- |",
        f"| EN | {_fmt(en)} |", f"| HI | {_fmt(hi)} |", f"| Overall | {_fmt(ov)} |", "",
    ]
    out = ROOT / "results" / "c2_lite_off_partial.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote OFF partial -> {out}", flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap total claims (quick smoke test)")
    args = ap.parse_args()

    gold = pd.read_csv(ROOT / "gold_final.csv", encoding="utf-8")
    sel = select_claims(gold, args.limit)
    print(f"comparing on {len(sel)} claims "
          f"({(sel.gold_verdict=='Hallucinated').sum()} Hallucinated, "
          f"{(sel.gold_verdict=='Verified').sum()} Verified)", flush=True)

    # experiment corpus + index (same as the pipeline / diagnose_retrieval)
    passages = json.loads((ROOT / "corpus_passages.json").read_text(encoding="utf-8"))
    vectors = np.load(ROOT / "corpus_vectors.npy")
    retr = FAISSRetriever(n_clusters=1)
    retr.build_index([p["id"] for p in passages], [p["text"] for p in passages], vectors)

    embedder = CrossLingualEmbedder()
    # force XLM-R (uniform space with corpus_vectors) -- same as recompute_signals
    cres = embedder.embed(sel["claim_id"].tolist(), sel["claim_text"].tolist(), ["en"] * len(sel))

    # retrieve ONCE (identical for both modes); filter by MIN_RELEVANCE_THRESHOLD
    # exactly as the pipeline does, so premise granularity is the only variable.
    retrieved = []
    for i in range(len(sel)):
        r = retr.retrieve(sel.iloc[i]["claim_id"], cres.vectors[i], top_k=NLI_EVIDENCE_TOP_K)
        retrieved.append([p for p in r.passages if p.score >= MIN_RELEVANCE_THRESHOLD])

    del embedder  # free memory before NLI (NLI is the heavy stage on CPU)
    nli = NLIScorer()

    print("scoring switch OFF (whole passage)...", flush=True)
    off_df, off_neutral, off_units = score_mode(sel, retrieved, nli, sentence_level=False)
    # persist OFF immediately -- the ON pass is the one that OOMed before chunking
    write_off_partial(off_df, off_neutral, off_units, len(sel), len(passages), nli.device)
    print("scoring switch ON (sentence-level)...", flush=True)
    on_df, on_neutral, on_units = score_mode(sel, retrieved, nli, sentence_level=True)

    # ---- assemble the report ----
    def block(df, neutral, units):
        out = {"overall_auc": auc_for(df), "neutral": neutral, "units": units}
        for lang in ("en", "hi"):
            out[lang] = auc_for(df[df.language == lang])
        return out

    off = block(off_df, off_neutral, off_units)
    on = block(on_df, on_neutral, on_units)

    # paired frame: off_df and on_df are built from the same `sel` in the same
    # order, so row i is the same claim scored both ways -> the pairing is exact.
    paired = pd.DataFrame({
        "language": off_df["language"].to_numpy(),
        "y": off_df["y"].to_numpy(),
        "net_off": off_df["net"].to_numpy(),
        "net_on": on_df["net"].to_numpy(),
    })
    print(f"paired bootstrap: {N_BOOT} resamples per group...", flush=True)
    ci = {
        "EN": bootstrap_delta_ci(paired[paired.language == "en"]),
        "HI": bootstrap_delta_ci(paired[paired.language == "hi"]),
        "Overall": bootstrap_delta_ci(paired),
    }

    fmt = _fmt

    def delta(a, b):
        if a == a and b == b:
            d = b - a
            return f"{d:+.3f}"
        return "n/a"

    L = ["# C2-lite comparison — sentence-level NLI premises\n",
         f"Change: `member3_backend/pipeline.py` can split each retrieved passage "
         f"into sentences before NLI (cap {MAX_SENTENCES_PER_PASSAGE}/passage), behind "
         f"`SATYASCORE_SENTENCE_PREMISES` (**default off** — the live API keeps the "
         f"whole-passage behaviour until this comparison justifies flipping it). Switch "
         f"off = the current default; switch on = C2-lite.\n",
         f"- Claims: {len(sel)} "
         f"({(sel.gold_verdict=='Hallucinated').sum()} Hallucinated, "
         f"{(sel.gold_verdict=='Verified').sum()} Verified), experiment corpus "
         f"({len(passages)} passages), top-{NLI_EVIDENCE_TOP_K} retrieval, "
         f"MIN_RELEVANCE_THRESHOLD={MIN_RELEVANCE_THRESHOLD}.",
         f"- Device: **{nli.device}**. NLI premise units scored: {off_units} (off) "
         f"vs {on_units} (on).",
         f"- Baseline NLI AUC on record (RESULTS_SUMMARY.md): EN {BASELINE_AUC['en']}, "
         f"HI {BASELINE_AUC['hi']}.\n",
         "## NLI AUC — does the change separate Hallucinated from Verified better?",
         "(AUC 0.5 = chance; higher = better. This is the metric that decides the change.)\n",
         "| Group | switch OFF (passage) | switch ON (sentence) | Δ (on − off) |",
         "| --- | --- | --- | --- |",
         f"| EN | {fmt(off['en'])} | {fmt(on['en'])} | {delta(off['en'], on['en'])} |",
         f"| HI | {fmt(off['hi'])} | {fmt(on['hi'])} | {delta(off['hi'], on['hi'])} |",
         f"| Overall | {fmt(off['overall_auc'])} | {fmt(on['overall_auc'])} | "
         f"{delta(off['overall_auc'], on['overall_auc'])} |\n",
         f"## ΔAUC 95% CI — paired bootstrap ({N_BOOT} resamples of claims)",
         "(ΔAUC = AUC(on) − AUC(off). The decision rests on this CI, not the point "
         "estimate: the change is only worth turning on if the improvement is larger "
         "than the sampling noise. **Rule: flip the default only if the EN CI lower "
         "bound is above 0.**)\n",
         "| Group | ΔAUC (point) | 95% CI | valid resamples |",
         "| --- | --- | --- | --- |"]
    for name in ("EN", "HI", "Overall"):
        pt, lo, hi, nv, nb = ci[name]
        ci_str = f"[{lo:+.3f}, {hi:+.3f}]" if lo == lo else "n/a"
        L.append(f"| {name} | {fmt(pt)} | {ci_str} | {nv}/{nb} |")
    L += ["",
          "## Neutral rate — fraction of NLI units landing in neutral",
          "(A drop here is necessary but NOT sufficient — a lower neutral rate can also "
          "mean confident *wrong* answers. Read it alongside the AUC above.)\n",
          "| switch OFF (passage) | switch ON (sentence) |",
          "| --- | --- |",
          f"| {fmt(off_neutral)} | {fmt(on_neutral)} |\n"]

    # ---- plain-language verdict: decided by the EN bootstrap CI, not the point ----
    en_off, en_on = off["en"], on["en"]
    en_pt, en_lo, en_hi, en_nv, _ = ci["EN"]
    if en_lo != en_lo:  # nan
        verdict = ("**Could not decide** — the English ΔAUC CI is undefined (a class was "
                   "missing, usually only at a small `--limit`). Re-run the full comparison.")
    elif en_lo > 0:
        verdict = (f"**Sentence-level premises IMPROVED English discrimination — significantly.** "
                   f"NLI AUC {en_off:.3f} → {en_on:.3f} (ΔAUC {en_pt:+.3f}), 95% CI "
                   f"[{en_lo:+.3f}, {en_hi:+.3f}] entirely above 0. The improvement clears the "
                   f"sampling noise, so this justifies flipping the default: set "
                   f"`SATYASCORE_SENTENCE_PREMISES=true` (or change the default in pipeline.py) "
                   f"so the live API uses it.")
    elif en_hi < 0:
        verdict = (f"**Sentence-level premises HURT English discrimination — significantly.** "
                   f"NLI AUC {en_off:.3f} → {en_on:.3f} (ΔAUC {en_pt:+.3f}), 95% CI "
                   f"[{en_lo:+.3f}, {en_hi:+.3f}] entirely below 0. The default stays off; the "
                   f"code stays in the tree behind the switch as a recorded negative result.")
    else:
        verdict = (f"**No significant change on English.** NLI AUC {en_off:.3f} → {en_on:.3f} "
                   f"(ΔAUC {en_pt:+.3f}), but the 95% CI [{en_lo:+.3f}, {en_hi:+.3f}] straddles "
                   f"0 — the effect is within sampling noise. The rule (flip only if the EN CI "
                   f"lower bound is above 0) is not met, so **the default stays off**. The honest "
                   f"reading is that sentence-level premises are not a reliable win at this "
                   f"sample size; the neutral rate may move without NLI actually separating "
                   f"hallucinated from verified claims any better.")

    L += ["## Verdict", verdict, "",
          "_Hindi has only 9 Hallucinated claims; any HI movement here is noise, not an "
          "effect, and is reported for completeness only._",
          "_NLI is deterministic, so these AUC/neutral numbers are the same on CPU or GPU "
          "— a full run (no `--limit`) is authoritative; GPU is only faster. A small "
          "`--limit` run is a mechanism smoke test only and its numbers are not meaningful._",
          "_This file does not regenerate RESULTS_SUMMARY.md or re-run recompute_signals.py "
          "— diagnostic comparison only._\n"]

    out = ROOT / "results" / "c2_lite_comparison.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
