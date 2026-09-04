# 149_conflict_prone_headline.R
# =============================
# THE ESSENTIAL TABLE (8/26): the headline IV decomposed by the ex-ante
# conflict-prone cut of 148. Pooled 2SLS per outcome with three terms:
#   reach (quiet-group slope; instrumented), conflict-prone level, and
#   reach x conflict-prone (instrumented by the mother-reach product).
# Also computes, data-driven for the table notes: the in/out split, the
# in-group gate battery, WCB p-values (interaction, in-group ITT, and the
# conflict-prone level term), the mother-level permutation, and the
# battery-partialled correlations of cp2 with reach and the instrument
# (previously hard-coded in the caption; now computed).
# Emits: tables/tab_app_cp2_inter.tex
# CSVs:  output/clean_iv/reg_cp2_interaction.csv, reg_cp2_split.csv,
#        reg_cp2_gates.csv
# CLI: Rscript scripts/149_conflict_prone_headline.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output"); TAB <- file.path(ROOT, "tables")
suppressPackageStartupMessages({library(data.table); library(fixest)})
set.seed(42)

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))
fl <- fread(file.path(OUTDIR, "clean_iv", "conflict_prone_v2_flags.csv"))
fam <- fread(file.path(OUTDIR, "clean_iv", "reg_complementarity_iv_df_sat2.csv"))[
  , .(person_id, fa_ldisp, pat_disp_anc, pat_secterr_anc, n_pat_anc)]
per <- fread(file.path(OUTDIR, "persons_imputed.csv"))[, .(person_id = id, pname = name)]
df <- Reduce(function(a, b) merge(a, b, by = "person_id", all.x = TRUE), list(df, fl, fam, per))
for (c in c("fa_ldisp","pat_disp_anc","pat_secterr_anc","n_pat_anc")) df[is.na(get(c)), (c) := 0]
coded <- fread(file.path(OUTDIR, "matched_docs_coded.csv"), colClasses = list(character = "doc_id"))[, .(doc_id, is_dispute)]
mt <- fread(file.path(OUTDIR, "doc_matches_ai_extracted_high.csv"),
            colClasses = list(character = "doc_id"))[doc_year >= 1100 & doc_year <= 1300, .(person_id, doc_id)]
mt <- merge(mt, coded, by = "doc_id")
dcx <- dcast(mt, person_id ~ is_dispute, value.var = "doc_id", fun.aggregate = length)
setnames(dcx, c("yes", "no"), c("dom_dispute", "dom_nondispute"), skip_absent = TRUE)
df <- merge(df, dcx[, .(person_id, dom_dispute, dom_nondispute)], by = "person_id", all.x = TRUE)
for (cc in c("dom_dispute", "dom_nondispute")) df[is.na(get(cc)), (cc) := 0]
df[, `:=`(EMFP = as.integer(birth <= 1215), lsize = log1p(n_nodes_4hop),
          z1c = mother_n_dyn_4hop - mean(mother_n_dyn_4hop))]
df[, `:=`(rx = n_dyn_4hop * cp2, ix = mother_n_dyn_4hop * cp2)]
df[, z12 := z1c * cp2]
FRED <- "p10223.htm#i102226"
H3RC <- df[grepl("Henry III, King of England|Richard, 1st Earl of Cornwall", pname), person_id]

anc <- c("factor(mother_title_rank)","factor(father_title_rank)","factor(mgf_title_rank)",
  "mother_log_n_nodes_4hop","father_log_n_nodes_4hop","mgf_log_n_nodes_4hop",
  "mother_log_pre_deg","father_log_pre_deg","mgf_log_pre_deg",
  "mother_log_total_inwin","father_log_total_inwin","mgf_log_total_inwin","mgf_n_dyn_4hop")
BAT <- paste(c("factor(title_rank)","factor(death_decade)","factor(dynasty)", anc, "f_extra4"), collapse = " + ")
FAM <- "fa_ldisp + pat_disp_anc + pat_secterr_anc + n_pat_anc"
DOMS <- c("secular_territorial","dispute","nondispute","total","ecclesiastical_appointments",
          "excommunication","crusade","other","ecclesiastical_property","inheritance","marriage")
