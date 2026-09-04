#!/usr/bin/env Rscript
# 104_wcb_permutation.R
# =====================
# FEW-CLUSTER INFERENCE for the unified Prediction-1 baseline (100_unified_
# baseline.R spec; 38 bloc clusters -- asymptotic clustered SEs may over-
# reject).  Two design-based checks, on the SAVED analysis frame
# output/clean_iv/unified_frame.csv, for outcomes log1p(dom_secular_
# territorial), log1p(dom_total), log1p(dom_ecclesiastical_appointments):
#
#  (a) WILD CLUSTER BOOTSTRAP (Cameron-Gelbach-Miller), Rademacher cluster
#      weights, B=9999, clustered on dynasty(=bloc), NULL-IMPOSED
#      (restricted) bootstrap-t, for
#        - the REDUCED FORM  (mother_n_dyn_4hop entering directly with the
#          full unified control set), and
#        - the FIRST STAGE   (n_dyn_4hop on mother_n_dyn_4hop + controls;
#          identical across outcomes, run once).
#      Neither fwildclusterboot nor boottest is installed in this R
#      library (checked 2026-07-28), so the manual CGM machinery is ported
#      from the project archive: 25_wild_cluster_bootstrap.R and
#      the project archive: 49f_wcb_excess.R, with a Frisch-Waugh/QR
#      speedup: in the restricted (null-imposed) design only y* changes
#      across draws, so we residualize once on the control matrix X and
#      recompute beta*, CRV1 t* analytically each draw.  A boottest-style
#      WRE bootstrap of the 2SLS coefficient itself is NOT run (no package;
#      hand-rolling WRE is error-prone) -- with first-stage F ~ 339 the
#      RF + FS pair is the honest few-cluster statement, and that caveat is
#      recorded in the output note column.
#
#  (b) RANDOMIZATION INFERENCE: NPERM=999 permutations of the instrument
#      WITHIN dynasty x death_decade cells (mirrors the within-cell
#      permutation-placebo design of the project archive: 
#      47_robustness_clean.R [4], which conditions the permutation on the
#      fixed-effect strata); empirical two-sided p for the RF beta.
#
# Manual FWL beta/t are cross-checked against feols before use (stop if
# beta mismatch > 1e-6 relative).
#
# Outputs (output/clean_iv/):
#   reg_unified_wcb.csv          outcome, stat, beta, p_analytic_bloc,
#                                p_analytic_2way, p_wcb_restricted, B, note
#   reg_unified_permutation.csv  outcome, beta_obs, n_perm, p_perm
#
# Usage: Rscript 104_wcb_permutation.R [<ROOT>] [B] [NPERM]

args <- commandArgs(trailingOnly = TRUE)
ROOT  <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
B     <- if (length(args) >= 2 && nzchar(args[2])) as.integer(args[2]) else 9999L
NPERM <- if (length(args) >= 3 && nzchar(args[3])) as.integer(args[3]) else 999L
OUTDIR <- file.path(ROOT, "output")
CLEAN  <- file.path(OUTDIR, "clean_iv")
suppressPackageStartupMessages({library(data.table); library(fixest)})
set.seed(20260728)

df <- fread(file.path(CLEAN, "unified_frame.csv"))
H <- 4L
ENDO <- sprintf("n_dyn_%dhop", H); INST <- sprintf("mother_n_dyn_%dhop", H)

# ---- unified control set (ctl_new of 100_unified_baseline.R) ----
anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
fe  <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
ctl <- paste(c(fe, anc, "f_extra4"), collapse=" + ")

OUTS <- c(secular_territorial = "dom_secular_territorial",
          total               = "dom_total",
          ecclesiastical_appointments = "dom_ecclesiastical_appointments")
for (o in names(OUTS)) df[, (paste0("y_", o)) := log1p(get(OUTS[[o]]))]

# ---- control model matrix, residualized once (FWL) ----
X <- model.matrix(as.formula(paste("~", ctl)), data = df)
stopifnot(nrow(X) == nrow(df))               # no NA rows silently dropped
qrX  <- qr(X)                                 # pivoted; rank-deficiency ok
rk   <- qrX$rank
Q    <- qr.Q(qrX)[, seq_len(rk), drop = FALSE]
Mx   <- function(v) v - Q %*% crossprod(Q, v) # annihilator of col-space(X)
z    <- df[[INST]]
zt   <- as.numeric(Mx(z)); denom <- sum(zt^2)
cl   <- df$dynasty; ucl <- sort(unique(cl)); G <- length(ucl)
clab <- match(cl, ucl)

