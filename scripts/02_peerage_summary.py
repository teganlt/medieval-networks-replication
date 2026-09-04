"""
02_peerage_summary.py
======================

Descriptive summary statistics for the imputed peerage dataset, with
explicit observed-vs-imputed flagging throughout.

Outputs are written as a series of small, modular CSV tables under
output/peerage_summary/. Each file addresses one slice; you can paste
any single table into the paper or appendix in isolation.

Cohort definitions (all three computed side-by-side; "lived_in" is the
headline):

  born_in_800_1500   800 <= birth <= 1500 (observed or imputed)
  died_in_800_1500   800 <= death <= 1500 (observed or imputed)
  lived_in_800_1500  the [birth, death] interval overlaps [800, 1500];
                     i.e. birth <= 1500 AND death >= 800.
                     This is the inclusive "alive at some point in the
                     window" definition. Persons missing both bounds
                     after imputation are excluded.

Imputation flag conventions (from 01_impute.py):
  birth_imputed in {0, 1}   1 = filled by Stage 1 imputer
  death_imputed in {0, 1}   1 = filled by Stage 1 imputer
  empty year + flag == 0    still missing
A person is "fully observed" if birth_imputed == 0 AND death_imputed == 0
AND both year fields are non-empty.

Inputs (in output/):
  persons_imputed.csv   from 01_impute.py
  parent_pairs.csv      from 00_normalize_consistency.py
  spouse_pairs.csv      from 00_normalize_consistency.py
  consistency_report.csv (optional, passed through to 09_)
  imputation_validation_metrics.csv (optional, passed through to 10_)

Outputs (in output/peerage_summary/):
  01_global_counts.csv             headline numbers (no time filter)
  02_cohorts_800_1500.csv          three cohort definitions side-by-side
  03_lived_in_by_century.csv       per-century breakdown of headline cohort
  04_imputation_rates.csv          imputation rates within cohort, by sex
  05_kin_degree_stats.csv          parent/child/spouse degree quantiles
  06_kin_degree_histograms.csv     long-format degree histograms
  07_lifespan_quantiles.csv        lifespan quantiles by sex x imputation
  08_decade_panel.csv              per-decade birth/death counts (time series)
  09_edge_consistency.csv          pass-through of consistency_report.csv
  10_imputation_validation.csv     pass-through of validation metrics
  peerage_summary.md               one-page narrative summary

Usage:
  python 02_peerage_summary.py
"""
from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
SUMMARY_DIR = OUT / "peerage_summary"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_LO = 800
WINDOW_HI = 1500


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_persons():
    """Load persons_imputed.csv with year columns as nullable ints."""
    df = pd.read_csv(OUT / "persons_imputed.csv", dtype={"id": str,
                                                           "name": str,
                                                           "sex": str})
    df["birth"] = pd.to_numeric(df["birth"], errors="coerce").astype("Int64")
    df["death"] = pd.to_numeric(df["death"], errors="coerce").astype("Int64")
    df["birth_imputed"] = df["birth_imputed"].fillna(0).astype(int)
    df["death_imputed"] = df["death_imputed"].fillna(0).astype(int)
    df["sex"] = df["sex"].fillna("").astype(str)
    df["name"] = df["name"].fillna("").astype(str)
    return df


def load_edges():
    """Load parent/spouse edges; compute per-person degree."""
    pp = pd.read_csv(OUT / "parent_pairs.csv", dtype=str)
    sp = pd.read_csv(OUT / "spouse_pairs.csv", dtype=str)

    n_parents = pp.groupby("child_id").size().rename("n_parents")
    n_children = pp.groupby("parent_id").size().rename("n_children")

    # Spouses: undirected; count appearances in either column.
    sp_long = pd.concat([sp["a"], sp["b"]], ignore_index=True)
    n_spouses = sp_long.value_counts().rename("n_spouses")
    n_spouses.index.name = "id"

    # Siblings: 2 children of the same parent are siblings.
    sibs = defaultdict(set)
    for parent_id, group in pp.groupby("parent_id"):
        kids = list(group["child_id"])
        for i, k in enumerate(kids):
            for k2 in kids[i + 1:]:
                sibs[k].add(k2)
                sibs[k2].add(k)
    n_siblings = pd.Series(
        {pid: len(s) for pid, s in sibs.items()}, name="n_siblings"
    )
    n_siblings.index.name = "id"

    return n_parents, n_children, n_spouses, n_siblings


