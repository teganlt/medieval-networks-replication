# MANIFEST — every number, figure, and table in the draft → script → output

Paper: `paper/draft_8_29_26.tex` in this repository. Stage ids
(e.g. 7.1) refer to `run_all.py`; run `python run_all.py --list` to see the plan.

## Verification record (clean-room run, 2026-09-03)

The full pipeline was run start-to-finish in an isolated copy containing only
`data/raw/` and `data/frozen/` (per-stage wall times: `run_log_reference.txt`).
Results:

- **Tables**: `verify_against_draft.py` — 17 of 18 block-marked tables match the
  draft **to the digit** (1,200+ numbers). The 18th, `tab_peer_flip`, matches on
  every number the draft prints; the regenerated table additionally carries a
  $p_{2\text{way}}$ column per era that the draft's pasted version omitted
  (format drift, not a numeric mismatch). `tab:kappa` and `tab:app-imputation`
  (no block markers) verified digit-for-digit from
  `output/recode_agreement/agreement_report.md` and
  `output/imputation_validation_metrics.csv`.
- **Figures**: all 11 draft figures regenerate; `fig_horizon` and
  `fig_comovement_anchorfree` confirmed visually identical to the draft's
  `figs/`; worked-example figures reproduce their caption numbers exactly
  (Berg: 101 kin, 3 blocs; Andrew Árpád: 53 peers, breadth 1.415, share 0.094).
- **In-text numbers**: verified to the digit across the board — headline
  0.0326/p₂ᵥ .0052/F=339; LOO/drop rows; hop sweep; WCB .147/.092/.069;
  permutations z=8.03 and mother-level 6.21σ/5.14σ; effective clusters 2.3–2.7;
  exposure 0.0314/.0071; pre-1300 0.0325/.0304 (frozen partition); bad-control
  0.0196/.0027; heiress 0.0326/F=354/indicator +0.007 (p=.88); conflict-prone
  splits; principal 0.0258/.0136 (n=115) and 0.0319/.0247; ambient
  0.524/0.220/0.0290/0.0275; peer diagnostics 0.490/0.091/ICC 0.967; Oster;
  censoring; bands; break sweep −0.049..−0.067 with donut +0.187/−0.062;
  Continental +0.235/−0.063 with British-Isles cells skipped for zero outcome
  variation; dual-coding strict 0.0250 (SE .0018, p₂ᵥ .0015) vs 0.0258; κ table
  incl. secterr 88.5%/0.62; pooled audit 186/195 [91.4, 97.9], Fisher p=1.0,
  terciles .935/.962/.978; 108/108 and 25/25 tallies; dyads 221/mean 3.71/median
  4; matches 6,407 → 23 dups → 6,384; 1,421 (31.3%) disputes; 25,190 letters;
  727,753 persons; frame 252,484; patrilines 204,671; 579 blocs; caption Ns
  18,091/17,810, 8,696, and 2,380 (non-overlapping-window tiling of the
  regenerated series).
- The dynasty-assignment file regenerated **byte-identical** to the original
  run's, as did `persons_imputed.csv` under the `--validate` rerun.
- Discrepancies between draft text and reproduction: see the DISCREPANCIES
  section at the bottom.

## Figures

| Draft figure | File | Emitter (stage) |
|---|---|---|
| fig:comove | fig_comovement_anchorfree.png | fig_intro_comovement.py (8.4) |
| fig:ancestors | fig_ancestor_uniqueness_n.png | 150_stylized_figs.py (8.5) |
| fig:leiden | fig_spanning_paper_n.png | 150_stylized_figs.py (8.5; series from fig_spanning_1700/fixedK/paper, 8.1–8.3) |
| fig:interdyn | fig_interdyn_n.png | 150_stylized_figs.py (8.5; series from 04, stage 2.2) |
| fig:pipeline | fig_measure_pipeline.png | fig_measure_pipeline.py (8.6) |
| fig:berg | fig_reach_berg.png | fig_measure_berg.py (8.7) |
| fig:reachsize | fig_reach_vs_size.png | fig_measure_data.py (8.8) |
| fig:horizon | fig_horizon.png | fig_horizon_unified.py (8.9) |
| fig:codedoc | (typeset box, no image) | content = APOSCRIPTA no. 160468 in output/matched_docs_coded.csv |
| fig:domains | fig_domain_distribution.png | fig_measure_data.py (8.8; panel (b) counts from 57_bloc_iv.R, stage 7.21) |
| fig:dag | fig_iv_dag.png | fig_iv_dags.py (8.10) |
| fig:peer_construction | fig_peer_triptych.png | fig_peer_triptych.py (8.11) |

