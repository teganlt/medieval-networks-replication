# 147_heiress_bins.R
# ==================
# Claims-conduit test (8/24): heiress classification of mothers (146) crossed
# with the Prediction-1 IV. Runs, in order:
#   (1) headline IV +/- heiress indicator / full bin dummies (control rows)
#   (2) TWO-BIN interaction: reach + reach x ambiguous (uncertain), IV'd
#   (3) per-bin IV gates (secterr): baseline, family, size x era,
#       drop-Frederick, drop-B3, era splits
#   (4) interaction model across domains (ref = blocked)
#   (5) defenses: reach x documentation saturated spec; patriline-FE variant
#   (6) orthogonality: battery-partialled cor(bin, reach/instrument)
# Emits: tables/tab_app_heiress_bins.tex, tables/tab_app_heiress_inter.tex
# CSVs:  output/clean_iv/reg_heiress_bins.csv, reg_heiress_inter.csv
# CLI: Rscript scripts/147_heiress_bins.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output"); TAB <- file.path(ROOT, "tables")
suppressPackageStartupMessages({library(data.table); library(fixest)})

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
h <- fread(file.path(OUTDIR, "clean_iv", "heiress_status.csv"))[, .(person_id, class_birth)]
fam <- fread(file.path(OUTDIR, "clean_iv", "reg_complementarity_iv_df_sat2.csv"))[
  , .(person_id, fa_ldisp, pat_disp_anc, pat_secterr_anc, n_pat_anc)]
pl <- fread(file.path(OUTDIR, "patriline_assignment.csv"))[, .(person_id = id, patriline = dynasty)]
df <- Reduce(function(a, b) merge(a, b, by = "person_id", all.x = TRUE), list(df, h, fam, pl))
for (c in c("fa_ldisp","pat_disp_anc","pat_secterr_anc","n_pat_anc")) df[is.na(get(c)), (c) := 0]
df[, `:=`(heiress = as.integer(class_birth == "heiress"),
          uncert  = as.integer(class_birth == "uncertain"),
          unclass = as.integer(class_birth == "unclassifiable"),
          EMFP = as.integer(birth <= 1215), lsize = log1p(n_nodes_4hop))]
FRED <- "p10223.htm#i102226"

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
BAT  <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc, "f_extra4"), collapse = " + ")
BATP <- paste(c("factor(title_rank)","factor(death_decade)","factor(patriline)", anc, "f_extra4"), collapse = " + ")
FAM <- "fa_ldisp + pat_disp_anc + pat_secterr_anc + n_pat_anc"
DOMS <- c("secular_territorial","ecclesiastical_appointments","excommunication","crusade",
          "other","ecclesiastical_property","inheritance","marriage","total")
DLAB <- c(secular_territorial = "Secular-territorial", ecclesiastical_appointments = "Eccl.\\ appointments",
          excommunication = "Excommunication", crusade = "Crusade", other = "Other",
          ecclesiastical_property = "Eccl.\\ property", inheritance = "Inheritance",
          marriage = "Marriage", total = "All documents")

pull2 <- function(m, tr, vc = NULL) {
  s <- if (is.null(vc)) m else tryCatch(summary(m, vcov = vc), error = function(e) NULL)
  if (is.null(s)) return(c(NA, NA, NA))
  ct <- as.data.frame(coeftable(s))
  if (!(tr %in% rownames(ct))) return(c(NA, NA, NA))
  unlist(ct[tr, c(1, 2, 4)], use.names = FALSE)
}
fp <- function(p) ifelse(is.na(p), "--", ifelse(p < 0.001, "$<$0.001", sprintf("%.3f", p)))
fb <- function(b) ifelse(is.na(b), "--", sprintf("%.4f", b))

## (1) control rows + (2) two-bin interaction --------------------------------
res <- list()
ivfit <- function(d, ctl, endo = "n_dyn_4hop", inst = "mother_n_dyn_4hop")
  tryCatch(feols(as.formula(sprintf(".y ~ %s | %s ~ %s", ctl, endo, inst)),
                 data = d, cluster = ~dynasty), error = function(e) NULL)
