#!/usr/bin/env Rscript
# 81_reverse_rf.R
# ===============
# REDUCED-FORM REVERSE of the clean bloc IV (the model's feedback / return
# arrow): does a FATHER's papal-court engagement predict his CHILD's kin-reach?
#   outcome   = child's BLOC reach  (n_dyn_4hop, lifetime, full graph) -- RAW
#   regressor = father's in-window appearance in a domain  (ladder below),
#               intensive log(1+count) AND extensive 1{count>0}
#   controls  = the IV's father-side / ancestor vector + BOTH parents' pre-natal
#               bloc reach (reach-transmission) + bloc FE + child death-decade FE.
#               Father's total in-window appearances is kept as a control (so each
#               domain is net of the father's general prominence) -- dropped only
#               on the 'total' rung (collinear).
# Everything BLOC-based (bloc reach, bloc FE, bloc clustering) -- no dynasties.
# SE: bloc-clustered + bloc&decade two-way. Reduced-form / correlational.
# Output: output/clean_iv/reg_reverse_rf.csv + console.
# Usage:  Rscript 81_reverse_rf.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
DOMS <- c("secular_territorial","ecclesiastical_property","ecclesiastical_appointments",
          "inheritance","marriage","crusade","excommunication","other")

br <- fread(file.path(OUTDIR,"bloc_cohesion_fullgraph.csv"))            # child bloc reach + ancestor reach/size/deg
iv <- rc("mother_iv_4hop.csv")[, .(person_id, mother_id, father_id, mgf_id)]
df <- merge(br, iv, by="person_id", all.x=TRUE)
df <- df[!is.na(mother_n_dyn_4hop) & !is.na(father_id) & father_id != ""]  # IV sample w/ known father
df[, death_decade := (death %/% 10)*10]
pl <- .ic$persons; dc <- .ic$doc_counts[, .(person_id, n_total_inwin)]
df <- merge(df, pl[, .(person_id=id, fname=name)], by="person_id", all.x=TRUE)
df[, title_rank := ic_title_rank_vec(fname)]; df[is.na(title_rank), title_rank := 0L]
for (who in c("mother","father","mgf")) {
  idc <- paste0(who,"_id")
  df <- merge(df, pl[, .(jid=id, jn=name)], by.x=idc, by.y="jid", all.x=TRUE); setnames(df,"jn",paste0(who,"_name"))
  df[, (paste0(who,"_title_rank")) := ic_title_rank_vec(get(paste0(who,"_name")))]; df[is.na(get(paste0(who,"_title_rank"))), (paste0(who,"_title_rank")) := 0L]
  df[, (paste0(who,"_log_pre_deg")) := log1p(get(paste0(who,"_pre_deg")))]; df[is.na(get(paste0(who,"_log_pre_deg"))), (paste0(who,"_log_pre_deg")) := 0]
  df[, (paste0(who,"_log_n_nodes_4hop")) := log1p(get(paste0(who,"_n_nodes_4hop")))]; df[is.na(get(paste0(who,"_log_n_nodes_4hop"))), (paste0(who,"_log_n_nodes_4hop")) := 0]
  df <- merge(df, dc[, .(jid=person_id, jt=n_total_inwin)], by.x=idc, by.y="jid", all.x=TRUE); setnames(df,"jt",paste0(who,"_tot")); df[is.na(get(paste0(who,"_tot"))), (paste0(who,"_tot")) := 0]
  df[, (paste0(who,"_log_total_inwin")) := log1p(get(paste0(who,"_tot")))]
  df[is.na(get(paste0(who,"_n_dyn_4hop"))), (paste0(who,"_n_dyn_4hop")) := 0]
}

