# 141b_band_sibship_perm.R
# ========================
# SIBSHIP-LEVEL permutation placebo + restricted WCB for the reformulated
# Prediction-2 headline cells (8/21; retires the E2 individual-level RI).
#
# Why sibship: the exposures vary at the family level (ICC 0.97; brothers are
# near-duplicates), so a valid placebo must shuffle at the mother level.
# Scheme: mother's treatment value = mean of her sons' exposure; permute the
# mother-level values across mothers WITHIN strata (bloc x decade of eldest
# in-frame son); every son inherits his mother's permuted value. Mothers alone
# in their stratum keep their value (standard). The observed statistic uses
# the same mother-mean treatment so observed and placebo are like-for-like;
# the individual-exposure beta is reported alongside for transparency.
# Diagnostic: perm SD / analytic SE (the ratio that exposed the old RI).
#
# Cells: zRB & zRD x era on secterr; zRD x era on total. 999 draws.
# WCB: fwildclusterboot boottest, Rademacher B=9999, cluster bloc (tryCatch).
# Out: output/clean_iv/reg_band_inference.csv
# CLI: Rscript scripts/141b_band_sibship_perm.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
set.seed(42); B <- 999

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
bd <- fread(file.path(OUTDIR, "clean_iv", "peer_rf_build.csv"))[
  , .(person_id, peer_nkin, peer_breadth_pre, peer_secterr_dated)]
df <- merge(df, bd, by = "person_id")
df <- df[peer_nkin > 0 & !is.na(mother_id) & mother_id != ""]
df[, EMFP := as.integer(birth <= 1215)]
zs <- function(x) (x - mean(x)) / sd(x)
df[, `:=`(z_rival_br = zs(peer_breadth_pre), z_rival_ss = zs(peer_secterr_dated))]
# NOTE (8/21): despite the variable names inherited from 141b, this run is on
# the PAPER'S BALL EXPOSURES (zB = peer_breadth_pre, zD = peer_secterr_dated)
# -- the sibship inference of record for Tables 5-6 (option A).

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
BAT <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc, "f_extra4"), collapse = " + ")

# mother-level frame: value = mother-mean exposure; stratum = bloc x eldest-son decade
df[, eldest := min(birth), by = mother_id]
df[, stratum := paste(dynasty, 10 * (eldest %/% 10), sep = "_")]
mo <- df[, .(mb = mean(z_rival_br), ms = mean(z_rival_ss), stratum = stratum[1]), by = mother_id]
df <- merge(df, mo[, .(mother_id, mb, ms)], by = "mother_id")
cat(sprintf("N=%d sons, %d mothers, %d strata (%.0f%% of mothers share a stratum with another)\n",
            nrow(df), nrow(mo), uniqueN(mo$stratum),
            100 * mean(mo[, .N, by = stratum][mo, on = "stratum"]$N > 1)))

fit_b <- function(d, tr, dom) {
  d[, .y := log1p(get(paste0("dom_", dom)))]
  m <- feols(as.formula(sprintf(".y ~ %s + n_dyn_4hop + %s", tr, BAT)), data = d, cluster = ~dynasty)
  ct <- as.data.frame(coeftable(m))
  s2 <- tryCatch(summary(m, vcov = ~dynasty + death_decade), error = function(e) NULL)
  p2 <- if (is.null(s2)) NA_real_ else as.data.frame(coeftable(s2))[tr, "Pr(>|t|)"]
  list(m = m, b = ct[tr, "Estimate"], se = ct[tr, "Std. Error"], p = ct[tr, "Pr(>|t|)"], p2 = p2)
}

CELLS <- list(
  list(tr = "z_rival_br", mcol = "mb", era = 1L, dom = "secular_territorial"),
  list(tr = "z_rival_br", mcol = "mb", era = 0L, dom = "secular_territorial"),
  list(tr = "z_rival_ss", mcol = "ms", era = 1L, dom = "secular_territorial"),
  list(tr = "z_rival_ss", mcol = "ms", era = 0L, dom = "secular_territorial"),
  list(tr = "z_rival_ss", mcol = "ms", era = 1L, dom = "total"),
  list(tr = "z_rival_ss", mcol = "ms", era = 0L, dom = "total"))

res <- list()
for (cl in CELLS) {
  d <- df[EMFP == cl$era]
  obs_i <- fit_b(copy(d), cl$tr, cl$dom)                       # individual exposure (headline)
  d2 <- copy(d); d2[, tperm := get(cl$mcol)]
  obs_m <- fit_b2 <- {
    d2[, .y := log1p(get(paste0("dom_", cl$dom)))]
    m <- feols(as.formula(sprintf(".y ~ tperm + n_dyn_4hop + %s", BAT)), data = d2, cluster = ~dynasty)
    as.data.frame(coeftable(m))["tperm", "Estimate"]
  }
  bs <- rep(NA_real_, B)
  mo_e <- mo[mother_id %in% d$mother_id]
  for (b_ in seq_len(B)) {
    perm <- copy(mo_e)
    perm[, val := get(sub("z_rival_br", "mb", sub("z_rival_ss", "ms", cl$mcol)))]
    perm[, val := val[sample.int(.N)], by = stratum]
    dd <- merge(copy(d), perm[, .(mother_id, val)], by = "mother_id")
    dd[, .y := log1p(get(paste0("dom_", cl$dom)))]
    m <- tryCatch(feols(as.formula(sprintf(".y ~ val + n_dyn_4hop + %s", BAT)), data = dd, lean = TRUE, notes = FALSE),
                  error = function(e) NULL)
    if (!is.null(m)) bs[b_] <- coef(m)["val"]
  }
  bs <- bs[is.finite(bs)]
  p_perm <- (1 + sum(abs(bs) >= abs(obs_m))) / (1 + length(bs))
  ratio <- sd(bs) / obs_i$se
  # restricted WCB on the individual-exposure model
  p_wcb <- tryCatch({
    suppressMessages(library(fwildclusterboot))
    bt <- suppressWarnings(boottest(obs_i$m, param = cl$tr, clustid = "dynasty", B = 9999,
                                    type = "rademacher", impose_null = TRUE))
    bt$p_val
  }, error = function(e) NA_real_)
  res[[length(res)+1]] <- data.table(era = ifelse(cl$era == 1, "EMFP", "post"), domain = cl$dom, term = cl$tr,
    beta = obs_i$b, SE = obs_i$se, p_bloc = obs_i$p, p_2way = obs_i$p2,
    beta_mmean = obs_m, p_perm_sibship = p_perm, perm_sd_over_SE = ratio, p_wcb = p_wcb, n_perm = length(bs))
  cat(sprintf("%-4s %-20s %-11s beta=%+.4f p=%.4f p2w=%.4f | sibship-perm p=%.3f (SDratio %.2f) | WCB p=%s\n",
              ifelse(cl$era == 1, "EMFP", "post"), cl$dom, cl$tr, obs_i$b, obs_i$p, obs_i$p2,
              p_perm, ratio, ifelse(is.na(p_wcb), "--", sprintf("%.3f", p_wcb))), sep = "")
}
fwrite(rbindlist(res), file.path(OUTDIR, "clean_iv", "reg_ball_sibship_inference.csv"))
cat("Wrote reg_ball_sibship_inference.csv\n")
