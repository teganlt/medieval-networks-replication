"""Spanning edges per community, Leiden AND Louvain, 1%/2% component filters,
non-overlapping 50-year birth-cohort buckets 800-1700, raw and edge-controlled
(residualized on log #edges). Mirrors 05_leiden_rolling_windows.py:
isolate-drop -> component filter -> detect -> count cross-community edges."""
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
plt.rcParams.update({"font.size": 11, "font.family": "serif", "figure.facecolor": "white",
                     "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.dpi": 200, "savefig.bbox": "tight"})
INK = "#222222"; ACC = "#1f4e79"; MUT = "#9e9e9e"

t0 = time.time()
pers = pd.read_csv(f"{ROOT}/output/persons_imputed.csv", dtype={"id": str})
birth = dict(zip(pers.id, pd.to_numeric(pers.birth, errors="coerce")))
pp = pd.read_csv(f"{ROOT}/output/parent_pairs.csv", dtype=str)
sp = pd.read_csv(f"{ROOT}/output/spouse_pairs.csv", dtype=str)
all_edges = list(zip(pp.parent_id, pp.child_id)) + list(zip(sp.a, sp.b))
print(f"loaded ({time.time()-t0:.0f}s)", flush=True)

def window_graph(ws, we):
    nodes = {p for p, y in birth.items() if y is not None and not np.isnan(y) and ws <= y < we}
    edges = [(a, b) for a, b in all_edges if a in nodes and b in nodes and a != b]
    if not edges: return None
    ns = sorted(nodes); idx = {p: i for i, p in enumerate(ns)}
    g = ig.Graph(n=len(ns), edges=[(idx[a], idx[b]) for a, b in edges], directed=False)
    g.simplify(multiple=True, loops=True)
    keep = np.where(np.array(g.degree()) > 0)[0]
    return g.subgraph(keep)

def spanning(g, drop_pct, detector):
    comp = g.connected_components(mode="weak")
    sizes = np.array(comp.sizes()); total = int(sizes.sum())
    thresh = max(1, int(np.ceil(drop_pct * total)))
    keep = np.where(np.array([sizes[m] >= thresh for m in comp.membership]))[0]
    if keep.size == 0: return None
    g1 = g.subgraph(keep)
    if detector == "leiden":
        part = leidenalg.find_partition(g1, leidenalg.RBConfigurationVertexPartition,
                                        resolution_parameter=1.0, seed=42)
        labels = np.array(part.membership)
    else:
        labels = np.array(g1.community_multilevel().membership)
    ncomm = len(set(labels))
    lab_s = labels[[e.source for e in g1.es]]
    lab_t = labels[[e.target for e in g1.es]]
    nspan = int(np.sum(lab_s != lab_t))
    return {"n_nodes": g1.vcount(), "n_edges": g1.ecount(), "n_comm": ncomm,
            "n_span": nspan, "spc": nspan / ncomm if ncomm else np.nan}

rows = []
for ws in range(800, 1700, 50):
    g = window_graph(ws, ws + 50)
    if g is None or g.vcount() == 0: continue
    for det in ("leiden", "louvain"):
        for tag, pct in (("1pct", 0.01), ("2pct", 0.02)):
            r = spanning(g, pct, det)
            if r is None: continue
            rows.append({"detector": det, "filter": tag, "window_mid": ws + 25, **r})
    print(f"  window {ws}-{ws+50} done ({time.time()-t0:.0f}s)", flush=True)
df = pd.DataFrame(rows)
df.to_csv(f"{ROOT}/output/spanning_windows_1700.csv", index=False)

# edge control: residualize spc on log(n_edges) within each detector x filter series
def adjust(sub):
    X = np.column_stack([np.ones(len(sub)), np.log(sub.n_edges)])
    b, *_ = np.linalg.lstsq(X, sub.spc.values, rcond=None)
    return sub.spc.values - X @ b + sub.spc.mean()
df["spc_adj"] = np.nan
for (det, tag), sub in df.groupby(["detector", "filter"]):
    df.loc[sub.index, "spc_adj"] = adjust(sub)

fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.6), sharex=True)
for i, det in enumerate(("leiden", "louvain")):
    for j, (col, ttl) in enumerate((("spc", "raw"), ("spc_adj", "controlling for number of edges"))):
        ax = axes[i, j]
        ax.axvspan(1000, 1215, color=ACC, alpha=0.06, zorder=0)
        for tag, ls in (("1pct", "-"), ("2pct", "--")):
            s = df[(df.detector == det) & (df["filter"] == tag)].sort_values("window_mid")
            ax.plot(s.window_mid, s[col], ls, color=(ACC if i == 0 else INK), lw=1.9,
                    marker="o", ms=3.5, label=f"component filter ≥ {tag[0]}%")
        ax.set_title(f"({'abcd'[i*2+j]}) {det.capitalize()}, {ttl}", fontsize=11, loc="left")
        if i == 1: ax.set_xlabel("window midpoint (birth-year basis)")
        if j == 0: ax.set_ylabel("spanning edges per community")
axes[0, 0].legend(frameon=False, fontsize=9, loc="upper left")
fig.tight_layout()
fig.savefig(f"{FIGS}/fig_spanning_1700.png"); plt.close(fig)
print("saved fig_spanning_1700.png")
print(df.pivot_table(index="window_mid", columns=["detector", "filter"], values="spc").round(2).to_string())
