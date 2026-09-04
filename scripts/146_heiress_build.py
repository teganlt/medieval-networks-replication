"""
146_heiress_build.py
====================
Heiress classification for the claims-conduit test (8/24).

For focal i with mother M and maternal grandfather G, the blocker set L(G) is
G's SONS plus everything downstream of them through male links (daughters of
male members are included as members but never expanded). M's own sisters --
daughters of G -- are NOT blockers (they co-inherit; separate indicator).
Under the representation toggle (default TRUE) female members of the sub-lines
block; under male-only they do not, but their recorded births still serve as
chain proofs that their (male, in-line) father was alive.

Evidence rules (asymmetric standards of proof; recorded = raw scrape dates,
never imputed):
  BLOCKED at B  : affirmative living blocker -- some counted member with
                  recorded death >= B, or a chain proof (any child of a male
                  member with recorded birth >= B proves the line alive at B).
  HEIRESS at B  : L(G) empty, or every member shows affirmative extinction
                  (recorded death < B).
  UNCERTAIN     : everything else (undated members, spouse-only evidence).
  UNCLASSIFIABLE: mgf unknown.
Ever-heiress (during focal's life, death D): blocked-for-life if proof of a
member alive past D; heiress-eventual if G recorded-dead <= D and all members
recorded-dead <= D; else uncertain.

Canon-law legitimacy: The Peerage scrape has no illegitimacy markers, so
exclusions are hand-maintained in validation/heiress/illegit_exclusions.csv
(id,note). Excluded persons are pruned WITH their whole subtree (an
illegitimate son transmits no claim to G's patrimony).

Usage:
  python scripts/146_heiress_build.py --validate    marquee-case rosters only
  python scripts/146_heiress_build.py               full build ->
                                                    output/clean_iv/heiress_status.csv
"""
from __future__ import annotations
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
EXCL_PATH = ROOT / "validation" / "heiress" / "illegit_exclusions.csv"
# hand rulings at the MOTHER level, applied after the code rules; for cases
# where the scrape is a stub but history is unambiguous (Eleanor), or where
# an undated entry needs a human call (Constance/Matina). Columns:
# mother_id, class_birth, class_ever, note. Blank class = leave code ruling.
RULINGS_PATH = ROOT / "validation" / "heiress" / "hand_rulings.csv"

VALIDATION_CASES = [
    # (focal_id, label, expectation)
    ("p10202.htm#i102013", "Henry II of England (b1133), M=Empress Matilda, G=Henry I",
     "HEIRESS after excluding Henry I's illegitimate sons (William Adelin d.1120, no issue)"),
    ("p10202.htm#i102018", "Richard I (b1157), M=Eleanor of Aquitaine, G=William X",
     "HEIRESS (William Aigret d.1130 as a child)"),
    ("p10201.htm#i102006", "John Lackland (b1167), M=Eleanor of Aquitaine, G=William X",
     "HEIRESS (same line, later birth)"),
    ("p10223.htm#i102226", "Frederick II (b1194), M=Constance of Sicily, G=Roger II",
     "BLOCKED with Tancred of Lecce's line counted; HEIRESS with it excluded"),
    ("p10310.htm#i103091", "Philip II Augustus (b1165), M=Adele de Champagne, G=Theobald II",
     "NEGATIVE CONTROL: BLOCKED (Adele's brothers alive)"),
    ("p10239.htm#i102383", "Louis VIII (b1187), M=Isabelle de Hainaut, G=Baldwin V",
     "NEGATIVE CONTROL: BLOCKED (Baldwin VI alive)"),
]


def to_year(x):
    try:
        v = float(x)
        return int(v) if v == v else None
    except (TypeError, ValueError):
        return None