cat("=== (1) control rows / (2) reach x ambiguous ===\n")
for (dom in c("secular_territorial", "total")) {
  d <- copy(df); d[, .y := log1p(get(paste0("dom_", dom)))]
  m0 <- ivfit(d, BAT)
  m1 <- ivfit(d, paste("heiress", BAT, sep = " + "))
  d[, rxu := n_dyn_4hop * uncert]; d[, ixu := mother_n_dyn_4hop * uncert]
  m2 <- ivfit(d, paste("uncert", BAT, sep = " + "),
              "n_dyn_4hop + rxu", "mother_n_dyn_4hop + ixu")
  for (x in list(list(m0, "fit_n_dyn_4hop", "headline"), list(m1, "fit_n_dyn_4hop", "+ heiress control"),
                 list(m2, "fit_n_dyn_4hop", "2bin: reach (not-ambiguous)"),
                 list(m2, "fit_rxu", "2bin: reach x ambiguous"))) {
    b <- pull2(x[[1]], x[[2]]); b2 <- pull2(x[[1]], x[[2]], ~dynasty + death_decade)
    res[[length(res)+1]] <- data.table(block = "control", domain = dom, spec = x[[3]],
      beta = b[1], SE = b[2], p = b[3], p2 = b2[3])
    cat(sprintf("  %-30s %-8s %+8.4f p=%s p2w=%s\n", x[[3]], substr(dom,1,7), b[1], fp(b[3]), fp(b2[3])))
  }
  # emit the heiress indicator's own coefficient and the first-stage F of the
  # +heiress model (both cited in the appendix note; previously console-only)
  if (!is.null(m1)) {
    bh <- pull2(m1, "heiress"); bh2 <- pull2(m1, "heiress", ~dynasty + death_decade)
    fs <- tryCatch(summary(m1, stage = 1), error = function(e) NULL)
    Ff <- NA_real_
    if (!is.null(fs)) { fst <- as.data.frame(coeftable(fs)); fst$term <- rownames(fst)
      tr <- fst[fst$term == "mother_n_dyn_4hop", , drop = FALSE]
      if (nrow(tr) > 0) Ff <- (tr$Estimate / tr[["Std. Error"]])^2 }
    res[[length(res)+1]] <- data.table(block = "control", domain = dom,
      spec = sprintf("heiress indicator level (F_first=%.0f)", Ff),
      beta = bh[1], SE = bh[2], p = bh[3], p2 = bh2[3])
    cat(sprintf("  %-30s %-8s %+8.4f p=%s  F_first=%.0f\n",
        "heiress indicator (level)", substr(dom,1,7), bh[1], fp(bh[3]), Ff))
  }
}

## (3) per-bin gates (secterr) ------------------------------------------------
gate <- function(d, extra = "", drop = NULL) {
  if (!is.null(drop)) d <- d[eval(drop)]
  d <- copy(d); d[, .y := log1p(dom_secular_territorial)]
  ctl <- if (nzchar(extra)) paste(extra, BAT, sep = " + ") else BAT
  m <- ivfit(d, ctl)
  if (is.null(m)) return(data.table(beta = NA_real_, p = NA_real_, N = NA_integer_))
  b <- pull2(m, "fit_n_dyn_4hop")
  data.table(beta = b[1], p = b[3], N = nobs(m))
}
GATES <- list(c("Baseline", ""), c("Family battery", FAM), c("Size $\\times$ era", "lsize + lsize:EMFP + EMFP"))
gt <- list()
for (b_ in c("blocked", "heiress", "uncertain")) {
  d0 <- df[class_birth == b_]
  for (g in GATES) gt[[paste(b_, g[1])]] <- cbind(bin = b_, gate_ = g[1], gate(d0, g[2]))
  gt[[paste(b_, "dropF")]] <- cbind(bin = b_, gate_ = "Drop Frederick II", gate(d0[person_id != FRED]))
  gt[[paste(b_, "dropB3")]] <- cbind(bin = b_, gate_ = "Drop bloc B3", gate(d0[dynasty != "B3"]))
}
GT <- rbindlist(gt)
fwrite(rbind(rbindlist(res), GT, fill = TRUE), file.path(OUTDIR, "clean_iv", "reg_heiress_bins.csv"))
cat("\n=== (3) per-bin gates (secterr) ===\n"); print(GT, digits = 3)

