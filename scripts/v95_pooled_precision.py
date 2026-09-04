"""v95_pooled_precision.py — pooled human match-audit precision (phase 1).

Pools the researcher's 100 stratified match verdicts (validation/audit_blitz,
items Z001-Z100, built by v94 with seed 43) with the research assistant's
blind 100 (validation/audit_ra_partial, items M001-M100, built by v90 with
seed 42; the RA-facing copy had the stratum column stripped for blinding --
the stratum-bearing items file ships here).

Reproduces the draft's audit numbers:
  - per-coder precision (y / (y+n), unsure excluded)
  - pooled precision + exact (Clopper-Pearson) 95% binomial interval
  - Fisher exact test comparing the two coders
  - precision by reach tercile (pooled across eras and coders)

Reads   validation/audit_blitz/match_audit_{items,verdicts}.csv
        validation/audit_ra_partial/match_audit_{items,verdicts}.csv
Writes  output/pooled_audit_precision.csv  (+ console report)
"""
from __future__ import annotations
import csv
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
VAL = ROOT / "validation"
OUT = ROOT / "output"
csv.field_size_limit(2_147_483_647)

def load(folder):
    items = {}
    with (VAL / folder / "match_audit_items.csv").open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            items[r["item_id"]] = r
    verdicts = []
    with (VAL / folder / "match_audit_verdicts.csv").open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            v = r["verdict"].strip().lower()
            if v not in ("y", "n", "u"):
                continue
            verdicts.append({"item_id": r["item_id"], "verdict": v,
                             "stratum": items.get(r["item_id"], {}).get("stratum", "")})
    return verdicts

blitz = load("audit_blitz")          # researcher
ra = load("audit_ra_partial")        # research assistant

def tally(rows):
    y = sum(1 for r in rows if r["verdict"] == "y")
    n = sum(1 for r in rows if r["verdict"] == "n")
    u = sum(1 for r in rows if r["verdict"] == "u")
    return y, n, u

def exact_ci(y, m, alpha=0.05):
    lo = stats.beta.ppf(alpha / 2, y, m - y + 1) if y > 0 else 0.0
    hi = stats.beta.ppf(1 - alpha / 2, y + 1, m - y) if y < m else 1.0
    return lo, hi

rows_out = []
print("== per-coder ==")
for lab, rows in (("researcher (blitz)", blitz), ("research assistant", ra)):
    y, n, u = tally(rows)
    print(f"  {lab}: {y}/{y+n} correct ({u} unsure excluded)  precision {y/(y+n):.3f}")
    rows_out.append({"group": lab, "y": y, "n": n, "u": u, "precision": y / (y + n)})

y1, n1, _ = tally(blitz)
y2, n2, _ = tally(ra)
y, n = y1 + y2, n1 + n2
m = y + n
lo, hi = exact_ci(y, m)
_, fisher_p = stats.fisher_exact([[y1, n1], [y2, n2]])
print(f"\n== pooled ==\n  {y}/{m} = {y/m:.3f}  exact 95% CI [{100*lo:.1f}, {100*hi:.1f}]")
print(f"  Fisher exact (coder 1 vs coder 2): p = {fisher_p:.2f}")
rows_out.append({"group": "pooled", "y": y, "n": n, "u": tally(blitz)[2] + tally(ra)[2],
                 "precision": y / m, "ci_lo": lo, "ci_hi": hi, "fisher_p": fisher_p})

print("\n== precision by reach stratum (pooled coders + eras; unsure excluded) ==")
by = {}
for r in blitz + ra:
    strat = r["stratum"].split("|")[-1] if r["stratum"] else "unknown"
    by.setdefault(strat, []).append(r)
for strat in sorted(by):
    y, n, u = tally(by[strat])
    if y + n == 0:
        continue
    print(f"  {strat:15s}: {y}/{y+n} = {y/(y+n):.3f}")
    rows_out.append({"group": f"stratum:{strat}", "y": y, "n": n, "u": u,
                     "precision": y / (y + n)})

OUT.mkdir(exist_ok=True)
fields = ["group", "y", "n", "u", "precision", "ci_lo", "ci_hi", "fisher_p"]
with (OUT / "pooled_audit_precision.csv").open("w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    for r in rows_out:
        w.writerow(r)
print(f"\nwrote output/pooled_audit_precision.csv")
