#!/usr/bin/env Rscript
# 102_hopsweep_iv.R
# =================
# Hop sweep of the UNIFIED Prediction-1 baseline (100_unified_baseline.R):
# for each h in 3..6, 2SLS with endogenous n_dyn_<h>hop and instrument
# mother_n_dyn_<h>hop, all controls / FE / clustering EXACTLY as in the
# unified spec (taken from output/clean_iv/unified_frame.csv; the ancestor
# battery stays at its hop-4 definition -- only the endogenous reach and
# its instrument move across hops).  Backs the paper's "5- and 6-hop radii"
# claim.  Outcomes: secular_territorial and total, log1p.
# Internal consistency check: hop 4 must reproduce the baseline
# (secterr beta = 0.0326).
# Output: output/clean_iv/reg_unified_hopsweep.csv
# Usage:  Rscript 102_hopsweep_iv.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
HOPS <- 3:6

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
hs <- fread(file.path(OUTDIR, "bloc_reach_hopsweep.csv"))

# ---- consistency of the hop-sweep BFS against the frame's hop-3/4 columns ----
chk <- merge(df[, .(person_id, n_dyn_3hop, n_dyn_4hop, n_nodes_4hop, mother_n_dyn_4hop)],
             hs[, .(person_id, h3 = n_dyn_3hop, h4 = n_dyn_4hop, s4 = n_nodes_4hop,
                    m4 = mother_n_dyn_4hop)], by = "person_id")
stopifnot(nrow(chk) == nrow(df),
          all(chk$n_dyn_3hop == chk$h3), all(chk$n_dyn_4hop == chk$h4),
          all(chk$n_nodes_4hop == chk$s4), all(chk$mother_n_dyn_4hop == chk$m4))
cat(sprintf("hop-sweep BFS matches unified_frame on hops 3-4 for all %d focals\n", nrow(chk)))

# merge in hop-5/6 (and take 3/4 from the frame itself, already verified equal)
keep <- c("person_id", as.vector(outer(c("n_dyn_", "n_nodes_", "mother_n_dyn_"),
                                       paste0(5:6, "hop"), paste0)))
df <- merge(df, hs[, ..keep], by = "person_id")
stopifnot(!anyNA(df$mother_n_dyn_5hop), !anyNA(df$mother_n_dyn_6hop))

# ---- unified controls (identical string to 100's ctl_new) ----
anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
fe <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
ctl <- paste(c(fe, anc, "f_extra4"), collapse = " + ")

fit_iv <- function(outcome, h, dat) {
  rhs <- sprintf("%s ~ %s | n_dyn_%dhop ~ mother_n_dyn_%dhop", outcome, ctl, h, h)
  tryCatch(feols(as.formula(rhs), data = dat, cluster = ~ dynasty),
           error = function(e) NULL)
}
extract <- function(m, h) {
  tname <- sprintf("fit_n_dyn_%dhop", h)
  if (is.null(m)) return(data.table(beta=NA_real_, SE=NA_real_, p_bloc=NA_real_,
                                    F_first=NA_real_, N=NA_integer_))
  ct <- as.data.frame(coeftable(m)); ct$term <- rownames(ct); setDT(ct)
  pcol <- intersect(c("Pr(>|t|)","Pr(>|z|)"), names(ct))[1]
  r <- ct[term == tname]
  fs <- tryCatch(summary(m, stage = 1), error = function(e) NULL); Ff <- NA_real_
  if (!is.null(fs)) {
    fst <- as.data.frame(coeftable(fs)); fst$term <- rownames(fst); setDT(fst)
    tr <- fst[term == sprintf("mother_n_dyn_%dhop", h)]
    if (nrow(tr) > 0) Ff <- (tr$Estimate / tr[["Std. Error"]])^2
  }
  data.table(beta = r$Estimate, SE = r[["Std. Error"]], p_bloc = r[[pcol]],
             F_first = Ff, N = nobs(m))
}
twoway_p <- function(m, h) {
  if (is.null(m)) return(NA_real_)
  s <- tryCatch(summary(m, vcov = ~ dynasty + death_decade), error = function(e) NULL)
  if (is.null(s)) return(NA_real_)
  ct <- as.data.frame(coeftable(s)); ct$t <- rownames(ct)
  pc <- intersect(c("Pr(>|t|)","Pr(>|z|)"), names(ct))[1]
  rr <- ct[ct$t == sprintf("fit_n_dyn_%dhop", h), ]
  if (nrow(rr)) rr[[pc]] else NA_real_
}

res <- rbindlist(lapply(HOPS, function(h) {
  rcol <- sprintf("n_dyn_%dhop", h); scol <- sprintf("n_nodes_%dhop", h)
  sdr <- sd(df[[rcol]]); crs <- cor(df[[rcol]], df[[scol]])
  rbindlist(lapply(c("dom_secular_territorial", "dom_total"), function(col) {
    d <- copy(df); d[, .y := log1p(get(col))]
    m <- fit_iv(".y", h, d); r <- extract(m, h)
    r[, `:=`(hop = h, domain = sub("dom_", "", col), beta_sd = beta * sdr,
             p_2way = twoway_p(m, h), sd_reach = sdr, cor_reach_size = crs)]
    r
  }))
}))
setcolorder(res, c("hop","domain","beta","beta_sd","SE","p_bloc","p_2way",
                   "F_first","sd_reach","cor_reach_size","N"))
fwrite(res, file.path(OUTDIR, "clean_iv", "reg_unified_hopsweep.csv"))

cat(sprintf("\n%-3s %-20s %9s %9s %9s %9s %9s %8s %8s %7s %5s\n",
            "hop","domain","beta","beta_sd","SE","p_bloc","p_2way","F_first","sd","corRS","N"))
for (i in seq_len(nrow(res))) { x <- res[i]
  cat(sprintf("%-3d %-20s %9.4f %9.4f %9.4f %9.4f %9.4f %8.1f %8.1f %7.3f %5d\n",
              x$hop, x$domain, x$beta, x$beta_sd, x$SE, x$p_bloc, x$p_2way,
              x$F_first, x$sd_reach, x$cor_reach_size, x$N)) }

b4 <- res[hop == 4 & domain == "secular_territorial", beta]
cat(sprintf("\nconsistency: hop-4 secterr beta = %.6f (baseline 0.032574)\n", b4))
stopifnot(abs(b4 - 0.032574394859147) < 1e-9)
cat("Wrote reg_unified_hopsweep.csv\n")
