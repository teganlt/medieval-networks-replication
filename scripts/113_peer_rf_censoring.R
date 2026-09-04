#!/usr/bin/env Rscript
# 113_peer_rf_censoring.R
# =======================
# Censoring robustness for the composite peer RF (111). Peers register
# appearances only if inside the document-matching universe (08's anchored
# era-eligible set), so the adoption share zD undercounts adoption in
# networks extending beyond the anchored core. Three checks, per era x domain:
#   C1  zDm : adoption share with MATCHABLE-ONLY denominator
#             (sample: peer_n_matchable > 0), + focal reach + battery
#   C2  zB + share_matchable control  (does breadth survive the share?)
#   C3  zD + share_matchable control  (does the flip survive the share?)
# Betas per full-sample SD of the treatment. Cluster bloc; two-way robustness.
# Output: output/clean_iv/reg_peer_rf_censoring.csv
# Usage:  Rscript 113_peer_rf_censoring.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})

df <- fread(file.path(OUTDIR,"clean_iv","unified_frame.csv"))
pr <- fread(file.path(OUTDIR,"clean_iv","peer_rf_build.csv"))
df <- merge(df, pr, by="person_id")
df <- df[peer_nkin > 0]
df[, zB := (peer_breadth_pre    - mean(peer_breadth_pre))    / sd(peer_breadth_pre)]
df[, zD := (peer_secterr_dated  - mean(peer_secterr_dated))  / sd(peer_secterr_dated)]
dm <- df[peer_n_matchable > 0]
sd_m <- dm[, sd(peer_secterr_dated_m)]; mu_m <- dm[, mean(peer_secterr_dated_m)]
df[, zDm := (peer_secterr_dated_m - mu_m) / sd_m]

cat(sprintf("N=%d; matchable-denominator sample N=%d (peer_n_matchable>0)\n", nrow(df), nrow(dm)))
cat(sprintf("share_matchable: mean=%.3f  cor(share, zB)=%.3f  cor(share, zD)=%.3f  cor(zD, zDm)=%.3f\n",
            mean(df$peer_share_matchable), cor(df$peer_share_matchable, df$zB),
            cor(df$peer_share_matchable, df$zD), cor(dm$peer_secterr_dated, dm$peer_secterr_dated_m)))

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
BAT <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc, "f_extra4"), collapse=" + ")
DOMS <- c("secular_territorial","ecclesiastical_appointments","crusade","excommunication",
          "ecclesiastical_property","inheritance","marriage","other","total")

specs <- list(
  list(tag="C1 zDm matchable-denom", tr="zDm", rhs=sprintf("zDm + n_dyn_4hop + %s", BAT), sub="peer_n_matchable > 0"),
  list(tag="C2 zB + share ctrl",     tr="zB",  rhs=sprintf("zB + peer_share_matchable + n_dyn_4hop + %s", BAT), sub="TRUE"),
  list(tag="C3 zD + share ctrl",     tr="zD",  rhs=sprintf("zD + peer_share_matchable + n_dyn_4hop + %s", BAT), sub="TRUE"))

pull <- function(m, term, twoway=FALSE) {
  if (is.null(m)) return(c(NA_real_,NA_real_,NA_real_))
  s <- if (twoway) tryCatch(summary(m, vcov=~dynasty+death_decade), error=function(e) NULL) else m
  if (is.null(s)) return(c(NA_real_,NA_real_,NA_real_))
  ct <- as.data.frame(coeftable(s)); ct$t <- rownames(ct)
  pcol <- intersect(c("Pr(>|t|)","Pr(>|z|)"), names(ct))[1]
  r <- ct[ct$t==term,]; if (nrow(r)==0) c(NA_real_,NA_real_,NA_real_) else c(r$Estimate, r$`Std. Error`, r[[pcol]])
}

res <- list()
for (era in list(c("ALL",-1L), c("EMFP",1L), c("post",0L))) {
  d0 <- if (era[[2]] < 0) df else df[EMFP == as.integer(era[[2]])]
  for (dom in DOMS) {
    for (s in specs) {
      d <- d0[eval(parse(text=s$sub))]
      d <- copy(d); d[, .y := log1p(get(paste0("dom_",dom)))]
      m <- tryCatch(feols(as.formula(paste0(".y ~ ", s$rhs)), data=d, cluster=~dynasty), error=function(e) NULL)
      b  <- pull(m, s$tr, FALSE); b2 <- pull(m, s$tr, TRUE)
      res[[length(res)+1]] <- data.table(era=era[[1]], domain=dom, spec=s$tag, term=s$tr,
        beta=b[1], SE=b[2], p_bloc=b[3], p_2way=b2[3],
        N=if(is.null(m)) NA_integer_ else nobs(m))
    }
  }
}
R <- rbindlist(res)
fwrite(R, file.path(OUTDIR,"clean_iv","reg_peer_rf_censoring.csv"))

cat("\n=== CENSORING ROBUSTNESS (beta per SD of treatment; p_bloc) ===\n")
for (e in c("ALL","EMFP","post")) {
  cat(sprintf("\n--- era %s ---\n  %-26s", e, "domain"))
  for (s in specs) cat(sprintf(" %24s", s$tag)); cat("\n")
  for (dom in DOMS) {
    cat(sprintf("  %-26s", dom))
    for (s in specs) {
      r <- R[era==e & domain==dom & spec==s$tag]
      if (nrow(r)==0 || is.na(r$beta)) { cat(sprintf(" %24s","-")) } else {
        st <- if (is.na(r$p_bloc)) "" else if (r$p_bloc<0.01) "**" else if (r$p_bloc<0.05) "*" else if (r$p_bloc<0.1) "." else ""
        cat(sprintf(" %14.4f(%.3f)%-2s", r$beta, r$p_bloc, st)) }
    }
    cat("\n")
  }
}
cat("\nWrote reg_peer_rf_censoring.csv\n")
