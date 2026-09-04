"""
50_father_increment.py
=======================
Compute the father's INCREMENTAL pre-natal dynastic reach: the count of
distinct dynasties within the father's pre-natal k-hop neighbourhood that
are NOT in the mother's pre-natal k-hop neighbourhood -- |F \ M|.

Motivation: father's reach |F| is collinear with the maternal instrument
|M| because they share the overlap |M n F|.  |F \ M| is the orthogonal
paternal contribution to the focal's reach (R_focal ~ |M u F| = |M| +
|F\M|), so controlling it blocks the assortative-mating backdoor without
the mechanical collinearity.

Reuses stage-18's exact graph (parent+spouse edges) and pre-natal rule
(kin born strictly before the focal's birth), and the SAME dynasty labels.

Output (output/clean_iv/father_increment.csv), per focal in mother_iv_4hop.csv:
  person_id,
  m_dyn3,f_dyn3,f_extra3,m_extra3,overlap3,union3,
  m_dyn4,f_dyn4,f_extra4,m_extra4,overlap4,union4
(*_extra = set difference; cross-check: m_dyn4 must equal mother_n_dyn_4hop.)

CLI: python 50_father_increment.py
"""
from __future__ import annotations
import csv, time
from pathlib import Path
import pandas as pd
import igraph as ig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
CLEAN = OUT / "clean_iv"; CLEAN.mkdir(exist_ok=True)
MAX_HOPS = 4


def main():
    print("Loading data ...", flush=True)
    persons = pd.read_csv(OUT / "persons_imputed.csv")
    parent_order = pd.read_csv(OUT / "parent_order.csv")
    parent_pairs = pd.read_csv(OUT / "parent_pairs.csv")
    spouse_pairs = pd.read_csv(OUT / "spouse_pairs.csv")
    labels = pd.read_csv(OUT / "named_dynasty_assignment.csv")
    iv = pd.read_csv(OUT / "mother_iv_4hop.csv")
    focal_ids = list(iv["person_id"].values)

    pid_to_birth = dict(zip(persons["id"], persons["birth"]))
    pid_to_sex = dict(zip(persons["id"], persons["sex"]))
    pid_to_dyn = dict(zip(labels["id"], labels["dynasty"]))

    all_pids = list(persons["id"].values)
    pid_to_idx = {p: i for i, p in enumerate(all_pids)}
    edges = []
    for parent_id, child_id in parent_pairs.values:
        if parent_id in pid_to_idx and child_id in pid_to_idx:
            edges.append((pid_to_idx[parent_id], pid_to_idx[child_id]))
    seen = set()
    for a, b in spouse_pairs.values:
        if a in pid_to_idx and b in pid_to_idx:
            k = (min(a, b), max(a, b))
            if k in seen:
                continue
            seen.add(k); edges.append((pid_to_idx[a], pid_to_idx[b]))
    G = ig.Graph(n=len(all_pids), edges=edges, directed=False)
    G.vs["birth"] = [pid_to_birth.get(p) for p in all_pids]
    G.vs["dyn"] = [pid_to_dyn.get(p, "") for p in all_pids]
    print(f"  graph: {G.vcount():,} nodes, {G.ecount():,} edges", flush=True)

    parent_lookup = {}
    for row in parent_order.itertuples(index=False):
        parent_lookup[row.child_id] = (row.parent0_id, row.parent1_id)

    def find_parents(cid):
        if cid not in parent_lookup:
            return None, None
        p0, p1 = parent_lookup[cid]
        s0, s1 = pid_to_sex.get(p0, ""), pid_to_sex.get(p1, "")
        mother = p0 if s0 == "F" else (p1 if s1 == "F" else None)
        father = p0 if s0 == "M" else (p1 if s1 == "M" else None)
        return mother, father

    def dyn_sets(target_pid, cutoff):
        """Return (dynset_3, dynset_4) pre-natal; empty if uncomputable."""
        if target_pid is None or target_pid not in pid_to_idx:
            return None, None
        tb = pid_to_birth.get(target_pid)
        if tb is None or cutoff is None or tb >= cutoff:
            return None, None
        ti = pid_to_idx[target_pid]
        one = [u for u in G.neighbors(ti)
               if (G.vs[u]["birth"] is not None and G.vs[u]["birth"] < cutoff)]
        visited = {ti}; visited.update(one)
        frontier = set(one); levels = [None, set(one)]
        for hop in range(2, MAX_HOPS + 1):
            nf = set()
            for v in frontier:
                for u in G.neighbors(v):
                    if u in visited:
                        continue
                    b = G.vs[u]["birth"]
                    if b is None or b >= cutoff:
                        continue
                    visited.add(u); nf.add(u)
            levels.append(nf); frontier = nf
            if not frontier:
                while len(levels) <= MAX_HOPS:
                    levels.append(set())
                break
        v3 = {ti} | levels[1] | levels[2] | levels[3]
        v4 = v3 | levels[4]
        d3 = {G.vs[v]["dyn"] for v in v3 if G.vs[v]["dyn"]}
        d4 = {G.vs[v]["dyn"] for v in v4 if G.vs[v]["dyn"]}
        return d3, d4

    print(f"Iterating {len(focal_ids):,} focals ...", flush=True)
    rows = []; t0 = time.time()
    for i, fid in enumerate(focal_ids):
        fb = pid_to_birth.get(fid)
        mid, fad = find_parents(fid)
        m3, m4 = dyn_sets(mid, fb)
        f3, f4 = dyn_sets(fad, fb)
        rec = {"person_id": fid}
        for tag, ms, fs in (("3", m3, f3), ("4", m4, f4)):
            if ms is None:
                ms = set()
            if fs is None:
                fs = set()
            rec[f"m_dyn{tag}"]    = len(ms)
            rec[f"f_dyn{tag}"]    = len(fs)
            rec[f"f_extra{tag}"]  = len(fs - ms)
            rec[f"m_extra{tag}"]  = len(ms - fs)
            rec[f"overlap{tag}"]  = len(ms & fs)
            rec[f"union{tag}"]    = len(ms | fs)
        rows.append(rec)
        if (i + 1) % 1000 == 0:
            print(f"  {i+1}/{len(focal_ids)} ({time.time()-t0:.0f}s)", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(CLEAN / "father_increment.csv", index=False)
    print(f"Wrote father_increment.csv ({len(out)} rows)")

    # cross-check m_dyn4 == mother_n_dyn_4hop where computable
    chk = out.merge(iv[["person_id", "mother_n_dyn_4hop", "father_n_dyn_4hop"]],
                    on="person_id")
    sub = chk[chk["mother_n_dyn_4hop"].notna()]
    mm = int((sub["m_dyn4"] != sub["mother_n_dyn_4hop"]).sum())
    sub2 = chk[chk["father_n_dyn_4hop"].notna()]
    fm = int((sub2["f_dyn4"] != sub2["father_n_dyn_4hop"]).sum())
    print(f"  cross-check m_dyn4 vs mother_n_dyn_4hop: {mm} mismatches of {len(sub)}")
    print(f"  cross-check f_dyn4 vs father_n_dyn_4hop: {fm} mismatches of {len(sub2)}")
    print(f"  mean f_dyn4={out.f_dyn4.mean():.2f} f_extra4={out.f_extra4.mean():.2f} "
          f"overlap4={out.overlap4.mean():.2f}")


if __name__ == "__main__":
    main()
