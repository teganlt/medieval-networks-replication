"""
88_patriline_propensity_build.py
================================
Build a multi-generation PATRILINE court-propensity index for each focal in the
complementarity-IV sample, to test exclusion concern (ii): heritable within-bloc
family court-proneness (ambition / litigiousness) that drives BOTH kin breadth
and focal court use. Walk the male line (father -> grandfather -> ...) via
parent_pairs x persons.sex, sum each ancestor's court use (excl. focal), log1p.
fa_ldisp (father, in baseline) handles generation 1; the NEW content is
grandfather-and-up (pat_*_anc). If the 2SLS survives adding these, the confound
must be orthogonal to *generations* of family court-proneness.
Court counts use the FULL matched corpus (no 1100-1300 window) to capture
pre-window ancestral engagement. Writes reg_complementarity_iv_df_sat2.csv.
CLI: python 88_patriline_propensity_build.py
"""
from __future__ import annotations
import time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
MAXGEN = 6


def main():
    t0 = time.time()
    persons = pd.read_csv(OUT/"persons_imputed.csv", dtype={"id": str})
    sex = dict(zip(persons.id, persons.sex))
    # father map: child -> first male parent
    pp = pd.read_csv(OUT/"parent_pairs.csv", dtype=str)
    father = {}
    for par, ch in pp[["parent_id", "child_id"]].values:
        if ch in father:
            continue
        if sex.get(par) == "M":
            father[ch] = par
    print(f"father map: {len(father):,} child->father links ({time.time()-t0:.0f}s)", flush=True)

    # per-person court counts from FULL matched corpus
    coded = pd.read_csv(OUT/"matched_docs_coded.csv", dtype={"doc_id": str})[["doc_id", "domain", "is_dispute"]]
    mt = pd.read_csv(OUT/"doc_matches_ai_extracted_high.csv", dtype={"doc_id": str})
    print(f"corpus doc_year range: {mt.doc_year.min():.0f}-{mt.doc_year.max():.0f}", flush=True)
    mt = mt[["person_id", "doc_id"]].merge(coded, on="doc_id")
    mt["person_id"] = mt.person_id.astype(str)
    pc = mt.groupby("person_id").agg(
        n_disp=("is_dispute", lambda s: (s == "yes").sum()),
        n_secterr=("domain", lambda s: (s == "secular_territorial").sum()),
        n_total=("doc_id", "size")).to_dict("index")

    def cnt(pid, key):
        r = pc.get(pid)
        return r[key] if r else 0

    df = pd.read_csv(OUT/"clean_iv"/"reg_complementarity_iv_df_sat.csv", dtype={"person_id": str})

    def walk(focal):
        line = []
        cur = father.get(focal)
        g = 0
        while cur is not None and g < MAXGEN:
            line.append(cur); g += 1
            cur = father.get(cur)
        return line  # [father, gf, ggf, ...]

    rec = []
    for pid in df.person_id.values:
        line = walk(pid)
        anc = line[1:]          # grandfather and up (exclude father)
        rec.append((
            np.log1p(sum(cnt(a, "n_disp") for a in line)),       # pat_disp_all  (incl father)
            np.log1p(sum(cnt(a, "n_disp") for a in anc)),        # pat_disp_anc  (gf+up)
            np.log1p(sum(cnt(a, "n_secterr") for a in anc)),     # pat_secterr_anc
            len(line), len(anc),
            int(any(cnt(a, "n_disp") > 0 for a in line))))       # any male-line ancestor used court
    cols = ["pat_disp_all", "pat_disp_anc", "pat_secterr_anc", "n_pat_all", "n_pat_anc", "any_anc_court"]
    for i, c in enumerate(cols):
        df[c] = [r[i] for r in rec]

    cov_any = df.n_pat_all.gt(0).mean()
    cov_anc = df.n_pat_anc.gt(0).mean()
    print(f"coverage: {cov_any:.2f} of focals have >=1 male-line ancestor; "
          f"{cov_anc:.2f} have a grandfather+ ; "
          f"{df.any_anc_court.mean():.2f} have an ancestor who used the court", flush=True)
    print(f"  mean n_pat_all={df.n_pat_all.mean():.2f}  pat_disp_all(log) mean={df.pat_disp_all.mean():.3f}  "
          f"pat_disp_anc(log) mean={df.pat_disp_anc.mean():.3f}", flush=True)
    print(f"  cor(pat_disp_anc, peer_reach1)={df.pat_disp_anc.corr(df.peer_reach1):.3f}  "
          f"cor(pat_disp_anc, peer_disp_rate)={df.pat_disp_anc.corr(df.peer_disp_rate):.3f}  "
          f"cor(pat_disp_anc, y_secterr)={df.pat_disp_anc.corr(df.y_secterr):.3f}", flush=True)
    df.to_csv(OUT/"clean_iv"/"reg_complementarity_iv_df_sat2.csv", index=False)
    print(f"wrote reg_complementarity_iv_df_sat2.csv N={len(df)}", flush=True)


if __name__ == "__main__":
    main()
