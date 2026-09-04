"""
01_impute.py
=============

Stage 1 of the replication pipeline.

Read the normalized person + edge tables from Stage 0 and iteratively
impute missing birth/death years from kin neighbours, using medieval-
elite priors (GAP_FATHER=30, GAP_MOTHER=25, LIFESPAN=60, SPOUSE_GAP=3).

Per-iteration, for each person with missing birth/death we build a
candidate list from all available kin signals and assign the integer
median. With dictionary iteration order and 20 passes the procedure
reaches fixed point (terminates early when no new imputations occur).

Inputs (in output/):
  persons.csv
  parent_pairs.csv
  spouse_pairs.csv

Outputs (in output/):
  persons_imputed.csv
      Columns: id, name, sex, birth, death, birth_imputed, death_imputed
      birth_imputed / death_imputed are 0/1 flags:
        0 = value present in persons.csv (observed in the source),
        1 = value filled in here (imputed).
      Empty year + flag=0 means the value is still missing after imputation.

  imputation_validation_metrics.csv  (only with --validate)
      Holdout cross-validation. Samples HOLDOUT_SIZE persons with both
      birth and death attested, masks both fields, re-runs the imputer,
      and reports MAE / RMSE / bias / coverage / within-K-year hit rates
      per (cohort x field). Cohort slices: "all", "lived_in_800_1500"
      (truth-value overlap with the cohort window), and the complement.

Usage:
  python 01_impute.py             # impute, write persons_imputed.csv
  python 01_impute.py --validate  # also run holdout validation
"""
from __future__ import annotations
import argparse
import csv
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

GAP_FATHER = 30
GAP_MOTHER = 25
LIFESPAN = 60
SPOUSE_GAP = 3
MAX_ITERS = 20
HOLDOUT_SIZE = 5000
HOLDOUT_SEED = 123

# Cohort window for restricted-MAE reporting (must match 02_peerage_summary.py)
COHORT_LO = 800
COHORT_HI = 1500


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


def med(xs):
    xs = list(xs)
    return None if not xs else int(round(statistics.median(xs)))


