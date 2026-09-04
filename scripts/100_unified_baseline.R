#!/usr/bin/env Rscript
# 100_unified_baseline.R
# ======================
# THE unified Prediction-1 baseline: the spec exactly as the paper text states
# it (results section 4.1) — resolves the 7/27 audit's text-code mismatch.
#   vs 57 (old headline): DROPS focal log_deg (undisclosed there), ADDS
#   f_extra4 (father's bloc increment |F\M|, listed in the paper but absent
#   from 57's controls). Frame otherwise identical: bloc_reach_fullgraph
#   (N=2,195), bloc+death-decade+title FE, ancestor battery, bloc cluster.
# Also runs:
#   - the OLD 57 spec side by side  -> reg_unified_spec_compare.csv
#   - Frederick II single-person omission (max total appearances)
#     for every domain                -> reg_unified_dropfrederick.csv
# Emits tables/tab_domains.tex programmatically (audit: the old table was
# hand-transcribed).
# Output: output/clean_iv/reg_unified_bloc_iv.csv (+ the two above)
# Usage:  Rscript 100_unified_baseline.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
H <- 4L
DOMS <- c("secular_territorial","ecclesiastical_appointments","crusade","excommunication",
          "ecclesiastical_property","inheritance","marriage","other")
LAB <- c(secular_territorial="Secular-territorial", ecclesiastical_appointments="Ecclesiastical appointments",
         crusade="Crusade", other="Other (heresy, diplomacy)", excommunication="Excommunication",
         ecclesiastical_property="Ecclesiastical property", inheritance="Inheritance",
         marriage="Marriage", total="All documents")

# ---- frame: identical to 57, plus f_extra4 ----
br <- fread(file.path(OUTDIR,"bloc_reach_fullgraph.csv"))
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
ctl_old <- paste(c("log_deg", fe, anc), collapse=" + ")      # = 57 as coded

twoway_p <- function(m){ if(is.null(m))return(NA_real_); s<-tryCatch(summary(m,vcov=~dynasty+death_decade),error=function(e)NULL); if(is.null(s))return(NA_real_)
  ct<-as.data.frame(coeftable(s));ct$t<-rownames(ct);pc<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1];rr<-ct[ct$t=="fit_n_dyn_4hop",];if(nrow(rr))rr[[pc]]else NA_real_}

run_all <- function(dat, ctl, tag) {
  rbindlist(lapply(c(paste0("dom_",DOMS),"dom_total"), function(col){
    d<-copy(dat); d[,.y:=log1p(get(col))]; m<-ic_fit_iv(".y",H,ctl,d); r<-ic_extract(m,H)
    r[,`:=`(domain=sub("dom_","",col), p_2way=twoway_p(m), npos=sum(dat[[col]]>0), spec=tag)]; r}), fill=TRUE)
}

cat(sprintf("N=%d  blocs=%d  cor(reach,size)=%.2f\n", nrow(df), uniqueN(df$dynasty), cor(df$n_dyn_4hop,df$n_nodes_4hop)))
fwrite(df, file.path(OUTDIR,"clean_iv","unified_frame.csv"))   # shared analysis frame for 101-111
res_new <- run_all(df, ctl_new, "unified (paper X_i: -log_deg +f_extra4)")
res_old <- run_all(df, ctl_old, "57 as coded (+log_deg -f_extra4)")

fwrite(res_new[,.(domain,beta,SE,p,p_2way,F_first,N,npos)], file.path(OUTDIR,"clean_iv","reg_unified_bloc_iv.csv"))
cmp <- merge(res_new[,.(domain,beta_new=beta,p2_new=p_2way)], res_old[,.(domain,beta_old=beta,p2_old=p_2way)], by="domain")
fwrite(cmp, file.path(OUTDIR,"clean_iv","reg_unified_spec_compare.csv"))

