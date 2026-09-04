"""check_inputs.py — Stage 0: verify raw + frozen inputs before the pipeline runs.

Run from the package root:  python scripts/check_inputs.py

Checks
  1. data/raw/thePeerage.csv       present, expected row count
  2. data/raw/aposcripta.dataset.json  present (replicator downloads this
     independently -- see README), expected letter count
  3. data/frozen/*                 all frozen artifacts present
  4. Unzips data/frozen/verdicts_sonnet-4-6.zip into
     output/batches_reextract/verdicts_sonnet-4-6/ if not already there
  5. Copies frozen artifacts that the pipeline consumes in place:
       matched_docs_coded.csv        -> output/
       patriline_bloc_assignment.csv -> output/   (frozen Louvain partition;
                                        rerun scripts/55_patriline_blocs.py
                                        to regenerate, see README)
       reextract_validation_aggregated.csv -> output/
       ai_calibration_verdicts.jsonl -> output/
       agent_coded_overlap.csv       -> output/recode_agreement/
"""
from __future__ import annotations
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
FROZEN = ROOT / "data" / "frozen"
OUT = ROOT / "output"

EXPECTED_PEERAGE_ROWS = 727_753          # persons in the August 2024 scrape
EXPECTED_APOSCRIPTA_ITEMS = 25_289       # raw datasetItems in the 2024-08-10 dump
                                         # (25,190 survive stage-07 filtering)
EXPECTED_VERDICT_FILES = 24_130          # one per letter dated 1020-1380

FROZEN_FILES = [
    "matched_docs_coded.csv",
    "patriline_bloc_assignment.csv",
    "patriline_bloc_assignment_pre1300.csv",
    "bloc_reach_pre1300.csv",
    "reextract_validation_aggregated.csv",
    "reextract_phase2_validation_sample.csv",
    "ai_calibration_verdicts.jsonl",
    "agent_coded_overlap.csv",
    "verdicts_sonnet-4-6.zip",
]

ok = True

def fail(msg: str) -> None:
    global ok
    ok = False
    print(f"  FAIL  {msg}")

def good(msg: str) -> None:
    print(f"  ok    {msg}")

print("== 1. thePeerage.csv")
peer = RAW / "thePeerage.csv"
if not peer.exists() and (RAW / "thePeerage.csv.gz").exists():
    print("  ...   decompressing thePeerage.csv.gz")
    import gzip
    with gzip.open(RAW / "thePeerage.csv.gz", "rb") as src, peer.open("wb") as dst:
        shutil.copyfileobj(src, dst)
if not peer.exists():
    fail("data/raw/thePeerage.csv missing. See README 'Data availability'.")
else:
    with peer.open(encoding="utf-8", errors="replace") as fh:
        n = sum(1 for _ in fh) - 1
    if n == EXPECTED_PEERAGE_ROWS:
        good(f"{n:,} person rows (expected {EXPECTED_PEERAGE_ROWS:,})")
    else:
        fail(f"{n:,} rows; expected {EXPECTED_PEERAGE_ROWS:,}. "
             "A different scrape vintage will NOT reproduce the paper's numbers.")

print("== 2. aposcripta.dataset.json")
apo = RAW / "aposcripta.dataset.json"
if not apo.exists():
    fail("data/raw/aposcripta.dataset.json missing. Download APOSCRIPTA per the "
         "README and place the JSON dump here.")
else:
    data = json.load(apo.open(encoding="utf-8"))
    n = len(data.get("datasetItems", [])) if isinstance(data, dict) else len(data)
    if n == EXPECTED_APOSCRIPTA_ITEMS:
        good(f"{n:,} datasetItems (expected {EXPECTED_APOSCRIPTA_ITEMS:,})")
    else:
        fail(f"{n:,} datasetItems; expected {EXPECTED_APOSCRIPTA_ITEMS:,}. "
             "APOSCRIPTA is a living corpus; a later dump will differ. The "
             "paper's numbers are tied to this vintage (see README).")

print("== 3. frozen artifacts")
for f in FROZEN_FILES:
    if (FROZEN / f).exists():
        good(f)
    else:
        fail(f"data/frozen/{f} missing")

print("== 4. frozen verdicts")
vdir = OUT / "batches_reextract" / "verdicts_sonnet-4-6"
if vdir.exists() and sum(1 for _ in vdir.glob("*.jsonl")) >= EXPECTED_VERDICT_FILES:
    good(f"verdicts already extracted ({EXPECTED_VERDICT_FILES:,} files)")
elif (FROZEN / "verdicts_sonnet-4-6.zip").exists():
    print("  ...   extracting verdicts_sonnet-4-6.zip (24,130 files)")
    (OUT / "batches_reextract").mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(FROZEN / "verdicts_sonnet-4-6.zip") as z:
        z.extractall(OUT / "batches_reextract")
    n = sum(1 for _ in vdir.glob("*.jsonl"))
    if n >= EXPECTED_VERDICT_FILES:
        good(f"extracted {n:,} verdict files")
    else:
        fail(f"extracted only {n:,} verdict files (expected {EXPECTED_VERDICT_FILES:,})")

print("== 5. seed frozen artifacts into output/")
OUT.mkdir(exist_ok=True)
(OUT / "clean_iv").mkdir(exist_ok=True)
(OUT / "recode_agreement").mkdir(exist_ok=True)
seeds = [
    (FROZEN / "matched_docs_coded.csv", OUT / "matched_docs_coded.csv"),
    (FROZEN / "patriline_bloc_assignment.csv", OUT / "patriline_bloc_assignment.csv"),
    (FROZEN / "patriline_bloc_assignment_pre1300.csv", OUT / "patriline_bloc_assignment_pre1300.csv"),
    (FROZEN / "bloc_reach_pre1300.csv", OUT / "bloc_reach_pre1300.csv"),
    (FROZEN / "reextract_validation_aggregated.csv", OUT / "reextract_validation_aggregated.csv"),
    (FROZEN / "reextract_phase2_validation_sample.csv", OUT / "reextract_phase2_validation_sample.csv"),
    (FROZEN / "ai_calibration_verdicts.jsonl", OUT / "ai_calibration_verdicts.jsonl"),
    (FROZEN / "agent_coded_overlap.csv", OUT / "recode_agreement" / "agent_coded_overlap.csv"),
]
for src, dst in seeds:
    if not src.exists():
        continue
    if dst.exists():
        good(f"{dst.relative_to(ROOT)} already in place")
    else:
        shutil.copy2(src, dst)
        good(f"seeded {dst.relative_to(ROOT)}")

print()
if ok:
    print("ALL INPUT CHECKS PASSED.")
else:
    print("INPUT CHECKS FAILED -- fix the items above before running the pipeline.")
    sys.exit(1)
