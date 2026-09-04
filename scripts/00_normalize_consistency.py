"""
00_normalize_consistency.py
============================

Stage 0 of the replication pipeline.

Read the raw thePeerage scrape and emit normalized person + edge tables.
Run reciprocity consistency checks (parents must mirror children; spouses
must mirror); record what fails.

Input:
  ../data/thePeerage.csv

Outputs (in output/):
  persons.csv               id, name, sex, birth, death (no imputation)
  parent_pairs.csv          (parent_id, child_id) directed edges
                            (union of parent-claims and child-claims)
  spouse_pairs.csv          (a, b) undirected, a < b
  parent_order.csv          one row per child, preserving parent0 (father)
                            and parent1 (mother) ordering
  consistency_report.csv    summary metrics (counts, mismatch rates)

Edge handling: parent and spouse claims are recorded separately per row,
then unioned at the end. A parent claim is "mirrored" iff both halves
appear: parent P claims child C in P's child columns AND child C claims
parent P in C's parent columns. One-sided claims are retained as
legitimate edges; consistency_report.csv tallies them but does not drop
them. One-sided claims are further split by whether the silent side has
its own row in the source (a genuine inconsistency) or no row at all
(could not have reciprocated).
"""
from __future__ import annotations
import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "thePeerage.csv"
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

csv.field_size_limit(2_000_000_000)


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


