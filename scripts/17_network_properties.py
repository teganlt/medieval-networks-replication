"""
17_network_properties.py
=========================

Stage 17 (A): per-person network properties for the IV.

For each person whose lifespan overlaps [WINDOW_LO, WINDOW_HI] (default
1100-1300), plus their immediate kin (parents, children, spouses, minus
isolates), compute:

  deg                  total kin-graph degree
  log_deg              log(1 + deg)
  n_dyn_3hop           # distinct dynasty/bloc labels within 3-hop
                       kinship neighborhood
  n_dyn_4hop           # distinct dynasty/bloc labels within 4-hop
                       kinship neighborhood
  cross_dyn_neighbors  # immediate neighbors whose dynasty/bloc differs
                       from own

The 4-hop reach is the headline IV variable. 3-hop is computed in
parallel as the robustness check.

The script is parameterized by the labels CSV (--labels), so the same
algorithm produces:
  - network_nodes_4hop.csv               (21-dynasty labels)
  - network_nodes_bloc_N{N}_4hop.csv     for N in 5..15 (bloc labels)

Both shipped via the sweep wrapper run_network_properties_sweep.py.

Edge convention:  undirected, parent+spouse, deduplicated.
Active subgraph:  lifespan_overlaps(WINDOW_LO, WINDOW_HI) U 1-hop kin,
                  drop isolates (degree 0). Same convention as the bloc
                  meta-clustering step (stage 15).

Inputs (in output/):
  persons_imputed.csv
  parent_pairs.csv
  spouse_pairs.csv
  named_dynasty_assignment.csv (default)
    or named_dynasty_assignment_bloc_N{N}.csv (via --labels)
  person_summary_ai_extracted_high.csv  (optional, for in_match_sample flag)

Output (in output/):
  network_nodes{SUFFIX}_4hop.csv
    Schema: person_id, name, sex, birth, death, in_match_sample,
            dynasty, deg, log_deg, n_dyn_3hop, n_dyn_4hop,
            cross_dyn_neighbors

CLI:
  python 17_network_properties.py
      Defaults: --labels named_dynasty_assignment.csv, --suffix ""
      Produces output/network_nodes_4hop.csv

  python 17_network_properties.py \\
      --labels named_dynasty_assignment_bloc_N10.csv \\
      --suffix _bloc_N10
      Produces output/network_nodes_bloc_N10_4hop.csv
"""
from __future__ import annotations
import argparse
import csv
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import igraph as ig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

WINDOW_LO = 1100
WINDOW_HI = 1300


