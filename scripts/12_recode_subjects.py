"""
recode_subjects.py
==================

One self-contained, reproducible pipeline that re-codes EVERY matched
APOSCRIPTA document (the distinct docs in doc_matches_ai_extracted_high.csv)
into a fixed subject scheme, using the Anthropic API directly. No per-batch
agent dispatch, no repeated permission prompts: run once.

It mirrors the project's existing 10_doc_match_batch_submit.py: env-var key,
Batch API (50% discount) with prompt caching, custom_id == doc_id, resumable
via on-disk per-doc cache, --estimate / --resume flags.

CODING SCHEME (two orthogonal axes; restrained vocabulary):
  is_dispute (yes/no) -> dispute_parties (lay_v_lay|church_v_lay|
      church_v_church|mixed) + matched_principal (yes/no)
  domain (one of: ecclesiastical_property, ecclesiastical_appointments, inheritance,
      marriage, crusade, excommunication, secular_territorial, other)
  + per-axis confidence + a prose summary.

USAGE
  set ANTHROPIC_API_KEY first.
  python recode_subjects.py --estimate            # cost preflight, no calls
  python recode_subjects.py --sync-test 5         # code 5 docs live, sync
  python recode_subjects.py --run                 # full Batch API run (resumable)
  python recode_subjects.py --resume msgbatch_xxx # poll+parse an existing batch
  python recode_subjects.py --merge               # rebuild CSV from cache only

OUTPUT
  codes_api/<doc_id>.json       one record per coded doc (the cache)
  matched_docs_coded.csv        merged final table
"""
from __future__ import annotations
import argparse, csv, html, json, os, re, sys, time
from collections import defaultdict, Counter
from pathlib import Path

import anthropic

# ----------------------------------------------------------------------------
# Repo-relative paths (script lives in scripts/ under the package root).
ROOT = Path(__file__).resolve().parent.parent        # package root
DATA = ROOT / "data" / "raw"
MATCH = ROOT / "output" / "doc_matches_ai_extracted_high.csv"
APO   = DATA / "aposcripta.dataset.json"
PEER  = DATA / "thePeerage.csv"
CACHE = ROOT / "output" / "recode_subjects_cache"     # per-doc JSON cache (resumable)
OUTCSV = ROOT / "output" / "matched_docs_coded.csv"   # merged final table
CACHE.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "claude-sonnet-4-6"
TRANS_CAP = 2000
OUTPUT_MAX_TOKENS = 1024

PRICING_BATCH = {  # per million tokens, Batch API (50% off list)
    "claude-haiku-4-5":  {"in": 0.40, "out": 2.00, "cache_write": 0.50, "cache_read": 0.04},
    "claude-sonnet-4-6": {"in": 1.50, "out": 7.50, "cache_write": 1.875, "cache_read": 0.15},
    "claude-opus-4-8":   {"in": 7.50, "out": 37.50, "cache_write": 9.375, "cache_read": 0.75},
}

csv.field_size_limit(min(sys.maxsize, 2147483647))

