"""
fig_peer_triptych.py
====================
Three-panel construction figure for the Prediction-2 peer variables (the 7/27
reduced-form redo, scripts 110-112), visually parallel to fig_reach_berg.png.

Example noble: Pedro II, Rey de Aragon (p11329.htm#i113283, b.1176, EMFP).
  (a) his birth network  : the focal + his pre-natal 4-hop peer set (temporal
                           BFS, every traversed node born strictly before 1176),
                           nodes colored by marriage-bloc.
  (b) each peer's breadth: zoom on one peer (Marguerite Capet) with her
                           pre-birth 1-hop neighbours colored by bloc; her
                           distinct-bloc count (3) is the per-peer breadth.
  (c) the two peer vars  : histogram of per-peer 1-hop bloc counts with the
                           mean marked (peer breadth zB) and the pre-birth
                           dispute-letter peers highlighted (adoption share zD).

Peer-set / breadth / adoption logic mirrors 110_peer_rf_build.py exactly.
Output: figs/fig_peer_triptych.png
CLI: python scripts/fig_peer_triptych.py
"""
import collections
import sys
from pathlib import Path

import igraph as ig
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Circle

R = Path(__file__).resolve().parent.parent
OUT = R / "output"
FIGS = R / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.family": "serif", "figure.facecolor": "white",
                     "savefig.dpi": 300, "savefig.bbox": "tight"})
INK = "#222222"; EDGE = "#b9b9b9"; OTHER = "#8a8a8a"
# NO reds in the bloc palette: brick red is reserved for the dispute-peer
# highlight in panel (c), so a red bloc node would read as "disputant".
PALETTE = ["#1f4e79", "#b07d2b", "#4a7c59", "#5b4a86", "#3d7a8a", "#7a6652"]
DISP = "#8c3b3b"          # dispute-peer highlight in panel (c)

FOCAL = "p11414.htm#i114133"   # Andrew Arpad, son of Andrew II of Hungary, b.1205
FOCAL_LAB = "Andrew Árpád"     # (Pedro II de Aragon was the exemplar for the
                               # dispute-flag version; his peers have no pre-1176
                               # secular-territorial letters, so switched 7/30)
PEER = "p10216.htm#i102152"    # Marguerite Capet, Princesse de France
PEER_LAB = "Marguerite Capet"
K = 4

# ---------------- data (identical construction to 110) ----------------
def to_year(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None

persons = pd.read_csv(OUT / "persons_imputed.csv", dtype={"id": str})
birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
name = dict(zip(persons.id, persons.name))
bloc = dict(zip(*[pd.read_csv(OUT / "patriline_bloc_assignment.csv", dtype=str)[c]
                  for c in ("id", "dynasty")]))
pp = pd.read_csv(OUT / "parent_pairs.csv", dtype=str)
sp = pd.read_csv(OUT / "spouse_pairs.csv", dtype=str)
pids = list(persons["id"].values)
fi = {p: i for i, p in enumerate(pids)}
ed = [(fi[a], fi[b]) for a, b in pp.values if a in fi and b in fi]
seen = set()
for a, b in sp.values:
    if a in fi and b in fi:
        k = (min(a, b), max(a, b))
        if k not in seen:
            seen.add(k)
            ed.append((fi[a], fi[b]))
G = ig.Graph(n=len(pids), edges=ed)
nbrs = [np.array(G.neighbors(v), dtype=np.int64) for v in range(G.vcount())]
barr = np.array([b if (b := birth.get(pids[i])) is not None else np.nan
                 for i in range(G.vcount())])
bloc_arr = [bloc.get(pids[i], "") for i in range(G.vcount())]

coded = pd.read_csv(OUT / "matched_docs_coded.csv", dtype={"doc_id": str})[["doc_id", "domain"]]
mt = pd.read_csv(OUT / "doc_matches_ai_extracted_high.csv", dtype={"doc_id": str, "person_id": str})
mt = mt.merge(coded, on="doc_id", how="left")
first_disp = np.full(G.vcount(), np.inf)   # first SECULAR-TERRITORIAL letter (the adoption companion, 7/30)
for r in mt.itertuples(index=False):
    if r.person_id in fi and pd.notna(r.doc_year) and r.domain == "secular_territorial":
        i = fi[r.person_id]
        first_disp[i] = min(first_disp[i], int(r.doc_year))

# temporal BFS (110's peer_stats), keeping the hop layer of each peer
ti = fi[FOCAL]
cut = barr[ti]
one = [u for u in nbrs[ti] if not np.isnan(barr[u]) and barr[u] < cut]
vis = {ti} | set(one)
fr = set(one)
hop = {u: 1 for u in one}
for h in range(2, K + 1):
    nf = set()
    for x in fr:
        for u in nbrs[x]:
            if u in vis or np.isnan(barr[u]) or barr[u] >= cut:
                continue
            vis.add(u); nf.add(u); hop[u] = h
    fr = nf
    if not fr:
        break
kin = sorted(hop)
n = len(kin)

def pre_blocs(u):
    return {bloc_arr[v] for v in nbrs[u] if bloc_arr[v]
            and not np.isnan(barr[v]) and barr[v] < cut}

bp = {u: len(pre_blocs(u)) for u in kin}
zB = float(np.mean(list(bp.values())))
disp_peers = [u for u in kin if first_disp[u] < cut]
zD = len(disp_peers) / n
print(f"focal {FOCAL_LAB} b.{int(cut)} | peers={n} | breadth={zB:.3f} | "
      f"dispute={len(disp_peers)}/{n} = {zD:.3f}")
print("dispute peers:", [name.get(pids[u]) for u in disp_peers])

# bloc -> color (top blocs by peer count; the panel-b peer's blocs included)
peer_bloc = {u: (bloc_arr[u] or "?") for u in kin}
cnt = collections.Counter(peer_bloc.values())
pi = fi[PEER]
pb_blocs = sorted(pre_blocs(pi))
top = [b for b, _ in cnt.most_common() if b != "?"][:4]
for b in pb_blocs:
    if b not in top:
        top.append(b)
BC = {b: PALETTE[i] for i, b in enumerate(top)}
col = lambda b: BC.get(b, OTHER)
print("colored blocs:", BC, "| panel-b peer blocs:", pb_blocs)

# ---------------- figure ----------------
fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(14, 5.0))
for ax in (a1, a2):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal"); ax.axis("off")

