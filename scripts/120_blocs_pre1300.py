"""
120_blocs_pre1300.py
====================
Referee robustness: the Louvain marriage-bloc partition (55_patriline_blocs.py)
weights patriline-marriage edges using couples with mean birth year in
[800,1500], so a 12th-century noble's reach counts bloc LABELS partly defined
by later marriages.  Rebuild the partition using ONLY marriages with mean
couple birth year in [800,1300] and recompute the bloc reach with the new
labels, so 121_pre1300_iv.R can show the baseline is unchanged.

Three parts (pipelines copied verbatim from 55 / 56, only the marriage window
and the label file differ):
  A. 55's pipeline with --marriage-hi 1300 (same defaults otherwise: no seed
     set, default Louvain resolution, community_multilevel on the weighted
     patriline-marriage graph).
       -> output/patriline_bloc_assignment_pre1300.csv  (schema: id,dynasty)
  B. Partition similarity vs patriline_bloc_assignment.csv:
       - adjusted Rand index on all persons covered by both (contingency form)
       - share of the estimation-sample focals (bloc_reach_fullgraph.csv with
         mother IV) whose bloc-MATES set is unchanged (exact, via joint counts)
  C. 56's temporal-BFS reach (focal lifetime / ancestor pre-natal, FULL graph)
     with the NEW labels, HOPS=[4] only.
       -> output/bloc_reach_pre1300.csv
     plus cor(new reach, old reach) on the estimation sample.

CLI: python 120_blocs_pre1300.py [--marriage-lo 800] [--marriage-hi 1300]
"""
from __future__ import annotations
import argparse, time
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


