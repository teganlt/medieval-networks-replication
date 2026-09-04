"""fig_horizon_unified.py -- rebuild figs/fig_horizon.png on the ESTIMATION variable.

Replaces the deprecated fig_measure_hopcorr.py (which used a non-temporal
neighborhood variant). Data source: output/bloc_reach_hopsweep.csv
(temporal-BFS n_dyn_{3,4,5,6}hop / n_nodes_{3,4,5,6}hop, same construction as
the baseline), restricted to the estimation sample = rows of
output/bloc_reach_fullgraph.csv with mother_n_dyn_4hop non-missing (N=2,195).

Panel (a): distribution of kin-reach (n_dyn) by hop radius, log-scale boxplot,
hop-4 highlighted. Panel (b): cor(n_dyn, n_nodes) by hop.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
FIGS = ROOT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 12, "font.family": "serif", "figure.facecolor": "white",
    "axes.spines.top": False, "axes.spines.right": False,
    "savefig.dpi": 300, "savefig.bbox": "tight",
})
INK = "#222222"; ACC = "#1f4e79"; MUT = "#9e9e9e"

hs = pd.read_csv(ROOT / "output" / "bloc_reach_hopsweep.csv")
fg = pd.read_csv(ROOT / "output" / "bloc_reach_fullgraph.csv")

est = fg.loc[fg["mother_n_dyn_4hop"].notna(), ["person_id"]]
df = est.merge(hs, on="person_id", how="inner")
print(f"estimation sample N = {len(est)}; merged to hopsweep N = {len(df)}")

hops = [3, 4, 5, 6]
stats = {}
for h in hops:
    d = df[f"n_dyn_{h}hop"].astype(float)
    n = df[f"n_nodes_{h}hop"].astype(float)
    med = d.median(); q1, q3 = d.quantile([0.25, 0.75])
    r = np.corrcoef(d, n)[0, 1]
    stats[h] = dict(med=med, q1=q1, q3=q3, r=r)
    print(f"hop {h}: median {med:g}, IQR {q1:g}-{q3:g}, cor(reach,size) = {r:.3f}")

assert stats[4]["med"] == 4 and stats[4]["q1"] == 3 and stats[4]["q3"] == 6, \
    "hop-4 stats do not match the audited estimation variable (median 4, IQR 3-6)"

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 4.0))

# ---- panel (a): log-scale boxplot of n_dyn by hop, hop-4 highlighted -------
data = [df[f"n_dyn_{h}hop"].astype(float).values for h in hops]
bp = ax1.boxplot(data, positions=range(len(hops)), widths=0.55, patch_artist=True,
                 showfliers=False, medianprops=dict(color=INK, lw=1.4),
                 whiskerprops=dict(color=INK), capprops=dict(color=INK))
for i, (box, h) in enumerate(zip(bp["boxes"], hops)):
    if h == 4:
        box.set(facecolor=ACC, alpha=0.85, edgecolor=ACC, lw=1.5)
        bp["medians"][i].set(color="white", lw=1.6)
    else:
        box.set(facecolor="white", edgecolor=MUT, lw=1.2)
        bp["medians"][i].set(color=MUT, lw=1.4)
ax1.set_yscale("log")
ax1.set_xticks(range(len(hops)))
ax1.set_xticklabels([str(h) for h in hops])
ax1.set_xlabel("hop radius", color=INK)
ax1.set_ylabel("kin-reach (blocs), log scale", color=INK)
ax1.set_title("(a) Reach distribution by horizon", color=INK, loc="left", fontsize=12)
ax1.tick_params(colors=INK)
s4 = stats[4]
ax1.annotate(f"median {s4['med']:g}, IQR {s4['q1']:g}–{s4['q3']:g}",
             xy=(1, s4["q3"]), xytext=(0.72, 30), color=ACC, fontsize=11,
             arrowprops=dict(arrowstyle="-", color=ACC, lw=0.9))

# ---- panel (b): cor(reach, size) by hop ------------------------------------
rs = [stats[h]["r"] for h in hops]
ax2.plot(hops, rs, "-", color=MUT, lw=1.5, zorder=1)
ax2.scatter(hops, rs, s=45, color=MUT, zorder=2)
ax2.scatter([4], [stats[4]["r"]], s=80, color=ACC, zorder=3)
ax2.annotate(f"{stats[4]['r']:.2f}", xy=(4, stats[4]["r"]),
             xytext=(4.12, stats[4]["r"] - 0.045), color=ACC, fontsize=12)
ax2.set_xticks(hops)
ax2.set_xlabel("hop radius", color=INK)
ax2.set_ylabel("cor(kin-reach, neighborhood size)", color=INK)
ax2.set_title("(b) Reach–size correlation by horizon", color=INK, loc="left", fontsize=12)
ax2.set_ylim(0.5, 0.85)
ax2.tick_params(colors=INK)

fig.tight_layout()
out = FIGS / "fig_horizon.png"
fig.savefig(out)
print(f"wrote {out}")
