#!/usr/bin/env Rscript
# 114_emit_peer_tables.R
# ======================
# Emit the two Prediction-2 paper tables from 111's output (replaces the
# superseded tab_peer_domains 2SLS table):
#   tables/tab_peer_rf.tex   - peer breadth (composite RF), by era x domain,
#                              primary spec + family-battery spec side by side
#   tables/tab_peer_flip.tex - the adoption companion's era flip (pre-dated
#                              peer dispute share), EMFP vs post
# Usage:  Rscript 114_emit_peer_tables.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
suppressPackageStartupMessages(library(data.table))
R <- fread(file.path(ROOT, "output", "clean_iv", "reg_peer_rf_domains.csv"))
dir.create(file.path(ROOT, "tables"), showWarnings = FALSE)

ORD <- c("secular_territorial","ecclesiastical_appointments","crusade","other",
         "excommunication","ecclesiastical_property","inheritance","marriage","total")
LAB <- c(secular_territorial="Secular-territorial", ecclesiastical_appointments="Ecclesiastical appointments",
         crusade="Crusade", other="Other (heresy, diplomacy)", excommunication="Excommunication",
         ecclesiastical_property="Ecclesiastical property", inheritance="Inheritance",
         marriage="Marriage", total="All documents")
fm <- function(v, d=3) formatC(v, format="f", digits=d)
fp <- function(p) ifelse(is.na(p), "--", ifelse(p < 0.001, "$<$0.001", fm(p, 3)))
cell <- function(r) if (nrow(r) == 0 || is.na(r$beta)) "-- & -- & -- & --" else
  sprintf("%s & %s & %s & %s", fm(r$beta), fm(r$SE), fp(r$p_bloc), fp(r$p_2way))

# ---------------- tab_peer_rf: breadth (zB) ----------------
lines <- c("\\begin{table}[!t]", "\\centering",
  "\\caption{The peer channel: birth-network breadth and papal appearance, by subject domain. Each cell is a separate OLS regression of $\\log(1+\\text{appearances})$ in that domain on the focal's peer breadth (standardized), with the full ancestor battery, the focal's own kin-reach, and bloc, death-decade, and title-rank fixed effects. The model provides no valid instrument for the peer channel (Proposition~\\ref{p:channels} gives peer exogamy a direct ambient-risk path), so these are reduced-form estimates of the composite peer effect.}",
  "\\label{tab:peer_rf}", "{\\small", "\\begin{tabular}{lcccccccc}", "\\toprule",
  " & \\multicolumn{4}{c}{Primary} & \\multicolumn{4}{c}{+ family court history} \\\\",
  "\\cmidrule(lr){2-5}\\cmidrule(lr){6-9}",
  "Domain & $\\beta$ & SE & $p$ & $p_{\\text{2w}}$ & $\\beta$ & SE & $p$ & $p_{\\text{2w}}$ \\\\")
for (e in c("EMFP", "post")) {
  n1 <- R[era == e & spec == "S1 primary" & domain == "total", N][1]
  hdr <- if (e == "EMFP") "born under the prohibition ($\\leq 1215$)" else "born after the rollback ($> 1215$)"
  lines <- c(lines, "\\midrule",
    sprintf("\\multicolumn{9}{l}{\\textit{Panel %s: %s}; $N = %s$} \\\\ \\addlinespace",
            ifelse(e == "EMFP", "A", "B"), hdr, format(n1, big.mark = ",")))
  for (dom in ORD) {
    r1 <- R[era == e & spec == "S1 primary" & domain == dom]
    r2 <- R[era == e & spec == "S2 family" & domain == dom]
    nm <- LAB[dom]
    row <- sprintf("%s & %s & %s \\\\", nm, cell(r1), cell(r2))
    if (dom == "secular_territorial") row <- sprintf("\\textbf{%s} & %s & %s \\\\", nm, cell(r1), cell(r2))
    lines <- c(lines, row)
  }
}
lines <- c(lines, "\\midrule",
  "\\multicolumn{9}{p{0.96\\textwidth}}{\\footnotesize \\textit{Notes:} Peer breadth = the mean, over the focal's pre-natal four-hop kin, of each kin's one-hop distinct-bloc count over neighbours born before the focal; fixed at the focal's birth and standardized by the full-sample SD. Family court history = father's dispute appearances plus patriline court-use indices over five ancestral generations. $p$ clusters on bloc (38); $p_{\\text{2w}}$ on bloc and death-decade (underpowered within era: both cluster dimensions shrink). The prohibition-era secular-territorial estimate survives a restricted wild-cluster bootstrap ($p=.047$, $B=9{,}999$); randomization inference (treatment permuted within bloc$\\times$decade cells, 999 draws) gives $p=.065$ (secular-territorial) and $p=.020$ (all documents) in the prohibition era and $p=.003$ post.} \\\\",
  "\\bottomrule", "\\end{tabular}", "}", "\\end{table}")
