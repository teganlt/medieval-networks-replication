"""Both identification DAGs, black and white, with edge endpoints anchored on
patch borders so no line passes behind a box.
  fig_iv_dag.png       - Pred 1 (forward IV), ancestor boxes now include 4-hop size
  fig_iv_dag_peer.png  - Pred 2 (complementarity IV), symmetric layout
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyBboxPatch, FancyArrowPatch

from pathlib import Path

FIGS = Path(__file__).resolve().parent.parent / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.size": 9})


def ellipse_anchor(cx, cy, w, h, tx, ty):
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0: return cx, cy
    t = np.arctan2(dy / (h / 2), dx / (w / 2))
    return cx + (w / 2) * np.cos(t), cy + (h / 2) * np.sin(t)


def box_anchor(cx, cy, w, h, tx, ty):
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0: return cx, cy
    sx = (w / 2) / abs(dx) if dx else np.inf
    sy = (h / 2) / abs(dy) if dy else np.inf
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


class Dag:
    def __init__(self, figsize=(8.6, 5.4), xlim=11, ylim=7.4):
        self.fig, self.ax = plt.subplots(figsize=figsize)
        self.ax.set_xlim(0, xlim); self.ax.set_ylim(0, ylim); self.ax.axis("off")
        self.nodes = {}

    def ellipse(self, name, x, y, text, sub, w=2.6, h=1.1):
        self.nodes[name] = ("e", x, y, w, h)
        self.ax.add_patch(Ellipse((x, y), w, h, facecolor="white",
                                  edgecolor="black", linewidth=1.4, zorder=3))
        self.ax.text(x, y + 0.14, text, ha="center", va="center",
                     fontsize=9.5, fontweight="bold", zorder=4)
        self.ax.text(x, y - 0.22, sub, ha="center", va="center",
                     fontsize=8, style="italic", color="0.35", zorder=4)

    def box(self, name, x, y, text, w=3.1, h=0.95):
        self.nodes[name] = ("b", x, y, w, h)
        self.ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                          boxstyle="round,pad=0.06", facecolor="0.93",
                          edgecolor="black", linewidth=1.0, zorder=3))
        self.ax.text(x, y, text, ha="center", va="center", fontsize=8.6, zorder=4)

    def _anchor(self, name, tx, ty):
        kind, x, y, w, h = self.nodes[name]
        f = ellipse_anchor if kind == "e" else box_anchor
        return f(x, y, w, h, tx, ty)

    def edge(self, a, b, style="-", lw=1.0, arrow=False, label=None,
             lab_dx=0.0, lab_dy=0.22, bold=False):
        _, xa, ya, *_ = self.nodes[a]
        _, xb, yb, *_ = self.nodes[b]
        p1 = self._anchor(a, xb, yb)
        p2 = self._anchor(b, xa, ya)
        if arrow:
            self.ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>",
                              mutation_scale=13, linewidth=3.0 if bold else lw,
                              linestyle=style, color="black", zorder=2,
                              shrinkA=0, shrinkB=1))
        else:
            self.ax.plot([p1[0], p2[0]], [p1[1], p2[1]], linestyle=style,
                         linewidth=lw, color="black", zorder=2)
        if label:
            mx, my = (p1[0] + p2[0]) / 2 + lab_dx, (p1[1] + p2[1]) / 2 + lab_dy
            self.ax.text(mx, my, label, ha="center", va="center",
                         fontsize=8.6, style="italic", zorder=4,
                         bbox=dict(fc="white", ec="none", pad=1))

    def save(self, path):
        self.fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(self.fig)


# ================= Pred 1: forward IV =================
d = Dag()
d.ellipse("Z", 1.9, 3.6, "Mother's\nnetwork reach", "instrument")
d.ellipse("D", 5.5, 3.6, "Focal's\nnetwork reach", "endogenous")
d.ellipse("Y", 9.1, 3.6, "Papal dispute\nappearance", "outcome")
d.box("M", 2.3, 6.3, "Mother: rank, degree,\n4-hop size, appearances")
d.box("G", 6.7, 6.3, "Maternal grandfather: rank, degree,\n4-hop size, appearances, reach", w=3.6)
d.box("F", 5.5, 0.9, "Father: rank, degree, 4-hop size,\nappearances, reach increment", w=3.5)
# identifying chain
d.edge("Z", "D", arrow=True, bold=True, label="first stage", lab_dy=0.28)
d.edge("D", "Y", arrow=True, bold=True, label=r"$\beta$  (LATE)", lab_dy=0.28)
# conditioned paths
d.edge("M", "Z", style="--", arrow=True)
d.edge("M", "Y", lw=0.9)
d.edge("G", "Z", style="--", arrow=True)
d.edge("G", "Y", lw=0.9)
d.edge("F", "Z", lw=0.9)
d.edge("F", "Y", lw=0.9)
d.save(f"{FIGS}/fig_iv_dag.png")
print("saved fig_iv_dag.png")

# ================= Pred 2: complementarity IV =================
d = Dag()
d.ellipse("Z", 1.9, 3.6, "Peer network\nbreadth", "instrument")
d.ellipse("D", 5.5, 3.6, "Peer\ncourt use", "endogenous")
d.ellipse("Y", 9.1, 3.6, "Papal dispute\nappearance", "outcome")
d.box("N", 2.3, 6.3, "Focal network: reach,\nsize, title rank")
d.box("B", 6.7, 6.3, "Bloc and death-decade\nfixed effects", w=3.0)
d.box("F", 5.5, 0.9, "Father:\ndispute appearances", w=2.8)
# identifying chain
d.edge("Z", "D", arrow=True, bold=True, label="first stage", lab_dy=0.28)
d.edge("D", "Y", arrow=True, bold=True, label=r"$\tau$", lab_dy=0.28)
# conditioned paths
d.edge("N", "Z", style="--", arrow=True)
d.edge("N", "Y", lw=0.9)
d.edge("B", "Z", lw=0.9)
d.edge("B", "Y", lw=0.9)
d.edge("F", "D", lw=0.9)
d.edge("F", "Y", lw=0.9)
d.save(f"{FIGS}/fig_iv_dag_peer.png")
print("saved fig_iv_dag_peer.png")
