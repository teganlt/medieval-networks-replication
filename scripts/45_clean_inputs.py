"""
45_clean_inputs.py
===================

Build the two CLEAN inputs the cleaned-up headline IV needs that the
canonical pipeline does not already provide:

  (A) output/clean_iv/person_doc_counts_inwin.csv
        Per person_id, document-appearance counts restricted to papal
        letters ISSUED in [1100, 1300] (the user's sample window).
        The canonical person_summary_* files count ALL years
        [1049, 1380]; ~11% of matches (and ~10% of dispute matches)
        fall outside 1100-1300.  Columns:
          person_id,
          n_total_inwin,                  all in-window matches
          n_dispute_inwin,                matches tagged 'dispute'
          n_nondispute_inwin,             total - dispute  (the split)
          n_<subject>_inwin               per-subject in-window counts
        Used for BOTH the focal outcomes and the parental prominence
        controls (mother/father/MGF dispute + non-dispute volume), so
        every document count in the regression respects 1100-1300.

  (B) output/clean_iv/focal_node_size.csv
        Per node in the stage-17 active subgraph, the network SIZE
        (head-count of distinct OTHER persons) within 3 and 4 hops:
          person_id, deg, n_dyn_3hop, n_dyn_4hop, n_nodes_3hop,
          n_nodes_4hop
        network_nodes_4hop.csv ships n_dyn (reach = #distinct dynasties)
        but NOT n_nodes (size = #persons).  The clean spec controls for
        the focal's "N within 4 hops" (size), distinct from the
        instrumented reach.  deg/n_dyn re-emitted for cross-checking
        against network_nodes_4hop.csv (must match exactly).

Graph construction in (B) is a byte-for-byte copy of stage 17's active
subgraph (lifespan overlaps [1100,1300] U 1-hop kin, simplify, drop
isolates) so n_nodes shares the identical denominator with the canonical
n_dyn.

Reads (output/):
  doc_matches_ai_extracted_high.csv   (match-level, has doc_year + subjects)
  persons_imputed.csv, parent_pairs.csv, spouse_pairs.csv
  named_dynasty_assignment.csv        (only for the n_dyn cross-check)

CLI:  python 45_clean_inputs.py
"""
from __future__ import annotations
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
CLEAN = OUT / "clean_iv"
CLEAN.mkdir(exist_ok=True)

WINDOW_LO = 1100
WINDOW_HI = 1300
MAX_HOPS = 4

SUBJECTS = ["marriage", "excommunication", "inheritance", "dispute",
            "crusade", "clerical_discipline", "ecclesiastical_property"]


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


# ----------------------------------------------------------------------
# (A) in-window per-person document counts
# ----------------------------------------------------------------------
def build_doc_counts():
    print("(A) Building in-window document counts [1100,1300] ...", flush=True)
    dm = pd.read_csv(OUT / "doc_matches_ai_extracted_high.csv")
    yr = pd.to_numeric(dm["doc_year"], errors="coerce")
    inwin = yr.between(WINDOW_LO, WINDOW_HI)
    print(f"  matches total={len(dm):,}  in-window={int(inwin.sum()):,}  "
          f"dropped={int((~inwin).sum()):,}")
    dmw = dm[inwin].copy()

    def subj_set(s):
        if not isinstance(s, str) or s == "":
            return set()
        return set(s.split(";"))
    dmw["subjset"] = dmw["inferred_subjects"].apply(subj_set)

    rows = {}
    for pid, grp in dmw.groupby("person_id"):
        rec = {"person_id": pid, "n_total_inwin": len(grp)}
        for s in SUBJECTS:
            rec[f"n_{s}_inwin"] = int(grp["subjset"].apply(
                lambda ss: s in ss).sum())
        rec["n_nondispute_inwin"] = rec["n_total_inwin"] - rec["n_dispute_inwin"]
        rows[pid] = rec
    out = pd.DataFrame(list(rows.values()))
    cols = (["person_id", "n_total_inwin", "n_dispute_inwin",
             "n_nondispute_inwin"]
            + [f"n_{s}_inwin" for s in SUBJECTS if s != "dispute"])
    out = out[cols].sort_values("person_id")
    out.to_csv(CLEAN / "person_doc_counts_inwin.csv", index=False)
    print(f"  wrote person_doc_counts_inwin.csv  ({len(out):,} persons w/ "
          f">=1 in-window match)")
    print(f"    sum dispute={int(out.n_dispute_inwin.sum()):,}  "
          f"nondispute={int(out.n_nondispute_inwin.sum()):,}  "
          f"total={int(out.n_total_inwin.sum()):,}")


