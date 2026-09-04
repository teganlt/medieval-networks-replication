#!/usr/bin/env Rscript
# 105_unified_loo.R
# =================
# Bloc leave-one-out + drop-largest-bloc for the UNIFIED baseline (100),
# secular_territorial and total. Persists the full LOO grid as CSV (the audit
# flagged that 60's LOO detail lived only in a console capture).
# Output: output/clean_iv/reg_unified_loo.csv, reg_unified_drop_largest.csv
# Usage:  Rscript 105_unified_loo.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})

df <- fread(file.path(OUTDIR,"clean_iv","unified_frame.csv"))
anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
CTL <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc, "f_extra4"), collapse=" + ")

fit1 <- function(d, col) {
  d <- copy(d); d[, .y := log1p(get(col))]
  m <- tryCatch(feols(as.formula(sprintf(".y ~ %s | n_dyn_4hop ~ mother_n_dyn_4hop", CTL)),
                      data=d, cluster=~dynasty), error=function(e) NULL)
  if (is.null(m)) return(data.table(beta=NA_real_, SE=NA_real_, p=NA_real_,
                                    SE_2way=NA_real_, p_2way=NA_real_, N=NA_integer_))
  ct <- as.data.frame(coeftable(m)); r <- ct[rownames(ct)=="fit_n_dyn_4hop",]
  # two-way (bloc x death-decade) added 8/19: previously the LOO grid shipped
  # bloc-clustered only; fixest's PSD fix applies as in the baseline (conservative)
  s2 <- tryCatch(summary(m, vcov=~dynasty+death_decade), error=function(e) NULL)
  r2 <- if (is.null(s2)) NULL else {
    ct2 <- as.data.frame(coeftable(s2)); ct2[rownames(ct2)=="fit_n_dyn_4hop",]
  }
  data.table(beta=r$Estimate, SE=r$`Std. Error`, p=r$`Pr(>|t|)`,
             SE_2way=if (is.null(r2)) NA_real_ else r2$`Std. Error`,
             p_2way=if (is.null(r2)) NA_real_ else r2$`Pr(>|t|)`, N=nobs(m))
}

blocs <- df[, .(nfoc=.N, secterr_mass=sum(dom_secular_territorial)), by=dynasty][order(-nfoc)]
res <- list()
for (b in blocs$dynasty) {
  for (col in c("dom_secular_territorial","dom_total")) {
    r <- fit1(df[dynasty != b], col)
    res[[length(res)+1]] <- data.table(dropped=b, outcome=sub("dom_","",col),
      nfoc_dropped=blocs[dynasty==b, nfoc], r)
  }
}
R <- rbindlist(res)
fwrite(R, file.path(OUTDIR,"clean_iv","reg_unified_loo.csv"))

big <- blocs$dynasty[1]
DL <- rbindlist(lapply(c("dom_secular_territorial","dom_total"), function(col) {
  full <- fit1(df, col); drop <- fit1(df[dynasty != big], col)
  data.table(outcome=sub("dom_","",col), beta_full=full$beta, beta_drop=drop$beta,
             p_full=full$p, p_drop=drop$p,
             p2_full=full$p_2way, p2_drop=drop$p_2way, largest=big,
             largest_share_focals=blocs[1,nfoc]/nrow(df),
             largest_share_secterr=blocs[1,secterr_mass]/sum(df$dom_secular_territorial))
}))
fwrite(DL, file.path(OUTDIR,"clean_iv","reg_unified_drop_largest.csv"))

st <- R[outcome=="secular_territorial"]
cat(sprintf("UNIFIED bloc-LOO (secterr): %d/%d drops significant at 5%% (bloc); beta range [%.4f, %.4f]\n",
            sum(st$p < .05, na.rm=TRUE), nrow(st), min(st$beta, na.rm=TRUE), max(st$beta, na.rm=TRUE)))
cat(sprintf("  two-way: %d/%d at 5%%; p_2way range [%.4f, %.4f]\n",
            sum(st$p_2way < .05, na.rm=TRUE), nrow(st),
            min(st$p_2way, na.rm=TRUE), max(st$p_2way, na.rm=TRUE)))
print(DL)
cat("Wrote reg_unified_loo.csv, reg_unified_drop_largest.csv\n")
