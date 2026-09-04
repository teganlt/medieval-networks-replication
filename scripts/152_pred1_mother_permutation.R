#!/usr/bin/env Rscript
# 152_pred1_mother_permutation.R
# ==============================
# Mother-level (sibship) randomization inference for the Pred-1 reduced form.
# The individual-level RI (106_wcb_proper.R) shuffles the instrument across
# noble-rows, so brothers sharing a mother can draw different placebo values;
# here the instrument is permuted ACROSS MOTHERS, and every son inherits his
# mother's permuted value — the sibship structure of the instrument is
# preserved. Two cell definitions: within bloc (matching 149's mother-level
# permutation), and within bloc x modal-son-death-decade (tighter, preserves
# the decade composition the FEs absorb).
# Statistic: reduced-form slope of log(1+Y) on the permuted instrument after
# FWL residualization on the full unified battery (exact algebra, QR).
# Output: output/clean_iv/reg_unified_perm_mother.csv
# Usage:  Rscript 152_pred1_mother_permutation.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages(library(data.table))
set.seed(42)
NDRAW <- 999L

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
X0 <- model.matrix(as.formula(paste("~", paste(anc, collapse = " + "),
      "+ f_extra4 + factor(title_rank) + factor(death_decade) + factor(dynasty)")), data = df)
qr0 <- qr(X0)

# mother-level table: one row per mother, instrument value + cells
df[, son_dd := death_decade]
mo <- df[, .(z = mother_n_dyn_4hop[1], dynasty = dynasty[1],
             dd = as.integer(names(sort(table(son_dd), decreasing = TRUE))[1])), by = mother_id]
gidx <- match(df$mother_id, mo$mother_id)
cat(sprintf("N=%d nobles, %d mothers, %d blocs\n", nrow(df), nrow(mo), uniqueN(df$dynasty)))

rf_beta <- function(zvec, ey) {
  ez <- qr.resid(qr0, zvec)
  sum(ez * ey) / sum(ez * ez)
}

res <- list()
for (dom in c("secular_territorial", "total")) {
  y <- log1p(df[[paste0("dom_", dom)]])
  ey <- qr.resid(qr0, y)
  ob <- rf_beta(df$mother_n_dyn_4hop, ey)
  for (cell in c("bloc", "bloc_x_decade")) {
    bs <- rep(NA_real_, NDRAW)
    for (b_ in seq_len(NDRAW)) {
      p <- copy(mo)
      if (cell == "bloc") p[, zp := z[sample.int(.N)], by = dynasty]
      else                p[, zp := z[sample.int(.N)], by = .(dynasty, dd)]
      bs[b_] <- rf_beta(p$zp[gidx], ey)
    }
    bs <- bs[is.finite(bs)]
    z_ri <- (ob - mean(bs)) / sd(bs)
    p_ri <- (1 + sum(abs(bs) >= abs(ob))) / (1 + length(bs))
    res[[paste(dom, cell)]] <- data.table(domain = dom, unit = "mother", cell = cell,
      n_draws = length(bs), beta_obs = ob, perm_mean = mean(bs), perm_sd = sd(bs),
      z = z_ri, p_perm = p_ri)
    cat(sprintf("%-22s cell=%-14s beta_obs=%.5f perm_sd=%.5f z=%.2f p=%.4f\n",
                dom, cell, ob, sd(bs), z_ri, p_ri))
  }
}
res <- rbindlist(res)
fwrite(res, file.path(OUTDIR, "clean_iv", "reg_unified_perm_mother.csv"))
cat("Wrote output/clean_iv/reg_unified_perm_mother.csv\n")
