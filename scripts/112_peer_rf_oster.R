#!/usr/bin/env Rscript
# 112_peer_rf_oster.R
# ===================
# Oster (2019) bounds for the composite peer RF (111), FULL GRID disclosed —
# the audit flagged that the old paper cited only the single favorable cell.
# Selection extrapolated from the observed family court-history battery
# (fa_ldisp + patriline indices) to unobserved within-bloc family traits.
#   short: y ~ zB + focal reach + ancestor battery + f_extra4 | FE
#   long : short + fa_ldisp + pat_disp_anc + pat_secterr_anc + n_pat_anc
# Every cell reported: era x outcome x Rmax in {1.3*Rtil (capped 1), 1.0}.
# Output: output/clean_iv/reg_peer_rf_oster.csv
# Usage:  Rscript 112_peer_rf_oster.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})

df <- fread(file.path(OUTDIR,"clean_iv","unified_frame.csv"))
pr <- fread(file.path(OUTDIR,"clean_iv","peer_rf_build.csv"))
fam <- fread(file.path(OUTDIR,"clean_iv","reg_complementarity_iv_df_sat2.csv"))[
  , .(person_id, fa_ldisp, pat_disp_anc, pat_secterr_anc, n_pat_anc)]
df <- merge(merge(df, pr, by="person_id"), fam, by="person_id", all.x=TRUE)
for (c in c("fa_ldisp","pat_disp_anc","pat_secterr_anc","n_pat_anc")) df[is.na(get(c)), (c):=0]
df <- df[peer_nkin > 0]
df[, zB := (peer_breadth_pre - mean(peer_breadth_pre)) / sd(peer_breadth_pre)]

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
BASE <- paste(c("zB","n_dyn_4hop", anc, "f_extra4"), collapse=" + ")
FAM  <- "fa_ldisp + pat_disp_anc + pat_secterr_anc + n_pat_anc"
FE   <- "dynasty + death_decade + title_rank"
wr2 <- function(m) tryCatch(as.numeric(r2(m, "wr2")), error=function(e) NA_real_)

res <- list()
for (era in list(c("ALL",-1L), c("EMFP",1L), c("post",0L))) {
  d <- if (era[[2]] < 0) df else df[EMFP == as.integer(era[[2]])]
  for (dom in c("secular_territorial","total")) {
    d2 <- copy(d); d2[, .y := log1p(get(paste0("dom_",dom)))]
    short <- feols(as.formula(sprintf(".y ~ %s | %s", BASE, FE)), data=d2, cluster=~dynasty)
    long  <- feols(as.formula(sprintf(".y ~ %s + %s | %s", BASE, FAM, FE)), data=d2, cluster=~dynasty)
    bdot <- coef(short)["zB"]; btil <- coef(long)["zB"]
    Rdot <- wr2(short); Rtil <- wr2(long)
    for (rm in c(min(1.3*Rtil, 1), 1.0)) {
      denom <- (bdot - btil) * (rm - Rtil)
      bstar1 <- btil - 1 * denom / (Rtil - Rdot)
      dstar <- if (abs(denom) < 1e-12) Inf else btil * (Rtil - Rdot) / denom
      res[[length(res)+1]] <- data.table(era=era[[1]], domain=dom, N=nrow(d2),
        beta_short=bdot, beta_long=btil, R2_short=Rdot, R2_long=Rtil, Rmax=rm,
        beta_star_d1=bstar1, delta_star=dstar,
        robust = (!is.finite(dstar)) | dstar < 0 | dstar >= 1,
        grows_away = abs(btil) >= abs(bdot))
    }
  }
}
R <- rbindlist(res)
fwrite(R, file.path(OUTDIR,"clean_iv","reg_peer_rf_oster.csv"))
cat("=== Oster grid, composite peer RF (treatment zB, per-SD) — ALL cells ===\n")
print(R[, .(era, domain, beta_short=round(beta_short,4), beta_long=round(beta_long,4),
            Rmax=round(Rmax,3), beta_star_d1=round(beta_star_d1,4),
            delta_star=round(delta_star,2), robust, grows_away)])
cat("\nWrote reg_peer_rf_oster.csv\n")
