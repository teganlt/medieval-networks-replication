"""
150_stylized_figs.py
====================
Stylized-fact figures for the data section (8/29): the three exogamy series,
each with an N subpanel underneath (log scale) showing per-window observation
counts, so the reader can see the measures plateau at ~1200 while N keeps
growing -- the shape is not mechanical record growth.

Reads existing CSVs only (no recomputation):
  ancestor_uniqueness_windows.csv   (n = nobles per cohort passing >=6-slot filter)
  spanning_windows_1700.csv / spanning_fixedK_1700.csv  (n_nodes per window)
  interdyn_marriage_timeseries.csv  (n_both_anchored per window)

Out (figs/): fig_ancestor_uniqueness_n.png, fig_spanning_paper_n.png,
             fig_interdyn_n.png
CLI: python scripts/150_stylized_figs.py
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGS = ROOT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 12, "font.family": "serif", "figure.facecolor": "white",
                     "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.dpi": 200, "savefig.bbox": "tight"})
INK = "#222222"; ACC = "#1f4e79"; MUT = "#9e9e9e"


def n_panel(ax, x, n, label):
    ax.axvspan(1000, 1215, color=ACC, alpha=0.06, zorder=0)
    ax.plot(x, n, color=INK, lw=1.4)
    ax.fill_between(x, 1, n, color=INK, alpha=0.10, lw=0)
    ax.set_yscale("log")
    ax.set_ylabel(label, fontsize=8.5)
    ax.tick_params(labelsize=8.5)


# ---------- 1. ancestor uniqueness + N ----------
g = pd.read_csv(ROOT / "output" / "ancestor_uniqueness_windows.csv")
g = g[g.wmid >= 925].sort_values("wmid")
fig = plt.figure(figsize=(8.6, 6.1))
gs = gridspec.GridSpec(2, 1, height_ratios=[4, 1.1], hspace=0.08)
ax = fig.add_subplot(gs[0]); axn = fig.add_subplot(gs[1], sharex=ax)
ax.axvspan(1000, 1215, color=ACC, alpha=0.06, zorder=0)
ax.fill_between(g.wmid, g.m - g.ci, g.m + g.ci, color=MUT, alpha=0.20, lw=0)
ax.plot(g.wmid, g.m, color=MUT, lw=1.8, marker="o", ms=3.5, label="weighted, raw")
ax.fill_between(g.wmid, g.ma - g.cia, g.ma + g.cia, color=ACC, alpha=0.18, lw=0)
ax.plot(g.wmid, g.ma, color=ACC, lw=2.2, marker="o", ms=4, label="weighted, depth-adjusted")
ax.fill_between(g.wmid, g.mu - g.ciu, g.mu + g.ciu, color=MUT, alpha=0.20, lw=0)
ax.plot(g.wmid, g.mu, color=MUT, lw=1.6, ls="--", marker="s", ms=3, label="unweighted, raw")
ax.fill_between(g.wmid, g.mua - g.ciua, g.mua + g.ciua, color=ACC, alpha=0.18, lw=0)
ax.plot(g.wmid, g.mua, color=ACC, lw=1.9, ls="--", marker="s", ms=3.5, label="unweighted, depth-adjusted")
ax.set_ylabel("ancestor uniqueness (depth $\\leq$ 7)")
ax.legend(frameon=False, fontsize=9, loc="lower right", ncol=2)
ax.text(1107, ax.get_ylim()[1] - 0.002, "prohibition", ha="center", va="top", color=ACC, fontsize=10)
plt.setp(ax.get_xticklabels(), visible=False)
n_panel(axn, g.wmid, g.n, "nobles\nper cohort")
axn.set_xlabel("birth window midpoint")
fig.savefig(FIGS / "fig_ancestor_uniqueness_n.png"); plt.close(fig)
print("saved fig_ancestor_uniqueness_n.png")

# ---------- 2. spanning (two panels) + N ----------
sw = pd.read_csv(ROOT / "output" / "spanning_windows_1700.csv")
sw = sw[(sw.detector == "leiden") & (sw["filter"] == "1pct") & (sw.window_mid <= 1475)].sort_values("window_mid")
fk = pd.read_csv(ROOT / "output" / "spanning_fixedK_1700.csv")
fk = fk[fk.window_mid <= 1475].sort_values("window_mid")
fig = plt.figure(figsize=(11.6, 5.9))
gs = gridspec.GridSpec(2, 2, height_ratios=[4, 1.1], hspace=0.08, wspace=0.18)
for j, (s, ttl) in enumerate([(sw, "(a) resolution 1.0"),
                              (fk, "(b) fixed number of communities ($K\\approx25$)")]):
    ax = fig.add_subplot(gs[0, j]); axn = fig.add_subplot(gs[1, j], sharex=ax)
    ax.axvspan(1000, 1215, color=ACC, alpha=0.06, zorder=0)
    ax.plot(s.window_mid, s.spc, color=ACC, lw=2.2, marker="o", ms=4)
    ax.set_title(ttl, fontsize=11.5, loc="left")
    if j == 0:
        ax.set_ylabel("spanning edges per community")
    plt.setp(ax.get_xticklabels(), visible=False)
    ncol = "n_nodes" if "n_nodes" in s.columns else s.columns[1]
    n_panel(axn, s.window_mid, s[ncol], "nodes\nper window" if j == 0 else "")
    axn.set_xlabel("window midpoint (birth-year basis)")
fig.savefig(FIGS / "fig_spanning_paper_n.png"); plt.close(fig)
print("saved fig_spanning_paper_n.png")

# ---------- 3. interdynastic marriage share + N ----------
it = pd.read_csv(ROOT / "output" / "interdyn_marriage_timeseries.csv")
it = it[(it.window_mid >= 850) & (it.window_mid <= 1500)].sort_values("window_mid")
fig = plt.figure(figsize=(8.6, 6.1))
gs = gridspec.GridSpec(2, 1, height_ratios=[4, 1.1], hspace=0.08)
ax = fig.add_subplot(gs[0]); axn = fig.add_subplot(gs[1], sharex=ax)
ax.axvspan(1000, 1215, color=ACC, alpha=0.06, zorder=0)
ax.fill_between(it.window_mid, it.frac_inter_ci_lo, it.frac_inter_ci_hi,
                color=ACC, alpha=0.15, lw=0)
ax.plot(it.window_mid, it.frac_inter, color=ACC, lw=2.2)
ax.set_ylabel("share of marriages across dynasty lines")
ax.text(1107, ax.get_ylim()[1] * 0.97, "prohibition", ha="center", va="top", color=ACC, fontsize=10)
plt.setp(ax.get_xticklabels(), visible=False)
n_panel(axn, it.window_mid, it.n_both_anchored, "anchored\nmarriages")
axn.set_xlabel("window midpoint (marriage-date basis)")
fig.savefig(FIGS / "fig_interdyn_n.png"); plt.close(fig)
print("saved fig_interdyn_n.png")
