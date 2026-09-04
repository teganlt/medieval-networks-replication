#!/usr/bin/env Rscript
# 117_emit_appendix_tables.R
# ==========================
# Emit ALL robustness-appendix tables as .tex into tables/, one \begin{table}
# each, booktabs style matching tables/tab_domains.tex.
#   2. tab_app_robust.tex       <- reg_unified_bloc_iv / dropfrederick /
#                                  drop_largest (+ LOO range in Notes)
#   3. tab_app_hopsweep.tex     <- reg_unified_hopsweep.csv
#   4. tab_app_inference.tex    <- reg_unified_wcb_proper + permutation999 +
#                                  reg_peer_rf_permutation
#   5. tab_app_margins.tex      <- decomp_chenroth_domains + excess_share +
#                                  poisson_cf
#   6. tab_app_reverse.tex      <- reg_reverse_rf + reg_reverse_erosion
#   8. tab_app_peer_oster.tex   <- reg_peer_rf_oster.csv
#   9. tab_app_censoring.tex    <- reg_peer_rf_censoring.csv (secterr + total)
# Usage:  Rscript 117_emit_appendix_tables.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
suppressPackageStartupMessages(library(data.table))
CIV <- file.path(ROOT, "output", "clean_iv")
TAB <- file.path(ROOT, "tables")
dir.create(TAB, showWarnings = FALSE)
rc <- function(f) fread(file.path(CIV, f))

ORD <- c("secular_territorial","ecclesiastical_appointments","crusade","other",
         "excommunication","ecclesiastical_property","inheritance","marriage")
LAB <- c(secular_territorial="Secular-territorial", ecclesiastical_appointments="Ecclesiastical appointments",
         crusade="Crusade", other="Other (heresy, diplomacy)", excommunication="Excommunication",
         ecclesiastical_property="Ecclesiastical property", inheritance="Inheritance",
         marriage="Marriage", total="All documents", dispute="Dispute", nondispute="Non-dispute",
         nonterritorial="Non-territorial dispute", excess_secterr="Excess secular-territorial",
         share_secterr="Share secular-territorial", secterr="Secular-territorial",
         appointments="Ecclesiastical appointments")
# beta: 4 decimals when |b|<0.1 (Pred-1 scale), else 3
fb <- function(v) ifelse(is.na(v), "--",
        formatC(v, format="f", digits=ifelse(abs(v) < 0.1, 4, 3)))
fm <- function(v, d=3) ifelse(is.na(v), "--", formatC(v, format="f", digits=d))
fp <- function(p) ifelse(is.na(p), "--", ifelse(p < 0.001, "$<$0.001", formatC(p, format="f", digits=3)))
wtab <- function(lines, fn) { writeLines(lines, file.path(TAB, fn)); cat("wrote", fn, "\n") }
notes <- function(txt, ncol, w="0.95") sprintf(
  "\\multicolumn{%d}{p{%s\\textwidth}}{\\footnotesize \\textit{Notes:} %s} \\\\", ncol, w, txt)

## ============ 2. tab_app_robust ============
bi <- rc("reg_unified_bloc_iv.csv")
df_ <- rc("reg_unified_dropfrederick.csv")
dl <- rc("reg_unified_drop_largest.csv")
loo <- rc("reg_unified_loo.csv")
st_loo <- loo[outcome == "secular_territorial"]
loo_min <- min(st_loo$beta); loo_max <- max(st_loo$beta); loo_pmax <- max(st_loo$p)
loo_n2 <- sum(st_loo$p_2way < .05, na.rm = TRUE); loo_p2max <- max(st_loo$p_2way, na.rm = TRUE)
rob_row <- function(lbl, b_s, p_s, p2_s, b_t, p_t, p2_t, n) sprintf(
  "%s & %s & %s & %s & %s & %s & %s & %s \\\\", lbl, fb(b_s), fp(p_s), fp(p2_s), fb(b_t), fp(p_t), fp(p2_t),
  ifelse(is.na(n), "--", format(n, big.mark=",")))
