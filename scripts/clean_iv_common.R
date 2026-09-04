# clean_iv_common.R
# =================
# Shared machinery for the CLEANED-UP headline dispute IV and its
# robustness battery (scripts 46_*, 47_*, 48_*).  Implements the exact
# specification requested for the SSRN draft:
#
#   endogenous : focal n_dyn_<hop>hop      (4-hop dynastic kin-reach)
#   instrument : mother_n_dyn_<hop>hop     (mother's pre-natal reach)
#   FE         : dynasty + death-decade + focal title-rank
#   focal X    : log(deg); log(1+ N within <hop> hops);
#                log(1+ non-outcome-class in-window appearances)  [visibility]
#   ancestor X : for mother, father, MGF -
#                  title-rank FE;
#                  log(1+ N within <hop> hops);
#                  log(1+ in-window DISPUTE appearances);
#                  log(1+ in-window NON-DISPUTE appearances);
#                  log(1+ pre-natal degree)           [node log-degree]
#   reach X    : FATHER and MGF <hop>-hop reach (levels).  Mother's reach
#                is the instrument, so it is NOT a control.
#   outcome    : in-window [1100,1300] document-class count, log(1+n) or
#                the extensive 1{n>0}.
#
# CLEAN-UP vs the canonical 19_/iv_common.R pipeline:
#   1. SAMPLE = anchored nobles whose LIFESPAN OVERLAPS [1100,1300]
#      (birth<=1300 & death>=1100), not the broader in_anchored_universe
#      flag (which also pulls in out-of-window 1-hop kin: 2,762 -> 2,167).
#   2. DOCUMENT COUNTS (focal outcomes AND ancestor controls) restricted
#      to letters ISSUED in [1100,1300]  (clean_iv/person_doc_counts_inwin.csv).
#   3. Parental documentary prominence SPLIT into dispute + non-dispute
#      (canonical used a single total n_matches).
#   4. FATHER's reach added to the control set (canonical had MGF only).
#   5. FOCAL "N within k hops" (size) added (clean_iv/focal_node_size.csv).
#   6. FOCAL non-outcome-class visibility control added to the headline.
#
# Before sourcing, the caller must set OUTDIR <- file.path(ROOT,"output").

suppressPackageStartupMessages({library(data.table); library(fixest)})

.ic <- new.env()
rc  <- function(name) fread(file = file.path(OUTDIR, name))
rcc <- function(name) fread(file = file.path(OUTDIR, "clean_iv", name))

SUBJECTS_IC <- c("marriage", "excommunication", "inheritance", "dispute",
                 "crusade", "clerical_discipline", "ecclesiastical_property")

ic_load_shared <- function() {
  dc <- rcc("person_doc_counts_inwin.csv")
  .ic$doc_counts <- dc
  .ic$node_size  <- rcc("focal_node_size.csv")[
    , .(person_id, n_nodes_3hop, n_nodes_4hop)]
  .ic$persons <- rc("persons_imputed.csv")[, .(id, name)]
  # canonical ALL-YEAR documentary totals (for the paper-baseline decomposition)
  ah <- rc("person_summary_ai_extracted_high.csv")
  .ic$ai_high <- ah[, .(person_id,
                        n_matches_all = n_matches_ai_extracted,
                        n_disp_all    = n_dispute_ai_extracted)]
  # father's INCREMENTAL pre-natal reach |F\M| (50_father_increment.py),
  # the default father-reach control (orthogonal to the maternal instrument)
  fi <- file.path(OUTDIR, "clean_iv", "father_increment.csv")
  .ic$father_inc <- if (file.exists(fi))
    fread(fi)[, .(person_id, father_extra_3hop = f_extra3,
                  father_extra_4hop = f_extra4)] else NULL
  pop <- file.path(OUTDIR, "papacy_timeline.csv")
  .ic$popes <- if (file.exists(pop)) fread(pop) else NULL
  invisible(TRUE)
}

