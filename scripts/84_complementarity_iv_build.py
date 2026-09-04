"""
84_complementarity_iv_build.py
==============================
Build the dataframe for an INSTRUMENTED peer-effect (network-good) test.
Endogenous peer regressor = focal's pre-natal kin court-engagement rate;
instrument = the kin network's REACH BREADTH (avg over the focal's pre-natal
kin of each kin's 1-hop bloc count -- a cheap, all-nodes proxy for reach).
Logic: forward IV says reach -> court use, so kin breadth shifts kin court use
(first stage); excludable from focal court use net of focal reach/size/title
(network-good channel). Reduced-form predetermination: pre-natal kin only.
Writes output/clean_iv/reg_complementarity_iv_df.csv for 85 (feols 2SLS).
CLI: python 84_complementarity_iv_build.py
"""
from __future__ import annotations
import re, time
from pathlib import Path
import igraph as ig
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
K = 4; LO, HI = 1100, 1300


def to_year(x):
    try: return int(float(x))
    except (TypeError, ValueError): return None


def title_rank(nm):
    if not isinstance(nm, str): return 0
    s = nm.lower()
    if re.search(r'emperor|empress|imperator|imperatrix', s): return 5
    if re.search(r'\bking\b|\bqueen\b|\broi\b|\breine\b|\brey de\b|\brei de\b|\bre di\b|\bk[oö]nig\b', s): return 4
    if re.search(r'\bduke\b|\bduc\b|\bherzog\b|\bduca\b|\bduque\b', s): return 3
    if re.search(r'\bcount\b|\bearl\b|\bcomte\b|\bgraf\b|\bconte\b|\bmarchese\b|\bmarkgraf\b|\bconde\b', s): return 2
    if re.search(r'\blord\b|\bsieur\b|\bbaron\b|\bvicomte\b|\bsire\b|\bseigneur\b|\bsignore\b', s): return 1
    return 0


def main():
    t0 = time.time()
    persons = pd.read_csv(OUT/"persons_imputed.csv", dtype={"id": str})
    birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
    name = dict(zip(persons.id, persons.name))
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
    # cheap per-node reach proxy: # distinct blocs among direct neighbours
    reach1 = np.array([len({bloc_arr[u] for u in nbrs[i] if bloc_arr[u]}) for i in range(G.vcount())], float)
    print(f"graph {G.vcount():,} nodes; reach1 computed ({time.time()-t0:.0f}s)", flush=True)

    coded = pd.read_csv(OUT/"matched_docs_coded.csv", dtype={"doc_id": str})[["doc_id", "domain", "is_dispute"]]
    mt = pd.read_csv(OUT/"doc_matches_ai_extracted_high.csv", dtype={"doc_id": str})
    mt = mt[(mt.doc_year >= LO) & (mt.doc_year <= HI)][["person_id", "doc_id"]].merge(coded, on="doc_id")
    mt["person_id"] = mt.person_id.astype(str)
    app_node = np.zeros(G.vcount(), bool); dsp_node = np.zeros(G.vcount(), bool)
    for p in set(mt.person_id):
        if p in fi: app_node[fi[p]] = True
    for p in set(mt[mt.is_dispute == "yes"].person_id):
        if p in fi: dsp_node[fi[p]] = True
    pcounts = mt.groupby("person_id").agg(n_secterr=("domain", lambda s: (s == "secular_territorial").sum()),
        n_total=("doc_id", "size"), n_dispute=("is_dispute", lambda s: (s == "yes").sum())).reset_index()

    br = pd.read_csv(OUT/"bloc_cohesion_fullgraph.csv")
    iv = pd.read_csv(OUT/"mother_iv_4hop.csv")[["person_id", "father_id"]]
    df = br.merge(iv, on="person_id", how="left")
    df = df[df.mother_n_dyn_4hop.notna()].copy(); df["person_id"] = df.person_id.astype(str)

    def peer(focal):
        if focal not in fi: return (np.nan,)*4
        ti = fi[focal]; cut = barr[ti]
        if np.isnan(cut): return (np.nan,)*4
        one = [u for u in nbrs[ti] if not np.isnan(barr[u]) and barr[u] < cut]
        vis = {ti} | set(one); fr = set(one); acc = set(one)
        for h in range(2, K+1):
            nf = set()
            for x in fr:
                for u in nbrs[x]:
                    if u in vis or np.isnan(barr[u]) or barr[u] >= cut: continue
                    vis.add(u); nf.add(u)
            acc |= nf; fr = nf
            if not fr: break
        kin = list(acc); n = len(kin)
        if n == 0: return (0.0, 0.0, 0.0, 0)
        return (sum(app_node[u] for u in kin)/n, sum(dsp_node[u] for u in kin)/n,
                float(np.mean([reach1[u] for u in kin])), n)

    print(f"computing peer rates + instrument for {len(df):,} focals ...", flush=True)
    pr = [peer(p) for p in df.person_id.values]
    df["peer_app_rate"] = [x[0] for x in pr]; df["peer_disp_rate"] = [x[1] for x in pr]
    df["peer_reach1"] = [x[2] for x in pr]; df["peer_nkin"] = [x[3] for x in pr]
    df = df.merge(pcounts, on="person_id", how="left")
    for c in ["n_secterr", "n_total", "n_dispute"]: df[c] = df[c].fillna(0)
    fa = pcounts.rename(columns={"person_id": "father_id", "n_dispute": "fa_disp", "n_total": "fa_total"})[["father_id", "fa_disp", "fa_total"]]
    df = df.merge(fa, on="father_id", how="left"); df[["fa_disp", "fa_total"]] = df[["fa_disp", "fa_total"]].fillna(0)
    df["death_decade"] = (df.death // 10 * 10)
    df["log_size"] = np.log1p(df.n_nodes_4hop)
    df["fa_ldisp"] = np.log1p(df.fa_disp); df["fa_ltotal"] = np.log1p(df.fa_total)
    df["y_secterr"] = np.log1p(df.n_secterr); df["y_total"] = np.log1p(df.n_total)
    df["title_rank"] = [title_rank(name.get(p)) for p in df.person_id.values]
    df["EMFP"] = (df.birth <= 1215).astype(int)
    keep = ["person_id", "bloc", "death_decade", "EMFP", "title_rank", "y_secterr", "y_total",
            "peer_app_rate", "peer_disp_rate", "peer_reach1", "peer_nkin", "n_dyn_4hop", "log_size", "fa_ldisp", "fa_ltotal"]
    out = df[df.peer_disp_rate.notna()][keep]
    out.to_csv(OUT/"clean_iv"/"reg_complementarity_iv_df.csv", index=False)
    print(f"wrote reg_complementarity_iv_df.csv N={len(out)} blocs={out.bloc.nunique()}", flush=True)
    print(f"  cor(peer_disp_rate, peer_reach1)={out.peer_disp_rate.corr(out.peer_reach1):.2f} (first-stage signal)")
    print(f"  peer_reach1 mean={out.peer_reach1.mean():.1f}  peer_disp_rate mean={out.peer_disp_rate.mean():.3f}")


if __name__ == "__main__":
    main()