## Tables

| Draft table | Emitter (stage) | Regenerated file |
|---|---|---|
| tab:kappa | recode_agreement.py (4.4) | output/recode_agreement/agreement_report.md |
| tab:summary_sample | build_summary_tables.py (9.1) | tables/tab_summary_sample.tex |
| tab:forward | 100_unified_baseline.R (7.1) | tables/tab_domains.tex |
| tab:summary_peers | build_summary_tables.py (9.1) | tables/tab_summary_peers.tex |
| tab:peer_rf, tab:peer_flip | 111_peer_rf.R (7.22) → 114_emit_peer_tables.R (9.2) | tables/tab_peer_rf.tex, tab_peer_flip.tex |
| tab:app-imputation | 01_impute.py holdout (1.2) | output/imputation_validation_metrics.csv |
| tab:bloc_roster | build_summary_tables.py (9.1) | tables/tab_bloc_roster.tex |
| tab:app_robust | 100 + 105 (7.1, 7.2) → 117 (9.3) | tables/tab_app_robust.tex |
| tab:app_hopsweep | 101 (5.10) + 102 (7.3) → 117 (9.3) | tables/tab_app_hopsweep.tex |
| tab:app_inference | 104, 106, 115 (7.4, 7.5, 7.25) → 117 (9.3) | tables/tab_app_inference.tex |
| tab:app_margins | 116 (7.13), 97 (7.14), 96 (7.15), 116a (7.17) → 117 (9.3) | tables/tab_app_margins.tex |
| tab:app_cp2_inter | 148 (7.1b) + 149 (7.12) | tables/tab_app_cp2_inter.tex |
| tab:app_peer_oster | 112 (7.23) → 117 (9.3) | tables/tab_app_peer_oster.tex |
| tab:app_censoring | 113 (7.24) → 117 (9.3) | tables/tab_app_censoring.tex |
| tab:app_reverse | 81, 82 (7.19, 7.20) → 117 (9.3) | tables/tab_app_reverse.tex |
| tab:app_bands | 140 (6.6) + 141/144 (7.27, 7.30) → 154 (9.4) | tables/tab_app_bands.tex |
| tab:app_fe_headline, tab:app_fe_peer | 155, 158 (7.31, 7.32) → 159 (9.5) | tables/tab_app_fe_headline.tex, tab_app_fe_peer.tex |
| tab:anchor_roster | 156_anchor_roster_table.py (9.6) | tables/tab_anchor_roster.tex |

Table notes in the draft are author-edited prose; `verify_against_draft.py`
compares the numeric rows, not the notes.

## In-text numbers (grouped by section)

