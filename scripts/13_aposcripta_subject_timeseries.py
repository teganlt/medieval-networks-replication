"""
13_aposcripta_subject_timeseries.py
====================================

Build share-over-time panels for the mandement genre flag and the 7
subject classifications from APOSCRIPTA, with Wilson 95% confidence
intervals to reflect per-window sample size variance.

For each 50-yr window with 10-yr stride, 800 to 1500:
  - n_total_docs = papal docs whose year falls in the window
  - For each flag F in {mandement, marriage, excommunication,
    inheritance, dispute, crusade, clerical_discipline,
    ecclesiastical_property}:
        n_F            count of in-window docs with F=1
        share_F        binomial proportion n_F / n_total_docs
        share_F_ci_lo  Wilson 95% lower bound
        share_F_ci_hi  Wilson 95% upper bound

Both observed-year and pope-reign-imputed-year docs are included. The
year_imputed docs concentrate at pope-midpoint years, which slightly
clusters them but does not bias within-window proportion estimates.

Inputs (in output/):
  aposcripta_per_doc.csv

Output (in output/):
  aposcripta_subject_timeseries.csv

Schema:
  window_start, window_end, window_mid, n_total_docs,
  n_mandement, share_mandement, share_mandement_ci_lo, share_mandement_ci_hi,
  n_marriage,  share_marriage,  ...
  ... (etc. for all 8 flags)
"""
from __future__ import annotations
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

WINDOW_LEN = 50
STRIDE = 10
YEAR_LO, YEAR_HI = 800, 1500
Z_95 = 1.959963984540054

FLAGS = [
    "mandement",
    "marriage",
    "excommunication",
    "inheritance",
    "dispute",
    "crusade",
    "clerical_discipline",
    "ecclesiastical_property",
]


def wilson_ci(k, n, z=Z_95):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    halfwidth = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
                 / denom)
    return (center - halfwidth, center + halfwidth)


def main():
    print("Loading aposcripta_per_doc.csv ...", flush=True)
    df = pd.read_csv(OUT / "aposcripta_per_doc.csv")
    df = df[df["year"].notna()]
    df["year"] = df["year"].astype(int)
    df = df[(df["year"] >= YEAR_LO) & (df["year"] <= YEAR_HI)]
    print(f"  docs in [{YEAR_LO}, {YEAR_HI}]: {len(df):,}", flush=True)

    for f in FLAGS:
        col = f"is_{f}"
        if col not in df.columns:
            raise SystemExit(f"missing column: {col}")
        df[col] = df[col].fillna(0).astype(int)

    rows = []
    for ws in range(YEAR_LO, YEAR_HI - WINDOW_LEN + 1, STRIDE):
        we = ws + WINDOW_LEN
        wm = (ws + we) // 2
        sub = df[(df["year"] >= ws) & (df["year"] < we)]
        n_total = len(sub)
        row = {"window_start": ws, "window_end": we, "window_mid": wm,
               "n_total_docs": n_total}
        for f in FLAGS:
            k = int(sub[f"is_{f}"].sum()) if n_total else 0
            share = (k / n_total) if n_total else math.nan
            lo, hi = wilson_ci(k, n_total)
            row[f"n_{f}"] = k
            row[f"share_{f}"] = share
            row[f"share_{f}_ci_lo"] = lo
            row[f"share_{f}_ci_hi"] = hi
        rows.append(row)

    out_df = pd.DataFrame(rows)
    out_path = OUT / "aposcripta_subject_timeseries.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\nWrote {out_path.name} ({len(out_df)} windows)")

    print("\nKey years (share + Wilson 95% CI):")
    for wm_target in (1050, 1100, 1150, 1200, 1250, 1300, 1400):
        row = out_df[out_df["window_mid"] >= wm_target].head(1)
        if row.empty:
            continue
        r = row.iloc[0]
        n = int(r.n_total_docs)
        if n == 0:
            continue
        mand = (r.share_mandement, r.share_mandement_ci_lo,
                r.share_mandement_ci_hi)
        disp = (r.share_dispute, r.share_dispute_ci_lo,
                r.share_dispute_ci_hi)
        print(f"  mid {int(r.window_mid)} (n={n:>5}): "
              f"mandement={mand[0]:.1%} [{mand[1]:.1%}, {mand[2]:.1%}]  "
              f"dispute={disp[0]:.1%} [{disp[1]:.1%}, {disp[2]:.1%}]")


if __name__ == "__main__":
    main()
