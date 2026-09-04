"""
56_bloc_reach_fullgraph.py
==========================
Bloc-reach for focal AND instrument on the SAME graph = the FULL complete
peerage (Task C fix: previously focal used the active subgraph, instrument
used the full graph). Labels = patriline marriage-blocs (55).

  focal reach   : distinct blocs within k hops on the FULL graph, among kin
                  born <= focal's death (the focal's lifetime network).
  mother/father/mgf : distinct blocs within k hops on the FULL graph, among
                  kin born < focal's birth (pre-natal; preserves exogeneity).
Both on the full graph; the only difference is the born-before reference
(death for the focal, focal-birth for ancestors). n_nodes (size) emitted too.

Sample = anchored males whose lifespan overlaps [1100,1300].
Output (output/): bloc_reach_fullgraph.csv
CLI: python 56_bloc_reach_fullgraph.py
"""
from __future__ import annotations
import csv, time
from pathlib import Path
import pandas as pd
import igraph as ig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
HOPS = [3, 4]; MAXH = 4; LO, HI = 1100, 1300


def to_year(x):
    s = str(x).strip()
    if s in ("", "nan", "NaN"): return None
    try: return int(float(s))
    except Exception: return None


def main():
    t0 = time.time()
    persons = pd.read_csv(OUT / "persons_imputed.csv")
    birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
    death = {r.id: to_year(r.death) for r in persons.itertuples(index=False)}
    sex = dict(zip(persons["id"], persons["sex"]))
    bloc = dict(zip(pd.read_csv(OUT/"patriline_bloc_assignment.csv")["id"],
                    pd.read_csv(OUT/"patriline_bloc_assignment.csv")["dynasty"]))
    pp = pd.read_csv(OUT/"parent_pairs.csv"); spp = pd.read_csv(OUT/"spouse_pairs.csv")
    po = pd.read_csv(OUT/"parent_order.csv")

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
        # distinct blocs / nodes within k hops, kin born < cutoff
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
    df.to_csv(OUT/"bloc_reach_fullgraph.csv", index=False)
    sub = df[df.mother_n_dyn_4hop.notna()]
    print(f"\nwrote bloc_reach_fullgraph.csv ({len(df)} rows, {len(sub)} with mother-IV)")
    print(f"focal bloc-reach 4hop: mean {df.n_dyn_4hop.mean():.1f}  size 4hop mean {df.n_nodes_4hop.mean():.0f}")
    print(f"cor(focal bloc-reach, focal size) @4hop = {df.n_dyn_4hop.corr(df.n_nodes_4hop):.3f}")
    print(f"cor(focal reach, mother reach) @4hop    = {sub.n_dyn_4hop.corr(sub.mother_n_dyn_4hop):.3f}")


if __name__ == "__main__":
    main()
