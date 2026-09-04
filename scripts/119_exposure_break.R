#!/usr/bin/env Rscript
# 119_exposure_break.R
# ====================
# Two quick robustness analyses on the 7/27 unified frame:
#  (a) EXPOSURE CONTROL: add years_in_window = pmin(death,1300)-pmax(birth,1100)+1
#      to the unified Pred-1 2SLS battery (100) for secular_territorial + total;
#      compare against the baseline (secterr 0.0326 / p_2way .005).
#  (b) BREAK-YEAR SENSITIVITY for the peer arbitration-share flip: the S3 zD
#      regression (111) re-run splitting at birth <= B, B in {1195,1205,1215,
#      1225,1235}, plus a DONUT (exclude born 1205-1225, split at 1215).
#      zD standardized ONCE on the FULL peer sample (as 111 does).
#  (c) COARSE REGION SPLIT: 38 in-sample blocs classified British-Isles vs
#      Continental by dominant named-dynasty label (roster logic of
#      build_summary_tables.py: Alba_Scottish / West_Saxon / Welsh_Dinefwr and
#      the Irish-dominant B48 = British Isles). S3 flip within each region only
#      if the thin cells are estimable; otherwise counts are reported and the
#      cell is skipped.
# Output: output/clean_iv/reg_unified_exposure_break.csv
#         (block, spec, era_or_break, domain, beta, SE, p_bloc, p_2way, N)
# Usage:  Rscript 119_exposure_break.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})

# ---- shared battery (identical to 100 / 111) ----
anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin",
  "mgf_n_dyn_4hop")
fe  <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
BAT <- paste(c(fe, anc, "f_extra4"), collapse=" + ")
DOMS2 <- c("secular_territorial","total")

# coefficient extractor: bloc-clustered row + two-way (bloc+decade) p
grab <- function(m, term) {
  out <- list(beta=NA_real_, SE=NA_real_, p_bloc=NA_real_, p_2way=NA_real_, N=NA_integer_)
  if (is.null(m)) return(out)
  ct <- as.data.frame(coeftable(m)); ct$t <- rownames(ct)
  pc <- intersect(c("Pr(>|t|)","Pr(>|z|)"), names(ct))[1]
  r <- ct[ct$t==term,]
  s2 <- tryCatch(summary(m, vcov=~dynasty+death_decade), error=function(e) NULL)
  if (!is.null(s2)) { c2 <- as.data.frame(coeftable(s2)); c2$t <- rownames(c2)
    pc2 <- intersect(c("Pr(>|t|)","Pr(>|z|)"), names(c2))[1]
    r2 <- c2[c2$t==term,]; if (nrow(r2)) out$p_2way <- r2[[pc2]] }
  out$N <- nobs(m)
  if (nrow(r)) { out$beta <- r$Estimate; out$SE <- r$`Std. Error`; out$p_bloc <- r[[pc]] }
  out
}
first_F <- function(m) {
  fs <- tryCatch(summary(m, stage=1), error=function(e) NULL)
  if (is.null(fs)) return(NA_real_)
  fct <- as.data.frame(coeftable(fs)); fct$t <- rownames(fct)
  r <- fct[fct$t=="mother_n_dyn_4hop",]
  if (nrow(r)) (r$Estimate/r$`Std. Error`)^2 else NA_real_
}
RES <- list()
keep <- function(block, spec, era, dom, g) {
  RES[[length(RES)+1]] <<- data.table(block=block, spec=spec, era_or_break=era,
    domain=dom, beta=g$beta, SE=g$SE, p_bloc=g$p_bloc, p_2way=g$p_2way, N=g$N)
}

# =====================================================================
# (a) EXPOSURE CONTROL on the unified 2SLS
# =====================================================================
df <- fread(file.path(OUTDIR,"clean_iv","unified_frame.csv"))
df[, years_in_window := pmin(death,1300) - pmax(birth,1100) + 1]
cat(sprintf("(a) unified frame: N=%d  blocs=%d  years_in_window: min=%d med=%.0f max=%d  cor(yiw, log1p(dom_total))=%.3f\n",
  nrow(df), uniqueN(df$dynasty), min(df$years_in_window), median(df$years_in_window),
  max(df$years_in_window), cor(df$years_in_window, log1p(df$dom_total))))

fit_iv <- function(dat, ctl, ycol) {
  d <- copy(dat); d[, .y := log1p(get(ycol))]
  tryCatch(feols(as.formula(sprintf(".y ~ %s | n_dyn_4hop ~ mother_n_dyn_4hop", ctl)),
                 data=d, cluster=~dynasty), error=function(e) NULL)
}
cat("\n=== (a) UNIFIED 2SLS: baseline vs + years_in_window ===\n")
cat(sprintf("  %-20s %-22s %9s %9s %10s %9s %7s %5s\n",
            "domain","spec","beta","SE","p_bloc","p_2way","F1st","N"))