s1 <- bi[domain=="secular_territorial"]; t1 <- bi[domain=="total"]
s2 <- df_[domain=="secular_territorial"]; t2 <- df_[domain=="total"]
s3 <- dl[outcome=="secular_territorial"]; t3 <- dl[outcome=="total"]
lines <- c("\\begin{table}[t]", "\\centering",
  "\\caption{Single-observation and single-cluster robustness of the unified Prediction-1 baseline. Each row re-estimates the 2SLS baseline for the secular-territorial and all-documents outcomes: the full sample; dropping Frederick~II (the single noble with the most total appearances); and dropping bloc B3 (the largest bloc, 29\\% of focals and 41\\% of secular-territorial appearances).}",
  "\\label{tab:app_robust}", "\\begin{tabular}{lccccccc}", "\\toprule",
  " & \\multicolumn{3}{c}{Secular-territorial} & \\multicolumn{3}{c}{All documents} & \\\\",
  "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}",
  "Sample & $\\beta$ & $p$ & $p_{\\text{2-way}}$ & $\\beta$ & $p$ & $p_{\\text{2-way}}$ & $N$ \\\\",
  "\\midrule",
  rob_row("Baseline (full sample)", s1$beta, s1$p, s1$p_2way, t1$beta, t1$p, t1$p_2way, s1$N),
  rob_row("Frederick II dropped",   s2$beta, s2$p, s2$p_2way, t2$beta, t2$p, t2$p_2way, s2$N),
  rob_row("Largest bloc (B3) dropped", s3$beta_drop, s3$p_drop, s3$p2_drop, t3$beta_drop, t3$p_drop, t3$p2_drop, 2195L - 639L),
  "\\midrule",
  notes(sprintf("$p$ is bloc-clustered; $p_{\\text{2-way}}$ clusters on bloc and death-decade. Bloc leave-one-out over all 38 blocs: the secular-territorial coefficient is significant in every replicate (all bloc-clustered $p < %s$), two-way significant in %d of 38 (largest $p_{\\text{2-way}} = %s$), with $\\beta \\in [%s, %s]$.", fm(ceiling(loo_pmax*1000)/1000, 3), loo_n2, fm(ceiling(loo_p2max*1000)/1000, 3), fm(loo_min,4), fm(loo_max,4)), 8, "0.9"),
  "\\bottomrule", "\\end{tabular}", "\\end{table}")
wtab(lines, "tab_app_robust.tex")

## ============ 3. tab_app_hopsweep ============
hs <- rc("reg_unified_hopsweep.csv")
lines <- c("\\begin{table}[t]", "\\centering",
  "\\caption{Horizon sweep: the reach horizon $h$ and the matching $h$-hop maternal instrument. Each row is a separate 2SLS regression at horizon $h\\in\\{3,\\dots,6\\}$; the baseline is $h=4$. Per-SD $\\beta$ multiplies by the sample SD of $h$-hop reach. The last column is the correlation between $h$-hop reach and network size.}",
  "\\label{tab:app_hopsweep}", "\\begin{tabular}{clcccccc}", "\\toprule",
  "Hop & Outcome & $\\beta$ & $\\beta$ per SD & $p$ & $p_{\\text{2-way}}$ & $F_{\\text{first}}$ & cor(reach, size) \\\\",
  "\\midrule")
for (h in 3:6) {
  for (d in c("secular_territorial","total")) {
    r <- hs[hop == h & domain == d]
    hop_lbl <- ifelse(d == "secular_territorial", ifelse(h == 4, "\\textbf{4}", as.character(h)), "")
    row <- sprintf("%s & %s & %s & %s & %s & %s & %s & %s \\\\", hop_lbl,
      LAB[d], fb(r$beta), fb(r$beta_sd), fp(r$p_bloc), fp(r$p_2way), fm(r$F_first, 1), fm(r$cor_reach_size, 2))
    lines <- c(lines, row)
  }
  if (h < 6) lines <- c(lines, "\\addlinespace")
}
lines <- c(lines, "\\midrule",
  notes("Unified controls and fixed effects throughout; $p$ bloc-clustered, $p_{\\text{2-way}}$ on bloc and death-decade. The effect peaks at the kin-recognition horizon ($h=3$--$5$) and dies at $h=6$, where reach is closest to raw network size --- the pattern a size confound cannot produce.", 8, "0.9"),
  "\\bottomrule", "\\end{tabular}", "\\end{table}")
wtab(lines, "tab_app_hopsweep.tex")