def to_year(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def load_persons():
    persons = {}
    with open(OUT / "persons_imputed.csv", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            persons[row["id"]] = {
                "name": row["name"], "sex": row["sex"],
                "birth": to_year(row["birth"]),
                "death": to_year(row["death"]),
            }
    return persons


def load_dynasty(labels_csv: Path):
    dyn = {}
    with open(labels_csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row["dynasty"]:
                dyn[row["id"]] = row["dynasty"]
    return dyn


def load_edges():
    parent_pairs, spouse_pairs = [], []
    adj = defaultdict(set)
    with open(OUT / "parent_pairs.csv", encoding="utf-8") as f:
        r = csv.reader(f); next(r)
        for p, c in r:
            parent_pairs.append((p, c))
            adj[p].add(c); adj[c].add(p)
    with open(OUT / "spouse_pairs.csv", encoding="utf-8") as f:
        r = csv.reader(f); next(r)
        for a, b in r:
            spouse_pairs.append((a, b))
            adj[a].add(b); adj[b].add(a)
    return parent_pairs, spouse_pairs, adj


def lifespan_overlaps(info, lo, hi):
    b, d = info["birth"], info["death"]
    if b is None or d is None:
        return False
    return b <= hi and d >= lo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--labels", type=str,
        default="named_dynasty_assignment.csv",
        help="Labels CSV filename in output/ "
             "(default named_dynasty_assignment.csv)")
    ap.add_argument(
        "--suffix", type=str, default="",
        help="Suffix appended to the output filename. Empty by default "
             "(produces network_nodes_4hop.csv).")
    ap.add_argument(
        "--window-lo", type=int, default=WINDOW_LO,
        help=f"Lower bound of active window (default {WINDOW_LO}).")
    ap.add_argument(
        "--window-hi", type=int, default=WINDOW_HI,
        help=f"Upper bound of active window (default {WINDOW_HI}).")
    args = ap.parse_args()

    labels_csv = OUT / args.labels
    if not labels_csv.exists():
        raise SystemExit(f"labels CSV not found: {labels_csv}")
    out_path = OUT / f"network_nodes{args.suffix}_4hop.csv"

    t0 = time.time()
    print(f"Labels:        {args.labels}")
    print(f"Output:        {out_path.name}")
    print(f"Active window: [{args.window_lo}, {args.window_hi}]\n")

    print("Loading persons + edges + labels ...", flush=True)
    persons = load_persons()
    parent_pairs, spouse_pairs, adj = load_edges()
    dyn_assign = load_dynasty(labels_csv)
    n_dyn_unique = len(set(dyn_assign.values()))
    print(f"  persons: {len(persons):,}; "
          f"dyn-assigned: {len(dyn_assign):,}; "
          f"unique labels: {n_dyn_unique}", flush=True)

    print(f"Building active subgraph (lifespan overlaps "
          f"[{args.window_lo}, {args.window_hi}] U 1-hop kin) ...",
          flush=True)
    L = {pid for pid, info in persons.items()
         if lifespan_overlaps(info, args.window_lo, args.window_hi)}
    expanded = set(L)
    for pid in L:
        expanded.update(adj.get(pid, ()))
    expanded &= persons.keys()

    nodes_sorted = sorted(expanded)
    idx = {pid: i for i, pid in enumerate(nodes_sorted)}
    edges = set()
    for a, b in parent_pairs:
        if a in idx and b in idx:
            i, j = idx[a], idx[b]
            edges.add((min(i, j), max(i, j)))
    for a, b in spouse_pairs:
        if a in idx and b in idx and a != b:
            i, j = idx[a], idx[b]
            edges.add((min(i, j), max(i, j)))
    g = ig.Graph(n=len(nodes_sorted), edges=list(edges), directed=False)
    g.simplify(multiple=True, loops=True)

    deg_pre = np.array(g.degree())
    keep = np.where(deg_pre > 0)[0]
    g_trim = g.subgraph(keep)
    nodes_trim = [nodes_sorted[i] for i in keep]
    print(f"  V_trim={g_trim.vcount():,}  E_trim={g_trim.ecount():,}",
          flush=True)

    deg = np.array(g_trim.degree())

    print("Computing 3-hop and 4-hop reach + cross_dyn_neighbors ...",
          flush=True)
    dyn_per = np.array([dyn_assign.get(nodes_trim[i], "")
                        for i in range(len(nodes_trim))])
    n_dyn_3hop = np.zeros(g_trim.vcount(), dtype=int)
    n_dyn_4hop = np.zeros(g_trim.vcount(), dtype=int)
    cross_dyn_neighbors = np.zeros(g_trim.vcount(), dtype=int)
    for v in range(g_trim.vcount()):
        own = dyn_per[v]
        n3 = g_trim.neighborhood(v, order=3)
        n4 = g_trim.neighborhood(v, order=4)
        d3 = set(dyn_per[u] for u in n3 if dyn_per[u])
        d4 = set(dyn_per[u] for u in n4 if dyn_per[u])
        n_dyn_3hop[v] = len(d3)
        n_dyn_4hop[v] = len(d4)
        if own:
            cross_dyn_neighbors[v] = sum(
                1 for u in g_trim.neighbors(v)
                if dyn_per[u] and dyn_per[u] != own)
        if (v + 1) % 2000 == 0:
            print(f"  {v+1}/{g_trim.vcount()} "
                  f"({time.time()-t0:.0f}s)", flush=True)

    # in_match_sample: 1 if the person appears in the AI-extracted high
    # confidence person summary. Renamed in spirit from the 5_15 regex-
    # based flag, but column name kept for downstream R compatibility.
    in_sample = set()
    p = OUT / "person_summary_ai_extracted_high.csv"
    if p.exists():
        ps = pd.read_csv(p)
        in_sample = set(ps["person_id"])
    else:
        print("  (no person_summary_ai_extracted_high.csv; "
              "in_match_sample = 0 for all)")

    print(f"\nWriting {out_path.name} ...", flush=True)
    rows = []
    for i, pid in enumerate(nodes_trim):
        info = persons.get(pid, {})
        rows.append({
            "person_id": pid, "name": info.get("name", ""),
            "sex": info.get("sex", ""),
            "birth": info.get("birth"),
            "death": info.get("death"),
            "in_match_sample": int(pid in in_sample),
            "dynasty": dyn_per[i],
            "deg": int(deg[i]),
            "log_deg": float(math.log1p(deg[i])),
            "n_dyn_3hop": int(n_dyn_3hop[i]),
            "n_dyn_4hop": int(n_dyn_4hop[i]),
            "cross_dyn_neighbors": int(cross_dyn_neighbors[i]),
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"  {len(rows):,} rows")
    print(f"\nDone in {time.time()-t0:.0f}s")
    print(f"  n_dyn_3hop  mean={np.mean(n_dyn_3hop):.2f}  "
          f"max={np.max(n_dyn_3hop)}")
    print(f"  n_dyn_4hop  mean={np.mean(n_dyn_4hop):.2f}  "
          f"max={np.max(n_dyn_4hop)}")
    print(f"  in_match_sample sum: "
          f"{sum(r['in_match_sample'] for r in rows):,}")


if __name__ == "__main__":
    main()