ic_title_rank <- function(nm) {
  if (is.na(nm)) return(NA_integer_)
  s <- tolower(nm)
  if (grepl("emperor|empress|imperator|imperatrix", s)) return(5L)
  if (grepl("\\bking\\b|\\bqueen\\b|\\broi\\b|\\breine\\b|\\brey de\\b|\\brei de\\b|\\bre di\\b|\\bkönig\\b", s)) return(4L)
  if (grepl("\\bduke\\b|\\bduc\\b|\\bherzog\\b|\\bduca\\b|\\bduque\\b", s)) return(3L)
  if (grepl("\\bcount\\b|\\bearl\\b|\\bcomte\\b|\\bgraf\\b|\\bconte\\b|\\bmarchese\\b|\\bmarkgraf\\b|\\bconde\\b", s)) return(2L)
  if (grepl("\\blord\\b|\\bsieur\\b|\\bbaron\\b|\\bvicomte\\b|\\bsire\\b|\\bseigneur\\b|\\bsignore\\b|\\bvoivode\\b", s)) return(1L)
  return(0L)
}
ic_title_rank_vec <- function(v) vapply(v, ic_title_rank, integer(1))

ic_year_to_pope <- function(year) {
  if (is.na(year) || is.null(.ic$popes)) return(NA_character_)
  cand <- .ic$popes[start_year <= year]
  if (nrow(cand) == 0) return(NA_character_)
  inr <- cand[end_year >= year]
  if (nrow(inr) > 0) return(inr[order(-start_year)][1]$pope_id)
  cand[order(-end_year)][1]$pope_id
}
ic_pope_vec <- function(v) vapply(v, ic_year_to_pope, character(1))