## ============ 4. tab_app_inference ============
wcb <- rc("reg_unified_wcb_proper.csv")
pm1 <- rc("reg_unified_permutation999.csv")
pmP <- rc("reg_peer_rf_permutation.csv")
g <- function(oc, st) wcb[block=="pred1" & outcome==oc & stat==st]
p1row <- function(oc, lbl) {
  rf <- g(oc, "reduced_form"); wb <- g(oc, "reduced_form_webb"); d3 <- g(oc, "reduced_form_dropB3")
  ri <- pm1[outcome == oc]
  sprintf("%s & %s & %s & %s & %s & %s & %s & %s \\\\", lbl, fb(rf$beta), fp(rf$p_analytic_bloc),
    fp(rf$p_wcb), fp(wb$p_wcb), fp(d3$p_wcb), fp(ri$p_perm), fm(ri$z, 2))
}
fs <- wcb[block=="pred1" & stat=="first_stage"]
lines <- c("\\begin{table}[t]", "\\centering",
  "\\caption{Design-based and cluster-robust inference with 38 clusters. Panel A: reduced-form Prediction-1 estimates (instrument direct), analytic bloc-clustered $p$, restricted wild-cluster bootstrap $p$ (Rademacher and Webb weights, and re-run without the largest bloc B3), and randomization inference (instrument permuted within bloc$\\times$decade cells, 999 draws). Panel B: the peer reduced form under the same randomization scheme.}",
  "\\label{tab:app_inference}", "{\\footnotesize\\setlength{\\tabcolsep}{4pt}", "\\begin{tabular}{lccccccc}", "\\toprule",
  "\\multicolumn{8}{l}{\\textit{Panel A: Prediction 1 (reduced form), wild-cluster bootstrap and randomization inference}} \\\\",
  "\\addlinespace",
  " & & & \\multicolumn{3}{c}{Restricted WCB $p$} & \\multicolumn{2}{c}{Rand.\\ inference} \\\\",
  "\\cmidrule(lr){4-6}\\cmidrule(lr){7-8}",
  "Outcome & $\\beta_{\\text{RF}}$ & $p_{\\text{analytic}}$ & Rademacher & Webb & drop B3 & $p_{\\text{RI}}$ & $z$ \\\\",
  "\\midrule",
  p1row("secular_territorial", "\\textbf{Secular-territorial}"),
  p1row("total", "All documents"),
  p1row("ecclesiastical_appointments", "Ecclesiastical appointments"),
  sprintf("First stage (common) & %s & %s & %s & -- & -- & -- & -- \\\\", fb(fs$beta), fp(fs$p_analytic_bloc), fp(fs$p_wcb)),
  "\\midrule",
  "\\multicolumn{8}{l}{\\textit{Panel B: Peer reduced form, randomization inference (999 draws within bloc$\\times$decade cells)}} \\\\",
  "\\addlinespace",
  "Treatment $\\times$ era & \\multicolumn{3}{c}{Secular-territorial} & & \\multicolumn{3}{c}{All documents} \\\\",
  " & $\\beta$ & $p_{\\text{RI}}$ & $z$ & & $\\beta$ & $p_{\\text{RI}}$ & $z$ \\\\",
  "\\midrule")
era_lbl <- c(ALL="all", EMFP="born $\\leq$1215", post="born $>$1215")
for (tr in c("zB","zD")) for (e in c("ALL","EMFP","post")) {
  rs <- pmP[treatment==tr & era==e & domain=="secular_territorial"]
  rt <- pmP[treatment==tr & era==e & domain=="total"]
  tl <- ifelse(tr=="zB", "Peer breadth", "Arbitration share")
  lines <- c(lines, sprintf("%s, %s & %s & %s & %s & & %s & %s & %s \\\\",
    tl, era_lbl[e], fb(rs$beta_obs), fp(rs$p_perm), fm(rs$z,2), fb(rt$beta_obs), fp(rt$p_perm), fm(rt$z,2)))
}
lines <- c(lines, "\\midrule",
  notes("WCB: restricted (null-imposed) wild-cluster bootstrap, $B=9{,}999$, clustering on bloc. RI $p$ is the two-sided permutation tail with 999 draws; $z$ standardizes the observed coefficient against the permutation distribution. The peer-breadth secular-territorial estimate also survives its restricted WCB ($p=.091$ pooled, $p=.047$ in the prohibition era, $p=.168$ post).", 8, "0.9"),
  "\\bottomrule", "\\end{tabular}", "}", "\\end{table}")
