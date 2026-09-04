"""Paper figure 1: birth-cohort Leiden spanning per community, 1% filter,
truncated 1500 — (a) resolution 1.0, (b) fixed K~25. From existing CSVs.
Paper figure 2: proximity-weighted ancestor uniqueness, depth<=7, same 50-yr
birth buckets 800-1500. index = sum_a 2^-d_first(a) / sum_d 2^-d P_d."""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGS = ROOT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 12, "font.family": "serif", "figure.facecolor": "white",
                     "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.dpi": 200, "savefig.bbox": "tight"})
INK = "#222222"; ACC = "#1f4e79"; MUT = "#9e9e9e"
G = 7

# ---------- figure 1: two-panel spanning ----------
sw = pd.read_csv(f"{ROOT}/output/spanning_windows_1700.csv")
sw = sw[(sw.detector == "leiden") & (sw["filter"] == "1pct") & (sw.window_mid <= 1475)].sort_values("window_mid")
fk = pd.read_csv(f"{ROOT}/output/spanning_fixedK_1700.csv")
fk = fk[fk.window_mid <= 1475].sort_values("window_mid")

fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.6, 4.4), sharex=True)
for ax, s, col, ttl in [(a1, sw, "spc", "(a) resolution 1.0"),
                        (a2, fk, "spc", "(b) fixed number of communities ($K\\approx25$)")]:
    ax.axvspan(1000, 1215, color=ACC, alpha=0.06, zorder=0)
    ax.plot(s.window_mid, s[col], color=ACC, lw=2.2, marker="o", ms=4)
    ax.set_title(ttl, fontsize=11.5, loc="left")
    ax.set_xlabel("window midpoint (birth-year basis)")
a1.set_ylabel("spanning edges per community")
fig.tight_layout()
fig.savefig(f"{FIGS}/fig_spanning_paper.png"); plt.close(fig)
print("saved fig_spanning_paper.png")

# ---------- figure 2: proximity-weighted ancestor uniqueness ----------
t0 = time.time()
pers = pd.read_csv(f"{ROOT}/output/persons_imputed.csv", dtype={"id": str})
birth = dict(zip(pers.id, pd.to_numeric(pers.birth, errors="coerce")))
po = pd.read_csv(f"{ROOT}/output/parent_order.csv", dtype=str)
par = {}
for r in po.itertuples(index=False):
    ps = [p for p in (r.parent0_id, r.parent1_id) if isinstance(p, str) and p]
    if ps: par[r.child_id] = ps

def uniq_index(pid):
    """(weighted distinct, weighted slots, distinct count, raw slot count), w=2^-d."""
    first_depth = {}
    frontier = {pid: 1}
    wnum = wden = 0.0
    nslots = 0
    for d in range(1, G + 1):
        nxt = {}
        for x, mult in frontier.items():
            for p in par.get(x, ()):
                nxt[p] = nxt.get(p, 0) + mult
        if not nxt: break
        w = 2.0 ** (-d)
        for p, mult in nxt.items():
            wden += w * mult; nslots += mult
            if p not in first_depth:
                first_depth[p] = d; wnum += w
        frontier = nxt
    return wnum, wden, len(first_depth), nslots

rows = []
ids = [p for p, y in birth.items() if y is not None and not np.isnan(y) and 800 <= y < 1500]
print(f"focals 800-1500: {len(ids):,}")
for i, pid in enumerate(ids):
    wn, wd, nd, ns = uniq_index(pid)
    if ns >= 6:
        rows.append({"id": pid, "birth": birth[pid], "idx": wn / wd, "idxu": nd / ns, "nslots": ns})
    if (i + 1) % 10000 == 0: print(f"  {i+1:,}/{len(ids):,} ({time.time()-t0:.0f}s)", flush=True)
df = pd.DataFrame(rows)
# depth control: residualize each index on a cubic in log(ancestor slots)
L = np.log(df.nslots.values.astype(float))
X = np.column_stack([np.ones(len(df)), L, L ** 2, L ** 3])
for col in ("idx", "idxu"):
    beta, *_ = np.linalg.lstsq(X, df[col].values, rcond=None)
    df[col + "_adj"] = df[col].values - X @ beta + df[col].mean()
df["wmid"] = (df.birth // 50 * 50 + 25).astype(int)
g = df.groupby("wmid").agg(n=("idx", "size"),
                           m=("idx", "mean"), sd=("idx", "std"),
                           ma=("idx_adj", "mean"), sda=("idx_adj", "std"),
                           mu=("idxu", "mean"), sdu=("idxu", "std"),
                           mua=("idxu_adj", "mean"), sdua=("idxu_adj", "std")).reset_index()
for m_, s_, c_ in (("m", "sd", "ci"), ("ma", "sda", "cia"), ("mu", "sdu", "ciu"), ("mua", "sdua", "ciua")):
    g[c_] = 1.96 * g[s_] / np.sqrt(g.n)
g.to_csv(f"{ROOT}/output/ancestor_uniqueness_windows.csv", index=False)
g = g[g.wmid >= 925]   # plot truncated at 900 (thin early windows dropped)

fig, ax = plt.subplots(figsize=(8.6, 4.9))
ax.axvspan(1000, 1215, color=ACC, alpha=0.06, zorder=0)
ax.fill_between(g.wmid, g.m - g.ci, g.m + g.ci, color=MUT, alpha=0.20, lw=0)
ax.plot(g.wmid, g.m, color=MUT, lw=1.8, marker="o", ms=3.5, label="weighted, raw")
ax.fill_between(g.wmid, g.ma - g.cia, g.ma + g.cia, color=ACC, alpha=0.18, lw=0)
ax.plot(g.wmid, g.ma, color=ACC, lw=2.2, marker="o", ms=4, label="weighted, depth-adjusted")
ax.fill_between(g.wmid, g.mu - g.ciu, g.mu + g.ciu, color=MUT, alpha=0.20, lw=0)
ax.plot(g.wmid, g.mu, color=MUT, lw=1.6, ls="--", marker="s", ms=3, label="unweighted, raw")
ax.fill_between(g.wmid, g.mua - g.ciua, g.mua + g.ciua, color=ACC, alpha=0.18, lw=0)
ax.plot(g.wmid, g.mua, color=ACC, lw=1.9, ls="--", marker="s", ms=3.5, label="unweighted, depth-adjusted")
ax.set_xlabel("birth window midpoint")
ax.set_ylabel("ancestor uniqueness (depth $\\leq$ 7)")
ax.legend(frameon=False, fontsize=9, loc="lower right", ncol=2)
ax.text(1107, ax.get_ylim()[1] - 0.002, "prohibition", ha="center", va="top", color=ACC, fontsize=10)
fig.savefig(f"{FIGS}/fig_ancestor_uniqueness.png"); plt.close(fig)
print("saved fig_ancestor_uniqueness.png")
print(g[["wmid", "n", "m", "ma", "mu", "mua"]].round(4).to_string(index=False))
