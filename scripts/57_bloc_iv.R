#!/usr/bin/env Rscript
# 57_bloc_iv.R
# ============
# Domain IV on the topology-only PATRILINE-BLOC reach, computed on the FULL
# peerage graph for BOTH focal (lifetime) and instrument (pre-natal) (56).
# Bloc FE + clustering; NO focal-size collider; ancestor controls kept.
# This is the cleanest construction: anchoring-free, reach decoupled from
# size (cor 0.66), same graph for focal & instrument.
# Output: output/clean_iv/reg_clean_bloc_iv.csv + console.
# Usage:  Rscript 57_bloc_iv.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
H <- 4L
DOMS <- c("ecclesiastical_property","ecclesiastical_appointments","inheritance",
          "marriage","crusade","excommunication","secular_territorial","other")

br <- fread(file.path(OUTDIR,"bloc_reach_fullgraph.csv"))
iv <- rc("mother_iv_4hop.csv")[, .(person_id, mother_id, father_id, mgf_id)]
df <- merge(br, iv, by="person_id", all.x=TRUE)
df <- df[!is.na(mother_n_dyn_4hop)]
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

cat(sprintf("N=%d  blocs in sample=%d  cor(reach,size)=%.2f  cor(endo,instr)=%.2f\n",
            nrow(df), uniqueN(df$dynasty), cor(df$n_dyn_4hop,df$n_nodes_4hop), cor(df$n_dyn_4hop,df$mother_n_dyn_4hop)))
ctl <- paste(c("log_deg","factor(title_rank)","factor(death_decade)","factor(dynasty)",
  "factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop"), collapse=" + ")
twoway_p <- function(m){ if(is.null(m))return(NA_real_); s<-tryCatch(summary(m,vcov=~dynasty+death_decade),error=function(e)NULL); if(is.null(s))return(NA_real_)
  ct<-as.data.frame(coeftable(s));ct$t<-rownames(ct);pc<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1];rr<-ct[ct$t=="fit_n_dyn_4hop",];if(nrow(rr))rr[[pc]]else NA_real_}
res <- rbindlist(lapply(c(paste0("dom_",DOMS),"dom_total"), function(col){
  d<-copy(df); d[,.y:=log1p(get(col))]; m<-ic_fit_iv(".y",H,ctl,d); r<-ic_extract(m,H)
  r[,`:=`(domain=sub("dom_","",col), p_2way=twoway_p(m), npos=sum(df[[col]]>0))]; r}), fill=TRUE)
fwrite(res[,.(domain,beta,SE,p,p_2way,F_first,N,npos)], file.path(OUTDIR,"clean_iv","reg_clean_bloc_iv.csv"))
cat("\n=== PATRILINE-BLOC IV (full-graph reach, bloc FE/cluster, no focal-size) ===\n")
cat(sprintf("  %-26s %9s %9s %9s %9s %7s %6s\n","domain","beta","SE","p_bloc","p_2way","Ffirst","npos"))
for (i in seq_len(nrow(res))) { r<-res[i]; st<-if(is.na(r$p))""else if(r$p<0.01)"**"else if(r$p<0.05)"*"else""
  cat(sprintf("  %-26s %9.4f %9.4f %9.4f %9.4f %7.1f %6d%s\n", r$domain,r$beta,r$SE,r$p,r$p_2way,r$F_first,r$npos,st)) }
cat("\nWrote reg_clean_bloc_iv.csv\n")
