#!/usr/bin/env Rscript
# 116a_persist_poisson.R
# ======================
# Persists the control-function Poisson (7/27 audit flag: 96_cf_poisson_oster.R
# prints everything via cat() and writes nothing; 96b/97 source 96 BY LINE
# NUMBER, so 96 itself must not be edited -- this wrapper persists instead).
# Same CF machinery as 96: first-stage OLS (endo ~ instrument + linear | FE),
# residual v-hat, fepois(count ~ endo + v-hat + linear | FE), pairs-cluster
# bootstrap over relabelled blocs for the generated regressor (seed 42, B=199,
# exactly as 96). Fitted on the UNIFIED-consistent frame + controls
# (100_unified_baseline.R: unified_frame.csv, ancestor battery + f_extra4,
# NO focal log_deg; FE = bloc + death-decade + title-rank; bloc cluster).
# Outcomes (counts, not log1p): dom_secular_territorial, n_dispute
# (is_dispute=='yes' matches, window 1100-1300), dom_total.
# Output: output/clean_iv/reg_unified_poisson_cf.csv
# Usage:  Rscript 116a_persist_poisson.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
set.seed(42); B <- 199

# ---- unified frame (written by 100) + dispute counts ----
df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
coded <- fread(file.path(OUTDIR, "matched_docs_coded.csv"),
               colClasses = list(character = "doc_id"))[, .(doc_id, is_dispute)]
mt <- fread(file.path(OUTDIR, "doc_matches_ai_extracted_high.csv"),
            colClasses = list(character = "doc_id"))[
  doc_year >= 1100 & doc_year <= 1300, .(person_id, doc_id)]
ndisp <- merge(mt, coded, by = "doc_id")[is_dispute == "yes",
                                         .(n_dispute = .N), by = person_id]
df <- merge(df, ndisp, by = "person_id", all.x = TRUE)
df[is.na(n_dispute), n_dispute := 0]

# ---- unified linear controls (ctl_new of 100, minus the FE factors, which
#      enter fepois as true FE exactly as in 96) ----
LIN <- paste(c("factor(mother_title_rank)", "factor(father_title_rank)", "factor(mgf_title_rank)",
               "mother_log_n_nodes_4hop", "father_log_n_nodes_4hop", "mgf_log_n_nodes_4hop",
               "mother_log_pre_deg", "father_log_pre_deg", "mgf_log_pre_deg",
               "mother_log_total_inwin", "father_log_total_inwin", "mgf_log_total_inwin",
               "mgf_n_dyn_4hop", "f_extra4"), collapse = " + ")
FES <- "dynasty + death_decade + title_rank"
CLU <- "dynasty"

# ---- CF machinery (verbatim 96, plus a 30s elapsed-time cap per bootstrap
#      rep: on the unified frame one resampled dispute rep's fepois failed to
#      converge and pinned a core for 20+ minutes; capped reps throw, are
#      caught by the existing tryCatch, and drop out exactly like 96's failed
#      reps -- reflected in B_effective) ----
REP_TIMEOUT <- 30
cf_pois <- function(d, ycol, endo, instr, lin, fes, clu) {
  d <- copy(d)
  fs <- feols(as.formula(paste0(endo, " ~ ", instr, " + ", lin, " | ", fes)), data = d)
  d[, vhat := NA_real_]; d[obs(fs), vhat := resid(fs)]
  d <- d[!is.na(vhat)]
  m <- tryCatch(fepois(as.formula(paste0(ycol, " ~ ", endo, " + vhat + ", lin, " | ", fes)),
                       data = d, cluster = as.formula(paste0("~", clu)), notes = FALSE),
                error = function(e) NULL)
  if (is.null(m)) return(NULL)
  ct <- as.data.frame(coeftable(m))
  list(b = ct[endo, "Estimate"], se = ct[endo, "Std. Error"], p = ct[endo, "Pr(>|z|)"],
       bv = ct["vhat", "Estimate"], pv = ct["vhat", "Pr(>|z|)"], n = m$nobs)
}

boot_cf <- function(d, ycol, endo, instr, lin, fes, clu, B) {
  blocs <- unique(d[[clu]]); out <- rep(NA_real_, B)
  for (b_ in seq_len(B)) {
    draw <- sample(blocs, length(blocs), replace = TRUE)
    dd <- rbindlist(lapply(seq_along(draw), function(k) {
      x <- d[get(clu) == draw[k]]; x[, (clu) := paste0("b", k)]; x
    }))
    r <- tryCatch({
      setTimeLimit(elapsed = REP_TIMEOUT, transient = TRUE)
      x <- cf_pois(dd, ycol, endo, instr, lin, fes, clu)
      setTimeLimit(elapsed = Inf, transient = TRUE)
      x
    }, error = function(e) { setTimeLimit(elapsed = Inf, transient = TRUE); NULL })
    if (!is.null(r)) out[b_] <- r$b
  }
  out[is.finite(out)]
}

# ---- run + collect ----
rows <- list()
for (ycol in c("dom_secular_territorial", "n_dispute", "dom_total")) {
  cat(sprintf("[%s] %s ...\n", format(Sys.time(), "%H:%M:%S"), ycol)); flush.console()
  r <- tryCatch(cf_pois(df, ycol, "n_dyn_4hop", "mother_n_dyn_4hop", LIN, FES, CLU),
                error = function(e) { cat("ERR:", conditionMessage(e), "\n"); NULL })
  if (is.null(r)) next
  bs <- boot_cf(df, ycol, "n_dyn_4hop", "mother_n_dyn_4hop", LIN, FES, CLU, B)
  madse <- 1.4826 * mad(bs, constant = 1)
  lo <- unname(quantile(bs, 0.025)); hi <- unname(quantile(bs, 0.975))
  pperc <- 2 * min(mean(bs <= 0), mean(bs >= 0)); if (pperc == 0) pperc <- 1 / length(bs)
  dom <- c(dom_secular_territorial = "secterr", n_dispute = "dispute", dom_total = "total")[ycol]
  rows[[length(rows) + 1]] <- data.table(
    domain = dom, beta = r$b, SE_analytic = r$se, p_analytic = r$p,
    boot_MAD_SE = madse, boot_ci_lo = lo, boot_ci_hi = hi, p_boot = pperc,
    B_requested = B, B_effective = length(bs),
    vhat_b = r$bv, vhat_p = r$pv, N = r$n)
  cat(sprintf("  beta=%+.4f (analytic SE %.4f, p=%.3g)  boot MAD-SE %.4f  95%% CI [%.3f,%.3f]  p_boot=%.3f  B_eff=%d  N=%d\n",
              r$b, r$se, r$p, madse, lo, hi, pperc, length(bs), r$n))
  cat(sprintf("  CF residual: %+.4f (p=%.3g)\n", r$bv, r$pv))
}
res <- rbindlist(rows)
fwrite(res, file.path(OUTDIR, "clean_iv", "reg_unified_poisson_cf.csv"))
cat("\nWrote output/clean_iv/reg_unified_poisson_cf.csv\n")
