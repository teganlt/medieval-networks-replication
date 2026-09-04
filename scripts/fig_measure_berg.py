import pandas as pd, numpy as np, igraph as ig, collections, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.lines import Line2D

from pathlib import Path

R = Path(__file__).resolve().parent.parent
FIGS = R / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "figure.facecolor": "white", "savefig.dpi": 300, "savefig.bbox": "tight"})
INK = "#222222"; EDGE = "#b9b9b9"
BC = {"B3": "#1f4e79", "B0": "#b07d2b", "B2": "#4a7c59"}   # bloc -> color
OTHER = "#8a8a8a"
AD = "p60458.htm#i604577"; DEATH = 1296

pp = pd.read_csv(f"{R}/output/parent_pairs.csv"); sp = pd.read_csv(f"{R}/output/spouse_pairs.csv")
pers = pd.read_csv(f"{R}/output/persons_imputed.csv").set_index("id")
pl = pd.read_csv(f"{R}/output/patriline_assignment.csv").set_index("id")["dynasty"].to_dict()
pb = pd.read_csv(f"{R}/output/patriline_bloc_assignment.csv").set_index("id")["dynasty"].to_dict()
sex = pers["sex"].to_dict(); birth = pers["birth"].to_dict()

verts = sorted(set(pp.parent_id) | set(pp.child_id) | set(sp.a) | set(sp.b)); vi = {v: i for i, v in enumerate(verts)}
E = [(vi[p], vi[c]) for p, c in zip(pp.parent_id, pp.child_id)] + [(vi[a], vi[b]) for a, b in zip(sp.a, sp.b)]
G = ig.Graph(n=len(verts), edges=E, directed=False); G.simplify()

fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(14, 5.0))
for ax in (a1, a2, a3):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal"); ax.axis("off")

def dot(ax, x, y, c, r=0.02, z=3, ec="white", lw=0.8):
    ax.add_patch(plt.Circle((x, y), r, facecolor=c, edgecolor=ec, lw=lw, zorder=z))

# ---------------- panel (a): patriline window ----------------
fc = [(p, c) for p, c in zip(pp.parent_id, pp.child_id)
      if sex.get(p) == "M" and pl.get(p) == "PL1385" and pl.get(c) == "PL1385"]
adj = collections.defaultdict(set)
for p, c in fc: adj[p].add(c); adj[c].add(p)
seen = {AD: 0}; q = collections.deque([AD])
while q:
    u = q.popleft()
    if seen[u] >= 3: continue
    for w in adj[u]:
        if w not in seen: seen[w] = seen[u] + 1; q.append(w)
W = set(seen)
wfc = [(p, c) for p, c in fc if p in W and c in W]
# clean tree layout (Reingold-Tilford) on the directed father->child window
Wl = list(W); widx = {n: i for i, n in enumerate(Wl)}
Gd = ig.Graph(n=len(Wl), edges=[(widx[p], widx[c]) for p, c in wfc], directed=True)
roots = [widx[n] for n in Wl if Gd.degree(widx[n], mode="in") == 0]
lay = Gd.layout_reingold_tilford(mode="out", root=roots)
cx0 = [lay[i][0] for i in range(len(Wl))]; cy0 = [lay[i][1] for i in range(len(Wl))]
xlo, xhi, ylo2, yhi2 = min(cx0), max(cx0), min(cy0), max(cy0)
xx = {n: 0.14 + 0.72 * (lay[widx[n]][0] - xlo) / (xhi - xlo + 1e-9) for n in W}
yy = {n: 0.84 - 0.72 * (lay[widx[n]][1] - ylo2) / (yhi2 - ylo2 + 1e-9) for n in W}
for p, c in wfc:
    a1.plot([xx[p], xx[c]], [yy[p], yy[c]], color=EDGE, lw=1.4, zorder=1)
for n in W:
    dot(a1, xx[n], yy[n], BC["B3"], r=0.026 if n == AD else 0.02,
        ec=INK if n == AD else "white", lw=1.6 if n == AD else 0.8, z=4 if n == AD else 3)
a1.text(xx[AD] + 0.055, yy[AD], "Adolf VII", ha="left", va="center", fontsize=9, color=INK, bbox=dict(fc="white", ec="none", alpha=0.85, pad=1), zorder=6)
a1.set_title("(a) his patriline", fontsize=13)

# ---------------- panel (b): the bloc ----------------
pm = collections.Counter()
for x, y in zip(sp.a, sp.b):
    px, py = pl.get(x), pl.get(y)
    if px and py and px != py: pm[tuple(sorted((px, py)))] += 1
nbrs = sorted([(k[1] if k[0] == "PL1385" else k[0], w) for k, w in pm.items() if "PL1385" in k],
              key=lambda t: -t[1])[:11]
