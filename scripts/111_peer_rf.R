#!/usr/bin/env Rscript
# 111_peer_rf.R
# =============
# PREDICTION 2, rebuilt as the COMPOSITE REDUCED FORM (7/27 redo).
# Treatment = peer breadth, strictly predetermined at the focal's birth
# (110_peer_rf_build.py); outcome = focal domain appearances 1100-1300.
# Interpretation: the model's Prop. 3 gives peer exogamy two channels into
# focal court use (peers' adoption pi, ambient conflict risk v-bar); this RF
# estimates their composite. No instrument is claimed — the model itself rules
# one out. Controls = the unified Pred-1 battery (100) + focal reach.
#   S0  no focal reach          y ~ zB + battery
#   S1  PRIMARY                 y ~ zB + focal reach + battery
#   S2  + family court history  S1 + fa_ldisp + pat_disp_anc + pat_secterr_anc + n_pat_anc
#   S3  adoption companion      y ~ zD (share of peers in SECULAR-TERRITORIAL
#                                letters pre-dating the focal's birth; switched
#                                from the is_dispute flag 7/30 -- secterr is the
#                                paper's headline domain) + focal reach + battery
#   S4  both                    y ~ zB + zD + focal reach + battery
# zB/zD standardized on the FULL sample (betas are per full-sample SD).
# Eras: ALL / EMFP-born (<=1215) / post. Cluster bloc; two-way as robustness.
# Output: output/clean_iv/reg_peer_rf_domains.csv
# Usage:  Rscript 111_peer_rf.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})

df <- fread(file.path(OUTDIR,"clean_iv","unified_frame.csv"))
pr <- fread(file.path(OUTDIR,"clean_iv","peer_rf_build.csv"))
fam <- fread(file.path(OUTDIR,"clean_iv","reg_complementarity_iv_df_sat2.csv"))[
  , .(person_id, fa_ldisp, pat_disp_anc, pat_secterr_anc, n_pat_anc)]
df <- merge(df, pr, by="person_id")
df <- merge(df, fam, by="person_id", all.x=TRUE)
for (c in c("fa_ldisp","pat_disp_anc","pat_secterr_anc","n_pat_anc")) df[is.na(get(c)), (c):=0]
df <- df[peer_nkin > 0]
df[, zB := (peer_breadth_pre    - mean(peer_breadth_pre))    / sd(peer_breadth_pre)]
df[, zD := (peer_secterr_dated  - mean(peer_secterr_dated))  / sd(peer_secterr_dated)]

cat(sprintf("N=%d  blocs=%d  EMFP=%d/post=%d\n", nrow(df), uniqueN(df$dynasty), sum(df$EMFP==1), sum(df$EMFP==0)))
cat(sprintf("diagnostics: cor(zB, focal reach)=%.3f  cor(breadth_pre, lifetime reach1)=%.3f  cor(zB,zD)=%.3f\n",
            cor(df$zB, df$n_dyn_4hop), cor(df$peer_breadth_pre, df$peer_reach1_life), cor(df$zB, df$zD)))

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
fe  <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
BAT <- paste(c(fe, anc, "f_extra4"), collapse=" + ")
FAM <- "fa_ldisp + pat_disp_anc + pat_secterr_anc + n_pat_anc"
DOMS <- c("secular_territorial","ecclesiastical_appointments","crusade","excommunication",
          "ecclesiastical_property","inheritance","marriage","other","total")

specs <- list(
  list(tag="S0 no-reach",  tr="zB", rhs=sprintf("zB + %s", BAT)),
  list(tag="S1 primary",   tr="zB", rhs=sprintf("zB + n_dyn_4hop + %s", BAT)),
  list(tag="S2 family",    tr="zB", rhs=sprintf("zB + n_dyn_4hop + %s + %s", FAM, BAT)),
  list(tag="S3 adoption",  tr="zD", rhs=sprintf("zD + n_dyn_4hop + %s", BAT)),
  list(tag="S4 both:zB",   tr="zB", rhs=sprintf("zB + zD + n_dyn_4hop + %s", BAT)),
  list(tag="S4 both:zD",   tr="zD", rhs=sprintf("zB + zD + n_dyn_4hop + %s", BAT)))

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
    d <- copy(d0); d[, .y := log1p(get(paste0("dom_",dom)))]
    for (s in specs) {
      key <- if (grepl("S4 both", s$tag)) "S4 both" else s$tag
      if (s$tag == "S4 both:zD" && dom != DOMS[1] && FALSE) next
      m <- tryCatch(feols(as.formula(paste0(".y ~ ", s$rhs)), data=d, cluster=~dynasty), error=function(e) NULL)
      b  <- pull(m, s$tr, FALSE); b2 <- pull(m, s$tr, TRUE)
      res[[length(res)+1]] <- data.table(era=era[[1]], domain=dom, spec=s$tag, term=s$tr,
        beta=b[1], SE=b[2], p_bloc=b[3], p_2way=b2[3],
        N=if(is.null(m)) NA_integer_ else nobs(m), npos=sum(d[[paste0("dom_",dom)]]>0))
    }
  }
}
R <- rbindlist(res)
fwrite(R, file.path(OUTDIR,"clean_iv","reg_peer_rf_domains.csv"))

cat("\n=== PEER COMPOSITE RF (beta per full-sample SD of treatment) ===\n")
for (e in c("ALL","EMFP","post")) {
  cat(sprintf("\n--- era %s ---\n  %-26s", e, "domain"))
  for (s in unique(R$spec)) cat(sprintf(" %18s", s)); cat("\n")
  for (dom in DOMS) {
    cat(sprintf("  %-26s", dom))
    for (s in unique(R$spec)) {
      r <- R[era==e & domain==dom & spec==s]
      if (nrow(r)==0 || is.na(r$beta)) { cat(sprintf(" %18s","-")) } else {
        st <- if (is.na(r$p_bloc)) "" else if (r$p_bloc<0.01) "**" else if (r$p_bloc<0.05) "*" else if (r$p_bloc<0.1) "." else ""
        cat(sprintf(" %10.4f(%.3f)%-2s", r$beta, r$p_bloc, st)) }
    }
    cat("\n")
  }
}
cat("\nWrote reg_peer_rf_domains.csv\n")
