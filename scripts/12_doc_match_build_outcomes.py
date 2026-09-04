"""
12_doc_match_build_outcomes.py
===============================

Stage 12: build the foundational match-level CSV (doc x person, with all
metadata) PLUS a family of subset person-summary CSVs for genre/subject-
specific IV analysis.

Reads: build_cache_matches.csv (written by stage 11)
       aposcripta_per_doc.csv  (written by stage 7)

Writes (in output/):
  doc_matches_ai_extracted_high.csv           match-level, one row
                                              per (doc, person) at
                                              confidence='high'
  person_summary_ai_extracted_mandement.csv   person summary using
                                              only matches from
                                              mandement docs
                                              (is_mandement=1)
  person_summary_ai_extracted_mandement_no_marriage.csv
                                              mandement docs AND
                                              excluding matches that
                                              carry the 'marriage'
                                              subject tag
  person_summary_ai_extracted_subject_<X>.csv per-subject outcome
                                              where n_matches counts
                                              only matches whose
                                              inferred_subjects
                                              includes subject X.
                                              One file per subject.

All person-summary outputs share the schema of
person_summary_ai_extracted_high.csv so downstream R scripts can read
them with --input_csv.

Prerequisite: stage 11 must have been run (writes build_cache_matches.csv).
"""
from __future__ import annotations
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
CACHE_PATH = OUT / "build_cache_matches.csv"

SUBJECTS = ["marriage", "excommunication", "inheritance", "dispute",
            "crusade", "clerical_discipline", "ecclesiastical_property"]
ROLES = ["beneficiary", "requestor", "subject_or_mention", "addressee"]


def load_doc_metadata() -> dict:
    out = {}
    with open(OUT / "aposcripta_per_doc.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["id"]] = {
                "year": (int(r["year"])
                         if r.get("year", "").isdigit() else None),
                "pope": r.get("pape", ""),
                "region": r.get("region", ""),
                "genre": r.get("genre", ""),
                "is_mandement": r.get("is_mandement", "0") == "1",
                "is_marriage_doc": r.get("is_marriage", "0") == "1",
            }
    return out


