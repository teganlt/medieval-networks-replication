#!/usr/bin/env Rscript
# 118_principal_outcome.R
# =======================
# Referee robustness: restrict the outcome to letters the coding marks as BOTH
# a live dispute AND one in which the matched noble is a principal party --
# the strictest "validated responsive dispute" reading of demand. (The
# principal flag is coded per letter; for multi-match letters it describes the
# matched nobles collectively -- disclosed in the table note.)
# Unified 2SLS spec (as 100). Outcomes: principal-dispute secular-territorial
# count; principal-dispute count over all domains.
# Output: output/clean_iv/reg_unified_principal.csv
# Usage:  Rscript 118_principal_outcome.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})

df <- fread(file.path(OUTDIR,"clean_iv","unified_frame.csv"))
coded <- fread(file.path(OUTDIR,"matched_docs_coded.csv"), colClasses=list(character="doc_id"))[
  , .(doc_id, domain, is_dispute, matched_principal)]
mt <- fread(file.path(OUTDIR,"doc_matches_ai_extracted_high.csv"), colClasses=list(character="doc_id"))[
  doc_year>=1100 & doc_year<=1300, .(person_id, doc_id)]
m <- merge(unique(mt), coded, by="doc_id")
pd <- m[is_dispute=="yes" & matched_principal=="yes"]
cnt <- pd[, .(n_prin_sec = sum(domain=="secular_territorial"), n_prin_tot = .N), by=person_id]
df <- merge(df, cnt, by="person_id", all.x=TRUE)
for (c in c("n_prin_sec","n_prin_tot")) df[is.na(get(c)), (c):=0]
cat(sprintf("principal-dispute letters: %d unique docs; sample nobles with >0: secterr %d, any %d\n",
            uniqueN(pd$doc_id), sum(df$n_prin_sec>0), sum(df$n_prin_tot>0)))

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
CTL <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc, "f_extra4"), collapse=" + ")
res <- rbindlist(lapply(c("n_prin_sec","n_prin_tot"), function(col){
  d <- copy(df); d[, .y := log1p(get(col))]
  m <- feols(as.formula(sprintf(".y ~ %s | n_dyn_4hop ~ mother_n_dyn_4hop", CTL)), data=d, cluster=~dynasty)
  ct <- as.data.frame(coeftable(m)); r <- ct[rownames(ct)=="fit_n_dyn_4hop",]
  s2 <- summary(m, vcov=~dynasty+death_decade); c2 <- as.data.frame(coeftable(s2))
  p2 <- c2[rownames(c2)=="fit_n_dyn_4hop","Pr(>|t|)"]
  data.table(outcome=col, beta=r$Estimate, SE=r$`Std. Error`, p_bloc=r$`Pr(>|t|)`,
             p_2way=p2, F_first=fitstat(m,"ivf1")[[1]]$stat, N=nobs(m), npos=sum(df[[col]]>0))
}))
fwrite(res, file.path(OUTDIR,"clean_iv","reg_unified_principal.csv"))
print(res[, .(outcome, beta=round(beta,4), SE=round(SE,4), p_bloc=round(p_bloc,4),
              p_2way=round(p_2way,4), npos)])
