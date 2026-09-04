"""Cross-community share of kinship ties at FIXED community count (K=25):
per 50-yr window (birth basis, 800-1700), 1% component filter, tune Leiden's
resolution so the partition has ~K communities, report n_span / n_edges.
Scale-free by construction: no resolution-limit drift, no subsampling damage."""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
import igraph as ig
import leidenalg
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
K_TARGET, PCT = 25, 0.01

t0 = time.time()
pers = pd.read_csv(f"{ROOT}/output/persons_imputed.csv", dtype={"id": str})
birth = dict(zip(pers.id, pd.to_numeric(pers.birth, errors="coerce")))
pp = pd.read_csv(f"{ROOT}/output/parent_pairs.csv", dtype=str)
sp = pd.read_csv(f"{ROOT}/output/spouse_pairs.csv", dtype=str)
all_edges = list(zip(pp.parent_id, pp.child_id)) + list(zip(sp.a, sp.b))

def window_kept_graph(ws, we):
    nodes = {p for p, y in birth.items() if y is not None and not np.isnan(y) and ws <= y < we}
    edges = [(a, b) for a, b in all_edges if a in nodes and b in nodes and a != b]
    if not edges: return None
    ns = sorted(nodes); idx = {p: i for i, p in enumerate(ns)}
    g = ig.Graph(n=len(ns), edges=[(idx[a], idx[b]) for a, b in edges], directed=False)
    g.simplify(multiple=True, loops=True)
    g = g.subgraph(np.where(np.array(g.degree()) > 0)[0])
    comp = g.connected_components(mode="weak")
    sizes = np.array(comp.sizes()); total = int(sizes.sum())
    thresh = max(1, int(np.ceil(PCT * total)))
    keep = np.where(np.array([sizes[m] >= thresh for m in comp.membership]))[0]
    if keep.size == 0: return None
    return g.subgraph(keep)

def partition_at(g, gamma):
    part = leidenalg.find_partition(g, leidenalg.RBConfigurationVertexPartition,
                                    resolution_parameter=gamma, seed=42)
    return np.array(part.membership)

def fixed_k_share(g, K, tol=2):
    lo, hi = 0.005, 50.0
    best = None
    for _ in range(24):
        mid = np.sqrt(lo * hi)
        labels = partition_at(g, mid)
        n = len(set(labels))
        if best is None or abs(n - K) < abs(best[0] - K):
            best = (n, mid, labels)
        if abs(n - K) <= tol: break
        if n < K: lo = mid
        else: hi = mid
    n, gamma, labels = best
    lab_s = labels[[e.source for e in g.es]]
    lab_t = labels[[e.target for e in g.es]]
    nspan = int(np.sum(lab_s != lab_t))
    return {"n_comm": n, "gamma": gamma, "n_span": nspan,
            "share": nspan / g.ecount(), "spc": nspan / n}

rows = []
for ws in range(800, 1700, 50):
    g = window_kept_graph(ws, ws + 50)
    if g is None or g.ecount() < 50: continue
    r = fixed_k_share(g, K_TARGET)
    rows.append({"window_mid": ws + 25, "n_nodes": g.vcount(), "n_edges": g.ecount(), **r})
    print(f"  {ws}-{ws+50}: E={g.ecount()} K={r['n_comm']} gamma={r['gamma']:.3f} share={r['share']:.3f} ({time.time()-t0:.0f}s)", flush=True)
df = pd.DataFrame(rows)
df.to_csv(f"{ROOT}/output/spanning_fixedK_1700.csv", index=False)

fig, ax = plt.subplots(figsize=(8.4, 4.6))
ax.axvspan(1000, 1215, color=ACC, alpha=0.06, zorder=0)
ax.plot(df.window_mid, df.share, color=ACC, lw=2.2, marker="o", ms=4)
ax.set_xlabel("window midpoint (birth-year basis)")
ax.set_ylabel(f"share of ties crossing communities\n(partition fixed at ~{K_TARGET} communities)")
ax.text(1107, ax.get_ylim()[1] * 0.95, "prohibition", ha="center", va="top", color=ACC, fontsize=10)
fig.savefig(f"{FIGS}/fig_spanning_fixedK.png"); plt.close(fig)
print("saved fig_spanning_fixedK.png")
print(df.round(3).to_string(index=False))