# ----------------------------------------------------------------------------
SYSTEM_PROMPT = r"""You code a single medieval papal document (APOSCRIPTA corpus, matched to The Peerage genealogical database) into a fixed scheme. You will be given the document's metadata, an editorial abstract ("Analyse", often French/German -- the scholarly summary, rely on it), a "Regeste", a Latin "Transcription" excerpt, and the matched Peerage persons (with role and the Latin phrase quoting them). Call the record_coding tool exactly once.

CRITICAL -- THE MATCHED PEERAGE PERSONS ARE A PARTIAL VIEW OF THE PARTIES.
The persons list contains ONLY the individuals the database happens to include. In a dispute, the matched noble's COUNTERPARTY is frequently NOT in the list -- it may be a bishop, abbey, cathedral chapter, monastery, town/commune, a non-noble, or a noble absent from the database. You MUST read the Analyse/Regeste/Transcription to identify ALL principal parties to any conflict, matched or not. NEVER conclude "no dispute" merely because only one side is a matched person. Code the document's substance, not the matched-persons list.

AXIS 1 -- is_dispute: "yes" or "no". "yes" only if the document concerns the Church handling an ACTUAL, LIVE conflict -- litigation, contested claim, arbitration, or peace-making -- between two or more parties identifiable IN THE DOCUMENT (not necessarily in the Peerage). A one-sided grant, a routine confirmation, or a mere mention of a past war/conflict as background is "no". The conflict must be the operative matter, not recited context.
  dispute_parties (only if yes): classify the PRINCIPAL parties as described in the document, regardless of Peerage match:
    "lay_v_lay"       -- all principals are lay (nobles, rulers, towns acting secularly).
    "church_v_lay"    -- at least one principal is ecclesiastical (pope, bishop, abbey, chapter, cleric) AND at least one is lay.
    "church_v_church" -- all principals are ecclesiastical (e.g. abbey v. bishop).
    "mixed"           -- multiple configurations, or parties cannot be cleanly resolved.
  matched_principal (only if yes): "yes" if AT LEAST ONE matched Peerage person is itself a principal party; "no" if every matched person appears only as an incidental mention, witness, prior donor, or neighbour while the real disputants are other (often unmatched) parties. Role hints: beneficiary/requestor/addressee usually = principal; subject_or_mention often = not.

AXIS 2 -- domain (the dominant operative act; assign whether or not it is a dispute). Choose exactly ONE:
- "ecclesiastical_property" -- donations, possessions, confirmations of CHURCH property, tithes/census/revenues, temporal ENDOWMENT of a benefice; church property as the stake of a dispute.
- "ecclesiastical_appointments" -- internal church administration & governance: provisions/appointments/ELECTIONS to office, clerical conduct/reform/celibacy/simony, privileges/indulgences/confessor-faculties to clergy.
- "inheritance" -- succession, legitimation of children, devolution of fiefs/titles/kingdoms by hereditary right.
- "marriage" -- marriage dispensations (consanguinity/affinity), validity/divorce/annulment, betrothals.
- "crusade" -- Holy Land/Reconquista/Baltic/Albigensian or political crusade; crusade finance, vows, indulgences, crusader protection.
- "excommunication" -- the censure/anathema/interdict, or absolution from it, as the substantive act.
- "secular_territorial" -- conflicts/settlements over SECULAR power: wars and papally-brokered peace/truces between rulers, sovereignty and territorial claims, contested secular fiefs/castles/realms, inter-realm or intra-dynastic political conflict NOT centred on church property or hereditary succession. (Lay-vs-lay territorial/sovereignty disputes belong HERE, not in "other".)
- "other" -- none of the above fits (e.g. heresy/Inquisition proceedings, pure diplomacy/news, fiscal matters). Set domain_other_detail to a short label.
TIE-BREAKS: church property/revenue -> ecclesiastical_property; office/person/governance -> ecclesiastical_appointments; secular fief/territory/sovereignty/inter-ruler war-and-peace -> secular_territorial; hereditary devolution -> inheritance. Multi-act letters -> code the dominant act.

DO NOT code on mere keyword presence. Code the OPERATIVE ACT, not the vocabulary:
- "Jerusalem" as a place name is NOT crusade.
- "patrimonium beati Petri" (the Papal State) is NOT inheritance.
- "ecclesiastice discipline contemptum" is NOT ecclesiastical_appointments.
- "investitus de regalibus" (enfeoffment with regalia) is NOT ecclesiastical_appointments.

WORKED CASES:
- Pope orders a count (matched) to stop molesting an abbey's lands -> yes, church_v_lay, matched_principal yes, ecclesiastical_property (abbey counterparty unmatched).
- Judges-delegate settle a quarrel between two bishops over a church; a local count (matched) appears only as a former donor -> yes, church_v_church, matched_principal no, ecclesiastical_property.
- Pope confirms a duke's (matched) donation to a priory, no opponent named -> no, ecclesiastical_property.
- Pope ratifies a peace between two kings ending a war over a kingdom -> yes, lay_v_lay, matched_principal yes, secular_territorial.

Rate is_dispute, dispute_parties, and domain each high/medium/low. For non-disputes leave dispute_parties, dispute_parties_conf, matched_principal empty. Leave domain_other_detail empty unless domain is "other". The summary is 2-4 sentences: what the document is, who the actual parties to any conflict are (naming unmatched counterparties), and why each matched person appears."""