def load():
    raw = pd.read_csv(OUT / "persons.csv", dtype={"id": str})
    imp = pd.read_csv(OUT / "persons_imputed.csv", dtype={"id": str})
    rb = {r.id: to_year(r.birth) for r in raw.itertuples(index=False)}
    rd = {r.id: to_year(r.death) for r in raw.itertuples(index=False)}
    ib = {r.id: to_year(r.birth) for r in imp.itertuples(index=False)}
    idd = {r.id: to_year(r.death) for r in imp.itertuples(index=False)}
    name = dict(zip(imp.id, imp.name))
    sex = dict(zip(imp.id, imp.sex))
    kids = defaultdict(list)
    for p, c in pd.read_csv(OUT / "parent_pairs.csv", dtype=str).values:
        kids[p].append(c)
    excl = set()
    if EXCL_PATH.exists():
        e = pd.read_csv(EXCL_PATH, dtype=str)
        excl = set(e["id"].dropna())
    rulings = {}
    if RULINGS_PATH.exists():
        for r in pd.read_csv(RULINGS_PATH, dtype=str).itertuples(index=False):
            rulings[r.mother_id] = (r.class_birth, r.class_ever)
    return rb, rd, ib, idd, name, sex, kids, excl, rulings


def apply_ruling(res, mother, rulings):
    if mother in rulings:
        cb, ce = rulings[mother]
        if isinstance(cb, str) and cb:
            res["class_birth"] = cb
            res["heiress_grade"] = "hand_ruled"
        if isinstance(ce, str) and ce:
            res["class_ever"] = ce
    return res


def blocker_lines(G, kids, sex, excl):
    """Members of L(G): sons of G and their male-line subtrees (daughters of
    male members included, not expanded). Excluded ids pruned with subtree.
    Returns (members, chain_birth_ids): chain ids = ALL children of male
    in-line members (birth-proofs even in male-only mode)."""
    members, chain, seen = [], [], set()
    frontier = [c for c in kids.get(G, []) if sex.get(c) == "M" and c not in excl]
    while frontier:
        m = frontier.pop()
        if m in seen:
            continue
        seen.add(m)
        members.append(m)
        for c in kids.get(m, []):
            if c in excl:
                continue
            chain.append(c)
            if sex.get(c) == "M":
                frontier.append(c)
            else:
                if c not in seen:
                    seen.add(c)
                    members.append(c)
    return members, chain


def classify(focal, mother, G, B, D, rb, rd, sex, kids, excl, females_block=True):
    if not isinstance(G, str) or G == "" or G != G:
        return dict(class_birth="unclassifiable", class_ever="unclassifiable",
                    n_blockers=0, bmax=None, n_sisters=0, heiress_grade="")
    members, chain = blocker_lines(G, kids, sex, excl)
    nkG = len([c for c in kids.get(G, []) if c not in excl])
    counted = [m for m in members if females_block or sex.get(m) == "M"]
    births = [rb[c] for c in chain if rb.get(c) is not None] + \
             [rb[m] for m in counted if rb.get(m) is not None]
    bmax = max(births) if births else None
    deaths = {m: rd.get(m) for m in counted}
    sisters = [c for c in kids.get(G, []) if sex.get(c) == "F" and c != mother and c not in excl]

    def status_at(t):
        """Returns (class, heiress_grade). An EMPTY male line is credible
        heiress evidence only when G has 2+ recorded children (someone
        recorded the family and found no sons); a stub G with only the
        mother recorded is a recording gap -> uncertain."""
        if t is None:
            return "uncertain", ""
        alive = any(d is not None and d >= t for d in deaths.values()) or \
                (bmax is not None and bmax >= t)
        if alive:
            return "blocked", ""
        if not counted:
            if nkG >= 2:
                return "heiress", "all_daughters"
            return "uncertain", "stub_demoted"
        if all(deaths[m] is not None and deaths[m] < t for m in counted):
            return "heiress", "extinct"
        return "uncertain", ""

    cb, grade = status_at(B)
    # ever: blocked-for-life if proof past D; heiress-eventual needs G dead too
    if D is None:
        ce = "uncertain"
    elif any(d is not None and d > D for d in deaths.values()) or (bmax is not None and bmax > D):
        ce = "blocked"
    elif (rd.get(G) is not None and rd[G] <= D) and \
         (not counted or all(deaths[m] is not None and deaths[m] <= D for m in counted)):
        ce = "heiress" if (counted or nkG >= 2) else "uncertain"
    else:
        ce = "uncertain"
    return dict(class_birth=cb, class_ever=ce, n_blockers=len(counted),
                bmax=bmax, n_sisters=len(sisters), heiress_grade=grade)


