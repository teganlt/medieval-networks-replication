#!/usr/bin/env Rscript
# 158_birthdec_headline.R
# =======================
# The headline 2SLS with BIRTH-decade fixed effects replacing death-decade
# fixed effects (and birth-decade in the two-way clustering), all domains.
# Backs the punch-list item-5 numbers (secterr 0.0306, two-way .0065).
# Output: output/clean_iv/reg_unified_birthdec.csv
ROOT <- if (length(commandArgs(trailingOnly=TRUE)) >= 1) commandArgs(trailingOnly=TRUE)[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
H <- 4L
df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
df[, birth_decade := (birth %/% 10) * 10]
anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
ctl <- paste(c("factor(title_rank)","factor(birth_decade)","factor(dynasty)", anc, "f_extra4"), collapse=" + ")
twoway_p <- function(m){ if(is.null(m))return(NA_real_); s<-tryCatch(summary(m,vcov=~dynasty+birth_decade),error=function(e)NULL); if(is.null(s))return(NA_real_)
  ct<-as.data.frame(coeftable(s));ct$t<-rownames(ct);pcn<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1];rr<-ct[ct$t=="fit_n_dyn_4hop",];if(nrow(rr))rr[[pcn]]else NA_real_}
DOMS <- c("secular_territorial","ecclesiastical_appointments","crusade","excommunication",
          "ecclesiastical_property","inheritance","marriage","other","total")
rows <- list()
cat(sprintf("%-28s %9s %9s %9s %9s %7s\n","domain","beta","SE","p_bloc","p_2way","Ffirst"))
for (dom in DOMS) {
  d <- copy(df); d[, .y := log1p(get(paste0("dom_", dom)))]
  m <- ic_fit_iv(".y", H, ctl, d); r <- ic_extract(m, H); p2 <- twoway_p(m)
  rows[[dom]] <- data.table(domain=dom, beta=r$beta, SE=r$SE, p=r$p, p_2way=p2, F_first=r$F_first, N=r$N)
  cat(sprintf("%-28s %9.4f %9.4f %9.2e %9.4f %7.1f\n", dom, r$beta, r$SE, r$p, p2, r$F_first))
}
fwrite(rbindlist(rows), file.path(OUTDIR, "clean_iv", "reg_unified_birthdec.csv"))
cat("Wrote output/clean_iv/reg_unified_birthdec.csv\n")