def dot(ax, x, y, c, r=0.02, z=3, ec="white", lw=0.8):
    ax.add_patch(Circle((x, y), r, facecolor=c, edgecolor=ec, lw=lw, zorder=z))

# ---- panel (a): the pre-natal 4-hop peer set, rings by hop ----
cx, cy = 0.5, 0.52
Rr = {1: 0.13, 2: 0.25, 3: 0.36, 4: 0.46}
for h in sorted(set(hop.values())):
    a1.add_patch(Circle((cx, cy), Rr[h], fill=False, ls=(0, (2, 4)), lw=0.7,
                        ec="#dddddd", zorder=0))
pos1 = {}
for h in (1, 2, 3, 4):
    ring = sorted([u for u in kin if hop[u] == h], key=lambda u: peer_bloc[u])
    for k, u in enumerate(ring):
        # ring 1 phase 0 keeps its nodes clear of the focal's label below
        t = 2 * np.pi * k / max(1, len(ring)) + (0.0 if h == 1 else 0.5 * h)
        pos1[u] = (cx + Rr[h] * np.cos(t), cy + Rr[h] * np.sin(t))
kset = set(kin)
drawn = set()
for u in kin:
    for v in nbrs[u]:
        if v in kset and (v, u) not in drawn:
            drawn.add((u, v))
            a1.plot([pos1[u][0], pos1[v][0]], [pos1[u][1], pos1[v][1]],
                    color=EDGE, lw=0.4, alpha=0.25, zorder=1)
    if ti in G.neighbors(int(u)):
        a1.plot([cx, pos1[u][0]], [cy, pos1[u][1]], color=EDGE, lw=0.4,
                alpha=0.25, zorder=1)
for u in kin:
    dot(a1, *pos1[u], col(peer_bloc[u]), r=0.016,
        ec=INK if u == pi else "white", lw=1.2 if u == pi else 0.8,
        z=4 if u == pi else 3)
dot(a1, cx, cy, INK, r=0.026, z=6, ec="white", lw=1.2)
a1.text(cx, cy - 0.062, FOCAL_LAB, ha="center", va="top", fontsize=8.5,
        color=INK, zorder=7, bbox=dict(fc="white", ec="none", alpha=0.85, pad=1))
