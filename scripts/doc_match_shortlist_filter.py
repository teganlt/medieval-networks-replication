"""
doc_match_shortlist_filter.py
==============================

Name-presence shortlist pre-filter for the Sonnet AI extraction pipeline.

THE IDEA
--------
Each rendered prompt currently includes the full era-eligible shortlist
(median ~1,634 candidates per doc). For any given doc, the vast majority
of those candidates have first names that don't appear ANYWHERE in the
Latin or French text. They are dead weight that Sonnet ignores at scale,
costing ~$0.04/doc in input tokens.

This module:
  1. Provides `filter_shortlist(candidates, doc_text, ...)` - drop any
     candidate whose normalized first-name prefix does not appear in the
     doc text. Royal-tier candidates are always retained (since medieval
     papal letters frequently address monarchs by title alone).
  2. Provides a CLI to validate the filter against the pilot's 150 Sonnet
     matches: how many TRUE matches would survive? Median shortlist size
     before vs after?

The filter is the single largest cost-reduction in the pipeline:
median shortlist 1,634 -> ~160 candidates per doc, ~90% input-token
reduction at the prompt level.

Run as a script:
  python doc_match_shortlist_filter.py

Validates prefix_len=4 across three tiers (name-only, +Royal, +Royal+Ducal)
against the pilot's match set. Reports recall on Sonnet's matches +
shortlist-size reduction stats + projected cost savings.

Inputs (only used by the CLI validation harness; not by filter_shortlist):
  output/batches_reextract/docs/                 per-doc payloads
  output/doc_matches_ai_extracted.csv            pilot matches
  output/reextract_validation_aggregated.csv     hand-validation verdicts
"""
from __future__ import annotations
import csv
import json
import statistics
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
DOCS_DIR = OUT / "batches_reextract" / "docs"

# Sonnet batch pricing (per million tokens, 50% off list)
SONNET_BATCH_IN = 1.50
SONNET_BATCH_OUT = 7.50
FULL_CORPUS_DOCS = 24_000  # era-eligible doc count for scale-up

# Tokens-per-character heuristic (matches the pilot's estimator).
TOKENS_PER_CHAR = 0.25  # i.e. 4 chars per token

# Stop-words / particles that are NOT names, even though they may appear
# at the start of a candidate `name` field for some entries.
STOPWORD_PREFIXES = {"de", "of", "the", "von", "van", "la", "le", "el"}

# Regnal-tier markers - substrings (case-insensitive) of the candidate
# `name` field that mark the person as a monarch / consort / emperor.
# These candidates are always kept regardless of name presence, since
# medieval papal letters frequently address them by title alone
# ('illustri regi Anglie', 'regina Anglie ilustris').
ROYAL_MARKERS = (
    "king", "queen", "emperor", "empress", "imperator", "imperatrix",
    "kaiser", "tsar", "tzar",
    "roi ", "reine ", "rey ", "reina ", " re ",   # Romance forms
    "konig", "konigin",                            # German
)

# Ducal-tier markers - covers Duke / Duc / Herzog / Doge.
# Used only if include_ducal=True.
DUCAL_MARKERS = (
    "duke ", "duke,", "duke of",
    "duc ", "duc,", "duc de",
    "herzog",
    "duchess", "duchesse",
    "doge",
)


