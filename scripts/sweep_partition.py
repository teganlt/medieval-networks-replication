"""sweep_partition.py — partition-perturbation sweep for the headline IV.

The marriage-bloc partition is one draw of a stochastic community-detection
algorithm (Louvain; scripts/55). This script quantifies how the unified
Prediction-1 baseline depends on that draw:

  for each seed s: reseed igraph's RNG, redraw the Louvain partition (running
  scripts/55 unmodified), compute the draw's modularity on the patriline-
  marriage graph, rebuild bloc kin-reach (scripts/56) and the father bloc
  increment (scripts/64), re-run the unified baseline 2SLS (scripts/100), and
  record the secular-territorial and all-documents estimates.

With --leiden it instead runs ONE draw using Leiden community detection
(modularity objective, run to convergence) — the algorithm that avoids
Louvain's resolution limit — by swapping the community-detection call and
leaving every other step of the production pipeline identical.

The frozen-partition state is restored when the run completes, and the
restored baseline is re-printed as a check.

Usage (from the package root, AFTER a full run_all.py pass):
    python scripts/sweep_partition.py --n 50           # the 50-seed sweep
    python scripts/sweep_partition.py --leiden         # the Leiden draw
    python scripts/sweep_partition.py --n 10 --start 41  # resume/extend

Appends to output/clean_iv/partition_seed_sweep.csv. Runtime ~50s per draw.
The run used for the paper's partition-robustness numbers ships at
validation/partition_sweep/partition_seed_sweep.csv (seeds 1-50 + leiden +
the frozen reference row).

Set RSCRIPT if Rscript is not on PATH. Seeded and deterministic per seed on
a fixed software environment (igraph RNG delegated to Python's random).
"""
from __future__ import annotations
import argparse
import csv
import os
import random
import runpy
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import igraph as ig
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
CIV = OUT / "clean_iv"
RSCRIPT = os.environ.get("RSCRIPT", "Rscript")
SWEEP_CSV = CIV / "partition_seed_sweep.csv"
FIELDS = ["seed", "algorithm", "n_blocs", "n_blocs_insample", "modularity",
          "cor_reach_frozen", "domain", "beta", "SE", "p", "p_2way",
          "F_first", "N", "npos"]


def to_year(x):
    s = str(x).strip()
    if s in ("", "nan", "NaN"):
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def build_marriage_graph():
    """The patriline-marriage graph exactly as scripts/55 builds it
    (marriages with mean birth year in [800, 1500], patriline nodes,
    marriage-count edge weights)."""
    persons = pd.read_csv(OUT / "persons_imputed.csv")
    birth = {r.id: to_year(r.birth) for r in persons.itertuples(index=False)}
    plf = pd.read_csv(OUT / "patriline_assignment.csv")
    pl = dict(zip(plf["id"], plf["dynasty"]))
    sp = pd.read_csv(OUT / "spouse_pairs.csv")
    w = Counter()
    seen = set()
    for r in sp.itertuples(index=False):
        key = tuple(sorted((r.a, r.b)))
        if key in seen:
            continue
        seen.add(key)
        ba, bb = birth.get(r.a), birth.get(r.b)
        if ba is None or bb is None or not (800 <= (ba + bb) / 2 <= 1500):
            continue
        pa, pb = pl.get(r.a), pl.get(r.b)
        if pa is None or pb is None or pa == pb:
            continue
        w[tuple(sorted((pa, pb)))] += 1
    nodes = sorted({p for e in w for p in e})
    idx = {p: i for i, p in enumerate(nodes)}
    g = ig.Graph([(idx[a], idx[b]) for a, b in w],
                 edge_attrs={"weight": list(w.values())})
    return g, nodes, idx, pl


def partition_modularity(g, nodes, idx, pl):
    """Modularity of the current output/patriline_bloc_assignment.csv on g."""
    pb = pd.read_csv(OUT / "patriline_bloc_assignment.csv", dtype=str)
    person_bloc = dict(zip(pb["id"], pb["dynasty"]))
    pat_bloc = {}
    for pid, pat in pl.items():
        if pat in idx and pat not in pat_bloc:
            b = person_bloc.get(pid)
            if b:
                pat_bloc[pat] = b
    labs = sorted(set(pat_bloc.values()))
    li = {l: i for i, l in enumerate(labs)}
    membership = [li[pat_bloc[p]] if p in pat_bloc else len(labs) + i
                  for i, p in enumerate(nodes)]
    return g.modularity(membership, weights="weight")


def run(cmd, tag):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"  FAIL {tag}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        raise RuntimeError(tag)
    return r.stdout