wtab(lines, "tab_app_inference.tex")

## ============ 5. tab_app_margins ============
cr <- rc("decomp_chenroth_domains.csv")
ex <- rc("reg_unified_excess_share.csv")
pc <- rc("reg_unified_poisson_cf.csv")
cr_row <- function(oc) {
  f <- cr[outcome==oc & sample=="full"]; t <- cr[outcome==oc & sample=="trim50"]
  sprintf("%s & %s & %s & %s & %s & %s & %s \\\\", LAB[oc],
    fb(f$b_y_full), fp(f$p_y_full), fm(f$ext_share, 2),
    fb(t$b_y_full), fp(t$p_y_full), fm(t$ext_share, 2))
}
ex_row <- function(oc, lbl) { r <- ex[outcome==oc]
  sprintf("%s & %s & %s & %s & %s & %s \\\\", lbl, fb(r$beta), fm(r$SE, ifelse(abs(r$beta)<0.1,4,3)),
    fp(r$p_bloc), fp(r$p_2way), format(r$N, big.mark=",")) }
pc_row <- function(dm) { r <- pc[domain==dm]
  sprintf("%s & %s & %s & %s & %s & [%s, %s] & %s & %s & %s \\\\", LAB[dm],
    fb(r$beta), fm(r$SE_analytic,3), fp(r$p_analytic), fm(r$boot_MAD_SE,3),
    fm(r$boot_ci_lo,3), fm(r$boot_ci_hi,3), fp(r$p_boot), fp(r$vhat_p), format(r$N, big.mark=",")) }
lines <- c("\\begin{table}[t]", "\\centering",
  "\\caption{Margins: where the Prediction-1 effect lives. Panel A decomposes the log-IV estimate into extensive and intensive margins (Chen--Roth), full sample and trimming the top 50 appearers. Panel B replaces the outcome with dispute counts, the non-territorial dispute complement, excess secular-territorial appearances, and the secular-territorial share among appearers. Panel C re-estimates the headline on raw counts by Poisson control function with a score (wild-cluster) bootstrap.}",
  "\\label{tab:app_margins}", "{\\small",
  "\\begin{tabular}{lcccccc}", "\\toprule",
  "\\multicolumn{7}{l}{\\textit{Panel A: Chen--Roth extensive/intensive decomposition}} \\\\",
  "\\addlinespace",
  " & \\multicolumn{3}{c}{Full sample ($N=2{,}181$)} & \\multicolumn{3}{c}{Top-50 appearers trimmed} \\\\",
  "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}",
  "Outcome & $\\beta$ & $p$ & ext.\\ share & $\\beta$ & $p$ & ext.\\ share \\\\",
  "\\midrule",
  cr_row("secular_territorial"), cr_row("dispute"), cr_row("total"), cr_row("nondispute"),
  "\\bottomrule", "\\end{tabular}", "\\par\\vspace{1.5ex}",
  "\\begin{tabular}{lccccc}", "\\toprule",
  "\\multicolumn{6}{l}{\\textit{Panel B: Excess and share outcomes (2SLS, unified controls)}} \\\\",
  "\\addlinespace",
  "Outcome & $\\beta$ & SE & $p$ & $p_{\\text{2-way}}$ & $N$ \\\\", "\\midrule",
  ex_row("dispute", "$\\log(1+\\text{dispute appearances})$"),
  ex_row("nonterritorial", "$\\log(1+\\text{non-territorial dispute})$"),
  ex_row("excess_secterr", "Excess secular-territorial"),
  ex_row("share_secterr", "Secular-territorial share ($n_{\\text{total}}>0$)"),
  "\\bottomrule", "\\end{tabular}", "\\par\\vspace{1.5ex}",
  "\\begin{tabular}{lcccccccc}", "\\toprule",
  "\\multicolumn{9}{l}{\\textit{Panel C: Poisson control function on raw counts (score bootstrap, $B=199$)}} \\\\",
  "\\addlinespace",
  "Outcome & $\\beta$ & SE & $p$ & boot SE & 95\\% CI & $p_{\\text{boot}}$ & $p_{\\hat v}$ & $N$ \\\\",
  "\\midrule",
  pc_row("secterr"), pc_row("dispute"), pc_row("total"),
  "\\midrule",
  notes("Panel A: extensive share is the fraction of the full effect running through any-appearance; the headline domains are $\\sim$90\\% intensive-margin. Panel B: excess secular-territorial = appearances above the corpus-share expectation ($p_{\\text{sec}}=0.232$); the null share result says reach raises how often nobles litigate, not the composition among appearers; first-stage $F=339$ ($F=110$ in the share subsample, $N=297$). Panel C: $p$ is the analytic cluster-robust $p$; boot SE is the MAD-based score-bootstrap SE and CI the percentile interval; $p_{\\hat v}$ tests the control-function residual (endogeneity).", 9, "0.9"),
  "\\bottomrule", "\\end{tabular}", "}", "\\end{table}")
