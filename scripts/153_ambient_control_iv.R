#!/usr/bin/env Rscript
# 153_ambient_control_iv.R
# ========================
# E3 required fix (docs/ADVERSARIAL_2026-07-31.md): the ambient-channel-
# controlled headline IV. Mother's pre-natal reach correlates with the peer
# breadth exposure (r ~ 0.52), and breadth reaches the outcome directly
# (tab_peer_rf), so the Pred-1 exclusion leak through the ambient channel is
# bounded by controlling its measured carriers: zB (pre-birth peer breadth)
# and zD (pre-birth peer secterr adoption share). Rows: headline on the
# peer-covered subsample, +zB, +zB+zD.
# Output: output/clean_iv/reg_unified_ambient.csv
# Usage:  Rscript 153_ambient_control_iv.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
pr <- fread(file.path(OUTDIR, "clean_iv", "peer_rf_build.csv"))
df <- merge(df, pr, by = "person_id")
df <- df[peer_nkin > 0]
df[, zB := (peer_breadth_pre   - mean(peer_breadth_pre))   / sd(peer_breadth_pre)]
df[, zD := (peer_secterr_dated - mean(peer_secterr_dated)) / sd(peer_secterr_dated)]
cat(sprintf("N=%d  cor(instrument, zB)=%.3f  cor(instrument, zD)=%.3f\n",
            nrow(df), cor(df$mother_n_dyn_4hop, df$zB), cor(df$mother_n_dyn_4hop, df$zD)))

# battery-partialled correlation between the instrument and breadth
# (cited in the body's footnote alongside the raw 0.52)
partial_cor_batt <- local({
  anc0 <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
    "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
    "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
    "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
  rhs <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc0, "f_extra4"),
               collapse = " + ")
  r1 <- tryCatch(resid(feols(as.formula(paste("mother_n_dyn_4hop ~", rhs)), data = df)),
                 error = function(e) NULL)
  r2 <- tryCatch(resid(feols(as.formula(paste("zB ~", rhs)), data = df)),
                 error = function(e) NULL)
  if (is.null(r1) || is.null(r2)) NA_real_ else cor(r1, r2)
})
cat(sprintf("partial cor(instrument, zB | battery) = %.3f\n", partial_cor_batt))

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
BAT <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc, "f_extra4"), collapse = " + ")

pull <- function(m, term, twoway = FALSE) {
  if (is.null(m)) return(c(NA_real_, NA_real_, NA_real_))
  s <- if (twoway) tryCatch(summary(m, vcov = ~dynasty + death_decade), error = function(e) NULL) else m
  if (is.null(s)) return(c(NA_real_, NA_real_, NA_real_))
  ct <- as.data.frame(coeftable(s)); ct$t <- rownames(ct)
  pcol <- intersect(c("Pr(>|t|)", "Pr(>|z|)"), names(ct))[1]
  r <- ct[ct$t == term, ]; if (nrow(r) == 0) c(NA_real_, NA_real_, NA_real_) else c(r$Estimate, r$`Std. Error`, r[[pcol]])
}

d <- copy(df); d[, .y := log1p(dom_secular_territorial)]
specs <- list(
  headline_subsample = BAT,
  plus_zB            = paste("zB", BAT, sep = " + "),
  plus_zB_zD         = paste("zB + zD", BAT, sep = " + "))

rows <- list()
cat(sprintf("\n%-20s %9s %9s %9s %9s %7s\n", "spec", "beta", "SE", "p_bloc", "p_2way", "Ffirst"))
for (nm in names(specs)) {
  m <- tryCatch(feols(as.formula(sprintf(".y ~ %s | n_dyn_4hop ~ mother_n_dyn_4hop", specs[[nm]])),
                      data = d, cluster = ~dynasty), error = function(e) NULL)
  b <- pull(m, "fit_n_dyn_4hop"); b2 <- pull(m, "fit_n_dyn_4hop", TRUE)
  Ff <- if (is.null(m)) NA_real_ else tryCatch(fitstat(m, "ivwald")$`ivwald1::n_dyn_4hop`$stat, error = function(e) NA_real_)
  rows[[nm]] <- data.table(spec = nm, beta = b[1], SE = b[2], p_bloc = b[3], p_2way = b2[3],
                           F_first = Ff, N = if (is.null(m)) NA_integer_ else nobs(m))
  cat(sprintf("%-20s %9.4f %9.4f %9.2e %9.4f %7.1f\n", nm, b[1], b[2], b[3], b2[3], Ff))
}
fwrite(rbindlist(rows), file.path(OUTDIR, "clean_iv", "reg_unified_ambient.csv"))
cat("\nWrote output/clean_iv/reg_unified_ambient.csv\n")
