"""Summary-statistics tables for the results sections + 38-bloc roster.
S1 sample (Pred 1), S2 peers (Pred 2, era split), S3 window-level (persistence),
roster appendix. Writes booktabs LaTeX to the paper's tables/ folder."""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
TAB = ROOT / "tables"
TAB.mkdir(parents=True, exist_ok=True)

br = pd.read_csv(OUT / "bloc_reach_fullgraph.csv", dtype={"person_id": str})
cf = pd.read_csv(OUT / "clean_iv" / "reg_complementarity_iv_df.csv", dtype={"person_id": str})
pr = pd.read_csv(OUT / "clean_iv" / "peer_rf_build.csv", dtype={"person_id": str})  # predetermined peer vars (110)
coded = pd.read_csv(OUT / "matched_docs_coded.csv", dtype={"doc_id": str})[["doc_id", "domain", "is_dispute"]]
mt = pd.read_csv(OUT / "doc_matches_ai_extracted_high.csv", dtype={"doc_id": str, "person_id": str})
mt = mt[(mt.doc_year >= 1100) & (mt.doc_year <= 1300)][["person_id", "doc_id"]].merge(coded, on="doc_id")
cnt = mt.groupby("person_id").agg(
    n_total=("doc_id", "size"),
    n_secterr=("domain", lambda s: int((s == "secular_territorial").sum())),
    n_dispute=("is_dispute", lambda s: int((s == "yes").sum()))).reset_index()
df = br[(br.sex == "M") & br.mother_n_dyn_4hop.notna()].merge(
    cf[["person_id", "title_rank", "fa_ldisp"]],
    on="person_id", how="inner").merge(
    pr[["person_id", "EMFP", "peer_nkin", "peer_breadth_pre", "peer_secterr_dated",
        "peer_app_dated", "peer_share_matchable"]],
    on="person_id", how="inner").merge(cnt, on="person_id", how="left")
for c in ("n_total", "n_secterr", "n_dispute"):
    df[c] = df[c].fillna(0)
df["lifespan"] = df.death - df.birth
df["appears"] = (df.n_total > 0).astype(int)
print(f"S1/S2 sample: N={len(df)}, blocs={df.bloc.nunique()}, appearers={df.appears.sum()}")

def fnum(v, d=2):
    if pd.isna(v): return "--"
    if d == 0: return f"{v:,.0f}"
    return f"{v:,.{d}f}"

# ---------------- S1 ----------------
app, non = df[df.appears == 1], df[df.appears == 0]
def fyear(v):
    return "--" if pd.isna(v) else f"{v:.0f}"          # years: no thousands separator

def fpct(v):
    return "--" if pd.isna(v) else f"{100 * v:.0f}\\%"  # rates: percentages

def s1row(label, s, kind="num", d=2):
    a, o = s[df.appears == 1], s[df.appears == 0]
    if kind == "year":
        return (f"{label} & {fyear(s.mean())} & {fyear(s.std())} & {fyear(s.median())}"
                f" & {fyear(a.mean())} & {fyear(o.mean())} \\\\")
    if kind == "pct":
        return f"{label} & {fpct(s.mean())} & -- & -- & {fpct(a.mean())} & {fpct(o.mean())} \\\\"
    return (f"{label} & {fnum(s.mean(), d)} & {fnum(s.std(), d)} & {fnum(s.median(), d)}"
            f" & {fnum(a.mean(), d)} & {fnum(o.mean(), d)} \\\\")

rows_a = [("Birth year", df.birth, "year"), ("Death year", df.death, "year"),
          ("Lifespan (years)", df.lifespan, "num", 1),
          ("Titled (rank $\\geq$ 1)", (df.title_rank >= 1).astype(float), "pct"),
          ("Royal or imperial (rank $\\geq$ 4)", (df.title_rank >= 4).astype(float), "pct")]
rows_b = [("Kin-reach (blocs within 4 hops)", df.n_dyn_4hop, "num", 2),
          ("Network size (persons within 4 hops)", df.n_nodes_4hop, "num", 1),
          ("Degree", df.deg, "num", 2),
          ("Mother's pre-natal reach (instrument)", df.mother_n_dyn_4hop, "num", 2),
          ("Mother's pre-natal network size", df.mother_n_nodes_4hop, "num", 1),
          ("Father's pre-natal reach", df.father_n_dyn_4hop, "num", 2),
          ("Maternal grandfather's pre-natal reach", df.mgf_n_dyn_4hop, "num", 2)]