writeLines(lines, file.path(ROOT, "tables", "tab_peer_rf.tex"))

# ---------------- tab_peer_flip: adoption companion (zD) ----------------
lines <- c("\\begin{table}[!t]", "\\centering",
  "\\caption{The arbitration companion and the 1215 rollback. Each cell is a separate OLS regression of $\\log(1+\\text{appearances})$ in that domain on the focal's peer arbitration share (standardized) --- the share of his pre-natal kin appearing in secular-territorial letters dated before his birth --- with the same controls as Table~\\ref{tab:peer_rf}.}",
  "\\label{tab:peer_flip}", "{\\small", "\\begin{tabular}{lcccccccc}", "\\toprule",
  " & \\multicolumn{4}{c}{Born $\\leq 1215$} & \\multicolumn{4}{c}{Born $> 1215$} \\\\",
  "\\cmidrule(lr){2-5}\\cmidrule(lr){6-9}",
  "Domain & $\\beta$ & SE & $p$ & $p_{\\text{2w}}$ & $\\beta$ & SE & $p$ & $p_{\\text{2w}}$ \\\\", "\\midrule")
for (dom in ORD) {
  r1 <- R[era == "EMFP" & spec == "S3 adoption" & domain == dom]
  r0 <- R[era == "post" & spec == "S3 adoption" & domain == dom]
  nm <- LAB[dom]
  row <- sprintf("%s & %s & %s \\\\", nm, cell(r1), cell(r0))
  if (dom == "secular_territorial") row <- sprintf("\\textbf{%s} & %s & %s \\\\", nm, cell(r1), cell(r0))
  lines <- c(lines, row)
}
n1 <- R[era == "EMFP" & spec == "S3 adoption" & domain == "total", N][1]
n0 <- R[era == "post" & spec == "S3 adoption" & domain == "total", N][1]
lines <- c(lines, "\\midrule",
  sprintf("$N$ & \\multicolumn{4}{c}{%s} & \\multicolumn{4}{c}{%s} \\\\", format(n1, big.mark=","), format(n0, big.mark=",")),
  "\\midrule",
  "\\multicolumn{9}{p{0.9\\textwidth}}{\\footnotesize \\textit{Notes:} $p$ clusters on bloc; $p_{\\text{2w}}$ on bloc and death-decade (within each era both cluster dimensions shrink, so the two-way test is demanding --- and it deflates most in domains where few blocs carry any outcome, e.g.\\ five of 38 for prohibition-era appointments, where the bloc-clustered SE is likely understated). The sign reversal at 1215 --- positive while the marriage prohibition bound and the cascade ran, negative after the rollback --- is robust to recomputing the share over matchable peers only and to controlling the matchable share (censoring appendix), and holds under design-based randomization inference (treatment permuted within bloc$\\times$decade cells, 999 draws): secular-territorial $p=.002$ in the prohibition era, $p=.001$ after. Peer breadth and the arbitration share are nearly orthogonal ($r=0.09$) and each retains its coefficient when both enter together.} \\\\",
  "\\bottomrule", "\\end{tabular}", "}", "\\end{table}")
writeLines(lines, file.path(ROOT, "tables", "tab_peer_flip.tex"))
cat("wrote tab_peer_rf.tex, tab_peer_flip.tex\n")
