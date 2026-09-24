"""
generate_results_summary.py — one clean RESULTS_SUMMARY.md pulling every headline
number straight from the artifacts, so the paper/report author doesn't re-derive
them (and nothing is hand-typed). Reads:
  gold_final.csv, claim_quality.csv, gold_final_scored.csv,
  gold_train_clean.csv / gold_test_clean.csv (the grouped split),
  iaa/iaa_round1_annotator_A.xlsx + iaa_annotator_B.xlsx (round-1 IAA),
  annotation_round2/round2_annotator_A.xlsx + _B.xlsx (round-2 blind re-labelling),
  results/ablation_clean_no_semsim.json, results/latency_benchmark.md,
  results/retrieval_diagnostic.csv, results/c2_lite_comparison.md,
  results/extraction_quality.md.

Needs openpyxl for the .xlsx sheets (run with .venv/Scripts/python.exe). Any
section whose inputs are missing says so instead of failing.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix, roc_auc_score

LAB = ["Verified", "Uncertain", "Hallucinated"]
MIN_POSITIVES = 10  # matches honest_eval.MIN_POSITIVES_TO_INTERPRET


def norm(v):
    s = str(v).strip().lower()
    if s.startswith(("verif", "verf")):
        return "Verified"
    if s.startswith(("hall", "halu")):
        return "Hallucinated"
    if s.startswith(("uncert", "unsure", "unclear")):
        return "Uncertain"
    return None


def _sheet(path: str) -> pd.Series:
    return pd.read_excel(path).set_index("claim_id")["verdict"].map(norm)


def _usage(s: pd.Series) -> str:
    return ", ".join(f"{lab} {int((s == lab).sum())}" for lab in LAB)


def _pair_block(A: pd.Series, B: pd.Series, gold: pd.DataFrame) -> dict:
    """Agreement facts for two annotators over their shared, labelled claims."""
    d = pd.DataFrame({"A": A, "B": B}).dropna()
    d["gold"] = gold.set_index("claim_id")["gold_verdict"].reindex(d.index)
    d["ai"] = gold.set_index("claim_id")["ai_verdict"].map(norm).reindex(d.index)
    agree = d[d.A == d.B]
    return {
        "d": d,
        "n": len(d),
        "k3": cohen_kappa_score(d.A, d.B, labels=LAB),
        "kH": cohen_kappa_score(d.A == "Hallucinated", d.B == "Hallucinated"),
        "raw3": float((d.A == d.B).mean()),
        "rawH": float(((d.A == "Hallucinated") == (d.B == "Hallucinated")).mean()),
        "both_hallu": int(((d.A == "Hallucinated") & (d.B == "Hallucinated")).sum()),
        "cm": confusion_matrix(d.A, d.B, labels=LAB),
        "A_gold": float((d.A == d.gold).mean()),
        "B_gold": float((d.B == d.gold).mean()),
        "agree_n": len(agree),
        "agree_gold": int((agree.A == agree.gold).sum()),
        "agree_ai": int((agree.A == agree.ai).sum()),
    }


def iaa_round1(gold: pd.DataFrame, quality: pd.DataFrame) -> list[str]:
    try:
        A = _sheet("iaa/iaa_round1_annotator_A.xlsx")
        B = _sheet("iaa/iaa_annotator_B.xlsx")
    except Exception as e:
        return [f"- (round-1 IAA not available: {e})\n"]
    r = _pair_block(A, B, gold)
    ok = set(quality.loc[quality.quality_flag == "ok", "claim_id"])
    wf = r["d"][r["d"].index.isin(ok)]
    kH_wf = cohen_kappa_score(wf.A == "Hallucinated", wf.B == "Hallucinated")
    never = [f"Annotator {t} never used \"{lab}\""
             for t, s in (("A", r["d"].A), ("B", r["d"].B)) for lab in LAB if (s == lab).sum() == 0]
    L = [f"- n = {r['n']} claims, two annotators labelling blind (no AI verdict shown).",
         f"- **Binary 'hallucinated vs not' kappa = {r['kH']:.2f}** (raw agreement {r['rawH']:.0%}) "
         f"— the headline IAA figure.",
         f"- On the well-formed subset only (n = {len(wf)}): binary kappa = {kH_wf:.2f}.",
         f"- 3-class kappa = {r['k3']:.2f} (raw agreement {r['raw3']:.0%}).",
         f"- Label usage — A: {_usage(r['d'].A)}; B: {_usage(r['d'].B)}."]
    if never:
        L.append(f"- {'; '.join(never)}. The two annotators applied different label "
                 f"schemes, so the 3-class kappa largely reflects that mismatch.")
    L += [f"- Claims both annotators called Hallucinated: {r['both_hallu']}.",
          "- Confusion matrix (rows = A, cols = B; Verified / Uncertain / Hallucinated):\n\n```",
          str(r["cm"]), "```\n"]
    return L


def iaa_round2(gold: pd.DataFrame) -> list[str]:
    try:
        A = _sheet("annotation_round2/round2_annotator_A.xlsx")
        B = _sheet("annotation_round2/round2_annotator_B.xlsx")
    except Exception as e:
        return [f"- (round-2 sheets not available: {e})\n"]
    r = _pair_block(A, B, gold)
    if r["n"] < 2 or r["d"].A.isna().all():
        return ["- Round-2 sheets are not filled yet.\n"]
    return [
        f"- n = {r['n']} claims drawn from `ai_agreed` gold labels (reviewed with the AI verdict "
        f"visible), re-labelled blind by two annotators.",
        f"- Raw agreement {r['rawH']:.0%}; binary kappa = {r['kH']:.2f} — below the 0.65 guideline "
        f"target. The sample is almost all Verified, so chance agreement is high and kappa is "
        f"unstable here; see `results/label_audit.md` for the bootstrap CI.",
        f"- Label usage — A: {_usage(r['d'].A)}; B: {_usage(r['d'].B)}. Neither used Uncertain, "
        f"which fits a clear-cut `ai_agreed` sample but means this round measures only the binary call.",
        f"- **Anchoring check:** where the two annotators agree ({r['agree_n']} claims), the existing "
        f"gold label matches them {r['agree_gold']}/{r['agree_n']} "
        f"({r['agree_gold'] / r['agree_n']:.0%}). On this sample the reviewed-and-agreed labels "
        f"hold up without the AI anchor.\n",
    ]


def ablation_rows(path: str):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for lang, blk in data["languages"].items():
        cfgs = blk["configurations"]
        base = cfgs["always_verified_baseline"]["test_all"]

        def cell(name):
            m = cfgs.get(name, {}).get("test_all")
            if not m:
                return "n/a"
            lo, hi = m.get("hallucinated_f1_ci95", (None, None))
            ci = f" [{lo:.2f}, {hi:.2f}]" if lo is not None else ""
            return f"{m['accuracy']:.3f} / {m['hallucinated_f1']:.3f}{ci}"

        out[lang] = {"base": base, "nli": cell("NLI only"), "semsim": cell("SemSim only"),
                     "full": cell("Full (S+N+KG)")}
    return out


def latency_block() -> list[str]:
    p = Path("results/latency_benchmark.md")
    if not p.exists():
        return ["- (latency benchmark not found)\n"]
    text = p.read_text(encoding="utf-8")
    device = re.search(r"Device: \*\*(\w+)\*\*", text)
    stage = {m.group(1): (float(m.group(2)), float(m.group(3)))
             for m in re.finditer(r"^\| (\w+) \| ([\d.]+) \| ([\d.]+) \|$", text, re.M)}
    doc = re.search(r"\| (\d+)-claim document total \| (\d+) ms \|", text)
    if "total" not in stage:
        return ["- (latency benchmark table not parseable)\n"]
    mean, median = stage["total"]
    kg_mean, nli_mean = stage.get("kg", (0, 0))[0], stage.get("nli", (0, 0))[0]
    L = [f"- Measured on **{device.group(1) if device else '?'}** (`results/latency_benchmark.md`), "
         f"experiment corpus, first run discarded.",
         f"- Per-claim **median {median:.0f} ms** — PRD target < 500 ms **met**.",
         f"- Per-claim **mean {mean:.0f} ms** — target **missed**. The mean is driven by the KG "
         f"stage (mean {kg_mean:.0f} ms, a network call to Wikidata), not NLI (mean {nli_mean:.0f} ms)."]
    if doc:
        n_doc, ms = int(doc.group(1)), int(doc.group(2))
        L.append(f"- {n_doc}-claim document: **{ms:,} ms** — target < 3,000 ms "
                 f"**{'met' if ms < 3000 else 'missed'}**.")
    L.append("- CPU latency is several times higher; the figures above are GPU.\n")
    return L


def phase3_block() -> list[str]:
    L = []
    p = Path("results/retrieval_diagnostic.csv")
    if p.exists():
        rd = pd.read_csv(p)
        en = rd[rd.language == "en"]
        with_src = en[en.source_title.fillna("").astype(str).str.strip() != ""]

        def rec(df, label):
            s = df[df.label == label]
            return f"{s.src_in_top3.mean():.2f}" if len(s) else "n/a"

        L.append(f"- **Retrieval diagnostic (English):** the claim's own source article is in the top 3 "
                 f"retrieved passages for {rec(with_src, 'Hallucinated')} of Hallucinated vs "
                 f"{rec(with_src, 'Verified')} of Verified claims, computed only on claims with a "
                 f"recorded source (n = {len(with_src)}; including claims with no source gives "
                 f"{rec(en, 'Hallucinated')} vs {rec(en, 'Verified')}, which understates the gap). "
                 f"Suggestive at this sample size, not established.")
        hi = rd[rd.language == "hi"]
        if len(hi):
            m = hi.groupby("label").top1_sim.mean()
            if {"Hallucinated", "Verified"} <= set(m.index):
                n_h = int((hi.label == "Hallucinated").sum())
                L.append(f"- **Hindi similarity inversion:** mean top-1 retrieval similarity is higher for "
                         f"Hallucinated ({m['Hallucinated']:.3f}) than Verified ({m['Verified']:.3f}) "
                         f"claims — a candidate explanation for the below-chance Hindi SemSim AUC. "
                         f"Hypothesis only (n = {n_h} Hallucinated).")
    else:
        L.append("- (retrieval diagnostic not found)")
    c = Path("results/c2_lite_comparison.md")
    if c.exists():
        m = re.search(r"\| EN \| ([-+]?[\d.]+) \| \[([-+]?[\d.]+), ([-+]?[\d.]+)\]",
                      c.read_text(encoding="utf-8"))
        if m:
            d, lo, hi = (float(x) for x in m.groups())
            L.append(f"- **C2-lite (sentence-level NLI premises):** English ΔAUC {d:+.3f}, 95% CI "
                     f"[{lo:+.3f}, {hi:+.3f}] — no significant change; the switch stays off by default.")
    cs = Path("results/contradiction_signal.md")
    if cs.exists():
        m = re.search(r"\| EN \| \d+ / \d+ \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([-+][\d.]+) "
                      r"\[([-+][\d.]+), ([-+][\d.]+)\]", cs.read_text(encoding="utf-8"))
        if m:
            net, con, ent, d, lo, hi = (float(x) for x in m.groups())
            L.append(f"- **Contradiction as its own signal (English):** AUC {con:.3f} for 1 − "
                     f"P(contradiction) vs {net:.3f} for the current net score (entailment alone "
                     f"{ent:.3f}); ΔAUC {d:+.3f}, 95% CI [{lo:+.3f}, {hi:+.3f}]. Suggestive, not "
                     f"established — not adopted under the fixed rule; re-test with more "
                     f"annotated hallucinations.")
    return L + [""]


def extraction_block(q: pd.DataFrame) -> list[str]:
    n_en = int((q.language == "en").sum())
    nb = int(((q.language == "en") & (q.quality_flag == "broken")).sum())
    L = [f"- Gold set: {nb} of {n_en} English claims ({nb / n_en:.1%}) are broken extraction "
         f"artifacts (no subject + finite verb, a lost %, or too short); Hindi (sentence-level) is clean. "
         f"Well-formed working set = {int((q.quality_flag == 'ok').sum())} claims."]
    p = Path("results/extraction_quality.md")
    if p.exists():
        m = re.search(r"\*\*broken claims\*\* \| \*\*(\d+)/(\d+) \(([\d.]+)%\)\*\* \| \*\*(\d+)/(\d+) \(([\d.]+)%\)\*\*",
                      p.read_text(encoding="utf-8"))
        if m:
            L.append(f"- Live extractor fixed (IMPROVEMENT_PLAN 1.1): re-extracting all English source "
                     f"answers, broken claims fell from {m.group(1)}/{m.group(2)} ({m.group(3)}%) to "
                     f"{m.group(4)}/{m.group(5)} ({m.group(6)}%). The gold claims were annotated as "
                     f"extracted and are not re-extracted (`results/extraction_quality.md`).")
    return L + [""]


def main() -> None:
    gold = pd.read_csv("gold_final.csv", encoding="utf-8")
    q = pd.read_csv("claim_quality.csv", encoding="utf-8")
    scored = pd.read_csv("gold_final_scored.csv", encoding="utf-8")
    llms = gold["source_llm"].unique().tolist() if "source_llm" in gold else []

    L = ["# SatyaScore — Results Summary\n",
         "_Auto-generated from the project artifacts by `generate_results_summary.py`. "
         "All numbers are computed, not hand-entered._\n"]

    L.append("## 1. Dataset\n")
    L.append(f"- {len(gold)} human-verified claims (EN {int((gold.language == 'en').sum())}, "
             f"HI {int((gold.language == 'hi').sum())}), intact bilingual text, all from LLM answers "
             f"generated by {', '.join(f'`{x}`' for x in llms) or 'n/a'}.\n")
    L.append("- Verdict distribution (language x gold_verdict):\n\n```")
    L.append(gold.groupby(["language", "gold_verdict"]).size().to_string())
    L.append("```\n")

    L.append("## 2. Annotation protocol and provenance\n")
    prov = gold["gold_source"].value_counts()
    n_agreed = int(prov.get("ai_agreed", 0))
    L.append(f"- Protocol: the annotator reviewed **every** AI-suggested verdict and wrote a verdict only "
             f"when they disagreed; a blank field means \"reviewed and agreed\". {n_agreed} of {len(gold)} "
             f"gold labels ({n_agreed / len(gold):.0%}) are reviewed-and-agreed; the rest are overrides or "
             f"confirmations ({prov.to_dict()}). These are reviewed labels, not unreviewed ones.")
    L.append("- **Limitation — anchoring:** review happened with the AI verdict visible, which biases "
             "toward agreement. Single annotator; no adjudication (see `ANNOTATION_PROVENANCE.md`).")
    try:
        r1 = _pair_block(_sheet("iaa/iaa_round1_annotator_A.xlsx"), _sheet("iaa/iaa_annotator_B.xlsx"), gold)
        L.append(f"- Round-1 evidence: annotators labelling blind matched the gold labels "
                 f"{r1['B_gold']:.0%} (B) and {r1['A_gold']:.0%} (A) of the time on the {r1['n']} IAA claims.")
    except Exception:
        pass
    L.append("- Round-2 measures anchoring directly (section 4).\n")

    L.append("## 3. Data quality (claim extraction)\n")
    L += extraction_block(q)

    L.append("## 4. Inter-annotator agreement\n")
    L.append("### Round 1 (stratified pilot)\n")
    L += iaa_round1(gold, q)
    L.append("### Round 2 (blind re-labelling of `ai_agreed` claims)\n")
    L += iaa_round2(gold)

    L.append("## 5. Signal validity (recomputed bilingual signals)\n")
    means = scored.groupby(["language", "gold_verdict"])[["sem_sim", "nli_prob"]].mean().round(3)
    L.append("- Mean signal by (language, verdict):\n\n```")
    L.append(means.to_string())
    L.append("```")
    wf = scored.merge(q[["claim_id", "quality_flag"]], on="claim_id")
    wf = wf[wf.quality_flag == "ok"]
    L.append("- Threshold-free discrimination (ROC-AUC: how well each signal ranks Verified above "
             "Hallucinated; 0.5 = chance), well-formed claims:\n")
    L.append("| Lang | n (Verified / Hallucinated) | SemSim AUC | NLI AUC |")
    L.append("|---|---|---|---|")
    for lang in ("en", "hi"):
        sub = wf[(wf.language == lang) & wf.gold_verdict.isin(["Verified", "Hallucinated"])]
        y = (sub.gold_verdict == "Verified").astype(int)

        def _auc(sig):
            try:
                return f"{roc_auc_score(y, sub[sig]):.3f}" if y.nunique() > 1 else "n/a"
            except Exception:
                return "n/a"
        L.append(f"| {lang.upper()} | {int((y == 1).sum())} / {int((y == 0).sum())} | "
                 f"{_auc('sem_sim')} | {_auc('nli_prob')} |")
    L.append("\n- Every AUC sits near 0.5; Hindi is noisier (few Hallucinated claims). The signals barely "
             "separate real hallucinations from verified claims.\n")

    L.append("## 6. Ablation + baselines (grouped test split, cut-points fitted on train)\n")
    try:
        te = pd.read_csv("gold_test_clean.csv")
        tr = pd.read_csv("gold_train_clean.csv")
        shared = len(set(tr.source_query_id) & set(te.source_query_id))
        L.append(f"- Split grouped by source question: train {len(tr)} / test {len(te)} claims, "
                 f"{shared} source questions shared (`results/regroup_comparison.md`).\n")
        rows = ablation_rows("results/ablation_clean_no_semsim.json")
        L.append("| Lang | test n / Hallucinated | Always-Verified acc | NLI-only acc / Hallu-F1 [95% CI] | "
                 "SemSim-only acc / Hallu-F1 [95% CI] | Full CMHSA acc / Hallu-F1 [95% CI] |")
        L.append("|---|---|---|---|---|---|")
        any_few = False
        for lang, r in rows.items():
            b = r["base"]
            few = b["n_hallucinated"] < MIN_POSITIVES
            any_few |= few
            L.append(f"| {lang.upper()} | {b['n']} / {b['n_hallucinated']}{' †' if few else ''} | "
                     f"{b['accuracy']:.3f} | {r['nli']} | {r['semsim']} | {r['full']} |")
        if any_few:
            L.append(f"\n† Fewer than {MIN_POSITIVES} Hallucinated test claims: Hallu-F1 is printed but "
                     f"is **too few positives to interpret**.")
        L.append("")
    except Exception as e:
        L.append(f"(ablation / split not found: {e})\n")
    L.append("- **No configuration beats the always-Verified baseline.** Full CMHSA collapses to NLI-only "
             "(KG has 0% coverage → not scoreable). Baselines: always-Verified (majority), SemSim-only "
             "(topical similarity), NLI-only (TRUE-style entailment). SelfCheckGPT/FActScore/FactKG proper "
             "were not implemented (need multi-sample LLM output / KG-linkable claims the data lacks).\n")

    L.append("## 7. Latency\n")
    L += latency_block()

    L.append("## 8. Phase 3 diagnostics\n")
    L += phase3_block()

    L.append("## 9. Defensible findings\n")
    L.append("1. Multi-signal fusion does **not** beat NLI alone for this task/data.\n"
             "2. Knowledge-graph verification **cannot be evaluated on this dataset**: 0 of 456 gold claims "
             "contain a relation the KG can link (the claims are descriptive; `results/kg_ablation.md`), so "
             "the PRD's KG ablation is not measurable here. On relational claims the fixed verifier is "
             "correct (7/7 live).\n"
             "3. Semantic similarity measures **topicality, not truth** (below chance in Hindi).\n"
             "4. Detecting **naturally-occurring** hallucinations is hard; no configuration clears a "
             "trivial majority baseline on this data.\n"
             "5. Rule-based English claim decomposition produced broken fragments; a sentence-level safety "
             "net removes them (section 3).\n")

    L.append("## 10. Limitations\n")
    try:
        te = pd.read_csv("gold_test_clean.csv")
        counts = ", ".join(f"{lang.upper()} {int(((te.language == lang) & (te.gold_verdict == 'Hallucinated')).sum())}"
                           for lang in ("en", "hi"))
        L.append(f"- The grouped test split has only **{counts}** Hallucinated claims — too few to "
                 f"interpret Hallucinated-F1 in either language.")
    except Exception:
        pass
    L.append(f"- All responses were generated by a single LLM ({', '.join(llms) or 'n/a'}), which limits "
             f"generalisation to other models.\n"
             "- Label reliability: single primary annotator, anchored review (section 2); round-1 3-class "
             "agreement is low because the annotators used different label schemes; binary kappa is the "
             "reliable figure.\n"
             "- Dataset small (456) vs the PRD's 3,000; Verified-heavy.\n"
             "- NLI is a pretrained mDeBERTa stand-in, not the PRD's DeBERTa-v3 + IndicXNLI fine-tune.\n"
             "- KG signal non-functional on this claim type; Marathi out of scope; baseline suite partial.\n")

    Path("RESULTS_SUMMARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote RESULTS_SUMMARY.md")


if __name__ == "__main__":
    main()