DLAB <- c(secular_territorial = "Secular-territorial", dispute = "All dispute-coded",
          nondispute = "All non-dispute", total = "All documents",
          ecclesiastical_appointments = "Eccl.\\ appointments", excommunication = "Excommunication",
          crusade = "Crusade", other = "Other", ecclesiastical_property = "Eccl.\\ property",
          inheritance = "Inheritance", marriage = "Marriage")
pull2 <- function(m, tr, vc = NULL) {
  s <- if (is.null(vc)) m else tryCatch(summary(m, vcov = vc), error = function(e) NULL)
  if (is.null(s)) return(c(NA, NA, NA))
  ct <- as.data.frame(coeftable(s)); if (!(tr %in% rownames(ct))) return(c(NA, NA, NA))
  unlist(ct[tr, c(1, 2, 4)], use.names = FALSE)
}
fp <- function(p) ifelse(is.na(p), "--", ifelse(p < 0.001, "$<$.001", sub("^0", "", sprintf("%.3f", p))))
fb <- function(b) ifelse(is.na(b), "--", sprintf("%.4f", b))

## (1) interaction grid — the essential table
IR <- list()
for (dom in DOMS) {
  d <- copy(df); d[, .y := log1p(get(paste0("dom_", dom)))]
  m <- tryCatch(feols(as.formula(sprintf(".y ~ cp2 + %s | n_dyn_4hop + rx ~ mother_n_dyn_4hop + ix", BAT)),
                      data = d, cluster = ~dynasty), error = function(e) NULL)
  if (is.null(m)) next
  row <- data.table(domain = dom)
  for (tr in c("fit_n_dyn_4hop", "cp2", "fit_rx")) {
    b <- pull2(m, tr); b2 <- pull2(m, tr, ~dynasty + death_decade)
    nm <- c(fit_n_dyn_4hop = "reach", cp2 = "level", fit_rx = "inter")[tr]
    row[, paste0(nm, c("_b", "_p", "_p2")) := as.list(c(b[1], b[3], b2[3]))]
  }
  IR[[dom]] <- row
}
IR <- rbindlist(IR)
fwrite(IR, file.path(OUTDIR, "clean_iv", "reg_cp2_interaction.csv"))

## (2) in/out split
SP <- list()
for (dom in DOMS) for (v in c(1L, 0L)) {
  d <- df[cp2 == v]; d[, .y := log1p(get(paste0("dom_", dom)))]
  m <- tryCatch(feols(as.formula(sprintf(".y ~ %s | n_dyn_4hop ~ mother_n_dyn_4hop", BAT)),
                      data = d, cluster = ~dynasty), error = function(e) NULL)
  b <- pull2(m, "fit_n_dyn_4hop"); b2 <- if (is.null(m)) c(NA,NA,NA) else pull2(m, "fit_n_dyn_4hop", ~dynasty + death_decade)
  SP[[paste(dom, v)]] <- data.table(domain = dom, group = ifelse(v == 1, "in", "out"),
                                    beta = b[1], p = b[3], p2 = b2[3],
                                    N = if (is.null(m)) NA_integer_ else nobs(m))
}
SP <- rbindlist(SP); fwrite(SP, file.path(OUTDIR, "clean_iv", "reg_cp2_split.csv"))

## (3) gates (secterr in-group) for the notes
g <- df[cp2 == 1]
gate <- function(d, extra = "", clu = ~dynasty) {
  d <- copy(d); d[, .y := log1p(dom_secular_territorial)]
  ctl <- if (nzchar(extra)) paste(extra, BAT, sep = " + ") else BAT
  m <- tryCatch(feols(as.formula(sprintf(".y ~ %s | n_dyn_4hop ~ mother_n_dyn_4hop", ctl)),
                      data = d, cluster = clu), error = function(e) NULL)
  c(pull2(m, "fit_n_dyn_4hop")[1], pull2(m, "fit_n_dyn_4hop", ~dynasty + death_decade)[3],
    pull2(m, "fit_n_dyn_4hop")[3])
}
G <- list(base = gate(g), fam = gate(g, FAM), sxe = gate(g, "lsize + lsize:EMFP + EMFP"),
          dfr = gate(g[person_id != FRED]), db3 = gate(g[dynasty != "B3"]),
          dhr = gate(g[!(person_id %in% H3RC)]),
          cmo = gate(g, "", ~mother_id), cmg = gate(g, "", ~mgf_id))
