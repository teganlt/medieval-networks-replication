"""
v94_build_blitz_fp_audit.py
===========================
Author-coded BLITZ false-positive audit (8/24): 100 additional high-confidence
person-letter matches, same construction and strata as v90 Track A, EXCLUDING
every (doc_id, person_id) pair already in the RA's match_audit_items.csv so
the two samples never overlap. Different seed (43).

Purpose: an interim precision estimate ready before NBER submission in case
the RA is slow. Label it author-coded wherever reported; the blind RA audit
supersedes it on return. Codeable with the same harness:

  cd validation/audit_blitz
  powershell -ExecutionPolicy Bypass -File code_items.ps1 -Track matches

Outputs (validation/audit_blitz/):
  match_audit_items.csv   100 items (utf-8-sig), stratified era x reach
  code_items.ps1          copy of the harness (verdicts land alongside)

CLI: python scripts/v94_build_blitz_fp_audit.py
"""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
AUD = ROOT / "validation" / "audit_regen"
BLZ = ROOT / "validation" / "audit_blitz_regen"
APO_JSON = ROOT / "data" / "raw" / "aposcripta.dataset.json"

SEED = 43
N_MATCH = 100
TRANS_CAP = 2000
LO, HI = 1100, 1300


def _norm(x):
    if not isinstance(x, str):
        return ""
    return " ".join(x.split())


def load_doc_texts(need):
    data = json.load(open(APO_JSON, encoding="utf-8"))
    tx = {}
    for it in data["datasetItems"]:
        did = str(it.get("itemIdTELMA", "")).strip()
        if did in need:
            tx[did] = {"analyse": _norm(it.get("analyse")), "regeste": _norm(it.get("regeste")),
                       "destinataire": _norm(it.get("destinataire")),
                       "transcription": _norm(it.get("transcription"))[:TRANS_CAP]}
    return tx


def main():
    rng = np.random.default_rng(SEED)
    BLZ.mkdir(parents=True, exist_ok=True)

    ra = pd.read_csv(AUD / "match_audit_items.csv", dtype={"doc_id": str, "person_id": str})
    ra_pairs = set(zip(ra.doc_id, ra.person_id))
    print(f"RA sample: {len(ra)} items; excluding {len(ra_pairs)} (doc, person) pairs")

    mt = pd.read_csv(OUT / "doc_matches_ai_extracted_high.csv", dtype={"doc_id": str, "person_id": str})
    mt = mt[(mt.doc_year >= LO) & (mt.doc_year <= HI)].copy()
    mt = mt.drop_duplicates(["person_id", "doc_id"])
    before = len(mt)
    mt = mt[~mt.apply(lambda r: (r.doc_id, r.person_id) in ra_pairs, axis=1)]
    print(f"pool: {before:,} high-confidence pairs -> {len(mt):,} after exclusion")

    persons = pd.read_csv(OUT / "persons_imputed.csv", dtype={"id": str})[["id", "name", "birth", "death"]]
    br = pd.read_csv(OUT / "bloc_reach_fullgraph.csv", dtype={"person_id": str})
    sample = br[br.mother_n_dyn_4hop.notna()][["person_id", "n_dyn_4hop"]].copy()
    terc = sample.n_dyn_4hop.quantile([1 / 3, 2 / 3]).values
    sample["stratum_reach"] = np.where(sample.n_dyn_4hop <= terc[0], "reach_low",
                              np.where(sample.n_dyn_4hop <= terc[1], "reach_mid", "reach_high"))

    a = mt.merge(persons, left_on="person_id", right_on="id", how="left").rename(columns={"doc_pope": "pope"})
    a = a.merge(sample[["person_id", "stratum_reach"]], on="person_id", how="left")
    a["stratum_reach"] = a.stratum_reach.fillna("out_of_sample")
    a["stratum_era"] = np.where(a.doc_year <= 1215, "era_emfp", "era_post")
    a["stratum"] = a.stratum_era + "|" + a.stratum_reach

    strata = sorted(a.stratum.unique())
    quota, rem = divmod(N_MATCH, len(strata))
    picks = []
    for i, s in enumerate(strata):
        pool = a[a.stratum == s]
        k = min(len(pool), quota + (1 if i < rem else 0))
        picks.append(pool.sample(n=k, random_state=int(rng.integers(0, 2**31))))
    A = pd.concat(picks)
    if len(A) < N_MATCH:
        extra = a.drop(A.index).sample(n=N_MATCH - len(A), random_state=int(rng.integers(0, 2**31)))
        A = pd.concat([A, extra])
    A = A.sample(frac=1, random_state=int(rng.integers(0, 2**31))).reset_index(drop=True)

    tx = load_doc_texts(set(A.doc_id))
    quote_col = next((c for c in ["quoted_latin", "quote", "evidence"] if c in A.columns), None)
    role_col = next((c for c in ["role", "person_role"] if c in A.columns), None)
    items = pd.DataFrame({
        "item_id": ["Z%03d" % (i + 1) for i in range(len(A))],
        "doc_id": A.doc_id,
        "doc_year": A.doc_year.astype(int),
        "pope": A.pope.fillna("") if "pope" in A.columns else "",
        "person_id": A.person_id,
        "person_name": A.name.fillna(""),
        "person_birth": A.birth,
        "person_death": A.death,
        "model_quote": A[quote_col].fillna("") if quote_col else "",
        "model_role": A[role_col].fillna("") if role_col else "",
        "stratum": A.stratum,
        "analyse": [tx.get(d, {}).get("analyse", "") for d in A.doc_id],
        "regeste": [tx.get(d, {}).get("regeste", "") for d in A.doc_id],
        "destinataire": [tx.get(d, {}).get("destinataire", "") for d in A.doc_id],
        "transcription": [tx.get(d, {}).get("transcription", "") for d in A.doc_id],
    })
    items.to_csv(BLZ / "match_audit_items.csv", index=False, encoding="utf-8-sig")
    if (AUD / "code_items.ps1").exists():
        shutil.copy(AUD / "code_items.ps1", BLZ / "code_items.ps1")

    overlap = set(zip(items.doc_id, items.person_id)) & ra_pairs
    assert not overlap, f"overlap with RA sample: {overlap}"
    print(f"\nBLITZ: {len(items)} items -> validation/audit_blitz/match_audit_items.csv (no RA overlap)")
    print(items.stratum.value_counts().to_string())
    print("\ncode with:\n  cd validation/audit_blitz\n  powershell -ExecutionPolicy Bypass -File code_items.ps1 -Track matches")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