# ----------------------------------------------------------------------
# Build the clean analysis frame.
#   nw_file, iv_file : network_nodes_*.csv + mother_iv_*.csv (21-dyn or bloc)
#   universe : "lifespan" (HEADLINE: lifespan overlaps [1100,1300])
#              "anchored_flag" (comparison: the canonical in_anchored_universe)
# Returns one row per anchored node (both sexes); callers filter M + IV.
# ----------------------------------------------------------------------
# restrict_anchored: keep only persons in the 21-dynasty anchored set (so a
#   topology-labeled network file, e.g. patriline, can be run on the SAME
#   2,167 anchored sample for comparability) while the network file's own
#   `dynasty` column (e.g. patriline id) drives FE/clustering.
build_clean_df <- function(nw_file, iv_file, universe = "lifespan",
                           restrict_anchored = FALSE) {
  stopifnot(universe %in% c("lifespan", "anchored_flag"))
  nw <- rc(nw_file); iv <- rc(iv_file)
  net <- nw[!is.na(dynasty) & dynasty != "",
            .(person_id, deg, log_deg, n_dyn_3hop, n_dyn_4hop,
              cross_dyn_neighbors, birth, death, name, sex, dynasty)]
  df <- merge(net, iv, by = "person_id", all.x = TRUE)
  setDT(df)
  # fill parental cross-dynasty-tie counts (NA -> 0 for missing parent)
  for (cd in c("mother_cross_dyn", "father_cross_dyn", "mgf_cross_dyn"))
    if (cd %in% names(df)) df[is.na(get(cd)), (cd) := 0]
  # focal network SIZE (label-independent; valid for bloc labelings too)
  df <- merge(df, .ic$node_size, by = "person_id", all.x = TRUE)

  # ---- SAMPLE WINDOW ----
  if (universe == "lifespan") {
    df <- df[!is.na(birth) & !is.na(death) & birth <= 1300 & death >= 1100]
  } else {
    df <- df[in_anchored_universe == 1]
  }
  if (restrict_anchored) {
    anc <- rc("named_dynasty_assignment.csv")
    anc_ids <- anc[!is.na(dynasty) & dynasty != "", id]
    df <- df[person_id %in% anc_ids]
  }

  # ---- focal in-window document counts ----
  dc <- .ic$doc_counts
  df <- merge(df, dc[, .(person_id, focal_total = n_total_inwin,
                         focal_disp = n_dispute_inwin,
                         focal_nondisp = n_nondispute_inwin)],
              by = "person_id", all.x = TRUE)
  for (cc in c("focal_total", "focal_disp", "focal_nondisp"))
    df[is.na(get(cc)), (cc) := 0]
  # per-subject focal in-window counts (for the specificity panel)
  for (s in SUBJECTS_IC) {
    col <- paste0("n_", s, "_inwin")
    df <- merge(df, dc[, .(person_id, x = get(col))],
                by = "person_id", all.x = TRUE)
    setnames(df, "x", paste0("focal_", s))
    df[is.na(get(paste0("focal_", s))), (paste0("focal_", s)) := 0]
  }
  df[, ever_dispute := as.integer(focal_disp > 0)]
  df[, log_disp     := log1p(focal_disp)]
  df[, log_nondisp  := log1p(focal_nondisp)]
  df[, log_total    := log1p(focal_total)]

  # canonical ALL-YEAR focal counts (paper-baseline decomposition only)
  df <- merge(df, .ic$ai_high[, .(person_id, focal_total_all = n_matches_all,
                                  focal_disp_all = n_disp_all)],
              by = "person_id", all.x = TRUE)
  df[is.na(focal_total_all), focal_total_all := 0]
  df[is.na(focal_disp_all),  focal_disp_all  := 0]
  df[, log_disp_all := log1p(focal_disp_all)]

  df[, title_rank   := ic_title_rank_vec(name)]
  df[, death_decade := (death %/% 10) * 10]
  df[, sex := factor(sex, levels = c("M", "F", ""))]

  # focal size logs
  for (h in c(3L, 4L)) {
    raw <- sprintf("n_nodes_%dhop", h)
    if (!raw %in% names(df)) df[, (raw) := 0]
    df[is.na(get(raw)), (raw) := 0]
    df[, (sprintf("focal_log_n_nodes_%dhop", h)) := log1p(get(raw))]
  }

  # ---- ancestor controls ----
  pl <- .ic$persons
  for (who in c("mother", "father", "mgf")) {
    idc <- paste0(who, "_id")
    # title rank
    df <- merge(df, pl[, .(jid = id, jn = name)], by.x = idc, by.y = "jid",
                all.x = TRUE)
    setnames(df, "jn", paste0(who, "_name"))
    df[, (paste0(who, "_title_rank")) :=
         ic_title_rank_vec(get(paste0(who, "_name")))]
    df[is.na(get(paste0(who, "_title_rank"))),
       (paste0(who, "_title_rank")) := 0L]
    # pre-natal node log-degree
    pd <- paste0(who, "_pre_deg")
    if (!pd %in% names(df)) df[, (pd) := NA_real_]
    df[, (paste0(who, "_log_pre_deg")) := log1p(get(pd))]
    df[is.na(get(paste0(who, "_log_pre_deg"))),
       (paste0(who, "_log_pre_deg")) := 0]
    # N within k hops (size), pre-natal headcount
    for (h in c(3L, 4L)) {
      raw <- sprintf("%s_n_nodes_%dhop", who, h)
      if (!raw %in% names(df)) df[, (raw) := 0]
      df[is.na(get(raw)), (raw) := 0]
      df[, (sprintf("%s_log_n_nodes_%dhop", who, h)) := log1p(get(raw))]
    }
    # in-window dispute + non-dispute documentary prominence
    df <- merge(df, dc[, .(jid = person_id, jd = n_dispute_inwin,
                           jn = n_nondispute_inwin)],
                by.x = idc, by.y = "jid", all.x = TRUE)
    setnames(df, c("jd", "jn"),
             c(paste0(who, "_disp"), paste0(who, "_nondisp")))
    df[is.na(get(paste0(who, "_disp"))),    (paste0(who, "_disp")) := 0]
    df[is.na(get(paste0(who, "_nondisp"))), (paste0(who, "_nondisp")) := 0]
    df[, (paste0(who, "_log_disp"))    := log1p(get(paste0(who, "_disp")))]
    df[, (paste0(who, "_log_nondisp")) := log1p(get(paste0(who, "_nondisp")))]
    # in-window TOTAL documentary prominence (coding-neutral; the default
    # parental control now that the dispute/non-dispute split is dropped)
    df[, (paste0(who, "_log_total_inwin")) :=
         log1p(get(paste0(who, "_disp")) + get(paste0(who, "_nondisp")))]
    # canonical ALL-YEAR total prominence (paper-baseline decomposition)
    df <- merge(df, .ic$ai_high[, .(jid = person_id, jt = n_matches_all)],
                by.x = idc, by.y = "jid", all.x = TRUE)
    setnames(df, "jt", paste0(who, "_total_all"))
    df[is.na(get(paste0(who, "_total_all"))),
       (paste0(who, "_total_all")) := 0]
    df[, (paste0(who, "_log_total_all")) :=
         log1p(get(paste0(who, "_total_all")))]
  }

  # father + MGF reach (levels), both hops; mother reach stays the instrument
  for (who in c("father", "mgf")) {
    for (h in c(3L, 4L)) {
      raw <- sprintf("%s_n_dyn_%dhop", who, h)
      if (!raw %in% names(df)) df[, (raw) := NA_real_]
      df[, (sprintf("%s_reach_%dhop", who, h)) :=
           ifelse(is.na(get(raw)), 0, get(raw))]
    }
  }
  # father's INCREMENTAL reach |F\M| (default father control): the
  # dynasties father reaches that mother does NOT -- orthogonal to the
  # maternal instrument (cf. 50b: cor 0.72 -> -0.03, first-stage F 29 -> 54).
  if (!is.null(.ic$father_inc))
    df <- merge(df, .ic$father_inc, by = "person_id", all.x = TRUE)
  for (h in c(3L, 4L)) {
    col <- sprintf("father_extra_%dhop", h)
    if (!col %in% names(df)) df[, (col) := NA_real_]
    df[is.na(get(col)), (col) := 0]
  }

  if (!is.null(.ic$popes)) {
    df[, midlife_year := as.integer((birth + death) / 2)]
    df[, papacy := ic_pope_vec(midlife_year)]
    df[, papacy := ifelse(is.na(papacy), "NA_papacy", papacy)]
  }
  df[]
}

