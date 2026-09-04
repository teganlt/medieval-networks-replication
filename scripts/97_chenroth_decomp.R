# Chen-Roth decomposition for every outcome: 8 domains + total + dispute/nondispute.
# log(1+n) = log2*1{n>0} + [log(1+n) - log2*1{n>0}]; each part as outcome in the
# identical Pred-1 IV spec. Full sample and drop n_total_inwin>50.
args <- commandArgs(trailingOnly = TRUE)
ROOT <- args[1]; if (is.na(ROOT)) ROOT <- if (length(commandArgs(trailingOnly=TRUE)) >= 1) commandArgs(trailingOnly=TRUE)[1] else "."; OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages({library(data.table); library(fixest)})
src <- readLines(file.path(ROOT, "scripts", "96_cf_poisson_oster.R"))
cut <- grep("^cf_pois <- function", src)[1]
eval(parse(text = paste(src[12:(cut - 1)], collapse = "\n")))

# dispute / non-dispute counts (script 58 definition)
coded2 <- fread(file.path(OUTDIR, "matched_docs_coded.csv"),
                colClasses = list(character = "doc_id"))[, .(doc_id, is_dispute)]
mt2 <- fread(file.path(OUTDIR, "doc_matches_ai_extracted_high.csv"),
             colClasses = list(character = "doc_id"))[
  doc_year >= 1100 & doc_year <= 1300, .(person_id, doc_id)]
mt2 <- merge(mt2, coded2, by = "doc_id")
pc <- mt2[, .(dom_dispute = sum(is_dispute == "yes"),
              dom_nondispute = sum(is_dispute == "no")), by = person_id]
pc[, person_id := as.character(person_id)]
df[, person_id := as.character(person_id)]
df <- merge(df, pc, by = "person_id", all.x = TRUE)
for (c_ in c("dom_dispute", "dom_nondispute")) df[is.na(get(c_)), (c_) := 0]
dc2 <- copy(dc); dc2[, person_id := as.character(person_id)]
df <- merge(df, dc2, by = "person_id", all.x = TRUE)
df[is.na(n_total_inwin), n_total_inwin := 0]

OUTC <- c("dom_secular_territorial", "dom_ecclesiastical_appointments", "dom_crusade",
          "dom_other", "dom_excommunication", "dom_ecclesiastical_property",
          "dom_inheritance", "dom_marriage", "dom_total", "dom_dispute", "dom_nondispute")

run1 <- function(d, oc) {
  d[, y_full := log1p(get(oc))]
  d[, y_ext  := as.numeric(get(oc) > 0)]
  d[, y_int  := y_full - log(2) * y_ext]
  r <- list(outcome = sub("dom_", "", oc), npos = sum(d[[oc]] > 0))
  for (y in c("y_full", "y_ext", "y_int")) {
    m <- feols(as.formula(paste0(y, " ~ ", LIN1,
          " | dynasty + death_decade + title_rank | n_dyn_4hop ~ mother_n_dyn_4hop")),
        data = d, cluster = ~dynasty, notes = FALSE)
    ct <- as.data.frame(coeftable(m))
    r[[paste0("b_", y)]] <- ct["fit_n_dyn_4hop", "Estimate"]
    r[[paste0("p_", y)]] <- ct["fit_n_dyn_4hop", "Pr(>|t|)"]
    r$N <- m$nobs
  }
  r$ext_share <- log(2) * r$b_y_ext / r$b_y_full
  as.data.table(r)
}
stars <- function(p) ifelse(p < .01, "***", ifelse(p < .05, "**", ifelse(p < .1, "*", "")))
show <- function(R, lab) {
  cat(sprintf("\n=== %s (N=%d) ===\n", lab, R$N[1]))
  cat(sprintf("%-28s %13s %14s %14s %9s %6s\n", "outcome", "full", "ext(x log2)", "intensive", "ext.shr", "n>0"))
  for (i in seq_len(nrow(R))) { r <- R[i]
    cat(sprintf("%-28s %+.4f%-4s %+.4f%-4s %+.4f%-4s %8s %6d\n",
        r$outcome, r$b_y_full, stars(r$p_y_full), log(2) * r$b_y_ext, stars(r$p_y_ext),
        r$b_y_int, stars(r$p_y_int),
        ifelse(abs(r$b_y_full) < .002, "--", sprintf("%.0f%%", 100 * r$ext_share)), r$npos))
  }
}
Rf <- rbindlist(lapply(OUTC, function(oc) run1(copy(df), oc)))
Rt <- rbindlist(lapply(OUTC, function(oc) run1(df[n_total_inwin <= 50], oc)))
show(Rf, "FULL SAMPLE"); show(Rt, "TRIMMED (drop n_total>50)")
Rf[, sample := "full"]; Rt[, sample := "trim50"]
fwrite(rbind(Rf, Rt), file.path(OUTDIR, "clean_iv", "decomp_chenroth_domains.csv"))
cat("\nwrote output/clean_iv/decomp_chenroth_domains.csv\n")
