# Result charts for the journal paper. Numbers: results/v2_results_final.md and the exploratory ablation (IEEE paper Table V).
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 10, "savefig.dpi": 300})
C1, C2, C3 = "#9aa7b8", "#1f4e8c", "#c9822b"

# Fig 3: overall, v1 vs v2 vs LLM alone
m = ["False items\ncaught", "False items\npassed as Verified", "True items\nVerified", "False alarms\n(true items flagged)"]
v1, v2, llm = [25, 22, 56, 11], [47, 6, 57, 13], [86, 11, 65, 28]
x = np.arange(4); w = 0.26
fig, ax = plt.subplots(figsize=(6.4, 3.0))
for off, vals, c, lab in ((-w, v1, C1, "Version 1 (no LLM)"), (0, v2, C2, "Version 2 (agreement-gated LLM)"), (w, llm, C3, "LLM alone")):
    b = ax.bar(x + off, vals, w, color=c, label=lab)
    ax.bar_label(b, labels=[f"{v}%" for v in vals], fontsize=8, padding=1.5)
ax.set_xticks(x, m); ax.set_ylabel("% of items"); ax.set_ylim(0, 100)
ax.legend(frameon=False, fontsize=8.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.13))
fig.tight_layout(); fig.savefig("fig3_overall.png"); plt.close(fig)

# Fig 4: per set, caught and false alarms
sets = ["FEVER (EN)", "Hindi Wikipedia (HI)", "Hindi Wiki., reworded (HI)", "Mu-SHROOM (EN)", "Mu-SHROOM (HI)", "TruthfulQA (EN)", "X-FACT rumours (HI)"]
c1, c2 = [37, 3, 28, 13, 7, 17, 67], [62, 39, 47, 20, 45, 43, 70]
f1, f2 = [13, 0, 3, 15, None, 18, None], [7, 0, 11, 15, None, 27, None]
y = np.arange(len(sets))[::-1]; h = 0.36
fig, (a, b) = plt.subplots(1, 2, figsize=(6.6, 3.3), sharey=True, gridspec_kw={"width_ratios": [1.35, 1]})
for ax, A, B, title in ((a, c1, c2, "False items caught (%)"), (b, f1, f2, "False alarms on true items (%)")):
    for vals, off, col, lab in ((A, h / 2, C1, "Version 1"), (B, -h / 2, C2, "Version 2")):
        vv = [v if v is not None else 0 for v in vals]
        bars = ax.barh(y + off, vv, h, color=col, label=lab)
        for yy, v in zip(y + off, vals):
            ax.text((v or 0) + 1, yy, "n/a" if v is None else str(v), va="center", fontsize=7.5)
    ax.set_title(title); ax.set_xlim(0, 85 if ax is a else 35)
a.set_yticks(y, sets); b.legend(frameon=False, fontsize=8, loc="lower right")
fig.tight_layout(); fig.savefig("fig4_perset.png"); plt.close(fig)

# Fig 5: ablation trade-off path
var = [("Version 1", 25, 11), ("LLM alone", 86, 28), ("+ agreement rule", 68, 22),
       ("+ no-evidence filter,\n+ second reading (same point;\n  true items Verified 47% → 57%)", 49, 16),
       ("+ LLM must say false,\n  check before flagging\n  = Version 2", 47, 13)]
fig, ax = plt.subplots(figsize=(5.6, 3.4))
ax.plot([v[1] for v in var[1:]], [v[2] for v in var[1:]], "-", color="#bbbbbb", zorder=1)
pos = {0: (2, -1.3), 1: (-15, 1.0), 2: (2, 0.8), 3: (3, 0.2), 4: (-4, -7.5)}
for i, (lab, cx, fa) in enumerate(var):
    col = C1 if i == 0 else (C3 if i == 1 else (C2 if i == len(var) - 1 else "#6c8ebf"))
    ax.scatter(cx, fa, s=55, color=col, zorder=3)
    ax.annotate(lab, (cx, fa), (cx + pos[i][0], fa + pos[i][1]), fontsize=8)
ax.set_xlabel("False items caught (%)  \u2192 better"); ax.set_ylabel("False alarms on true items (%)  \u2193 better")
ax.set_xlim(15, 95); ax.set_ylim(0, 32)
fig.tight_layout(); fig.savefig("fig5_ablation.png"); plt.close(fig)

# Fig 6: Mu-SHROOM span IoU
lab = ["V1, flagged\nclaims", "V2, flagged\nclaims", "V2, wrong\nwords only", "Mark-all\nbaseline"]
hi, en = [0.010, 0.097, 0.189, 0.318], [0.114, 0.172, 0.184, 0.307]
x = np.arange(4); w = 0.36
fig, ax = plt.subplots(figsize=(5.6, 2.8))
for off, vals, col, l in ((-w / 2, hi, C3, "Hindi (52 answers)"), (w / 2, en, C2, "English (72 answers)")):
    bb = ax.bar(x + off, vals, w, color=col, label=l); ax.bar_label(bb, labels=[f"{v:.3f}" for v in vals], fontsize=7.5, padding=1.5)
ax.set_xticks(x, lab); ax.set_ylabel("Mean span IoU"); ax.set_ylim(0, 0.38); ax.legend(frameon=False, fontsize=8.5)
fig.tight_layout(); fig.savefig("fig6_iou.png"); plt.close(fig)
print("ok")
