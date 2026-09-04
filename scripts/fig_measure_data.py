import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGS = ROOT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 12, "font.family": "serif", "figure.facecolor": "white",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": False, "savefig.dpi": 200, "savefig.bbox": "tight",
})
INK = "#222222"; MUT = "#9e9e9e"; ACC = "#1f4e79"; LGT = "#cfcfcf"

# ---------- FIG: reach vs size decoupling ----------
d = pd.read_csv(f"{ROOT}/output/bloc_reach_fullgraph.csv")
d = d[(d.sex == "M") & d.mother_n_dyn_4hop.notna()].copy()
r = np.corrcoef(d.n_dyn_4hop, d.n_nodes_4hop)[0, 1]
fig, ax = plt.subplots(figsize=(6.2, 4.6))
rng = np.random.default_rng(7)
ax.scatter(d.n_nodes_4hop, d.n_dyn_4hop + rng.uniform(-0.28, 0.28, len(d)),
           s=9, c=INK, alpha=0.30, edgecolors="none")
ax.set_xlabel("network size  (people within 4 hops)")
ax.set_ylabel("kin-reach  (distinct blocs within 4 hops)")
ax.text(0.96, 0.07, f"$r = {r:.2f}$", transform=ax.transAxes, ha="right", fontsize=14)
ax.set_ylim(bottom=-0.5)
fig.savefig(f"{FIGS}/fig_reach_vs_size.png"); plt.close(fig)
print("reach/size N", len(d), "cor", round(r, 3))

# ---------- FIG: outcome domain composition ----------
dc = pd.read_csv(f"{ROOT}/output/matched_docs_coded.csv")
biv = pd.read_csv(f"{ROOT}/output/clean_iv/reg_clean_bloc_iv.csv").set_index("domain")
order = ["secular_territorial", "ecclesiastical_appointments", "ecclesiastical_property",
         "crusade", "excommunication", "other", "marriage", "inheritance"]
lab = {"secular_territorial": "secular-territorial", "ecclesiastical_appointments": "eccl. appointments",
       "ecclesiastical_property": "eccl. property", "crusade": "crusade",
       "excommunication": "excommunication", "other": "other",
       "marriage": "marriage", "inheritance": "inheritance"}
ct = dc.groupby(["domain", "is_dispute"]).size().unstack(fill_value=0).reindex(order)
npos = biv["npos"].reindex(order)
y = np.arange(len(order))[::-1]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.8, 4.8), gridspec_kw={"width_ratios": [1.5, 1]})
a1.barh(y, ct["yes"], color=ACC, label="dispute", height=0.7)
a1.barh(y, ct["no"], left=ct["yes"], color=LGT, label="non-dispute", height=0.7)
a1.set_yticks(y); a1.set_yticklabels([lab[o] for o in order])
a1.set_xlabel("papal documents (1100--1300)")
a1.legend(frameon=False, loc="lower right", fontsize=10)
a1.set_title("(a) coded documents, by domain", fontsize=11, loc="left")
for yi, o in zip(y, order):
    a1.text(ct.loc[o].sum() + 15, yi, f"{int(ct.loc[o].sum())}", va="center", fontsize=9, color=INK)
a1.set_xlim(right=ct.sum(axis=1).max() * 1.12)
cols = [ACC if o == "secular_territorial" else MUT for o in order]
a2.barh(y, npos.values, color=cols, height=0.7)
a2.set_yticks(y); a2.set_yticklabels([])
a2.set_xlabel("nobles appearing ($N{=}2{,}195$)")
a2.set_title("(b) focal-level outcome, by domain", fontsize=11, loc="left")
for yi, o in zip(y, order):
    a2.text(npos[o] + 2, yi, f"{int(npos[o])}", va="center", fontsize=9, color=INK)
a2.set_xlim(right=npos.max() * 1.15)
fig.savefig(f"{FIGS}/fig_domain_distribution.png"); plt.close(fig)
print("domain fig done")
print("ALL DONE")
