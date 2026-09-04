"""recode_agreement.py — inter-coder agreement for the subject coding (Table: tab:kappa).

Primary coder = the production coding pass (12_recode_subjects.py; frozen in
output/matched_docs_coded.csv). Second coder = an independent model pass under
identical instructions over 2,000 of the matched letters (frozen in
output/recode_agreement/agent_coded_overlap.csv).

Reproduces the paper's inter-coder agreement table plus the
secular-territorial-specific binary agreement cited in the text.

Reads   output/matched_docs_coded.csv
        output/recode_agreement/agent_coded_overlap.csv
Writes  output/recode_agreement/agreement_report.md
"""
from __future__ import annotations
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
csv.field_size_limit(2_147_483_647)

api = {}
with (OUT / "matched_docs_coded.csv").open(encoding="utf-8-sig", newline="") as fh:
    for r in csv.DictReader(fh):
        api[r["doc_id"].strip()] = r

agent = {}
with (OUT / "recode_agreement" / "agent_coded_overlap.csv").open(
        encoding="utf-8-sig", newline="") as fh:
    for r in csv.DictReader(fh):
        agent[r["doc_id"].strip()] = r

overlap = sorted(set(agent) & set(api))
print(f"agent-coded docs: {len(agent)} | api-coded: {len(api)} | overlap: {len(overlap)}")

def kappa(pairs):
    n = len(pairs)
    cats = set(x for p in pairs for x in p)
    po = sum(1 for a, b in pairs if a == b) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    return po, (po - pe) / (1 - pe) if pe < 1 else 1.0

def agree(field, subset=None, norm=lambda x: x):
    pairs = [(norm(agent[d].get(field, "")), norm(api[d].get(field, "")))
             for d in (subset or overlap)]
    po, k = kappa(pairs)
    return po, k, len(pairs)

rows = []
po, k, n = agree("is_dispute")
rows.append(("Live dispute (yes/no)", po, k, n))
po, k, n = agree("domain")
rows.append(("Domain (eight-way)", po, k, n))
both_disp = [d for d in overlap
             if agent[d].get("is_dispute") == "yes" and api[d].get("is_dispute") == "yes"]
po, k, n = agree("dispute_parties", both_disp)
rows.append(("Parties to the dispute", po, k, n))
po, k, n = agree("matched_principal", both_disp)
rows.append(("Matched noble a principal", po, k, n))

# secular-territorial as a binary axis (cited in the body text)
po_st, k_st, n_st = agree(
    "domain", norm=lambda x: "secterr" if x == "secular_territorial" else "other")

lines = ["# Inter-coder agreement (reproduces tab:kappa)", "",
         f"Overlap analysed: {len(overlap)} documents.", "",
         "| Axis | Agreement | Cohen's kappa | n |", "|---|---|---|---|"]
for lab, po, k, n in rows:
    lines.append(f"| {lab} | {100*po:.1f}% | {k:.2f} | {n:,} |")
lines += ["",
          f"Secular-territorial (binary): {100*po_st:.1f}% agreement, "
          f"Cohen's kappa = {k_st:.2f} (n={n_st:,}).", ""]

rep = OUT / "recode_agreement" / "agreement_report.md"
rep.parent.mkdir(parents=True, exist_ok=True)
rep.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
print(f"\nwrote {rep.relative_to(ROOT)}")