fwrite(data.table(gate = names(G), beta = sapply(G, `[`, 1), p2w = sapply(G, `[`, 2),
                  p_alt = sapply(G, `[`, 3)), file.path(OUTDIR, "clean_iv", "reg_cp2_gates.csv"))

## (4) WCB + permutation for the notes
p_wcb_z12 <- NA_real_; p_wcb_itt <- NA_real_
if (requireNamespace("fwildclusterboot", quietly = TRUE)) {
  suppressMessages(library(fwildclusterboot))
  d <- copy(df); d[, .y := log1p(dom_secular_territorial)]
  m <- feols(as.formula(sprintf(".y ~ z1c + z12 + cp2 + %s", BAT)), data = d, cluster = ~dynasty)
  p_wcb_z12 <- tryCatch(suppressWarnings(boottest(m, param = "z12", clustid = "dynasty", B = 9999,
                                                  type = "rademacher", impose_null = TRUE))$p_val,
                        error = function(e) NA_real_)
  gi <- d[cp2 == 1]
  mi <- feols(as.formula(sprintf(".y ~ z1c + %s", BAT)), data = gi, cluster = ~dynasty)
  p_wcb_itt <- tryCatch(suppressWarnings(boottest(mi, param = "z1c", clustid = "dynasty", B = 9999,
                                                  type = "rademacher", impose_null = TRUE))$p_val,
                        error = function(e) NA_real_)
}
Xf <- model.matrix(as.formula(paste("~ z1c +", paste(anc, collapse = " + "),
      "+ f_extra4 + factor(title_rank) + factor(death_decade) + factor(dynasty)")), data = df)
qrX <- qr(Xf)
mo <- df[, .(cp2 = cp2[1], dynasty = dynasty[1]), by = mother_id]
gidx <- match(df$mother_id, mo$mother_id)
y <- log1p(df$dom_secular_territorial); ey <- qr.resid(qrX, y)
ob <- qr.solve(qr.resid(qrX, cbind(df$z1c * df$cp2, df$cp2)), ey)[1]
bs <- rep(NA_real_, 999)
for (b_ in 1:999) {
  p <- copy(mo); p[, cperm := cp2[sample.int(.N)], by = dynasty]
  cper <- p$cperm[gidx]
  bs[b_] <- tryCatch(qr.solve(qr.resid(qrX, cbind(df$z1c * cper, cper)), ey)[1], error = function(e) NA_real_)
}
bs <- bs[is.finite(bs)]
p_perm <- (1 + sum(abs(bs) >= abs(ob))) / (1 + length(bs))

# level-term WCB (run AFTER the seeded blocks above so their draws are unchanged)
p_wcb_level <- NA_real_
if (requireNamespace("fwildclusterboot", quietly = TRUE) && exists("m")) {
  p_wcb_level <- tryCatch(suppressWarnings(boottest(m, param = "cp2", clustid = "dynasty", B = 9999,
                                                    type = "rademacher", impose_null = TRUE))$p_val,
                          error = function(e) NA_real_)
}

# battery-partialled correlations of cp2 with reach and the instrument
X0 <- model.matrix(as.formula(paste("~", paste(anc, collapse = " + "),
      "+ f_extra4 + factor(title_rank) + factor(death_decade) + factor(dynasty)")), data = df)
qr0 <- qr(X0)
ecp <- qr.resid(qr0, df$cp2)
pc_reach <- cor(ecp, qr.resid(qr0, df$n_dyn_4hop))
pc_instr <- cor(ecp, qr.resid(qr0, df$mother_n_dyn_4hop))

cat(sprintf("notes inputs: WCB z12=%.4f  WCB in-group ITT=%.4f  WCB level=%.4f  perm=%.4f  pcor(reach)=%.4f  pcor(instr)=%.4f\n",
            p_wcb_z12, p_wcb_itt, p_wcb_level, p_perm, pc_reach, pc_instr))
