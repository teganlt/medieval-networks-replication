"""
04_interdyn_marriage_panel.py
==============================

Build the inter-dynastic marriage time series with Wilson 95% confidence
intervals and a fertility-weighted variant.

For each 50-yr window with 10-yr stride, 800 to 1500, count marriages
whose two spouses both have a named-dynasty assignment and compute the
inter-dynasty share of those marriages.

Two weightings:
  Unweighted: each marriage = 1.
  Fertility-weighted: each marriage = number of documented children of
                       the couple (intersection of children_of[a] and
                       children_of[b] in parent_pairs).
                       "Documented" is the only fertility signal we have;
                       no survival-to-adulthood filter is applied.

Marriage year proxy: midpoint of (a.death + b.death) / 2 when both deaths
attested (observed or imputed). Marriages are placed in window if year
falls within [window_start, window_end). The proxy is biased ~30 years
late vs actual marriage; flag this in the writeup.

Confidence intervals: Wilson 95% CI on the binomial proportion
n_inter / n_both. For the fertility-weighted variant, CIs are computed
on the analogue using the "effective N" = sum of weights, which is a
reasonable approximation when weights are non-negative integers.

Inputs (in output/):
  persons_imputed.csv
  spouse_pairs.csv
  parent_pairs.csv
  named_dynasty_assignment.csv

Output (in output/):
  interdyn_marriage_timeseries.csv

Schema:
  window_start, window_end, window_mid,
  n_marriages_total, n_both_anchored,
  n_intra_anchored, n_inter_anchored,
  frac_inter, frac_inter_ci_lo, frac_inter_ci_hi,
  n_children_intra, n_children_inter, n_children_both,
  frac_inter_fert, frac_inter_fert_ci_lo, frac_inter_fert_ci_hi
"""
from __future__ import annotations
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

WINDOW_LEN = 50
STRIDE = 10
YEAR_LO, YEAR_HI = 800, 1500


