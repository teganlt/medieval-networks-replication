#!/usr/bin/env Rscript
# 157_effective_clusters.R
# ========================
# Leverage-adjusted effective cluster counts for the Pred-1 reduced form
# (Carter-Schnepel-Steigerwald-style 1/sum(s^2) diagnostics on the bloc
# dimension): shares of battery-residualized instrument variation per bloc,
# and shares of squared score contributions per bloc. Backs the appendix
# sentence that the effective number of blocs is ~2.5 for secterr.
# Output: output/clean_iv/reg_effective_clusters.csv
ROOT <- if (length(commandArgs(trailingOnly=TRUE)) >= 1) commandArgs(trailingOnly=TRUE)[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table)})
df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
X0 <- model.matrix(as.formula(paste("~", paste(anc, collapse=" + "),
      "+ f_extra4 + factor(title_rank) + factor(death_decade) + factor(dynasty)")), data = df)
qr0 <- qr(X0)
zt <- qr.resid(qr0, df$mother_n_dyn_4hop)
res <- list()
for (dom in c("secular_territorial", "total")) {
  yt <- qr.resid(qr0, log1p(df[[paste0("dom_", dom)]]))
  eh <- yt - zt * (sum(zt * yt) / sum(zt * zt))          # RF residuals
  g  <- df$dynasty
  wz <- tapply(zt^2, g, sum);      sz <- wz / sum(wz)    # instrument-variation shares
  us <- tapply(zt * eh, g, sum);   ss <- us^2 / sum(us^2) # score-contribution shares
  res[[dom]] <- data.table(domain = dom,
    G_eff_instrument = 1 / sum(sz^2), G_eff_score = 1 / sum(ss^2),
    top_bloc_instr_share = max(sz), top_bloc_score_share = max(ss))
  cat(sprintf("%-20s G*_instrument=%.2f  G*_score=%.2f  (top bloc shares %.2f / %.2f)\n",
      dom, 1/sum(sz^2), 1/sum(ss^2), max(sz), max(ss)))
}
fwrite(rbindlist(res), file.path(OUTDIR, "clean_iv", "reg_effective_clusters.csv"))
cat("Wrote output/clean_iv/reg_effective_clusters.csv\n")