CODING_TOOL = {
    "name": "record_coding",
    "description": "Record the coding of one document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "is_dispute": {"type": "string", "enum": ["yes", "no"]},
            "is_dispute_conf": {"type": "string", "enum": ["high", "medium", "low"]},
            "dispute_parties": {"type": "string", "enum": ["lay_v_lay", "church_v_lay", "church_v_church", "mixed", ""]},
            "dispute_parties_conf": {"type": "string", "enum": ["high", "medium", "low", ""]},
            "matched_principal": {"type": "string", "enum": ["yes", "no", ""]},
            "domain": {"type": "string", "enum": ["ecclesiastical_property", "ecclesiastical_appointments", "inheritance", "marriage", "crusade", "excommunication", "secular_territorial", "other"]},
            "domain_conf": {"type": "string", "enum": ["high", "medium", "low"]},
            "domain_other_detail": {"type": "string"},
        },
        "required": ["summary", "is_dispute", "is_dispute_conf", "dispute_parties",
                     "dispute_parties_conf", "matched_principal", "domain",
                     "domain_conf", "domain_other_detail"],
    },
}

# ----------------------------------------------------------------------------
def _norm(v):
    if v is None: return ""
    s = " ".join(str(x) for x in v if x is not None) if isinstance(v, list) else str(v)
    s = html.unescape(s); s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def load_data():
    rows = list(csv.DictReader(open(MATCH, encoding="utf-8")))
    doc_persons, doc_meta = defaultdict(list), {}
    for r in rows:
        d = r["doc_id"].strip(); doc_persons[d].append(r); doc_meta[d] = r
    docs = sorted(doc_persons, key=lambda d: (0, int(d)) if d.isdigit() else (1, d))
    need_p = {pr["person_id"].strip() for d in docs for pr in doc_persons[d]}

    data = json.load(open(APO, encoding="utf-8"))
    doc_text = {}
    need_d = set(docs)
    for it in data["datasetItems"]:
        did = str(it.get("itemIdTELMA", "")).strip()
        if did in need_d:
            doc_text[did] = {"analyse": _norm(it.get("analyse")), "regeste": _norm(it.get("regeste")),
                             "destinataire": _norm(it.get("destinataire")),
                             "transcription": _norm(it.get("transcription"))[:TRANS_CAP],
                             "genre": _norm(it.get("genre"))}
    peer = {}
    for row in csv.DictReader(open(PEER, encoding="cp1252", errors="replace")):
        link = (row.get("link") or "").strip()
        if link in need_p:
            peer[link] = {"name": (row.get("name") or "").strip(),
                          "birth": (row.get("birth") or "").strip(),
                          "death": (row.get("death") or "").strip()}
    return docs, doc_persons, doc_meta, doc_text, peer

def persons_str(did, doc_persons, peer):
    out = []
    for pr in doc_persons[did]:
        p = peer.get(pr["person_id"].strip(), {})
        out.append(f"{p.get('name','(unknown)')} ({pr.get('role','')})")
    return " | ".join(out)

def user_content(did, doc_persons, doc_meta, doc_text, peer):
    t, m = doc_text.get(did, {}), doc_meta.get(did, {})
    lines = [f"DOCUMENT id={did}",
             f"Year: {m.get('doc_year','?')} | Pope: {m.get('doc_pope','?')} | "
             f"Region: {m.get('doc_region','') or '-'} | Genre: {m.get('doc_genre','') or t.get('genre','')}"]
    if t.get("destinataire"): lines.append(f"Addressee: {t['destinataire']}")
    if t.get("analyse"): lines.append(f"\nAnalyse (editorial abstract): {t['analyse']}")
    if t.get("regeste"): lines.append(f"\nRegeste: {t['regeste']}")
    if t.get("transcription"): lines.append(f"\nTranscription (Latin, first {TRANS_CAP} chars): {t['transcription']}")
    lines.append("\nMatched Peerage persons:")
    for pr in doc_persons[did]:
        p = peer.get(pr["person_id"].strip(), {})
        lines.append(f"  - {p.get('name','(not found)')} (b.{p.get('birth','?')}/d.{p.get('death','?')}); "
                     f"role={pr.get('role','')}; quoted=\"{pr.get('quoted_latin','')}\"")
    return "\n".join(lines)