# ---- Frederick II omission (max total appearances) ----
fred <- df[which.max(dom_total)]
cat(sprintf("\nDropping max-appearance noble: %s (person_id=%s, %d total appearances)\n",
            fred$fname, fred$person_id, fred$dom_total))
res_nofred <- run_all(df[person_id != fred$person_id], ctl_new, "unified, drop Frederick II")
fwrite(res_nofred[,.(domain,beta,SE,p,p_2way,F_first,N,npos)], file.path(OUTDIR,"clean_iv","reg_unified_dropfrederick.csv"))

# ---- console ----
show <- function(r, hdr){ cat(sprintf("\n=== %s ===\n", hdr))
  cat(sprintf("  %-26s %9s %9s %9s %9s %7s %6s\n","domain","beta","SE","p_bloc","p_2way","Ffirst","npos"))
  o <- r[order(-beta)]
  for (i in seq_len(nrow(o))) { x<-o[i]; st<-if(is.na(x$p))""else if(x$p<0.01)"**"else if(x$p<0.05)"*"else""
    cat(sprintf("  %-26s %9.4f %9.4f %9.4f %9.4f %7.1f %6d%s\n", x$domain,x$beta,x$SE,x$p,x$p_2way,x$F_first,x$npos,st)) } }
show(res_new, "UNIFIED baseline (paper X_i)")
show(res_nofred, "UNIFIED, Frederick II dropped")
cat("\nSpec deltas (new vs 57-as-coded):\n"); print(cmp[order(-abs(beta_new-beta_old))])

# ---- emit tab_domains.tex ----
fm <- function(v,d=3) formatC(v, format="f", digits=d)
fp <- function(p) ifelse(is.na(p), "--", ifelse(p<0.001, "$<$0.001", fm(p,3)))
ord <- res_new[domain!="total"][order(-beta)]
tot <- res_new[domain=="total"]
lines <- c("\\begin{table}[t]","\\centering",
  sprintf("\\caption{Kin-reach and papal appearance, by subject domain. Each row is a separate 2SLS regression of $\\log(1+\\text{appearances})$ in that domain on focal kin-reach, instrumented by the mother's pre-natal reach. $N=%s$; $%d$ blocs; first-stage $F=%.0f$. $p$ is bloc-clustered; $p_{\\text{2-way}}$ clusters on bloc and decade. The last column counts nobles with at least one appearance in the domain.}",
          format(res_new$N[1], big.mark=","), uniqueN(df$dynasty), res_new$F_first[1]),
  "\\label{tab:forward}","\\begin{tabular}{lccccc}","\\toprule",
  "Domain & $\\beta$ & SE & $p$ & $p_{\\text{2-way}}$ & $n>0$ \\\\","\\midrule")
for (i in seq_len(nrow(ord))) { r <- ord[i]
  nm <- LAB[r$domain]; b <- fm(r$beta); s <- fm(r$SE)
  if (r$domain=="secular_territorial") lines <- c(lines, sprintf("\\textbf{%s} & \\textbf{%s} & %s & %s & \\textbf{%s} & %d \\\\", nm,b,s,fp(r$p),fp(r$p_2way),r$npos))
  else lines <- c(lines, sprintf("%s & %s & %s & %s & %s & %d \\\\", nm,b,s,fp(r$p),fp(r$p_2way),r$npos)) }
lines <- c(lines,"\\midrule",
  sprintf("All documents & %s & %s & %s & %s & %d \\\\", fm(tot$beta),fm(tot$SE),fp(tot$p),fp(tot$p_2way),tot$npos),
  "\\bottomrule","\\end{tabular}","\\end{table}")
dir.create(file.path(ROOT,"tables"), showWarnings=FALSE)
writeLines(lines, file.path(ROOT,"tables","tab_domains.tex"))
cat("\nWrote reg_unified_bloc_iv.csv, reg_unified_spec_compare.csv, reg_unified_dropfrederick.csv, tables/tab_domains.tex\n")
