#!/usr/bin/env Rscript
# dual_code_strict_iv.R
# =====================
# The strict dual-coded outcome rebuild reported in the data appendix
# (subject-coding section): rebuild the secular-territorial outcome from
# only the documents that BOTH independent coding passes assign to that
# domain (the strictest available definition), re-run the unified 2SLS
# baseline, and compare against the main (API) coding restricted to the
# same dual-coded 2,000 documents.
#
# Inputs : output/clean_iv/unified_frame.csv          (from 100_unified_baseline.R)
#          output/matched_docs_coded.csv              (primary coding; frozen)
#          output/recode_agreement/agent_coded_overlap.csv (second coding; frozen)
#          output/doc_matches_ai_extracted_high.csv
# Output : output/clean_iv/reg_dual_code_strict.csv
# Usage  : Rscript dual_code_strict_iv.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
H <- 4L

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"),
            colClasses = list(character = "person_id"))

api <- fread(file.path(OUTDIR, "matched_docs_coded.csv"),
             colClasses = list(character = "doc_id"))[, .(doc_id, domain_api = domain)]
agent <- fread(file.path(OUTDIR, "recode_agreement", "agent_coded_overlap.csv"),
               colClasses = list(character = "doc_id"))[, .(doc_id, domain_agent = domain)]
ov <- merge(api, agent, by = "doc_id")   # the dual-coded overlap (2,000 docs)

both_st  <- ov[domain_api == "secular_territorial" & domain_agent == "secular_territorial", doc_id]
api_st   <- ov[domain_api == "secular_territorial", doc_id]
api_only <- ov[domain_api == "secular_territorial" & domain_agent != "secular_territorial", doc_id]
agn_only <- ov[domain_api != "secular_territorial" & domain_agent == "secular_territorial", doc_id]
neither  <- ov[domain_api != "secular_territorial" & domain_agent != "secular_territorial", doc_id]
cat(sprintf("overlap=%d  both=%d  api_only=%d  agent_only=%d  neither=%d\n",
            nrow(ov), length(both_st), length(api_only), length(agn_only), length(neither)))

mt <- fread(file.path(OUTDIR, "doc_matches_ai_extracted_high.csv"),
            colClasses = list(character = "doc_id"))[
  doc_year >= 1100 & doc_year <= 1300, .(person_id, doc_id)]

count_docs <- function(doc_set, col) {
  cc <- mt[doc_id %in% doc_set][, .(n = .N), by = person_id]
  d <- merge(df[, .(person_id)], cc, by = "person_id", all.x = TRUE)
  d[is.na(n), n := 0]
  df[[col]] <<- d$n[match(df$person_id, d$person_id)]
  invisible()
}
count_docs(both_st, "n_strict")
count_docs(api_st, "n_api_dual")

# identical control string to 100_unified_baseline.R (the paper's stated X_i)
anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
fe <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
ctl <- paste(c(fe, anc, "f_extra4"), collapse = " + ")

twoway_p <- function(m){ if (is.null(m)) return(NA_real_)
  s <- tryCatch(summary(m, vcov = ~ dynasty + death_decade), error = function(e) NULL)
  if (is.null(s)) return(NA_real_)
  ct <- as.data.frame(coeftable(s)); ct$t <- rownames(ct)
  pc <- intersect(c("Pr(>|t|)","Pr(>|z|)"), names(ct))[1]
  rr <- ct[ct$t == "fit_n_dyn_4hop", ]; if (nrow(rr)) rr[[pc]] else NA_real_ }

run1 <- function(col, tag) {
  d <- copy(df); d[, .y := log1p(get(col))]
  m <- ic_fit_iv(".y", H, ctl, d)
  r <- ic_extract(m, H)
  r[, `:=`(spec = tag, p_2way = twoway_p(m), npos = sum(df[[col]] > 0),
           n_docs = NA_integer_)]
  r
}
res <- rbindlist(list(
  cbind(run1("n_strict",   "both-coders secular-territorial (strict)"),  docs = length(both_st)),
  cbind(run1("n_api_dual", "API coding restricted to dual-coded docs"),  docs = length(api_st))
), fill = TRUE)

cat("\n")
for (i in seq_len(nrow(res))) { x <- res[i]
  cat(sprintf("  %-45s beta=%.4f SE=%.4f p=%.4g p_2way=%.4g F=%.0f N=%d npos=%d docs=%d\n",
              x$spec, x$beta, x$SE, x$p, x$p_2way, x$F_first, x$N, x$npos, x$docs)) }

fwrite(res[, .(spec, beta, SE, p, p_2way, F_first, N, npos, docs)],
       file.path(OUTDIR, "clean_iv", "reg_dual_code_strict.csv"))
cat("\nwrote output/clean_iv/reg_dual_code_strict.csv\n")