plbloc = {}
for k, v in pl.items(): plbloc.setdefault(v, pb.get(k))
plsize = collections.Counter(pl.values())
nodesB = ["PL1385"] + [n for n, _ in nbrs]
ang = np.linspace(0, 2 * np.pi, len(nbrs), endpoint=False)
pos = {"PL1385": (0.5, 0.52)}
for (n, _), t in zip(nbrs, ang):
    pos[n] = (0.5 + 0.33 * np.cos(t), 0.52 + 0.33 * np.sin(t))
b3 = [n for n in nodesB if plbloc.get(n) == "B3"]
xs = [pos[n][0] for n in b3]; ysb = [pos[n][1] for n in b3]
a2.add_patch(Ellipse((np.mean(xs), np.mean(ysb)), 0.82, 0.82, facecolor=BC["B3"], alpha=0.08,
                     edgecolor=BC["B3"], lw=1.1, zorder=0))
for (n, w) in nbrs:
    a2.plot([pos["PL1385"][0], pos[n][0]], [pos["PL1385"][1], pos[n][1]],
            color=EDGE, lw=0.8 + 0.55 * w, zorder=1)
for n in nodesB:
    c = BC.get(plbloc.get(n), OTHER)
    rr = 0.018 + 0.010 * np.log1p(plsize[n])
    dot(a2, *pos[n], c, r=rr, ec=INK if n == "PL1385" else "white", lw=1.6 if n == "PL1385" else 0.8,
        z=5 if n == "PL1385" else 3)
a2.set_title("(b) his bloc", fontsize=13)
a2.legend(handles=[Line2D([0], [0], marker='o', color='w', markerfacecolor=BC["B3"], ms=9, label="bloc B3"),
                   Line2D([0], [0], marker='o', color='w', markerfacecolor=BC["B2"], ms=9, label="other bloc")],
          loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, frameon=False,
          fontsize=9, handletextpad=0.2, columnspacing=1.2)

# ---------------- panel (c): 4-hop neighborhood ----------------
nb = [u for u in G.neighborhood(vi[AD], order=4) if u != vi[AD]]
names = [verts[u] for u in nb]
keep = [n for n in names if birth.get(n, 9999) <= DEATH]
dvec = G.distances(source=vi[AD], target=[vi[n] for n in keep])[0]
dist = {n: int(d) for n, d in zip(keep, dvec)}
blc = {n: pb.get(n, "?") for n in keep}
cx, cy = 0.5, 0.53
for rr in (0.12, 0.24, 0.35, 0.45):
    a3.add_patch(plt.Circle((cx, cy), rr, fill=False, ls=(0, (2, 4)), lw=0.7, ec="#dddddd", zorder=0))
Rr = {1: 0.12, 2: 0.24, 3: 0.35, 4: 0.45}
pos3 = {}
for d in (1, 2, 3, 4):
    ring = sorted([n for n in keep if dist[n] == d], key=lambda z: blc[z])
    for k, n in enumerate(ring):
        t = 2 * np.pi * k / max(1, len(ring)) + 0.5 * d
        pos3[n] = (cx + Rr[d] * np.cos(t), cy + Rr[d] * np.sin(t))
kset = set(keep)
drawn = set()
for n in keep:
    for u in G.neighbors(vi[n]):
        nm = verts[u]
        if nm in kset and (nm, n) not in drawn:
            drawn.add((n, nm))
            a3.plot([pos3[n][0], pos3[nm][0]], [pos3[n][1], pos3[nm][1]], color=EDGE, lw=0.4, alpha=0.22, zorder=1)
    if vi[AD] in G.neighbors(vi[n]):
        a3.plot([cx, pos3[n][0]], [cy, pos3[n][1]], color=EDGE, lw=0.4, alpha=0.22, zorder=1)
for n in keep:
    dot(a3, *pos3[n], BC.get(blc[n], OTHER), r=0.016, z=3)
dot(a3, cx, cy, INK, r=0.026, z=6, ec="white", lw=1.2)
a3.text(cx, cy - 0.062, "Adolf VII", ha="center", va="top", fontsize=8.5, color=INK, zorder=7, bbox=dict(fc="white", ec="none", alpha=0.85, pad=1))
a3.set_title("(c) his 4-hop neighborhood", fontsize=13)
from collections import Counter
cnt = Counter(blc[n] for n in keep)
a3.legend(handles=[Line2D([0], [0], marker='o', color='w', markerfacecolor=BC.get(b, OTHER), ms=9,
                          label=f"{b} ({cnt[b]})") for b in ["B3", "B0", "B2"]],
          loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=3, frameon=False,
          fontsize=9, handletextpad=0.2, columnspacing=1.2)

fig.savefig(f"{FIGS}/fig_reach_berg.png"); plt.close(fig)
print("berg fig done | 4hop kept:", len(keep), "| blocs:", dict(cnt))