def load_cache() -> list[dict]:
    if not CACHE_PATH.exists():
        print(f"ERROR: cache not found: {CACHE_PATH}")
        print(f"Run 11_doc_match_build_person_summary.py first.")
        sys.exit(1)
    out = []
    with open(CACHE_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("is_hallucination", "False") == "True":
                continue
            if r.get("inferred_subjects"):
                r["subject_set"] = set(r["inferred_subjects"].split(";"))
            else:
                r["subject_set"] = set()
            out.append(r)
    return out


def aggregate_per_person(matches: list[dict],
                         doc_year_lookup: dict) -> dict:
    by_person = defaultdict(lambda: {
        "n_matches": 0, "docs": set(), "doc_years": [],
        **{f"n_{s}": 0 for s in SUBJECTS},
        **{f"n_role_{r}": 0 for r in ROLES},
    })
    for m in matches:
        pid = m["person_id"]
        rec = by_person[pid]
        rec["n_matches"] += 1
        rec["docs"].add(m["doc_id"])
        y = doc_year_lookup.get(m["doc_id"])
        if y is not None:
            rec["doc_years"].append(y)
        for s in m.get("subject_set", set()):
            if s in SUBJECTS:
                rec[f"n_{s}"] += 1
        role = (m.get("role") or "").strip()
        if role in ROLES:
            rec[f"n_role_{role}"] += 1
    return by_person


def write_summary(by_person: dict, out_path: Path):
    fieldnames = (
        ["person_id", "n_matches_ai_extracted", "n_unique_docs_ai_extracted",
         "median_doc_year_ai_extracted", "mean_doc_year_ai_extracted"]
        + [f"n_{s}_ai_extracted" for s in SUBJECTS]
        + [f"n_role_{r}_ai_extracted" for r in ROLES]
    )
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fieldnames)
        for pid in sorted(by_person.keys()):
            rec = by_person[pid]
            ys = sorted(rec["doc_years"])
            if ys:
                median_y = ys[len(ys) // 2]
                mean_y = round(sum(ys) / len(ys))
            else:
                median_y = ""
                mean_y = ""
            row = [pid, rec["n_matches"], len(rec["docs"]),
                   median_y, mean_y,
                   *(rec[f"n_{s}"] for s in SUBJECTS),
                   *(rec[f"n_role_{r}"] for r in ROLES)]
            w.writerow(row)


def main():
    print("Loading doc metadata + match cache ...")
    doc_meta = load_doc_metadata()
    matches = load_cache()
    doc_year_lookup = {did: m["year"] for did, m in doc_meta.items()
                       if m["year"] is not None}
    print(f"  doc metadata records:        {len(doc_meta):,}")
    print(f"  matches (post-closed-set):   {len(matches):,}")

    high_matches = []
    for m in matches:
        if m.get("confidence") != "high":
            continue
        meta = doc_meta.get(m["doc_id"], {})
        m["doc_year"] = meta.get("year")
        m["doc_pope"] = meta.get("pope", "")
        m["doc_region"] = meta.get("region", "")
        m["doc_genre"] = meta.get("genre", "")
        m["doc_is_mandement"] = meta.get("is_mandement", False)
        high_matches.append(m)
    print(f"  high-confidence matches:     {len(high_matches):,}")

    # 1. Match-level CSV
    out_match = OUT / "doc_matches_ai_extracted_high.csv"
    match_cols = ["doc_id", "doc_year", "doc_pope", "doc_region",
                  "doc_genre", "doc_is_mandement", "person_id",
                  "confidence", "role", "inferred_subjects",
                  "quoted_latin"]
    with open(out_match, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(match_cols)
        for m in high_matches:
            w.writerow([
                m["doc_id"], m.get("doc_year") or "",
                m.get("doc_pope", ""), m.get("doc_region", ""),
                m.get("doc_genre", ""),
                "1" if m.get("doc_is_mandement") else "0",
                m["person_id"], m.get("confidence", ""),
                m.get("role", ""),
                ";".join(sorted(m.get("subject_set", set()))),
                (m.get("quoted_latin") or "")[:200],
            ])
    print(f"Wrote {out_match.name} ({len(high_matches):,} rows)")

    # 2. Mandement-only
    mand_matches = [m for m in high_matches if m.get("doc_is_mandement")]
    print(f"\nMandement subset: {len(mand_matches):,} matches "
          f"({100*len(mand_matches)/max(len(high_matches), 1):.1f}% of high-conf)")
    by_p = aggregate_per_person(mand_matches, doc_year_lookup)
    out = OUT / "person_summary_ai_extracted_mandement.csv"
    write_summary(by_p, out)
    print(f"  Wrote {out.name} ({len(by_p):,} persons)")

    # 3. Mandement-only minus marriage-tagged
    mand_nm_matches = [m for m in mand_matches
                       if "marriage" not in m.get("subject_set", set())]
    print(f"\nMandement minus marriage: {len(mand_nm_matches):,} matches")
    by_p = aggregate_per_person(mand_nm_matches, doc_year_lookup)
    out = OUT / "person_summary_ai_extracted_mandement_no_marriage.csv"
    write_summary(by_p, out)
    print(f"  Wrote {out.name} ({len(by_p):,} persons)")

    # 4. Per-subject outcomes
    print(f"\nPer-subject outcomes:")
    for subj in SUBJECTS:
        sub_matches = [m for m in high_matches
                       if subj in m.get("subject_set", set())]
        by_p = aggregate_per_person(sub_matches, doc_year_lookup)
        out = OUT / f"person_summary_ai_extracted_subject_{subj}.csv"
        write_summary(by_p, out)
        print(f"  {subj:<28} {len(sub_matches):>5} matches  "
              f"{len(by_p):>4} persons  -> {out.name}")

    print("\nDone.")


if __name__ == "__main__":
    main()