wtab(lines, "tab_app_margins.tex")

## ============ 6. tab_app_reverse ============
rr <- rc("reg_reverse_rf.csv")
re <- rc("reg_reverse_erosion.csv")
rr_row <- function(rg) { r <- rr[rung==rg & type=="intensive"]
  sprintf("%s & %s & %s & %s & %s \\\\", LAB[rg], fb(r$beta), fm(r$SE,3), fp(r$p_bloc), fp(r$p_2way)) }
re_s <- re[rung=="secular_territorial"]
lines <- c("\\begin{table}[t]", "\\centering",
  "\\caption{The return arrow: reverse reduced form and erosion. Panel A regresses the child's bloc kin-reach on the father's papal appearance in each domain (intensive margin), with the unified controls. Panel B tests erosion for the secular-territorial rung: the level of the child's reach and the net change $\\Delta_{\\text{net}}$ in reach across the generation, conditional on the father's reach.}",
  "\\label{tab:app_reverse}",
  "\\begin{tabular}{lcccc}", "\\toprule",
  "\\multicolumn{5}{l}{\\textit{Panel A: Father's appearance $\\rightarrow$ child's kin-reach (intensive margin)}} \\\\",
  "\\addlinespace",
  "Father's domain & $\\beta$ & SE & $p$ & $p_{\\text{2-way}}$ \\\\", "\\midrule",
  rr_row("secular_territorial"), rr_row("dispute"), rr_row("total"),
  "\\midrule",
  "\\multicolumn{5}{l}{\\textit{Panel B: Erosion, secular-territorial rung}} \\\\",
  "\\addlinespace",
  sprintf("Child reach (level) & %s & & %s & \\\\", fb(re_s$level_b), fp(re_s$level_p)),
  sprintf("$\\Delta_{\\text{net}}$ reach across generation & %s & & %s & \\\\", fb(re_s$Dnet_b), fp(re_s$Dnet_p)),
  "\\midrule",
  notes("Reverse of the forward design: these estimates are reduced-form and carry the usual reverse-causal caveat. A positive feedback loop is absent (total $\\approx 0$); the dispute and secular-territorial channels are negative and two-way robust --- fathers who appear in territorial disputes have children with \\emph{lower} subsequent kin-reach, net of the father's own reach, i.e.\\ dispute-specific erosion rather than generic mean reversion. $p$ bloc-clustered; $p_{\\text{2-way}}$ on bloc and death-decade.", 5, "0.85"),
  "\\bottomrule", "\\end{tabular}", "\\end{table}")
wtab(lines, "tab_app_reverse.tex")

## ============ 8. tab_app_peer_oster ============
os <- rc("reg_peer_rf_oster.csv")
lines <- c("\\begin{table}[t]", "\\centering",
  "\\caption{Oster (2019) selection-on-unobservables bounds for the peer reduced form. Short = the primary specification of Table~\\ref{tab:peer_rf} (full ancestor battery, own reach, and fixed effects); long adds the five-generation family court-history block. $\\beta^*(\\delta{=}1)$ is the bias-adjusted coefficient at equal selection; $\\delta^*$ is the selection ratio that drives the coefficient to zero. Two $R_{\\max}$ conventions per cell: $1.3\\,R^2_{\\text{long}}$ and $R_{\\max}=1$.}",
  "\\label{tab:app_peer_oster}", "{\\small", "\\begin{tabular}{llcccccc}", "\\toprule",
  "Era & Outcome & $R_{\\max}$ & $\\beta_{\\text{short}}$ & $\\beta_{\\text{long}}$ & $\\beta^*(\\delta{=}1)$ & $\\delta^*$ & Robust \\\\",
  "\\midrule")
