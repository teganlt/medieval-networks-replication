"""v96_match_validation_tallies.py — tallies for the two preliminary match audits.

1. Cross-model validation (frozen: output/reextract_validation_aggregated.csv):
   a stratified sample of 119 match records re-examined by independent model
   auditors; the draft reports all 108 high-confidence matches judged correct.
2. Preliminary human validation (frozen: output/reextract_phase2_validation_sample.csv):
   38 hand-checked match records; all 25 high-confidence among them correct.

Both input files are frozen artifacts of audits run in an earlier phase of the
project (the auditing scripts themselves called model APIs and are not
re-runnable; see MANIFEST.md for provenance).

Reads   output/reextract_validation_aggregated.csv
        output/reextract_phase2_validation_sample.csv
Writes  console report only
"""
from __future__ import annotations
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
csv.field_size_limit(2_147_483_647)

print("== 1. cross-model validation (119 records) ==")
rows = list(csv.DictReader((OUT / "reextract_validation_aggregated.csv").open(
    encoding="utf-8-sig", newline="")))
print(f"  records: {len(rows)}")
by = Counter((r.get("confidence", "").strip().lower(),
              r.get("verdict", "").strip().upper()) for r in rows)
for conf in ("high", "medium", "low"):
    tot = sum(v for (c, _), v in by.items() if c == conf)
    ok = by.get((conf, "TRUE"), 0)
    print(f"  confidence={conf:6s}: {ok}/{tot} judged TRUE "
          f"({', '.join(f'{v}:{n}' for (c, v), n in sorted(by.items()) if c == conf)})")

print("\n== 2. preliminary human validation (38 records) ==")
rows = list(csv.DictReader((OUT / "reextract_phase2_validation_sample.csv").open(
    encoding="utf-8-sig", newline="")))
print(f"  records: {len(rows)}")
conf_col = next(c for c in rows[0] if c.lower().endswith("confidence"))
by = Counter((r.get(conf_col, "").strip().lower(),
              r.get("VERDICT", "").strip().upper()) for r in rows)
for conf in ("high", "medium", "low"):
    tot = sum(v for (c, _), v in by.items() if c == conf)
    ok = by.get((conf, "TRUE"), 0)
    if tot:
        print(f"  confidence={conf:6s}: {ok}/{tot} TRUE "
              f"({', '.join(f'{v}:{n}' for (c, v), n in sorted(by.items()) if c == conf)})")