def build_params(did, doc_persons, doc_meta, doc_text, peer, model):
    return {
        "model": model,
        "max_tokens": OUTPUT_MAX_TOKENS,
        "temperature": 0,
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "tools": [CODING_TOOL],
        "tool_choice": {"type": "tool", "name": "record_coding"},
        "messages": [{"role": "user", "content": user_content(did, doc_persons, doc_meta, doc_text, peer)}],
    }

def extract_record(message):
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "record_coding":
            return block.input
    return None

def save_record(did, rec):
    (CACHE / f"{did}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")

def pending(docs):
    return [d for d in docs if not (CACHE / f"{d}.json").exists()]

# ----------------------------------------------------------------------------
def cmd_estimate(docs, doc_persons, doc_meta, doc_text, peer, model):
    # rough token estimate: system ~1700 tok (cached after first), per-doc user content
    sys_tok = len(SYSTEM_PROMPT) // 4
    user_toks = [len(user_content(d, doc_persons, doc_meta, doc_text, peer)) // 4 for d in docs]
    n = len(docs); pr = PRICING_BATCH.get(model, PRICING_BATCH[DEFAULT_MODEL])
    in_user = sum(user_toks)
    cache_write = sys_tok                      # written once
    cache_read = sys_tok * (n - 1)             # re-read per subsequent doc
    out_tok = n * 350
    cost = (in_user/1e6*pr["in"] + cache_write/1e6*pr["cache_write"]
            + cache_read/1e6*pr["cache_read"] + out_tok/1e6*pr["out"])
    print(f"Model {model} | docs={n}")
    print(f"  sys/doc ~{sys_tok} tok (cached) | mean user ~{in_user//n} tok | out ~350 tok/doc")
    print(f"  est input(user) {in_user:,} | cache_write {cache_write:,} | cache_read {cache_read:,} | out {out_tok:,}")
    print(f"  ESTIMATED BATCH COST: ${cost:,.2f}")

def cmd_sync_test(n, docs, doc_persons, doc_meta, doc_text, peer, model):
    client = anthropic.Anthropic()
    todo = pending(docs)[:n]
    print(f"Sync-coding {len(todo)} docs with {model} ...")
    for did in todo:
        msg = client.messages.create(**build_params(did, doc_persons, doc_meta, doc_text, peer, model))
        rec = extract_record(msg)
        if rec is None:
            print(f"  {did}: NO tool_use returned"); continue
        save_record(did, rec)
        print(f"  {did}: dispute={rec['is_dispute']}/{rec.get('dispute_parties','')} "
              f"domain={rec['domain']}{'/'+rec['domain_other_detail'] if rec['domain']=='other' else ''}")
    print("Done. (run --merge to build the CSV)")

def cmd_run(docs, doc_persons, doc_meta, doc_text, peer, model, limit):
    client = anthropic.Anthropic()
    todo = pending(docs)
    if limit: todo = todo[:limit]
    if not todo:
        print("All docs already cached. Nothing to submit."); return
    print(f"Submitting {len(todo)} docs to the Batch API ({model}) ...")
    requests = [{"custom_id": did,
                 "params": build_params(did, doc_persons, doc_meta, doc_text, peer, model)}
                for did in todo]
    batch = client.messages.batches.create(requests=requests)
    print(f"  batch id: {batch.id}  (save this; resume with --resume {batch.id})")
    _poll_and_parse(client, batch.id)

def cmd_resume(batch_id):
    client = anthropic.Anthropic()
    _poll_and_parse(client, batch_id)

def _poll_and_parse(client, batch_id):
    while True:
        b = client.messages.batches.retrieve(batch_id)
        c = b.request_counts
        print(f"  [{b.processing_status}] done={c.succeeded} err={c.errored} "
              f"proc={c.processing} cancel={c.canceled} expired={c.expired}", flush=True)
        if b.processing_status == "ended":
            break
        time.sleep(30)
    ok = err = 0
    for res in client.messages.batches.results(batch_id):
        did = res.custom_id
        if res.result.type == "succeeded":
            rec = extract_record(res.result.message)
            if rec is not None:
                save_record(did, rec); ok += 1
            else:
                err += 1; print(f"  {did}: no tool_use")
        else:
            err += 1; print(f"  {did}: {res.result.type}")
    print(f"Parsed: {ok} saved, {err} failed. (run --merge to build the CSV)")

# Legacy domain-label normalization: the frozen recode cache predates the
# clerical_discipline -> ecclesiastical_appointments relabel (2026-06-24).
# Map on merge so a rebuilt CSV uses the current label WITHOUT mutating the
# frozen per-doc cache.
_LEGACY_DOMAIN = {"clerical_discipline": "ecclesiastical_appointments"}


def cmd_merge(docs, doc_persons, doc_meta, peer):
    cols = ["doc_id", "year", "pope", "region", "genre", "persons", "summary",
            "is_dispute", "is_dispute_conf", "dispute_parties", "dispute_parties_conf",
            "matched_principal", "domain", "domain_conf", "domain_other_detail"]
    n = 0
    with open(OUTCSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL); w.writeheader()
        for did in docs:
            fp = CACHE / f"{did}.json"
            if not fp.exists(): continue
            rec = json.loads(fp.read_text(encoding="utf-8")); m = doc_meta.get(did, {})
            w.writerow({"doc_id": did, "year": m.get("doc_year",""), "pope": m.get("doc_pope",""),
                        "region": m.get("doc_region",""), "genre": m.get("doc_genre",""),
                        "persons": persons_str(did, doc_persons, peer),
                        "summary": rec.get("summary",""),
                        "is_dispute": rec.get("is_dispute",""), "is_dispute_conf": rec.get("is_dispute_conf",""),
                        "dispute_parties": rec.get("dispute_parties",""), "dispute_parties_conf": rec.get("dispute_parties_conf",""),
                        "matched_principal": rec.get("matched_principal",""),
                        "domain": _LEGACY_DOMAIN.get(rec.get("domain",""), rec.get("domain","")),
                        "domain_conf": rec.get("domain_conf",""),
                        "domain_other_detail": rec.get("domain_other_detail","")}); n += 1
    print(f"Wrote {n} rows -> {OUTCSV}")
    cov = sum(1 for d in docs if (CACHE / f'{d}.json').exists())
    print(f"Coverage: {cov}/{len(docs)} docs coded ({100*cov/len(docs):.1f}%)")
    if n:
        recs = [json.loads((CACHE/f'{d}.json').read_text(encoding='utf-8')) for d in docs if (CACHE/f'{d}.json').exists()]
        print("  is_dispute:", dict(Counter(r['is_dispute'] for r in recs)))
        print("  domain    :", dict(Counter(r['domain'] for r in recs).most_common()))

# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--sync-test", type=int, metavar="N")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--resume", metavar="BATCH_ID")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    if a.resume:
        cmd_resume(a.resume)
        docs, doc_persons, doc_meta, _, peer = load_data()
        cmd_merge(docs, doc_persons, doc_meta, peer); return

    print("Loading source data ...", flush=True)
    docs, doc_persons, doc_meta, doc_text, peer = load_data()
    print(f"  {len(docs)} distinct matched docs | {len(peer)} persons | "
          f"{sum((CACHE/f'{d}.json').exists() for d in docs)} already cached", flush=True)

    if a.estimate:   cmd_estimate(docs, doc_persons, doc_meta, doc_text, peer, a.model)
    elif a.sync_test: cmd_sync_test(a.sync_test, docs, doc_persons, doc_meta, doc_text, peer, a.model)
    elif a.run:      cmd_run(docs, doc_persons, doc_meta, doc_text, peer, a.model, a.limit); cmd_merge(docs, doc_persons, doc_meta, peer)
    elif a.merge:    cmd_merge(docs, doc_persons, doc_meta, peer)
    else:            print("Nothing to do. Use --estimate | --sync-test N | --run | --resume ID | --merge")

if __name__ == "__main__":
    main()