def marriage_year(ia, ib, proxy):
    """Marriage-year proxy from two spouse info dicts.
      death   = midpoint of the two death years (default; biased ~30y late)
      birth   = midpoint of the two birth years (closest to actual marriage)
      midlife = midpoint of the two per-spouse midlife years
    Returns int year, or None if a required field is missing.
    """
    if proxy == "death":
        a, b = ia["death"], ib["death"]
    elif proxy == "birth":
        a, b = ia["birth"], ib["birth"]
    elif proxy == "midlife":
        if None in (ia["birth"], ia["death"], ib["birth"], ib["death"]):
            return None
        a = (ia["birth"] + ia["death"]) / 2
        b = (ib["birth"] + ib["death"]) / 2
    else:
        raise ValueError(f"unknown proxy: {proxy}")
    if a is None or b is None:
        return None
    return int((a + b) // 2)
Z_95 = 1.959963984540054   # qnorm(0.975)


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


def wilson_ci(k, n, z=Z_95):
    """Wilson 95% CI for a binomial proportion. Returns (lo, hi)."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    halfwidth = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
                 / denom)
    return (center - halfwidth, center + halfwidth)


def load_persons():
    persons = {}
    with open(OUT / "persons_imputed.csv", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            persons[row["id"]] = {
                "birth": to_year(row["birth"]),
                "death": to_year(row["death"]),
            }
    return persons


def load_dynasty():
    dyn = {}
    with open(OUT / "named_dynasty_assignment.csv",
              encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row["dynasty"]:
                dyn[row["id"]] = row["dynasty"]
    return dyn


def load_spouse_pairs():
    pairs = []
    with open(OUT / "spouse_pairs.csv", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)
        for a, b in r:
            pairs.append((a, b))
    return pairs


def load_children_of():
    """Return children_of: parent_id -> set of child_ids."""
    children_of = defaultdict(set)
    with open(OUT / "parent_pairs.csv", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)
        for p, c in r:
            children_of[p].add(c)
    return children_of


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year-proxy", choices=["death", "birth", "midlife"],
                    default="death",
                    help="Marriage-year proxy (default death).")
    args = ap.parse_args()
    proxy = args.year_proxy
    suffix = "" if proxy == "death" else f"_{proxy}"
    print(f"Marriage-year proxy: {proxy}", flush=True)

    print("Loading ...", flush=True)
    persons = load_persons()
    dyn = load_dynasty()
    pairs = load_spouse_pairs()
    children_of = load_children_of()
    print(f"  persons: {len(persons):,}; dyn-assigned: {len(dyn):,}; "
          f"spouse pairs: {len(pairs):,}", flush=True)

    # Per-marriage record:
    #   (mid_year, dyn_a, dyn_b, n_common_children)
    marriages = []
    for a, b in pairs:
        ia = persons.get(a)
        ib = persons.get(b)
        if not ia or not ib:
            continue
        mid = marriage_year(ia, ib, proxy)
        if mid is None or mid < YEAR_LO or mid > YEAR_HI:
            continue
        dyn_a = dyn.get(a, "")
        dyn_b = dyn.get(b, "")
        n_kids = len(children_of.get(a, set()) & children_of.get(b, set()))
        marriages.append((mid, dyn_a, dyn_b, n_kids))
    print(f"  marriages with {proxy}-proxy year in [{YEAR_LO},"
          f" {YEAR_HI}]: {len(marriages):,}", flush=True)
    print(f"  mean documented children per marriage: "
          f"{np.mean([m[3] for m in marriages]):.2f}", flush=True)

    rows = []
    for ws in range(YEAR_LO, YEAR_HI - WINDOW_LEN + 1, STRIDE):
        we = ws + WINDOW_LEN
        wm = (ws + we) // 2

        # Counts
        n_total = n_both = n_intra = n_inter = 0
        # Fertility-weighted counts (= # children of in-window couples)
        c_total = c_both = c_intra = c_inter = 0
        for (yr, da, db, k) in marriages:
            if not (ws <= yr < we):
                continue
            n_total += 1
            c_total += k
            if da and db:
                n_both += 1
                c_both += k
                if da == db:
                    n_intra += 1
                    c_intra += k
                else:
                    n_inter += 1
                    c_inter += k

        frac = (n_inter / n_both) if n_both else math.nan
        ci_lo, ci_hi = wilson_ci(n_inter, n_both)

        # Fertility-weighted Wilson CI uses effective N = c_both
        # (sum of weights). Reasonable for integer weights >= 0.
        frac_fert = (c_inter / c_both) if c_both else math.nan
        fci_lo, fci_hi = wilson_ci(c_inter, c_both)

        rows.append((ws, we, wm, n_total, n_both, n_intra, n_inter,
                     frac, ci_lo, ci_hi,
                     c_intra, c_inter, c_both,
                     frac_fert, fci_lo, fci_hi))

    df = pd.DataFrame(rows, columns=[
        "window_start", "window_end", "window_mid",
        "n_marriages_total", "n_both_anchored",
        "n_intra_anchored", "n_inter_anchored",
        "frac_inter", "frac_inter_ci_lo", "frac_inter_ci_hi",
        "n_children_intra", "n_children_inter", "n_children_both",
        "frac_inter_fert", "frac_inter_fert_ci_lo", "frac_inter_fert_ci_hi",
    ])
    out_path = OUT / f"interdyn_marriage_timeseries{suffix}.csv"
    df.to_csv(out_path, index=False)
    print(f"\nWrote {out_path.name} ({len(df)} windows)")

    print("\nKey years (inter-dyn share among both-anchored, "
          "with 95% Wilson CI):")
    for ws_target in (900, 1000, 1050, 1100, 1150, 1200, 1250, 1300, 1400):
        match = df[df["window_mid"] >= ws_target].head(1)
        if match.empty:
            continue
        r = match.iloc[0]
        if r.n_both_anchored == 0:
            continue
        print(f"  win {int(r.window_start)}-{int(r.window_end)} "
              f"(mid {int(r.window_mid)}): "
              f"n_both={int(r.n_both_anchored):>4}  "
              f"frac={r.frac_inter:.1%} "
              f"[{r.frac_inter_ci_lo:.1%}, {r.frac_inter_ci_hi:.1%}]  "
              f"fert={r.frac_inter_fert:.1%} "
              f"[{r.frac_inter_fert_ci_lo:.1%}, "
              f"{r.frac_inter_fert_ci_hi:.1%}]")


if __name__ == "__main__":
    main()
