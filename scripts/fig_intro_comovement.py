"""Anchor-free introduction comovement figure: unweighted depth-adjusted
ancestor uniqueness (birth-cohort basis, left axis) vs mandement share of
papal letters (letter-date basis, right axis). Replaces the dynasty-based
interdynastic-marriage line. Output: fig_comovement_anchorfree.png"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGS = ROOT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 12, "font.family": "serif", "figure.facecolor": "white",
                     "savefig.dpi": 200, "savefig.bbox": "tight"})
INK = "#222222"; ACC = "#1f4e79"; MUT = "#9e9e9e"

au = pd.read_csv(f"{ROOT}/output/ancestor_uniqueness_windows.csv")
au = au[au.wmid >= 925]
ap = pd.read_csv(f"{ROOT}/output/aposcripta_subject_timeseries.csv")
ap = ap[(ap.window_mid >= 900) & (ap.window_mid <= 1500)]

fig, ax1 = plt.subplots(figsize=(8.8, 4.9))
ax1.axvspan(1000, 1215, color=ACC, alpha=0.06, zorder=0)

ax1.fill_between(au.wmid, au.mua - au.ciua, au.mua + au.ciua, color=ACC, alpha=0.18, lw=0)
l1, = ax1.plot(au.wmid, au.mua, color=ACC, lw=2.2, marker="o", ms=3.5,
               label="ancestor uniqueness (left)")
ax1.set_xlabel("year")
ax1.set_ylabel("ancestor uniqueness\n(unweighted, depth-adjusted)", color=ACC)
ax1.tick_params(axis="y", colors=ACC)
ax1.set_ylim(0.905, 0.975)
ax1.spines["top"].set_visible(False)

ax2 = ax1.twinx()
l2, = ax2.plot(ap.window_mid, ap.share_mandement, color=INK, lw=1.9, ls=(0, (2, 2)),
               label="mandement share (right)")
ax2.set_ylabel("mandement share of papal letters", color=INK)
ax2.tick_params(axis="y", colors=INK)
ax2.set_ylim(0, 1.0)
ax2.spines["top"].set_visible(False)

ax1.text(1155, 0.9635, "prohibition", ha="center", color=ACC, fontsize=10)
ax1.legend(handles=[l1, l2], frameon=False, fontsize=10, loc="upper left")
ax1.set_xlim(890, 1510)
fig.savefig(f"{FIGS}/fig_comovement_anchorfree.png"); plt.close(fig)
print("saved fig_comovement_anchorfree.png")
print("uniqueness (mua):", au.set_index("wmid").mua.round(3).to_dict())
