"""
11_doc_match_build_person_summary.py
=====================================

Stage 11: aggregate the Sonnet-batch verdicts into per-person outcome
tables.

Pipeline steps (in order):
  1. CLOSED-SET FILTER: drop any match whose person_id is not in the
     doc payload's candidates list (silently drops the ~0.14%
     hallucinations).
  2. CONFIDENCE FILTER: split into two outcome tracks
       - confidence='high' only        -> primary
       - confidence in {'high','medium'} -> sensitivity
  3. AGGREGATE per person:
       - n_matches, n_unique_docs
       - mean/median doc-year
       - per-subject counts (marriage, excommunication, inheritance,
                              dispute, crusade, clerical_discipline,
                              ecclesiastical_property)
       - per-role counts (beneficiary, requestor, subject_or_mention,
                          addressee)

Inputs:
  output/aposcripta_per_doc.csv
  output/batches_reextract/docs/doc_<id>.json          (for closed-set check)
  output/batches_reextract/verdicts_sonnet-4-6/        (all verdicts)

Outputs (in output/):
  person_summary_ai_extracted_high.csv         (primary)
  person_summary_ai_extracted_high_medium.csv  (sensitivity)
  ai_extracted_dropped_records.csv             (hallucination audit)
  build_cache_matches.csv                      (intermediate; reused by stage 12)

Modes:
  python 11_doc_match_build_person_summary.py
      DEFAULT: full rebuild from scratch. Idempotent. ~10-20 min over
      24K verdicts on cloud-synced storage (much faster on local disk). Always writes the cache
      so stage 12 can read it.

  python 11_doc_match_build_person_summary.py --incremental
      DEV-MODE: uses build_manifest.csv to skip verdict files already
      processed whose mtime is unchanged. ~10x faster for milestone
      snapshots during development. Safe to delete the cache files
      to force a fresh rebuild.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
DOCS = OUT / "batches_reextract" / "docs"
VERDICTS = OUT / "batches_reextract" / "verdicts_sonnet-4-6"

# Cache files (always written, regardless of --incremental flag)
MANIFEST_PATH = OUT / "build_manifest.csv"      # verdict_file -> mtime
CACHE_PATH    = OUT / "build_cache_matches.csv"  # parsed records

SUBJECTS = ["marriage", "excommunication", "inheritance", "dispute",
            "crusade", "clerical_discipline", "ecclesiastical_property"]
ROLES = ["beneficiary", "requestor", "subject_or_mention", "addressee"]

CACHE_FIELDS = ["verdict_file", "doc_id", "person_id", "confidence",
                "role", "inferred_subjects", "is_hallucination",
                "quoted_latin"]


def load_payload(did):
    return json.load(open(DOCS / f"doc_{did}.json", encoding="utf-8"))


def load_doc_years() -> dict[str, int]:
    out = {}
    with open(OUT / "aposcripta_per_doc.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[r["id"]] = int(r["year"])
            except (ValueError, TypeError):
                pass
    return out


_DOC_YEAR = load_doc_years()


def aggregate(matches: list[dict]) -> dict:
    """Aggregate match records by person_id."""
    by_person = defaultdict(lambda: {
        "n_matches": 0,
        "docs": set(),
        "doc_years": [],
        **{f"n_{s}": 0 for s in SUBJECTS},
        **{f"n_role_{r}": 0 for r in ROLES},
    })
    for m in matches:
        pid = m["person_id"]
        rec = by_person[pid]
        rec["n_matches"] += 1
        rec["docs"].add(m["doc_id"])
        yr = _DOC_YEAR.get(m["doc_id"])
        if yr is not None:
            rec["doc_years"].append(yr)
        subs = m.get("inferred_subjects") or []
        if isinstance(subs, str):
            subs = [s.strip() for s in subs.split(";") if s.strip()]
        for s in subs:
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
            row = [
                pid, rec["n_matches"], len(rec["docs"]),
                median_y, mean_y,
                *(rec[f"n_{s}"] for s in SUBJECTS),
                *(rec[f"n_role_{r}"] for r in ROLES),
            ]
            w.writerow(row)


def parse_verdict_file(vf: Path) -> tuple[list[dict], list[dict], int]:
    """Parse one verdicts JSONL. Returns (kept, dropped, n_summaries)."""
    did = vf.stem.removeprefix("verdicts_")
    payload = load_payload(did)
    valid_ids = {c["id"] for c in payload.get("candidates", [])}
    kept, dropped, n_sum = [], [], 0
    vf_name = vf.name
    for line in open(vf, encoding="utf-8"):
        ln = line.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("_summary"):
            n_sum += 1
            continue
        if "person_id" not in rec:
            continue
        rec.setdefault("doc_id", did)
        rec["verdict_file"] = vf_name
        if rec["person_id"] not in valid_ids:
            rec["is_hallucination"] = True
            dropped.append(rec)
        else:
            rec["is_hallucination"] = False
            kept.append(rec)
    return kept, dropped, n_sum


def load_cache() -> list[dict]:
    if not CACHE_PATH.exists():
        return []
    out = []
    with open(CACHE_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["is_hallucination"] = r.get("is_hallucination",
                                            "False") == "True"
            if r.get("inferred_subjects"):
                r["inferred_subjects"] = r["inferred_subjects"].split(";")
            else:
                r["inferred_subjects"] = []
            out.append(r)
    return out


def save_cache(records: list[dict]) -> None:
    with open(CACHE_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CACHE_FIELDS,
                           extrasaction="ignore")
        w.writeheader()
        for r in records:
            row = dict(r)
            subs = row.get("inferred_subjects") or []
            if isinstance(subs, list):
                row["inferred_subjects"] = ";".join(subs)
            row["is_hallucination"] = str(bool(row.get("is_hallucination")))
            row["quoted_latin"] = (row.get("quoted_latin") or "")[:200]
            w.writerow(row)


def load_manifest() -> dict[str, float]:
    if not MANIFEST_PATH.exists():
        return {}
    out = {}
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[r["verdict_file"]] = float(r["mtime"])
            except (ValueError, TypeError):
                pass
    return out


def save_manifest(manifest: dict[str, float]) -> None:
    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["verdict_file", "mtime"])
        for vf_name in sorted(manifest.keys()):
            w.writerow([vf_name, manifest[vf_name]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--incremental", action="store_true",
                    help="Dev-mode: skip unchanged verdict files using "
                         "the manifest cache. Default (no flag) is full "
                         "rebuild, the canonical replication pipeline.")
    args = ap.parse_args()
    print(f"Mode: "
          f"{'INCREMENTAL (dev)' if args.incremental else 'FULL REBUILD (canonical)'}")

    verdict_files = sorted(VERDICTS.glob("verdicts_*.jsonl"))
    disk_state = {vf.name: vf.stat().st_mtime for vf in verdict_files}

    all_matches: list[dict] = []
    dropped: list[dict] = []
    n_summaries = 0

    if args.incremental:
        cached_records = load_cache()
        manifest = load_manifest()

        on_disk_names = set(disk_state.keys())
        in_manifest = set(manifest.keys())
        new_files = on_disk_names - in_manifest
        removed_files = in_manifest - on_disk_names
        unchanged_files = set()
        modified_files = set()
        for name in on_disk_names & in_manifest:
            if abs(disk_state[name] - manifest[name]) < 1.0:
                unchanged_files.add(name)
            else:
                modified_files.add(name)

        print(f"  verdict files on disk:      {len(on_disk_names):,}")
        print(f"  cached (unchanged):         {len(unchanged_files):,}")
        print(f"  new (will process):         {len(new_files):,}")
        print(f"  modified (will reprocess):  {len(modified_files):,}")
        print(f"  removed (will drop):        {len(removed_files):,}")

        to_reparse_names = new_files | modified_files
        kept_cache = [r for r in cached_records
                      if r["verdict_file"] in unchanged_files]
        new_parsed: list[dict] = []
        for vf in verdict_files:
            if vf.name not in to_reparse_names:
                continue
            kept_v, dropped_v, _ = parse_verdict_file(vf)
            for r in kept_v:
                new_parsed.append(r)
            for r in dropped_v:
                new_parsed.append(r)

        combined_cache = kept_cache + new_parsed
        n_summaries = len(on_disk_names)
        all_matches = [r for r in combined_cache
                       if not r["is_hallucination"]]
        dropped     = [r for r in combined_cache
                       if r["is_hallucination"]]
    else:
        # Full rebuild (canonical pipeline)
        combined_cache: list[dict] = []
        for vf in verdict_files:
            kept_v, dropped_v, n_sum_v = parse_verdict_file(vf)
            all_matches.extend(kept_v)
            dropped.extend(dropped_v)
            n_summaries += n_sum_v
            combined_cache.extend(kept_v)
            combined_cache.extend(dropped_v)

    # ALWAYS persist cache + manifest (stage 12 reads the cache).
    save_cache(combined_cache)
    save_manifest({name: disk_state[name] for name in disk_state})

    print(f"\nVerdicts loaded:")
    print(f"  total docs:                  {n_summaries}")
    print(f"  total raw matches:           {len(all_matches) + len(dropped)}")
    print(f"  closed-set drops:            {len(dropped)}")
    print(f"  matches passing closed-set:  {len(all_matches)}")

    # Write dropped-records audit
    with open(OUT / "ai_extracted_dropped_records.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["doc_id", "person_id",
                                            "reason", "confidence",
                                            "quoted_latin"])
        w.writeheader()
        for r in dropped:
            w.writerow({
                "doc_id": r.get("doc_id", ""),
                "person_id": r.get("person_id", ""),
                "reason": "closed_set_violation",
                "confidence": r.get("confidence", ""),
                "quoted_latin": (r.get("quoted_latin") or "")[:200],
            })

    # Apply confidence filters and aggregate
    conf_dist = Counter(m.get("confidence") for m in all_matches)
    print(f"\nConfidence after closed-set filter:")
    for k, v in conf_dist.most_common():
        print(f"  {str(k):<10} {v:>5}")

    high_only = [m for m in all_matches if m.get("confidence") == "high"]
    high_med  = [m for m in all_matches
                  if m.get("confidence") in ("high", "medium")]

    high_summary = aggregate(high_only)
    hm_summary = aggregate(high_med)

    write_summary(high_summary,
                  OUT / "person_summary_ai_extracted_high.csv")
    write_summary(hm_summary,
                  OUT / "person_summary_ai_extracted_high_medium.csv")
    print(f"\nWrote:")
    print(f"  person_summary_ai_extracted_high.csv         "
          f"({len(high_summary)} persons, {len(high_only)} matches)")
    print(f"  person_summary_ai_extracted_high_medium.csv  "
          f"({len(hm_summary)} persons, {len(high_med)} matches)")
    print(f"  ai_extracted_dropped_records.csv             "
          f"({len(dropped)} dropped)")
    print(f"  build_cache_matches.csv                      "
          f"({len(combined_cache)} cached records)")


if __name__ == "__main__":
    main()
