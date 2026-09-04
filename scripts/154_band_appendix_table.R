#!/usr/bin/env Rscript
# 154_band_appendix_table.R
# =========================
# Emits the ally/rival band table promised in the peer section: the two peer
# exposures recomputed within graph-distance bands of the focal's pre-natal
# kin (ally 1-2 hops; rival 3-4, the modal dispute distance; rival 3-7),
# secular-territorial and total outcomes, by era. Reads the emitted CSVs of
# scripts 141 (reg_band_main.csv) and 144 (reg_band34_battery.csv); no new
# estimation.
# Output: tables/tab_app_bands.tex
# Usage:  Rscript 154_band_appendix_table.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
suppressPackageStartupMessages(library(data.table))

m  <- fread(file.path(ROOT, "output", "clean_iv", "reg_band_main.csv"))
b4 <- fread(file.path(ROOT, "output", "clean_iv", "reg_band34_battery.csv"))

grab <- function(dt, sp, tr, er, dom) {
  r <- dt[spec == sp & term == tr & era == er & domain == dom]
  if (nrow(r) == 0) return(c(NA_real_, NA_real_, NA_real_))
  c(r$beta[1], r$p_bloc[1], r$p_2way[1])
}
fp <- function(p) ifelse(is.na(p), "--", ifelse(p < 0.001, "$<$.001", sub("^0", "", sprintf("%.3f", p))))
fb <- function(b) ifelse(is.na(b), "--", sprintf("%.3f", b))

row6 <- function(lab, dt, sp, tr, dom) {
  e <- grab(dt, sp, tr, "EMFP", dom); p <- grab(dt, sp, tr, "post", dom)
  sprintf("%s & %s & %s & %s & %s & %s & %s \\\\", lab,
          fb(e[1]), fp(e[2]), fp(e[3]), fb(p[1]), fp(p[2]), fp(p[3]))
}

L <- c(
"\\begin{table}[t]", "\\centering",
"\\caption{The peer exposures by graph-distance band. Each cell is a separate OLS regression of $\\log(1+\\text{appearances})$ on the banded exposure (standardized by its full-sample SD), with the full battery, own reach, and bloc, death-decade, and title-rank fixed effects. The ally band recomputes each exposure over pre-natal kin at one and two hops of the focal; the rival bands over kin at three-to-four hops (the modal distance between matched disputants) and three-to-seven hops. $N = 1{,}073$ (born $\\leq$1215) and $1{,}106$ (born $>$1215).}",
"\\label{tab:app_bands}", "{\\small", "\\begin{tabular}{lcccccc}", "\\toprule",
" & \\multicolumn{3}{c}{Born $\\leq 1215$} & \\multicolumn{3}{c}{Born $> 1215$} \\\\",
"\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}",
"Band & $\\beta$ & $p$ & $p_{\\text{2w}}$ & $\\beta$ & $p$ & $p_{\\text{2w}}$ \\\\",
"\\midrule",
"\\multicolumn{7}{l}{\\textit{Panel A: peer arbitration share, secular-territorial outcome}} \\\\ \\addlinespace",
row6("Ally band (1--2 hops)",  m,  "ALLY",           "z_ally_ss",    "secular_territorial"),
row6("Rival band (3--4 hops)", b4, "B34 RD primary", "z_rival_ss34", "secular_territorial"),
row6("Rival band (3--7 hops)", m,  "RD primary",     "z_rival_ss",   "secular_territorial"),
"\\addlinespace",
"\\multicolumn{7}{l}{\\textit{Panel B: peer arbitration share, all documents}} \\\\ \\addlinespace",
row6("Ally band (1--2 hops)",  m,  "ALLY",           "z_ally_ss",    "total"),
row6("Rival band (3--4 hops)", b4, "B34 RD primary", "z_rival_ss34", "total"),
row6("Rival band (3--7 hops)", m,  "RD primary",     "z_rival_ss",   "total"),
"\\addlinespace",
"\\multicolumn{7}{l}{\\textit{Panel C: peer breadth, secular-territorial outcome}} \\\\ \\addlinespace",
row6("Ally band (1--2 hops)",  m,  "ALLY",           "z_ally_br",    "secular_territorial"),
row6("Rival band (3--4 hops)", b4, "B34 RB primary", "z_rival_br34", "secular_territorial"),
row6("Rival band (3--7 hops)", m,  "RB primary",     "z_rival_br",   "secular_territorial"),
"\\addlinespace",
"\\multicolumn{7}{l}{\\textit{Panel D: peer breadth, all documents}} \\\\ \\addlinespace",
row6("Ally band (1--2 hops)",  m,  "ALLY",           "z_ally_br",    "total"),
row6("Rival band (3--4 hops)", b4, "B34 RB primary", "z_rival_br34", "total"),
row6("Rival band (3--7 hops)", m,  "RB primary",     "z_rival_br",   "total"),
"\\midrule",
"\\multicolumn{7}{p{0.92\\textwidth}}{\\footnotesize \\textit{Notes:} $p$ clusters on bloc; $p_{\\text{2w}}$ on bloc and death-decade. The rival 3--4 band results survive the family-history battery, dropping Frederick~II, and (for the prohibition-era arbitration share) strengthen when the largest bloc is dropped; the 3--5 band gives qualitatively identical results (scripts 141/144 of the replication package). The wide 3--7 band dilutes the modal-dispute-distance kin with hop-6--7 kin who are rarely opponents, and its exposures lose significance accordingly.} \\\\",
"\\bottomrule", "\\end{tabular}", "}", "\\end{table}")

writeLines(L, file.path(ROOT, "tables", "tab_app_bands.tex"))
cat("wrote tables/tab_app_bands.tex\n")
