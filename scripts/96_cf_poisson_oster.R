#!/usr/bin/env Rscript
# (1) Control-function Poisson for the two headline IVs (counts, not log1p):
#     first stage OLS -> residual v-hat -> fepois(count ~ endo + v-hat + ctl | FE).
#     Pairs-cluster bootstrap (relabelled blocs) for the generated regressor.
# (2) Oster (2019) delta* for the forward IV's secterr REDUCED FORM:
#     always-keep = focal position + FE; extrapolation battery = ancestor controls.
# Usage: Rscript cf_poisson_oster.R <ROOT>
args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
set.seed(42); B <- 199

# ---------- Pred-1 dataframe (verbatim 57 build) ----------
br <- fread(file.path(OUTDIR, "bloc_reach_fullgraph.csv"))
iv <- rc("mother_iv_4hop.csv")[, .(person_id, mother_id, father_id, mgf_id)]
df <- merge(br, iv, by = "person_id", all.x = TRUE)
df <- df[!is.na(mother_n_dyn_4hop)]
df[, dynasty := bloc]; df[, log_deg := log1p(deg)]; df[, death_decade := (death %/% 10) * 10]
pl <- .ic$persons; dc <- .ic$doc_counts[, .(person_id, n_total_inwin)]
df <- merge(df, pl[, .(person_id = id, fname = name)], by = "person_id", all.x = TRUE)
df[, title_rank := ic_title_rank_vec(fname)]; df[is.na(title_rank), title_rank := 0L]
for (who in c("mother", "father", "mgf")) {
  idc <- paste0(who, "_id")
  df <- merge(df, pl[, .(jid = id, jn = name)], by.x = idc, by.y = "jid", all.x = TRUE)
  setnames(df, "jn", paste0(who, "_name"))
  df[, (paste0(who, "_title_rank")) := ic_title_rank_vec(get(paste0(who, "_name")))]
  df[is.na(get(paste0(who, "_title_rank"))), (paste0(who, "_title_rank")) := 0L]
  df[, (paste0(who, "_log_pre_deg")) := log1p(get(paste0(who, "_pre_deg")))]
  df[is.na(get(paste0(who, "_log_pre_deg"))), (paste0(who, "_log_pre_deg")) := 0]
  df[, (paste0(who, "_log_n_nodes_4hop")) := log1p(get(paste0(who, "_n_nodes_4hop")))]
  df[is.na(get(paste0(who, "_log_n_nodes_4hop"))), (paste0(who, "_log_n_nodes_4hop")) := 0]
  df <- merge(df, dc[, .(jid = person_id, jt = n_total_inwin)], by.x = idc, by.y = "jid", all.x = TRUE)
  setnames(df, "jt", paste0(who, "_tot")); df[is.na(get(paste0(who, "_tot"))), (paste0(who, "_tot")) := 0]
  df[, (paste0(who, "_log_total_inwin")) := log1p(get(paste0(who, "_tot")))]
  df[is.na(get(paste0(who, "_n_dyn_4hop"))), (paste0(who, "_n_dyn_4hop")) := 0]
}
coded <- fread(file.path(OUTDIR, "matched_docs_coded.csv"), colClasses = list(character = "doc_id"))[, .(doc_id, domain)]
mt <- fread(file.path(OUTDIR, "doc_matches_ai_extracted_high.csv"), colClasses = list(character = "doc_id"))[
  doc_year >= 1100 & doc_year <= 1300, .(person_id, doc_id)]
mt <- merge(mt, coded, by = "doc_id")
dcd <- dcast(mt, person_id ~ domain, value.var = "doc_id", fun.aggregate = length)
setnames(dcd, setdiff(names(dcd), "person_id"), paste0("dom_", setdiff(names(dcd), "person_id")))
dcd[, dom_total := rowSums(.SD), .SDcols = patterns("^dom_")]
df <- merge(df, dcd, by = "person_id", all.x = TRUE)
for (c_ in grep("^dom_", names(dcd), value = TRUE)) if (c_ %in% names(df)) df[is.na(get(c_)), (c_) := 0] else df[, (c_) := 0]

ANC <- paste(c("factor(mother_title_rank)", "factor(father_title_rank)", "factor(mgf_title_rank)",
               "mother_log_n_nodes_4hop", "father_log_n_nodes_4hop", "mgf_log_n_nodes_4hop",
               "mother_log_pre_deg", "father_log_pre_deg", "mgf_log_pre_deg",
               "mother_log_total_inwin", "father_log_total_inwin", "mgf_log_total_inwin",
               "mgf_n_dyn_4hop"), collapse = " + ")
