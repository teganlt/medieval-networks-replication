# 144_band34_battery.R
# ====================
# Rival band at 3-4 hops (8/22): the modal dispute distance (134: mean 3.7,
# median 4). Reruns the 141 main cells + gates on the 3-4 band exposures
# (and the 3-5 band, 84% of dispute mass) from the rebuilt 140 output.
# Spec identical to 141: unified battery + own reach, bloc/decade/title FE
# as factors, cluster bloc, two-way reported, era split at born <= 1215,
# exposures standardized on the full sample. Within-era log band size is
# included in the size gate (era split => size x era by construction).
#
# Out: output/clean_iv/reg_band34_battery.csv, reg_band34_break.csv,
#      reg_band34_oster.csv
# CLI: Rscript scripts/144_band34_battery.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
bd <- fread(file.path(OUTDIR, "clean_iv", "band_exposures.csv"))
fam <- fread(file.path(OUTDIR, "clean_iv", "reg_complementarity_iv_df_sat2.csv"))[
  , .(person_id, fa_ldisp, pat_disp_anc, pat_secterr_anc, n_pat_anc)]
df <- merge(df, bd, by = "person_id")
df <- merge(df, fam, by = "person_id", all.x = TRUE)
for (c in c("fa_ldisp", "pat_disp_anc", "pat_secterr_anc", "n_pat_anc")) df[is.na(get(c)), (c) := 0]
df <- df[!is.na(rival_br34) & !is.na(rival_ss34)]
df[, EMFP := as.integer(birth <= 1215)]
zs <- function(x) (x - mean(x, na.rm = TRUE)) / sd(x, na.rm = TRUE)
for (v in c("rival_br34","rival_ss34","rival_br35","rival_ss35","rival_br","rival_ss"))
  df[, (paste0("z_", v)) := zs(get(v))]
df[, `:=`(ls34 = log1p(n_r34), ls35 = log1p(n_r35))]

cat(sprintf("N=%d  EMFP=%d/post=%d\n", nrow(df), sum(df$EMFP==1), sum(df$EMFP==0)))
cat(sprintf("cor(zRB34,zRD34)=%.3f  cor(zRB34, 3-7 flat zRB)=%.3f  cor(zRB34, own reach)=%.3f\n",
            cor(df$z_rival_br34, df$z_rival_ss34), cor(df$z_rival_br34, df$z_rival_br),
            cor(df$z_rival_br34, df$n_dyn_4hop)))
cat(sprintf("band sizes: n_r34 med=%d  n_r37 med=%d (3-4 band = %.0f%% of 3-7 members)\n",
            as.integer(median(df$n_r34)), as.integer(median(df$n_r37)),
            100 * median(df$n_r34 / pmax(df$n_r37, 1))))

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
fe <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
BAT <- paste(c(fe, anc, "f_extra4"), collapse = " + ")
FAM <- "fa_ldisp + pat_disp_anc + pat_secterr_anc + n_pat_anc"

pull <- function(m, term, twoway = FALSE) {
  if (is.null(m)) return(c(NA_real_, NA_real_, NA_real_))
  s <- if (twoway) tryCatch(summary(m, vcov = ~dynasty + death_decade), error = function(e) NULL) else m
  if (is.null(s)) return(c(NA_real_, NA_real_, NA_real_))
  ct <- as.data.frame(coeftable(s)); ct$t <- rownames(ct)
  pcol <- intersect(c("Pr(>|t|)", "Pr(>|z|)"), names(ct))[1]
  r <- ct[ct$t == term, ]
  if (nrow(r) == 0) c(NA_real_, NA_real_, NA_real_) else c(r$Estimate, r$`Std. Error`, r[[pcol]])
}
res <- list()
run <- function(d, rhs, terms, tag, era, dom) {
  m <- tryCatch(feols(as.formula(paste0(".y ~ ", rhs)), data = d, cluster = ~dynasty), error = function(e) NULL)
  for (tr in terms) {
    b <- pull(m, tr, FALSE); b2 <- pull(m, tr, TRUE)
    res[[length(res)+1]] <<- data.table(era = era, domain = dom, spec = tag, term = tr,
      beta = b[1], SE = b[2], p_bloc = b[3], p_2way = b2[3],
      N = if (is.null(m)) NA_integer_ else nobs(m))
  }
}