# ---- per-person in-window appearance counts (domain / total / dispute) ----
coded <- fread(file.path(OUTDIR,"matched_docs_coded.csv"),colClasses=list(character="doc_id"))[,.(doc_id,domain,is_dispute)]
mt <- fread(file.path(OUTDIR,"doc_matches_ai_extracted_high.csv"),colClasses=list(character="doc_id"))[doc_year>=1100&doc_year<=1300,.(person_id,doc_id)]
mt <- merge(mt,coded,by="doc_id")
dcd <- dcast(mt, person_id ~ domain, value.var="doc_id", fun.aggregate=length)
for (d in DOMS) if (d %in% names(dcd)) setnames(dcd, d, paste0("c_",d)) else dcd[,(paste0("c_",d)):=0]
agg <- mt[, .(c_total=.N, c_dispute=sum(is_dispute=="yes"), c_nondispute=sum(is_dispute=="no")), by=person_id]
cnt <- merge(dcd[, c("person_id", paste0("c_",DOMS)), with=FALSE], agg, by="person_id", all=TRUE)
for (cc in setdiff(names(cnt),"person_id")) cnt[is.na(get(cc)), (cc):=0]
# join FATHER's counts onto child rows
setnames(cnt, "person_id", "father_id")
df <- merge(df, cnt, by="father_id", all.x=TRUE)
RUNGS <- c(paste0("c_",DOMS), "c_total", "c_dispute", "c_nondispute")
for (cc in RUNGS) { if (!cc %in% names(df)) df[,(cc):=0]; df[is.na(get(cc)),(cc):=0]
  df[, (paste0("l",cc)) := log1p(get(cc))]; df[, (paste0("e",cc)) := as.integer(get(cc)>0)] }

ANC <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
CTL <- c("father_n_dyn_4hop","mother_n_dyn_4hop", ANC, "factor(bloc)","factor(death_decade)")  # + parental reach (pt 1)

cat(sprintf("N=%d  blocs=%d  (reverse RF: child bloc reach ~ father appearance)\n", nrow(df), uniqueN(df$bloc)))
twoway_p <- function(m, term){ s<-tryCatch(summary(m,vcov=~bloc+death_decade),error=function(e)NULL); if(is.null(s))return(NA_real_)
  ct<-as.data.frame(coeftable(s));ct$t<-rownames(ct);pc<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1];r<-ct[ct$t==term,];if(nrow(r))r[[pc]]else NA_real_}
fitrf <- function(regterm, total_rung){
  ctl <- if (total_rung) setdiff(CTL, "father_log_total_inwin") else CTL
  m <- tryCatch(feols(as.formula(paste("n_dyn_4hop ~", regterm, "+", paste(ctl,collapse=" + "))),
                      data=df, cluster=~bloc), error=function(e) NULL)
  if (is.null(m)) return(c(NA,NA,NA,NA))
  ct<-as.data.frame(coeftable(m));ct$t<-rownames(ct);pc<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1]
  r<-ct[ct$t==regterm,]; if(!nrow(r)) return(c(NA,NA,NA,NA))
  c(r$Estimate, r[["Std. Error"]], r[[pc]], twoway_p(m, regterm))
}

res <- list()
for (cc in RUNGS) {
  tot <- cc == "c_total"
  for (ty in c("intensive","extensive")) {
    term <- paste0(if(ty=="intensive")"l" else "e", cc)
    v <- fitrf(term, tot)
    res[[length(res)+1]] <- data.table(rung=sub("c_","",cc), type=ty, beta=v[1], SE=v[2],
                                        p_bloc=v[3], p_2way=v[4], father_npos=sum(df[[cc]]>0))
  }
}
res <- rbindlist(res)
fwrite(res, file.path(OUTDIR,"clean_iv","reg_reverse_rf.csv"))
st<-function(p) if(is.na(p))"" else if(p<.01)"**" else if(p<.05)"*" else ""
cat("\n=== REVERSE reduced form: child bloc reach ~ father's appearance (+ IV father controls, bloc FE/cluster) ===\n")
cat(sprintf("  %-28s %-10s %9s %9s %9s %9s %7s\n","rung","type","beta","SE","p_bloc","p_2way","f_npos"))
for (i in seq_len(nrow(res))) { r<-res[i]
  cat(sprintf("  %-28s %-10s %9.4f %9.4f %9.4f %9.4f %7d%s\n", r$rung, r$type, r$beta, r$SE, r$p_bloc, r$p_2way, r$father_npos, st(r$p_bloc))) }
cat("\nOutcome = raw child bloc reach (mean", round(mean(df$n_dyn_4hop),2), "). Wrote reg_reverse_rf.csv\n")
