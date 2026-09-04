#!/usr/bin/env Rscript
# 82_reverse_erosion.R
# ====================
# Follow-up to 81 (reverse reduced form). Does a father's dispute engagement
# predict reach DECLINE (erosion) rather than just a low level? Logic: the
# forward IV says disputers are HIGH-reach (reach->disputes); 81 says their
# CHILDREN are low-reach. If so, reach falls across the dispute.
# Outcome (new): Delta_reach = child bloc reach - FATHER'S OWN lifetime bloc
# reach (father must be a focal). Three specs per ladder rung (intensive
# log(1+father count)):
#   LEVEL    : child_reach ~ app + BASE                (81's spec, this subsample)
#   D_raw    : Delta_reach ~ app + BASE                (raw decline)
#   D_net    : Delta_reach ~ app + BASE + father_own_reach   (decline net of the
#              father's reach level == strips mechanical mean-reversion; the
#              dispute-vs-nondispute gap here = dispute-specific erosion)
# BASE = 81 controls (parental pre-natal bloc reach + ancestor vector + bloc FE
# + child death-decade FE + father total, dropped on the total rung). Bloc
# clustering. Reduced-form / correlational.
# Output: output/clean_iv/reg_reverse_erosion.csv + console.
# Usage:  Rscript 82_reverse_erosion.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
DOMS <- c("secular_territorial","ecclesiastical_property","ecclesiastical_appointments",
          "inheritance","marriage","crusade","excommunication","other")

br <- fread(file.path(OUTDIR,"bloc_cohesion_fullgraph.csv"))
iv <- rc("mother_iv_4hop.csv")[, .(person_id, mother_id, father_id, mgf_id)]
df <- merge(br, iv, by="person_id", all.x=TRUE)
df <- df[!is.na(mother_n_dyn_4hop) & !is.na(father_id) & father_id != ""]
df[, death_decade := (death %/% 10)*10]
# father's OWN lifetime bloc reach (father must be a focal)
df <- merge(df, br[, .(father_id=person_id, father_own_reach=n_dyn_4hop)], by="father_id", all.x=TRUE)
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
coded <- fread(file.path(OUTDIR,"matched_docs_coded.csv"),colClasses=list(character="doc_id"))[,.(doc_id,domain,is_dispute)]
mt <- fread(file.path(OUTDIR,"doc_matches_ai_extracted_high.csv"),colClasses=list(character="doc_id"))[doc_year>=1100&doc_year<=1300,.(person_id,doc_id)]
mt <- merge(mt,coded,by="doc_id")
dcd <- dcast(mt, person_id ~ domain, value.var="doc_id", fun.aggregate=length)
for (d in DOMS) if (d %in% names(dcd)) setnames(dcd, d, paste0("c_",d)) else dcd[,(paste0("c_",d)):=0]
agg <- mt[, .(c_total=.N, c_dispute=sum(is_dispute=="yes"), c_nondispute=sum(is_dispute=="no")), by=person_id]
cnt <- merge(dcd[, c("person_id", paste0("c_",DOMS)), with=FALSE], agg, by="person_id", all=TRUE)
for (cc in setdiff(names(cnt),"person_id")) cnt[is.na(get(cc)), (cc):=0]
setnames(cnt, "person_id", "father_id")
df <- merge(df, cnt, by="father_id", all.x=TRUE)
RUNGS <- c(paste0("c_",DOMS), "c_total", "c_dispute", "c_nondispute")
for (cc in RUNGS) { if (!cc %in% names(df)) df[,(cc):=0]; df[is.na(get(cc)),(cc):=0]; df[, (paste0("l",cc)) := log1p(get(cc))] }

df <- df[!is.na(father_own_reach)]                       # father must be a focal
df[, Dreach := n_dyn_4hop - father_own_reach]
cat(sprintf("N=%d (father-is-focal pairs)  blocs=%d  child reach mean=%.2f  father reach mean=%.2f  mean Delta=%.2f\n",
            nrow(df), uniqueN(df$bloc), mean(df$n_dyn_4hop), mean(df$father_own_reach), mean(df$Dreach)))
