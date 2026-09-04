#!/usr/bin/env Rscript
# 106_wcb_proper.R
# ================
# Proper few-cluster inference on the UNIFIED spec (replaces 104's manual
# B=199 fallback):
#  (1) fwildclusterboot restricted Rademacher WCB, B=9999, clustered on the
#      38 blocs, for: reduced form (mother reach -> outcome), first stage,
#      and the 2SLS itself via the WRE (Davidson-MacKinnon) bootstrap on an
#      ivreg fit. Outcomes: secular_territorial, total, eccl_appointments.
#  (2) Same restricted WCB for the peer composite RF (zB), secterr,
#      eras ALL / EMFP / post.
#  (3) Randomization inference, 999 permutations of the instrument within
#      dynasty x death-decade cells, RF beta, all three outcomes.
# Outputs: output/clean_iv/reg_unified_wcb_proper.csv,
#          output/clean_iv/reg_unified_permutation999.csv
# Usage:  Rscript 106_wcb_proper.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")

lib <- Sys.getenv("R_LIBS_USER")
if (nzchar(lib)) { dir.create(lib, recursive = TRUE, showWarnings = FALSE); .libPaths(c(lib, .libPaths())) }
# fwildclusterboot is archived on CRAN for recent R; its maintained builds live
# on the author's r-universe. ivreg is on CRAN.
REPOS <- c("https://s3alfisc.r-universe.dev", "https://cloud.r-project.org")
need <- c("fwildclusterboot", "ivreg")
for (p in need) if (!requireNamespace(p, quietly = TRUE))
  install.packages(p, repos = REPOS, lib = if (nzchar(lib)) lib else NULL)
suppressPackageStartupMessages({library(data.table); library(fixest); library(fwildclusterboot); library(ivreg)})
dqrng_ok <- requireNamespace("dqrng", quietly = TRUE)
set.seed(20260728); if (dqrng_ok) dqrng::dqset.seed(20260728)

B <- 9999
df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
pr <- fread(file.path(OUTDIR, "clean_iv", "peer_rf_build.csv"))
df <- merge(df, pr[, .(person_id, peer_nkin, peer_breadth_pre, EMFP)], by = "person_id", all.x = TRUE)

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
CTL <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc, "f_extra4"), collapse = " + ")
DOMS <- c("secular_territorial", "total", "ecclesiastical_appointments")

wcb_p <- function(fit, param, dat) {
  bt <- tryCatch(
    fwildclusterboot::boottest(fit, param = param, clustid = "dynasty",
                               B = B, type = "rademacher", impose_null = TRUE),
    error = function(e) e)
  if (inherits(bt, "error")) return(list(p = NA_real_, note = conditionMessage(bt)))
  list(p = bt$p_val, note = "")
}

res <- list()
cat(sprintf("N=%d, %d blocs, B=%d\n", nrow(df), uniqueN(df$dynasty), B))

# ---------- (1) unified Pred-1: RF, FS, WRE 2SLS ----------
for (dom in DOMS) {
  d <- copy(df); d[, .y := log1p(get(paste0("dom_", dom)))]
  d <- droplevels(as.data.frame(d))

  rf <- feols(as.formula(paste0(".y ~ mother_n_dyn_4hop + ", CTL)), data = d, cluster = ~dynasty)
  brf <- as.data.frame(coeftable(rf))["mother_n_dyn_4hop", ]
  w <- wcb_p(rf, "mother_n_dyn_4hop", d)
  res[[length(res)+1]] <- data.table(block = "pred1", outcome = dom, stat = "reduced_form",
    beta = brf$Estimate, p_analytic_bloc = brf$`Pr(>|t|)`, p_wcb = w$p, B = B, note = w$note)
  cat(sprintf("[%s] RF     beta=%.5f  p_bloc=%.2e  p_wcb=%.4f %s\n", dom, brf$Estimate, brf$`Pr(>|t|)`, w$p, w$note))

  if (dom == DOMS[1]) {  # first stage identical across outcomes
    fs <- feols(as.formula(paste0("n_dyn_4hop ~ mother_n_dyn_4hop + ", CTL)), data = d, cluster = ~dynasty)
    bfs <- as.data.frame(coeftable(fs))["mother_n_dyn_4hop", ]
    w <- wcb_p(fs, "mother_n_dyn_4hop", d)
    res[[length(res)+1]] <- data.table(block = "pred1", outcome = "(common)", stat = "first_stage",
      beta = bfs$Estimate, p_analytic_bloc = bfs$`Pr(>|t|)`, p_wcb = w$p, B = B, note = w$note)
    cat(sprintf("[FS]   beta=%.5f  p_bloc=%.2e  p_wcb=%.4f\n", bfs$Estimate, bfs$`Pr(>|t|)`, w$p))
  }

  # NOTE: WRE (2SLS) bootstrap in fwildclusterboot >=0.13 requires the Julia
  # backend (WildBootTests.jl), not installed here. With first-stage F=339 the
  # 2SLS inference is carried by the RF (2SLS ~ RF / FS with a tight FS), so
  # the RF+FS restricted-WCB pair is the few-cluster statement.

  # Diagnostics for the conservative full-sample WCB: (a) drop the dominant
  # mega-cluster B3 (29% of obs, 41% of secterr mass) -- if WCB non-rejection
  # is B3-leverage-driven, it should reject without B3; (b) Webb 6-point
  # weights (better with unbalanced clusters).
  dnb <- droplevels(subset(d, dynasty != "B3"))
  rfnb <- feols(as.formula(paste0(".y ~ mother_n_dyn_4hop + ", CTL)), data = dnb, cluster = ~dynasty)
  brfnb <- as.data.frame(coeftable(rfnb))["mother_n_dyn_4hop", ]
  wnb <- wcb_p(rfnb, "mother_n_dyn_4hop", dnb)
  res[[length(res)+1]] <- data.table(block = "pred1", outcome = dom, stat = "reduced_form_dropB3",
    beta = brfnb$Estimate, p_analytic_bloc = brfnb$`Pr(>|t|)`, p_wcb = wnb$p, B = B, note = wnb$note)
  cat(sprintf("[%s] RF-noB3 beta=%.5f  p_bloc=%.2e  p_wcb=%.4f %s\n", dom, brfnb$Estimate, brfnb$`Pr(>|t|)`, wnb$p, wnb$note))

  btw <- tryCatch(fwildclusterboot::boottest(rf, param = "mother_n_dyn_4hop", clustid = "dynasty",
                                             B = B, type = "webb", impose_null = TRUE),
                  error = function(e) e)
  pw <- if (inherits(btw, "error")) NA_real_ else btw$p_val
  res[[length(res)+1]] <- data.table(block = "pred1", outcome = dom, stat = "reduced_form_webb",
    beta = brf$Estimate, p_analytic_bloc = brf$`Pr(>|t|)`, p_wcb = pw, B = B,
    note = if (inherits(btw, "error")) conditionMessage(btw) else "Webb 6-point weights")
  cat(sprintf("[%s] RF-webb p_wcb=%.4f\n", dom, pw))
}