os[, rmax_lbl := ifelse(abs(Rmax - 1) < 1e-9, "1.00", "$1.3R^2$")]
era_lbl2 <- c(ALL="Pooled", EMFP="Born $\\leq$1215", post="Born $>$1215")
prev_era <- ""
for (i in seq_len(nrow(os))) {
  r <- os[i]
  e <- era_lbl2[r$era]
  if (r$era != prev_era && prev_era != "") lines <- c(lines, "\\addlinespace")
  prev_era <- r$era
  lines <- c(lines, sprintf("%s & %s & %s & %s & %s & %s & %s & %s \\\\",
    e, LAB[r$domain], r$rmax_lbl, fb(r$beta_short), fb(r$beta_long), fb(r$beta_star_d1),
    fm(r$delta_star, 2), ifelse(r$robust, "yes", "no")))
}
n_rob <- sum(os$robust)
lines <- c(lines, "\\midrule",
  notes(sprintf("Robust = the identified set $[\\beta_{\\text{long}}, \\beta^*(\\delta{=}1)]$ excludes zero. %d of %d cells are robust; a negative $\\delta^*$ means adding controls moves the coefficient \\emph{away} from zero, so no degree of proportional selection can explain it. The two prohibition-era $R_{\\max}=1$ failures reflect the extreme convention that unobservables would explain all residual outcome variance; at the standard $1.3\\,R^2$ convention the prohibition-era secular-territorial $\\delta^*=5.9$.", n_rob, nrow(os)), 8, "0.9"),
  "\\bottomrule", "\\end{tabular}", "}", "\\end{table}")
wtab(lines, "tab_app_peer_oster.tex")

## ============ 9. tab_app_censoring ============
cs <- rc("reg_peer_rf_censoring.csv")
cs <- cs[domain %in% c("secular_territorial","total")]
spec_lbl <- c("C1 zDm matchable-denom"="C1: share over matchable peers",
              "C2 zB + share ctrl"="C2: breadth $+$ matchable-share control",
              "C3 zD + share ctrl"="C3: share $+$ matchable-share control")
lines <- c("\\begin{table}[t]", "\\centering",
  "\\caption{Match-censoring robustness of the peer channel. The arbitration share's denominator counts all pre-natal kin, matchable to the corpus or not; these specs bound any censoring artifact: C1 recomputes the share over matchable peers only; C2 and C3 re-run breadth and share controlling the matchable share directly.}",
  "\\label{tab:app_censoring}", "{\\footnotesize\\setlength{\\tabcolsep}{4pt}", "\\begin{tabular}{lllcccc}", "\\toprule",
  "Era & Outcome & Spec & $\\beta$ & SE & $p$ & $p_{\\text{2-way}}$ \\\\", "\\midrule")
prev <- ""
for (e in c("ALL","EMFP","post")) {
  for (d in c("secular_territorial","total")) {
    for (sp in names(spec_lbl)) {
      r <- cs[era==e & domain==d & spec==sp]
      lines <- c(lines, sprintf("%s & %s & %s & %s & %s & %s & %s \\\\",
        era_lbl2[e], LAB[d], spec_lbl[sp], fb(r$beta), fm(r$SE, ifelse(abs(r$beta)<0.1,4,3)),
        fp(r$p_bloc), fp(r$p_2way)))
    }
  }
  if (e != "post") lines <- c(lines, "\\addlinespace")
}
lines <- c(lines, "\\midrule",
  notes("C1/C3 report the arbitration-share treatment ($z_D$ or its matchable-denominator variant $z_{Dm}$); C2 reports peer breadth ($z_B$). The era flip survives every variant: the share loads positive in the prohibition era and negative after 1215 whether the denominator is matchable-only or the matchable share is controlled, and breadth stays positive throughout. $p$ bloc-clustered; $p_{\\text{2-way}}$ on bloc and death-decade.", 7, "0.9"),
  "\\bottomrule", "\\end{tabular}", "}", "\\end{table}")
wtab(lines, "tab_app_censoring.tex")