cat(sprintf("disputers high-reach? cor(father_own_reach, father lsecterr)=%.2f  cor(.., ltotal)=%.2f  cor(.., ldispute)=%.2f\n",
            cor(df$father_own_reach, df$lc_secular_territorial), cor(df$father_own_reach, df$lc_total), cor(df$father_own_reach, df$lc_dispute)))

ANC <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
BASE <- c("father_n_dyn_4hop","mother_n_dyn_4hop", ANC, "factor(bloc)","factor(death_decade)")
getp <- function(m, term){ if(is.null(m))return(c(NA,NA)); ct<-as.data.frame(coeftable(m));ct$t<-rownames(ct)
  pc<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1];r<-ct[ct$t==term,];if(nrow(r))c(r$Estimate,r[[pc]])else c(NA,NA)}
fit <- function(y, term, ctl){ tryCatch(feols(as.formula(paste(y,"~",term,"+",paste(ctl,collapse=" + "))),data=df,cluster=~bloc),error=function(e)NULL) }

res <- list()
for (cc in RUNGS) {
  term <- paste0("l",cc); tot <- cc=="c_total"
  base <- if (tot) setdiff(BASE,"father_log_total_inwin") else BASE
  lv <- getp(fit("n_dyn_4hop", term, base), term)
  dr <- getp(fit("Dreach", term, base), term)
  dn <- getp(fit("Dreach", term, c(base,"father_own_reach")), term)
  res[[length(res)+1]] <- data.table(rung=sub("c_","",cc), level_b=lv[1], level_p=lv[2],
                                      Draw_b=dr[1], Draw_p=dr[2], Dnet_b=dn[1], Dnet_p=dn[2])
}
res <- rbindlist(res); fwrite(res, file.path(OUTDIR,"clean_iv","reg_reverse_erosion.csv"))
st<-function(p) if(is.na(p))"" else if(p<.01)"**" else if(p<.05)"*" else ""
cat("\n=== father appearance -> child reach LEVEL vs DELTA(child-father) [intensive] ===\n")
cat(sprintf("  %-28s %18s %18s %18s\n","rung","LEVEL child","D raw (child-fa)","D net of fa-reach"))
for (i in seq_len(nrow(res))) { r<-res[i]
  cat(sprintf("  %-28s %9.3f (%.3f)%s %9.3f (%.3f)%s %9.3f (%.3f)%s\n", r$rung,
      r$level_b,r$level_p,st(r$level_p), r$Draw_b,r$Draw_p,st(r$Draw_p), r$Dnet_b,r$Dnet_p,st(r$Dnet_p))) }
cat("\n=== reach-level control coefficients (secterr rung) ===\n")
g2 <- function(m, terms){ if(is.null(m)){cat("    (fit failed)\n");return()}; ct<-as.data.frame(coeftable(m)); ct$t<-rownames(ct)
  pc<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1]
  for(tm in terms){ r<-ct[ct$t==tm,]; if(nrow(r)) cat(sprintf("    %-22s %+.3f (p=%.3f)\n", tm, r$Estimate, r[[pc]])) } }
cat("  LEVEL  child_reach ~ secterr + BASE :\n")
g2(fit("n_dyn_4hop","lc_secular_territorial", BASE), c("lc_secular_territorial","mother_n_dyn_4hop","father_n_dyn_4hop"))
cat("  Dnet   Delta ~ secterr + BASE + father_own_reach :\n")
g2(fit("Dreach","lc_secular_territorial", c(BASE,"father_own_reach")), c("lc_secular_territorial","father_own_reach","mother_n_dyn_4hop","father_n_dyn_4hop"))
cat("  (Dnet coef on father_own_reach = d(child-father)/d(father) = persistence - 1; -1 => full reversion)\n")
cat("\nWrote reg_reverse_erosion.csv\n")
