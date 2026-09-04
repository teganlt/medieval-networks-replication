#!/usr/bin/env Rscript
# 116_unified_excess_share.R
# ==========================
# Ports the dispute / excess / share companions (58's outcomes, 68's
# constructions) to the UNIFIED Pred-1 spec (100_unified_baseline.R): same
# frame (output/clean_iv/unified_frame.csv, N=2,195), same 2SLS
# (n_dyn_4hop ~ mother_n_dyn_4hop), same controls (paper X_i: title/decade/bloc
# FE + ancestor battery + f_extra4, NO focal log_deg), bloc cluster.
# Outcomes:
#   dispute          log1p(n_dispute)   n_dispute = matched docs with
#                    is_dispute=='yes' (matched_docs_coded x doc_matches_high,
#                    window 1100-1300), per person -- the 95/110 construction
#   nonterritorial   log1p(n_total - n_secterr)
#   excess_secterr   n_secterr - p_sec*n_total, p_sec = corpus share of
#                    secterr docs (68 lines 53-54: uniqueN doc-level)
#   share_secterr    n_secterr/n_total on the n_total>0 subsample
# Output: output/clean_iv/reg_unified_excess_share.csv
# Usage:  Rscript 116_unified_excess_share.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R"))
H <- 4L

# ---- unified frame (written by 100) ----
df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))

# ---- dispute counts + corpus secterr share ----
coded <- fread(file.path(OUTDIR, "matched_docs_coded.csv"),
               colClasses = list(character = "doc_id"))[, .(doc_id, is_dispute, domain)]
mt <- fread(file.path(OUTDIR, "doc_matches_ai_extracted_high.csv"),
            colClasses = list(character = "doc_id"))[
  doc_year >= 1100 & doc_year <= 1300, .(person_id, doc_id)]
mtd <- merge(mt, coded, by = "doc_id")
ndisp <- mtd[is_dispute == "yes", .(n_dispute = .N), by = person_id]
df <- merge(df, ndisp, by = "person_id", all.x = TRUE)
df[is.na(n_dispute), n_dispute := 0]
p_sec <- mtd[domain == "secular_territorial", uniqueN(doc_id)] / mtd[, uniqueN(doc_id)]

df[, n_secterr := dom_secular_territorial]
df[, n_total   := dom_total]
df[, n_nonterr := n_total - n_secterr]
df[, excess_sec := n_secterr - p_sec * n_total]

cat(sprintf("N=%d  blocs=%d  p_sec=%.4f  dispute_pos=%d  secterr_pos=%d  appearers=%d\n",
            nrow(df), uniqueN(df$dynasty), p_sec,
            sum(df$n_dispute > 0), sum(df$n_secterr > 0), sum(df$n_total > 0)))

# ---- unified controls (verbatim ctl_new in 100) ----
anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
fe <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
ctl_new <- paste(c(fe, anc, "f_extra4"), collapse = " + ")

twoway_p <- function(m){ if(is.null(m))return(NA_real_); s<-tryCatch(summary(m,vcov=~dynasty+death_decade),error=function(e)NULL); if(is.null(s))return(NA_real_)
  ct<-as.data.frame(coeftable(s));ct$t<-rownames(ct);pc<-intersect(c("Pr(>|t|)","Pr(>|z|)"),names(ct))[1];rr<-ct[ct$t=="fit_n_dyn_4hop",];if(nrow(rr))rr[[pc]]else NA_real_}

run1 <- function(yexpr, lab, sub = NULL) {
  d <- copy(df); if (!is.null(sub)) d <- d[eval(parse(text = sub))]
  d[, .y := eval(parse(text = yexpr))]
  m <- ic_fit_iv(".y", H, ctl_new, d)
  r <- ic_extract(m, H)
  npos <- if (lab == "dispute") sum(d$n_dispute > 0)
          else if (lab == "nonterritorial") sum(d$n_nonterr > 0)
          else sum(d$n_secterr > 0)
  r[, `:=`(outcome = lab, p_2way = twoway_p(m), npos = npos)]
  r
}

res <- rbindlist(list(
  run1("log1p(n_dispute)",   "dispute"),
  run1("log1p(n_nonterr)",   "nonterritorial"),
  run1("excess_sec",         "excess_secterr"),
  run1("n_secterr/n_total",  "share_secterr", sub = "n_total>0")
), fill = TRUE)
res[, p_sec_corpus := p_sec]
out <- res[, .(outcome, beta, SE, p_bloc = p, p_2way, F_first, N, npos, p_sec_corpus)]

cat(sprintf("\n  %-16s %10s %10s %9s %9s %8s %6s %6s\n",
            "outcome","beta","SE","p_bloc","p_2way","F_first","N","npos"))
for (i in seq_len(nrow(out))) { x <- out[i]
  cat(sprintf("  %-16s %10.4f %10.4f %9.4f %9.4f %8.1f %6d %6d\n",
              x$outcome, x$beta, x$SE, x$p_bloc, x$p_2way, x$F_first, x$N, x$npos)) }

fwrite(out, file.path(OUTDIR, "clean_iv", "reg_unified_excess_share.csv"))
cat("\nWrote output/clean_iv/reg_unified_excess_share.csv\n")
