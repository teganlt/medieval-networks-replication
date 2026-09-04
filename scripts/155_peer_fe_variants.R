#!/usr/bin/env Rscript
# 155_peer_fe_variants.R
# ======================
# FE and clustering variants of the peer reduced forms (111), backing the
# results-section claim that the peer estimates survive patriline and
# birth-decade fixed effects and patriline clustering:
#   V1 birth-decade FEs replace death-decade FEs
#   V2 patriline FEs replace bloc FEs (death-decade kept), cluster patriline
#   V3 baseline FEs, patriline-clustered SEs
# Cells: zB (breadth) and zD (arbitration share) on secular-territorial and
# total, by era. Output: output/clean_iv/reg_peer_fe_variants.csv
# Usage:  Rscript 155_peer_fe_variants.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
pr <- fread(file.path(OUTDIR, "clean_iv", "peer_rf_build.csv"))[
  , .(person_id, EMFP_pr = EMFP, peer_nkin, peer_breadth_pre, peer_secterr_dated)]
pa <- fread(file.path(OUTDIR, "patriline_assignment.csv"))[, .(person_id = id, patriline = dynasty)]
df <- Reduce(function(a, b) merge(a, b, by = "person_id"), list(df, pr, pa))
df <- df[peer_nkin > 0]
df[, zB := (peer_breadth_pre   - mean(peer_breadth_pre))   / sd(peer_breadth_pre)]
df[, zD := (peer_secterr_dated - mean(peer_secterr_dated)) / sd(peer_secterr_dated)]
df[, birth_decade := (birth %/% 10) * 10]
cat(sprintf("N=%d  patrilines=%d\n", nrow(df), uniqueN(df$patriline)))

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
CORE <- paste(c(anc, "f_extra4", "n_dyn_4hop", "factor(title_rank)"), collapse = " + ")

pull <- function(m, term, vc = NULL) {
  if (is.null(m)) return(c(NA_real_, NA_real_))
  s <- if (is.null(vc)) m else tryCatch(summary(m, vcov = vc), error = function(e) NULL)
  if (is.null(s)) return(c(NA_real_, NA_real_))
  ct <- as.data.frame(coeftable(s)); ct$t <- rownames(ct)
  pcol <- intersect(c("Pr(>|t|)", "Pr(>|z|)"), names(ct))[1]
  r <- ct[ct$t == term, ]; if (nrow(r) == 0) c(NA_real_, NA_real_) else c(r$Estimate, r[[pcol]])
}

V <- list(
  V1_birthdec_fe   = list(fe = "factor(dynasty) + factor(birth_decade)",  cl = ~dynasty),
  V2_patriline_fe  = list(fe = "factor(patriline) + factor(death_decade)", cl = ~patriline),
  V3_patriline_cl  = list(fe = "factor(dynasty) + factor(death_decade)",  cl = ~patriline))

res <- list()
for (er in c("EMFP", "post")) {
  d0 <- df[EMFP_pr == as.integer(er == "EMFP")]
  for (dom in c("secular_territorial", "total")) {
    d <- copy(d0); d[, .y := log1p(get(paste0("dom_", dom)))]
    for (tr in c("zB", "zD")) for (vn in names(V)) {
      v <- V[[vn]]
      m <- tryCatch(feols(as.formula(sprintf(".y ~ %s + %s + %s", tr, CORE, v$fe)),
                          data = d, cluster = v$cl), error = function(e) NULL)
      b <- pull(m, tr)
      res[[length(res) + 1]] <- data.table(era = er, domain = dom, term = tr, variant = vn,
        beta = b[1], p = b[2], N = if (is.null(m)) NA_integer_ else nobs(m))
    }
  }
}
R <- rbindlist(res)
fwrite(R, file.path(OUTDIR, "clean_iv", "reg_peer_fe_variants.csv"))
cat(sprintf("\n%-5s %-20s %-3s %-16s %9s %9s\n", "era", "domain", "trt", "variant", "beta", "p"))
for (i in seq_len(nrow(R))) with(R[i], cat(sprintf("%-5s %-20s %-3s %-16s %9.4f %9.4f\n", era, domain, term, variant, beta, p)))
cat("\nWrote output/clean_iv/reg_peer_fe_variants.csv\n")