for (ev in list(c("EMFP",1L), c("post",0L))) {
  d0 <- df[EMFP == as.integer(ev[[2]])]
  for (dom in c("secular_territorial", "total")) {
    d <- copy(d0); d[, .y := log1p(get(paste0("dom_", dom)))]
    e <- ev[[1]]
    run(d, sprintf("z_rival_br34 + n_dyn_4hop + %s", BAT), "z_rival_br34", "B34 RB primary", e, dom)
    run(d, sprintf("z_rival_ss34 + n_dyn_4hop + %s", BAT), "z_rival_ss34", "B34 RD primary", e, dom)
    run(d, sprintf("z_rival_br34 + z_rival_ss34 + n_dyn_4hop + %s", BAT),
        c("z_rival_br34","z_rival_ss34"), "B34 joint", e, dom)
    run(d, sprintf("z_rival_br34 + z_rival_ss34 + n_dyn_4hop + ls34 + %s", BAT),
        c("z_rival_br34","z_rival_ss34"), "B34 size", e, dom)
    run(d, sprintf("z_rival_br34 + z_rival_ss34 + n_dyn_4hop + %s + %s", FAM, BAT),
        c("z_rival_br34","z_rival_ss34"), "B34 family", e, dom)
    run(d[dynasty != "B3"], sprintf("z_rival_br34 + z_rival_ss34 + n_dyn_4hop + %s", BAT),
        c("z_rival_br34","z_rival_ss34"), "B34 drop-B3", e, dom)
    run(d[person_id != "p10223.htm#i102226"], sprintf("z_rival_br34 + z_rival_ss34 + n_dyn_4hop + %s", BAT),
        c("z_rival_br34","z_rival_ss34"), "B34 drop-Fred", e, dom)
    run(d, sprintf("z_rival_br35 + z_rival_ss35 + n_dyn_4hop + ls35 + %s", BAT),
        c("z_rival_br35","z_rival_ss35"), "B35 size", e, dom)
    run(d, sprintf("z_rival_br35 + z_rival_ss35 + n_dyn_4hop + %s", BAT),
        c("z_rival_br35","z_rival_ss35"), "B35 joint", e, dom)
  }
}
fwrite(rbindlist(res), file.path(OUTDIR, "clean_iv", "reg_band34_battery.csv"))

## break-year sweep + donut on the 3-4 dispute-share exposure (secterr)
res_brk <- list()
for (cut in c(1195, 1205, 1215, 1225, 1235)) {
  for (side in c("pre", "post")) {
    d <- if (side == "pre") df[birth <= cut] else df[birth > cut]
    d[, .y := log1p(dom_secular_territorial)]
    m <- tryCatch(feols(as.formula(sprintf(".y ~ z_rival_ss34 + n_dyn_4hop + %s", BAT)), data = d, cluster = ~dynasty), error = function(e) NULL)
    b <- pull(m, "z_rival_ss34", FALSE)
    res_brk[[length(res_brk)+1]] <- data.table(split = cut, side = side, beta = b[1], SE = b[2], p_bloc = b[3],
      N = if (is.null(m)) NA_integer_ else nobs(m))
  }
}
dn <- df[birth < 1205 | birth > 1225]
for (side in c("pre", "post")) {
  d <- if (side == "pre") dn[birth <= 1215] else dn[birth > 1215]
  d[, .y := log1p(dom_secular_territorial)]
  m <- tryCatch(feols(as.formula(sprintf(".y ~ z_rival_ss34 + n_dyn_4hop + %s", BAT)), data = d, cluster = ~dynasty), error = function(e) NULL)
  b <- pull(m, "z_rival_ss34", FALSE)
  res_brk[[length(res_brk)+1]] <- data.table(split = NA_integer_, side = paste0("donut-", side), beta = b[1], SE = b[2], p_bloc = b[3],
    N = if (is.null(m)) NA_integer_ else nobs(m))
}
fwrite(rbindlist(res_brk), file.path(OUTDIR, "clean_iv", "reg_band34_break.csv"))

## Oster (secterr, per exposure x era)
wr2 <- function(m) {
  v <- tryCatch(fixest::r2(m, "wr2"), error = function(e) NA_real_)
  if (is.na(v)) v <- tryCatch(fixest::r2(m, "r2"), error = function(e) NA_real_)
  v
}
res_ost <- list()
for (ev in list(c("EMFP",1L), c("post",0L))) {
  d <- df[EMFP == as.integer(ev[[2]])]; d[, .y := log1p(dom_secular_territorial)]
  for (tr in c("z_rival_br34", "z_rival_ss34")) {
    ms <- feols(as.formula(sprintf(".y ~ %s + n_dyn_4hop + %s", tr, BAT)), data = d, cluster = ~dynasty)
    ml <- feols(as.formula(sprintf(".y ~ %s + n_dyn_4hop + %s + %s", tr, FAM, BAT)), data = d, cluster = ~dynasty)
    bs <- coef(ms)[tr]; bl <- coef(ml)[tr]; Rs <- wr2(ms); Rl <- wr2(ml)
    rmx <- min(1.3 * Rl, 1)
    dstar <- bl * (Rl - Rs) / ((bs - bl) * (rmx - Rl))
    bstar <- bl - (bs - bl) * (rmx - Rl) / (Rl - Rs)
    res_ost[[length(res_ost)+1]] <- data.table(era = ev[[1]], term = tr, beta_short = bs, beta_long = bl,
      R2_short = Rs, R2_long = Rl, Rmax = rmx, delta_star = dstar, beta_star = bstar,
      robust = (dstar >= 1 | dstar < 0))
  }
}
fwrite(rbindlist(res_ost), file.path(OUTDIR, "clean_iv", "reg_band34_oster.csv"))

R <- rbindlist(res)
cat("\n=== 3-4 BAND: secterr ===\n"); print(R[domain == "secular_territorial"], digits = 3)
cat("\n=== 3-4 BAND: total ===\n");   print(R[domain == "total"], digits = 3)
cat("\n=== BREAK SWEEP (zRD34 secterr) ===\n"); print(rbindlist(res_brk), digits = 3)
cat("\n=== OSTER ===\n"); print(rbindlist(res_ost), digits = 3)
cat("\nWrote reg_band34_battery / _break / _oster .csv\n")
