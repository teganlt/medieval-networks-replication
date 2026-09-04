"""run_all.py — replication pipeline orchestrator.

Usage (from the package root):
    python run_all.py                 # full pipeline from raw data + frozen AI artifacts
    python run_all.py --list          # print the stage plan and exit
    python run_all.py --from 7.1      # resume from a stage id
    python run_all.py --only 7.1      # run a single stage
    python run_all.py --rerun-louvain # regenerate the marriage-bloc partition
                                      # instead of using the frozen one (stochastic;
                                      # digits will differ slightly -- see README)

The two generative-AI stages (person-letter extraction; subject coding) are
NOT run: their frozen outputs ship in data/frozen/ and are seeded into
output/ by stage 0. The scripts that produced them (09, 10, 12_recode_subjects)
are included for transparency; running them requires an Anthropic API key and
will not reproduce the frozen verdicts bit-for-bit (see README).

R is invoked as `Rscript <script> <package root>`. Set the RSCRIPT environment
variable if Rscript is not on PATH.
"""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
RSCRIPT = os.environ.get("RSCRIPT", "Rscript")

def py(script, *args):
    return [PY, str(ROOT / "scripts" / script), *args]

def rr(script):
    return [RSCRIPT, str(ROOT / "scripts" / script), str(ROOT)]