def one_draw(seed, leiden, g, nodes, idx, pl, ref, writer, fh):
    t0 = time.time()
    random.seed(seed)
    ig.set_random_number_generator(random)
    if leiden:
        # swap ONLY the community-detection call; scripts/55 runs otherwise
        # unmodified, so every construction choice is held fixed
        orig = ig.Graph.community_multilevel
        ig.Graph.community_multilevel = (
            lambda self, weights=None, return_levels=False:
            self.community_leiden(objective_function="modularity",
                                  weights=weights, n_iterations=-1))
    sys.argv = ["55_patriline_blocs.py"]
    try:
        runpy.run_path(str(ROOT / "scripts" / "55_patriline_blocs.py"),
                       run_name="__main__")
    finally:
        if leiden:
            ig.Graph.community_multilevel = orig
    pb = pd.read_csv(OUT / "patriline_bloc_assignment.csv", dtype=str)
    blocs = pb.loc[pb["dynasty"].notna()
                   & ~pb["dynasty"].str.startswith("solo"), "dynasty"]
    n_blocs = blocs.nunique()
    q = partition_modularity(g, nodes, idx, pl)
    run([sys.executable, str(ROOT / "scripts" / "56_bloc_reach_fullgraph.py")], "56")
    run([sys.executable, str(ROOT / "scripts" / "64_father_bloc_increment.py")], "64")
    out100 = run([RSCRIPT, str(ROOT / "scripts" / "100_unified_baseline.R"),
                  str(ROOT)], "100")
    insample = ""
    for line in out100.splitlines():
        if "blocs=" in line:
            insample = line.split("blocs=")[1].split()[0]
            break
    br = pd.read_csv(OUT / "bloc_reach_fullgraph.csv",
                     dtype={"person_id": str})[["person_id", "n_dyn_4hop"]]
    cor = br.merge(ref, on="person_id")["n_dyn_4hop"].corr(
        br.merge(ref, on="person_id")["reach_frozen"])
    reg = pd.read_csv(CIV / "reg_unified_bloc_iv.csv")
    algo = "leiden" if leiden else "louvain"
    for dom in ("secular_territorial", "total"):
        r = reg[reg["domain"] == dom].iloc[0]
        writer.writerow({"seed": seed, "algorithm": algo, "n_blocs": n_blocs,
                         "n_blocs_insample": insample,
                         "modularity": round(q, 4),
                         "cor_reach_frozen": round(float(cor), 4),
                         "domain": dom, "beta": r["beta"], "SE": r["SE"],
                         "p": r["p"], "p_2way": r["p_2way"],
                         "F_first": r["F_first"], "N": r["N"],
                         "npos": r["npos"]})
    fh.flush()
    st = reg[reg["domain"] == "secular_territorial"].iloc[0]
    print(f"{algo.upper()} seed {seed}: blocs={n_blocs} insample={insample} "
          f"Q={q:.4f} cor={cor:.3f} secterr beta={st['beta']:.4f} "
          f"p2w={st['p_2way']:.4f} ({time.time() - t0:.0f}s)", flush=True)


def restore():
    print("restoring frozen-partition state...", flush=True)
    shutil.copy2(ROOT / "data" / "frozen" / "patriline_bloc_assignment.csv",
                 OUT / "patriline_bloc_assignment.csv")
    run([sys.executable, str(ROOT / "scripts" / "56_bloc_reach_fullgraph.py")],
        "56-restore")
    run([sys.executable, str(ROOT / "scripts" / "64_father_bloc_increment.py")],
        "64-restore")
    run([RSCRIPT, str(ROOT / "scripts" / "100_unified_baseline.R"), str(ROOT)],
        "100-restore")
    reg = pd.read_csv(CIV / "reg_unified_bloc_iv.csv")
    st = reg[reg["domain"] == "secular_territorial"].iloc[0]
    print(f"restored baseline: secterr beta={st['beta']:.4f} "
          f"p_2way={st['p_2way']:.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="number of Louvain seeds")
    ap.add_argument("--start", type=int, default=1, help="first seed")
    ap.add_argument("--leiden", action="store_true",
                    help="run ONE Leiden draw instead of the Louvain sweep")
    a = ap.parse_args()

    ref = pd.read_csv(OUT / "bloc_reach_fullgraph.csv",
                      dtype={"person_id": str})[["person_id", "n_dyn_4hop"]]
    ref = ref.rename(columns={"n_dyn_4hop": "reach_frozen"})
    g, nodes, idx, pl = build_marriage_graph()
    print(f"patriline-marriage graph: {g.vcount()} nodes, {g.ecount()} edges")

    new_file = not SWEEP_CSV.exists()
    with SWEEP_CSV.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        try:
            if a.leiden:
                one_draw(42, True, g, nodes, idx, pl, ref, w, fh)
            else:
                for seed in range(a.start, a.start + a.n):
                    one_draw(seed, False, g, nodes, idx, pl, ref, w, fh)
        finally:
            restore()

    df = pd.read_csv(SWEEP_CSV)
    st = df[(df["domain"] == "secular_territorial")
            & (df["algorithm"] == "louvain")]
    if len(st):
        print(f"\n== secular-territorial, {len(st)} Louvain draws ==")
        print(f"  beta min {st['beta'].min():.4f} | median "
              f"{st['beta'].median():.4f} | max {st['beta'].max():.4f}")
        print(f"  one-way p<.05: {(st['p'] < .05).sum()}/{len(st)} | "
              f"two-way p<.05: {(st['p_2way'] < .05).sum()}/{len(st)}")
        print(f"  cor(beta, modularity) = "
              f"{st['beta'].corr(st['modularity']):+.3f}")


if __name__ == "__main__":
    main()
