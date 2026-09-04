"""
18_mother_iv_construct.py
==========================

Stage 18 (C): construct the maternal instrument + parent/MGF controls.

For each focal noble, find the mother, father, and maternal grandfather
(MGF), and compute each of their PRE-FOCAL-BIRTH network scores on the
full kinship graph:

  <parent>_n_dyn_3hop   # distinct dynasty/bloc labels within 3 hops,
                        counting only kin born before the focal's birth
  <parent>_n_dyn_4hop   # same at 4 hops
  <parent>_cross_dyn    # pre-natal 1-hop neighbors in a different
                        dynasty/bloc than the parent
  <parent>_pre_deg      # pre-natal 1-hop degree

The "pre-natal" restriction (only counting kin born before the focal's
birth) is what makes mother_n_dyn_4hop a valid instrument: it captures
the maternal alliance network that existed BEFORE the focal was born,
so it cannot be a consequence of the focal's own life.

mother_n_dyn_4hop is the headline instrument. The 3-hop columns and the
father/MGF columns support the robustness ladder and over-identification.

FOCAL UNIVERSE (union, tagged with flags so one file serves both):
  in_anchored_universe = 1 if the focal is anchored (21-dynasty
        assignment) AND in the 1100-1300 active subgraph. This is the
        methods-doc "all anchored nobles" sample.
  in_dedup_universe = 1 if the focal is in person_summary_dedup.csv,
        the old regex-era candidate list used by the 5_20 regressions.
        Kept ONLY to reproduce the exact 5_20 numbers.

The two universes overlap heavily but are not identical (see the
package notes). Downstream regressions filter on whichever flag they
want.

Parameterized by --labels so the same focal set is scored under the
21-dynasty labeling and under each bloc labeling:
  mother_iv_4hop.csv                 (21-dynasty)
  mother_iv_bloc_N{N}_4hop.csv       for N in 5..15

Inputs (in output/):
  persons_imputed.csv
  parent_order.csv
  parent_pairs.csv
  spouse_pairs.csv
  named_dynasty_assignment.csv             (for the anchored-universe flag)
  network_nodes_4hop.csv                   (for active-window membership)
  person_summary_dedup.csv                 (for the dedup-universe flag)
  <labels csv>                             (for the scoring labeling)

Output (in output/):
  mother_iv{SUFFIX}_4hop.csv

CLI:
  python 18_mother_iv_construct.py
      Defaults: --labels named_dynasty_assignment.csv, --suffix ""
      -> mother_iv_4hop.csv (21-dynasty)

  python 18_mother_iv_construct.py \\
      --labels named_dynasty_assignment_bloc_N10.csv --suffix _bloc_N10
      -> mother_iv_bloc_N10_4hop.csv
"""
from __future__ import annotations
import argparse
import time
from pathlib import Path

import pandas as pd
import igraph as ig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