def main():
    print(f"Reading {SRC} ...", flush=True)

    persons = {}
    has_own_row = set()
    # Claims recorded per-row, NOT auto-mirrored:
    child_says_parent = defaultdict(set)   # child_id -> {parents named on child's row}
    parent_says_child = defaultdict(set)   # parent_id -> {children named on parent's row}
    person_says_spouse = defaultdict(set)  # ego_id  -> {spouses named on ego's row}
    parent0 = {}
    parent1 = {}

    spouse_cols = [(f"spouse{i}_link", f"spouse{i}_name") for i in range(9)]
    child_cols = [(f"child{i}_link", f"child{i}_name") for i in range(31)]

    n_rows = 0
    for chunk in pd.read_csv(SRC, chunksize=50_000, dtype=str,
                              low_memory=False, na_filter=False):
        n_rows += len(chunk)
        for r in chunk.itertuples(index=False):
            d = r._asdict()
            pid = d.get("link", "").strip()
            if not pid:
                continue
            has_own_row.add(pid)
            name = d.get("name", "").strip()
            sex = (d.get("sex", "") or "").strip().upper()
            sex = sex if sex in ("M", "F") else ""
            birth = to_year(d.get("birth", ""))
            death = to_year(d.get("death", ""))
            if pid not in persons:
                persons[pid] = {"name": name, "sex": sex,
                                "birth": birth, "death": death}
            else:
                cur = persons[pid]
                if not cur["name"] and name:
                    cur["name"] = name
                if not cur["sex"] and sex:
                    cur["sex"] = sex
                if cur["birth"] is None and birth is not None:
                    cur["birth"] = birth
                if cur["death"] is None and death is not None:
                    cur["death"] = death

            p0 = d.get("parent0_link", "").strip()
            p1 = d.get("parent1_link", "").strip()
            if p0:
                child_says_parent[pid].add(p0)
                if pid not in parent0:
                    parent0[pid] = p0
            if p1:
                child_says_parent[pid].add(p1)
                if pid not in parent1:
                    parent1[pid] = p1

            for link_col, _ in spouse_cols:
                sp = d.get(link_col, "").strip()
                if sp:
                    person_says_spouse[pid].add(sp)

            for link_col, _ in child_cols:
                kid = d.get(link_col, "").strip()
                if kid:
                    parent_says_child[pid].add(kid)
    print(f"  raw rows: {n_rows:,}; unique persons: {len(persons):,}",
          flush=True)

    # All implied parent->child edges (union of both sides), classified.
    all_parent_edges = set()
    for c, parents in child_says_parent.items():
        for p in parents:
            all_parent_edges.add((p, c))
    for p, kids in parent_says_child.items():
        for c in kids:
            all_parent_edges.add((p, c))

    n_parent_mirrored = 0
    n_parent_child_only_other_has_row = 0   # child names parent; parent has row but is silent
    n_parent_parent_only_other_has_row = 0  # parent names child; child has row but is silent
    n_parent_child_only_other_no_row = 0    # child names parent; parent has no row
    n_parent_parent_only_other_no_row = 0   # parent names child; child has no row
    for p, c in all_parent_edges:
        child_claims = p in child_says_parent.get(c, ())
        parent_claims = c in parent_says_child.get(p, ())
        if child_claims and parent_claims:
            n_parent_mirrored += 1
        elif child_claims:
            if p in has_own_row:
                n_parent_child_only_other_has_row += 1
            else:
                n_parent_child_only_other_no_row += 1
        else:  # parent_claims only
            if c in has_own_row:
                n_parent_parent_only_other_has_row += 1
            else:
                n_parent_parent_only_other_no_row += 1
    n_parent_oneside = (n_parent_child_only_other_has_row
                        + n_parent_parent_only_other_has_row
                        + n_parent_child_only_other_no_row
                        + n_parent_parent_only_other_no_row)
    n_parent_claims = len(all_parent_edges)

    # All implied spouse edges, undirected.
    all_spouse_edges = set()
    for a, sps in person_says_spouse.items():
        for b in sps:
            if a != b:
                all_spouse_edges.add((min(a, b), max(a, b)))

    n_spouse_mirrored = 0
    n_spouse_oneside_silent_has_row = 0
    n_spouse_oneside_silent_no_row = 0
    for a, b in all_spouse_edges:
        a_claims_b = b in person_says_spouse.get(a, ())
        b_claims_a = a in person_says_spouse.get(b, ())
        if a_claims_b and b_claims_a:
            n_spouse_mirrored += 1
        else:
            silent = b if a_claims_b else a
            if silent in has_own_row:
                n_spouse_oneside_silent_has_row += 1
            else:
                n_spouse_oneside_silent_no_row += 1
    n_spouse_claims = len(all_spouse_edges)
    n_spouse_oneside = (n_spouse_oneside_silent_has_row
                        + n_spouse_oneside_silent_no_row)

    parent_pairs = sorted(all_parent_edges)
    spouse_pairs = sorted(all_spouse_edges)
    print(f"  parent edges: {len(parent_pairs):,}; "
          f"spouse edges: {len(spouse_pairs):,}", flush=True)
    print(f"  parent claims: mirrored={n_parent_mirrored:,}, "
          f"child-only (other has row)={n_parent_child_only_other_has_row:,}, "
          f"parent-only (other has row)={n_parent_parent_only_other_has_row:,}, "
          f"child-only (other missing)={n_parent_child_only_other_no_row:,}, "
          f"parent-only (other missing)={n_parent_parent_only_other_no_row:,}",
          flush=True)
    print(f"  spouse claims: mirrored={n_spouse_mirrored:,}, "
          f"one-sided silent has row={n_spouse_oneside_silent_has_row:,}, "
          f"one-sided silent missing={n_spouse_oneside_silent_no_row:,}",
          flush=True)

    with open(OUT / "persons.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "sex", "birth", "death"])
        for pid, d in persons.items():
            w.writerow([pid, d["name"], d["sex"],
                        d["birth"] if d["birth"] is not None else "",
                        d["death"] if d["death"] is not None else ""])

    with open(OUT / "parent_pairs.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["parent_id", "child_id"])
        for p, c in parent_pairs:
            w.writerow([p, c])

    with open(OUT / "spouse_pairs.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a", "b"])
        for a, b in spouse_pairs:
            w.writerow([a, b])

    with open(OUT / "parent_order.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["child_id", "parent0_id", "parent1_id"])
        all_children = set(parent0.keys()) | set(parent1.keys())
        for cid in sorted(all_children):
            w.writerow([cid, parent0.get(cid, ""), parent1.get(cid, "")])

    with open(OUT / "consistency_report.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["raw_rows", n_rows])
        w.writerow(["unique_persons", len(persons)])
        w.writerow(["parent_claims", n_parent_claims])
        w.writerow(["parent_claims_mirrored", n_parent_mirrored])
        w.writerow(["parent_claims_oneside", n_parent_oneside])
        w.writerow(["parent_claims_oneside_child_side_other_has_row",
                    n_parent_child_only_other_has_row])
        w.writerow(["parent_claims_oneside_parent_side_other_has_row",
                    n_parent_parent_only_other_has_row])
        w.writerow(["parent_claims_oneside_child_side_other_no_row",
                    n_parent_child_only_other_no_row])
        w.writerow(["parent_claims_oneside_parent_side_other_no_row",
                    n_parent_parent_only_other_no_row])
        w.writerow(["spouse_pair_claims_unique", n_spouse_claims])
        w.writerow(["spouse_pair_claims_mirrored", n_spouse_mirrored])
        w.writerow(["spouse_pair_claims_oneside", n_spouse_oneside])
        w.writerow(["spouse_pair_claims_oneside_silent_has_row",
                    n_spouse_oneside_silent_has_row])
        w.writerow(["spouse_pair_claims_oneside_silent_no_row",
                    n_spouse_oneside_silent_no_row])
        w.writerow(["parent_edges_kept", len(parent_pairs)])
        w.writerow(["spouse_edges_kept", len(spouse_pairs)])

    print(f"\nDone. Stage 0 outputs in output/:")
    for f in ("persons.csv", "parent_pairs.csv", "spouse_pairs.csv",
              "parent_order.csv", "consistency_report.csv"):
        p = OUT / f
        if p.exists():
            print(f"  {f}  ({p.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
