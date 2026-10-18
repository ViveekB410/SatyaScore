"""Figures for the Version 2 IEEE paper: architecture (Fig. 1) and the per-claim decision (Fig. 2)."""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon

OUT = sys.argv[1]
plt.rcParams["font.family"] = "Times New Roman"
BLUE, GREEN, ORANGE, GREY, PURPLE, YELLOW = "#DCE6F2", "#E2F0D9", "#FCE4D6", "#EDEDED", "#E4DFEC", "#FFF2CC"


def box(ax, cx, cy, w, h, text, fc=BLUE, fs=11, bold=False):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc=fc, ec="black", lw=1.1))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", linespacing=1.25)


def diamond(ax, cx, cy, w, h, text, fs=10.5):
    ax.add_patch(Polygon([(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)],
                         closed=True, fc=ORANGE, ec="black", lw=1.1))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, linespacing=1.2)


def arrow(ax, x1, y1, x2, y2, label=None, lx=0.0, ly=0.0, fs=10):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=1.2, color="black"))
    if label:
        ax.text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label, ha="center", va="center", fontsize=fs,
                style="italic", bbox=dict(fc="white", ec="none", pad=1))


def canvas(w, h, xmax, ymax):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xmax); ax.set_ylim(0, ymax); ax.axis("off")
    return fig, ax


# ---------- Fig. 1: architecture ----------
fig, ax = canvas(7.2, 9.6, 12, 16)
box(ax, 6, 15.1, 10.4, 1.1, "Web application (React) and REST API (FastAPI)\ntext / .txt / .pdf input  ·  marked text  ·  claim cards  ·  history", BLUE, 11)
box(ax, 6, 13.3, 10.4, 1.1, "Claim extraction\nEnglish: spaCy parsing, splitting, pronoun resolution  ·  Hindi: sentence split", GREEN, 11)
arrow(ax, 6, 14.55, 6, 13.85)
srcs = [(1.6, "Official\nstatistics\n(World Bank,\nWHO)"), (4.2, "Knowledge\ngraph\n(Wikidata)"), (6.8, "Published\nfact-checks\n(Google Fact\nCheck API)")]
for x, t in srcs:
    box(ax, x, 10.9, 2.3, 2.2, t, PURPLE, 10.5)
    arrow(ax, x, 12.75, x, 12.0)
box(ax, 10.0, 10.9, 3.4, 2.2, "Evidence retrieval\nXLM-R + FAISS\ntop-10 passages\n(102,069 + on demand)", PURPLE, 10.5)
arrow(ax, 10.0, 12.75, 10.0, 12.0)
box(ax, 4.2, 7.9, 7.5, 1.4, "Source decision (first that applies)\nstatistics / Wikidata: 1.0 or 0.0 and the correct value\nfact-check: 0.95 or 0.05", ORANGE, 10.5)
for x in (1.6, 4.2, 6.8):
    arrow(ax, x, 9.8, 4.2 + (x - 4.2) * 0.8, 8.6)
box(ax, 10.0, 7.9, 3.4, 1.4, "NLI (mDeBERTa)\nevidence rule: score s", PURPLE, 10.5)
arrow(ax, 10.0, 9.8, 10.0, 8.6)
box(ax, 8.4, 5.0, 7.2, 1.9, "LLM cross-check (gpt-oss-20b, local)\nfirst reading: top-5 passages + own knowledge\nsecond reading: all 10 passages only\nagreement rule with s (Fig. 2)", YELLOW, 10.5)
arrow(ax, 10.0, 7.2, 10.0, 5.95)
arrow(ax, 2.0, 7.2, 2.0, 3.05, "decided", 0.0, 1.4)
arrow(ax, 6.6, 7.2, 6.6, 5.95, "not decided", -1.0, 0.0)
box(ax, 6, 2.2, 10.4, 1.6, "Verdict, score and explanation per claim\nVerified / Uncertain / Hallucinated  ·  deciding source  ·  wrong words marked\nwhole text: Hallucinated if ≥ 1/3 of its claims are", ORANGE, 10.5)
arrow(ax, 8.5, 4.05, 8.5, 3.0)
ax.set_ylim(1.2, 15.8)
fig.savefig(f"{OUT}/fig1_architecture_v2.png", dpi=220, bbox_inches="tight"); plt.close(fig)