# dominant-cluster leverage on the residualized instrument (the WCB caveat,
# cf. 49f's Norman_Ducal share): share_g = sum_{i in g} ztilde_i^2 / sum ztilde^2
lev <- data.table(bloc = cl, z2 = zt^2)[, .(share = sum(z2)), by = bloc][order(-share)]
lev[, share := share / sum(share)]
LEV_NOTE <- sprintf("dominant-cluster leverage: %s=%.0f%%, top3=%.0f%% of residualized-instrument variation -> restricted WCB severely conservative (MacKinnon-Webb); randomization inference is the design-based test robust to this",
                    lev$bloc[1], 100*lev$share[1], 100*sum(lev$share[1:3]))
Npts <- nrow(df); Kfull <- rk + 1L
ssc_c <- (G/(G-1)) * ((Npts-1)/(Npts-Kfull))  # CRV1, fixest default ssc

crv1_t <- function(beta, e) {                 # cluster-robust t for the z coef
  sc <- rowsum(zt * e, clab)
  se <- sqrt(ssc_c * sum(sc^2)) / denom
  beta / se
}
fwl_fit <- function(y) {                      # y already numeric vector
  yt   <- as.numeric(Mx(y))
  beta <- sum(zt * yt) / denom
  e    <- yt - beta * zt
  list(beta = beta, t = crv1_t(beta, e), u_restricted = yt)  # M_X y = restricted resid
}
# restricted (null-imposed) WCB: y* = X b_r + u_r*w  =>  M_X y* = M_X(u_r*w)
wcb_p <- function(u_r, t_obs, tag) {
  bt <- rep(NA_real_, B); t0 <- Sys.time()
  for (b in seq_len(B)) {
    w  <- sample(c(-1, 1), G, replace = TRUE)[clab]
    vt <- as.numeric(Mx(u_r * w))
    bb <- sum(zt * vt) / denom
    bt[b] <- crv1_t(bb, vt - bb * zt)
    if (b %% 2000 == 0) cat(sprintf("    [%s] b=%d/%d (%.0fs)\n", tag, b, B,
      as.numeric(difftime(Sys.time(), t0, units="secs"))))
  }
  bt <- bt[is.finite(bt)]
  cat(sprintf("    [%s] |t*| quantiles 50/90/95/99: %s\n", tag,
      paste(sprintf("%.1f", quantile(abs(bt), c(.5,.9,.95,.99))), collapse=" / ")))
  list(p = mean(abs(bt) >= abs(t_obs)), B_used = length(bt))
}

# ---- analytic feols fits (reference p-values + FWL verification) ----
p2way_of <- function(m, term) {
  s <- tryCatch(summary(m, vcov = ~dynasty + death_decade), error=function(e) NULL)
  if (is.null(s)) return(NA_real_)
  ct <- as.data.frame(coeftable(s)); ct$t <- rownames(ct)
  pc <- intersect(c("Pr(>|t|)","Pr(>|z|)"), names(ct))[1]
  r <- ct[ct$t == term, ]; if (nrow(r)) r[[pc]] else NA_real_
}
row_of <- function(m, term) {
  ct <- as.data.frame(coeftable(m)); ct$t <- rownames(ct)
  setnames(ct, "Std. Error", "SE")
  pc <- intersect(c("Pr(>|t|)","Pr(>|z|)"), names(ct))[1]
  r <- ct[ct$t == term, ]; list(beta = r$Estimate, se = r$SE, p = r[[pc]],
                                tstat = r$Estimate / r$SE)
}

NOTE_2SLS <- "no boottest/fwildclusterboot installed; 2SLS WCB (WRE) not run -- restricted-WCB RF+FS pair is the few-cluster statement (F_first~339 so RF ~ 2SLS x FS scale)"
res <- list()

cat(sprintf("N=%d  clusters(blocs)=%d  rank(X)=%d  B=%d  NPERM=%d\n", Npts, G, rk, B, NPERM))
cat("Top blocs by share of residualized-instrument variation (WCB leverage caveat):\n")
print(head(lev, 5)); cat(LEV_NOTE, "\n\n")

# ---- FIRST STAGE (outcome-invariant): analytic + restricted WCB ----
cat("=== FIRST STAGE ===\n")
m_fs <- feols(as.formula(sprintf("%s ~ %s + %s", ENDO, INST, ctl)), df, cluster=~dynasty)
a_fs <- row_of(m_fs, INST)
f_fs <- fwl_fit(df[[ENDO]])
stopifnot(abs(f_fs$beta - a_fs$beta) < 1e-6 * max(1, abs(a_fs$beta)))
cat(sprintf("  beta=%.4f  t_feols=%.3f  t_manual=%.3f  (F_first=t^2=%.0f)\n",
            a_fs$beta, a_fs$tstat, f_fs$t, a_fs$tstat^2))
w_fs <- wcb_p(f_fs$u_restricted, f_fs$t, "FS")
cat(sprintf("  p_analytic_bloc=%.2e  p_wcb_restricted=%.4f (B=%d)\n\n",
            a_fs$p, w_fs$p, w_fs$B_used))
