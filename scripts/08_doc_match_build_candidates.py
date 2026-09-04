"""
08_doc_match_build_candidates.py
=================================

Stage 8: build per-document AI extraction payloads. One JSON file per
era-eligible APOSCRIPTA document, each containing the doc's text + a
candidate person shortlist drawn from the closed universe of named-
anchor-dynasty-assigned peerage whose lifespan intersects
[doc_year +/- 15].

Universe: era-eligible (lifespan 1050-1350) persons assigned to one of
the 21 named anchor dynasties. ~6,200 persons.

Per-doc filter: candidate's [birth, death] must overlap
[doc_year - 15, doc_year + 15]. (The +/-15 year window is the standard
"alive plus posthumous reference buffer" for medieval canon law cases.)

Inputs (in output/):
  named_dynasty_assignment.csv
  persons_imputed.csv
  aposcripta_per_doc.csv
  doc_matches_dedup.csv      (OPTIONAL: if missing, stratum=""
                              and n_regex_matches=0 for every doc;
                              regex matching is fully superseded by
                              the AI extraction in this pipeline)

Inputs (in ../data/):
  aposcripta.dataset.json

Outputs (in output/):
  reextract_full_doc_index.csv         one row per era-eligible doc
  batches_reextract/docs/doc_<id>.json one per-doc payload with
                                        shortlist (~115 KB each).
                                        ~2.7 GB total at 24,130 docs.

Downstream:
  09_doc_match_render_prompts.py reads docs/ + produces prompts_v3/
  10_doc_match_batch_submit.py reads prompts_v3/ + submits to API
"""
from __future__ import annotations
import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
DATA = ROOT / "data" / "raw"
BATCHES_DIR = OUT / "batches_reextract"
BATCHES_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = BATCHES_DIR / "docs"
DOCS_DIR.mkdir(exist_ok=True)

ERA_LO, ERA_HI = 1050, 1350
K_WINDOW = 15

# Doc-year filter for the candidate-overlap pool. Era is [1050, 1350];
# allow doc years within K_WINDOW * 2 (= 30y buffer) of either edge.
DOC_YEAR_LO, DOC_YEAR_HI = 1020, 1380

# Char cap on the Latin transcription. ~3K tokens for medieval Latin at
# ~4 chars/token. Truncated text is flagged in the payload.
TRANSCRIPTION_CHAR_CAP = 12000


