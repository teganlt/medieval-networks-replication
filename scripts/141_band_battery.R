# 141_band_battery.R
# ==================
# PREDICTION 2, REFORMULATED (8/21): main grids + full battery for the
# rival-band exposures of 140. Spec = 111's (unified battery + own reach,
# bloc/decade/title FE as factors, cluster bloc, two-way reported), era split
# at born <= 1215, exposures standardized on the full sample.
#
# Outputs (output/clean_iv/):
#   reg_band_main.csv     domain grid x era: zRB primary/family, zRD primary,
#                         joint zRB+zRD, ally falsification (secterr/total)
#   reg_band_battery.csv  gates: size, family, censoring, boundary, count,
#                         exposure, no-reach, drop-B3, drop-Frederick,
#                         Continental-only  (secterr + total, both eras)
#   reg_band_break.csv    break-year sweep 1195-1235 + donut (zRD, secterr)
#   reg_band_oster.csv    Oster delta* (zRB, zRD x era, secterr)
# CLI: Rscript scripts/141_band_battery.R [<ROOT>]

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
df <- df[!is.na(rival_br) & !is.na(rival_ss) & !is.na(ally_br)]
df[, EMFP := as.integer(birth <= 1215)]
df[, yrs_win := pmax(0, pmin(death, 1300) - pmax(birth, 1100))]
zs <- function(x) (x - mean(x, na.rm = TRUE)) / sd(x, na.rm = TRUE)
for (v in c("rival_br","rival_ss","rival_cnt","rival_cntw","rival_ss_m","ally_br","ally_ss",
            "rival_br27","rival_ss27","rival_br47","rival_ss47","rival_br_pw","rival_ss_pw"))
  df[, (paste0("z_", v)) := zs(get(v))]
df[, `:=`(lsA = log1p(n_a12), lsR = log1p(n_r37), ls27 = log1p(n_r27), ls47 = log1p(n_r47))]

# Continental classification (119's recipe)
pers <- fread(file.path(OUTDIR, "persons_imputed.csv"))[, .(id, birth_p = suppressWarnings(as.numeric(birth)))]
pb <- fread(file.path(OUTDIR, "patriline_bloc_assignment.csv"))[, .(id, bloc_pb = dynasty)]
ndl <- fread(file.path(OUTDIR, "named_dynasty_assignment.csv"))[, .(id, lab = dynasty)]
mem <- merge(pb, pers, by = "id", all.x = TRUE)[!is.na(birth_p) & birth_p >= 800 & birth_p <= 1500]
mem <- merge(mem, ndl, by = "id", all.x = TRUE)
dom_lab <- mem[!is.na(lab) & lab != "", .N, by = .(bloc_pb, lab)][order(bloc_pb, -N)][
  , .(dom_label = lab[1]), by = bloc_pb]
BI <- c("Alba_Scottish", "West_Saxon", "Welsh_Dinefwr")
df <- merge(df, dom_lab, by.x = "dynasty", by.y = "bloc_pb", all.x = TRUE)
df[, continental := !(dynasty == "B48" | dom_label %in% BI)]

cat(sprintf("N=%d  EMFP=%d/post=%d  Continental=%d\n", nrow(df), sum(df$EMFP==1), sum(df$EMFP==0), sum(df$continental)))
cat(sprintf("cor(zRB,zRD)=%.3f  cor(zRB, own reach)=%.3f  SD raw: rival_br=%.4f rival_ss=%.4f\n",
            cor(df$z_rival_br, df$z_rival_ss), cor(df$z_rival_br, df$n_dyn_4hop),
            sd(df$rival_br), sd(df$rival_ss)))

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
fe <- c("factor(title_rank)","factor(death_decade)","factor(dynasty)")
BAT <- paste(c(fe, anc, "f_extra4"), collapse = " + ")
FAM <- "fa_ldisp + pat_disp_anc + pat_secterr_anc + n_pat_anc"
DOMS <- c("secular_territorial","ecclesiastical_appointments","crusade","other",
          "excommunication","ecclesiastical_property","inheritance","marriage","total")