# --------------------------------------------------------------------------
# Cohort definitions
# --------------------------------------------------------------------------

def add_cohort_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add 0/1 cohort membership columns based on imputed birth/death."""
    has_birth = df["birth"].notna()
    has_death = df["death"].notna()

    born_in = has_birth & df["birth"].between(WINDOW_LO, WINDOW_HI)
    died_in = has_death & df["death"].between(WINDOW_LO, WINDOW_HI)
    # Interval overlap: need birth <= 1500 AND death >= 800.
    # A person with only one bound is included if that bound is consistent
    # with overlap (e.g. only birth observed and birth <= 1500, we assume
    # the standard LIFESPAN extension already happened in 01_impute.py;
    # so by this point both bounds should be present for anyone we know
    # anything about).
    lived_in = (has_birth & has_death
                & (df["birth"] <= WINDOW_HI)
                & (df["death"] >= WINDOW_LO))

    df = df.copy()
    df["born_in_800_1500"] = born_in.astype(int)
    df["died_in_800_1500"] = died_in.astype(int)
    df["lived_in_800_1500"] = lived_in.astype(int)
    df["fully_observed"] = ((df["birth_imputed"] == 0)
                            & (df["death_imputed"] == 0)
                            & has_birth & has_death).astype(int)
    df["any_imputed"] = ((df["birth_imputed"] == 1)
                         | (df["death_imputed"] == 1)).astype(int)
    return df


# --------------------------------------------------------------------------
# Table 01: global headline counts (no time filter)
# --------------------------------------------------------------------------

def table_global_counts(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n = len(df)
    rows.append(("total_persons", n))
    rows.append(("has_name", int((df["name"] != "").sum())))
    rows.append(("sex_male", int((df["sex"] == "M").sum())))
    rows.append(("sex_female", int((df["sex"] == "F").sum())))
    rows.append(("sex_missing", int(((df["sex"] != "M") & (df["sex"] != "F")).sum())))
    rows.append(("birth_observed", int((df["birth"].notna() & (df["birth_imputed"] == 0)).sum())))
    rows.append(("birth_imputed", int(df["birth_imputed"].sum())))
    rows.append(("birth_missing", int(df["birth"].isna().sum())))
    rows.append(("death_observed", int((df["death"].notna() & (df["death_imputed"] == 0)).sum())))
    rows.append(("death_imputed", int(df["death_imputed"].sum())))
    rows.append(("death_missing", int(df["death"].isna().sum())))
    rows.append(("both_observed", int(df["fully_observed"].sum())))
    rows.append(("any_imputed", int(df["any_imputed"].sum())))
    rows.append(("no_date_after_imputation",
                 int((df["birth"].isna() & df["death"].isna()).sum())))
    rows.append(("born_in_800_1500", int(df["born_in_800_1500"].sum())))
    rows.append(("died_in_800_1500", int(df["died_in_800_1500"].sum())))
    rows.append(("lived_in_800_1500", int(df["lived_in_800_1500"].sum())))
    return pd.DataFrame(rows, columns=["metric", "value"])


# --------------------------------------------------------------------------
# Table 02: three cohort definitions side-by-side
# --------------------------------------------------------------------------

def cohort_breakdown(df_co: pd.DataFrame) -> dict:
    """Compute counts/sex/imputation status for one cohort frame."""
    return {
        "n": len(df_co),
        "male": int((df_co["sex"] == "M").sum()),
        "female": int((df_co["sex"] == "F").sum()),
        "sex_missing": int(((df_co["sex"] != "M") & (df_co["sex"] != "F")).sum()),
        "birth_observed": int((df_co["birth"].notna() & (df_co["birth_imputed"] == 0)).sum()),
        "birth_imputed": int(df_co["birth_imputed"].sum()),
        "death_observed": int((df_co["death"].notna() & (df_co["death_imputed"] == 0)).sum()),
        "death_imputed": int(df_co["death_imputed"].sum()),
        "fully_observed": int(df_co["fully_observed"].sum()),
        "any_imputed": int(df_co["any_imputed"].sum()),
    }


def table_cohorts(df: pd.DataFrame) -> pd.DataFrame:
    born = df[df["born_in_800_1500"] == 1]
    died = df[df["died_in_800_1500"] == 1]
    lived = df[df["lived_in_800_1500"] == 1]
    rows = []
    for label, frame in [("born_in_800_1500", born),
                         ("died_in_800_1500", died),
                         ("lived_in_800_1500", lived)]:
        stats = cohort_breakdown(frame)
        for metric, value in stats.items():
            rows.append((label, metric, value))
    return pd.DataFrame(rows, columns=["cohort", "metric", "value"])


# --------------------------------------------------------------------------
# Table 03: per-century breakdown of headline cohort
# --------------------------------------------------------------------------

def table_by_century(df: pd.DataFrame) -> pd.DataFrame:
    co = df[df["lived_in_800_1500"] == 1].copy()
    co["birth_century"] = ((co["birth"] // 100) * 100).astype("Int64")
    rows = []
    for century, group in co.groupby("birth_century", dropna=True):
        rows.append({
            "birth_century": int(century),
            "n": len(group),
            "male": int((group["sex"] == "M").sum()),
            "female": int((group["sex"] == "F").sum()),
            "sex_missing": int(((group["sex"] != "M") & (group["sex"] != "F")).sum()),
            "birth_observed": int((group["birth_imputed"] == 0).sum()),
            "birth_imputed": int(group["birth_imputed"].sum()),
            "death_observed": int((group["death"].notna()
                                   & (group["death_imputed"] == 0)).sum()),
            "death_imputed": int(group["death_imputed"].sum()),
            "fully_observed": int(group["fully_observed"].sum()),
        })
    return pd.DataFrame(rows).sort_values("birth_century")


# --------------------------------------------------------------------------
# Table 04: imputation rates within headline cohort
# --------------------------------------------------------------------------

def table_imputation_rates(df: pd.DataFrame) -> pd.DataFrame:
    co = df[df["lived_in_800_1500"] == 1]
    rows = []
    for label, group in [("all", co),
                         ("male", co[co["sex"] == "M"]),
                         ("female", co[co["sex"] == "F"]),
                         ("sex_missing", co[(co["sex"] != "M") & (co["sex"] != "F")])]:
        n = len(group)
        rows.append({
            "subset": label,
            "n": n,
            "birth_imputed_rate": (group["birth_imputed"].mean() if n else None),
            "death_imputed_rate": (group["death_imputed"].mean() if n else None),
            "any_imputed_rate": (group["any_imputed"].mean() if n else None),
            "fully_observed_rate": (group["fully_observed"].mean() if n else None),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Tables 05 + 06: kin degree distributions
# --------------------------------------------------------------------------

def attach_degrees(df: pd.DataFrame, n_parents, n_children, n_spouses, n_siblings):
    df = df.merge(n_parents, left_on="id", right_index=True, how="left")
    df = df.merge(n_children, left_on="id", right_index=True, how="left")
    df = df.merge(n_spouses, left_on="id", right_index=True, how="left")
    df = df.merge(n_siblings, left_on="id", right_index=True, how="left")
    for col in ("n_parents", "n_children", "n_spouses", "n_siblings"):
        df[col] = df[col].fillna(0).astype(int)
    return df


def table_degree_stats(df: pd.DataFrame) -> pd.DataFrame:
    co = df[df["lived_in_800_1500"] == 1]
    rows = []
    for col in ("n_parents", "n_children", "n_spouses", "n_siblings"):
        s = co[col]
        rows.append({
            "relation": col,
            "n": len(s),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "p75": float(s.quantile(0.75)),
            "p90": float(s.quantile(0.90)),
            "p99": float(s.quantile(0.99)),
            "max": int(s.max()),
            "share_zero": float((s == 0).mean()),
            "share_ge1": float((s >= 1).mean()),
        })
    return pd.DataFrame(rows)


def table_degree_histograms(df: pd.DataFrame) -> pd.DataFrame:
    co = df[df["lived_in_800_1500"] == 1]
    rows = []
    for col in ("n_parents", "n_children", "n_spouses", "n_siblings"):
        counts = co[col].value_counts().sort_index()
        for deg, n in counts.items():
            rows.append({"relation": col, "degree": int(deg), "n": int(n)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Table 07: lifespan quantiles
# --------------------------------------------------------------------------

def table_lifespan(df: pd.DataFrame) -> pd.DataFrame:
    co = df[df["lived_in_800_1500"] == 1].copy()
    co = co[co["birth"].notna() & co["death"].notna()]
    co["lifespan"] = (co["death"] - co["birth"]).astype(int)
    # Trim implausible (negative or > 110) before reporting:
    co_trim = co[(co["lifespan"] >= 0) & (co["lifespan"] <= 110)]
    rows = []
    for label, group in [
        ("fully_observed_all", co_trim[co_trim["fully_observed"] == 1]),
        ("fully_observed_male", co_trim[(co_trim["fully_observed"] == 1)
                                         & (co_trim["sex"] == "M")]),
        ("fully_observed_female", co_trim[(co_trim["fully_observed"] == 1)
                                           & (co_trim["sex"] == "F")]),
        ("any_imputed_all", co_trim[co_trim["any_imputed"] == 1]),
        ("any_imputed_male", co_trim[(co_trim["any_imputed"] == 1)
                                      & (co_trim["sex"] == "M")]),
        ("any_imputed_female", co_trim[(co_trim["any_imputed"] == 1)
                                        & (co_trim["sex"] == "F")]),
    ]:
        n = len(group)
        if n == 0:
            rows.append({"subset": label, "n": 0, "mean": None, "p10": None,
                         "p25": None, "p50": None, "p75": None, "p90": None})
            continue
        s = group["lifespan"]
        rows.append({
            "subset": label,
            "n": n,
            "mean": float(s.mean()),
            "p10": float(s.quantile(0.10)),
            "p25": float(s.quantile(0.25)),
            "p50": float(s.quantile(0.50)),
            "p75": float(s.quantile(0.75)),
            "p90": float(s.quantile(0.90)),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Table 08: per-decade panel (for time-series figures)
# --------------------------------------------------------------------------

def table_decade_panel(df: pd.DataFrame) -> pd.DataFrame:
    co = df[df["lived_in_800_1500"] == 1].copy()
    co["birth_decade"] = ((co["birth"] // 10) * 10).astype("Int64")
    co["death_decade"] = ((co["death"] // 10) * 10).astype("Int64")

    birth_rows = []
    for decade, group in co.groupby("birth_decade", dropna=True):
        birth_rows.append({
            "decade": int(decade),
            "field": "birth",
            "n_total": len(group),
            "n_observed": int((group["birth_imputed"] == 0).sum()),
            "n_imputed": int(group["birth_imputed"].sum()),
            "n_male": int((group["sex"] == "M").sum()),
            "n_female": int((group["sex"] == "F").sum()),
        })

    death_rows = []
    for decade, group in co.groupby("death_decade", dropna=True):
        death_rows.append({
            "decade": int(decade),
            "field": "death",
            "n_total": len(group),
            "n_observed": int((group["death_imputed"] == 0).sum()),
            "n_imputed": int(group["death_imputed"].sum()),
            "n_male": int((group["sex"] == "M").sum()),
            "n_female": int((group["sex"] == "F").sum()),
        })

    panel = pd.DataFrame(birth_rows + death_rows)
    return panel.sort_values(["field", "decade"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# Tables 09 + 10: pass-throughs
# --------------------------------------------------------------------------

def passthrough(name: str) -> pd.DataFrame | None:
    p = OUT / name
    if not p.exists():
        return None
    return pd.read_csv(p)


# --------------------------------------------------------------------------
# Markdown summary
# --------------------------------------------------------------------------

def write_markdown_summary(global_counts, cohorts, by_century,
                            imputation_rates, lifespan, validation):
    lines = []
    lines.append("# Peerage descriptive summary\n")
    lines.append("Generated by `02_peerage_summary.py`. ")
    lines.append("All tables are in `output/peerage_summary/`; this file is a ")
    lines.append("one-page narrative companion.\n")

    g = dict(zip(global_counts["metric"], global_counts["value"]))
    lines.append("## Headline counts (full dataset, no time filter)\n")
    lines.append(f"- Total persons: **{g['total_persons']:,}**")
    lines.append(f"- Birth observed: {g['birth_observed']:,} ; "
                 f"birth imputed: {g['birth_imputed']:,} ; "
                 f"birth missing: {g['birth_missing']:,}")
    lines.append(f"- Death observed: {g['death_observed']:,} ; "
                 f"death imputed: {g['death_imputed']:,} ; "
                 f"death missing: {g['death_missing']:,}")
    lines.append(f"- Both observed: {g['both_observed']:,} ; "
                 f"any imputed: {g['any_imputed']:,} ; "
                 f"no date after imputation: {g['no_date_after_imputation']:,}")
    lines.append(f"- Lived in 800-1500 (headline cohort): "
                 f"**{g['lived_in_800_1500']:,}**\n")

    lines.append("## Headline cohort (lived 800-1500)\n")
    lived_stats = cohorts[cohorts["cohort"] == "lived_in_800_1500"]
    s = dict(zip(lived_stats["metric"], lived_stats["value"]))
    lines.append(f"- N = **{s['n']:,}** "
                 f"(M={s['male']:,}, F={s['female']:,}, "
                 f"sex missing={s['sex_missing']:,})")
    lines.append(f"- Birth observed: {s['birth_observed']:,} ; "
                 f"imputed: {s['birth_imputed']:,}")
    lines.append(f"- Death observed: {s['death_observed']:,} ; "
                 f"imputed: {s['death_imputed']:,}")
    lines.append(f"- Fully observed (both birth and death attested): "
                 f"{s['fully_observed']:,}")
    lines.append(f"- Any imputed: {s['any_imputed']:,}\n")

    if not by_century.empty:
        lines.append("## Per-century counts (lived 800-1500)\n")
        lines.append("| Birth century | N | M | F | Birth obs | Birth imp | Death obs | Death imp |")
        lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, row in by_century.iterrows():
            lines.append(
                f"| {int(row['birth_century'])} | {int(row['n']):,} | "
                f"{int(row['male']):,} | {int(row['female']):,} | "
                f"{int(row['birth_observed']):,} | {int(row['birth_imputed']):,} | "
                f"{int(row['death_observed']):,} | {int(row['death_imputed']):,} |"
            )
        lines.append("")

    if not lifespan.empty:
        lines.append("## Lifespan quantiles (lived 800-1500, trimmed to 0-110y)\n")
        lines.append("| Subset | N | mean | p10 | p25 | p50 | p75 | p90 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for _, row in lifespan.iterrows():
            if row["n"] == 0:
                lines.append(f"| {row['subset']} | 0 | - | - | - | - | - | - |")
                continue
            lines.append(
                f"| {row['subset']} | {int(row['n']):,} | "
                f"{row['mean']:.1f} | {row['p10']:.0f} | {row['p25']:.0f} | "
                f"{row['p50']:.0f} | {row['p75']:.0f} | {row['p90']:.0f} |"
            )
        lines.append("")

    if not imputation_rates.empty:
        lines.append("## Imputation rates (lived 800-1500)\n")
        lines.append("| Subset | N | Birth imp | Death imp | Any imp | Fully obs |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for _, row in imputation_rates.iterrows():
            n = int(row["n"])
            if n == 0:
                lines.append(f"| {row['subset']} | 0 | - | - | - | - |")
                continue
            lines.append(
                f"| {row['subset']} | {n:,} | "
                f"{row['birth_imputed_rate']:.3f} | "
                f"{row['death_imputed_rate']:.3f} | "
                f"{row['any_imputed_rate']:.3f} | "
                f"{row['fully_observed_rate']:.3f} |"
            )
        lines.append("")

    if validation is not None and not validation.empty:
        lines.append("## Imputation holdout validation\n")
        lines.append("From `01_impute.py --validate`. Holdout sample of "
                     "persons with both birth and death attested in source; "
                     "fields masked and re-imputed; errors measured against "
                     "truth. Sliced by cohort membership (overlap with "
                     "800-1500 evaluated on truth values).\n")
        lines.append("| Cohort | Field | N | Coverage | MAE | RMSE | Bias | Within 10y |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
        # Treat possibly-missing cohort column for backward compat.
        cohort_col = "cohort" if "cohort" in validation.columns else None
        for _, row in validation.iterrows():
            cohort_val = row[cohort_col] if cohort_col else "all"
            n = int(row["sample_size"])
            if n == 0:
                lines.append(
                    f"| {cohort_val} | {row['field']} | 0 | - | - | - | - | - |"
                )
                continue
            lines.append(
                f"| {cohort_val} | {row['field']} | {n:,} | "
                f"{float(row['coverage']):.3f} | "
                f"{float(row['mae']):.2f} | {float(row['rmse']):.2f} | "
                f"{float(row['bias']):.2f} | "
                f"{float(row['within_10']):.3f} |"
            )
        lines.append("")

    with open(SUMMARY_DIR / "peerage_summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    print("Loading inputs from output/...", flush=True)
    df = load_persons()
    n_parents, n_children, n_spouses, n_siblings = load_edges()
    print(f"  persons: {len(df):,}", flush=True)

    df = add_cohort_flags(df)
    df = attach_degrees(df, n_parents, n_children, n_spouses, n_siblings)

    print("Computing tables...", flush=True)
    t01 = table_global_counts(df)
    t02 = table_cohorts(df)
    t03 = table_by_century(df)
    t04 = table_imputation_rates(df)
    t05 = table_degree_stats(df)
    t06 = table_degree_histograms(df)
    t07 = table_lifespan(df)
    t08 = table_decade_panel(df)
    t09 = passthrough("consistency_report.csv")
    t10 = passthrough("imputation_validation_metrics.csv")

    t01.to_csv(SUMMARY_DIR / "01_global_counts.csv", index=False)
    t02.to_csv(SUMMARY_DIR / "02_cohorts_800_1500.csv", index=False)
    t03.to_csv(SUMMARY_DIR / "03_lived_in_by_century.csv", index=False)
    t04.to_csv(SUMMARY_DIR / "04_imputation_rates.csv", index=False)
    t05.to_csv(SUMMARY_DIR / "05_kin_degree_stats.csv", index=False)
    t06.to_csv(SUMMARY_DIR / "06_kin_degree_histograms.csv", index=False)
    t07.to_csv(SUMMARY_DIR / "07_lifespan_quantiles.csv", index=False)
    t08.to_csv(SUMMARY_DIR / "08_decade_panel.csv", index=False)
    if t09 is not None:
        t09.to_csv(SUMMARY_DIR / "09_edge_consistency.csv", index=False)
    if t10 is not None:
        t10.to_csv(SUMMARY_DIR / "10_imputation_validation.csv", index=False)

    write_markdown_summary(t01, t02, t03, t04, t07, t10)

    print(f"\nWrote {len(list(SUMMARY_DIR.glob('*.csv')))} CSV tables + "
          f"peerage_summary.md to {SUMMARY_DIR}")


if __name__ == "__main__":
    main()
