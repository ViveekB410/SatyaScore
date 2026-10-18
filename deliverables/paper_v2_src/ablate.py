"""Exploratory ablations on testL from cached answers (no new LLM calls), plus CIs and McNemar."""
import json, sys, random
from pathlib import Path
ROOT = Path(r"C:\Users\vivek\Downloads\satyascore"); sys.path[:0] = [str(ROOT), str(ROOT / "v2data")]
import score
from scipy.stats import binomtest
RUN = "v1_testL"; split = "testL"
run = [json.loads(l) for l in (ROOT / "v2data/runs" / f"{RUN}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
LLM = ROOT / "v2data/llm" / f"{RUN}__ollama__gpt-oss-20b.jsonl"
llm = score.load_llm(str(LLM)); reasons = score.load_llm(str(LLM), "reason")
grounded = score.load_llm(str(LLM)[:-6] + "__grounded10.jsonl")
def cfg(reasons_on, grounded_on, flag_needs):
    score.REASONS = reasons if reasons_on else None
    score.GROUNDED = grounded if grounded_on else None
    score.FLAG_NEEDS_LLM = flag_needs
    return score.predictions(run, split, "crosscheck", llm)
def o(df):
    t, f = df[df.gold == "Verified"], df[df.gold == "Hallucinated"]
    return dict(n=len(df), nt=len(t), nf=len(f), caught=(f.pred == "Hallucinated").sum(), fv=(f.pred == "Verified").sum(),
                tv=(t.pred == "Verified").sum(), fa=(t.pred == "Hallucinated").sum())
rows = {}
rows["v1"] = score.predictions(run, split, "live", None)
# LLM alone: the LLM's own verdict for every claim no source decided
orig = score.claim_verdict
def llm_alone(c, mode, l):
    if mode == "crosscheck" and not score.decided_by_source(c):
        return (llm.get(c["text"]) or "Uncertain")
    return orig(c, "live", None)
score.claim_verdict = llm_alone
rows["LLM alone"] = score.predictions(run, split, "crosscheck", llm)
score.claim_verdict = orig
rows["cross-check, no safeguards (v2 first)"] = cfg(False, False, False)
rows["+ no-evidence filter (v2)"] = cfg(True, False, False)
rows["+ second reading (v3)"] = cfg(True, True, False)
rows["+ LLM must say false, guard (v4a)"] = cfg(True, True, True)
for k, df in rows.items():
    r = o(df); print(f"{k:42s} caught {r['caught']}/{r['nf']} ({r['caught']/r['nf']:.0%})  falseVer {r['fv']}/{r['nf']} ({r['fv']/r['nf']:.0%})  trueVer {r['tv']}/{r['nt']} ({r['tv']/r['nt']:.0%})  FA {r['fa']}/{r['nt']} ({r['fa']/r['nt']:.0%})")
# paired comparisons v1 vs v4a
a, b = rows["v1"].reset_index(drop=True), rows["+ LLM must say false, guard (v4a)"].reset_index(drop=True)
assert (a.gold == b.gold).all() and len(a) == len(b)
def mcn(mask_a, mask_b):
    x = int((mask_a & ~mask_b).sum()); y = int((~mask_a & mask_b).sum())
    return x, y, binomtest(min(x, y), x + y, 0.5).pvalue if x + y else 1.0
F = a.gold == "Hallucinated"; T = a.gold == "Verified"
print("caught  (v1 only, v4a only, p):", mcn((a.pred == "Hallucinated") & F, (b.pred == "Hallucinated") & F))
print("falseVer(v1 only, v4a only, p):", mcn((a.pred == "Verified") & F, (b.pred == "Verified") & F))
print("FA      (v1 only, v4a only, p):", mcn((a.pred == "Hallucinated") & T, (b.pred == "Hallucinated") & T))
print("trueVer (v1 only, v4a only, p):", mcn((a.pred == "Verified") & T, (b.pred == "Verified") & T))
# bootstrap CI for caught ratio and differences
random.seed(0); idx = list(range(len(a))); ratios = []; dfa = []
for _ in range(2000):
    s = [random.choice(idx) for _ in idx]
    aa, bb = a.iloc[s], b.iloc[s]
    fa_, fb_ = aa[aa.gold == "Hallucinated"], bb[bb.gold == "Hallucinated"]
    ta_, tb_ = aa[aa.gold == "Verified"], bb[bb.gold == "Verified"]
    ca, cb = (fa_.pred == "Hallucinated").mean(), (fb_.pred == "Hallucinated").mean()
    ratios.append(cb / ca if ca else float("nan")); dfa.append((tb_.pred == "Hallucinated").mean() - (ta_.pred == "Hallucinated").mean())
ratios.sort(); dfa.sort()
print(f"caught ratio 95% CI {ratios[50]:.2f}-{ratios[1949]:.2f}; FA diff 95% CI {dfa[50]*100:+.1f} to {dfa[1949]*100:+.1f} points")
# claims sent to the LLM / second reading counts
claims = [c for r in run for c in r["claims"]]
nd = [c for c in claims if not score.decided_by_source(c)]
print("claims:", len(claims), "not decided by a source:", len(nd), "with LLM answer:", sum(c["text"] in llm for c in nd),
      "grounded answers:", sum(c["text"] in grounded for c in nd))