def main():
    validate_only = "--validate" in sys.argv
    rb, rd, ib, idd, name, sex, kids, excl, rulings = load()
    print(f"exclusion list: {len(excl)} ids; hand rulings: {len(rulings)} mothers")
    iv = pd.read_csv(OUT / "mother_iv_4hop.csv", dtype={"person_id": str, "mother_id": str, "mgf_id": str})
    ivm = {r.person_id: (r.mother_id, r.mgf_id) for r in iv.itertuples(index=False)}
    br = pd.read_csv(OUT / "bloc_reach_fullgraph.csv", dtype={"person_id": str})
    frame = br[br.mother_n_dyn_4hop.notna()]["person_id"].tolist()

    if validate_only:
        for fid, label, expect in VALIDATION_CASES:
            mother, G = ivm.get(fid, (None, None))
            B = rb.get(fid) if rb.get(fid) is not None else ib.get(fid)
            D = rd.get(fid) if rd.get(fid) is not None else idd.get(fid)
            print("\n" + "=" * 78)
            print(f"{label}\n  EXPECT: {expect}")
            print(f"  focal={fid} B={B} D={D}  mother={mother} ({str(name.get(mother))[:40]})")
            print(f"  G={G} ({str(name.get(G))[:40]}) recorded death={rd.get(G)}")
            if not isinstance(G, str) or G != G:
                print("  ** mgf unknown -> unclassifiable")
                continue
            members, chain = blocker_lines(G, kids, sex, excl)
            print(f"  L(G): {len(members)} members ({sum(1 for m in members if sex.get(m)=='M')} male)")
            for m in sorted(members, key=lambda m: (rb.get(m) or ib.get(m) or 9999)):
                tag = " EXCLUDABLE?" if False else ""
                print(f"    {m:26s} {str(name.get(m))[:44]:44s} rb={rb.get(m)} rd={rd.get(m)} sex={sex.get(m)}{tag}")
            r = apply_ruling(classify(fid, mother, G, B, D, rb, rd, sex, kids, excl), mother, rulings)
            print(f"  -> at-birth: {r['class_birth'].upper():10s} ever: {r['class_ever'].upper():10s} "
                  f"grade={r['heiress_grade'] or '-'} "
                  f"(bmax={r['bmax']}, blockers={r['n_blockers']}, sisters={r['n_sisters']})")
        return

    rows = []
    for fid in frame:
        mother, G = ivm.get(fid, (None, None))
        B = rb.get(fid) if rb.get(fid) is not None else ib.get(fid)
        D = rd.get(fid) if rd.get(fid) is not None else idd.get(fid)
        r = apply_ruling(classify(fid, mother, G, B, D, rb, rd, sex, kids, excl), mother, rulings)
        r2 = classify(fid, mother, G, B, D, rb, rd, sex, kids, excl, females_block=False)
        rows.append(dict(person_id=fid, mother_id=mother, mgf_id=G, focal_birth=B,
                         **{k: r[k] for k in ("class_birth", "class_ever", "n_blockers",
                                              "bmax", "n_sisters", "heiress_grade")},
                         class_birth_maleonly=r2["class_birth"],
                         coheiress=int(r["class_birth"] == "heiress" and r["n_sisters"] > 0)))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "clean_iv" / "heiress_status.csv", index=False)
    print(f"\nwrote heiress_status.csv N={len(df)}")
    for col in ("class_birth", "class_ever"):
        print(f"\n{col}:")
        print(df[col].value_counts().to_string())
    hb = df[df.class_birth == "heiress"]
    print("\nheiress evidence grades:")
    print(hb.heiress_grade.value_counts().to_string())
    print(f"\nat-birth heiress share (of classifiable): "
          f"{len(hb) / max(1, (df.class_birth != 'unclassifiable').sum()):.3f}"
          f" | coheiress among heiresses: {hb.coheiress.mean():.3f}"
          f" | male-only toggle agreement: {(df.class_birth == df.class_birth_maleonly).mean():.3f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