for (dom in DOMS2) {
  ycol <- paste0("dom_",dom)
  for (sp in list(c("baseline", BAT), c("+years_in_window", paste(BAT,"+ years_in_window")))) {
    m <- fit_iv(df, sp[2], ycol); g <- grab(m, "fit_n_dyn_4hop")
    keep("a_exposure", sp[1], "ALL", dom, g)
    cat(sprintf("  %-20s %-22s %9.4f %9.4f %10.2g %9.4f %7.1f %5d\n",
                dom, sp[1], g$beta, g$SE, g$p_bloc, g$p_2way, first_F(m), g$N))
  }
}

# =====================================================================
# (b) BREAK-YEAR SENSITIVITY for the peer S3 zD flip
# =====================================================================
pr <- fread(file.path(OUTDIR,"clean_iv","peer_rf_build.csv"))[
  , .(person_id, peer_nkin, peer_breadth_pre, peer_secterr_dated, EMFP)]
pf <- merge(df, pr, by="person_id")          # inner join, as in 111
pf <- pf[peer_nkin > 0]
pf[, zD := (peer_secterr_dated - mean(peer_secterr_dated)) / sd(peer_secterr_dated)]  # FULL-sample SD
mism <- pf[, sum(EMFP != as.integer(birth <= 1215))]
cat(sprintf("\n(b) peer frame: N=%d  blocs=%d  born<=1215=%d / >1215=%d  (EMFP-vs-birth mismatches: %d)\n",
  nrow(pf), uniqueN(pf$dynasty), sum(pf$birth<=1215), sum(pf$birth>1215), mism))

fit_s3 <- function(d, ycol) {
  dd <- copy(d); dd[, .y := log1p(get(ycol))]
  tryCatch(feols(as.formula(paste0(".y ~ zD + n_dyn_4hop + ", BAT)),
                 data=dd, cluster=~dynasty), error=function(e) NULL)
}

cat("\n=== (b) S3 zD by break year (beta per FULL-sample SD of peer_secterr_dated) ===\n")
cat(sprintf("  %-14s %-6s %-20s %9s %9s %10s %9s %5s %5s\n",
            "break","side","domain","beta","SE","p_bloc","p_2way","N","npos"))
run_side <- function(tag, side, d) {
  for (dom in DOMS2) {
    ycol <- paste0("dom_",dom)
    m <- fit_s3(d, ycol); g <- grab(m, "zD")
    keep("b_break", "S3 zD", paste0(tag,"_",side), dom, g)
    cat(sprintf("  %-14s %-6s %-20s %9.4f %9.4f %10.2g %9.4f %5d %5d\n",
                tag, side, dom, g$beta, g$SE, g$p_bloc, g$p_2way, g$N, sum(d[[ycol]]>0)))
  }
}
for (B in c(1195,1205,1215,1225,1235)) {
  run_side(sprintf("B%d",B), "pre",  pf[birth <= B])
  run_side(sprintf("B%d",B), "post", pf[birth >  B])
}
dnt <- pf[!(birth >= 1205 & birth <= 1225)]
cat(sprintf("  [donut drops %d focals born 1205-1225]\n", nrow(pf)-nrow(dnt)))
run_side("donut1215", "pre",  dnt[birth <= 1215])
run_side("donut1215", "post", dnt[birth >  1215])

# =====================================================================
# (c) COARSE REGION SPLIT (British Isles vs Continental)
# =====================================================================
pers <- fread(file.path(OUTDIR,"persons_imputed.csv"))[, .(id, birth_p = suppressWarnings(as.numeric(birth)))]
pb   <- fread(file.path(OUTDIR,"patriline_bloc_assignment.csv"))[, .(id, bloc_pb = dynasty)]
nd   <- fread(file.path(OUTDIR,"named_dynasty_assignment.csv"))[, .(id, lab = dynasty)]
mem  <- merge(pb, pers, by="id", all.x=TRUE)
mem  <- mem[!is.na(birth_p) & birth_p >= 800 & birth_p <= 1500]      # roster's medieval filter
mem  <- merge(mem, nd, by="id", all.x=TRUE)
lab_tab <- mem[!is.na(lab) & lab != "",
               .N, by=.(bloc_pb, lab)][order(bloc_pb, -N)]
