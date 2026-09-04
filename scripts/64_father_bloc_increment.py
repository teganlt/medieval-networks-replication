"""
64_father_bloc_increment.py
============================
BLOC-SPACE version of 50_father_increment.py. Computes the father's
INCREMENTAL pre-natal reach in MARRIAGE-BLOC space: the count of distinct
marriage-blocs within the father's pre-natal k-hop neighbourhood that are
NOT in the mother's pre-natal k-hop neighbourhood -- |F \ M|.

Identical machinery to 50 (same graph = parent+spouse edges, same pre-natal
rule = kin born strictly before the focal's birth, same hop depth k=4). The
ONLY change is the label source: patriline_bloc_assignment.csv (the 579
Louvain marriage-blocs) instead of named_dynasty_assignment.csv (the 21
hand-curated dynasties). This keeps the father control on the SAME topology-
only construction as the bloc reach/HHI it sits beside -- no dynasties
reintroduced.

Motivation (unchanged): father's reach |F| is collinear with the maternal
instrument |M| via the shared overlap |M n F|. |F \ M| is the orthogonal
paternal contribution (R_focal ~ |M u F| = |M| + |F\M|), so controlling it
blocks the assortative-mating backdoor without the mechanical collinearity.

Output (output/clean_iv/father_bloc_increment.csv), per focal in
mother_iv_4hop.csv:
  person_id,
  m_dyn3,f_dyn3,f_extra3,m_extra3,overlap3,union3,
  m_dyn4,f_dyn4,f_extra4,m_extra4,overlap4,union4
(*_dyn/_extra/etc are now BLOC counts; f_extra4 is the control of interest.)

CLI: python 64_father_bloc_increment.py
"""
from __future__ import annotations
import time
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
    # ONLY change vs 50: bloc labels (id, dynasty[=bloc]) instead of dynasties.
    labels = pd.read_csv(OUT / "patriline_bloc_assignment.csv")
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
        """Return (blocset_3, blocset_4) pre-natal; empty if uncomputable."""
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
    out.to_csv(CLEAN / "father_bloc_increment.csv", index=False)
    print(f"Wrote father_bloc_increment.csv ({len(out)} rows)")

    # Consistency check vs 62's bloc reach (bloc_cohesion_fullgraph.csv).
    # NOTE: dyn_sets here INCLUDES the target ego's own bloc (50's convention),
    # whereas 62's reach EXCLUDES ego -> expect m_dyn4 = mother_n_dyn_4hop + {0,1}.
    try:
        bc = pd.read_csv(OUT / "bloc_cohesion_fullgraph.csv")[
            ["person_id", "mother_n_dyn_4hop", "n_dyn_4hop"]]
        chk = out.merge(bc, on="person_id")
        sub = chk[chk["mother_n_dyn_4hop"].notna()]
        d = (sub["m_dyn4"] - sub["mother_n_dyn_4hop"])
        within1 = int((d.abs() <= 1).sum())
        print(f"  consistency m_dyn4 vs 62 mother bloc-reach (ego-inclusive): "
              f"{within1}/{len(sub)} within 1; mean diff {d.mean():.2f}")
        cor_fm = chk["f_extra4"].corr(chk["mother_n_dyn_4hop"])
        cor_fr = chk["f_extra4"].corr(chk["n_dyn_4hop"])
        print(f"  cor(f_extra4, mother bloc-reach) = {cor_fm:.3f}  "
              f"cor(f_extra4, focal bloc-reach) = {cor_fr:.3f}")
    except Exception as e:
        print(f"  (consistency check skipped: {e})")
    print(f"  mean f_dyn4={out.f_dyn4.mean():.2f} f_extra4={out.f_extra4.mean():.2f} "
          f"overlap4={out.overlap4.mean():.2f}  (BLOC space)")


if __name__ == "__main__":
    main()