# ---------- Fig. 2: decision for one claim that no source decided ----------
fig, ax = canvas(7.4, 7.6, 14.6, 15)
box(ax, 6.2, 14.3, 9.4, 0.9, "Claim not decided by a structured source or a fact-check", BLUE, 11)
box(ax, 7.0, 12.7, 13.6, 1.5, "s = NLI evidence score over the top-10 passages, equations (1)-(2)\n"
    "j = LLM verdict from the top-5 passages and its own knowledge\n"
    "a Hallucinated j whose reason only says the evidence is missing counts as Uncertain", GREEN, 9.5)
arrow(ax, 6.2, 13.85, 6.2, 13.45)
X1, X2, X3 = 3.2, 8.5, 12.6
diamond(ax, X1, 10.4, 5.0, 1.8, "s > 0.65 and\nj = Verified ?", 10.5)
arrow(ax, X1, 11.95, X1, 11.3)
box(ax, X3, 10.4, 2.8, 0.9, "Verified", "#C6E0B4", 11, True)
arrow(ax, X1 + 2.5, 10.4, X3 - 1.4, 10.4, "yes", 0, 0.32)
diamond(ax, X1, 7.8, 5.0, 1.8, "j = Hallucinated\nand s ≤ 0.65 ?", 10.5)
arrow(ax, X1, 9.5, X1, 8.7, "no", 0.35, 0)
diamond(ax, X2, 7.8, 4.4, 1.8, "second reading\n(10 passages only)\nstates the claim?", 9.5)
arrow(ax, X1 + 2.5, 7.8, X2 - 2.2, 7.8, "yes", 0, 0.32)
box(ax, X3, 8.75, 2.8, 0.9, "Uncertain", GREY, 11, True)
box(ax, X3, 6.85, 2.8, 0.9, "Hallucinated", "#F4B183", 11, True)
arrow(ax, X2 + 2.2, 7.8, X3 - 1.4, 8.55, "yes", 0, 0.3)
arrow(ax, X2 + 2.2, 7.8, X3 - 1.4, 7.05, "no", 0, -0.3)
diamond(ax, X1, 5.0, 5.6, 2.0, "leans true?\nj ≠ Hallucinated and\n(s > 0.65 or j = Verified)", 9.5)
arrow(ax, X1, 6.9, X1, 5.95, "no", 0.35, 0)
diamond(ax, X2, 5.0, 4.4, 1.8, "second reading\n(10 passages only)\nstates the claim?", 9.5)
arrow(ax, X1 + 2.5, 5.0, X2 - 2.2, 5.0, "yes", 0, 0.32)
box(ax, X3, 5.0, 2.8, 0.9, "Verified", "#C6E0B4", 11, True)
arrow(ax, X2 + 2.2, 5.0, X3 - 1.4, 5.0, "yes", 0, 0.3)
box(ax, X2, 2.6, 2.8, 0.9, "Uncertain", GREY, 11, True)
arrow(ax, X2, 4.1, X2, 3.05, "no", 0.35, 0)
box(ax, X1, 2.6, 2.8, 0.9, "Uncertain", GREY, 11, True)
arrow(ax, X1, 4.05, X1, 3.05, "no", 0.35, 0)
ax.set_xlim(0.1, 14.3); ax.set_ylim(1.9, 15.0)
fig.savefig(f"{OUT}/fig2_decision_v2.png", dpi=220, bbox_inches="tight"); plt.close(fig)
print("figures written")