cat("gates:\n"); print(data.table(gate = names(G), beta = sapply(G, `[`, 1), p2w = sapply(G, `[`, 2)))

## (5) emit the essential table
L <- c(
"\\begin{table}[t]", "\\centering",
sprintf("\\caption{The baseline IV decomposed by ex-ante conflict-prone maternal-family structure. One pooled 2SLS per outcome: reach (instrumented by mother's pre-natal reach), a conflict-prone indicator, and their interaction (instrumented by the mother-reach product). Conflict-prone ($N$=%d of %d; %d mothers with two or more recorded husbands, %d sonless maternal grandfathers with a rival sister-line, %d living collateral great-uncles; unions overlap) is defined from family structure alone and is orthogonal to reach and the instrument after the battery (partial correlations $%.3f$ and $%.3f$). Bloc-clustered $p$ and two-way (bloc and death-decade) $p_{2\\text{w}}$.}",
        sum(df$cp2), nrow(df), sum(df$H1), sum(df$H2), sum(df$H3), pc_reach, pc_instr),
"\\label{tab:app_cp2_inter}", "\\small", "\\begin{tabular}{lcccccc}", "\\toprule",
" & \\multicolumn{2}{c}{Reach (quiet-group slope)} & \\multicolumn{2}{c}{Conflict-prone (level)} & \\multicolumn{2}{c}{Reach $\\times$ conflict-prone} \\\\",
"\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}",
"Outcome & $\\beta$ & $p_{2\\text{w}}$ & $\\beta$ & $p_{2\\text{w}}$ & $\\beta$ & $p_{2\\text{w}}$ \\\\",
"\\midrule")
for (dom in DOMS) {
  r <- IR[domain == dom]
  if (nrow(r) == 0) next
  L <- c(L, sprintf("%s & %s & %s & %s & %s & %s & %s \\\\", DLAB[dom],
    fb(r$reach_b), fp(r$reach_p2), fb(r$level_b), fp(r$level_p2), fb(r$inter_b), fp(r$inter_p2)))
}
sIN <- SP[domain == "secular_territorial" & group == "in"]
lvl_note <- if (is.finite(p_wcb_level) && p_wcb_level >= 0.05) {
  sprintf("The level coefficient does not survive the wild bootstrap ($p$ = %s) and is reported as descriptive.", fp(p_wcb_level))
} else if (is.finite(p_wcb_level)) {
  sprintf("The level coefficient (wild bootstrap $p$ = %s) is nevertheless reported as descriptive, as the moderator is endogenous.", fp(p_wcb_level))
} else "The level coefficient is reported as descriptive."
L <- c(L, "\\midrule",
sprintf("\\multicolumn{7}{p{0.94\\textwidth}}{\\footnotesize \\textit{Notes:} The split-sample counterpart for the secular-territorial outcome: reach $=$ %s ($p_{2\\text{w}}$ = %s) among the conflict-prone and %s ($p$ = %s) elsewhere. In-group gate battery (secular-territorial, two-way $p$): family history %s; size$\\times$era %s; dropping Frederick~II (not in the group) %s; dropping bloc B3 %s (coefficient rises to %s); dropping Henry~III and Richard of Cornwall %s (coefficient %s); clustering at the mother %s and at the maternal grandfather %s. Wild-cluster bootstrap: interaction $p$ = %s, in-group reduced form on the instrument $p$ = %s. Mother-level permutation of the indicator within blocs (999 draws): $p$ = %s. %s} \\\\",
  fb(sIN$beta), fp(sIN$p2), fb(SP[domain == "secular_territorial" & group == "out", beta]),
  fp(SP[domain == "secular_territorial" & group == "out", p]),
  fp(G$fam[2]), fp(G$sxe[2]), fp(G$dfr[2]), fp(G$db3[2]), fb(G$db3[1]),
  fp(G$dhr[2]), fb(G$dhr[1]), fp(G$cmo[3]), fp(G$cmg[3]),
  fp(p_wcb_z12), fp(p_wcb_itt), fp(p_perm), lvl_note),
"\\bottomrule", "\\end{tabular}", "\\end{table}")
writeLines(L, file.path(TAB, "tab_app_cp2_inter.tex"))
cat("wrote tab_app_cp2_inter.tex\n")