# Latin-equivalent root prefixes for high-frequency medieval names whose
# modern (French/English/German/Spanish) form diverges from the Latin
# form by character 2-3, so plain prefix matching fails. Each entry maps
# a normalized modern first-name token to one or more 3-5 char roots; a
# candidate survives if ANY of its roots appears in the doc text.
#
# Tokens here are POST-normalize (lower, no diacritics, j->i, k->c, etc.).
# After that pre-pass: Karl/Charles -> "carl"/"charles", Heinrich ->
# "heinrich", Jean -> "iean", Iohannes -> "iohannes", etc.
LATIN_ROOTS: dict[str, list[str]] = {
    # Henry family (modern French/English/German all converge on Latin Henr-)
    "henry":     ["henr", "heinr", "hend"],
    "henri":     ["henr", "heinr", "hend"],
    "heinrich":  ["henr", "heinr", "hend"],
    "hendrik":   ["henr", "heinr", "hend"],
    "harry":     ["henr"],
    "enrico":    ["henr"],
    "enrique":   ["henr"],
    "enric":     ["henr"],
    # John / Jean family. After j->i: jean -> iean, john -> iohn
    "jean":      ["iohan", "ioann", "iohn"],
    "iean":      ["iohan", "ioann", "iohn"],
    "john":      ["iohan", "ioann", "iohn"],
    "iohn":      ["iohan", "ioann"],
    "iohann":    ["iohan", "ioann"],
    "iohannes":  ["iohan", "ioann"],
    "ioannes":   ["iohan", "ioann"],
    "iohanna":   ["iohan", "ioann"],
    "ioanna":    ["iohan", "ioann"],
    "iohanne":   ["iohan", "ioann"],
    "iohanni":   ["iohan", "ioann"],
    "joanna":    ["iohan", "ioann"],
    "jeanne":    ["iohan", "ioann"],
    "ieanne":    ["iohan", "ioann"],
    "juan":      ["iohan", "ioann", "iuan"],
    "iuan":      ["iohan", "ioann", "iuan"],
    "joao":      ["iohan", "ioann"],
    "ioao":      ["iohan", "ioann"],
    # William / Guillaume / Wilhelm - Latin Willelm-/Guillelm-
    "william":   ["will", "wilh", "guill", "gillem", "gilelm", "wilelm"],
    "guillaume": ["will", "wilh", "guill", "gillem", "gilelm", "wilelm"],
    "guilelm":   ["will", "guill", "gilelm"],
    "willelm":   ["will", "guill", "gilelm"],
    "wilhelm":   ["will", "wilh", "guill", "wilelm"],
    "wilelmus":  ["will", "wilelm", "guill"],
    "guglielmo": ["will", "guill", "gilelm"],
    "gilberto":  ["gilb", "gisl"],
    # Louis / Ludwig / Ludovicus
    "louis":     ["ludov", "ludow", "lodov", "loys", "ludevic"],
    "ludwig":    ["ludov", "ludow", "lodov", "ludwig"],
    "ludovico":  ["ludov", "ludow"],
    "ludovic":   ["ludov", "ludow"],
    "lodovico":  ["ludov", "lodov"],
    # Peter / Pierre / Pedro - Latin Petr-
    "peter":     ["petr"],
    "pierre":    ["petr"],
    "pedro":     ["petr", "pedr"],
    "petrus":    ["petr"],
    "petri":     ["petr"],
    "pere":      ["petr", "pere"],
    "piero":     ["petr"],
    "pietro":    ["petr"],
    # James / Jacques / Jaime / Iacobus
    "james":     ["iacob", "iacom", "iaco"],
    "jaime":     ["iacob", "iacom", "iaco"],
    "iaime":     ["iacob", "iaco"],
    "jacques":   ["iacob", "iaco"],
    "iacques":   ["iacob", "iaco"],
    "iago":      ["iacob"],
    "iacobus":   ["iacob"],
    "iacopo":    ["iacob"],
    "iacomo":    ["iacob", "iacom"],
    # Charles / Karl / Carlos / Carolus
    "charles":   ["carol", "carl", "char"],
    "charl":     ["carol", "carl"],
    "karl":      ["carol", "carl"],
    "carl":      ["carol", "carl"],
    "carlo":     ["carol", "carl"],
    "carlos":    ["carol", "carl"],
    "carolus":   ["carol", "carl"],
    # Frederick / Friedrich / Federico / Fadrique - Latin Frider-/Freder-
    "frederick": ["frider", "freder", "friedr", "feder"],
    "friedrich": ["frider", "freder", "friedr", "feder", "friedr"],
    "federico":  ["frider", "freder", "feder"],
    "federic":   ["frider", "freder", "feder"],
    "fadrique":  ["frider", "freder", "feder"],
    "fridericus": ["frider"],
    # Godfrey / Godefroi / Gotfried - Latin Godefr-/Gotefr-
    "godfrey":   ["godefr", "gotefr", "godfr", "gotfr"],
    "godefroy":  ["godefr", "gotefr"],
    "godefroi":  ["godefr", "gotefr"],
    "gottfried": ["godefr", "gotefr", "gotfr"],
    "goffredo":  ["godefr", "goffr"],
    # Edmund - also Latin Eadmund-
    "edmund":    ["edmun", "eadmu", "aedmu"],
    "eadmund":   ["edmun", "eadmu"],
    "edmondo":   ["edmun"],
    # Edward - also Latin Eadward-/Aedward-
    "edward":    ["edwar", "eadwa", "aedwa"],
    "eduardo":   ["edwar", "eadwa", "eduar"],
    # Alphonse / Alfonso - Latin Alfons-
    "alphonse":  ["alfons", "alphons"],
    "alfonso":   ["alfons", "alphons"],
    "alfonse":   ["alfons", "alphons"],
    "alphonso":  ["alfons", "alphons"],
    # Stephen / Etienne / Stefano - Latin Stephan-
    "stephen":   ["stephan", "stephen", "stefan", "estev"],
    "stefano":   ["stephan", "stefan"],
    "etienne":   ["stephan", "stefan", "estev"],
    "esteban":   ["stephan", "estev"],
    "istvan":    ["stephan", "stefan"],
    # Conrad / Konrad / Corradus
    "conrad":    ["conrad", "cuonrad", "konrad", "corrad", "corad"],
    "konrad":    ["conrad", "cuonrad", "konrad", "corrad"],
    "corrado":   ["conrad", "corrad", "corad"],
    # Otto
    "otto":      ["otto", "oddo", "otho"],
    # Mathilda / Maud / Matilde
    "mathilda":  ["mathild", "matild", "mahalt", "maud"],
    "matilda":   ["mathild", "matild", "mahalt", "maud"],
    "matilde":   ["mathild", "matild", "maud"],
    "mathilde":  ["mathild", "matild", "maud"],
    "maud":      ["mathild", "matild"],
    # Margaret / Marguerite / Margarita - Latin Margaret-/Margarit-
    "margaret":  ["margar"],
    "marguerite": ["margar"],
    "margarita": ["margar"],
    "margherita": ["margar"],
    # Eleanor / Alienor / Eleonora - Latin Alienor-
    "eleanor":   ["alienor", "elienor", "eleon"],
    "alienor":   ["alienor", "elienor", "eleon"],
    "eleonora":  ["alienor", "eleon"],
    "leonor":    ["alienor", "leonor"],
    # Berengaria - Latin Berengar-
    "berengaria": ["berengar"],
    "berenguer":  ["berengar"],
    # Raymond / Ramon - Latin Raimund-/Ramond-
    "raymond":   ["raimun", "raimon", "raymon", "ramon"],
    "raimond":   ["raimun", "raimon", "ramon"],
    "ramon":     ["raimun", "raimon", "ramon"],
    # Robert / Rodbert / Rotbert
    "robert":    ["rober", "rotber", "rodber"],
    "ruperto":   ["rober", "ruper"],
    # Richard
    "richard":   ["ricar", "richar"],
    "ricardo":   ["ricar"],
    # Geoffrey / Geoffroy / Goffredo - Latin Galfrid-/Gausfrid-/Gaufrid-
    "geoffrey":  ["galfri", "gausfri", "gaufri", "geofr"],
    "geoffroy":  ["galfri", "gausfri", "gaufri", "geofr"],
    "goffredo":  ["galfri", "gausfri", "goffre"],
    # Anjou / Angevin handling for popular Anjou names
    "fulk":      ["fulco", "fulk"],
    "fulco":     ["fulco", "fulk"],
    # Theobald / Thibaut / Tibald - Latin Theobald-/Theobaud-
    "theobald":  ["theobald", "thibau", "tebald"],
    "thibaut":   ["theobald", "thibau"],
    "thibault":  ["theobald", "thibau"],
    "tebaldo":   ["theobald", "tebald"],
    # Hugh / Hugues / Hugo - Latin Hugo/Hugon-
    "hugh":      ["hugo", "hugon"],
    "hugues":    ["hugo", "hugon"],
    "hugo":      ["hugo", "hugon"],
    "ugo":       ["hugo", "hugon"],
    "ugon":      ["hugo", "hugon"],
    # Albert / Adalbert / Albrecht
    "albert":    ["albert", "adalber", "aelbert", "alber"],
    "adalbert":  ["albert", "adalber", "alber"],
    "albrecht":  ["albert", "adalber", "alber"],
    # Leopold / Liutpold / Lipoldus
    "leopold":   ["leopold", "liupold", "liutpold", "leupold", "lipold"],
    "leupold":   ["leopold", "liupold", "leupold", "lipold"],
    # Premysl / Ottokar (Bohemian) - Latin Premizl-/Otokar-/Othakar-
    "premysl":   ["premysl", "premizl", "primizl", "primisl",
                  "ottocar", "ottokar", "othakar", "otacar"],
    "ottokar":   ["ottocar", "ottokar", "othakar", "otacar"],
    # Fernando / Ferdinand - Latin Ferdinand-
    "fernando":  ["ferdin", "ferdinan"],
    "ferdinand": ["ferdin", "ferdinan"],
    "ferran":    ["ferdin", "ferran"],
    # Bohemond / Bohemund
    "bohemond":  ["boemund", "boamund", "boamondo"],
    "boemundo":  ["boemund", "boamund"],
    # Tancred
    "tancred":   ["tancred", "tancreda"],
    # Renaud / Reynold
    "renaud":    ["rainald", "reginald", "renald"],
    "reynold":   ["rainald", "reginald", "renald"],
    "reginald":  ["rainald", "reginald", "renald"],
    "renald":    ["rainald", "renald"],
    # Manfred
    "manfred":   ["manfred", "manfredo"],
    "manfredo":  ["manfred", "manfredo"],
    # Phillip / Philippe / Felipe - Latin Philipp-/Filipp-
    "philip":    ["philip", "filipp", "philipp"],
    "philippe":  ["philip", "filipp", "philipp"],
    "philipp":   ["philip", "filipp"],
    "felipe":    ["philip", "filipp", "felipp"],
    "filippo":   ["philip", "filipp"],
    "phillip":   ["philip", "filipp"],
    # Conan / Conon
    "conan":     ["conan", "conon", "cuanan"],
    "conon":     ["conan", "conon"],
    # Anglo-Saxon names (E-/Ae- in Latin)
    "alfred":    ["aelfred", "alfred"],
    "ethelred":  ["aethelred", "ethelred", "ethelr"],
    "eadgar":    ["edgar", "eadgar"],
    "edgar":     ["edgar", "eadgar"],
    "harold":    ["harold", "haroald", "haral"],
    # Sancho (Iberian)
    "sancho":    ["sancho", "santiu", "sancii"],
    "sancha":    ["sancha", "sanci"],
    # Berthold / Bertrand
    "berthold":  ["bertold", "berthold"],
    "bertrand":  ["bertran"],
    # Mary / Marie / Maria
    "mary":      ["maria"],
    "marie":     ["maria"],
    "maria":     ["maria"],
}


