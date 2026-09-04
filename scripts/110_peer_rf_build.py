"""
110_peer_rf_build.py
====================
Build the PREDICTION-2 COMPOSITE REDUCED-FORM frame (the 7/27 redo).

Replaces the peer 2SLS (old scripts 83-95): the model's own Prop. 3 gives peer
breadth a direct path to focal court use (ambient conflict risk), so peer
breadth cannot instrument peer court use. Prediction 2 is instead tested as a
reduced form on peer variables that are STRICTLY PREDETERMINED at the focal's
birth — fixing the two timing leaks the audit found in 84:

  peer set        : kin within 4 hops of the focal via temporal BFS in which
                    every traversed node AND peer has birth < focal's birth
                    (identical to 84).
  peer_breadth_pre: mean over peers of each peer's 1-hop distinct-bloc count
                    counting ONLY neighbours born before the focal
                    (84's peer_reach1 counted lifetime edges).
  peer_disp_dated : share of peers with >=1 dispute-coded matched letter DATED
                    before the focal's birth (84's rate used the whole
                    1100-1300 window, allowing contemporaneous/reflection
                    contamination). peer_app_dated likewise for any letter.
  (lifetime versions peer_reach1_life / peer_disp_rate_life are kept for
   comparison with the old construction.)

CENSORING DIAGNOSTICS (added 7/28): peers can only register appearances if
they sit inside the document-MATCHING UNIVERSE (08: named-anchor dynasty
label + integer birth/death + lifespan intersecting [1050,1350], ~6,233
persons). Kin outside it are structural zeros in the dated-share numerators.
So the build also records, per focal:
  peer_n_matchable     : # peers inside the matching universe
  peer_share_matchable : peer_n_matchable / peer_nkin
  peer_disp_dated_m    : pre-birth-dated dispute share with MATCHABLE-ONLY
                         denominator (NaN if no matchable peers)
  peer_app_dated_m     : same for any letter
113_peer_rf_censoring.R uses these for the robustness suite.

Output: output/clean_iv/peer_rf_build.csv (person_id, birth, EMFP, peer_nkin,
peer_breadth_pre, peer_disp_dated, peer_app_dated, peer_reach1_life,
peer_disp_rate_life, + the four matchable-universe columns).
Analysis: 111_peer_rf.R; Oster grid: 112_peer_rf_oster.R; censoring: 113.
CLI: python scripts/110_peer_rf_build.py
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
K = 4
LO, HI = 1100, 1300  # window for the LIFETIME comparison rate only


def to_year(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def main():
    t0 = time.time()
    persons = pd.read_csv(OUT / "persons_imputed.csv", dtype={"id": str})
    birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
    death = {r.id: to_year(r.death) for r in persons.itertuples(index=False)}
    bloc = dict(zip(*[pd.read_csv(OUT / "patriline_bloc_assignment.csv", dtype=str)[c] for c in ("id", "dynasty")]))
    # document-matching universe, mirroring 08 exactly: named-anchor label +
    # integer birth/death + lifespan intersects [1050, 1350]
    nd = pd.read_csv(OUT / "named_dynasty_assignment.csv", dtype=str)
    anch = set(nd.loc[nd.dynasty.fillna("") != "", "id"])
    matchable_ids = {p for p in anch
                     if birth.get(p) is not None and death.get(p) is not None
                     and birth[p] <= 1350 and death[p] >= 1050}
    print(f"matching universe (08 mirror): {len(matchable_ids):,} persons", flush=True)
    pp = pd.read_csv(OUT / "parent_pairs.csv", dtype=str)
    sp = pd.read_csv(OUT / "spouse_pairs.csv", dtype=str)
    pids = list(persons["id"].values)
    fi = {p: i for i, p in enumerate(pids)}
    ed = [(fi[a], fi[b]) for a, b in pp.values if a in fi and b in fi]
    seen = set()
    for a, b in sp.values:
        if a in fi and b in fi:
            k = (min(a, b), max(a, b))
            if k not in seen:
                seen.add(k)
                ed.append((fi[a], fi[b]))
    G = ig.Graph(n=len(pids), edges=ed)
    nbrs = [np.array(G.neighbors(v), dtype=np.int64) for v in range(G.vcount())]
    barr = np.array([b if (b := birth.get(pids[i])) is not None else np.nan for i in range(G.vcount())])
    bloc_arr = [bloc.get(pids[i], "") for i in range(G.vcount())]
    matchable = np.array([pids[i] in matchable_ids for i in range(G.vcount())])
    print(f"graph {G.vcount():,} nodes / {G.ecount():,} edges  ({time.time()-t0:.0f}s)", flush=True)

    # --- matched letters: per-person doc years (any / dispute / secterr), full matched corpus ---
    coded = pd.read_csv(OUT / "matched_docs_coded.csv", dtype={"doc_id": str})[["doc_id", "is_dispute", "domain"]]
    mt = pd.read_csv(OUT / "doc_matches_ai_extracted_high.csv", dtype={"doc_id": str, "person_id": str})
    mt = mt.merge(coded, on="doc_id", how="left")
    yrs_any, yrs_disp, yrs_sect = {}, {}, {}
    for r in mt.itertuples(index=False):
        if r.person_id in fi and pd.notna(r.doc_year):
            yrs_any.setdefault(r.person_id, []).append(int(r.doc_year))
            if r.is_dispute == "yes":
                yrs_disp.setdefault(r.person_id, []).append(int(r.doc_year))
            if r.domain == "secular_territorial":
                yrs_sect.setdefault(r.person_id, []).append(int(r.doc_year))
    first_any = np.full(G.vcount(), np.inf)
    first_disp = np.full(G.vcount(), np.inf)
    first_sect = np.full(G.vcount(), np.inf)
    for p, ys in yrs_any.items():
        first_any[fi[p]] = min(ys)
    for p, ys in yrs_disp.items():
        first_disp[fi[p]] = min(ys)
    for p, ys in yrs_sect.items():
        first_sect[fi[p]] = min(ys)
    # lifetime in-window flags (the old 84 construction, for comparison)
    inwin = mt[(mt.doc_year >= LO) & (mt.doc_year <= HI)]
    disp_life = np.zeros(G.vcount(), bool)
    for p in set(inwin[inwin.is_dispute == "yes"].person_id):
        if p in fi:
            disp_life[fi[p]] = True

    # --- sample: same as the unified frame (bloc_reach_fullgraph + maternal IV) ---
    br = pd.read_csv(OUT / "bloc_reach_fullgraph.csv", dtype={"person_id": str})
    sample = br[br.mother_n_dyn_4hop.notna()]["person_id"].tolist()

    def peer_stats(focal):
        if focal not in fi:
            return None
        ti = fi[focal]
        cut = barr[ti]
        if np.isnan(cut):
            return None
        one = [u for u in nbrs[ti] if not np.isnan(barr[u]) and barr[u] < cut]
        vis = {ti} | set(one)
        fr = set(one)
        acc = set(one)
        for h in range(2, K + 1):
            nf = set()
            for x in fr:
                for u in nbrs[x]:
                    if u in vis or np.isnan(barr[u]) or barr[u] >= cut:
                        continue
                    vis.add(u)
                    nf.add(u)
            acc |= nf
            fr = nf
            if not fr:
                break
        kin = list(acc)
        n = len(kin)
        if n == 0:
            return (cut, 0, np.nan, np.nan, np.nan, np.nan, np.nan, 0, np.nan, np.nan, np.nan)
        bp, r1life = [], []
        for u in kin:
            nb = nbrs[u]
            pre = {bloc_arr[v] for v in nb if bloc_arr[v] and not np.isnan(barr[v]) and barr[v] < cut}
            life = {bloc_arr[v] for v in nb if bloc_arr[v]}
            bp.append(len(pre))
            r1life.append(len(life))
        disp_dated = float(np.mean([first_disp[u] < cut for u in kin]))
        sect_dated = float(np.mean([first_sect[u] < cut for u in kin]))
        app_dated = float(np.mean([first_any[u] < cut for u in kin]))
        disp_lifer = float(np.mean([disp_life[u] for u in kin]))
        km = [u for u in kin if matchable[u]]
        nm = len(km)
        disp_dated_m = float(np.mean([first_disp[u] < cut for u in km])) if nm else np.nan
        sect_dated_m = float(np.mean([first_sect[u] < cut for u in km])) if nm else np.nan
        app_dated_m = float(np.mean([first_any[u] < cut for u in km])) if nm else np.nan
        return (cut, n, float(np.mean(bp)), disp_dated, sect_dated, app_dated, float(np.mean(r1life)), disp_lifer,
                nm, nm / n, disp_dated_m, sect_dated_m, app_dated_m)

    print(f"computing predetermined peer stats for {len(sample):,} focals ...", flush=True)
    rows = []
    for j, p in enumerate(sample):
        st = peer_stats(p)
        if st is None:
            continue
        rows.append((p,) + st)
        if (j + 1) % 500 == 0:
            print(f"  {j+1:,} done ({time.time()-t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows, columns=["person_id", "birth", "peer_nkin", "peer_breadth_pre",
                                     "peer_disp_dated", "peer_secterr_dated", "peer_app_dated",
                                     "peer_reach1_life", "peer_disp_rate_life",
                                     "peer_n_matchable", "peer_share_matchable",
                                     "peer_disp_dated_m", "peer_secterr_dated_m", "peer_app_dated_m"])
    df["EMFP"] = (df.birth <= 1215).astype(int)
    df.to_csv(OUT / "clean_iv" / "peer_rf_build.csv", index=False)
    ok = df[df.peer_nkin > 0]
    print(f"wrote peer_rf_build.csv N={len(df)} (peer set >0 for {len(ok)})")
    print(f"  peer_breadth_pre: mean={ok.peer_breadth_pre.mean():.3f} sd={ok.peer_breadth_pre.std():.3f} "
          f"cor(vs lifetime reach1)={ok.peer_breadth_pre.corr(ok.peer_reach1_life):.3f}")
    print(f"  peer_disp_dated: mean={ok.peer_disp_dated.mean():.4f} "
          f"(lifetime-window rate mean={ok.peer_disp_rate_life.mean():.4f}, cor={ok.peer_disp_dated.corr(ok.peer_disp_rate_life):.3f})")
    print(f"  peer_secterr_dated: mean={ok.peer_secterr_dated.mean():.4f} "
          f"cor(vs dispute-dated)={ok.peer_secterr_dated.corr(ok.peer_disp_dated):.3f}")
    print(f"  EMFP share: {df.EMFP.mean():.3f}")
    print(f"  CENSORING: peer_share_matchable mean={ok.peer_share_matchable.mean():.3f} "
          f"(p10={ok.peer_share_matchable.quantile(.1):.3f}, p90={ok.peer_share_matchable.quantile(.9):.3f})")
    print(f"    cor(share_matchable, breadth_pre)={ok.peer_share_matchable.corr(ok.peer_breadth_pre):.3f}  <- the concern's magnitude")
    print(f"    peer_disp_dated_m mean={ok.peer_disp_dated_m.mean():.4f}  cor(zD, zDm)={ok.peer_disp_dated.corr(ok.peer_disp_dated_m):.3f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