### §3 / Appendix B — sources, measurement, matching
| Claim | Source (stage) | Output |
|---|---|---|
| 727,753 persons; edge reciprocity 97.9% / 96.8%; 20,079 one-sided (17,949 / 2,130; 94% post-1500) | 00_normalize_consistency.py (1.1) | output/consistency_report.csv + console (output/logs/stage_1_1.log) |
| date coverage 51.0% / 37.8% → 99.8%; 1,722 undated; MAE 5.4 / 18.8; within-10 87.2% / 34.0%; 800–1500 subsample | 01_impute.py (1.2) | output/imputation_validation_metrics.csv |
| 25,190 letters; 24,130 in 1020–1380; 21,584 in 1100–1300; 91% dated; 99.9% analyse; 53 pontificates; 68.6% mandements | 07_aposcripta_parse.py (3.1) + 13 (3.2) | output/aposcripta_per_doc.csv, aposcripta_summary_stats.csv, console |
| frame: 252,484 assigned (34.7%); 16,836 → 6,233; 7,810 → 2,610; 21 dynasties | 03_named_anchor_dynasty.py (2.1) | output/dynasty_assignment_summary.csv + console |
| shortlist screen: median 1,708 → 106; royal retention | 08_doc_match_build_candidates.py (4.1) | console — **verified** (see DISCREPANCIES 3, resolved) |
| 96.4% pilot retention of matches under the name filter | doc_match_shortlist_filter.py calibration vs output/reextract_validation_aggregated.csv (frozen) | frozen artifact; see AI-provenance note below |
| 6,407 high-confidence matches; 521 nobles; 4,536 letters; 23 duplicate pairs → 6,384; ~1.4% out-of-shortlist dropped | 11 (4.2) + 12_doc_match_build_outcomes (4.3) | output/doc_matches_ai_extracted_high.csv, ai_extracted_dropped_records.csv, console |
| 1,421 of 4,536 (31.3%) live disputes | frozen matched_docs_coded.csv (coding pass; see AI-provenance) | data/frozen/matched_docs_coded.csv |
| κ table + secterr binary 88.5% / κ 0.62 | recode_agreement.py (4.4) | output/recode_agreement/agreement_report.md — **verified to the digit** |
| strict both-coders 2SLS on 258 docs: 0.025 (p₂ᵥ .002) vs 0.026 | dual_code_strict_iv.R (7.33) | output/clean_iv/reg_dual_code_strict.csv — **verified** (see DISCREPANCIES 1, resolved) |
| cross-model audit: 119 records; 108/108 high-confidence correct | v96_match_validation_tallies.py (10.4) over frozen reextract_validation_aggregated.csv | console — **verified** |
| hand-check: 38 records; 25/25 high-confidence correct | v96 (10.4) over frozen reextract_phase2_validation_sample.csv | console — **verified** |
| pooled human audit: 186/195 = 95.4% [91.4, 97.9]; researcher 93/97 (3 unsure); RA 93/98 (2 unsure); Fisher p = 1.0; terciles .935/.962/.978 | v95_pooled_precision.py (10.3) over frozen verdicts in validation/ | output/pooled_audit_precision.csv — **verified to the digit** |
| audit design: 200 in 8 strata of 25 (RA), disjoint 100 (researcher) | v90 (10.1), v94 (10.2) regenerate the sample frames into validation/*_regen for comparison against the frozen items | validation/audit_regen/, audit_blitz_regen/ |
| 204,671 patriline components; 579 blocs; modularity 0.83; 135,977 covered | 51 (5.1) + 55 (5.2; frozen partition is the default) | output/patriline_assignment.csv; data/frozen/patriline_bloc_assignment.csv; console |
| cor(reach, size) = 0.63; 0.95 on patrilines; median 4, IQR 3–6; horizon corrs 0.57/0.63/0.75 | 56 (5.4), 101 (5.10), fig_horizon_unified.py (8.9) | output/bloc_reach_fullgraph.csv, bloc_reach_hopsweep.csv, console |
| dispute dyads: 221; 84% within 5 hops; median 4; mean 3.7 | 134_dispute_distance.py (6.5) | output/clean_iv/dispute_dyad_distance.csv + console |
| Berg example (reach 3, 101 kin) | fig_measure_berg.py (8.7) | figure + console |

### §4.1 — forward IV
| Claim | Source (stage) | Output |
|---|---|---|
| headline table; F = 339; N = 2,195; 38 blocs | 100 (7.1) | output/clean_iv/reg_unified_bloc_iv.csv |
| permutation 8σ, p=.001; mother-level 6.2σ / 5.1σ (1,152 mothers) | 104 (7.4), 152 (7.6) | reg_unified_permutation999.csv, reg_unified_mother_permutation.csv |
| WCB p = .147 / .092 / .069; first stage .014 | 106 (7.5) | reg_unified_wcb_proper.csv |
| patriline FE/recluster 0.059 (p=.097) | 158/155 → 159 (9.5) | tables/tab_app_fe_headline.tex |
| net-of-prominence 0.02 (p₂ᵥ=.003), bad-control note | 151_badcontrol_unified.R (7.10) | reg_unified_badcontrol.csv |
| heiress control 0.0326 (F=354); indicator ≈ 0 | 146 (6.7) + 147 (7.11; patched to emit the F and the indicator row) | reg_heiress_bins.csv |
| LOO 38/38, β∈[0.0292, 0.0371]; drop-B3 0.0308; drop-Frederick 0.0334 (p₂ᵥ .004) | 100 + 105 (7.2) → 117 | reg_unified_loo.csv, reg_unified_drop_largest.csv, reg_unified_dropfrederick.csv |
| effect at 3–5 hops, dead at 6; three-hop F = 25 | 101 + 102 (7.3) | reg_unified_hopsweep.csv |
| conflict-prone: N=728 (363/138/323); partial corrs −0.005/−0.003; split 0.0528 (<.001) vs −0.0067 (.712); interaction 0.0335 (.010); gate battery | 148 (7.1b) + 149 (7.12) | reg_cp2_inter.csv, reg_cp2_gates.csv |
| years-in-window 0.0326 → 0.0314 (p₂ᵥ=.007) | 119 (7.8) block (a) | reg_unified_exposure_break.csv |
| pre-1300 partition: 265 blocs; ARI 0.28; <1% identical bloc-mates; cor 0.87/0.96; 0.0325 (p₂ᵥ=.030) | frozen partition (data/frozen) + 121 (7.9); 120 (5.11) regenerates with `--rerun-louvain` | reg_unified_blocs_pre1300.csv |
| principal-party strict outcome 0.026 (p₂ᵥ=.014, 115 nobles); 0.032 (.025) | 118 (7.18) | reg_principal_outcome.csv |

### §4.2 — peer channel
| Claim | Source (stage) | Output |
|---|---|---|
| correlations: 0.52 raw, 0.22 battery-partialled (patched into 153), 0.49 own-reach, r=0.09 | 153 (7.26), 111 (7.22) | console (output/logs) — **0.524 / 0.220 verified** |
| breadth RF panel; family-history panel | 110 (6.4) + 88 (6.3) + 111 (7.22) | reg_peer_rf_domains.csv |
| arbitration-share flip table | 111 (7.22) | same |
| WCB p=.047 (pre-era secterr); RI p-values | 106 (7.5), 115 (7.25) | reg_unified_wcb_proper.csv, reg_peer_rf_permutation.csv |
| Oster δ*=5.9; 10/12 robust | 112 (7.23) | reg_peer_rf_oster.csv |
| ambient bounding 0.0325 → 0.0290 → 0.0275 (N=2,193); share-instrument corr 0.03 | 153 (7.26) | reg_unified_ambient.csv |
| ally/rival bands; 3–5 similar; FE/cluster variants | 140 (6.6), 141 (7.27), 144 (7.30), 155 (7.31) → 154/159 | reg_band_battery.csv, reg_band34_battery.csv |
| sibship ICC 0.97; mother-level peer permutations (.003/.008/.003/.001); breadth sibship p=.19 | 141b/141c (7.28, 7.29) | reg_band_inference.csv, reg_ball_sibship_inference.csv |
| censoring C1–C3 | 113 (7.24) | reg_peer_rf_censoring.csv |
| break sweep 1195–1235 (−0.05..−0.07); donut 1205–1225; Continental-only +0.24/−0.06; British Isles no variation | 119 (7.8) blocks (b), (c) | reg_unified_exposure_break.csv |
| Andrew Árpád example (53 kin; 1.42; 0.094) | fig_peer_triptych.py (8.11) | figure + console |
| effective clusters ≈ 2.5 | 157 (7.7) | reg_effective_clusters.csv |
| reverse RF (−0.720/−0.589/−0.154) + erosion (−0.687/−0.344) | 81, 82 (7.19–7.20) | reg_reverse_rf.csv, reg_reverse_erosion.csv |
| Chen–Roth ~90% intensive; N=2,181 | 97 (7.14) | decomp_chenroth_domains.csv |

### Appendix D — prompts
The extraction prompt is `doc_match_prompt.py` (rendered by 09/10); the coding
prompt and JSON schema are in `12_recode_subjects.py`. Both are reproduced
verbatim in the draft's appendix.

### Appendix C — partition-robustness sweep
| Claim | Source (stage) | Output |
|---|---|---|
| 50 Louvain redraws: secterr β median 0.0342, range [0.0174, 0.0412], all positive; bloc-clustered p<.05 in 47/50 (worst .119); two-way p<.05 in 40/50 (worst .155) | sweep_partition.py (11.1, optional `--sweep`) | validation/partition_sweep/partition_seed_sweep.csv — **verified** (seeded; seed-level reruns reproduce to the digit) |
| β rises with partition quality: cor(β, modularity) = +0.59; cor(β, agreement with frozen reach) = +0.69; attenuated draws are lower-quality partitions | same CSV (diagnostics computable from its columns) | same |
| Leiden draw (Q = 0.837, highest of any partition): secterr 0.0379 (p₂ᵥ .0027); total 0.0407 (p₂ᵥ .0355) | sweep_partition.py (11.2, `--leiden`) | same |
| frozen (paper) partition: Q = 0.8291, 579 blocs — below the sweep's median β, finest partition observed | reference row `algorithm=frozen_paper` in the same CSV | same |

## Frozen AI artifacts (data/frozen/) — provenance

| File | What it is | Producing process |
|---|---|---|
| verdicts_sonnet-4-6.zip | 24,130 per-letter extraction verdicts (JSONL) | Claude Sonnet 4.6 batch run (10_doc_match_batch_submit.py), default temperature — not bit-reproducible; ~$330 in API charges |
| matched_docs_coded.csv | subject coding of the 4,536 matched letters | Claude Sonnet 4.6 batch (12_recode_subjects.py), temperature 0 |
| agent_coded_overlap.csv | independent second coding of 2,000 letters | separate model pass, identical codebook |
| reextract_validation_aggregated.csv | 119-record cross-model match audit | model subagent audit (scripts in the project archive, not this package; see DISCREPANCIES on the draft's auditor-model attribution) |
| reextract_phase2_validation_sample.csv | 38-record hand-checked match audit | human (author) |
| ai_calibration_verdicts.jsonl | 200-record calibration of the superseded regex pipeline | retained for provenance only; no draft number depends on it |
| patriline_bloc_assignment.csv | the paper's Louvain marriage-bloc partition | 55_patriline_blocs.py (Louvain is stochastic; the frozen partition is the default, `--rerun-louvain` regenerates) |
| patriline_bloc_assignment_pre1300.csv, bloc_reach_pre1300.csv | the paper's pre-1300 repartition (robustness appendix) | 120_blocs_pre1300.py (same frozen-Louvain policy; see DISCREPANCIES note 5) |
| validation/audit_blitz, validation/audit_ra_partial | human match-audit items + verdicts (researcher; RA) | v94 / v90 built the samples; humans coded the verdicts |
| validation/heiress/*.csv | hand rulings for the heiress classification | author |

## Deliberately excluded (in the project archive, not this package)

Scripts that produce no number/figure/table in this draft: the match-recovery
pipeline (160–171), marriage-increment test (130/131), zone/ring analyses
(135–138b), network-breadth series (132/133), cohesion horserace (62 ships
only as an input builder; 65–67 excluded), variance test (69/70),
dynasty-IV cross-check (49), speccompare/heiress-bins appendix tables
(emitters trimmed in 117/147 output where the draft dropped the table),
old prominence tests (68, 139), wide break sweep (145), saturation dating
(143), trimmed-Poisson variant (96b — console-only, no draft number), deprecated fig_measure_hopcorr.py, theory-sim figures
(fig_theory_*), recall-audit sheet builders (phase-2 false-negative audit is
reported as in progress, with no numbers in the draft); v91_audit_agreement.py
(per-directory audit scorer superseded by v95/v96 for the draft's numbers).

## DISCREPANCIES between draft and reproduction

Items 1–3 below were found during the 2026-09-03 verification and are
**RESOLVED in the paper revision of 2026-09-04** (the version shipped in
paper/): the both-coders count now reads 258, the auditor-model attribution
was corrected, and the shortlist sentence now states the verified medians
(1,708 → 106). They are retained here as a record of the verification.

1. **RESOLVED — "403 documents" (subject-coding appendix)**: the both-coders
   secular-territorial set contains **258** documents (93 API-only, 137
   agent-only, 1,512 neither; 2,000 total). The regression digits (0.025,
   p₂ᵥ 0.002 vs 0.026) reproduce exactly on the 258-document set.
2. **RESOLVED — auditor-model attribution (validation appendix)**: an earlier
   draft attributed the 119-record audit to a specific frontier model; the
   project archive records Claude Sonnet-family subagents, and the revision
   now says "an independent auditor model".
3. **RESOLVED — shortlist screen sentence (matching appendix)**: pre-screen
   median is 1,708 (mean 1,634; min 358, p25 1,448, p75 1,804, max 2,307);
   post-screen, under the exact production filter, median 106 (mean 131.9).
   The revision states the medians.
4. **RESOLVED — heiress note "F=354" and "indicator is null"**: previously
   hardcoded prose; 147 now computes and emits both, and the clean-room run
   confirms F_first = 354 and indicator +0.007 (p = 0.88). The draft's claim
   is correct.
5. **Note — pre-1300 repartition digits are partition-vintage-specific**: the
   draft's "265 blocs / ARI 0.28 / cor 0.87, 0.96 / 0.0325 (p₂ᵥ .030)" reproduce
   exactly from the frozen pre-1300 partition shipped in `data/frozen/`.
   Re-running Louvain (`--rerun-louvain`) draws a different partition (our
   rerun: 267 blocs, ARI 0.283, cor 0.865/0.942, β = 0.0397, p₂ᵥ .0012) — the
   robustness conclusion is unchanged or stronger, but the specific digits
   require the frozen partition, exactly as for the main bloc partition.
6. **Format drift — `tab:peer_flip`**: the regenerated table adds a
   $p_{2\text{way}}$ column per era not present in the draft's pasted version;
   all numbers the draft prints match exactly.
