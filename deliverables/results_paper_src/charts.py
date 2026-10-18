"""Charts for the results paper (numbers from results/v2_results_final.md and the exploratory ablation)."""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1]
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 11})
GREY, BLUE, RED = "#9E9E9E", "#1F5FBF", "#C0392B"

# 1. caught per set, Version 1 -> Version 2 (dumbbell)
rows = [("Mu-SHROOM Hindi", 7, 45), ("Hindi Wikipedia", 3, 39), ("TruthfulQA English", 17, 43),
        ("FEVER English", 37, 62), ("Hindi Wikipedia, reworded", 28, 47), ("Mu-SHROOM English", 13, 20),
        ("X-FACT Hindi", 67, 70)]
fig, ax = plt.subplots(figsize=(6.6, 3.3))
for i, (name, a, b) in enumerate(rows):
    y = len(rows) - 1 - i
    ax.plot([a, b], [y, y], color=BLUE, alpha=0.35, lw=3, zorder=1)
    ax.scatter([a], [y], color=GREY, s=36, zorder=2)
    ax.scatter([b], [y], color=BLUE, s=42, zorder=3)
    ax.text(a - 1.5, y, f"{a}%", ha="right", va="center", fontsize=9.5, color="#555555")
    ax.text(b + 1.5, y, f"{b}%", ha="left", va="center", fontsize=9.5, fontweight="bold")
ax.set_yticks(range(len(rows)))
ax.set_yticklabels([r[0] for r in rows][::-1])
ax.set_xlim(-8, 100); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
ax.grid(axis="x", color="#E5E5E5"); ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.scatter([], [], color=GREY, label="Version 1"); ax.scatter([], [], color=BLUE, label="Version 2 (cross-check)")
ax.legend(loc="upper right", frameon=False, fontsize=9.5)
ax.set_title("False items caught, per test set (620 held-out items)", fontsize=11.5, loc="left")
fig.tight_layout(); fig.savefig(f"{OUT}/chart_caught.png", dpi=220); plt.close(fig)

# 2. ablation: caught vs false alarms
ab = [("Version 1\n(no LLM)", 25, 11), ("LLM\nalone", 86, 28), ("Agreement\nrule only", 68, 22),
      ("+ no-evidence\nfilter", 49, 16), ("+ second\nreading", 49, 16), ("Version 2\n(final)", 47, 13)]
fig, ax = plt.subplots(figsize=(6.6, 3.0))
x = range(len(ab)); w = 0.38
b1 = ax.bar([i - w / 2 for i in x], [r[1] for r in ab], w, color=BLUE, label="False items caught")
b2 = ax.bar([i + w / 2 for i in x], [r[2] for r in ab], w, color=RED, alpha=0.75, label="False alarms on true items")
for bars in (b1, b2):
    for r in bars:
        ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 1.5, f"{int(r.get_height())}%", ha="center", fontsize=9)
ax.set_xticks(list(x)); ax.set_xticklabels([r[0] for r in ab], fontsize=9.5)
ax.set_ylim(0, 100); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
ax.grid(axis="y", color="#E5E5E5"); ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=False, fontsize=9.5, loc="upper right")
ax.set_title("The LLM alone catches most errors but raises many false alarms", fontsize=11.5, loc="left")
fig.tight_layout(); fig.savefig(f"{OUT}/chart_ablation.png", dpi=220); plt.close(fig)
print("charts written")
