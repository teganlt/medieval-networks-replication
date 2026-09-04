#!/usr/bin/env Rscript
# 115_peer_rf_permutation.R
# =========================
# Randomization inference for the composite peer RF (111) — the design-based
# answer to the era-subsample two-way power problem. For each era x treatment
# x outcome: permute the TREATMENT across focals WITHIN bloc x death-decade
# cells (mirroring 106's design for the Pred-1 instrument), refit the exact
# regression, and compare the observed beta to the permutation distribution.
#   treatments: zB (peer breadth, spec S1) and zD (secterr adoption share,
#               spec S3), standardized on the FULL sample as in 111.
#   outcomes:   secular_territorial, total (log1p).
#   eras:       ALL / EMFP-born (<=1215) / post.
# NPERM=999; two-sided p = (1 + #{|b_perm| >= |b_obs|}) / (1 + NPERM).
# Output: output/clean_iv/reg_peer_rf_permutation.csv
# Usage:  Rscript 115_peer_rf_permutation.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
set.seed(20260730)
NPERM <- 999

df <- fread(file.path(OUTDIR,"clean_iv","unified_frame.csv"))
pr <- fread(file.path(OUTDIR,"clean_iv","peer_rf_build.csv"))
df <- merge(df, pr, by="person_id")
df <- df[peer_nkin > 0]
df[, zB := (peer_breadth_pre    - mean(peer_breadth_pre))    / sd(peer_breadth_pre)]
df[, zD := (peer_secterr_dated  - mean(peer_secterr_dated))  / sd(peer_secterr_dated)]
df[, cell := paste(dynasty, death_decade)]

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
BAT <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc, "f_extra4"), collapse=" + ")

res <- list()
for (era in list(c("ALL",-1L), c("EMFP",1L), c("post",0L))) {
  d0 <- if (era[[2]] < 0) df else df[EMFP == as.integer(era[[2]])]
  for (tr in c("zB", "zD")) {
    rhs <- sprintf("%s + n_dyn_4hop + %s", tr, BAT)
    for (dom in c("secular_territorial", "total")) {
      d <- copy(d0); d[, .y := log1p(get(paste0("dom_", dom)))]
      m0 <- tryCatch(feols(as.formula(paste0(".y ~ ", rhs)), data=d), error=function(e) NULL)
      if (is.null(m0)) next
      b0 <- coef(m0)[tr]
      bp <- numeric(NPERM)
      d[, tr_perm := get(tr)]
      rhs_p <- sprintf("tr_perm + n_dyn_4hop + %s", BAT)
      for (i in seq_len(NPERM)) {
        d[, tr_perm := { v <- get(tr); v[sample.int(.N)] }, by = cell]
        mi <- tryCatch(feols(as.formula(paste0(".y ~ ", rhs_p)), data=d), error=function(e) NULL)
        bp[i] <- if (is.null(mi)) NA_real_ else coef(mi)["tr_perm"]
      }
      bp <- bp[!is.na(bp)]
      pperm <- (1 + sum(abs(bp) >= abs(b0))) / (1 + length(bp))
      res[[length(res)+1]] <- data.table(era=era[[1]], treatment=tr, domain=dom,
        beta_obs=b0, n_perm=length(bp), p_perm=pperm,
        perm_mean=mean(bp), perm_sd=sd(bp), z=(b0-mean(bp))/sd(bp), N=nrow(d))
      cat(sprintf("[%s %s %s] beta=%+.4f  p_perm=%.4f  z=%+.1f  (N=%d)\n",
                  era[[1]], tr, dom, b0, pperm, (b0-mean(bp))/sd(bp), nrow(d)))
    }
  }
}
R <- rbindlist(res)
fwrite(R, file.path(OUTDIR,"clean_iv","reg_peer_rf_permutation.csv"))
cat("\nWrote reg_peer_rf_permutation.csv\n")
