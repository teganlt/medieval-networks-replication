"""
134_dispute_distance.py
=======================
Where in the kinship graph does territorial conflict live? (8/19)

Sample: distinct dyads of matched nobles co-appearing as principals in
lay-vs-lay secular-territorial dispute letters (221 pairs; earliest letter
year per dyad). Distance = shortest path in the kinship graph (parent-child +
spouse edges), TIME-GATED at the letter year: only nodes born before the
letter year are traversable, so a pair linked only through later descendants
is not counted as close at dispute time. Cap 15 (report capped/unreachable).

Null: for each dyad, 5 random pairs from the matching universe (anchored,
dated, lifespan overlapping [1050,1350]) both alive in the letter year,
distance computed identically -- the benchmark that holds documentation and
era fixed.

Reports: mean/SD/median (dyads vs null), same excluding distance-1 dyads
(parent/child/spouse pairs are plausibly co-parties, not adversaries), the
full distance distribution, and 50-year letter-date buckets.

Out: output/clean_iv/dispute_dyad_distance.csv, output/fig_dispute_distance.png
CLI: python scripts/134_dispute_distance.py
"""
from __future__ import annotations
import random
import sys
from collections import deque
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
CAP = 15
NULL_PER_DYAD = 5
random.seed(42)


def to_year(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def main():
    persons = pd.read_csv(OUT / "persons_imputed.csv", dtype={"id": str})
    pids = list(persons["id"].values)
    fi = {p: i for i, p in enumerate(pids)}
    birth = np.full(len(pids), np.nan)
    death = np.full(len(pids), np.nan)
    for i, r in enumerate(persons.itertuples(index=False)):
        b, d = to_year(r.birth), to_year(r.death)
        if b is not None:
            birth[i] = b
        if d is not None:
            death[i] = d

    ed = []
    for a, b in pd.read_csv(OUT / "parent_pairs.csv", dtype=str).values:
        if a in fi and b in fi:
            ed.append((fi[a], fi[b]))
    seen = set()
    for a, b in pd.read_csv(OUT / "spouse_pairs.csv", dtype=str).values:
        if a in fi and b in fi:
            k = (min(a, b), max(a, b))
            if k not in seen:
                seen.add(k)
                ed.append((fi[a], fi[b]))
    nbrs = [[] for _ in pids]
    for a, b in ed:
        nbrs[a].append(b)
        nbrs[b].append(a)
    print(f"graph: {len(pids):,} nodes, {len(ed):,} edges", flush=True)

    def dist(a, b, year):
        """BFS distance a->b over nodes born < year; CAP+1 if not reached."""
        if a == b:
            return 0
        vis = {a}
        fr = [a]
        d = 0
        while fr and d < CAP:
            d += 1
            nf = []
            for x in fr:
                for u in nbrs[x]:
                    if u in vis or np.isnan(birth[u]) or birth[u] >= year:
                        continue
                    if u == b:
                        return d
                    vis.add(u)
                    nf.append(u)
            fr = nf
        return CAP + 1

    coded = pd.read_csv(OUT / "matched_docs_coded.csv", dtype={"doc_id": str})
    mt = pd.read_csv(OUT / "doc_matches_ai_extracted_high.csv", dtype={"doc_id": str, "person_id": str})
    n_per = mt.groupby("doc_id").person_id.nunique()
    multi = set(n_per[n_per >= 2].index)
    core = coded[coded.doc_id.isin(multi) & (coded.is_dispute == "yes")
                 & (coded.matched_principal == "yes") & (coded.dispute_parties == "lay_v_lay")
                 & (coded.domain == "secular_territorial")]
    yr = dict(zip(core.doc_id, core.year))
    dy = {}
    for doc, ps in mt[mt.doc_id.isin(set(core.doc_id))].groupby("doc_id").person_id.apply(set).items():
        for a, b in combinations(sorted(ps), 2):
            key = (a, b)
            y = to_year(yr.get(doc))
            if y is None:
                continue
            if key not in dy or y < dy[key]:
                dy[key] = y
    print(f"dyads: {len(dy)} (lay_v_lay secular-territorial, earliest letter year)", flush=True)

    nd = pd.read_csv(OUT / "named_dynasty_assignment.csv", dtype=str)
    anch = [fi[p] for p in nd.loc[nd.dynasty.fillna("") != "", "id"] if p in fi]
    anch = [i for i in anch if not np.isnan(birth[i]) and not np.isnan(death[i])
            and birth[i] <= 1350 and death[i] >= 1050]
    anch_b = np.array([birth[i] for i in anch])
    anch_d = np.array([death[i] for i in anch])
    anch = np.array(anch)

    rows = []
    for j, ((a, b), y) in enumerate(sorted(dy.items(), key=lambda kv: kv[1])):
        if a not in fi or b not in fi:
            continue
        rows.append(("dyad", y, dist(fi[a], fi[b], y)))
        alive = anch[(anch_b < y) & (anch_d >= y)]
        for _ in range(NULL_PER_DYAD):
            u, v = random.sample(list(alive), 2)
            rows.append(("null", y, dist(u, v, y)))
        if (j + 1) % 50 == 0:
            print(f"  {j+1}/{len(dy)} dyads done", flush=True)

    df = pd.DataFrame(rows, columns=["kind", "year", "d"])
    df["bucket"] = (df.year // 50) * 50
    df.to_csv(OUT / "clean_iv" / "dispute_dyad_distance.csv", index=False)

    def summ(x, label):
        r = x[x.d <= CAP]
        print(f"{label}: N={len(x)}  reachable={len(r)} ({len(r)/len(x):.0%})  "
              f"mean={r.d.mean():.2f}  sd={r.d.std():.2f}  median={r.d.median():.0f}")
        return r

    print("\n=== overall (distance capped at 15; capped/unreachable excluded from moments) ===")
    dd = summ(df[df.kind == "dyad"], "dyads      ")
    dn = summ(df[df.kind == "null"], "null pairs ")
    print("\nexcluding distance-1 dyads (likely co-parties):")
    summ(df[(df.kind == "dyad") & (df.d > 1)], "dyads d>1  ")

    print("\n=== distance distribution (share of reachable) ===")
    for d in range(1, CAP + 1):
        sh_d = (dd.d == d).mean()
        sh_n = (dn.d == d).mean()
        bar = "#" * int(sh_d * 60)
        print(f"  d={d:2d}  dyads {sh_d:5.1%}  null {sh_n:5.1%}  {bar}")

    print("\n=== by 50-year letter bucket ===")
    for bk, g in dd.groupby("bucket"):
        gn = dn[dn.bucket == bk]
        print(f"  {bk}-{bk+49}: N={len(g):3d}  mean={g.d.mean():.2f}  sd={g.d.std():.2f}  "
              f"median={g.d.median():.0f}  | null mean={gn.d.mean():.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    ax = axes[0]
    ds = np.arange(1, CAP + 1)
    w = 0.4
    ax.bar(ds - w/2, [(dd.d == d).mean() for d in ds], width=w, color="#8c3b3b", label="dispute dyads")
    ax.bar(ds + w/2, [(dn.d == d).mean() for d in ds], width=w, color="#2b6ca3", label="random co-alive pairs")
    ax.set_xlabel("kinship-graph distance (hops, gated at letter year)", fontsize=9)
    ax.set_ylabel("share of reachable pairs", fontsize=9)
    ax.set_title("(a) where territorial conflict lives", fontsize=10, loc="left")
    ax.legend(frameon=False, fontsize=9)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax = axes[1]
    bks = sorted(dd.bucket.unique())
    ax.plot(bks, [dd[dd.bucket == b].d.mean() for b in bks], color="#8c3b3b", lw=2, marker="o", label="dispute dyads")
    ax.plot(bks, [dn[dn.bucket == b].d.mean() for b in bks], color="#2b6ca3", lw=2, marker="o", label="random co-alive pairs")
    ax.set_xlabel("letter date (50-year bucket)", fontsize=9)
    ax.set_ylabel("mean distance", fontsize=9)
    ax.set_title("(b) mean dispute distance over time", fontsize=10, loc="left")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig_dispute_distance.png", dpi=160)
    print("\nwrote fig_dispute_distance.png + dispute_dyad_distance.csv")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