a1.set_title("(a) his birth network", fontsize=13)
leg_blocs = [b for b in BC if cnt.get(b, 0) > 0]
handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor=BC[b], ms=8,
                  label=f"{b} ({cnt[b]})") for b in leg_blocs]
oth = sum(v for k2, v in cnt.items() if k2 not in BC)
if oth:
    handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor=OTHER,
                          ms=8, label=f"other ({oth})"))
a1.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.02),
          frameon=False, fontsize=8.5, ncol=3, handletextpad=0.15,
          columnspacing=0.9)

# ---- panel (b): one peer's 1-hop pre-birth bloc count ----
pnb = [v for v in nbrs[pi] if not np.isnan(barr[v]) and barr[v] < cut]
pnb = sorted(pnb, key=lambda v: (bloc_arr[v] or "~", name.get(pids[v], "")))
bx, by = 0.5, 0.55
rad = 0.25
pos2 = {}
ang0 = np.pi / 4          # diagonals keep the labels inside the axes
for k, v in enumerate(pnb):
    t = ang0 + 2 * np.pi * k / max(1, len(pnb))
    pos2[v] = (bx + rad * np.cos(t), by + rad * np.sin(t))
for v in pnb:
    a2.plot([bx, pos2[v][0]], [by, pos2[v][1]], color=EDGE, lw=1.2, zorder=1)
for v in pnb:
    c = col(bloc_arr[v]) if bloc_arr[v] else OTHER
    dot(a2, *pos2[v], c, r=0.024, z=3)
    lx, ly = pos2[v]
    short = name.get(pids[v], "").split(",")[0]
    lab = f"{short}\n({bloc_arr[v] or '—'})"
    va = "bottom" if ly > by else "top"
    ly2 = ly + (0.045 if ly > by else -0.045)
    a2.text(lx, ly2, lab, ha="center", va=va, fontsize=7.5, color=INK,
            linespacing=1.15, bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.8))
dot(a2, bx, by, col(bloc_arr[pi]) if bloc_arr[pi] else OTHER, r=0.032,
    ec=INK, lw=1.6, z=5)
a2.text(bx + 0.062, by, f"{PEER_LAB}\n({len(pb_blocs)} blocs)", ha="left", va="center",
        fontsize=8.5, color=INK, zorder=7,
        bbox=dict(fc="white", ec="none", alpha=0.85, pad=1))
a2.set_title("(b) each peer's breadth", fontsize=13)

# ---- panel (c): the two peer variables ----
vals = sorted(set(bp.values()))
xs = list(range(min(vals), max(vals) + 1))
tot = [sum(1 for u in kin if bp[u] == x) for x in xs]
dis = [sum(1 for u in disp_peers if bp[u] == x) for x in xs]
non = [t - d for t, d in zip(tot, dis)]
a3.bar(xs, non, width=0.62, color="#9db4c8", edgecolor="white", lw=0.8, zorder=2)
a3.bar(xs, dis, width=0.62, bottom=non, color=DISP, edgecolor="white", lw=0.8,
       zorder=3)
for x, t in zip(xs, tot):
    a3.text(x, t + 0.7, str(t), ha="center", va="bottom", fontsize=9, color=INK)
a3.axvline(zB, color=INK, ls="--", lw=1.2, zorder=4)
ymax = max(tot) * 1.28
a3.set_ylim(0, ymax)
a3.set_xticks(xs)
a3.text(zB + 0.05, ymax * 0.97, f"peer breadth = {zB:.2f}", ha="left", va="top",
        fontsize=10, color=INK)
a3.text(0.97, 0.71, f"{len(disp_peers)} of {n} peers in\n"
        f"secular-territorial letters\n"
        f"before his birth\n(arbitration share {zD:.3f})",
        transform=a3.transAxes, ha="right", va="top", fontsize=9, color=DISP)
a3.set_xlabel("1-hop bloc count per peer", fontsize=10)
a3.set_ylabel("peers", fontsize=10)
for s in ("top", "right"):
    a3.spines[s].set_visible(False)
a3.tick_params(labelsize=9)
a3.set_box_aspect(1)
a3.set_title("(c) the two peer variables", fontsize=13)

fig.savefig(FIGS / "fig_peer_triptych.png")
plt.close(fig)
print(f"peer triptych done | peers={n} rings={collections.Counter(hop.values())} "
      f"| panel-b nbrs={len(pnb)} | hist={dict(zip(xs, tot))} disp={dict(zip(xs, dis))}")