MAX_HOPS = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=str,
                    default="named_dynasty_assignment.csv")
    ap.add_argument("--suffix", type=str, default="")
    args = ap.parse_args()

    labels_csv = OUT / args.labels
    if not labels_csv.exists():
        raise SystemExit(f"labels CSV not found: {labels_csv}")
    out_path = OUT / f"mother_iv{args.suffix}_4hop.csv"

    print(f"Labels:  {args.labels}")
    print(f"Output:  {out_path.name}\n")

    print("Loading data ...", flush=True)
    persons = pd.read_csv(OUT / "persons_imputed.csv")
    parent_order = pd.read_csv(OUT / "parent_order.csv")
    parent_pairs = pd.read_csv(OUT / "parent_pairs.csv")
    spouse_pairs = pd.read_csv(OUT / "spouse_pairs.csv")
    labels = pd.read_csv(labels_csv)

    # Canonical 21-dynasty anchoring (for the anchored-universe flag) +
    # active-window membership (network_nodes is labeling-independent).
    anchor21 = pd.read_csv(OUT / "named_dynasty_assignment.csv")
    anchored_ids = set(anchor21.loc[anchor21["dynasty"].notna()
                                    & (anchor21["dynasty"] != ""), "id"])
    nw = pd.read_csv(OUT / "network_nodes_4hop.csv")
    active_ids = set(nw["person_id"])
    anchored_active = anchored_ids & active_ids

    dedup_ids = set()
    dedup_path = OUT / "person_summary_dedup.csv"
    if dedup_path.exists():
        dedup_ids = set(pd.read_csv(dedup_path)["person_id"])
    else:
        print("  (person_summary_dedup.csv not present; "
              "in_dedup_universe = 0 for all)")

    focal_set = anchored_active | dedup_ids
    print(f"  anchored & active:       {len(anchored_active):,}")
    print(f"  dedup (5_20) universe:   {len(dedup_ids):,}")
    print(f"  union focal set:         {len(focal_set):,}")

    pid_to_birth = dict(zip(persons["id"], persons["birth"]))
    pid_to_sex = dict(zip(persons["id"], persons["sex"]))
    pid_to_dyn = dict(zip(labels["id"], labels["dynasty"]))

    print("Building full kinship graph ...", flush=True)
    t0 = time.time()
    all_pids = list(persons["id"].values)
    pid_to_idx = {p: i for i, p in enumerate(all_pids)}

    edges = []
    for parent_id, child_id in parent_pairs.values:
        if parent_id in pid_to_idx and child_id in pid_to_idx:
            edges.append((pid_to_idx[parent_id], pid_to_idx[child_id]))
    seen_spouse = set()
    for a, b in spouse_pairs.values:
        if a in pid_to_idx and b in pid_to_idx:
            key = (min(a, b), max(a, b))
            if key in seen_spouse:
                continue
            seen_spouse.add(key)
            edges.append((pid_to_idx[a], pid_to_idx[b]))

    G = ig.Graph(n=len(all_pids), edges=edges, directed=False)
    G.vs["pid"] = all_pids
    G.vs["birth"] = [pid_to_birth.get(p) for p in all_pids]
    G.vs["dyn"] = [pid_to_dyn.get(p, "") for p in all_pids]
    print(f"  full graph: {G.vcount():,} nodes, {G.ecount():,} edges "
          f"({time.time()-t0:.0f}s)", flush=True)

    parent_lookup = {}
    for row in parent_order.itertuples(index=False):
        parent_lookup[row.child_id] = (row.parent0_id, row.parent1_id)

    def find_parents(child_id):
        if child_id not in parent_lookup:
            return None, None
        p0, p1 = parent_lookup[child_id]
        s0 = pid_to_sex.get(p0, "")
        s1 = pid_to_sex.get(p1, "")
        mother = None
        father = None
        if s0 == "F":
            mother = p0
        elif s1 == "F":
            mother = p1
        if s0 == "M":
            father = p0
        elif s1 == "M":
            father = p1
        return mother, father

    def compute_scores(target_pid, cutoff_year, max_hops=MAX_HOPS):
        """Return (n_dyn_3hop, n_dyn_4hop, n_nodes_3hop, n_nodes_4hop,
        cross_dyn_neighbors, pre_deg).

        n_nodes_*hop = headcount of distinct OTHER persons (network SIZE)
        reachable within that many hops, pre-natal; the size counterpart
        to the n_dyn reach/diversity score. Excludes ego.

        Pre-natal: only count kin born strictly before cutoff_year.
        """
        if target_pid is None or target_pid not in pid_to_idx:
            return None, None, None, None, None, None
        target_birth = pid_to_birth.get(target_pid)
        if target_birth is None or cutoff_year is None:
            return None, None, None, None, None, None
        if target_birth >= cutoff_year:
            return None, None, None, None, None, None

        target_idx = pid_to_idx[target_pid]
        target_dyn = pid_to_dyn.get(target_pid, "")

        one_hop = []
        for u in G.neighbors(target_idx):
            u_birth = G.vs[u]["birth"]
            if u_birth is None or u_birth >= cutoff_year:
                continue
            one_hop.append(u)
        pre_degree = len(one_hop)

        visited = {target_idx}
        visited.update(one_hop)
        frontier = set(one_hop)
        levels = [None, set(one_hop)]  # levels[1] = 1-hop
        for hop in range(2, max_hops + 1):
            next_frontier = set()
            for v in frontier:
                for u in G.neighbors(v):
                    if u in visited:
                        continue
                    u_birth = G.vs[u]["birth"]
                    if u_birth is None or u_birth >= cutoff_year:
                        continue
                    visited.add(u)
                    next_frontier.add(u)
            levels.append(next_frontier)
            frontier = next_frontier
            if not frontier:
                while len(levels) <= max_hops:
                    levels.append(set())
                break

        visited_3 = {target_idx} | levels[1] | levels[2] | levels[3]
        dyns_3 = set(G.vs[v]["dyn"] for v in visited_3 if G.vs[v]["dyn"])

        visited_4 = visited_3 | levels[4]
        dyns_4 = set(G.vs[v]["dyn"] for v in visited_4 if G.vs[v]["dyn"])

        # Network SIZE: distinct persons reachable within 3/4 hops,
        # excluding ego (the visited_* sets include target_idx).
        n_nodes_3 = len(visited_3) - 1
        n_nodes_4 = len(visited_4) - 1

        cross = 0
        if target_dyn:
            for u in one_hop:
                u_dyn = G.vs[u]["dyn"]
                if u_dyn and u_dyn != target_dyn:
                    cross += 1

        return (int(len(dyns_3)), int(len(dyns_4)),
                int(n_nodes_3), int(n_nodes_4),
                int(cross), int(pre_degree))

    print("\nIterating focal nobles (union universe) ...", flush=True)
    focal_list = sorted(focal_set)
    print(f"  focals: {len(focal_list):,}", flush=True)

    rows = []
    t0 = time.time()
    for i, focal_id in enumerate(focal_list):
        focal_birth = pid_to_birth.get(focal_id)
        mother_id, father_id = find_parents(focal_id)

        m3 = m4 = m_n3 = m_n4 = m_cross = m_deg = None
        f3 = f4 = f_n3 = f_n4 = f_cross = f_deg = None
        g3 = g4 = g_n3 = g_n4 = g_cross = g_deg = None

        if focal_birth is not None and mother_id is not None:
            m3, m4, m_n3, m_n4, m_cross, m_deg = compute_scores(mother_id, focal_birth)
        if focal_birth is not None and father_id is not None:
            f3, f4, f_n3, f_n4, f_cross, f_deg = compute_scores(father_id, focal_birth)

        mgf_id = None
        if mother_id is not None and mother_id in parent_lookup:
            mp0, mp1 = parent_lookup[mother_id]
            if pid_to_sex.get(mp0, "") == "M":
                mgf_id = mp0
            elif pid_to_sex.get(mp1, "") == "M":
                mgf_id = mp1

        if focal_birth is not None and mgf_id is not None:
            g3, g4, g_n3, g_n4, g_cross, g_deg = compute_scores(mgf_id, focal_birth)

        rows.append({
            "person_id": focal_id, "focal_birth": focal_birth,
            "focal_sex": pid_to_sex.get(focal_id, ""),
            "mother_id": mother_id, "father_id": father_id, "mgf_id": mgf_id,
            "mother_n_dyn_3hop": m3, "mother_n_dyn_4hop": m4,
            "mother_n_nodes_3hop": m_n3, "mother_n_nodes_4hop": m_n4,
            "mother_cross_dyn": m_cross, "mother_pre_deg": m_deg,
            "father_n_dyn_3hop": f3, "father_n_dyn_4hop": f4,
            "father_n_nodes_3hop": f_n3, "father_n_nodes_4hop": f_n4,
            "father_cross_dyn": f_cross, "father_pre_deg": f_deg,
            "mgf_n_dyn_3hop": g3, "mgf_n_dyn_4hop": g4,
            "mgf_n_nodes_3hop": g_n3, "mgf_n_nodes_4hop": g_n4,
            "mgf_cross_dyn": g_cross, "mgf_pre_deg": g_deg,
            "in_anchored_universe": int(focal_id in anchored_active),
            "in_dedup_universe": int(focal_id in dedup_ids),
        })

        if (i + 1) % 1000 == 0:
            print(f"  {i+1}/{len(focal_list)} ({time.time()-t0:.0f}s)",
                  flush=True)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(out_path, index=False)
    print(f"\nWrote {out_path.name}  ({len(out_df)} rows)", flush=True)
    print(f"  in_anchored_universe: {int(out_df['in_anchored_universe'].sum()):,}")
    print(f"  in_dedup_universe:    {int(out_df['in_dedup_universe'].sum()):,}")
    print(f"  mother_n_dyn_4hop non-null: "
          f"{out_df['mother_n_dyn_4hop'].notna().sum():,}")
    print(f"  mother_n_dyn_4hop mean (non-null): "
          f"{out_df['mother_n_dyn_4hop'].mean():.2f}")
    print(f"  mother_n_nodes_4hop mean (non-null): "
          f"{out_df['mother_n_nodes_4hop'].mean():.2f}")


if __name__ == "__main__":
    main()