res[[length(res)+1]] <- data.table(outcome="(common)", stat="first_stage",
  beta=a_fs$beta, p_analytic_bloc=a_fs$p, p_analytic_2way=p2way_of(m_fs, INST),
  p_wcb_restricted=w_fs$p, B=w_fs$B_used, max_lev_bloc=lev$bloc[1], max_lev_share=lev$share[1],
  note=paste("first stage identical across outcomes; run once.", LEV_NOTE))

# ---- per outcome: 2SLS analytic, RF analytic + WCB, permutation ----
perm_rows <- list()
df[, cell := paste(dynasty, death_decade, sep="_")]
cell_idx <- split(seq_len(Npts), df$cell)

for (o in names(OUTS)) {
  cat(sprintf("=== %s ===\n", o))
  yv <- df[[paste0("y_", o)]]

  # 2SLS analytic (context row; matches 100_unified_baseline.R)
  m_iv <- feols(as.formula(sprintf("y_%s ~ %s | %s ~ %s", o, ctl, ENDO, INST)),
                df, cluster=~dynasty)
  a_iv <- row_of(m_iv, sprintf("fit_%s", ENDO))
  res[[length(res)+1]] <- data.table(outcome=o, stat="2sls_analytic",
    beta=a_iv$beta, p_analytic_bloc=a_iv$p,
    p_analytic_2way=p2way_of(m_iv, sprintf("fit_%s", ENDO)),
    p_wcb_restricted=NA_real_, B=NA_integer_, note=NOTE_2SLS)
  cat(sprintf("  2SLS: beta=%.4f p_bloc=%.4g p_2way=%.4g\n", a_iv$beta, a_iv$p,
              p2way_of(m_iv, sprintf("fit_%s", ENDO))))

  # reduced form: analytic + restricted WCB
  m_rf <- feols(as.formula(sprintf("y_%s ~ %s + %s", o, INST, ctl)), df, cluster=~dynasty)
  a_rf <- row_of(m_rf, INST)
  f_rf <- fwl_fit(yv)
  stopifnot(abs(f_rf$beta - a_rf$beta) < 1e-6 * max(1, abs(a_rf$beta)))
  cat(sprintf("  RF  : beta=%.5f  t_feols=%.3f  t_manual=%.3f\n",
              a_rf$beta, a_rf$tstat, f_rf$t))
  w_rf <- wcb_p(f_rf$u_restricted, f_rf$t, paste0("RF:", o))
  cat(sprintf("  RF  : p_analytic_bloc=%.4g  p_wcb_restricted=%.4f (B=%d)\n",
              a_rf$p, w_rf$p, w_rf$B_used))
  res[[length(res)+1]] <- data.table(outcome=o, stat="reduced_form",
    beta=a_rf$beta, p_analytic_bloc=a_rf$p, p_analytic_2way=p2way_of(m_rf, INST),
    p_wcb_restricted=w_rf$p, B=w_rf$B_used, max_lev_bloc=lev$bloc[1], max_lev_share=lev$share[1],
    note=paste("restricted (null-imposed) Rademacher WCB on bloc clusters.", LEV_NOTE))

  # randomization inference: permute instrument within dynasty x decade cell
  yt <- f_rf$u_restricted                      # M_X y
  b_obs <- a_rf$beta
  bp <- rep(NA_real_, NPERM)
  for (i in seq_len(NPERM)) {
    zp <- z
    for (ix in cell_idx) if (length(ix) > 1L) zp[ix] <- zp[ix][sample.int(length(ix))]
    zpt <- as.numeric(Mx(zp)); dn <- sum(zpt^2)
    if (dn > 1e-10) bp[i] <- sum(zpt * yt) / dn
  }
  bp <- bp[is.finite(bp)]
  p_perm <- mean(abs(bp) >= abs(b_obs))
  cat(sprintf("  PERM: beta_obs=%.5f  perm mean=%.5f sd=%.5f  p_perm=%.4f (n=%d, within dynasty x decade cells)\n\n",
              b_obs, mean(bp), sd(bp), p_perm, length(bp)))
  perm_rows[[length(perm_rows)+1]] <- data.table(outcome=o, beta_obs=b_obs,
    n_perm=length(bp), p_perm=p_perm,
    perm_mean=mean(bp), perm_sd=sd(bp),
    note="RF beta; instrument permuted within dynasty x death_decade cells (mirrors 47_robustness_clean.R placebo design)")
}

res <- rbindlist(res, fill=TRUE)
fwrite(res, file.path(CLEAN, "reg_unified_wcb.csv"))
fwrite(rbindlist(perm_rows), file.path(CLEAN, "reg_unified_permutation.csv"))
cat("=== SUMMARY ===\n"); print(res[, .(outcome, stat, beta=round(beta,4),
  p_analytic_bloc=signif(p_analytic_bloc,3), p_analytic_2way=signif(p_analytic_2way,3),
  p_wcb_restricted, B)])
cat("\nWrote reg_unified_wcb.csv, reg_unified_permutation.csv\n")