def comb2(n):
    return n * (n - 1) // 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--marriage-lo", type=int, default=800)
    ap.add_argument("--marriage-hi", type=int, default=1300)
    a = ap.parse_args()
    t0 = time.time()

    persons = pd.read_csv(OUT / "persons_imputed.csv")
    birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
    death = {r.id: to_year(r.death) for r in persons.itertuples(index=False)}
    sex = dict(zip(persons["id"], persons["sex"]))
    plf = pd.read_csv(OUT / "patriline_assignment.csv")
    pl = dict(zip(plf["id"], plf["dynasty"]))
    sp = pd.read_csv(OUT / "spouse_pairs.csv")

    # ---------------- A. 55's pipeline, marriage window capped at 1300 ------
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
    print(f"patriline-marriage graph [{a.marriage_lo},{a.marriage_hi}]: "
          f"{len(pls):,} patrilines, {len(edges):,} edges, {sum(wts):,} marriages")

    comm = g.community_multilevel(weights="weight")
    print(f"Louvain blocs: {len(comm):,}  modularity={comm.modularity:.3f}")
    memb = comm.membership
    pl_to_bloc = {pls[i]: f"B{memb[i]}" for i in range(len(pls))}

    rows = []
    for pid, plab in pl.items():
        rows.append((pid, pl_to_bloc.get(plab, f"solo_{plab}")))
    newas = pd.DataFrame(rows, columns=["id", "dynasty"])
    newas.to_csv(OUT / "patriline_bloc_assignment_pre1300.csv", index=False)

    bloc_pl = Counter(pl_to_bloc.values())
    persons_per_bloc = Counter(newas["dynasty"])
    big = persons_per_bloc.most_common(8)
    print(f"blocs (non-solo): {len(bloc_pl):,}")
    print(f"  patrilines/bloc: max {max(bloc_pl.values())}, "
          f"median {pd.Series(list(bloc_pl.values())).median():.0f}")
    print(f"  largest blocs by persons: {[(b, n) for b, n in big]}")
    nsolo = sum(1 for v in newas['dynasty'] if v.startswith('solo_'))
    print(f"  persons in solo (unmarried-line) blocs: {nsolo:,} of {len(newas):,}")
    print(f"Wrote patriline_bloc_assignment_pre1300.csv ({time.time()-t0:.0f}s)\n")

    # ---------------- B. partition similarity vs the [800,1500] labels ------
    oldas = pd.read_csv(OUT / "patriline_bloc_assignment.csv")
    both = oldas.merge(newas, on="id", suffixes=("_old", "_new"))
    n = len(both)
    print(f"persons covered by both partitions: {n:,}")

    joint = both.groupby(["dynasty_old", "dynasty_new"]).size()
    a_i = both.groupby("dynasty_old").size()
    b_j = both.groupby("dynasty_new").size()
    sum_ij = int(sum(comb2(int(v)) for v in joint.values))
    sum_a = int(sum(comb2(int(v)) for v in a_i.values))
    sum_b = int(sum(comb2(int(v)) for v in b_j.values))
    ctot = comb2(n)
    exp_idx = sum_a * sum_b / ctot
    max_idx = (sum_a + sum_b) / 2
    ari = (sum_ij - exp_idx) / (max_idx - exp_idx)
    print(f"adjusted Rand index (all {n:,} persons): {ari:.4f}")
    # raw pairwise agreement (same-bloc/diff-bloc concordance) for intuition
    agree = (sum_ij + (ctot - sum_a - sum_b + sum_ij)) / ctot
    print(f"raw pairwise agreement: {agree:.6f}")

    # estimation-sample focals whose bloc-mates set is unchanged
    br_old = pd.read_csv(OUT / "bloc_reach_fullgraph.csv")
    est = br_old[br_old.mother_n_dyn_4hop.notna()]["person_id"].tolist()
    old_lab = dict(zip(both["id"], both["dynasty_old"]))
    new_lab = dict(zip(both["id"], both["dynasty_new"]))
    n_old = a_i.to_dict(); n_new = b_j.to_dict(); n_joint = joint.to_dict()
    same = missing = 0
    for f in est:
        lo, ln = old_lab.get(f), new_lab.get(f)
        if lo is None or ln is None: missing += 1; continue
        j = n_joint.get((lo, ln), 0)
        if j == n_old[lo] == n_new[ln]: same += 1
    print(f"estimation-sample focals (N={len(est):,}): bloc-mates set "
          f"unchanged for {same:,} ({100*same/len(est):.1f}%)"
          + (f"  [{missing} unlabeled]" if missing else ""))
    print(f"({time.time()-t0:.0f}s)\n")

    # ---------------- C. 56's reach pipeline with the NEW labels ------------
    HOPS = [4]; MAXH = 4; LO, HI = 1100, 1300
    bloc = dict(zip(newas["id"], newas["dynasty"]))
    pp = pd.read_csv(OUT / "parent_pairs.csv"); spp = sp
    po = pd.read_csv(OUT / "parent_order.csv")

    pids = list(persons["id"].values); fi = {p: i for i, p in enumerate(pids)}
    ed = [(fi[p], fi[c]) for p, c in pp.values if p in fi and c in fi]
    seen = set()
    for x, y in spp.values:
        if x in fi and y in fi:
            k = (min(x, y), max(x, y))
            if k not in seen: seen.add(k); ed.append((fi[x], fi[y]))
    G = ig.Graph(n=len(pids), edges=ed); G.vs["pid"] = pids
    print(f"full graph {G.vcount():,} nodes {G.ecount():,} edges ({time.time()-t0:.0f}s)", flush=True)

    plk = {r.child_id: (r.parent0_id, r.parent1_id) for r in po.itertuples(index=False)}
    def parents(c):
        if c not in plk: return None, None
        p0, p1 = plk[c]
        mo = p0 if sex.get(p0)=="F" else (p1 if sex.get(p1)=="F" else None)
        fa = p0 if sex.get(p0)=="M" else (p1 if sex.get(p1)=="M" else None)
        return mo, fa

    def scores(tgt, cutoff):
        if tgt is None or tgt not in fi or cutoff is None: return None
        ti = fi[tgt]
        one = [u for u in G.neighbors(ti)
               if birth.get(G.vs[u]["pid"]) is not None and birth[G.vs[u]["pid"]] < cutoff]
        vis = {ti} | set(one); fr = set(one); lv = [None, set(one)]
        for h in range(2, MAXH+1):
            nf = set()
            for x in fr:
                for u in G.neighbors(x):
                    if u in vis: continue
                    b = birth.get(G.vs[u]["pid"])
                    if b is None or b >= cutoff: continue
                    vis.add(u); nf.add(u)
            lv.append(nf); fr = nf
            if not fr:
                while len(lv) <= MAXH: lv.append(set())
                break
        out = {"pre_deg": len(one)}; acc = {ti}
        for k in range(1, MAXH+1):
            acc |= lv[k]
            if k in HOPS:
                out[f"n_dyn_{k}hop"] = len({bloc.get(G.vs[u]["pid"]) for u in acc
                                            if bloc.get(G.vs[u]["pid"]) is not None})
                out[f"n_nodes_{k}hop"] = len(acc) - 1
        return out

    nd = pd.read_csv(OUT/"named_dynasty_assignment.csv")
    anch = set(nd.loc[nd["dynasty"].notna() & (nd["dynasty"]!=""), "id"])
    cand = [p for p in anch if sex.get(p)=="M" and birth.get(p) is not None
            and death.get(p) is not None and birth[p]<=HI and death[p]>=LO]
    print(f"{len(cand):,} sample focals ({time.time()-t0:.0f}s)", flush=True)
    rows = []
    for i, f in enumerate(cand):
        fb, fd = birth.get(f), death.get(f)
        mo, fa = parents(f); mgf = None
        if mo is not None and mo in plk:
            m0, m1 = plk[mo]; mgf = m0 if sex.get(m0)=="M" else (m1 if sex.get(m1)=="M" else None)
        rec = {"person_id": f, "bloc": bloc.get(f), "birth": fb, "death": fd, "sex": "M",
               "deg": G.degree(fi[f])}
        sf = scores(f, (fd + 1) if fd is not None else None)   # focal lifetime
        if sf:
            for k in HOPS: rec[f"n_dyn_{k}hop"]=sf[f"n_dyn_{k}hop"]; rec[f"n_nodes_{k}hop"]=sf[f"n_nodes_{k}hop"]
        for who, t in (("mother",mo),("father",fa),("mgf",mgf)):
            s = scores(t, fb)                                   # ancestor pre-natal
            if s:
                rec[f"{who}_pre_deg"]=s["pre_deg"]
                for k in HOPS: rec[f"{who}_n_dyn_{k}hop"]=s[f"n_dyn_{k}hop"]; rec[f"{who}_n_nodes_{k}hop"]=s[f"n_nodes_{k}hop"]
        rows.append(rec)
        if (i+1)%500==0: print(f"  {i+1}/{len(cand)} ({time.time()-t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT/"bloc_reach_pre1300.csv", index=False)
    sub = df[df.mother_n_dyn_4hop.notna()]
    print(f"\nwrote bloc_reach_pre1300.csv ({len(df)} rows, {len(sub)} with mother-IV)")
    print(f"focal bloc-reach 4hop: mean {df.n_dyn_4hop.mean():.1f}  size 4hop mean {df.n_nodes_4hop.mean():.0f}")
    print(f"cor(focal bloc-reach, focal size) @4hop = {df.n_dyn_4hop.corr(df.n_nodes_4hop):.3f}")
    print(f"cor(focal reach, mother reach) @4hop    = {sub.n_dyn_4hop.corr(sub.mother_n_dyn_4hop):.3f}")

    # cor(new reach, old reach) on the estimation sample
    cmp = sub[["person_id", "n_dyn_4hop", "mother_n_dyn_4hop"]].merge(
        br_old[br_old.mother_n_dyn_4hop.notna()][
            ["person_id", "n_dyn_4hop", "mother_n_dyn_4hop"]],
        on="person_id", suffixes=("_new", "_old"))
    print(f"\nestimation-sample overlap new/old: {len(cmp):,}")
    print(f"cor(new focal reach, old focal reach)   @4hop = "
          f"{cmp.n_dyn_4hop_new.corr(cmp.n_dyn_4hop_old):.4f}")
    print(f"cor(new mother reach, old mother reach) @4hop = "
          f"{cmp.mother_n_dyn_4hop_new.corr(cmp.mother_n_dyn_4hop_old):.4f}")
    print(f"done ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