def c_row(label, s):
    pos = s[s > 0]
    return (f"{label} & {fpct((s > 0).mean())} & {fnum(s.mean(), 2)}"
            f" & {fnum(pos.median(), 0)} & {fnum(pos.quantile(0.9), 0)} & {fnum(pos.max(), 0)} \\\\")
rows_c = [c_row("Total appearances", df.n_total),
          c_row("Secular-territorial appearances", df.n_secterr),
          c_row("Dispute appearances", df.n_dispute)]

lines = [
    "\\begin{table}[!t]", "\\centering",
    "\\caption{Summary statistics: the estimation sample.}",
    "\\label{tab:summary_sample}", "{\\small",
    "\\begin{tabular}{lccccc}", "\\toprule",
    " & Mean & SD & Median & \\multicolumn{2}{c}{Mean by appearance} \\\\",
    "\\cmidrule(lr){5-6}",
    " & & & & Appearers & Others \\\\", "\\midrule",
    "\\multicolumn{6}{l}{\\textit{Panel A: vitals}} \\\\"]
lines += [s1row(*r) for r in rows_a]
lines += ["\\addlinespace", "\\multicolumn{6}{l}{\\textit{Panel B: kinship network}} \\\\"]
lines += [s1row(*r) for r in rows_b]
lines += ["\\addlinespace", "\\multicolumn{6}{l}{\\textit{Panel C: papal appearances, 1100--1300}} \\\\",
          " & Share $>0$ & Mean & \\multicolumn{3}{c}{Among those appearing} \\\\",
          "\\cmidrule(lr){4-6}",
          " & & & Median & P90 & Max \\\\"]
lines += rows_c
lines += ["\\midrule",
          f"\\multicolumn{{6}}{{p{{0.92\\textwidth}}}}{{\\footnotesize \\textit{{Notes:}} $N={len(df):,}$ male nobles"
          f" across {df.bloc.nunique()} marriage-blocs; {int(df.appears.sum())} appear in at least one letter."
          " Reach and size are computed on the full kinship graph over kin born by the focal's death;"
          " ancestors' values over kin born before the focal's birth. First-stage $F = 339$;"
          " cor(reach, size) $= 0.63$. The 858-appearance noble is Frederick II Hohenstaufen;"
          " results survive his omission (see robustness appendix).} \\\\",
          "\\bottomrule", "\\end{tabular}", "}", "\\end{table}"]
(TAB / "tab_summary_sample.tex").write_text("\n".join(lines), encoding="utf-8")
print("wrote tab_summary_sample.tex")

# ---------------- S2 (predetermined peer variables, build 110) ----------------
df["fa_disp"] = np.expm1(df.fa_ldisp)
e1, e0 = df[df.EMFP == 1], df[df.EMFP == 0]
def s2row(label, col, d=3):
    return (f"{label} & {fnum(df[col].mean(), d)} & {fnum(df[col].std(), d)}"
            f" & {fnum(e1[col].mean(), d)} & {fnum(e0[col].mean(), d)} \\\\")
lines = [
    "\\begin{table}[!t]", "\\centering",
    "\\caption{Summary statistics: peer variables, by era of birth.}",
    "\\label{tab:summary_peers}", "{\\small",
    "\\begin{tabular}{lcccc}", "\\toprule",
    " & \\multicolumn{2}{c}{Full sample} & Born $\\leq 1215$ & Born $> 1215$ \\\\",
    "\\cmidrule(lr){2-3}\\cmidrule(lr){4-4}\\cmidrule(lr){5-5}",
    " & Mean & SD & Mean & Mean \\\\", "\\midrule",
    s2row("Peer set size", "peer_nkin", 1),
    s2row("Peer breadth (pre-birth edges)", "peer_breadth_pre", 2),
    s2row("Peer arbitration share", "peer_secterr_dated", 3),
    s2row("Peer appearance share", "peer_app_dated", 3),
    s2row("Share of peers in the matching universe", "peer_share_matchable", 2),
    s2row("Father's dispute appearances", "fa_disp", 2),
    "\\midrule",
    f"$N$ & \\multicolumn{{2}}{{c}}{{{len(df):,}}} & {len(e1):,} & {len(e0):,} \\\\",
    "\\midrule",
    "\\multicolumn{5}{p{0.88\\textwidth}}{\\footnotesize \\textit{Notes:} The peer set is the focal's"
    " pre-natal four-hop kin (kin born before the focal, reached by paths through earlier-born kin)."
    " Peer breadth is the mean, over those kin, of each kin's one-hop distinct-bloc count over"
    " neighbours born before the focal. The arbitration share is the share of peers appearing in a"
    " secular-territorial letter dated before the focal's birth. All peer variables are fixed at the"
    " focal's birth; regressions use them standardized by the full-sample SD.} \\\\",
    "\\bottomrule", "\\end{tabular}", "}", "\\end{table}"]
