"""
v90_build_audit_samples.py
==========================
Build the two stratified human-audit samples for pre-submission validation.

Track A — MATCH AUDIT (precision of the high-confidence person-letter matches):
  200 high-confidence matches, doc_year in [1100,1300], stratified by
  (era: doc_year<=1215 vs >1215) x (matched noble in the N=2,195 IV sample,
  and if so his kin-reach tercile; else stratum "out-of-sample").
  The coder sees the letter text, the candidate noble, and the model's quote,
  and judges whether the person named in the letter is that noble.

Track B — DOMAIN AUDIT (human-vs-model agreement on the subject coding):
  200 coded letters, 25 per model-assigned domain (8 domains). BLIND: the
  items file carries NO model labels; they are written to a separate answer
  key. The coder sees exactly what the recode model saw (analyse + regeste +
  Latin transcription capped at 2000 chars) and codes is_dispute + domain.

Outputs (validation/audit/):
  match_audit_items.csv     — Track A items (utf-8-sig for PowerShell)
  domain_audit_items.csv    — Track B items (blind)
  domain_answer_key.csv     — model labels for Track B (DO NOT open while coding)

Deterministic: SEED=42. Rerunning overwrites the item files; verdicts made by
the coder live in *_verdicts.csv and are never touched by this script.

CLI: python scripts/v90_build_audit_samples.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
AUD = ROOT / "validation" / "audit_regen"  # regenerated design check; the frozen items the verdicts were coded against live in validation/audit_blitz + audit_ra_partial
APO_JSON = ROOT / "data" / "raw" / "aposcripta.dataset.json"

SEED = 42
N_MATCH = 200
N_PER_DOMAIN = 25
TRANS_CAP = 2000  # same cap the recode model saw
LO, HI = 1100, 1300

DOMAINS = ["secular_territorial", "ecclesiastical_appointments", "crusade", "other",
           "excommunication", "ecclesiastical_property", "inheritance", "marriage"]


def _norm(x):
    if not isinstance(x, str):
        return ""
    return " ".join(x.split())


def load_doc_texts(need: set[str]) -> dict:
    print(f"loading letter texts for {len(need):,} docs from {APO_JSON.name} ...", flush=True)
    data = json.load(open(APO_JSON, encoding="utf-8"))
    tx = {}
    for it in data["datasetItems"]:
        did = str(it.get("itemIdTELMA", "")).strip()
        if did in need:
            tx[did] = {
                "analyse": _norm(it.get("analyse")),
                "regeste": _norm(it.get("regeste")),
                "destinataire": _norm(it.get("destinataire")),
                "transcription": _norm(it.get("transcription"))[:TRANS_CAP],
            }
    missing = need - set(tx)
    if missing:
        print(f"  WARNING: {len(missing)} sampled docs missing from raw JSON: {sorted(missing)[:5]} ...")
    return tx


def main():
    rng = np.random.default_rng(SEED)
    AUD.mkdir(parents=True, exist_ok=True)

    mt = pd.read_csv(OUT / "doc_matches_ai_extracted_high.csv", dtype={"doc_id": str, "person_id": str})
    mt = mt[(mt.doc_year >= LO) & (mt.doc_year <= HI)].copy()
    mt = mt.drop_duplicates(["person_id", "doc_id"])
    persons = pd.read_csv(OUT / "persons_imputed.csv", dtype={"id": str})[["id", "name", "birth", "death"]]
    br = pd.read_csv(OUT / "bloc_reach_fullgraph.csv", dtype={"person_id": str})
    sample = br[br.mother_n_dyn_4hop.notna()][["person_id", "n_dyn_4hop"]].copy()
    terc = sample.n_dyn_4hop.quantile([1 / 3, 2 / 3]).values
    sample["stratum_reach"] = np.where(sample.n_dyn_4hop <= terc[0], "reach_low",
                              np.where(sample.n_dyn_4hop <= terc[1], "reach_mid", "reach_high"))

    # ---------------- Track A: match audit ----------------
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
        picks.append(pool.sample(n=k, random_state=rng.integers(0, 2**31)))
    A = pd.concat(picks)
    if len(A) < N_MATCH:  # top up from the whole pool if a stratum ran dry
        extra = a.drop(A.index).sample(n=N_MATCH - len(A), random_state=int(rng.integers(0, 2**31)))
        A = pd.concat([A, extra])
    A = A.sample(frac=1, random_state=int(rng.integers(0, 2**31))).reset_index(drop=True)  # shuffle order

    tx = load_doc_texts(set(A.doc_id) | set())
    quote_col = next((c for c in ["quoted_latin", "quote", "evidence"] if c in A.columns), None)
    role_col = next((c for c in ["role", "person_role"] if c in A.columns), None)
    items = pd.DataFrame({
        "item_id": ["M%03d" % (i + 1) for i in range(len(A))],
        "doc_id": A.doc_id,
        "doc_year": A.doc_year.astype(int),
        "pope": A.pope.fillna(""),
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
    items.to_csv(AUD / "match_audit_items.csv", index=False, encoding="utf-8-sig")
    print(f"Track A: {len(items)} match items -> match_audit_items.csv")
    print(items.stratum.value_counts().to_string())

    # ---------------- Track B: domain audit (blind) ----------------
    coded = pd.read_csv(OUT / "matched_docs_coded.csv", dtype={"doc_id": str})
    coded = coded.drop_duplicates("doc_id")
    picks = []
    for i, dom in enumerate(DOMAINS):
        pool = coded[coded.domain == dom]
        k = min(len(pool), N_PER_DOMAIN)
        picks.append(pool.sample(n=k, random_state=int(rng.integers(0, 2**31))))
    B = pd.concat(picks).sample(frac=1, random_state=int(rng.integers(0, 2**31))).reset_index(drop=True)

    txb = load_doc_texts(set(B.doc_id))
    b_items = pd.DataFrame({
        "item_id": ["D%03d" % (i + 1) for i in range(len(B))],
        "doc_id": B.doc_id,
        "doc_year": B["year"],
        "pope": B.pope.fillna(""),
        "analyse": [txb.get(d, {}).get("analyse", "") for d in B.doc_id],
        "regeste": [txb.get(d, {}).get("regeste", "") for d in B.doc_id],
        "destinataire": [txb.get(d, {}).get("destinataire", "") for d in B.doc_id],
        "transcription": [txb.get(d, {}).get("transcription", "") for d in B.doc_id],
    })
    b_items.to_csv(AUD / "domain_audit_items.csv", index=False, encoding="utf-8-sig")

    key_cols = ["doc_id", "domain"] + [c for c in ["is_dispute", "dispute_parties", "matched_principal"] if c in B.columns]
    key = B[key_cols].copy()
    key.insert(0, "item_id", b_items.item_id)
    key.to_csv(AUD / "domain_answer_key.csv", index=False, encoding="utf-8-sig")
    print(f"Track B: {len(b_items)} blind domain items -> domain_audit_items.csv "
          f"(answer key sealed in domain_answer_key.csv)")
    print(B.domain.value_counts().to_string())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
