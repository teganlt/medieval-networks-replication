# 148_conflict_prone_build.R
# ==========================
# Conflict-prone maternal-family flags (8/26; specified ex ante on
# structural-legal grounds, then tested):
#   H1  mother has >= 2 recorded husbands (remarriage entanglements)
#   H2  only sororal nephews: MGF has no recorded sons AND at least one
#       sister of the mother has a recorded son (a rival sister-line)
#   H3  a brother of the MGF provably alive at the focal's birth
#       (recorded death >= birth year, or a child of his born after it)
#   cp2 = union. Full 2,195 frame; G-dependent flags are 0 when the MGF is
#   unknown (conservative dilution). Recorded dates only for the H3 proofs.
# Out: output/clean_iv/conflict_prone_v2_flags.csv
# Analysis/emitter: 149_conflict_prone_headline.R
# CLI: Rscript scripts/148_conflict_prone_build.R [<ROOT>]

args <- commandArgs(trailingOnly = TRUE)
ROOT <- if (length(args) >= 1 && nzchar(args[1])) args[1] else "."
OUTDIR <- file.path(ROOT, "output")
suppressPackageStartupMessages(library(data.table))

df <- fread(file.path(OUTDIR, "clean_iv", "unified_frame.csv"))[, .(person_id, mother_id, mgf_id, birth)]
raw <- fread(file.path(OUTDIR, "persons.csv"))[, .(id, rb = suppressWarnings(as.numeric(birth)),
                                                   rd = suppressWarnings(as.numeric(death)))]
imp <- fread(file.path(OUTDIR, "persons_imputed.csv"))[, .(id, csex = sex)]
pp <- fread(file.path(OUTDIR, "parent_pairs.csv"), colClasses = "character"); setnames(pp, c("p", "c"))
sp <- fread(file.path(OUTDIR, "spouse_pairs.csv"), colClasses = "character"); setnames(sp, c("a", "b"))

nsp <- rbind(sp[, .(id = a)], sp[, .(id = b)])[, .N, by = id]
rbm <- setNames(raw$rb, raw$id); rdm <- setNames(raw$rd, raw$id)
sexm <- setNames(imp$csex, imp$id)
kids <- split(pp$c, pp$p); pars <- split(pp$p, pp$c)

df <- merge(df, nsp[, .(mother_id = id, m_nsp = N)], by = "mother_id", all.x = TRUE)
df[is.na(m_nsp), m_nsp := 0]
df[, H1 := as.integer(m_nsp >= 2)]

B <- ifelse(is.na(rbm[df$person_id]), df$birth, rbm[df$person_id])
h2 <- integer(nrow(df)); h3 <- integer(nrow(df))
for (i in seq_len(nrow(df))) {
  G <- df$mgf_id[i]; M <- df$mother_id[i]
  if (is.na(G) || G == "") next
  gk <- kids[[G]]
  if (is.null(gk)) next
  sons <- gk[sexm[gk] == "M" & !is.na(sexm[gk])]
  if (length(sons) == 0) {
    sis <- setdiff(gk[sexm[gk] == "F" & !is.na(sexm[gk])], M)
    for (s in sis) {
      sk <- kids[[s]]
      if (!is.null(sk) && any(sexm[sk] == "M", na.rm = TRUE)) { h2[i] <- 1L; break }
    }
  }
  gg <- pars[[G]]; gg <- gg[sexm[gg] == "M" & !is.na(sexm[gg])]
  if (length(gg)) {
    bros <- setdiff(kids[[gg[1]]], G); bros <- bros[sexm[bros] == "M" & !is.na(sexm[bros])]
    for (b in bros) {
      alive <- (!is.na(rdm[b]) && !is.na(B[i]) && rdm[b] >= B[i])
      if (!alive) { bk <- kids[[b]]; if (!is.null(bk)) alive <- any(!is.na(rbm[bk]) & rbm[bk] >= B[i]) }
      if (isTRUE(alive)) { h3[i] <- 1L; break }
    }
  }
}
df[, `:=`(H2 = h2, H3 = h3)]
df[, cp2 := as.integer(H1 == 1 | H2 == 1 | H3 == 1)]
fwrite(df[, .(person_id, H1, H2, H3, cp2)], file.path(OUTDIR, "clean_iv", "conflict_prone_v2_flags.csv"))
cat(sprintf("wrote conflict_prone_v2_flags.csv: H1=%d H2=%d H3=%d union=%d of %d (%.1f%%)\n",
            sum(df$H1), sum(df$H2), sum(df$H3), sum(df$cp2), nrow(df), 100 * mean(df$cp2)))