pull <- function(m, term, twoway = FALSE) {
  if (is.null(m)) return(c(NA_real_, NA_real_, NA_real_))
  s <- if (twoway) tryCatch(summary(m, vcov = ~dynasty + death_decade), error = function(e) NULL) else m
  if (is.null(s)) return(c(NA_real_, NA_real_, NA_real_))
  ct <- as.data.frame(coeftable(s)); ct$t <- rownames(ct)
  pcol <- intersect(c("Pr(>|t|)", "Pr(>|z|)"), names(ct))[1]
  r <- ct[ct$t == term, ]
  if (nrow(r) == 0) c(NA_real_, NA_real_, NA_real_) else c(r$Estimate, r$`Std. Error`, r[[pcol]])
}
res_main <- list(); res_bat <- list()
run <- function(store, d, rhs, terms, tag, era, dom) {
  m <- tryCatch(feols(as.formula(paste0(".y ~ ", rhs)), data = d, cluster = ~dynasty), error = function(e) NULL)
  for (tr in terms) {
    b <- pull(m, tr, FALSE); b2 <- pull(m, tr, TRUE)
    row <- data.table(era = era, domain = dom, spec = tag, term = tr,
      beta = b[1], SE = b[2], p_bloc = b[3], p_2way = b2[3],
      N = if (is.null(m)) NA_integer_ else nobs(m))
    if (store == "main") res_main[[length(res_main)+1]] <<- row else res_bat[[length(res_bat)+1]] <<- row
  }
}

## ================= MAIN GRID =================
for (ev in list(c("EMFP",1L), c("post",0L))) {
  d0 <- df[EMFP == as.integer(ev[[2]])]
  for (dom in DOMS) {
    d <- copy(d0); d[, .y := log1p(get(paste0("dom_", dom)))]
    run("main", d, sprintf("z_rival_br + n_dyn_4hop + %s", BAT), "z_rival_br", "RB primary", ev[[1]], dom)
    run("main", d, sprintf("z_rival_br + n_dyn_4hop + %s + %s", FAM, BAT), "z_rival_br", "RB family", ev[[1]], dom)
    run("main", d, sprintf("z_rival_ss + n_dyn_4hop + %s", BAT), "z_rival_ss", "RD primary", ev[[1]], dom)
    if (dom %in% c("secular_territorial", "total")) {
      run("main", d, sprintf("z_rival_br + z_rival_ss + n_dyn_4hop + %s", BAT),
          c("z_rival_br","z_rival_ss"), "JOINT", ev[[1]], dom)
      run("main", d, sprintf("z_ally_br + z_ally_ss + n_dyn_4hop + %s", BAT),
          c("z_ally_br","z_ally_ss"), "ALLY", ev[[1]], dom)
    }
  }
}

## ================= BATTERY (secterr + total) =================
for (ev in list(c("EMFP",1L), c("post",0L))) {
  d0 <- df[EMFP == as.integer(ev[[2]])]
  for (dom in c("secular_territorial", "total")) {
    d <- copy(d0); d[, .y := log1p(get(paste0("dom_", dom)))]
    e <- ev[[1]]
    run("bat", d, sprintf("z_rival_br + z_rival_ss + n_dyn_4hop + lsA + lsR + %s", BAT),
        c("z_rival_br","z_rival_ss"), "G size", e, dom)
    run("bat", d, sprintf("z_rival_br + z_rival_ss + n_dyn_4hop + %s + %s", FAM, BAT),
        c("z_rival_br","z_rival_ss"), "G family", e, dom)
    run("bat", d, sprintf("z_rival_br + z_rival_ss_m + n_dyn_4hop + m_a12 + m_r37 + %s", BAT),
        c("z_rival_br","z_rival_ss_m"), "G censor-m", e, dom)
    run("bat", d, sprintf("z_rival_br + z_rival_ss + n_dyn_4hop + m_a12 + m_r37 + %s", BAT),
        c("z_rival_br","z_rival_ss"), "G censor-ctl", e, dom)
    run("bat", d, sprintf("z_rival_br27 + z_rival_ss27 + n_dyn_4hop + ls27 + %s", BAT),
        c("z_rival_br27","z_rival_ss27"), "G band 2-7", e, dom)
    run("bat", d, sprintf("z_rival_br47 + z_rival_ss47 + n_dyn_4hop + ls47 + %s", BAT),
        c("z_rival_br47","z_rival_ss47"), "G band 4-7", e, dom)
    run("bat", d, sprintf("z_rival_br_pw + z_rival_ss_pw + n_dyn_4hop + %s", BAT),
        c("z_rival_br_pw","z_rival_ss_pw"), "G profile-wt", e, dom)
    run("bat", d, sprintf("z_rival_br + z_rival_cntw + n_dyn_4hop + %s", BAT),
        c("z_rival_cntw"), "G count-w10", e, dom)
    run("bat", d, sprintf("z_rival_br + z_rival_cnt + n_dyn_4hop + %s", BAT),
        c("z_rival_cnt"), "G count-raw", e, dom)
    run("bat", d, sprintf("z_rival_br + z_rival_ss + n_dyn_4hop + yrs_win + %s", BAT),
        c("z_rival_br","z_rival_ss"), "G exposure", e, dom)
    run("bat", d, sprintf("z_rival_br + z_rival_ss + %s", BAT),
        c("z_rival_br","z_rival_ss"), "G no-reach", e, dom)
    run("bat", d[dynasty != "B3"], sprintf("z_rival_br + z_rival_ss + n_dyn_4hop + %s", BAT),
        c("z_rival_br","z_rival_ss"), "G drop-B3", e, dom)
    run("bat", d[person_id != "p10223.htm#i102226"], sprintf("z_rival_br + z_rival_ss + n_dyn_4hop + %s", BAT),
        c("z_rival_br","z_rival_ss"), "G drop-Fred", e, dom)
    run("bat", d[continental == TRUE], sprintf("z_rival_br + z_rival_ss + n_dyn_4hop + %s", BAT),
        c("z_rival_br","z_rival_ss"), "G Continental", e, dom)
  }
}
fwrite(rbindlist(res_main), file.path(OUTDIR, "clean_iv", "reg_band_main.csv"))
fwrite(rbindlist(res_bat), file.path(OUTDIR, "clean_iv", "reg_band_battery.csv"))