# ---------- (2) peer composite RF (zB), secterr, by era ----------
pf <- df[!is.na(peer_nkin) & peer_nkin > 0]
pf[, zB := (peer_breadth_pre - mean(peer_breadth_pre)) / sd(peer_breadth_pre)]
for (era in list(c("ALL", -1L), c("EMFP", 1L), c("post", 0L))) {
  d <- if (era[[2]] < 0) pf else pf[EMFP == as.integer(era[[2]])]
  d <- copy(d); d[, .y := log1p(dom_secular_territorial)]
  d <- droplevels(as.data.frame(d))
  m <- feols(as.formula(paste0(".y ~ zB + n_dyn_4hop + ", CTL)), data = d, cluster = ~dynasty)
  bb <- as.data.frame(coeftable(m))["zB", ]
  w <- wcb_p(m, "zB", d)
  res[[length(res)+1]] <- data.table(block = "peer_rf", outcome = paste0("secterr_", era[[1]]), stat = "zB",
    beta = bb$Estimate, p_analytic_bloc = bb$`Pr(>|t|)`, p_wcb = w$p, B = B, note = w$note)
  cat(sprintf("[peer %s] zB=%.4f  p_bloc=%.3f  p_wcb=%.4f %s\n", era[[1]], bb$Estimate, bb$`Pr(>|t|)`, w$p, w$note))
  dnb <- droplevels(subset(d, dynasty != "B3"))
  mnb <- feols(as.formula(paste0(".y ~ zB + n_dyn_4hop + ", CTL)), data = dnb, cluster = ~dynasty)
  bbnb <- as.data.frame(coeftable(mnb))["zB", ]
  wnb <- wcb_p(mnb, "zB", dnb)
  res[[length(res)+1]] <- data.table(block = "peer_rf", outcome = paste0("secterr_", era[[1]]), stat = "zB_dropB3",
    beta = bbnb$Estimate, p_analytic_bloc = bbnb$`Pr(>|t|)`, p_wcb = wnb$p, B = B, note = wnb$note)
  cat(sprintf("[peer %s] zB-noB3=%.4f  p_bloc=%.3f  p_wcb=%.4f\n", era[[1]], bbnb$Estimate, bbnb$`Pr(>|t|)`, wnb$p))
}

R1 <- rbindlist(res)
fwrite(R1, file.path(OUTDIR, "clean_iv", "reg_unified_wcb_proper.csv"))

# ---------- (3) randomization inference, 999 draws ----------
NPERM <- 999
df2 <- as.data.table(df)
df2[, cell := paste(dynasty, death_decade)]
perm_res <- list()
for (dom in DOMS) {
  d <- copy(df2); d[, .y := log1p(get(paste0("dom_", dom)))]
  m0 <- feols(as.formula(paste0(".y ~ mother_n_dyn_4hop + ", CTL)), data = d)
  b0 <- coef(m0)["mother_n_dyn_4hop"]
  bp <- numeric(NPERM)
  for (i in seq_len(NPERM)) {
    d[, iv_perm := mother_n_dyn_4hop[sample.int(.N)], by = cell]
    mi <- tryCatch(feols(as.formula(paste0(".y ~ iv_perm + ", CTL)), data = d), error = function(e) NULL)
    bp[i] <- if (is.null(mi)) NA_real_ else coef(mi)["iv_perm"]
    if (i %% 200 == 0) cat(sprintf("  [%s] %d/%d perms\n", dom, i, NPERM))
  }
  bp <- bp[!is.na(bp)]
  pperm <- (1 + sum(abs(bp) >= abs(b0))) / (1 + length(bp))
  perm_res[[length(perm_res)+1]] <- data.table(outcome = dom, beta_obs = b0, n_perm = length(bp),
    p_perm = pperm, perm_mean = mean(bp), perm_sd = sd(bp), z = (b0 - mean(bp)) / sd(bp))
  cat(sprintf("[perm %s] beta_obs=%.5f  p_perm=%.4f  z=%.1f\n", dom, b0, pperm, (b0 - mean(bp)) / sd(bp)))
}
R2 <- rbindlist(perm_res)
fwrite(R2, file.path(OUTDIR, "clean_iv", "reg_unified_permutation999.csv"))
cat("\nWrote reg_unified_wcb_proper.csv, reg_unified_permutation999.csv\n")