# ---------- Normalization helpers ----------

def strip_diacritics(s: str) -> str:
    """Remove combining marks: 'Helene' -> 'Helene'."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """Lowercase + strip diacritics + light medieval-Latin orthographic
    equivalence (j->i, k->c, ae/oe ligatures expanded) + strip editorial
    brackets/parens. Used on both doc text and candidate names so the
    comparison is symmetric.

    NOT applied: v->u (would break 'Ludovico'); ae->e (too aggressive,
    kills 'Caesar', 'Aelfric'). Instead, the LATIN_ROOTS table lists all
    relevant medieval-Latin variants explicitly.

    Bracket/paren stripping recovers editorial reconstructions common in
    APOSCRIPTA: 'C[arolus]' -> 'carolus', 'Ph[ilippum]' -> 'philippum',
    'K(aroli)' -> 'caroli'.
    """
    s = strip_diacritics(text).lower()
    s = (s.replace("j", "i")
          .replace("k", "c")
          .replace("æ", "ae").replace("œ", "oe"))
    for ch in "[]()":
        s = s.replace(ch, "")
    return s


# Normalize the LATIN_ROOTS table keys + values once at import.
_LATIN_ROOTS_NORM: dict[str, list[str]] = {
    normalize(k): [normalize(r) for r in v]
    for k, v in LATIN_ROOTS.items()
}


def first_name_token(candidate_name: str) -> str:
    """Pull the leading personal-name token.

    Candidate names are formatted as
        '<personal name> [byname/ordinal/of-place], <title>'
    Examples:
        'Agnes de Poitou'                         -> 'agnes'
        'Henry II Curtmantle dAnjou, King of En.' -> 'henry'
        'Hugues IV de Bourgogne'                  -> 'hugues'

    The pre-comma half is always the personal name; strip the post-comma
    title rather than guess between halves.
    """
    norm = normalize(candidate_name).strip()
    if "," in norm:
        norm = norm.split(",", 1)[0].strip()
    raw = norm.replace("(", " ").replace(")", " ").replace("'", " ")
    tokens = [t for t in raw.split() if t]
    for t in tokens:
        if t in STOPWORD_PREFIXES:
            continue
        if t.isdigit():
            continue
        if not t.isalpha():
            continue
        return t
    return tokens[0] if tokens else ""


# ---------- Filter ----------

def make_doc_haystack(payload: dict) -> str:
    """Concatenated normalized text used for name-presence checks."""
    return normalize((payload.get("analyse") or "") + " " +
                     (payload.get("transcription") or ""))


def has_regnal_marker(candidate: dict, markers: tuple[str, ...]) -> bool:
    nm = (candidate.get("name") or "").lower()
    return any(m in nm for m in markers)


def candidate_survives(candidate: dict, haystack: str, prefix_len: int,
                       include_royal: bool = False,
                       include_ducal: bool = False) -> bool:
    """True if the candidate should be kept on the post-filter shortlist.

    Inclusion rules (any one passes):
      1. include_royal=True AND candidate's name has a royal-tier marker
         (King / Queen / Emperor / Empress / Roi / Rey / etc.) - recovers
         title-only references like 'regi Aragonum'.
      2. include_ducal=True AND candidate's name has a ducal-tier marker
         (Duke / Duc / Herzog / Doge).
      3. First-name token has a Latin-equivalent root in LATIN_ROOTS, and
         at least one of those roots appears in the haystack.
      4. Default: first prefix_len chars of the normalized first name
         appear in the haystack. Short names (< prefix_len) require
         exact substring match.
    """
    if include_royal and has_regnal_marker(candidate, ROYAL_MARKERS):
        return True
    if include_ducal and has_regnal_marker(candidate, DUCAL_MARKERS):
        return True

    fn = first_name_token(candidate.get("name", ""))
    if not fn:
        return True

    roots = _LATIN_ROOTS_NORM.get(fn)
    if roots is not None:
        return any(r in haystack for r in roots)
    if len(fn) < prefix_len:
        return fn in haystack
    return fn[:prefix_len] in haystack


def filter_shortlist(candidates: list[dict], doc_text: str,
                     prefix_len: int = 4,
                     include_royal: bool = False,
                     include_ducal: bool = False) -> list[dict]:
    """Return only candidates whose first-name prefix appears in doc_text
    (with optional always-include for royal/ducal-marked candidates)."""
    haystack = normalize(doc_text)
    return [c for c in candidates
            if candidate_survives(c, haystack, prefix_len,
                                  include_royal=include_royal,
                                  include_ducal=include_ducal)]


# ---------- Token-size estimator ----------

def candidate_line_chars(c: dict) -> int:
    """Approximate the char-length of one shortlist row in the prompt.
    Format: 'p3.htm#i27 | Agnes de Poitou | F | 1018-1077 | Salian'"""
    return (len(str(c.get("id", ""))) + len(str(c.get("name", ""))) +
            len(str(c.get("sex", ""))) + len(str(c.get("b", ""))) +
            len(str(c.get("d", ""))) + len(str(c.get("dyn", ""))) +
            len(" | | | -- | "))


# ---------- Validation harness (CLI) ----------

def load_doc_payload(doc_id: str) -> dict:
    p = DOCS_DIR / f"doc_{doc_id}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def load_pilot_matches() -> list[dict]:
    """All pilot Sonnet matches (overlap + AI-only)."""
    out = []
    path = OUT / "doc_matches_ai_extracted.csv"
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append(r)
    return out


def load_validation_verdicts() -> dict[tuple[str, str], str]:
    """Map (doc_id, person_id) -> verdict (TRUE/PLAUSIBLE/FALSE) for the
    119 AI-only matches that were validated."""
    out = {}
    path = OUT / "reextract_validation_aggregated.csv"
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[(r["doc_id"], r["person_id"])] = r["verdict"]
    return out


def validate_prefix_len(prefix_len: int,
                        include_royal: bool = False,
                        include_ducal: bool = False) -> dict:
    """Run the filter against the pilot data; collect stats."""
    matches = load_pilot_matches()
    verdicts = load_validation_verdicts()

    doc_ids_in_matches = {m["doc_id"] for m in matches}
    payloads = {did: load_doc_payload(did) for did in doc_ids_in_matches}

    by_verdict = {"TRUE": [0, 0], "PLAUSIBLE": [0, 0], "FALSE": [0, 0],
                  "overlap": [0, 0], "unknown": [0, 0]}
    misses = []
    for m in matches:
        did, pid = m["doc_id"], m["person_id"]
        payload = payloads.get(did, {})
        if not payload:
            continue
        cand = next((c for c in payload.get("candidates", [])
                     if c["id"] == pid), None)
        if cand is None:
            continue
        haystack = make_doc_haystack(payload)
        survives = candidate_survives(cand, haystack, prefix_len,
                                      include_royal=include_royal,
                                      include_ducal=include_ducal)

        if m.get("is_regex_overlap") == "1":
            key = "overlap"
        else:
            key = verdicts.get((did, pid), "unknown")
        by_verdict[key][0] += 1
        if survives:
            by_verdict[key][1] += 1
        else:
            misses.append({
                "doc_id": did, "person_id": pid,
                "candidate_name": cand.get("name", ""),
                "first_name_token": first_name_token(cand.get("name", "")),
                "quoted_latin": m.get("quoted_latin", "")[:80],
                "verdict": key,
            })

    sizes_before, sizes_after = [], []
    char_before, char_after = [], []
    for did, payload in payloads.items():
        cands = payload.get("candidates", [])
        if not cands:
            continue
        sizes_before.append(len(cands))
        kept = filter_shortlist(cands, make_doc_haystack(payload),
                                prefix_len,
                                include_royal=include_royal,
                                include_ducal=include_ducal)
        sizes_after.append(len(kept))
        char_before.append(sum(candidate_line_chars(c) for c in cands))
        char_after.append(sum(candidate_line_chars(c) for c in kept))

    return {
        "prefix_len": prefix_len,
        "include_royal": include_royal,
        "include_ducal": include_ducal,
        "by_verdict": by_verdict,
        "misses": misses,
        "n_docs": len(sizes_before),
        "median_before": int(statistics.median(sizes_before)) if sizes_before else 0,
        "median_after": int(statistics.median(sizes_after)) if sizes_after else 0,
        "mean_before": int(statistics.mean(sizes_before)) if sizes_before else 0,
        "mean_after": int(statistics.mean(sizes_after)) if sizes_after else 0,
        "median_char_before": int(statistics.median(char_before)) if char_before else 0,
        "median_char_after": int(statistics.median(char_after)) if char_after else 0,
        "mean_char_before": int(statistics.mean(char_before)) if char_before else 0,
        "mean_char_after": int(statistics.mean(char_after)) if char_after else 0,
    }


def project_savings(stats: dict, instruction_chars: int = 12_000,
                    doc_text_chars: int = 12_000,
                    output_tokens_per_doc: int = 3000) -> dict:
    """Project full-corpus Sonnet cost before vs after filter."""
    in_chars_before = instruction_chars + doc_text_chars + stats["mean_char_before"]
    in_chars_after = instruction_chars + doc_text_chars + stats["mean_char_after"]
    in_tok_before = int(in_chars_before * TOKENS_PER_CHAR)
    in_tok_after = int(in_chars_after * TOKENS_PER_CHAR)
    cost_before = FULL_CORPUS_DOCS * (
        in_tok_before * SONNET_BATCH_IN +
        output_tokens_per_doc * SONNET_BATCH_OUT
    ) / 1_000_000
    cost_after = FULL_CORPUS_DOCS * (
        in_tok_after * SONNET_BATCH_IN +
        output_tokens_per_doc * SONNET_BATCH_OUT
    ) / 1_000_000
    return {
        "in_tok_before": in_tok_before, "in_tok_after": in_tok_after,
        "cost_before": cost_before, "cost_after": cost_after,
        "savings": cost_before - cost_after,
    }


def print_report(stats: dict):
    pl = stats["prefix_len"]
    tier_bits = []
    if stats.get("include_royal"):
        tier_bits.append("+ROYAL")
    if stats.get("include_ducal"):
        tier_bits.append("+DUCAL")
    tier_label = "  ".join(tier_bits) if tier_bits else "(name-only)"
    print(f"\n{'='*70}")
    print(f"PREFIX LENGTH = {pl}   {tier_label}")
    print(f"{'='*70}")
    print(f"\nRecall on Sonnet's pilot matches:")
    print(f"  {'verdict':<12} {'survive':>10} {'total':>10} {'recall':>10}")
    total_n = total_s = 0
    for k in ["TRUE", "PLAUSIBLE", "FALSE", "overlap", "unknown"]:
        total, survives = stats["by_verdict"][k]
        if total == 0:
            continue
        recall = 100 * survives / total
        flag = "" if recall == 100 else "  <-- MISSES"
        print(f"  {k:<12} {survives:>10} {total:>10} {recall:>9.1f}%{flag}")
        total_n += total
        total_s += survives
    overall = 100 * total_s / total_n if total_n else 0
    print(f"  {'OVERALL':<12} {total_s:>10} {total_n:>10} {overall:>9.1f}%")

    if stats["n_docs"]:
        print(f"\nShortlist size reduction (n={stats['n_docs']} docs):")
        print(f"  median:  {stats['median_before']:>5} -> "
              f"{stats['median_after']:>5} "
              f"({100 * stats['median_after'] / max(stats['median_before'], 1):.1f}%)")
        print(f"  mean:    {stats['mean_before']:>5} -> "
              f"{stats['mean_after']:>5} "
              f"({100 * stats['mean_after'] / max(stats['mean_before'], 1):.1f}%)")

        proj = project_savings(stats)
        print(f"\nFull-corpus projection ({FULL_CORPUS_DOCS:,} docs, "
              f"Sonnet 4.6 batch):")
        print(f"  input tokens/doc:  {proj['in_tok_before']:,} -> "
              f"{proj['in_tok_after']:,}")
        print(f"  total cost:        ${proj['cost_before']:,.0f} -> "
              f"${proj['cost_after']:,.0f}")
        print(f"  savings:           ${proj['savings']:,.0f}")


def main():
    print(f"Loading docs from: {DOCS_DIR}")
    print(f"Loading pilot matches:   {OUT / 'doc_matches_ai_extracted.csv'}")
    print(f"Loading verdicts:        {OUT / 'reextract_validation_aggregated.csv'}")

    tiers = [
        {"include_royal": False, "include_ducal": False},
        {"include_royal": True,  "include_ducal": False},
        {"include_royal": True,  "include_ducal": True},
    ]
    for t in tiers:
        stats = validate_prefix_len(4, **t)
        print_report(stats)


if __name__ == "__main__":
    main()