(TAB / "tab_summary_peers.tex").write_text("\n".join(lines), encoding="utf-8")
print("wrote tab_summary_peers.tex")

# ---------------- Roster ----------------
pers = pd.read_csv(OUT / "persons_imputed.csv", dtype={"id": str})
name = dict(zip(pers.id, pers.name))
byear = dict(zip(pers.id, pd.to_numeric(pers.birth, errors="coerce")))
dyear = dict(zip(pers.id, pd.to_numeric(pers.death, errors="coerce")))
pb = pd.read_csv(OUT / "patriline_bloc_assignment.csv", dtype=str)
nd = pd.read_csv(OUT / "named_dynasty_assignment.csv", dtype=str)
nd_map = dict(zip(nd.id, nd.dynasty))

def trank(nm):
    if not isinstance(nm, str): return 0
    s = nm.lower()
    if re.search(r"emperor|empress|imperator|imperatrix", s): return 5
    if re.search(r"\bking\b|\bqueen\b|\broi\b|\breine\b|rey de|rei de|re di|könig", s): return 4
    if re.search(r"\bduke\b|\bduc\b|\bherzog\b|\bduca\b|\bduque\b", s): return 3
    if re.search(r"\bcount\b|\bearl\b|\bcomte\b|\bgraf\b|\bconte\b|\bmarchese\b|\bmarkgraf\b|\bconde\b", s): return 2
    return 0

def esc(s):
    return (s.replace("&", "\\&").replace("#", "\\#").replace("_", "\\_")
             .replace("%", "\\%").replace("$", "\\$"))

focal_counts = df.groupby("bloc").size().to_dict()
pb_med = pb[pb.id.map(lambda i: (byear.get(i) or 0) >= 800 and (byear.get(i) or 9e9) <= 1500)]
members = pb_med.groupby("dynasty")["id"].apply(list).to_dict()

rows = []
for b, nf in sorted(focal_counts.items(), key=lambda kv: -kv[1]):
    ids = members.get(b, [])
    ranked = sorted(ids, key=lambda i: (-trank(name.get(i, "")), byear.get(i) or 9e9))
    tops = []
    for i in ranked[:2]:
        nm = str(name.get(i, ""))[:46]
        by, dy = byear.get(i), dyear.get(i)
        span = (f" ({int(by)}--{int(dy)})" if by and dy and not (np.isnan(by) or np.isnan(dy)) else "")
        tops.append(esc(nm) + span)
    labs = [nd_map.get(i) for i in ids if isinstance(nd_map.get(i), str)]
    if labs:
        c = pd.Series(labs).value_counts()
        dom = f"{esc(c.index[0])} ({100 * c.iloc[0] / len(labs):.0f}\\%)"
    else:
        dom = "--"
    rows.append((b, nf, len(ids), dom, "; ".join(tops)))

lines = [
    "\\begin{longtable}{lrrp{2.6cm}p{5.9cm}}",
    "\\caption{The 38 in-sample marriage-blocs.}\\label{tab:bloc_roster}\\\\",
    "\\toprule",
    "Bloc & Focals & Members & Dominant dynasty label & Highest-ranking medieval members \\\\",
    "\\midrule", "\\endfirsthead",
    "\\multicolumn{5}{c}{\\tablename~\\thetable\\ (continued)}\\\\", "\\toprule",
    "Bloc & Focals & Members & Dominant dynasty label & Highest-ranking medieval members \\\\",
    "\\midrule", "\\endhead", "\\bottomrule", "\\endlastfoot"]
for b, nf, nm_, dom, tops in rows:
    lines.append(f"{esc(b)} & {nf} & {nm_:,} & {dom} & {{\\footnotesize {tops}}} \\\\")
lines += ["\\end{longtable}"]
(TAB / "tab_bloc_roster.tex").write_text("\n".join(lines), encoding="utf-8")
print(f"wrote tab_bloc_roster.tex ({len(rows)} blocs)")
print("top 5 blocs:")
for r in rows[:5]:
    print("  ", r[0], r[1], r[2], "|", r[3], "|", r[4][:80])
