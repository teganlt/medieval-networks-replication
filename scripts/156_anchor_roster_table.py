"""
156_anchor_roster_table.py
==========================
Emits the hand-curated dynastic-anchor roster for Appendix B, read directly
from 03_named_anchor_dynasty.py's NAMED_ANCHORS dict (no hand-transcription)
plus the located counts of dynasty_assignment_summary.csv.
Out: tables/tab_anchor_roster.tex.  CLI: python scripts/156_anchor_roster_table.py
"""
import ast, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "scripts" / "03_named_anchor_dynasty.py").read_text(encoding="utf-8")
anchors = ast.literal_eval(re.search(r"NAMED_ANCHORS = (\{.*?\n\})", src, re.S).group(1))
summ = pd.read_csv(ROOT / "output" / "dynasty_assignment_summary.csv").set_index("dynasty")

def esc(s):
    return s.strip().replace("&", r"\&").replace("_", r"\_").replace("#", r"\#")

L = [r"% ===== BEGIN tables/tab_anchor_roster =====",
     r"\begin{longtable}{lrp{9.2cm}}",
     r"\caption{The hand-curated dynastic anchors, as named in \emph{The Peerage}. ``Located'' counts the person-records matched in the scraped genealogy; a name matching more than one in-window record contributes each match, so the count can exceed the number of names. The dynasty labels are descriptive only (Appendix~\ref{app:data-frame}).}\label{tab:anchor_roster}\\",
     r"\toprule", r"Dynasty & Located & Anchors \\", r"\midrule", r"\endfirsthead",
     r"\multicolumn{3}{c}{\tablename~\thetable\ (continued)}\\", r"\toprule",
     r"Dynasty & Located & Anchors \\", r"\midrule", r"\endhead",
     r"\bottomrule", r"\endlastfoot"]
for dyn, names in anchors.items():
    loc = int(summ.loc[dyn, "n_anchors_located"]) if dyn in summ.index else len(names)
    nm = "; ".join(esc(n) for n in names)
    L.append(rf"{esc(dyn)} & {loc} & {{\footnotesize {nm}}} \\")
L += [r"\end{longtable}", r"% ===== END tables/tab_anchor_roster ====="]
(ROOT / "tables" / "tab_anchor_roster.tex").write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"wrote tables/tab_anchor_roster.tex ({sum(len(v) for v in anchors.values())} anchors, {len(anchors)} dynasties)")