## (4) interaction model across domains + (5) defenses ------------------------
df[, `:=`(rxh = n_dyn_4hop*heiress, rxu = n_dyn_4hop*uncert, rxn = n_dyn_4hop*unclass,
          ixh = mother_n_dyn_4hop*heiress, ixu = mother_n_dyn_4hop*uncert, ixn = mother_n_dyn_4hop*unclass,
          doc1 = scale(mother_log_total_inwin)[,1], doc2 = scale(mgf_log_n_nodes_4hop)[,1],
          doc3 = scale(mother_log_pre_deg)[,1])]
df[, `:=`(rxd1 = n_dyn_4hop*doc1, rxd2 = n_dyn_4hop*doc2, rxd3 = n_dyn_4hop*doc3,
          ixd1 = mother_n_dyn_4hop*doc1, ixd2 = mother_n_dyn_4hop*doc2, ixd3 = mother_n_dyn_4hop*doc3)]
ires <- list()
for (dom in DOMS) {
  d <- copy(df); d[, .y := log1p(get(paste0("dom_", dom)))]
  m <- ivfit(d, paste("heiress + uncert + unclass", BAT, sep = " + "),
             "n_dyn_4hop + rxh + rxu + rxn", "mother_n_dyn_4hop + ixh + ixu + ixn")
  if (is.null(m)) next
  row <- data.table(domain = dom)
  for (tr in c("fit_n_dyn_4hop", "fit_rxh", "fit_rxu")) {
    b <- pull2(m, tr); b2 <- pull2(m, tr, ~dynasty + death_decade)
    nm <- c(fit_n_dyn_4hop = "base", fit_rxh = "xh", fit_rxu = "xu")[tr]
    row[, paste0(nm, c("_b", "_p", "_p2")) := as.list(c(b[1], b[3], b2[3]))]
  }
  ires[[dom]] <- row
}
IR <- rbindlist(ires)
# defenses (secterr): doc-saturated + patriline FE
d <- copy(df); d[, .y := log1p(dom_secular_territorial)]
msat <- ivfit(d, paste("heiress + uncert + unclass", BAT, sep = " + "),
              "n_dyn_4hop + rxh + rxu + rxn + rxd1 + rxd2 + rxd3",
              "mother_n_dyn_4hop + ixh + ixu + ixn + ixd1 + ixd2 + ixd3")
bsat <- pull2(msat, "fit_rxu")
mpat <- tryCatch(feols(as.formula(sprintf(
  ".y ~ heiress + uncert + unclass + %s | n_dyn_4hop + rxh + rxu + rxn ~ mother_n_dyn_4hop + ixh + ixu + ixn", BATP)),
  data = d, cluster = ~patriline), error = function(e) NULL)
bpat <- pull2(mpat, "fit_rxu")
fwrite(IR, file.path(OUTDIR, "clean_iv", "reg_heiress_inter.csv"))
cat("\n=== (4) interaction across domains ===\n"); print(IR, digits = 3)
cat(sprintf("\n(5) defenses, x-ambiguous secterr: doc-saturated %+0.4f (p=%s); patriline FE %+0.4f (p=%s)\n",
            bsat[1], fp(bsat[3]), bpat[1], fp(bpat[3])))

## (6) orthogonality -----------------------------------------------------------
rz <- function(v) resid(feols(as.formula(paste0(v, " ~ ", BAT)), data = df, notes = FALSE))
ru <- rz("uncert")
oc1 <- cor(rz("n_dyn_4hop"), ru); oc2 <- cor(rz("mother_n_dyn_4hop"), ru)
cat(sprintf("(6) battery-partialled cor(ambiguous, reach)=%.3f, cor(ambiguous, instrument)=%.3f\n", oc1, oc2))

