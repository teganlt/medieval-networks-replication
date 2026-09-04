"""
62_bloc_cohesion.py
==================
Cohesion measures to pair with bloc-REACH, on the same full peerage graph,
for focal (lifetime) and M/F/MGF (pre-natal) -- so each can be instrumented
by its maternal pre-natal version (reach-vs-cohesion horse race, 63).

Per target, within the k-hop (k=4) neighbourhood, kin born before the
reference (focal death / focal birth):
  n_dyn_4hop  : REACH = # distinct blocs (breadth)               [cross-check vs 56]
  hhi_4hop    : COHESION (compositional) = Sum_b (n_b/N)^2 bloc-share Herfindahl
                (high = kin concentrated in one bloc = endogamous/cohesive)
  clust1      : COHESION (structural) = local clustering coeff of the immediate
                (1-hop) kin (fraction of kin-pairs that are themselves tied;
                high = tight interconnected clan that can self-enforce)
  n_nodes_4hop, pre_deg

Output (output/): bloc_cohesion_fullgraph.csv
CLI: python 62_bloc_cohesion.py
"""
from __future__ import annotations
import time
from pathlib import Path
import pandas as pd
import igraph as ig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
K = 4; LO, HI = 1100, 1300


def to_year(x):
    s = str(x).strip()
    if s in ("", "nan", "NaN"): return None
    try: return int(float(s))
    except Exception: return None


def main():
    t0 = time.time()
    persons = pd.read_csv(OUT/"persons_imputed.csv")
    birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
    death = {r.id: to_year(r.death) for r in persons.itertuples(index=False)}
    sex = dict(zip(persons["id"], persons["sex"]))
    bloc = dict(zip(pd.read_csv(OUT/"patriline_bloc_assignment.csv")["id"],
                    pd.read_csv(OUT/"patriline_bloc_assignment.csv")["dynasty"]))
    pp = pd.read_csv(OUT/"parent_pairs.csv"); spp = pd.read_csv(OUT/"spouse_pairs.csv")
    po = pd.read_csv(OUT/"parent_order.csv")
    pids = list(persons["id"].values); fi = {p:i for i,p in enumerate(pids)}
    ed = [(fi[p],fi[c]) for p,c in pp.values if p in fi and c in fi]
    seen=set()
    for x,y in spp.values:
        if x in fi and y in fi:
            k=(min(x,y),max(x,y))
            if k not in seen: seen.add(k); ed.append((fi[x],fi[y]))
    G = ig.Graph(n=len(pids), edges=ed); G.vs["pid"]=pids
    nbrs = [set(G.neighbors(v)) for v in range(G.vcount())]   # precompute adjacency sets
    print(f"full graph {G.vcount():,} nodes {G.ecount():,} edges, adj cached ({time.time()-t0:.0f}s)", flush=True)

    plk = {r.child_id:(r.parent0_id,r.parent1_id) for r in po.itertuples(index=False)}
    def parents(c):
        if c not in plk: return None,None
        p0,p1=plk[c]
        mo=p0 if sex.get(p0)=="F" else (p1 if sex.get(p1)=="F" else None)
        fa=p0 if sex.get(p0)=="M" else (p1 if sex.get(p1)=="M" else None)
        return mo,fa

    def scores(tgt, cutoff):
        if tgt is None or tgt not in fi or cutoff is None: return None
        ti=fi[tgt]
        one=[u for u in nbrs[ti] if birth.get(pids[u]) is not None and birth[pids[u]]<cutoff]
        vis={ti}|set(one); fr=set(one); acc={ti}|set(one)
        for h in range(2,K+1):
            nf=set()
            for x in fr:
                for u in nbrs[x]:
                    if u in vis: continue
                    b=birth.get(pids[u])
                    if b is None or b>=cutoff: continue
                    vis.add(u); nf.add(u)
            acc|=nf; fr=nf
            if not fr: break
        # REACH + HHI over acc (exclude ego)
        kin=[u for u in acc if u!=ti]
        bl=[bloc.get(pids[u]) for u in kin]; bl=[b for b in bl if b is not None]
        from collections import Counter
        cnt=Counter(bl); N=sum(cnt.values())
        reach=len(cnt)
        hhi=sum((c/N)**2 for c in cnt.values()) if N>0 else None
        # structural cohesion: local clustering of the 1-hop kin
        os=set(one); n1=len(os)
        if n1>=2:
            e=sum(len(nbrs[u]&os) for u in os)//2
            clust1=e/(n1*(n1-1)/2)
        else:
            clust1=None
        return {"reach":reach,"hhi":hhi,"clust1":clust1,"n_nodes":len(kin),"pre_deg":len(one)}

    nd=pd.read_csv(OUT/"named_dynasty_assignment.csv")
    anch=set(nd.loc[nd["dynasty"].notna()&(nd["dynasty"]!=""),"id"])
    cand=[p for p in anch if sex.get(p)=="M" and birth.get(p) is not None and death.get(p) is not None
          and birth[p]<=HI and death[p]>=LO]
    print(f"{len(cand):,} sample focals ({time.time()-t0:.0f}s)", flush=True)
    rows=[]
    for i,f in enumerate(cand):
        fb,fd=birth.get(f),death.get(f); mo,fa=parents(f); mgf=None
        if mo is not None and mo in plk:
            m0,m1=plk[mo]; mgf=m0 if sex.get(m0)=="M" else (m1 if sex.get(m1)=="M" else None)
        rec={"person_id":f,"bloc":bloc.get(f),"birth":fb,"death":fd,"deg":len(nbrs[fi[f]])}
        sf=scores(f,(fd+1) if fd is not None else None)
        if sf: rec.update({"n_dyn_4hop":sf["reach"],"hhi_4hop":sf["hhi"],"clust1":sf["clust1"],"n_nodes_4hop":sf["n_nodes"]})
        for who,t in (("mother",mo),("father",fa),("mgf",mgf)):
            s=scores(t,fb)
            if s: rec.update({f"{who}_n_dyn_4hop":s["reach"],f"{who}_hhi_4hop":s["hhi"],
                              f"{who}_clust1":s["clust1"],f"{who}_n_nodes_4hop":s["n_nodes"],f"{who}_pre_deg":s["pre_deg"]})
        rows.append(rec)
        if (i+1)%500==0: print(f"  {i+1}/{len(cand)} ({time.time()-t0:.0f}s)", flush=True)
    df=pd.DataFrame(rows); df.to_csv(OUT/"bloc_cohesion_fullgraph.csv", index=False)
    sub=df[df.mother_n_dyn_4hop.notna()]
    print(f"\nwrote bloc_cohesion_fullgraph.csv ({len(df)} rows, {len(sub)} mother-IV)")
    print("focal:  reach mean %.1f | hhi mean %.3f | clust1 mean %.3f"
          % (df.n_dyn_4hop.mean(), df.hhi_4hop.mean(), df.clust1.mean()))
    print("cor(reach, hhi)    = %.3f" % df.n_dyn_4hop.corr(df.hhi_4hop))
    print("cor(reach, clust1) = %.3f" % df.n_dyn_4hop.corr(df.clust1))
    print("cor(hhi,  clust1)  = %.3f" % df.hhi_4hop.corr(df.clust1))
    print("cor(mother reach, mother hhi)    = %.3f" % sub.mother_n_dyn_4hop.corr(sub.mother_hhi_4hop))
    print("cor(mother reach, mother clust1) = %.3f" % sub.mother_n_dyn_4hop.corr(sub.mother_clust1))


if __name__ == "__main__":
    main()
