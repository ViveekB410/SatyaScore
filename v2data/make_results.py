"""
v2data/make_results.py -- results/v2_results.md: v1 vs v2 on the held-out test sample, with the dev tuning
figures and every disclosure the protocol requires. Re-run any time; it reports how complete the LLM step is.

    .venv/Scripts/python.exe v2data/make_results.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "v2data"))
import score  # noqa: E402

# --round 2: the fix round on the new test sample (protocol: "Fix round"); default: the first held-out run
ROUND = sys.argv[sys.argv.index("--round") + 1] if "--round" in sys.argv else "1"
ROUND2 = ROUND in ("2", "3", "L")  # no-evidence filter from round 2; second reading from round 3
ROUND3 = ROUND in ("3", "L")
FINAL = ROUND == "L"  # the large final test, v4a (protocol: "Large final test")
RUN = {"1": "v1_testS", "2": "v1_testS2", "3": "v1_testS3", "L": "v1_testL"}[ROUND]
NEW = "v4a" if FINAL else "v3" if ROUND3 else "v2"
score.FLAG_NEEDS_LLM = FINAL
# v2's LLM answers: the same gpt-oss-20b weights run locally (protocol: provider fallback); Groq for agreement
LLM = ROOT / "v2data" / "llm" / f"{RUN}__ollama__gpt-oss-20b.jsonl"  # the bake-off ("open") prompt in both rounds
GROQ = ROOT / "v2data" / "llm" / f"{RUN}__groq__openai_gpt-oss-20b.jsonl"
OUT = ROOT / "results" / {"1": "v2_results.md", "2": "v2_results_round2.md", "3": "v2_results_round3.md",
                          "L": "v2_results_final.md"}[ROUND]


def table(df: pd.DataFrame) -> list[str]:
    cols = ["set", "lang", "n_true", "n_false", "caught", "false_verified", "true_verified", "false_alarm", "uncertain"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df[cols].itertuples(index=False):
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    return lines


def overall(df: pd.DataFrame) -> dict:
    t, f = df[df.gold == "Verified"], df[df.gold == "Hallucinated"]
    return {"items": len(df), "caught": (f.pred == "Hallucinated").mean(), "false_verified": (f.pred == "Verified").mean(),
            "true_verified": (t.pred == "Verified").mean(), "false_alarm": (t.pred == "Hallucinated").mean()}


def main() -> None:
    run = [json.loads(l) for l in (ROOT / "v2data" / "runs" / f"{RUN}.jsonl").read_text(encoding="utf-8").splitlines()]
    llm = score.load_llm(str(LLM)) if LLM.exists() else {}
    spans = score.load_llm(str(LLM), "wrong_span") if LLM.exists() else {}
    score.REASONS = score.load_llm(str(LLM), "reason") if LLM.exists() and ROUND2 else None  # no-evidence filter
    second = Path(str(LLM)[:-6] + "__grounded10.jsonl")
    score.GROUNDED = score.load_llm(str(second)) if ROUND3 and second.exists() else None
    from llm_answer import scored_claims
    need = scored_claims(RUN)
    have = sum(c["text"] in llm for c in need)
    complete = have == len(need)
    split = RUN.split("_", 1)[1]
    v1 = score.predictions(run, split, "live", None)
    v2 = score.predictions(run, split, "crosscheck", llm)
    L = ["# Satya-Score Version 2: held-out results", "",
         f"Test sample: {len(v1)} items from the locked test splits (results/v2_data_PROTOCOL.md, \"Held-out test sample\"), "
         "run once. v1 = the current system. v2 = v1 plus the LLM cross-check (gpt-oss-20b, the same open weights as on Groq, run locally with Ollama; symmetric rule); "
         "structured sources and fact-checks still decide first.", ""]
    if GROQ.exists() and llm:
        g = score.load_llm(str(GROQ))
        both = [c for c in llm if c in g and llm[c] and g[c]]
        if both:
            agree = sum(llm[c] == g[c] for c in both) / len(both)
            L += [f"Provider check: on the {len(both)} claims both answered, the local run (Ollama) and Groq gave the "
                  f"same verdict {agree:.0%} of the time.", ""]
    if not complete:
        L += [f"**INCOMPLETE: the LLM has answered {have} of {len(need)} claims (free-quota limit).** Claims without an "
              "answer keep their v1 verdict, so v2 below is a mix. Re-run when the LLM step finishes.", ""]
    if ROUND2:
        L[0] = "# Satya-Score Version 2, fix round: held-out results (new test sample)"
        L += ["Fix round: an LLM 'Hallucinated' whose reason only says evidence is missing counts as Uncertain "
              "(no-evidence filter), chosen on dev data. New test sample `testS2`, no item shared with the first one. Cells already "
              "used up are missing: Mu-SHROOM Hindi true claims and old-gold false claims.", ""]
        o1, o2 = overall(v1), overall(v2)
        checks = [("caught >= 2x v1", o2["caught"] >= 2 * o1["caught"], f"{o2['caught']:.0%} vs {o1['caught']:.0%}"),
                  ("hallucinations marked Verified <= half of v1", o2["false_verified"] <= o1["false_verified"] / 2,
                   f"{o2['false_verified']:.0%} vs {o1['false_verified']:.0%}"),
                  ("false alarms <= v1 + 3 points", o2["false_alarm"] <= o1["false_alarm"] + 0.03,
                   f"{o2['false_alarm']:.0%} vs {o1['false_alarm']:.0%}")]
        if ROUND3:
            L[0] = "# Satya-Score Version 2, last round: held-out results (third test sample)"
            L[-2] = ("Last round: v3 = the fix round plus the second reading (for claims left Uncertain although one side "
                     "leans true, the LLM reads all 10 retrieved passages, passages only; Verified if they state the claim). "
                     "Chosen on the burned testS and testS2. Third test sample `testS3`, no item shared with the earlier two; "
                     "hiwiki_swap is used up.")
            if FINAL:
                L[0] = "# Satya-Score Version 2: final held-out results (large test sample)"
                L[-2] = ("Final: v4a = v3 plus two safeguards against false alarms: a passage 'contradiction' alone never "
                         "flags a claim (the LLM must say false), and a claim about to be flagged is first read against "
                         "all 10 retrieved sources (if they state it, it is Uncertain). Chosen on the three burned samples "
                         "(~510 items). Large test sample `testL`: 620 items, none used before; hiwiki_swap and the old "
                         "gold set are used up, Mu-SHROOM Hindi has false items only.")
            checks.append(("true claims Verified >= v1 - 5 points", o2["true_verified"] >= o1["true_verified"] - 0.05,
                           f"{o2['true_verified']:.0%} vs {o1['true_verified']:.0%}"))
        ok = all(c[1] for c in checks)
        L += ["## Decision (rule fixed before this run)", ""] +              [f"- {name}: {'PASS' if good else 'FAIL'} ({val})" for name, good, val in checks] +              ["", f"**{NEW} {'IS' if ok else 'is NOT'} adopted under the pre-set rule.**", ""]
    L += ["## Overall (all sets pooled)", "", "| system | items | caught | hallucinations marked Verified | true claims Verified | false alarms |",
          "|---|---|---|---|---|---|"]
    for name, df in (("v1", v1), (NEW, v2)):
        o = overall(df)
        L.append(f"| {name} | {o['items']} | {o['caught']:.0%} | {o['false_verified']:.0%} | {o['true_verified']:.0%} | {o['false_alarm']:.0%} |")
    for name, df, mode, l in (("v1", v1, "live", None), (NEW, v2, "crosscheck", llm)):
        L += ["", f"## {name} by set", ""] + table(score.summary(df))
        L += [""] + [f"- {x}" for x in score.mushroom_iou(run, split, mode, l, spans if l else None)]
    xf1 = score.summary(score.predictions(run, split, "no_factcheck", None))
    xf1 = xf1[xf1.set == "xfact_hi"]
    if len(xf1):
        L += ["", f"X-FACT (Hindi rumours) without the fact-check source, v1: caught {xf1.iloc[0]['caught']} "
              "(fact-check sites cover exactly these rumours, so both figures are shown)."]
    L += ["", "## How to read this, and what to disclose", "",
          "- caught = share of false items marked Hallucinated; false alarms = share of true items marked Hallucinated; "
          "items neither Verified nor Hallucinated are Uncertain.",
          ("- Up to 60 true and 60 false items per set, so each percentage moves by about 2-3 points per item."
           if FINAL else
           "- Small sample: about 12 true and 12 false items per set, so each percentage moves by about 8 points per item."),
          ("- History, all disclosed: the first v2 failed on the first test sample (false alarms 17% vs v1 9%, "
           "results/v2_results.md). Its cause (the LLM calling claims false only because the passages did not mention them) "
           "was found on dev data and on that burned sample. The decision rule was changed to be relative to v1 (the first "
           "rule, an absolute 5%, was set when v1's own rate looked like 3-6%; on these sets v1 has 9-12%). The rule and the fix "
           "were both fixed before this sample was run."
           if ROUND2 else
           "- v2 did NOT meet the pre-set dev rule on false alarms (7% on the dev sample, limit 5%); it is reported anyway."),
          "- Cost of v2: fewer true claims are Verified (they become Uncertain), because Verified needs the passages and "
          "the LLM to agree.",
          "- Mu-SHROOM Hindi has very few true claims; Hindi false alarms are better read from hiwiki and hiwiki_para.",
          "- hiwiki = sentences copied from Hindi Wikipedia (easier, the system can find them); hiwiki_para = the same "
          "sentences reworded by an LLM (Qwen) and checked to keep meaning and numbers.",
          "- Constructed false items (hiwiki, hiwiki_para, hiwiki_swap) change one number or one place name.",
          "- Wikidata relations added in v2 decided ~1% of dev claims and are switched off; 'country' was dropped by the rule.",
          "- The LLM is a second opinion: it can make a claim Verified only together with a supporting passage."]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:16]))
    print(f"... written to {OUT} (LLM answered {have}/{len(need)})")


if __name__ == "__main__":
    main()