# ---- Step 1: build candidate universe ---------------------------------
print("Loading named_dynasty_assignment ...", flush=True)
dyn_assign: dict[str, str] = {}
with open(OUT / "named_dynasty_assignment.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["dynasty"]:
            dyn_assign[r["id"]] = r["dynasty"]
print(f"  assigned persons: {len(dyn_assign):,}")

print("Loading persons_imputed (era-filter) ...", flush=True)
candidates: list[dict] = []
# UTF-8 throughout: persons_imputed.csv is written as UTF-8 by
# 01_impute.py (the historical 5_15 file was latin-1 but the
# replication-package version is UTF-8 to match the rest of the pipeline).
with open(OUT / "persons_imputed.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["id"] not in dyn_assign:
            continue
        try:
            b = int(r["birth"])
            d = int(r["death"])
        except (ValueError, TypeError):
            continue
        if b <= ERA_HI and d >= ERA_LO:
            candidates.append({
                "id":   r["id"],
                "name": r["name"],
                "sex":  r["sex"],
                "b":    b,
                "d":    d,
                "dyn":  dyn_assign[r["id"]],
            })
print(f"  era-eligible candidates: {len(candidates):,}")


# ---- Step 2: load APOSCRIPTA raw text ---------------------------------
print("Loading APOSCRIPTA raw ...", flush=True)
with open(DATA / "aposcripta.dataset.json", encoding="utf-8") as f:
    raw = json.load(f)
items = raw["datasetItems"]
print(f"  records: {len(items):,}")


def clean(s):
    if not s:
        return ""
    if isinstance(s, list):
        s = " | ".join(clean(x) for x in s if x)
    if isinstance(s, dict):
        s = " | ".join(f"{k}={clean(v)}" for k, v in s.items() if v)
    if not isinstance(s, str):
        s = str(s)
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


doc_text: dict[str, dict] = {}
for rec in items:
    rid = str(rec.get("itemIdTELMA", ""))
    if not rid:
        continue
    doc_text[rid] = {
        "analyse":       clean(rec.get("analyse", "")),
        "transcription": clean(rec.get("transcription", "")),
        "pope":          rec.get("pape", ""),
    }
print(f"  doc text records: {len(doc_text):,}")


# ---- Step 3: doc metadata (year + region) -----------------------------
doc_meta: dict[str, dict] = {}
n_outside_era = 0
with open(OUT / "aposcripta_per_doc.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        try:
            yr = int(r["year"])
        except (ValueError, TypeError):
            continue
        if yr < DOC_YEAR_LO or yr > DOC_YEAR_HI:
            n_outside_era += 1
            continue
        doc_meta[r["id"]] = {
            "year":         yr,
            "year_imputed": r.get("year_imputed", "0") == "1",
            "region":       r.get("region", ""),
            "genre":        r.get("genre", ""),
        }
print(f"  docs with year in [{DOC_YEAR_LO}, {DOC_YEAR_HI}]: "
      f"{len(doc_meta):,}")
print(f"  docs excluded (year outside era):                  "
      f"{n_outside_era:,}")


# ---- Step 4: legacy regex match counts (optional) ---------------------
# In 5_15 this drove pilot-mode stratification (500 random + 500
# regex-positive). The full-corpus mode (here) just labels each doc as
# regex_pos vs random in the index CSV; the labels are not consumed
# downstream. The file is OPTIONAL in this replication package.
regex_n: dict[str, int] = {}
regex_pos: set[str] = set()
regex_dedup_path = OUT / "doc_matches_dedup.csv"
if regex_dedup_path.exists():
    with open(regex_dedup_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            regex_n[r["doc_id"]] = regex_n.get(r["doc_id"], 0) + 1
    regex_pos = set(regex_n.keys())
    print(f"  regex-positive docs (legacy):  {len(regex_pos):,}")
else:
    print(f"  doc_matches_dedup.csv not found; stratum / n_regex_matches "
          f"will be blank in the index.")


# ---- Step 5: doc selection --------------------------------------------
all_doc_ids = sorted(doc_meta.keys())
strat_map = {did: ("regex_pos" if did in regex_pos else "random")
             for did in all_doc_ids}
print(f"\n  total era-eligible docs: {len(all_doc_ids):,}")
if regex_pos:
    print(f"    regex_pos: "
          f"{sum(1 for d in all_doc_ids if strat_map[d]=='regex_pos'):,}")
    print(f"    random:    "
          f"{sum(1 for d in all_doc_ids if strat_map[d]=='random'):,}")


# ---- Write doc index --------------------------------------------------
idx_out = OUT / "reextract_full_doc_index.csv"
with open(idx_out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["doc_id", "stratum", "year", "year_imputed", "region",
                "n_regex_matches"])
    for did in all_doc_ids:
        m = doc_meta[did]
        w.writerow([did, strat_map[did], m["year"], int(m["year_imputed"]),
                    m["region"], regex_n.get(did, 0)])
print(f"Wrote {idx_out.name}")


# ---- Step 6: write per-doc payloads -----------------------------------
def filter_candidates(year: int) -> list[dict]:
    lo, hi = year - K_WINDOW, year + K_WINDOW
    return [c for c in candidates if c["b"] <= hi and c["d"] >= lo]


def build_payload(did: str) -> dict:
    m = doc_meta[did]
    txt = doc_text.get(did, {})
    full_transcription = txt.get("transcription", "")
    transcription = full_transcription[:TRANSCRIPTION_CHAR_CAP]
    truncated = len(full_transcription) > TRANSCRIPTION_CHAR_CAP
    shortlist = filter_candidates(m["year"])
    return {
        "doc_id":                  did,
        "stratum":                 strat_map[did],
        "year":                    m["year"],
        "year_imputed":            m["year_imputed"],
        "region":                  m["region"],
        "genre":                   m["genre"],
        "pope":                    txt.get("pope", ""),
        "analyse":                 txt.get("analyse", ""),
        "transcription":           transcription,
        "transcription_truncated": truncated,
        "n_candidates":            len(shortlist),
        "candidates":              shortlist,
    }


print(f"\nWriting {len(all_doc_ids):,} per-doc payloads to {DOCS_DIR} ...")
shortlist_sizes: list[int] = []
transcription_truncated_count = 0
for i, did in enumerate(all_doc_ids, start=1):
    payload = build_payload(did)
    if payload["transcription_truncated"]:
        transcription_truncated_count += 1
    shortlist_sizes.append(payload["n_candidates"])
    per_doc = DOCS_DIR / f"doc_{did}.json"
    with open(per_doc, "w", encoding="utf-8") as pdf:
        json.dump(payload, pdf, ensure_ascii=False, indent=None)
    if i % 2500 == 0:
        print(f"  ... {i:,}/{len(all_doc_ids):,} written")


# ---- Stats ------------------------------------------------------------
sl = sorted(shortlist_sizes)
n = len(sl)
print(f"\n=== Shortlist size distribution ===")
print(f"  N docs:                       {n}")
print(f"  min:                          {sl[0]}")
print(f"  p25:                          {sl[n // 4]}")
print(f"  median:                       {sl[n // 2]}")
print(f"  p75:                          {sl[3 * n // 4]}")
print(f"  max:                          {sl[-1]}")
print(f"  mean:                         {sum(sl) / n:.0f}")
print(f"  transcription-truncated docs: {transcription_truncated_count}")
print(f"\nDone. {n:,} per-doc payloads in {DOCS_DIR}")
