"""
86_complementarity_iv_saturate_build.py
=======================================
Augment 84's IV frame with the focal's OWN network position, richly, to test
exclusion concern (i): is focal bloc reach (n_dyn_4hop) a SUFFICIENT statistic
for the focal's network -> court use? If the 2SLS is stable as we add the
focal's 1-hop bloc breadth (the instrument's direct analog), degree,
concentration (HHI), and multi-hop reach (3/5/6), the instrument (peer breadth)
is not just proxying the focal's own network position -> exclusion (i) closed.

Reuses 84's reg_complementarity_iv_df.csv (peer rates + instrument), adds the
focal-network controls computed here. Writes reg_complementarity_iv_df_sat.csv.
CLI: python 86_complementarity_iv_saturate_build.py
"""
from __future__ import annotations
import time
from pathlib import Path
import igraph as ig
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"


def to_year(x):
    try: return int(float(x))
    except (TypeError, ValueError): return None


def main():
    t0 = time.time()
    base = pd.read_csv(OUT/"clean_iv"/"reg_complementarity_iv_df.csv", dtype={"person_id": str})
    coh = pd.read_csv(OUT/"bloc_cohesion_fullgraph.csv", dtype={"person_id": str})[["person_id", "death", "hhi_4hop"]]
    coh["person_id"] = coh.person_id.astype(str)
    base = base.merge(coh, on="person_id", how="left")
    persons = pd.read_csv(OUT/"persons_imputed.csv", dtype={"id": str})
    birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
    bloc = dict(zip(*[pd.read_csv(OUT/"patriline_bloc_assignment.csv", dtype=str)[c] for c in ("id", "dynasty")]))
    pp = pd.read_csv(OUT/"parent_pairs.csv", dtype=str); sp = pd.read_csv(OUT/"spouse_pairs.csv", dtype=str)
    pids = list(persons["id"].values); fi = {p: i for i, p in enumerate(pids)}
    ed = [(fi[a], fi[b]) for a, b in pp.values if a in fi and b in fi]
    seen = set()
    for a, b in sp.values:
        if a in fi and b in fi:
            k = (min(a, b), max(a, b))
            if k not in seen: seen.add(k); ed.append((fi[a], fi[b]))
    G = ig.Graph(n=len(pids), edges=ed); nbrs = [set(G.neighbors(v)) for v in range(G.vcount())]
    barr = np.array([birth.get(pids[i], np.nan) for i in range(G.vcount())])
    bloc_arr = [bloc.get(pids[i], "") for i in range(G.vcount())]
    print(f"graph built ({time.time()-t0:.0f}s)", flush=True)

    def dc(s): return len({bloc_arr[u] for u in s if bloc_arr[u]})

    def fmulti(focal, death):
        if focal not in fi: return None
        ti = fi[focal]; cut = (death + 1) if not np.isnan(death) else np.inf
        one = [u for u in nbrs[ti] if not np.isnan(barr[u]) and barr[u] < cut]
        vis = {ti} | set(one); fr = set(one); acc = set(one)
        out = {1: dc(acc)}
        for h in range(2, 7):
            nf = set()
            for x in fr:
                for u in nbrs[x]:
                    if u in vis or np.isnan(barr[u]) or barr[u] >= cut: continue
                    vis.add(u); nf.add(u)
            acc |= nf; fr = nf; out[h] = dc(acc)
            if not fr:
                for hh in range(h+1, 7): out[hh] = out[h]
                break
        return out, len(nbrs[ti])

    rows = []
    for pid, dth in zip(base.person_id.values, base.death.values):
        r = fmulti(pid, dth)
        if r is None:
            rows.append((np.nan,)*5); continue
        o, deg = r
        rows.append((o[1], o[3], o[5], o[6], deg))
    base["focal_r1"] = [x[0] for x in rows]; base["focal_r3"] = [x[1] for x in rows]
    base["focal_r5"] = [x[2] for x in rows]; base["focal_r6"] = [x[3] for x in rows]
    base["focal_ldeg"] = np.log1p([x[4] for x in rows])
    base["focal_hhi"] = base["hhi_4hop"].fillna(base["hhi_4hop"].median())
    print(f"  sanity cor(focal_r4_recomputed? n_dyn_4hop vs focal_r5..): n_dyn_4hop mean={base.n_dyn_4hop.mean():.1f}, "
          f"focal_r3={base.focal_r3.mean():.1f} focal_r5={base.focal_r5.mean():.1f} focal_r6={base.focal_r6.mean():.1f} "
          f"focal_r1={base.focal_r1.mean():.1f}", flush=True)
    base.to_csv(OUT/"clean_iv"/"reg_complementarity_iv_df_sat.csv", index=False)
    print(f"wrote reg_complementarity_iv_df_sat.csv N={len(base)}", flush=True)


if __name__ == "__main__":
    main()
