import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch

from pathlib import Path

FIGS = Path(__file__).resolve().parent.parent / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "figure.facecolor": "white", "savefig.dpi": 300, "savefig.bbox": "tight"})

C = ["#1f4e79", "#4a7c59", "#b07d2b", "#7a5a83", "#8a8a8a"]  # bloc colors
INK = "#222222"; EDGE = "#9e9e9e"

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13.5, 4.7))
for ax in (ax1, ax2, ax3):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal"); ax.axis("off")

def node(ax, x, y, c, r=0.022, z=3):
    ax.add_patch(plt.Circle((x, y), r, facecolor=c, edgecolor="white", lw=0.8, zorder=z))
def edge(ax, p, q, c=EDGE, lw=1.2, ls="-", z=1):
    ax.plot([p[0], q[0]], [p[1], q[1]], color=c, lw=lw, ls=ls, zorder=z)

# ---------- Panel (a): patrilines ----------
P1 = {"r": (0.22, 0.74), "a": (0.10, 0.48), "b": (0.34, 0.48), "c": (0.34, 0.22), "d": (0.10, 0.22)}
P2 = {"r": (0.72, 0.74), "a": (0.60, 0.48), "b": (0.84, 0.48), "c": (0.84, 0.22)}
for (u, v) in [("r", "a"), ("r", "b"), ("b", "c"), ("a", "d")]:
    edge(ax1, P1[u], P1[v], c=C[0], lw=1.6)
for (u, v) in [("r", "a"), ("r", "b"), ("b", "c")]:
    edge(ax1, P2[u], P2[v], c=C[1], lw=1.6)
edge(ax1, P1["c"], P2["a"], c=INK, lw=1.3, ls=(0, (3, 3)))  # marriage across lines
for p in P1.values(): node(ax1, *p, C[0])
for p in P2.values(): node(ax1, *p, C[1])
ax1.text(0.5, 0.99, "(a) patrilines", ha="center", va="top", fontsize=13)

# ---------- Panel (b): marriage-blocs ----------
# patriline nodes (each a small line); two blocs
B1 = [(0.14, 0.52), (0.30, 0.66), (0.36, 0.38), (0.16, 0.28)]
B2 = [(0.70, 0.58), (0.86, 0.46), (0.72, 0.30)]
ax2.add_patch(Ellipse((0.24, 0.46), 0.48, 0.60, facecolor=C[0], alpha=0.09, edgecolor=C[0], lw=1.1, zorder=0))
ax2.add_patch(Ellipse((0.77, 0.45), 0.38, 0.50, facecolor=C[1], alpha=0.09, edgecolor=C[1], lw=1.1, zorder=0))
mar = [(B1[0], B1[1], 3), (B1[0], B1[3], 2), (B1[1], B1[2], 2), (B1[2], B1[3], 1),
       (B2[0], B2[1], 2), (B2[0], B2[2], 3), (B1[2], B2[2], 1)]
for p, q, w in mar:
    edge(ax2, p, q, c=EDGE, lw=1.0 + 0.9 * w)
for p in B1: node(ax2, *p, C[0], r=0.028)
for p in B2: node(ax2, *p, C[1], r=0.028)
ax2.text(0.5, 0.99, "(b) marriage-blocs", ha="center", va="top", fontsize=13)

# ---------- Panel (c): kin-reach ----------
cx, cy = 0.47, 0.55
for rr in (0.10, 0.19, 0.28, 0.37):
    ax3.add_patch(plt.Circle((cx, cy), rr, fill=False, ls=(0, (2, 3)), lw=0.8, ec=EDGE, zorder=0))
rng = np.random.default_rng(3)
# (radius, angle, bloc-color-index) laid out by hop; ego reaches 5 distinct blocs
ring = {1: [(0), (0)], 2: [], 3: [], 4: []}
pts = []  # (x,y,color idx, hop)
def place(hop, angs, cols):
    r = {1: 0.10, 2: 0.19, 3: 0.28, 4: 0.37}[hop]
    for a, ci in zip(angs, cols):
        pts.append((cx + r * np.cos(a), cy + r * np.sin(a), ci, hop))
place(1, np.deg2rad([70, 200, 320]), [0, 0, 1])
place(2, np.deg2rad([40, 110, 250, 300]), [0, 1, 1, 2])
place(3, np.deg2rad([20, 80, 150, 220, 330]), [0, 2, 1, 3, 2])
place(4, np.deg2rad([55, 130, 190, 265, 350]), [3, 4, 2, 4, 3])
# edges: connect each node to a plausible closer-hop parent
def nearest_inner(x, y, hop):
    cand = [(px, py) for (px, py, _, h) in pts if h == hop - 1] or [(cx, cy)]
    return min(cand, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2)
for (x, y, ci, hop) in pts:
    q = (cx, cy) if hop == 1 else nearest_inner(x, y, hop)
    edge(ax3, (x, y), q, c=EDGE, lw=0.9)
for (x, y, ci, hop) in pts:
    node(ax3, x, y, C[ci], r=0.020)
ax3.add_patch(plt.Circle((cx, cy), 0.028, facecolor=INK, edgecolor="white", lw=1, zorder=5))
ax3.text(0.5, 0.99, "(c) kin-reach", ha="center", va="top", fontsize=13)
ax3.text(cx, 0.09, "reach = 5 blocs, 17 people", ha="center", va="top", fontsize=10, color=INK)

fig.savefig(f"{FIGS}/fig_measure_pipeline.png"); plt.close(fig)
print("pipeline done")
