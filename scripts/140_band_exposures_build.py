"""
140_band_exposures_build.py
===========================
PREDICTION 2, REFORMULATED (8/21): rival-band exposures for the paper's new
statement. The conflict-distance profile (134) locates disputants at 3-7
hops; the RIVAL BAND is the flat 3-7 hop range of the focal's pre-birth
network (unweighted member means, per the paper's prose), the ALLY BAND is
1-2 hops (the falsification companion). All exposures are frozen at birth:
temporal BFS in which every traversed node is born before the focal; letters
count only if dated before the focal's birth.

Per focal (unified estimation frame):
  ally_br / rival_br     mean per-member pre-birth 1-hop distinct-bloc count
  ally_ss / rival_ss     share of members with >=1 secterr letter pre-dating birth
  rival_cnt / rival_cntw mean per-member pre-birth secterr letter COUNT
                         (raw, and winsorized at 10 per member)
  rival_ss_m             share over MATCHABLE members only (censoring variant)
  m_a12 / m_r37          matchable share of each band (censoring controls)
  boundary variants      rival_br27/ss27 (2-7), rival_br47/ss47 (4-7),
                         rival_br34/ss34 (3-4, the modal dispute distance),
                         rival_br35/ss35 (3-5, 84% of dispute mass)
  rival_br_pw/ss_pw      conflict-profile-weighted (134 weights, ring means)
  n_a12, n_r37, n_r27, n_r47, nm_r37   band sizes (size-gate controls)

Out: output/clean_iv/band_exposures.csv
Analysis: 141_band_battery.R; inference: 141b_band_sibship_perm.R
CLI: python scripts/140_band_exposures_build.py
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

import igraph as ig
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
KMAX = 7


def to_year(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def main():
    t0 = time.time()
    dd = pd.read_csv(OUT / "clean_iv" / "dispute_dyad_distance.csv")
    prof = dd[(dd.kind == "dyad") & (dd.d >= 3) & (dd.d <= 7)].d.value_counts(normalize=True).sort_index()
    W = dict(prof / prof.sum())

    persons = pd.read_csv(OUT / "persons_imputed.csv", dtype={"id": str})
    birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
    death = {r.id: to_year(r.death) for r in persons.itertuples(index=False)}
    pba = pd.read_csv(OUT / "patriline_bloc_assignment.csv", dtype=str)
    bloc = dict(zip(pba["id"], pba["dynasty"]))
    nd = pd.read_csv(OUT / "named_dynasty_assignment.csv", dtype=str)
    anch = set(nd.loc[nd.dynasty.fillna("") != "", "id"])
    matchable_ids = {p for p in anch
                     if birth.get(p) is not None and death.get(p) is not None
                     and birth[p] <= 1350 and death[p] >= 1050}

    pids = list(persons["id"].values)
    fi = {p: i for i, p in enumerate(pids)}
    ed = [(fi[a], fi[b]) for a, b in pd.read_csv(OUT / "parent_pairs.csv", dtype=str).values if a in fi and b in fi]
    seen = set()
    for a, b in pd.read_csv(OUT / "spouse_pairs.csv", dtype=str).values:
        if a in fi and b in fi:
            k = (min(a, b), max(a, b))
            if k not in seen:
                seen.add(k)
                ed.append((fi[a], fi[b]))
    G = ig.Graph(n=len(pids), edges=ed)
    nbrs = [np.array(G.neighbors(v), dtype=np.int64) for v in range(G.vcount())]
    barr = np.array([b if (b := birth.get(pids[i])) is not None else np.nan for i in range(G.vcount())])
    bloc_arr = [bloc.get(pids[i]) for i in range(G.vcount())]
    matchable = np.array([pids[i] in matchable_ids for i in range(G.vcount())])
    print(f"graph {G.vcount():,} nodes / {G.ecount():,} edges  ({time.time()-t0:.0f}s)", flush=True)

    coded = pd.read_csv(OUT / "matched_docs_coded.csv", dtype={"doc_id": str})[["doc_id", "domain"]]
    mt = pd.read_csv(OUT / "doc_matches_ai_extracted_high.csv", dtype={"doc_id": str, "person_id": str})
    mt = mt.merge(coded, on="doc_id", how="left")
    sect_years = {}
    for r in mt.itertuples(index=False):
        if r.person_id in fi and pd.notna(r.doc_year) and r.domain == "secular_territorial":
            sect_years.setdefault(fi[r.person_id], []).append(float(r.doc_year))
    sect_years = {i: np.sort(np.array(v)) for i, v in sect_years.items()}

    def pre_cnt(u, cut):
        ys = sect_years.get(u)
        return 0 if ys is None else int(np.searchsorted(ys, cut, side="left"))

    br = pd.read_csv(OUT / "bloc_reach_fullgraph.csv", dtype={"person_id": str})
    sample = br[br.mother_n_dyn_4hop.notna()]["person_id"].tolist()

    def stats(focal):
        ti = fi[focal]
        cut = barr[ti]
        if np.isnan(cut):
            return None
        rings = {}
        vis = {ti}
        fr = [u for u in nbrs[ti] if not np.isnan(barr[u]) and barr[u] < cut]
        d = 1
        while fr and d <= KMAX:
            rings[d] = fr
            vis.update(fr)
            nf = []
            for x in fr:
                for u in nbrs[x]:
                    if u in vis or np.isnan(barr[u]) or barr[u] >= cut:
                        continue
                    vis.add(u)
                    nf.append(u)
            fr = nf
            d += 1

        def nb(u):  # per-member pre-birth 1-hop distinct blocs
            return len({bloc_arr[v] for v in nbrs[u] if bloc_arr[v] and not np.isnan(barr[v]) and barr[v] < cut})

        def band(rng):
            return [u for d_ in rng for u in rings.get(d_, [])]

        def agg(members):
            if not members:
                return (np.nan,) * 5 + (0, 0)
            brm = float(np.mean([nb(u) for u in members]))
            cnts = [pre_cnt(u, cut) for u in members]
            ss = float(np.mean([c > 0 for c in cnts]))
            cnt = float(np.mean(cnts))
            cntw = float(np.mean([min(c, 10) for c in cnts]))
            mm = [u for u in members if matchable[u]]
            ssm = float(np.mean([pre_cnt(u, cut) > 0 for u in mm])) if mm else np.nan
            return brm, ss, cnt, cntw, ssm, len(members), len(mm)

        a_br, a_ss, _, _, _, n_a, nm_a = agg(band(range(1, 3)))
        r_br, r_ss, r_cnt, r_cntw, r_ssm, n_r, nm_r = agg(band(range(3, 8)))
        b27_br, b27_ss, _, _, _, n27, _ = agg(band(range(2, 8)))
        b47_br, b47_ss, _, _, _, n47, _ = agg(band(range(4, 8)))
        b34_br, b34_ss, _, _, _, n34, _ = agg(band(range(3, 5)))
        b35_br, b35_ss, _, _, _, n35, _ = agg(band(range(3, 6)))
        ring_br = {d_: float(np.mean([nb(u) for u in m])) for d_, m in rings.items() if m}
        ring_ss = {d_: float(np.mean([pre_cnt(u, cut) > 0 for u in m])) for d_, m in rings.items() if m}
        wr = {d_: W[d_] for d_ in W if d_ in ring_br}
        pw_br = (sum(ring_br[d_] * w for d_, w in wr.items()) / sum(wr.values())) if wr else np.nan
        pw_ss = (sum(ring_ss[d_] * w for d_, w in wr.items()) / sum(wr.values())) if wr else np.nan
        return (a_br, a_ss, n_a, nm_a, r_br, r_ss, r_cnt, r_cntw, r_ssm, n_r, nm_r,
                b27_br, b27_ss, n27, b47_br, b47_ss, n47,
                b34_br, b34_ss, n34, b35_br, b35_ss, n35, pw_br, pw_ss)

    rows = []
    for j, p in enumerate(sample):
        s = stats(p)
        if s is None:
            continue
        rows.append((p,) + s)
        if (j + 1) % 500 == 0:
            print(f"  {j+1:,}/{len(sample):,} ({time.time()-t0:.0f}s)", flush=True)
    cols = ["person_id", "ally_br", "ally_ss", "n_a12", "nm_a12",
            "rival_br", "rival_ss", "rival_cnt", "rival_cntw", "rival_ss_m", "n_r37", "nm_r37",
            "rival_br27", "rival_ss27", "n_r27", "rival_br47", "rival_ss47", "n_r47",
            "rival_br34", "rival_ss34", "n_r34", "rival_br35", "rival_ss35", "n_r35",
            "rival_br_pw", "rival_ss_pw"]
    df = pd.DataFrame(rows, columns=cols)
    df["m_a12"] = df.nm_a12 / df.n_a12.clip(lower=1)
    df["m_r37"] = df.nm_r37 / df.n_r37.clip(lower=1)
    df.to_csv(OUT / "clean_iv" / "band_exposures.csv", index=False)
    ok = df.dropna(subset=["rival_br", "rival_ss"])
    print(f"\nwrote band_exposures.csv N={len(df)} (rival band nonmissing: {len(ok)})")
    print(f"  rival_br  mean={ok.rival_br.mean():.3f} sd={ok.rival_br.std():.3f}")
    print(f"  rival_ss  mean={ok.rival_ss.mean():.4f} sd={ok.rival_ss.std():.4f} share>0={(ok.rival_ss>0).mean():.3f}")
    print(f"  rival_cnt mean={ok.rival_cnt.mean():.4f} max={ok.rival_cnt.max():.2f} | winsorized max={ok.rival_cntw.max():.2f}")
    print(f"  cor(rival_br, rival_ss)={ok.rival_br.corr(ok.rival_ss):.3f}  cor(flat, profile-weighted br)={ok.rival_br.corr(ok.rival_br_pw):.4f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