# 8/18 unification (R3 fix): the battery now matches 100's ctl_new exactly --
# focal log_deg OUT (collider), father's bloc increment f_extra4 IN.
fbi <- fread(file.path(OUTDIR, "clean_iv", "father_bloc_increment.csv"))[, .(person_id, f_extra4)]
df <- merge(df, fbi, by = "person_id", all.x = TRUE); df[is.na(f_extra4), f_extra4 := 0]
LIN1 <- paste("f_extra4", ANC, sep = " + ")

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
    r <- tryCatch(cf_pois(dd, ycol, endo, instr, lin, fes, clu), error = function(e) NULL)
    if (!is.null(r)) out[b_] <- r$b
  }
  out[is.finite(out)]
}

boot_summ <- function(bs, b) {
  bs <- bs[is.finite(bs)]
  madse <- 1.4826 * mad(bs, constant = 1)
  lo <- quantile(bs, 0.025); hi <- quantile(bs, 0.975)
  pperc <- 2 * min(mean(bs <= 0), mean(bs >= 0)); if (pperc == 0) pperc <- 1 / length(bs)
  sprintf("boot MAD-SE %.4f, 95%% CI [%.3f, %.3f], p_perc=%.3f, B=%d", madse, lo, hi, pperc, length(bs))
}

cat("=============== (1) CONTROL-FUNCTION POISSON ===============\n")
cat("--- Pred 1: reach -> counts (N=", nrow(df), ") ---\n", sep = "")
for (ycol in c("dom_secular_territorial", "dom_total")) {
  r <- tryCatch(cf_pois(df, ycol, "n_dyn_4hop", "mother_n_dyn_4hop", LIN1,
               "dynasty + death_decade + title_rank", "dynasty"), error = function(e) {cat("ERR:", conditionMessage(e), "\n"); NULL})
  if (is.null(r)) next
  bs <- boot_cf(df, ycol, "n_dyn_4hop", "mother_n_dyn_4hop", LIN1,
                "dynasty + death_decade + title_rank", "dynasty", B)
  cat(sprintf("  %-24s beta=%+.4f (analytic SE %.4f, p=%.3g)  N=%d\n",
              sub("dom_", "", ycol), r$b, r$se, r$p, r$n))
  cat(sprintf("  %-24s   %s\n", "", boot_summ(bs, r$b)))
  cat(sprintf("  %-24s   CF residual: %+.4f (p=%.3g)\n", "", r$bv, r$pv))
}

# (Pred-2 CF-Poisson block removed 8/18: it consumed the deprecated
#  complementarity-IV frame, superseded by the composite reduced form of 110/111.)

cat("\n=============== (2) OSTER delta* — forward IV, secterr reduced form ===============\n")
df[, y_sec := log1p(dom_secular_territorial)]
wr2 <- function(m) tryCatch(r2(m, "wr2"), error = function(e) NA)
short <- feols(as.formula("y_sec ~ mother_n_dyn_4hop + log_deg + factor(title_rank) | dynasty + death_decade"),
               data = df, cluster = ~dynasty)
long <- feols(as.formula(paste0("y_sec ~ mother_n_dyn_4hop + log_deg + factor(title_rank) + ", ANC,
                                " | dynasty + death_decade")), data = df, cluster = ~dynasty)
bdot <- coef(short)["mother_n_dyn_4hop"]; btil <- coef(long)["mother_n_dyn_4hop"]
Rdot <- wr2(short); Rtil <- wr2(long)
cat(sprintf("  RF short (focal position + FE):   bdot=%+.5f (wR2=%.4f)\n", bdot, Rdot))
cat(sprintf("  RF long  (+ ancestor battery):    btil=%+.5f (wR2=%.4f)   movement %+.5f (%s)\n",
            btil, Rtil, btil - bdot, ifelse(abs(btil) >= abs(bdot), "GROWS away from 0", "shrinks toward 0")))
for (rmx in c(min(1.3 * Rtil, 1), 1)) {
  dstar <- btil * (Rtil - Rdot) / ((bdot - btil) * (rmx - Rtil))
  bstar <- btil - (bdot - btil) * (rmx - Rtil) / (Rtil - Rdot)
  cat(sprintf("  Rmax=%.3f : beta*(delta=1)=%+.5f   delta*=%+.2f%s\n",
              rmx, bstar, dstar, ifelse(dstar >= 1 | dstar < 0, "  [ROBUST]", "")))
}