def load_stage0():
    persons = {}
    with open(OUT / "persons.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            persons[row["id"]] = {
                "name": row["name"],
                "sex": row["sex"],
                "birth": to_year(row["birth"]),
                "death": to_year(row["death"]),
            }

    parent_pairs = []
    with open(OUT / "parent_pairs.csv", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for parent_id, child_id in reader:
            parent_pairs.append((parent_id, child_id))

    spouse_pairs = []
    with open(OUT / "spouse_pairs.csv", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for a, b in reader:
            spouse_pairs.append((a, b))

    return persons, parent_pairs, spouse_pairs


def build_graphs(parent_pairs, spouse_pairs):
    parent_of = defaultdict(set)
    children_of = defaultdict(set)
    for parent_id, child_id in parent_pairs:
        parent_of[child_id].add(parent_id)
        children_of[parent_id].add(child_id)

    spouse_of = defaultdict(set)
    for a, b in spouse_pairs:
        spouse_of[a].add(b)
        spouse_of[b].add(a)

    siblings = defaultdict(set)
    for parent_id, kids in children_of.items():
        kids_list = list(kids)
        for i, kid in enumerate(kids_list):
            for other in kids_list[i + 1:]:
                siblings[kid].add(other)
                siblings[other].add(kid)

    return parent_of, children_of, spouse_of, siblings


def impute_years(persons, parent_pairs, spouse_pairs):
    parent_of, children_of, spouse_of, siblings = build_graphs(
        parent_pairs, spouse_pairs
    )

    for it in range(MAX_ITERS):
        changes = 0
        for pid, info in persons.items():
            if info["birth"] is None:
                candidates = []
                for parent_id in parent_of.get(pid, ()):
                    parent = persons.get(parent_id)
                    if not parent:
                        continue
                    sex = parent["sex"]
                    gap = (
                        GAP_FATHER if sex == "M"
                        else GAP_MOTHER if sex == "F"
                        else (GAP_FATHER + GAP_MOTHER) / 2
                    )
                    if parent["birth"] is not None:
                        candidates.append(int(parent["birth"] + gap))
                    elif parent["death"] is not None:
                        candidates.append(int(parent["death"] - LIFESPAN + gap))
                for child_id in children_of.get(pid, ()):
                    child = persons.get(child_id)
                    if not child:
                        continue
                    sex = info["sex"]
                    gap = (
                        GAP_FATHER if sex == "M"
                        else GAP_MOTHER if sex == "F"
                        else (GAP_FATHER + GAP_MOTHER) / 2
                    )
                    if child["birth"] is not None:
                        candidates.append(int(child["birth"] - gap))
                    elif child["death"] is not None:
                        candidates.append(int(child["death"] - LIFESPAN - gap))
                for spouse_id in spouse_of.get(pid, ()):
                    spouse = persons.get(spouse_id)
                    if not spouse or spouse["birth"] is None:
                        continue
                    if info["sex"] == "M" and spouse["sex"] == "F":
                        candidates.append(int(spouse["birth"] - SPOUSE_GAP))
                    elif info["sex"] == "F" and spouse["sex"] == "M":
                        candidates.append(int(spouse["birth"] + SPOUSE_GAP))
                    else:
                        candidates.append(int(spouse["birth"]))
                if info["death"] is not None:
                    candidates.append(int(info["death"] - LIFESPAN))
                sibling_births = [
                    persons[s]["birth"]
                    for s in siblings.get(pid, ())
                    if s in persons and persons[s]["birth"] is not None
                ]
                if sibling_births:
                    candidates.append(med(sibling_births))
                if candidates:
                    info["birth"] = med(candidates)
                    changes += 1
            if info["death"] is None:
                candidates = []
                if info["birth"] is not None:
                    candidates.append(int(info["birth"] + LIFESPAN))
                for spouse_id in spouse_of.get(pid, ()):
                    spouse = persons.get(spouse_id)
                    if spouse and spouse["death"] is not None:
                        candidates.append(int(spouse["death"]))
                sibling_deaths = [
                    persons[s]["death"]
                    for s in siblings.get(pid, ())
                    if s in persons and persons[s]["death"] is not None
                ]
                if sibling_deaths:
                    candidates.append(med(sibling_deaths))
                for parent_id in parent_of.get(pid, ()):
                    parent = persons.get(parent_id)
                    if parent and parent["death"] is not None:
                        candidates.append(int(parent["death"] + 25))
                for child_id in children_of.get(pid, ()):
                    child = persons.get(child_id)
                    if child and child["birth"] is not None:
                        candidates.append(int(child["birth"] + LIFESPAN - GAP_FATHER))
                if candidates:
                    info["death"] = med(candidates)
                    changes += 1
        print(f"  iter {it + 1}: {changes:,} new imputations", flush=True)
        if changes == 0:
            break

    return persons


def write_persons_imputed(persons, originally_known_birth,
                          originally_known_death, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "sex", "birth", "death",
                         "birth_imputed", "death_imputed"])
        for pid, info in persons.items():
            birth = info["birth"]
            death = info["death"]
            b_imp = 1 if (birth is not None
                          and pid not in originally_known_birth) else 0
            d_imp = 1 if (death is not None
                          and pid not in originally_known_death) else 0
            writer.writerow([
                pid, info["name"], info["sex"],
                birth if birth is not None else "",
                death if death is not None else "",
                b_imp, d_imp,
            ])


def sample_holdout(persons, sample_size=HOLDOUT_SIZE, seed=HOLDOUT_SEED):
    eligible = [
        pid for pid, info in persons.items()
        if info["birth"] is not None and info["death"] is not None
    ]
    if len(eligible) <= sample_size:
        return set(eligible)
    random.seed(seed)
    return set(random.sample(eligible, sample_size))


def summarize_errors(errors):
    if not errors:
        return {"n": 0, "mean_error": None, "median_error": None,
                "rmse": None, "mae": None, "bias": None,
                "within_1": None, "within_5": None,
                "within_10": None, "within_20": None}
    abs_errors = [abs(e) for e in errors]
    return {
        "n": len(errors),
        "mean_error": statistics.mean(errors),
        "median_error": statistics.median(abs_errors),
        "rmse": math.sqrt(statistics.mean([e * e for e in errors])),
        "mae": statistics.mean(abs_errors),
        "bias": statistics.mean(errors),
        "within_1": sum(1 for e in abs_errors if e <= 1) / len(errors),
        "within_5": sum(1 for e in abs_errors if e <= 5) / len(errors),
        "within_10": sum(1 for e in abs_errors if e <= 10) / len(errors),
        "within_20": sum(1 for e in abs_errors if e <= 20) / len(errors),
    }


def evaluate_holdout(truth, imputed, field, include=None):
    """Compute MAE/RMSE/etc. on the held-out set.

    `include` is an optional predicate (pid, truth[pid]) -> bool; if given,
    only persons for whom it returns True are scored. Used to slice the
    holdout into cohorts (e.g. lived_in_800_1500 vs outside).
    """
    errors = []
    missing = 0
    n_in_slice = 0
    for pid, actual in truth.items():
        if include is not None and not include(pid, actual):
            continue
        n_in_slice += 1
        estimated = imputed.get(pid, {}).get(field)
        if estimated is None:
            missing += 1
            continue
        errors.append(estimated - actual[field])
    metrics = summarize_errors(errors)
    metrics["missing"] = missing
    metrics["sample_size"] = n_in_slice
    metrics["coverage"] = (n_in_slice - missing) / n_in_slice if n_in_slice else 0
    return metrics


def in_cohort_lived_in(_pid, actual):
    """Truth-value membership in lived_in_800_1500 (interval overlap).

    Holdout truth always has both birth and death attested, so the overlap
    test is exact: birth <= COHORT_HI AND death >= COHORT_LO.
    """
    return actual["birth"] <= COHORT_HI and actual["death"] >= COHORT_LO


def out_of_cohort(_pid, actual):
    return not in_cohort_lived_in(_pid, actual)


def write_validation_metrics(metrics, path):
    """Write validation metrics to CSV.

    `metrics` is a dict keyed by (cohort, field) -> stats dict.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "cohort", "field", "sample_size", "coverage", "missing",
            "mean_error", "bias", "median_error", "rmse", "mae",
            "within_1", "within_5", "within_10", "within_20",
        ])
        for (cohort, field), stats in metrics.items():
            writer.writerow([
                cohort, field, stats["sample_size"],
                f"{stats['coverage']:.3f}", stats["missing"],
                stats["mean_error"] if stats["mean_error"] is not None else "",
                stats["bias"] if stats["bias"] is not None else "",
                stats["median_error"] if stats["median_error"] is not None else "",
                stats["rmse"] if stats["rmse"] is not None else "",
                stats["mae"] if stats["mae"] is not None else "",
                f"{stats['within_1']:.3f}" if stats["within_1"] is not None else "",
                f"{stats['within_5']:.3f}" if stats["within_5"] is not None else "",
                f"{stats['within_10']:.3f}" if stats["within_10"] is not None else "",
                f"{stats['within_20']:.3f}" if stats["within_20"] is not None else "",
            ])


def main():
    parser = argparse.ArgumentParser(
        description="Stage 1: impute birth/death years; optionally validate."
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Also run holdout validation; write imputation_validation_metrics.csv",
    )
    args = parser.parse_args()

    print("Loading Stage 0 data from output/...", flush=True)
    persons, parent_pairs, spouse_pairs = load_stage0()
    print(f"  persons: {len(persons):,}; parent_pairs: {len(parent_pairs):,}; "
          f"spouse_pairs: {len(spouse_pairs):,}")

    originally_known_birth = {pid for pid, info in persons.items()
                               if info["birth"] is not None}
    originally_known_death = {pid for pid, info in persons.items()
                               if info["death"] is not None}
    print(f"  birth known in source: {len(originally_known_birth):,}")
    print(f"  death known in source: {len(originally_known_death):,}")

    print("Running full imputation...", flush=True)
    full_persons = {pid: info.copy() for pid, info in persons.items()}
    full_imputed = impute_years(full_persons, parent_pairs, spouse_pairs)
    write_persons_imputed(full_imputed, originally_known_birth,
                          originally_known_death,
                          OUT / "persons_imputed.csv")

    n_birth = sum(1 for d in full_imputed.values() if d["birth"] is not None)
    n_death = sum(1 for d in full_imputed.values() if d["death"] is not None)
    n_birth_imp = n_birth - len(originally_known_birth)
    n_death_imp = n_death - len(originally_known_death)
    print(f"\nWrote output/persons_imputed.csv")
    print(f"  birth: known {len(originally_known_birth):,} + "
          f"imputed {n_birth_imp:,} = {n_birth:,}")
    print(f"  death: known {len(originally_known_death):,} + "
          f"imputed {n_death_imp:,} = {n_death:,}")

    if not args.validate:
        return

    holdout_ids = sample_holdout(persons)
    print(f"\nSelected {len(holdout_ids):,} known individuals for holdout validation",
          flush=True)

    truth = {pid: {"birth": persons[pid]["birth"], "death": persons[pid]["death"]}
             for pid in holdout_ids}
    masked_persons = {pid: info.copy() for pid, info in persons.items()}
    for pid in holdout_ids:
        masked_persons[pid]["birth"] = None
        masked_persons[pid]["death"] = None

    print("Running imputation on holdout sample...", flush=True)
    holdout_imputed = impute_years(masked_persons, parent_pairs, spouse_pairs)

    metrics = {}
    cohort_slices = [
        ("all", None),
        (f"lived_in_{COHORT_LO}_{COHORT_HI}", in_cohort_lived_in),
        (f"outside_{COHORT_LO}_{COHORT_HI}", out_of_cohort),
    ]
    for cohort_label, predicate in cohort_slices:
        metrics[(cohort_label, "birth")] = evaluate_holdout(
            truth, holdout_imputed, "birth", include=predicate
        )
        metrics[(cohort_label, "death")] = evaluate_holdout(
            truth, holdout_imputed, "death", include=predicate
        )
    write_validation_metrics(metrics,
                             OUT / "imputation_validation_metrics.csv")

    print("Validation summary:", flush=True)
    for (cohort_label, field), stats in metrics.items():
        if stats["sample_size"] == 0:
            print(f"  {cohort_label} {field}: empty slice")
            continue
        mae_str = f"{stats['mae']:.2f}" if stats['mae'] is not None else "-"
        bias_str = f"{stats['bias']:.2f}" if stats['bias'] is not None else "-"
        w10_str = (f"{stats['within_10']:.3f}"
                   if stats['within_10'] is not None else "-")
        print(f"  {cohort_label} {field}: n={stats['sample_size']:,} "
              f"coverage={stats['coverage']:.3f} "
              f"mae={mae_str} bias={bias_str} within 10y={w10_str}")
    print("Wrote output/imputation_validation_metrics.csv")


if __name__ == "__main__":
    main()
