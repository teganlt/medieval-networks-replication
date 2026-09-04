#!/usr/bin/env Rscript
# 159_fe_variants_table.R  (v2 -- 8/31 redesign)
# =======================
# Two appendix tables of fixed-effect / clustering variants, every cell run
# fresh here so all four outcomes (secular-territorial, dispute, non-dispute,
# all documents) are covered:
#   Table A (tab_app_fe_headline.tex): the Pred-1 2SLS under three variants --
#     (1) bloc + death-decade FEs, bloc-clustered (baseline);
#     (2) bloc + birth-decade FEs, bloc-clustered;
#     (3) patriline + death-decade FEs, patriline-clustered.
#     Columns per outcome: beta, analytic p (row's own cluster dimension),
#     and two-way p (row's cluster dimension + its decade dimension).
#   Table B (tab_app_fe_peer.tex): the peer reduced forms (breadth zB and
#     arbitration share zD, by era) under the same three variants.
# CSVs: output/clean_iv/reg_unified_fe_variants.csv, reg_peer_fe_variants2.csv
ROOT <- if (length(commandArgs(trailingOnly=TRUE)) >= 1) commandArgs(trailingOnly=TRUE)[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
source(file.path(ROOT, "scripts", "clean_iv_common.R")); ic_load_shared()
H <- 4L

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
pa <- fread(file.path(OUTDIR, "patriline_assignment.csv"))[, .(person_id = id, patriline = dynasty)]
df <- merge(df, pa, by = "person_id")
df[, birth_decade := (birth %/% 10) * 10]
# dispute / non-dispute outcome counts (149's construction)
coded <- fread(file.path(OUTDIR, "matched_docs_coded.csv"), colClasses = list(character = "doc_id"))[, .(doc_id, is_dispute)]
mt <- fread(file.path(OUTDIR, "doc_matches_ai_extracted_high.csv"),
            colClasses = list(character = "doc_id"))[doc_year >= 1100 & doc_year <= 1300, .(person_id, doc_id)]
mt <- merge(mt, coded, by = "doc_id")
pc <- mt[, .(dom_dispute = sum(is_dispute == "yes"), dom_nondispute = sum(is_dispute == "no")), by = person_id]
df <- merge(df, pc, by = "person_id", all.x = TRUE)
for (cc in c("dom_dispute", "dom_nondispute")) df[is.na(get(cc)), (cc) := 0]

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
CORE <- paste(c("factor(title_rank)", anc, "f_extra4"), collapse = " + ")

pull <- function(m, term, vc = NULL) {
  if (is.null(m)) return(c(NA_real_, NA_real_))
  s <- if (is.null(vc)) m else tryCatch(summary(m, vcov = vc), error = function(e) NULL)
  if (is.null(s)) return(c(NA_real_, NA_real_))
  ct <- as.data.frame(coeftable(s)); ct$t <- rownames(ct)
  pcn <- intersect(c("Pr(>|t|)","Pr(>|z|)"), names(ct))[1]
  r <- ct[ct$t == term, ]; if (nrow(r)) c(r$Estimate, r[[pcn]]) else c(NA_real_, NA_real_)
}

VAR <- list(
  baseline  = list(fe = "factor(dynasty) + factor(death_decade)",   cl = ~dynasty,   v2 = ~dynasty + death_decade,   lab = "Baseline"),
  birthdec  = list(fe = "factor(dynasty) + factor(birth_decade)",   cl = ~dynasty,   v2 = ~dynasty + birth_decade,   lab = "Birth-decade clock"),
  patriline = list(fe = "factor(patriline) + factor(death_decade)", cl = ~patriline, v2 = ~patriline + death_decade, lab = "Patriline FEs"))
OUTC <- c(secular_territorial = "Secular-territorial", dispute = "Dispute",
          nondispute = "Non-dispute", total = "All documents")

## ---- Table A: headline 2SLS ----
A <- list()
for (vn in names(VAR)) {
  v <- VAR[[vn]]
  for (oc in names(OUTC)) {
    d <- copy(df); d[, .y := log1p(get(paste0("dom_", oc)))]
    m <- tryCatch(feols(as.formula(sprintf(".y ~ %s + %s | n_dyn_4hop ~ mother_n_dyn_4hop", CORE, v$fe)),
                        data = d, cluster = v$cl), error = function(e) NULL)
    b <- pull(m, "fit_n_dyn_4hop"); b2 <- pull(m, "fit_n_dyn_4hop", v$v2)
    A[[paste(vn, oc)]] <- data.table(variant = vn, outcome = oc, beta = b[1], p = b[2], p_2way = b2[2],
                                     N = if (is.null(m)) NA_integer_ else nobs(m))
    cat(sprintf("A %-10s %-20s beta=%.4f p=%.4f p2w=%.4f\n", vn, oc, b[1], b[2], b2[2]))
  }
}
A <- rbindlist(A); fwrite(A, file.path(OUTDIR, "clean_iv", "reg_unified_fe_variants.csv"))

## ---- Table B: peer reduced forms ----
pr <- fread(file.path(OUTDIR, "clean_iv", "peer_rf_build.csv"))[
  , .(person_id, EMFP_pr = EMFP, peer_nkin, peer_breadth_pre, peer_secterr_dated)]
dp <- merge(df, pr, by = "person_id"); dp <- dp[peer_nkin > 0]
dp[, zB := (peer_breadth_pre   - mean(peer_breadth_pre))   / sd(peer_breadth_pre)]
dp[, zD := (peer_secterr_dated - mean(peer_secterr_dated)) / sd(peer_secterr_dated)]
B <- list()
for (vn in names(VAR)) {
  v <- VAR[[vn]]
  for (er in c("EMFP", "post")) {
    d0 <- dp[EMFP_pr == as.integer(er == "EMFP")]
    for (oc in names(OUTC)) {
      d <- copy(d0); d[, .y := log1p(get(paste0("dom_", oc)))]
      for (tr in c("zB", "zD")) {
        m <- tryCatch(feols(as.formula(sprintf(".y ~ %s + %s + n_dyn_4hop + %s", tr, CORE, v$fe)),
                            data = d, cluster = v$cl), error = function(e) NULL)
        b <- pull(m, tr)
        B[[paste(vn, er, oc, tr)]] <- data.table(variant = vn, era = er, outcome = oc, term = tr,
          beta = b[1], p = b[2], N = if (is.null(m)) NA_integer_ else nobs(m))
      }
    }
  }
}
B <- rbindlist(B); fwrite(B, file.path(OUTDIR, "clean_iv", "reg_peer_fe_variants2.csv"))

## ---- emit ----
fp <- function(p) ifelse(is.na(p), "--", ifelse(p < 0.001, "$<$.001", sub("^0", "", sprintf("%.3f", p))))
fb <- function(b) ifelse(is.na(b), "--", sprintf("%.3f", b))

LA <- c("% ===== BEGIN tables/tab_app_fe_headline =====",
"\\begin{table}[t]", "\\centering",
"\\caption{The baseline 2SLS under alternative fixed effects and clustering. Each row keeps the full battery and re-estimates all four outcomes; $p$ is the analytic $p$ clustered on the row's group dimension (bloc or patriline), and $p_{\\text{2w}}$ clusters two-way on that dimension and the row's decade dimension. $N = 2{,}195$.}",
"\\label{tab:app_fe_headline}",
"{\\footnotesize\\setlength{\\tabcolsep}{3pt}", "\\begin{tabular}{lcccccccccccc}", "\\toprule",
" & \\multicolumn{3}{c}{Secular-territorial} & \\multicolumn{3}{c}{Dispute} & \\multicolumn{3}{c}{Non-dispute} & \\multicolumn{3}{c}{All documents} \\\\",
"\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\\cmidrule(lr){8-10}\\cmidrule(lr){11-13}",
"Specification & $\\beta$ & $p$ & $p_{\\text{2w}}$ & $\\beta$ & $p$ & $p_{\\text{2w}}$ & $\\beta$ & $p$ & $p_{\\text{2w}}$ & $\\beta$ & $p$ & $p_{\\text{2w}}$ \\\\",
"\\midrule")
for (vn in names(VAR)) {
  cells <- character(0)
  for (oc in names(OUTC)) { r <- A[variant == vn & outcome == oc]
    cells <- c(cells, fb(r$beta), fp(r$p), fp(r$p_2way)) }
  LA <- c(LA, paste(VAR[[vn]]$lab, "&", paste(cells, collapse = " & "), "\\\\"))
}
LA <- c(LA, "\\midrule",
"\\multicolumn{13}{p{0.96\\textwidth}}{\\footnotesize \\textit{Notes:} Row 1 is the baseline of Table~\\ref{tab:forward}. Row 2 swaps the fixed-effect clock to birth decade. Row 3 replaces bloc fixed effects with patriline fixed effects ($271$ male lines; identification within sets of brothers and cousins) and clusters at the patriline; its $p_{\\text{2w}}$ clusters on patriline and death-decade. Dispute and non-dispute aggregate the eight domains by the live-dispute flag.} \\\\",
"\\bottomrule", "\\end{tabular}", "}", "\\end{table}",
"% ===== END tables/tab_app_fe_headline =====")
writeLines(LA, file.path(ROOT, "tables", "tab_app_fe_headline.tex"))

cellBP <- function(vn, er, oc, tr) { r <- B[variant == vn & era == er & outcome == oc & term == tr]
  sprintf("%s (%s)", fb(r$beta), fp(r$p)) }
LB <- c("% ===== BEGIN tables/tab_app_fe_peer =====",
"\\begin{table}[t]", "\\centering",
"\\caption{The peer reduced forms under alternative fixed effects and clustering. Cells are $\\beta$ per full-sample SD of the exposure, with the analytic $p$ clustered on the row's group dimension in parentheses. Same battery and own-reach control as Table~\\ref{tab:peer_rf}; $N = 1{,}082$ (born $\\leq$1215) and $1{,}111$ (born $>$1215).}",
"\\label{tab:app_fe_peer}",
"{\\footnotesize\\setlength{\\tabcolsep}{4pt}", "\\begin{tabular}{lcccc}", "\\toprule",
" & \\multicolumn{2}{c}{Peer breadth} & \\multicolumn{2}{c}{Peer arbitration share} \\\\",
"\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}",
"Specification & $\\leq$1215 & $>$1215 & $\\leq$1215 & $>$1215 \\\\",
"\\midrule")
for (oc in names(OUTC)) {
  LB <- c(LB, sprintf("\\multicolumn{5}{l}{\\textit{%s}} \\\\", OUTC[[oc]]))
  for (vn in names(VAR)) {
    LB <- c(LB, sprintf("~~%s & %s & %s & %s & %s \\\\", VAR[[vn]]$lab,
      cellBP(vn, "EMFP", oc, "zB"), cellBP(vn, "post", oc, "zB"),
      cellBP(vn, "EMFP", oc, "zD"), cellBP(vn, "post", oc, "zD")))
  }
  if (oc != "total") LB <- c(LB, "\\addlinespace")
}
LB <- c(LB, "\\midrule",
"\\multicolumn{5}{p{0.9\\textwidth}}{\\footnotesize \\textit{Notes:} Within-patriline variation in breadth is thin nearly by construction -- brothers share a birth network -- so the patriline-FE breadth cells are underpowered rather than contrary; the arbitration-share sign flip at 1215 survives every variant and sharpens within patrilines. Two nobles with empty peer sets drop from all rows.} \\\\",
"\\bottomrule", "\\end{tabular}", "}", "\\end{table}",
"% ===== END tables/tab_app_fe_peer =====")
writeLines(LB, file.path(ROOT, "tables", "tab_app_fe_peer.tex"))
cat("wrote tables/tab_app_fe_headline.tex and tables/tab_app_fe_peer.tex\n")