# Control RHS string.
#   hop          : 3 or 4 (selects reach, size, parental size)
#   time         : "decade" (headline) or "papacy"
#   dyn_fe       : include factor(dynasty)
#   visibility   : focal visibility control = log(1 + focal_total - focal_<class>)
#                  Pass the OUTCOME CLASS ("dispute","nondispute","total",
#                  or a subject); "total"/"" -> no visibility term.
# The visibility column must be precomputed on `dat` (see ic_set_visibility).
#   father_mode : "increment" (DEFAULT) uses |F\M| = father_extra_<hop>hop,
#                 orthogonal to the maternal instrument; "level" uses the
#                 raw father reach |F| (collinear); "none" drops it.
#   parental_doc : "total" (DEFAULT) controls each ancestor's in-window
#                  TOTAL documentary prominence (one term, coding-neutral);
#                  "split" controls dispute + non-dispute separately
#                  (the old first-pass-dependent form).
#   focal_size : include the focal's own log(1 + N within k hops). DEFAULT
#                FALSE -- it is a post-treatment COLLIDER (measured kin-network
#                size is driven by the focal's documentation/prominence, the
#                same latent that drives the outcome, AND is mechanically caused
#                by the maternal instrument; conditioning on it opens
#                Z -> [size] <- U -> Y). Ancestor (pre-natal) sizes are NOT
#                colliders and stay in.
clean_controls <- function(hop, time = "decade", dyn_fe = TRUE,
                           visibility = "dispute", father_mode = "increment",
                           parental_doc = "total", focal_size = FALSE) {
  time_fe <- if (time == "papacy") "factor(papacy)" else "factor(death_decade)"
  focal <- "log_deg"
  if (focal_size) focal <- c(focal, sprintf("focal_log_n_nodes_%dhop", hop))
  if (!visibility %in% c("total", "", "none"))
    focal <- c(focal, "focal_log_vis")
  anc <- c()
  for (who in c("mother", "father", "mgf")) {
    anc <- c(anc,
             sprintf("factor(%s_title_rank)", who),
             sprintf("%s_log_n_nodes_%dhop", who, hop))
    if (parental_doc == "split")
      anc <- c(anc, sprintf("%s_log_disp", who), sprintf("%s_log_nondisp", who))
    else
      anc <- c(anc, sprintf("%s_log_total_inwin", who))
    anc <- c(anc, sprintf("%s_log_pre_deg", who))
  }
  reach <- sprintf("mgf_reach_%dhop", hop)
  if (father_mode == "increment")
    reach <- c(sprintf("father_extra_%dhop", hop), reach)
  else if (father_mode == "level")
    reach <- c(sprintf("father_reach_%dhop", hop), reach)
  rhs <- c("factor(title_rank)", time_fe, focal, anc, reach)
  if (dyn_fe) rhs <- c(rhs, "factor(dynasty)")
  paste(rhs, collapse = " + ")
}