## ================= BREAK-YEAR SWEEP + DONUT (zRD, secterr) =================
res_brk <- list()
for (cut in c(1195, 1205, 1215, 1225, 1235)) {
  for (side in c("pre", "post")) {
    d <- if (side == "pre") df[birth <= cut] else df[birth > cut]
    d[, .y := log1p(dom_secular_territorial)]
    m <- tryCatch(feols(as.formula(sprintf(".y ~ z_rival_ss + n_dyn_4hop + %s", BAT)), data = d, cluster = ~dynasty), error = function(e) NULL)
    b <- pull(m, "z_rival_ss", FALSE)
    res_brk[[length(res_brk)+1]] <- data.table(split = cut, side = side, beta = b[1], SE = b[2], p_bloc = b[3],
      N = if (is.null(m)) NA_integer_ else nobs(m))
  }
}
dn <- df[birth < 1205 | birth > 1225]
for (side in c("pre", "post")) {
  d <- if (side == "pre") dn[birth <= 1215] else dn[birth > 1215]
  d[, .y := log1p(dom_secular_territorial)]
  m <- tryCatch(feols(as.formula(sprintf(".y ~ z_rival_ss + n_dyn_4hop + %s", BAT)), data = d, cluster = ~dynasty), error = function(e) NULL)
  b <- pull(m, "z_rival_ss", FALSE)
  res_brk[[length(res_brk)+1]] <- data.table(split = NA_integer_, side = paste0("donut-", side), beta = b[1], SE = b[2], p_bloc = b[3],
    N = if (is.null(m)) NA_integer_ else nobs(m))
}
fwrite(rbindlist(res_brk), file.path(OUTDIR, "clean_iv", "reg_band_break.csv"))

## ================= OSTER (secterr, per exposure x era) =================
# factors-in-RHS models have no FE slot, so "wr2" is undefined; fall back to "r2"
wr2 <- function(m) {
  v <- tryCatch(fixest::r2(m, "wr2"), error = function(e) NA_real_)
  if (is.na(v)) v <- tryCatch(fixest::r2(m, "r2"), error = function(e) NA_real_)
  v
}
res_ost <- list()
for (ev in list(c("EMFP",1L), c("post",0L))) {
  d <- df[EMFP == as.integer(ev[[2]])]; d[, .y := log1p(dom_secular_territorial)]
  for (tr in c("z_rival_br", "z_rival_ss")) {
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
fwrite(rbindlist(res_ost), file.path(OUTDIR, "clean_iv", "reg_band_oster.csv"))

## ================= console summary =================
M <- rbindlist(res_main)
cat("\n=== MAIN: secterr + total ===\n")
print(M[domain %in% c("secular_territorial","total")], digits = 3)
cat("\n=== BATTERY (secterr) ===\n")
print(rbindlist(res_bat)[domain == "secular_territorial"], digits = 3)
cat("\n=== BREAK SWEEP (zRD secterr) ===\n")
print(rbindlist(res_brk), digits = 3)
cat("\n=== OSTER ===\n")
print(rbindlist(res_ost), digits = 3)
cat("\nWrote reg_band_main / _battery / _break / _oster .csv\n")
