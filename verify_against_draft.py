"""verify_against_draft.py — diff the regenerated tables against the draft.

The draft (paper/draft_8_29_26.tex in this repository) hardcodes its
tables; each block is delimited by
    % ===== BEGIN tables/<name> =====  ...  % ===== END tables/<name> =====
and was pasted from an emitted tables/<name>.tex. This script compares the
NUMERIC CONTENT of each regenerated table against the corresponding draft
block, row by row (lines containing '&'). Caption and label wording is
ignored -- the author edits prose in the tex; the numbers are the contract.

Usage (from the package root, after run_all.py completes):
    python verify_against_draft.py [path/to/draft.tex]

Exit code 0 if every matched table agrees; 1 otherwise.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DRAFT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "paper" / "draft_8_29_26.tex"

if not DRAFT.exists():
    print(f"draft not found at {DRAFT}; pass its path as the first argument")
    sys.exit(2)

text = DRAFT.read_text(encoding="utf-8")
blocks = dict(re.findall(
    r"% ===== BEGIN tables/(\w+) =====\n(.*?)% ===== END tables/\1 =====",
    text, re.S))

NUM = re.compile(r"-?\d+(?:[.,]\d+)*")

def row_numbers(tex: str):
    """Numeric tokens from data rows only (lines with '&'), normalized."""
    out = []
    for line in tex.split("\n"):
        if "&" not in line or line.lstrip().startswith("%"):
            continue
        if "multicolumn" in line and ("Notes" in line or "footnotesize" in line):
            continue  # notes lines: prose numbers, legitimately edited
        clean = re.sub(r"\\[A-Za-z]+", " ", line)   # drop latex commands
        nums = [n.replace(",", "") for n in NUM.findall(clean)]
        if nums:
            out.append((re.sub(r"\s+", " ", line).strip()[:60], nums))
    return out

overall_ok = True
n_checked = 0
for name, draft_block in sorted(blocks.items()):
    gen = ROOT / "tables" / f"{name}.tex"
    if not gen.exists():
        print(f"[MISSING ] {name}: no regenerated tables/{name}.tex")
        overall_ok = False
        continue
    d_rows = row_numbers(draft_block)
    g_rows = row_numbers(gen.read_text(encoding="utf-8"))
    d_nums = [n for _, r in d_rows for n in r]
    g_nums = [n for _, r in g_rows for n in r]
    n_checked += 1
    if d_nums == g_nums:
        print(f"[OK      ] {name}: {len(d_nums)} numbers match")
        continue
    # align per row for a readable report
    print(f"[MISMATCH] {name}: draft has {len(d_nums)} numbers, regenerated {len(g_nums)}")
    overall_ok = False
    for i in range(max(len(d_rows), len(g_rows))):
        dr = d_rows[i] if i < len(d_rows) else ("<no row>", [])
        gr = g_rows[i] if i < len(g_rows) else ("<no row>", [])
        if dr[1] != gr[1]:
            print(f"    draft : {dr[0]}  -> {dr[1]}")
            print(f"    regen : {gr[0]}  -> {gr[1]}")

print(f"\n{n_checked} tables checked against {DRAFT.name}.")
print("ALL TABLES MATCH." if overall_ok else "MISMATCHES FOUND -- see above.")
sys.exit(0 if overall_ok else 1)
