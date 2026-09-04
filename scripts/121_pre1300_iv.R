#!/usr/bin/env Rscript
# 121_pre1300_iv.R
# ================
# Referee robustness companion to 120_blocs_pre1300.py: rerun the unified
# Prediction-1 baseline (spec EXACTLY as 100_unified_baseline.R: ancestor
# battery + f_extra4, bloc + death-decade + title FE, bloc cluster) with the
# PRE-1300 marriage-bloc labels and reach (bloc_reach_pre1300.csv), for
# secular_territorial and total only.  Shows the baseline does not depend on
# post-1300 marriages entering the Louvain partition.
# Output: output/clean_iv/reg_unified_blocs_pre1300.csv
# Usage:  Rscript 121_pre1300_iv.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
H <- 4L
DOMS <- c("secular_territorial","ecclesiastical_appointments","crusade","excommunication",
          "ecclesiastical_property","inheritance","marriage","other")
RUN_DOMS <- c("dom_secular_territorial","dom_total")   # the two reported legs

# ---- frame: identical to 100, but reach + labels from the pre-1300 build ----
br <- fread(file.path(OUTDIR,"bloc_reach_pre1300.csv"))
iv <- rc("mother_iv_4hop.csv")[, .(person_id, mother_id, father_id, mgf_id)]
df <- merge(br, iv, by="person_id", all.x=TRUE)
df <- df[!is.na(mother_n_dyn_4hop)]
fbi <- fread(file.path(OUTDIR,"clean_iv","father_bloc_increment.csv"))[, .(person_id, f_extra4)]
df <- merge(df, fbi, by="person_id", all.x=TRUE); df[is.na(f_extra4), f_extra4 := 0]
df[, dynasty := bloc]
df[, log_deg := log1p(deg)]
df[, death_decade := (death %/% 10)*10]
pl <- .ic$persons; dc <- .ic$doc_counts[, .(person_id, n_total_inwin)]
df <- merge(df, pl[, .(person_id=id, fname=name)], by="person_id", all.x=TRUE)
df[, title_rank := ic_title_rank_vec(fname)]; df[is.na(title_rank), title_rank := 0L]
for (who in c("mother","father","mgf")) {
  idc <- paste0(who,"_id")
  df <- merge(df, pl[, .(jid=id, jn=name)], by.x=idc, by.y="jid", all.x=TRUE)
  setnames(df,"jn",paste0(who,"_name"))
  df[, (paste0(who,"_title_rank")) := ic_title_rank_vec(get(paste0(who,"_name")))]
  df[is.na(get(paste0(who,"_title_rank"))), (paste0(who,"_title_rank")) := 0L]
  df[, (paste0(who,"_log_pre_deg")) := log1p(get(paste0(who,"_pre_deg")))]
  df[is.na(get(paste0(who,"_log_pre_deg"))), (paste0(who,"_log_pre_deg")) := 0]
  df[, (paste0(who,"_log_n_nodes_4hop")) := log1p(get(paste0(who,"_n_nodes_4hop")))]
  df[is.na(get(paste0(who,"_log_n_nodes_4hop"))), (paste0(who,"_log_n_nodes_4hop")) := 0]
  df <- merge(df, dc[, .(jid=person_id, jt=n_total_inwin)], by.x=idc, by.y="jid", all.x=TRUE)
  setnames(df,"jt",paste0(who,"_tot")); df[is.na(get(paste0(who,"_tot"))), (paste0(who,"_tot")) := 0]
  df[, (paste0(who,"_log_total_inwin")) := log1p(get(paste0(who,"_tot")))]
  df[is.na(get(paste0(who,"_n_dyn_4hop"))), (paste0(who,"_n_dyn_4hop")) := 0]
}
coded <- fread(file.path(OUTDIR,"matched_docs_coded.csv"),colClasses=list(character="doc_id"))[,.(doc_id,domain)]
mt <- fread(file.path(OUTDIR,"doc_matches_ai_extracted_high.csv"),colClasses=list(character="doc_id"))[doc_year>=1100&doc_year<=1300,.(person_id,doc_id)]
mt <- merge(mt,coded,by="doc_id"); dcd <- dcast(mt, person_id ~ domain, value.var="doc_id", fun.aggregate=length)
present <- DOMS[DOMS %in% names(dcd)]; setnames(dcd, present, paste0("dom_",present)); dcd[, dom_total := rowSums(.SD), .SDcols=patterns("^dom_")]
df <- merge(df, dcd, by="person_id", all.x=TRUE)
for (c in c(paste0("dom_",DOMS),"dom_total")) if(c%in%names(df)) df[is.na(get(c)),(c):=0] else df[,(c):=0]

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
fe <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
ctl_new <- paste(c(fe, anc, "f_extra4"), collapse=" + ")     # = the paper's stated X_i

twoway_p <- function(m){ if(is.null(m))return(NA_real_); s<-tryCatch(summary(m,vcov=~dynasty+death_decade),error=function(e)NULL); if(is.null(s))return(NA_real_)
  ct<-as.data.frame(coeftable(s));ct$t<-rownames(ct);pc<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1];rr<-ct[ct$t=="fit_n_dyn_4hop",];if(nrow(rr))rr[[pc]]else NA_real_}

run_all <- function(dat, ctl, tag) {
  rbindlist(lapply(RUN_DOMS, function(col){
    d<-copy(dat); d[,.y:=log1p(get(col))]; m<-ic_fit_iv(".y",H,ctl,d); r<-ic_extract(m,H)
    r[,`:=`(domain=sub("dom_","",col), p_2way=twoway_p(m), npos=sum(dat[[col]]>0), spec=tag)]; r}), fill=TRUE)
}

cat(sprintf("N=%d  pre1300-blocs in frame=%d  cor(reach,size)=%.2f\n",
            nrow(df), uniqueN(df$dynasty), cor(df$n_dyn_4hop,df$n_nodes_4hop)))
res <- run_all(df, ctl_new, "unified, pre-1300 bloc partition")
out <- res[,.(domain, beta, SE, p_bloc=p, p_2way, F_first, N)]
fwrite(out, file.path(OUTDIR,"clean_iv","reg_unified_blocs_pre1300.csv"))

cat("\n=== UNIFIED baseline on PRE-1300 blocs (paper X_i) ===\n")
cat(sprintf("  %-22s %9s %9s %9s %9s %8s %6s\n","domain","beta","SE","p_bloc","p_2way","Ffirst","N"))
for (i in seq_len(nrow(out))) { x<-out[i]
  cat(sprintf("  %-22s %9.4f %9.4f %9.4f %9.4f %8.1f %6d\n",
              x$domain,x$beta,x$SE,x$p_bloc,x$p_2way,x$F_first,x$N)) }
cat("\nBaseline ([800,1500] blocs, script 100): secular_territorial 0.0326 (p_2way .0052, F=339); total 0.0325\n")
cat("Wrote clean_iv/reg_unified_blocs_pre1300.csv\n")