# Attach focal_log_vis = log(1 + focal_total - focal_<class>) for the
# given outcome class.  Mutates `dat` by reference.
ic_set_visibility <- function(dat, outcome_class) {
  col <- paste0("focal_", outcome_class)
  if (!col %in% names(dat)) { dat[, focal_log_vis := 0]; return(invisible()) }
  dat[, focal_log_vis := log1p(pmax(0, focal_total - get(col)))]
  invisible()
}

# 2SLS fit. outcome is a column name; endogenous/instrument selected by hop.
ic_fit_iv <- function(outcome, hop, controls, dat) {
  endo <- sprintf("n_dyn_%dhop", hop)
  inst <- sprintf("mother_n_dyn_%dhop", hop)
  rhs <- sprintf("%s ~ %s | %s ~ %s", outcome, controls, endo, inst)
  tryCatch(feols(as.formula(rhs), data = dat, cluster = ~ dynasty),
           error = function(e) NULL)
}
# reduced form (instrument enters directly) - for the permutation placebo
ic_fit_reduced <- function(outcome, hop, controls, dat) {
  inst <- sprintf("mother_n_dyn_%dhop", hop)
  rhs <- sprintf("%s ~ %s + %s", outcome, inst, controls)
  tryCatch(feols(as.formula(rhs), data = dat, cluster = ~ dynasty),
           error = function(e) NULL)
}

ic_extract <- function(m, hop, label = NA_character_) {
  tname <- sprintf("fit_n_dyn_%dhop", hop)
  if (is.null(m)) return(data.table(label = label, beta = NA_real_,
                                     SE = NA_real_, p = NA_real_,
                                     F_first = NA_real_, N = NA_integer_))
  ct <- as.data.frame(coeftable(m)); ct$term <- rownames(ct); setDT(ct)
  pcol <- intersect(c("Pr(>|t|)", "Pr(>|z|)"), names(ct))[1]
  setnames(ct, pcol, "p"); setnames(ct, "Std. Error", "SE")
  r <- ct[term == tname]
  inst <- sprintf("mother_n_dyn_%dhop", hop)
  fs <- tryCatch(summary(m, stage = 1), error = function(e) NULL)
  Ff <- NA_real_
  if (!is.null(fs)) {
    fst <- as.data.frame(coeftable(fs)); fst$term <- rownames(fst); setDT(fst)
    tr <- fst[term == inst]
    if (nrow(tr) > 0) Ff <- (tr$Estimate / tr[["Std. Error"]])^2
  }
  data.table(label = label, beta = r$Estimate, SE = r$SE, p = r$p,
             F_first = Ff, N = nobs(m))
}