# ----------------------------------------------------------------------
# (B) focal node sizes (n_nodes within k hops), stage-17 active subgraph
# ----------------------------------------------------------------------
def load_persons():
    persons = {}
    with open(OUT / "persons_imputed.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            persons[row["id"]] = {
                "name": row["name"], "sex": row["sex"],
                "birth": to_year(row["birth"]), "death": to_year(row["death"]),
            }
    return persons


def load_edges():
    parent_pairs, spouse_pairs = [], []
    adj = defaultdict(set)
    with open(OUT / "parent_pairs.csv", encoding="utf-8") as f:
        r = csv.reader(f); next(r)
        for p, c in r:
            parent_pairs.append((p, c)); adj[p].add(c); adj[c].add(p)
    with open(OUT / "spouse_pairs.csv", encoding="utf-8") as f:
        r = csv.reader(f); next(r)
        for a, b in r:
            spouse_pairs.append((a, b)); adj[a].add(b); adj[b].add(a)
    return parent_pairs, spouse_pairs, adj


def load_dynasty():
    dyn = {}
    with open(OUT / "named_dynasty_assignment.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["dynasty"]:
                dyn[row["id"]] = row["dynasty"]
    return dyn


def lifespan_overlaps(info, lo, hi):
    b, d = info["birth"], info["death"]
    if b is None or d is None:
        return False
    return b <= hi and d >= lo


def build_node_sizes():
    print("\n(B) Building focal node sizes (stage-17 active subgraph) ...",
          flush=True)
    t0 = time.time()
    persons = load_persons()
    parent_pairs, spouse_pairs, adj = load_edges()
    dyn_assign = load_dynasty()

    # ---- active subgraph: identical convention to stage 17 ----
    L = {pid for pid, info in persons.items()
         if lifespan_overlaps(info, WINDOW_LO, WINDOW_HI)}
    expanded = set(L)
    for pid in L:
        expanded.update(adj.get(pid, ()))
    expanded &= persons.keys()

    nodes_sorted = sorted(expanded)
    idx = {pid: i for i, pid in enumerate(nodes_sorted)}
    edges = set()
    for a, b in parent_pairs:
        if a in idx and b in idx:
            i, j = idx[a], idx[b]; edges.add((min(i, j), max(i, j)))
    for a, b in spouse_pairs:
        if a in idx and b in idx and a != b:
            i, j = idx[a], idx[b]; edges.add((min(i, j), max(i, j)))
    g = ig.Graph(n=len(nodes_sorted), edges=list(edges), directed=False)
    g.simplify(multiple=True, loops=True)

    deg_pre = np.array(g.degree())
    keep = np.where(deg_pre > 0)[0]
    g_trim = g.subgraph(keep)
    nodes_trim = [nodes_sorted[i] for i in keep]
    deg = np.array(g_trim.degree())
    print(f"  V_trim={g_trim.vcount():,}  E_trim={g_trim.ecount():,} "
          f"({time.time()-t0:.0f}s)", flush=True)

    dyn_per = np.array([dyn_assign.get(nodes_trim[i], "")
                        for i in range(len(nodes_trim))])
    rows = []
    for v in range(g_trim.vcount()):
        n3 = g_trim.neighborhood(v, order=3)
        n4 = g_trim.neighborhood(v, order=4)
        d3 = len({dyn_per[u] for u in n3 if dyn_per[u]})
        d4 = len({dyn_per[u] for u in n4 if dyn_per[u]})
        rows.append({
            "person_id": nodes_trim[v],
            "deg": int(deg[v]),
            "n_dyn_3hop": int(d3), "n_dyn_4hop": int(d4),
            "n_nodes_3hop": int(len(n3) - 1),   # exclude ego
            "n_nodes_4hop": int(len(n4) - 1),
        })
        if (v + 1) % 4000 == 0:
            print(f"  {v+1}/{g_trim.vcount()} ({time.time()-t0:.0f}s)",
                  flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(CLEAN / "focal_node_size.csv", index=False)
    print(f"  wrote focal_node_size.csv  ({len(out):,} nodes)")
    print(f"    n_nodes_4hop mean={out.n_nodes_4hop.mean():.1f} "
          f"max={out.n_nodes_4hop.max()}")

    # cross-check n_dyn against canonical network_nodes_4hop.csv
    nn = pd.read_csv(OUT / "network_nodes_4hop.csv")[
        ["person_id", "deg", "n_dyn_3hop", "n_dyn_4hop"]]
    chk = out.merge(nn, on="person_id", suffixes=("_new", "_canon"))
    for c in ["deg", "n_dyn_3hop", "n_dyn_4hop"]:
        mism = int((chk[f"{c}_new"] != chk[f"{c}_canon"]).sum())
        print(f"    cross-check {c}: {mism} mismatches of {len(chk)}")


if __name__ == "__main__":
    build_doc_counts()
    build_node_sizes()
    print("\nDone.")