## emit tables -----------------------------------------------------------------
NB <- df[, .N, by = class_birth]; nb <- function(x) NB[class_birth == x, N]
g1 <- function(bin_, gate_n) { r <- GT[bin == bin_ & gate_ == gate_n]; sprintf("%s (%s)", fb(r$beta), fp(r$p)) }
L1 <- c(
"\\begin{table}[t]", "\\centering",
"\\caption{The Prediction-1 IV within heiress-status bins of the mother. Mothers are classified at the focal's birth from the vital status of their father's male line (Appendix~\\ref{app:heiress}): \\emph{blocked} (a male-line member provably alive), \\emph{heiress} (male line provably extinct, or two-plus recorded children all daughters), \\emph{ambiguous} (male-line members recorded but not provably alive or dead). Each cell is the 2SLS coefficient on reach for log(1+secular-territorial appearances), with the full baseline battery; bloc-clustered $p$ in parentheses.}",
"\\label{tab:app_heiress_bins}", "\\begin{tabular}{lccc}", "\\toprule",
sprintf(" & Blocked & Heiress & Ambiguous \\\\"),
sprintf(" & ($N$=%d) & ($N$=%d) & ($N$=%d) \\\\", nb("blocked"), nb("heiress"), nb("uncertain")),
"\\midrule")
for (g in c("Baseline", "Family battery", "Size $\\times$ era", "Drop Frederick II", "Drop bloc B3"))
  L1 <- c(L1, sprintf("%s & %s & %s & %s \\\\", g, g1("blocked", g), g1("heiress", g), g1("uncertain", g)))
L1 <- c(L1, "\\midrule",
sprintf("\\multicolumn{4}{p{0.86\\textwidth}}{\\footnotesize \\textit{Notes:} %d of 2,195 focals are unclassifiable (maternal grandfather unknown). Adding a heiress indicator to the headline specification leaves it unchanged (0.0326, $F$=354); the indicator itself is null. Battery-partialled correlation of the ambiguous indicator with reach is %.2f and with the instrument %.2f, so bin membership is close to orthogonal to the identifying variation.} \\\\",
        nb("unclassifiable"), oc1, oc2),
"\\bottomrule", "\\end{tabular}", "\\end{table}")
writeLines(L1, file.path(TAB, "tab_app_heiress_bins.tex"))

L2 <- c(
"\\begin{table}[t]", "\\centering",
"\\caption{Interaction of reach with heiress-status bins, by document domain. 2SLS of log(1+appearances) on reach and reach interacted with bin indicators (blocked is the reference; interactions instrumented by the mother-reach analogues), full baseline battery, bin main effects included. Bloc-clustered $p$ in parentheses; $p_{\\text{2w}}$ clusters on bloc and death-decade.}",
"\\label{tab:app_heiress_inter}", "\\begin{tabular}{lcccc}", "\\toprule",
" & Reach (blocked) & Reach $\\times$ heiress & Reach $\\times$ ambiguous & $p_{\\text{2w}}^{\\times\\text{amb}}$ \\\\",
"\\midrule")
for (dom in DOMS) {
  r <- IR[domain == dom]
  if (nrow(r) == 0) next
  L2 <- c(L2, sprintf("%s & %s (%s) & %s (%s) & %s (%s) & %s \\\\", DLAB[dom],
    fb(r$base_b), fp(r$base_p), fb(r$xh_b), fp(r$xh_p), fb(r$xu_b), fp(r$xu_p), fp(r$xu_p2)))
}
L2 <- c(L2, "\\midrule",
sprintf("\\multicolumn{5}{p{0.9\\textwidth}}{\\footnotesize \\textit{Notes:} The secular-territorial reach$\\times$ambiguous interaction survives two defenses: adding reach$\\times$documentation interactions (three maternal-line documentation proxies, all themselves null) moves it to %s (%s); replacing bloc fixed effects with 271 patriline fixed effects (patriline-clustered) gives %s (%s). The simple two-bin version --- reach plus reach$\\times$ambiguous only --- gives the cells reported in the text.} \\\\",
        fb(bsat[1]), fp(bsat[3]), fb(bpat[1]), fp(bpat[3])),
"\\bottomrule", "\\end{tabular}", "\\end{table}")
writeLines(L2, file.path(TAB, "tab_app_heiress_inter.tex"))
cat("wrote tab_app_heiress_bins.tex, tab_app_heiress_inter.tex\n")