# (stage id, description, command) — order is the dependency order.
STAGES = [
    # ---- stage 0: inputs ----
    ("0.1", "check raw + frozen inputs; seed frozen artifacts", py("check_inputs.py")),

    # ---- stage 1: Peerage base tables ----
    ("1.1", "normalize scrape; persons/parent/spouse edge lists; reciprocity", py("00_normalize_consistency.py")),
    ("1.2", "impute birth/death years + 5,000-person holdout validation", py("01_impute.py", "--validate")),
    ("1.3", "Peerage summary statistics (console)", py("02_peerage_summary.py")),

    # ---- stage 2: sampling frame ----
    ("2.1", "dynastic anchors; sampling frame; dynasty labels", py("03_named_anchor_dynasty.py")),
    ("2.2", "interdynastic marriage time series", py("04_interdyn_marriage_panel.py")),

    # ---- stage 3: APOSCRIPTA ----
    ("3.1", "parse APOSCRIPTA dump to per-document table", py("07_aposcripta_parse.py")),
    ("3.2", "APOSCRIPTA subject time series (mandement share)", py("13_aposcripta_subject_timeseries.py")),

    # ---- stage 4: person-letter matching (from frozen verdicts) ----
    ("4.1", "build per-document extraction payloads + shortlists (~2.7 GB)", py("08_doc_match_build_candidates.py")),
    ("4.2", "aggregate frozen verdicts into person summaries", py("11_doc_match_build_person_summary.py")),
    ("4.3", "build match-level table + outcome variants", py("12_doc_match_build_outcomes.py")),
    ("4.4", "inter-coder agreement for the subject coding (tab:kappa)", py("recode_agreement.py")),

    # ---- stage 5: network construction ----
    ("5.1", "patriline labels (father-child components)", py("51_patriline_labels.py")),
    ("5.2", "marriage-blocs (Louvain; SKIPPED by default: frozen partition seeded in stage 0)", py("55_patriline_blocs.py")),
    ("5.3", "network properties: 4-hop reach on dynasty labels", py("17_network_properties.py")),
    ("5.4", "bloc kin-reach on the full graph (focal + ancestors, pre-natal)", py("56_bloc_reach_fullgraph.py")),
    ("5.5", "clean IV inputs: in-window doc counts; focal network size", py("45_clean_inputs.py")),
    ("5.6", "maternal instrument construction (pre-natal reach)", py("18_mother_iv_construct.py")),
    ("5.7", "father's incremental reach |F\\M| (dynasty labels)", py("50_father_increment.py")),
    ("5.8", "father's incremental reach |F\\M| (bloc labels)", py("64_father_bloc_increment.py")),
    ("5.9", "bloc cohesion measures (HHI, clustering)", py("62_bloc_cohesion.py")),
    ("5.10", "hop-sweep reach build (3-6 hops + matching instruments)", py("101_bloc_reach_hopsweep.py")),
    ("5.11", "pre-1300 marriage-bloc repartition (Louvain; SKIPPED by default: frozen partition seeded in stage 0)", py("120_blocs_pre1300.py")),

    # ---- stage 6: analysis frames ----
    ("6.1", "peer/complementarity frame (base)", py("84_complementarity_iv_build.py")),
    ("6.2", "peer/complementarity frame (saturation columns)", py("86_complementarity_iv_saturate_build.py")),
    ("6.3", "patriline court-propensity indices (family history block)", py("88_patriline_propensity_build.py")),
    ("6.4", "predetermined peer variables (breadth, arbitration share)", py("110_peer_rf_build.py")),
    ("6.5", "matched-disputant dyad distances", py("134_dispute_distance.py")),
    ("6.6", "graph-distance band exposures", py("140_band_exposures_build.py")),
    ("6.7", "heiress/contestability status of mothers", py("146_heiress_build.py")),

    # ---- stage 7: regressions ----
    ("7.1", "UNIFIED Prediction-1 baseline (tab:forward; emits tab_domains.tex)", rr("100_unified_baseline.R")),
    ("7.1b", "conflict-prone maternal-family flags (needs unified frame)", rr("148_conflict_prone_build.R")),
    ("7.2", "bloc leave-one-out + drop-largest", rr("105_unified_loo.R")),
    ("7.3", "hop-sweep 2SLS (3-6 hops)", rr("102_hopsweep_iv.R")),
    ("7.4", "WCB + within-cell permutation (Prediction 1)", rr("104_wcb_permutation.R")),
    ("7.5", "restricted wild-cluster bootstrap (proper)", rr("106_wcb_proper.R")),
    ("7.6", "mother-level permutation inference", rr("152_pred1_mother_permutation.R")),
    ("7.7", "effective number of clusters", rr("157_effective_clusters.R")),
    ("7.8", "exposure (years-in-window) control", rr("119_exposure_break.R")),
    ("7.9", "pre-1300 partition 2SLS", rr("121_pre1300_iv.R")),
    ("7.10", "bad-control (net-of-prominence) bound", rr("151_badcontrol_unified.R")),
    ("7.11", "heiress-indicator control", rr("147_heiress_bins.R")),
    ("7.12", "conflict-prone decomposition + gates (tab:app_cp2_inter)", rr("149_conflict_prone_headline.R")),
    ("7.13", "excess + share outcomes (tab:app_margins panel B)", rr("116_unified_excess_share.R")),
    ("7.14", "Chen-Roth extensive/intensive decomposition", rr("97_chenroth_decomp.R")),
    ("7.15", "Poisson control function (analytic)", rr("96_cf_poisson_oster.R")),
    ("7.17", "Poisson score bootstrap (tab:app_margins panel C)", rr("116a_persist_poisson.R")),
    ("7.18", "principal-party strict outcome", rr("118_principal_outcome.R")),
    ("7.19", "reverse reduced form (return arrow)", rr("81_reverse_rf.R")),
    ("7.20", "reverse erosion", rr("82_reverse_erosion.R")),
    ("7.21", "old-spec bloc IV (npos inputs for fig:domains)", rr("57_bloc_iv.R")),
    ("7.22", "peer reduced forms: breadth + arbitration share (tab:peer_rf/flip)", rr("111_peer_rf.R")),
    ("7.23", "Oster selection bounds for peer breadth", rr("112_peer_rf_oster.R")),
    ("7.24", "peer match-censoring bounds", rr("113_peer_rf_censoring.R")),
    ("7.25", "peer permutation inference", rr("115_peer_rf_permutation.R")),
    ("7.26", "ambient-channel bounding (reach IV + peer controls)", rr("153_ambient_control_iv.R")),
    ("7.27", "band battery (ally/rival bands)", rr("141_band_battery.R")),
    ("7.28", "band sibship permutation", rr("141b_band_sibship_perm.R")),
    ("7.29", "ball sibship permutation", rr("141c_ball_sibship_perm.R")),
    ("7.30", "3-4 hop band battery", rr("144_band34_battery.R")),
    ("7.31", "peer FE/clustering variants", rr("155_peer_fe_variants.R")),
    ("7.32", "birth-decade FE headline", rr("158_birthdec_headline.R")),
    ("7.33", "dual-coding strict secular-territorial 2SLS", rr("dual_code_strict_iv.R")),

    # ---- stage 8: figures ----
    ("8.1", "fig: ancestor uniqueness data + spanning windows (Leiden, seeded)", py("fig_spanning_1700.py")),
    ("8.2", "fig: fixed-K spanning windows (Leiden, seeded)", py("fig_spanning_fixedK.py")),
    ("8.3", "fig: spanning paper series + ancestor uniqueness windows", py("fig_spanning_paper.py")),
    ("8.4", "fig: comovement (intro)", py("fig_intro_comovement.py")),
    ("8.5", "figs: ancestor/spanning/interdyn with N subpanels (paper versions)", py("150_stylized_figs.py")),
    ("8.6", "fig: measurement pipeline diagram", py("fig_measure_pipeline.py")),
    ("8.7", "fig: Berg worked example", py("fig_measure_berg.py")),
    ("8.8", "figs: reach vs size; domain distribution", py("fig_measure_data.py")),
    ("8.9", "fig: horizon (reach distribution + cor by hop)", py("fig_horizon_unified.py")),
    ("8.10", "fig: IV DAG", py("fig_iv_dags.py")),
    ("8.11", "fig: peer construction triptych (Andrew Arpad)", py("fig_peer_triptych.py")),

    # ---- stage 9: tables ----
    ("9.1", "summary tables + bloc roster", py("build_summary_tables.py")),
    ("9.2", "peer tables (tab_peer_rf, tab_peer_flip)", rr("114_emit_peer_tables.R")),
    ("9.3", "appendix tables (robust, hopsweep, inference, margins, reverse, oster, censoring)", rr("117_emit_appendix_tables.R")),
    ("9.4", "band appendix table", rr("154_band_appendix_table.R")),
    ("9.5", "FE-variant tables", rr("159_fe_variants_table.R")),
    ("9.6", "anchor roster table", py("156_anchor_roster_table.py")),

    # ---- stage 10: validation / audit numbers ----
    ("10.1", "rebuild human-audit sample frames (design check; frozen items are canonical)", py("v90_build_audit_samples.py")),
    ("10.2", "rebuild blitz FP audit sample (researcher 100; seed 43)", py("v94_build_blitz_fp_audit.py")),
    ("10.3", "pooled human audit precision (186/195; Fisher; terciles)", py("v95_pooled_precision.py")),
    ("10.4", "cross-model + preliminary human validation tallies (108/108; 25/25)", py("v96_match_validation_tallies.py")),

    # ---- stage 11: partition-robustness sweep (OPTIONAL: run with --sweep; ~45 min) ----
    ("11.1", "partition seed sweep: 50 Louvain redraws of the marriage-bloc partition", py("sweep_partition.py", "--n", "50")),
    ("11.2", "Leiden draw of the marriage-bloc partition (resolution-limit-free)", py("sweep_partition.py", "--leiden")),
]

