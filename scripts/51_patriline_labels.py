"""
51_patriline_labels.py
======================
Topology-only replacement for the hand-curated 21-dynasty labels: the
connected components of the FATHER->child graph = patrilineal houses
(male-line descent; daughters are leaves in their father's tree, their
children join the husband's line, so marriages never merge lines -> the
graph is a forest, components are clean patrilines).

Writes patriline_assignment.csv (id, dynasty=patriline id) in the same
schema as named_dynasty_assignment.csv, so it drops straight into the
existing stage 17/18 via --labels.  Each person gets a patriline id
("PL<root>"); this is strictly finer than the 21 dynasties and requires
no anchoring.

CLI: python 51_patriline_labels.py
"""
from __future__ import annotations
import csv
from collections import Counter
from pathlib import Path
import pandas as pd
import igraph as ig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"


def main():
    persons = pd.read_csv(OUT / "persons_imputed.csv")
    sex = dict(zip(persons["id"], persons["sex"]))
    po = pd.read_csv(OUT / "parent_order.csv")

    all_ids = list(persons["id"].values)
    idx = {p: i for i, p in enumerate(all_ids)}

    # father->child edges (father = the male parent in parent_order)
    edges = []
    n_father = 0
    for row in po.itertuples(index=False):
        c = row.child_id
        p0, p1 = row.parent0_id, row.parent1_id
        father = None
        if isinstance(p0, str) and sex.get(p0) == "M":
            father = p0
        elif isinstance(p1, str) and sex.get(p1) == "M":
            father = p1
        if father is not None and father in idx and c in idx:
            edges.append((idx[father], idx[c])); n_father += 1

    G = ig.Graph(n=len(all_ids), edges=edges, directed=False)
    comp = G.connected_components(mode="weak")
    membership = comp.membership
    sizes = comp.sizes()

    print(f"persons: {len(all_ids):,} | father-child edges: {n_father:,}")
    print(f"patriline components: {len(sizes):,}")
    szc = Counter(sizes)
    print(f"  singletons (size 1): {szc.get(1,0):,}")
    print(f"  size>=2: {sum(1 for s in sizes if s>=2):,}")
    ss = sorted(sizes, reverse=True)
    print(f"  largest 5 patrilines: {ss[:5]}")
    print(f"  largest as % of all persons: {100*ss[0]/len(all_ids):.2f}%")
    print(f"  median (size>=2): {pd.Series([s for s in sizes if s>=2]).median():.0f}")

    # label each person; write CSV (schema matches named_dynasty_assignment)
    labels = [f"PL{membership[idx[p]]}" for p in all_ids]
    out = pd.DataFrame({"id": all_ids, "dynasty": labels})
    out.to_csv(OUT / "patriline_assignment.csv", index=False)
    print(f"\nWrote patriline_assignment.csv ({len(out):,} rows)")

    # sanity: how many distinct patrilines does each 21-dynasty span?
    nd = pd.read_csv(OUT / "named_dynasty_assignment.csv")
    nd = nd[nd["dynasty"].notna() & (nd["dynasty"] != "")]
    pl = dict(zip(all_ids, labels))
    nd["pl"] = nd["id"].map(pl)
    span = nd.groupby("dynasty")["pl"].nunique().sort_values(ascending=False)
    print("\ndistinct patrilines spanned by each 21-dynasty (top/bottom):")
    print(span.head(6).to_string())
    print("  ...")
    print(span.tail(3).to_string())
    print(f"  -> patriline is {span.sum()} distinct lines across the 21 dynasties "
          f"(mean {span.mean():.0f}/dynasty)")


if __name__ == "__main__":
    main()
