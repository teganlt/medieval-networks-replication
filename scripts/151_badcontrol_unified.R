#!/usr/bin/env Rscript
# 151_badcontrol_unified.R
# ========================
# Port of script 68's bad-control test (row B) to the UNIFIED frame (N=2,195):
# secterr 2SLS with log1p(non-territorial appearances) added as a control,
# plus the headline and non-territorial-outcome reference rows.
# The control is post-treatment (collider); the estimate is conservative.
# Output: output/clean_iv/reg_unified_badcontrol.csv
# Usage:  Rscript 151_badcontrol_unified.R
ROOT <- if (length(commandArgs(trailingOnly=TRUE)) >= 1) commandArgs(trailingOnly=TRUE)[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
H <- 4L

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
df[, log_nonterr := log1p(dom_total - dom_secular_territorial)]

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
fe <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
base <- c(fe, anc, "f_extra4")

twoway_p <- function(m){ if(is.null(m))return(NA_real_); s<-tryCatch(summary(m,vcov=~dynasty+death_decade),error=function(e)NULL); if(is.null(s))return(NA_real_)
  ct<-as.data.frame(coeftable(s));ct$t<-rownames(ct);pcn<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1];rr<-ct[ct$t=="fit_n_dyn_4hop",];if(nrow(rr))rr[[pcn]]else NA_real_}

rows <- list()
run <- function(d, extra, tag) {
  m <- ic_fit_iv(".y", H, paste(c(base, extra), collapse=" + "), d); r <- ic_extract(m, H)
  p2 <- twoway_p(m)
  cat(sprintf("%-34s %9.4f %9.4f %9.2e %9.4f %7.1f\n", tag, r$beta, r$SE, r$p, p2, r$F_first))
  data.table(spec=tag, beta=r$beta, SE=r$SE, p=r$p, p_2way=p2, F_first=r$F_first, N=r$N)
}
cat(sprintf("%-34s %9s %9s %9s %9s %7s   (N=%d)\n","spec","beta","SE","p_bloc","p_2way","Ffirst",nrow(df)))
dA <- copy(df); dA[, .y := log1p(dom_secular_territorial)]
dN <- copy(df); dN[, .y := log_nonterr]
rows[[1]] <- run(dA, NULL,          "A  secterr (unified headline)")
rows[[2]] <- run(dN, NULL,          "A' non-territorial outcome")
rows[[3]] <- run(dA, "log_nonterr", "B  secterr | non-terr control")
fwrite(rbindlist(rows), file.path(OUTDIR, "clean_iv", "reg_unified_badcontrol.csv"))
cat("\nWrote output/clean_iv/reg_unified_badcontrol.csv\n")
