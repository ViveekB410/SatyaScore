"""
aggregation_eval.py -- should the live pipeline switch from the `legacy` evidence
rule (the most decisive passage wins) to `gated` (support first; only an
on-topic passage may contradict)? See member3_backend/evidence_rules.py.

Everything runs through the live objects (member3_backend.api): the same
retrieval (FAISS IVF, top-3, relevance cut), NLI model and claim extractor
(bracketed asides blanked). Both rules score the SAME per-passage NLI numbers.

DECISION RULE (fixed 2026-09-28, committed before running). `gated` becomes the
default only if ALL hold:
  (a) FRESH true statements (lead sentences of Wikipedia articles, seed 11,
      excluding every sentence of the seed-7 sample the fix was designed on):
      fewer false alarms
      (true claims marked Hallucinated) than legacy;
  (b) TRAIN gold-Verified claims: false-alarm rate not higher than legacy;
  (c) TRAIN, EN+HI pooled: ROC-AUC (gated - legacy) paired-bootstrap 95% CI
      lower bound above -0.03 (it must not get worse at ranking real
      hallucinations below true claims).
Test, round 3 and the seed-7 design sample are reported only.

    .venv/Scripts/python.exe aggregation_eval.py        (GPU recommended)
Writes results/aggregation_eval.md.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from diagnose_true_claims import samples as true_samples
from member3_backend.evidence_rules import RULES
from member3_backend.pipeline import MIN_RELEVANCE_THRESHOLD
from nli_model_search import load_sets

ROOT = Path(__file__).resolve().parent
N_BOOT, SEED = 2000, 42
LOW, HIGH = 0.35, 0.65
NON_INFERIORITY = -0.03


def tier(s: np.ndarray) -> np.ndarray:
    return np.where(s < LOW, "Hallucinated", np.where(s > HIGH, "Verified", "Uncertain"))


def rows_for(api, claims: list[str], langs: list[str]) -> list[list[tuple[float, float, bool]]]:
    """Per claim: (P(entail), P(contradict), on_topic) for each retrieved passage, as live."""
    pipe = api._pipeline
    vecs = api._embedder.embed([str(i) for i in range(len(claims))], claims, langs).vectors
    out = []
    for claim, v in zip(claims, vecs):
        ps = [p for p in api._retriever.retrieve("q", v, top_k=pipe.nli_top_k).passages
              if p.score >= MIN_RELEVANCE_THRESHOLD]
        res = api._nli_scorer.score_batch(["q"] * len(ps), [p.text for p in ps], [claim] * len(ps)) if ps else []
        out.append([(r.entailment_prob, r.contradiction_prob, pipe.subjects.on_topic(claim, p.passage_id))
                    for p, r in zip(ps, res)])
    return out


def paired(y, a, b):
    rng = np.random.default_rng(SEED)
    d = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if len(set(y[i])) == 2:
            d.append(roc_auc_score(y[i], b[i]) - roc_auc_score(y[i], a[i]))
    lo, hi = np.percentile(d, [2.5, 97.5])
    return roc_auc_score(y, b) - roc_auc_score(y, a), lo, hi


def verdict_table(gold: np.ndarray, verdicts: dict[str, np.ndarray]) -> list[str]:
    L = ["| rule | correct | true claims marked Hallucinated (false alarms) | real hallucinations caught | Uncertain |",
         "|---|---|---|---|---|"]
    nv, nh = int((gold == "Verified").sum()), int((gold == "Hallucinated").sum())
    for name, v in verdicts.items():
        fa = int(((gold == "Verified") & (v == "Hallucinated")).sum())
        hit = int(((gold == "Hallucinated") & (v == "Hallucinated")).sum())
        L.append(f"| {name} | {int((v == gold).sum())}/{len(gold)} | {fa}/{nv} ({fa / max(nv, 1):.0%}) | "
                 f"{hit}/{nh} ({hit / max(nh, 1):.0%}) | {int((v == 'Uncertain').sum())} |")
    return L


def sample_texts(seed: int) -> list[dict]:
    import diagnose_true_claims as d
    d.SEED = seed
    return true_samples()


def true_statement_block(api, seed: int, label: str, exclude: set[str] = frozenset()) -> tuple[list[str], dict[str, int]]:
    items = [it for it in sample_texts(seed) if it["text"] not in exclude]
    claims, langs, groups = [], [], []
    for it in items:
        for c in api._pipeline.claim_extractor.extract(it["text"], it["lang"]):
            claims.append(c.text)
            langs.append(it["lang"])
            groups.append(f"{it['group']} {it['lang']}")
    rows = rows_for(api, claims, langs)
    L = [f"## {label}: {len(items)} true lead sentences (seed {seed}) → {len(claims)} claims\n",
         "| rule | " + " | ".join(sorted(set(groups))) + " | **all: false alarms** | all: Verified |",
         "|---|" + "---|" * (len(set(groups)) + 2)]
    fas = {}
    for name, rule in RULES.items():
        v = tier(np.array([rule(r) for r in rows]))
        per = [f"{int(((np.array(groups) == g) & (v == 'Hallucinated')).sum())}/{groups.count(g)}"
               for g in sorted(set(groups))]
        fas[name] = int((v == "Hallucinated").sum())
        L.append(f"| {name} | " + " | ".join(per) + f" | **{fas[name]}** ({fas[name] / len(v):.0%}) | "
                 f"{int((v == 'Verified').sum())} |")
    return L + ["", "(cells: false alarms / claims)", ""], fas


def main() -> None:
    import member3_backend.api as api
    api.load_starter_corpus()
    api._warmup_models()
    sets = load_sets()
    L = ["# Evidence aggregation: legacy vs gated\n",
         "Same retrieval, NLI numbers and extractor for both rules (the live objects). **Decision rule "
         "(fixed before running):** gated becomes the default only if (a) false alarms fall on FRESH true "
         "statements, (b) the train false-alarm rate does not rise, and (c) pooled train ΔAUC has a 95% CI "
         f"lower bound above {NON_INFERIORITY}.\n"]
    design_texts = {it["text"] for it in sample_texts(7)}
    fresh, fa_fresh = true_statement_block(api, 11, "(a) FRESH true statements (none from the design sample) — decides",
                                           exclude=design_texts)
    design, _ = true_statement_block(api, 7, "Design sample (the fix was designed on it) — reported only")
    L += fresh + design

    kg3 = pd.read_csv(ROOT / "round3" / "signals_round3_kgfix.csv").set_index("claim_id").kg_conf
    decision = {}
    for name in ("train", "test", "round3"):
        df = sets[name]
        rows = rows_for(api, df.claim_text.tolist(), df.language.tolist())
        gold = df.gold_verdict.to_numpy()
        y = (gold == "Verified").astype(int)
        s = {r: np.array([fn(x) for x in rows]) for r, fn in RULES.items()}
        v = {r: tier(sc) for r, sc in s.items()}
        if name == "round3":  # live system: the KG decides when it answers
            kg = kg3.reindex(df.claim_id).to_numpy(dtype=float)
            has = ~np.isnan(kg)
            v = {r: np.where(has, tier(np.nan_to_num(kg)), vv) for r, vv in v.items()}
        d, lo, hi = paired(y, s["legacy"], s["gated"])
        L += [f"## {name} (n = {len(df)}, Hallucinated {int((y == 0).sum())})"
              + (" — decides (b) and (c)" if name == "train" else " — reported only"), "",
              f"- ROC-AUC legacy {roc_auc_score(y, s['legacy']):.3f} → gated {roc_auc_score(y, s['gated']):.3f} "
              f"(Δ {d:+.3f} [{lo:+.3f}, {hi:+.3f}])" + (" (NLI part; the KG decides 12 claims)" if name == "round3" else ""),
              ""] + verdict_table(gold, v) + [""]
        if name == "train":
            fa = {r: float(((gold == "Verified") & (vv == "Hallucinated")).sum() / (gold == "Verified").sum())
                  for r, vv in v.items()}
            decision = {"a": fa_fresh["gated"] < fa_fresh["legacy"], "b": fa["gated"] <= fa["legacy"],
                        "c": lo > NON_INFERIORITY, "ci": (d, lo, hi)}
    ok = decision["a"] and decision["b"] and decision["c"]
    d, lo, hi = decision["ci"]
    L += ["## Decision",
          f"- (a) fewer false alarms on fresh true statements: **{'yes' if decision['a'] else 'no'}** "
          f"({fa_fresh['legacy']} → {fa_fresh['gated']})",
          f"- (b) train false-alarm rate not higher: **{'yes' if decision['b'] else 'no'}**",
          f"- (c) train ΔAUC {d:+.3f} [{lo:+.3f}, {hi:+.3f}], lower bound above {NON_INFERIORITY}: "
          f"**{'yes' if decision['c'] else 'no'}**",
          f"- **{'Adopt gated as the default.' if ok else 'Keep legacy as the default.'}**"]
    out = ROOT / "results" / "aggregation_eval.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