SWEEP_STAGES = {"11.1", "11.2"}  # only run with --sweep (the paper's run ships at validation/partition_sweep/)

SKIP_BY_DEFAULT = {"5.2", "5.11"}  # frozen Louvain partitions (main + pre-1300) are the paper's

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--from", dest="from_stage", default=None)
    ap.add_argument("--only", default=None)
    ap.add_argument("--rerun-louvain", action="store_true")
    ap.add_argument("--sweep", action="store_true",
                    help="also run the partition-robustness sweep (stages 11.x, ~45 min)")
    args = ap.parse_args()

    stages = STAGES
    if args.list:
        for sid, desc, _ in stages:
            skip = "  [skipped by default]" if sid in SKIP_BY_DEFAULT else ""
            print(f"{sid:>5}  {desc}{skip}")
        return

    if args.only:
        stages = [s for s in stages if s[0] == args.only]
    elif args.from_stage:
        ids = [s[0] for s in stages]
        stages = stages[ids.index(args.from_stage):]

    for d in ("output", "figs", "tables"):
        (ROOT / d).mkdir(exist_ok=True)
    logdir = ROOT / "output" / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    log = (ROOT / "run_log.txt").open("a", encoding="utf-8")
    log.write(f"\n=== run_all start {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    for sid, desc, cmd in stages:
        if sid in SKIP_BY_DEFAULT and not args.rerun_louvain and not args.only:
            print(f"[{sid}] SKIP (frozen artifact in use): {desc}")
            log.write(f"[{sid}] SKIP {desc}\n")
            continue
        print(f"\n[{sid}] {desc}")
        t0 = time.time()
        stage_log = logdir / f"stage_{sid.replace('.', '_')}.log"
        with stage_log.open("w", encoding="utf-8") as slog:
            env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace", env=env)
            for line in proc.stdout:
                sys.stdout.write(line)
                slog.write(line)
            proc.wait()
        dt = time.time() - t0
        line = f"[{sid}] {'OK' if proc.returncode == 0 else 'FAIL'} ({dt:,.0f}s) {desc}\n"
        log.write(line); log.flush()
        if proc.returncode != 0:
            print(f"\nSTAGE {sid} FAILED (exit {proc.returncode}). "
                  f"See {stage_log.relative_to(ROOT)}.")
            sys.exit(proc.returncode)
    log.write("=== run_all complete ===\n")
    print("\nPIPELINE COMPLETE. Outputs in output/, figs/, tables/. "
          "Per-stage console logs in output/logs/.")

if __name__ == "__main__":
    main()