dom_lab <- lab_tab[, .(dom_label = lab[1], dom_share = N[1]/sum(N)), by=bloc_pb]
BI_LABELS <- c("Alba_Scottish","West_Saxon","Welsh_Dinefwr")
cls <- data.table(bloc = sort(unique(df$bloc)))
cls <- merge(cls, dom_lab, by.x="bloc", by.y="bloc_pb", all.x=TRUE)
cls[, region := ifelse(bloc == "B48" | dom_label %in% BI_LABELS, "British_Isles", "Continental")]
cls <- merge(cls, df[, .(n_focal_unified = .N), by=bloc], by="bloc", all.x=TRUE)
cls <- merge(cls, pf[, .(n_focal_peer = .N), by=bloc], by="bloc", all.x=TRUE)
cls[is.na(n_focal_peer), n_focal_peer := 0L]

cat("\n=== (c) 38-bloc region classification (dominant named-dynasty label) ===\n")
cat(sprintf("  %-6s %-24s %6s %8s %8s  %s\n","bloc","dom_label","share","focals","peerN","region"))
for (i in seq_len(nrow(cls))) { r <- cls[i]
  cat(sprintf("  %-6s %-24s %5.0f%% %8d %8d  %s\n", r$bloc,
      ifelse(is.na(r$dom_label),"--",r$dom_label),
      100*ifelse(is.na(r$dom_share),0,r$dom_share), r$n_focal_unified, r$n_focal_peer, r$region))
}
cat(sprintf("  -> British Isles: %d blocs, %d focals (peer frame %d) | Continental: %d blocs, %d focals (peer frame %d)\n",
  cls[region=="British_Isles",.N], cls[region=="British_Isles",sum(n_focal_unified)], cls[region=="British_Isles",sum(n_focal_peer)],
  cls[region=="Continental",.N],  cls[region=="Continental",sum(n_focal_unified)],  cls[region=="Continental",sum(n_focal_peer)]))

pf <- merge(pf, cls[, .(bloc, region)], by="bloc")
cat("\n  cell counts (peer frame), split at birth<=1215:\n")
cat(sprintf("  %-14s %-9s %6s %6s %14s %10s\n","region","era","N","blocs","npos_secterr","npos_total"))
feas <- list()
for (rg in c("British_Isles","Continental")) for (er in c("pre1215","post1215")) {
  d <- if (er=="pre1215") pf[region==rg & birth<=1215] else pf[region==rg & birth>1215]
  np_s <- sum(d$dom_secular_territorial>0); np_t <- sum(d$dom_total>0)
  feas[[paste(rg,er)]] <- list(d=d, np_s=np_s, np_t=np_t)
  cat(sprintf("  %-14s %-9s %6d %6d %14d %10d\n", rg, er, nrow(d), uniqueN(d$dynasty), np_s, np_t))
}
MIN_POS <- 8L   # minimum positive-outcome focals to attempt estimation in a cell
cat(sprintf("\n=== (c) S3 zD within region (cells with npos>=%d only) ===\n", MIN_POS))
cat(sprintf("  %-14s %-9s %-20s %9s %9s %10s %9s %5s %5s\n",
            "region","era","domain","beta","SE","p_bloc","p_2way","N","npos"))
for (rg in c("British_Isles","Continental")) for (er in c("pre1215","post1215")) {
  f <- feas[[paste(rg,er)]]
  for (dom in DOMS2) {
    np <- if (dom=="secular_territorial") f$np_s else f$np_t
    if (np < MIN_POS) {
      cat(sprintf("  %-14s %-9s %-20s   SKIPPED: only %d focals with >0 appearances -- too few to estimate\n",
                  rg, er, dom, np))
      keep("c_region", "S3 zD SKIPPED(too few npos)", paste0(rg,"_",er), dom,
           list(beta=NA_real_, SE=NA_real_, p_bloc=NA_real_, p_2way=NA_real_, N=nrow(f$d)))
      next
    }
    m <- fit_s3(f$d, paste0("dom_",dom)); g <- grab(m, "zD")
    keep("c_region", "S3 zD", paste0(rg,"_",er), dom, g)
    cat(sprintf("  %-14s %-9s %-20s %9.4f %9.4f %10.2g %9.4f %5d %5d\n",
                rg, er, dom, g$beta, g$SE, g$p_bloc, g$p_2way, g$N, np))
  }
}

# ---- persist ----
R <- rbindlist(RES)
fwrite(R, file.path(OUTDIR,"clean_iv","reg_unified_exposure_break.csv"))
cat(sprintf("\nWrote %s (%d rows)\n",
    file.path(OUTDIR,"clean_iv","reg_unified_exposure_break.csv"), nrow(R)))

# ---- cross-check vs 111's stored S3 rows (should match ALL/EMFP/post) ----
p111 <- file.path(OUTDIR,"clean_iv","reg_peer_rf_domains.csv")
if (file.exists(p111)) {
  chk <- fread(p111)[spec=="S3 adoption" & domain %in% DOMS2, .(era,domain,beta,p_bloc)]
  cat("\n111 stored S3 rows (cross-check; B1215 pre/post should match EMFP/post):\n"); print(chk)
}
