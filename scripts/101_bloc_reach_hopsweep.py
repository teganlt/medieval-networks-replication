"""
101_bloc_reach_hopsweep.py
==========================
Hop sweep of 56_bloc_reach_fullgraph.py: identical graph, sample, and
temporal-BFS logic, but carries the bloc-reach / size counts at EVERY hop
h in 3..6 for the focal (lifetime cutoff) AND mother/father/mgf (pre-natal
cutoff).  Backs the paper's "5- and 6-hop radii" robustness claim.

  focal reach   : distinct blocs within h hops on the FULL graph, among kin
                  born <= focal's death (the focal's lifetime network).
  mother/father/mgf : distinct blocs within h hops on the FULL graph, among
                  kin born < focal's birth (pre-natal; preserves exogeneity).

Sample = anchored males whose lifespan overlaps [1100,1300]  (same as 56).
Output (output/): bloc_reach_hopsweep.csv
CLI: python 101_bloc_reach_hopsweep.py
"""
from __future__ import annotations
import time
from pathlib import Path
import pandas as pd
import igraph as ig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
HOPS = [3, 4, 5, 6]; MAXH = 6; LO, HI = 1100, 1300


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

    # ---- speedups (pure precomputation; BFS logic below identical to 56) ----
    adj = G.get_adjlist()                                    # list-of-lists adjacency
    birth_v = [birth.get(p) for p in pids]                   # birth year by vertex idx
    bloc_v = [bloc.get(p) for p in pids]                     # bloc label by vertex idx

    plk = {r.child_id: (r.parent0_id, r.parent1_id) for r in po.itertuples(index=False)}
    def parents(c):
        if c not in plk: return None, None
        p0, p1 = plk[c]
        mo = p0 if sex.get(p0)=="F" else (p1 if sex.get(p1)=="F" else None)
        fa = p0 if sex.get(p0)=="M" else (p1 if sex.get(p1)=="M" else None)
        return mo, fa

    def scores(tgt, cutoff):
        # distinct blocs / nodes within h hops, kin born < cutoff (temporal BFS,
        # per-hop frontier expansion under the birth cutoff -- exactly as in 56)
        if tgt is None or tgt not in fi or cutoff is None: return None
        ti = fi[tgt]
        one = [u for u in adj[ti]
               if birth_v[u] is not None and birth_v[u] < cutoff]
        vis = {ti} | set(one); fr = set(one); lv = [None, set(one)]
        for h in range(2, MAXH+1):
            nf = set()
            for x in fr:
                for u in adj[x]:
                    if u in vis: continue
                    b = birth_v[u]
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
                out[f"n_dyn_{k}hop"] = len({bloc_v[u] for u in acc
                                            if bloc_v[u] is not None})
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
        if (i+1)%200==0: print(f"  {i+1}/{len(cand)} ({time.time()-t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT/"bloc_reach_hopsweep.csv", index=False)
    sub = df[df.mother_n_dyn_4hop.notna()]
    print(f"\nwrote bloc_reach_hopsweep.csv ({len(df)} rows, {len(sub)} with mother-IV)")
    for k in HOPS:
        print(f"hop {k}: focal reach mean {df[f'n_dyn_{k}hop'].mean():6.1f}  size mean {df[f'n_nodes_{k}hop'].mean():8.0f}"
              f"  cor(reach,size) {df[f'n_dyn_{k}hop'].corr(df[f'n_nodes_{k}hop']):.3f}"
              f"  cor(focal,mother reach) {sub[f'n_dyn_{k}hop'].corr(sub[f'mother_n_dyn_{k}hop']):.3f}")


if __name__ == "__main__":
    main()
