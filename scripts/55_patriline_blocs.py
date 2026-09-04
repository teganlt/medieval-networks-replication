"""
55_patriline_blocs.py
=====================
Coarsen patrilines into marriage BLOCS (topology-only, no anchoring) -- the
analog of the dynasty->bloc step (stage 15), but starting from patrilines.
Build the weighted patriline-to-patriline MARRIAGE graph (nodes = patrilines,
edge weight = # marriages between them) and community-detect with Louvain
(community_multilevel on the marriage graph -- NOT the person graph, so it
finds intermarrying-patriline blocs, not nuclear families).

Why: patrilines are too fine (inter-patriline marriage ~99% flat; reach==size
cor 0.95). Marriage blocs are coarse enough to (a) show an EMFP exogamy trend
and (b) decouple reach from size. Used as the new label for reach.

Outputs (output/):
  patriline_bloc_assignment.csv   id (person) -> bloc label (schema like
                                  named_dynasty_assignment.csv)
CLI: python 55_patriline_blocs.py [--marriage-lo 800] [--marriage-hi 1500]
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
import igraph as ig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"


def to_year(x):
    s = str(x).strip()
    if s in ("", "nan", "NaN"): return None
    try: return int(float(s))
    except Exception: return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--marriage-lo", type=int, default=800)
    ap.add_argument("--marriage-hi", type=int, default=1500)
    a = ap.parse_args()

    persons = pd.read_csv(OUT / "persons_imputed.csv")
    birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
    plf = pd.read_csv(OUT / "patriline_assignment.csv")
    pl = dict(zip(plf["id"], plf["dynasty"]))
    sp = pd.read_csv(OUT / "spouse_pairs.csv")

    # weighted patriline-marriage edges (couples with mean birth in window)
    w = defaultdict(int)
    for x, y in sp.values:
        bx, by = birth.get(x), birth.get(y)
        if bx is None or by is None: continue
        m = (bx + by) / 2
        if m < a.marriage_lo or m > a.marriage_hi: continue
        px, py = pl.get(x), pl.get(y)
        if px is None or py is None or px == py: continue
        w[(min(px, py), max(px, py))] += 1

    pls = sorted({p for e in w for p in e})
    idx = {p: i for i, p in enumerate(pls)}
    edges = [(idx[u], idx[v]) for (u, v) in w]
    wts = [w[(u, v)] for (u, v) in w]
    g = ig.Graph(n=len(pls), edges=edges); g.es["weight"] = wts
    print(f"patriline-marriage graph: {len(pls):,} patrilines, {len(edges):,} edges, "
          f"{sum(wts):,} marriages")

    comm = g.community_multilevel(weights="weight")
    print(f"Louvain blocs: {len(comm):,}  modularity={comm.modularity:.3f}")
    memb = comm.membership
    pl_to_bloc = {pls[i]: f"B{memb[i]}" for i in range(len(pls))}

    # person -> bloc (patrilines not in any inter-patriline marriage = solo bloc)
    rows = []
    for pid, plab in pl.items():
        rows.append((pid, pl_to_bloc.get(plab, f"solo_{plab}")))
    out = pd.DataFrame(rows, columns=["id", "dynasty"])
    out.to_csv(OUT / "patriline_bloc_assignment.csv", index=False)

    # diagnostics: bloc sizes in patrilines and persons
    bloc_pl = Counter(pl_to_bloc.values())
    persons_per_bloc = Counter(out["dynasty"])
    big = persons_per_bloc.most_common(8)
    print(f"\nblocs (non-solo): {len(bloc_pl):,}")
    print(f"  patrilines/bloc: max {max(bloc_pl.values())}, "
          f"median {pd.Series(list(bloc_pl.values())).median():.0f}")
    print(f"  largest blocs by persons: {[(b, n) for b, n in big]}")
    nsolo = sum(1 for v in out['dynasty'] if v.startswith('solo_'))
    print(f"  persons in solo (unmarried-line) blocs: {nsolo:,} of {len(out):,}")
    print(f"\nWrote patriline_bloc_assignment.csv")


if __name__ == "__main__":
    main()
