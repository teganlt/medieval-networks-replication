"""
doc_match_prompt.py
====================

Prompt template + builder for the per-document AI extraction.

Public API:
  build_subagent_prompt(doc_payload: dict, output_path: str,
                        *, v3: bool = False) -> str

The Anthropic batch submitter (10_doc_match_batch_submit.py) is what calls
this. Each doc gets one rendered prompt + one verdicts JSONL output.

v3=True applies the +Royal shortlist filter (see doc_match_shortlist_filter)
AND uses the compressed candidate row format AND emits the strengthened
prompt template (Rule 1 two-check version, Rule 4 peerage-cleric
clarification, FP (h) wrong-candidate substitution, counter-example,
WORK CAREFULLY verification checklist). Produces a prompt that is
byte-identical (in its shared preamble) across all docs, enabling
Anthropic prompt caching.

The DOC_SECTION_MARKER constant is the boundary between the shared
preamble (cached) and the doc-specific tail (uncached). The batch
submitter splits the prompt here before assigning cache_control.

Companion files:
  08_doc_match_build_candidates.py    upstream  - produces per-doc payloads
  09_doc_match_render_prompts.py      this file's caller - renders prompts
  10_doc_match_batch_submit.py        downstream - submits prompts to API
  11_doc_match_build_person_summary.py  downstream - aggregates verdicts
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

# Add this file's directory to sys.path so we can import the sibling
# shortlist filter even when called from elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_match_shortlist_filter import filter_shortlist  # noqa: E402


# Marker where the shared-across-docs preamble ends and the doc-specific
# portion begins. Used by the batch submitter to split for prompt caching.
DOC_SECTION_MARKER = "# THE DOCUMENT"


PROMPT_TEMPLATE = """\
You are a medieval Latin and canon-law specialist performing CLOSED-SET
person extraction on a single papal letter from the APOSCRIPTA corpus.

# THE TASK
Identify every reference in this document to a person on the CANDIDATE
SHORTLIST below. The shortlist is the closed universe of possible
matches: European royal/noble peerage whose lifespan intersects
[doc_year - 15, doc_year + 15].

For each match, produce one JSONL record with: the candidate's person_id
(from the shortlist), exact Latin quotation, French analogue (if present
in the analyse field), role, confidence level, brief reasoning, and
inferred subjects.

# RULES

1. CLOSED-SET MATCHING -- TWO CHECKS, BOTH REQUIRED.
   (a) The person_id you emit MUST appear verbatim in the supplied
       candidate list. Never invent, guess, or partially construct a
       person_id.
   (b) The candidate you choose MUST refer to the SAME HISTORICAL
       INDIVIDUAL the doc names -- not merely someone with a similar
       title, a similar first name, or a lifespan that happens to
       overlap the doc year. Verify BOTH the candidate's full name
       AND lifespan against the person identified in your quoted_latin.
       If no candidate matches both, you MUST record them in
       `unmatched_named_persons` per Rule 4. Do NOT substitute another
       candidate as a stand-in. An empty match list is always preferable
       to a wrong match.

2. ONE RECORD PER (DOC, PERSON). If a person is mentioned multiple times
   in one doc, emit a single record and combine all quotations.

3. CONTEXT-DRIVEN DISAMBIGUATION. Many candidates share first names. Use
   ALL available context to pick the right one: title in the doc, region
   or diocese in the doc, candidate's dynasty, candidate's dates relative
   to doc year. If two candidates are equally plausible, pick the one
   with stronger contextual fit and downgrade confidence to "medium" or
   "low".

4. UNMATCHED NAMED PERSONS. If the document names a person who is
   clearly NOT in the shortlist (whether by name absence, by date-window
   exclusion, or by lifespan mismatch), record their Latin/French name
   in `unmatched_named_persons` in the closing summary. This is the
   CORRECT and SAFE response -- do not avoid it.

   Two important clarifications:
   (a) CLERICS WITH PEERAGE STATUS. The shortlist includes ecclesiastical
       princes (bishops, archbishops, cardinals, abbots) who are also
       members of European royal/noble dynasties -- e.g., Henri de
       France (archbishop of Reims, son of Louis VI), Heinrich von
       Bayern (bishop), and prince-bishops of the HRE. If a candidate
       on the shortlist matches a named cleric in the doc by name AND
       lifespan, emit the match normally. Only flag a cleric as
       unmatched if no suitable candidate exists on the shortlist.
   (b) EXCLUSIONS. Do NOT flag in unmatched_named_persons: saints
       ("Petrus apostolus", "Sancti Pauli"), biblical figures, or popes
       being referred to AS popes (the pope writing the letter, or
       prior popes invoked by their papal name). These are not peerage
       references in the relevant sense.

   This flag exists to surface cases where the shortlist scope was too
   tight; recording many entries here is expected and useful.

5. FINAL SUMMARY LINE. After all match records (zero or more), emit one
   summary JSONL line with `_summary: true`.

# FALSE-POSITIVE PATTERNS TO AVOID

The upstream regex matcher had 38% precision. Common failure modes —
DO NOT replicate:

(a) BIBLICAL / SAINT FORMULAE. Standard papal address forms ("servus
    servorum Dei", "fideles in Christo dilecti", "Petrus apostolus",
    "Iohannes evangelista") are NOT references to contemporary persons.

(b) POPES AS POPES. "Honorius", "Innocentius", "Gregorius", "Bonifatius",
    "Clemens" used to refer to a sitting or recent pope are NOT
    references to a peerage noble of the same name. The doc's `pope`
    field tells you who is writing.

(c) PLACE NAMES WITH SAINT PREFIX. "Sancti Dyonisii" = Saint-Denis;
    "Sancti Petri" = St Peter's; "Sancti Pauli" = St Paul's. Always a
    place, never a person.

(d) LATIN VERB / ADJECTIVE FORMS. "constanter" is not Constantine.
    "henricianus", "ludovicianus" are adjectival, not personal-name
    references. Verb conjugations sharing roots with names are common.

(e) FORMAL ADDRESS PHRASES. "dilecti filii", "fratres carissimi",
    "fideles nostri" — these are templated salutations, not person
    references.

(f) DATE MISMATCH. The shortlist already enforces a ±15 year window. Do
    a final sanity check: if the doc clearly refers to events in a
    specific year, the matched person should plausibly be alive (or
    recently deceased, for inheritance/excommunication cases).

(g) SAME NAME, DIFFERENT PERSON. A major false-positive class. When
    multiple candidates share a first name (e.g., many "Henricus",
    "Ludovicus", "Conradus"), use TITLE + REGION + DATE to disambiguate.
    If one candidate is clearly the best fit on multiple converging
    signals (title + region + date all align), emit at "medium" or
    "low" confidence with reasoning. If NO candidate disambiguates
    cleanly, emit NOTHING for that reference and record the name in
    `unmatched_named_persons` instead. Do not guess.

(h) WRONG-CANDIDATE SUBSTITUTION. When the doc clearly references a
    specific person (by name, patronymic, deposed-king status, or
    explicit relationship like "filium"), the shortlist sometimes does
    not contain that exact person -- often because their death date is
    outside the doc's +/-15 year window, or because they belong to a
    dynasty not in the closed universe. You must NOT substitute a
    candidate who merely shares a title or name fragment.

    Example failure mode: the Latin reads "Friderici olim Romani
    imperatoris filium" (= the son of Frederick II), Frederick II is
    not on the shortlist. WRONG: match to Alexander III, King of
    Scotland because he is also a king. RIGHT: record "Friderici olim
    Romani imperatoris" in unmatched_named_persons; emit no match for
    that reference.

    The same rule applies when the name partially matches but the dates
    do not: if the doc references "Balduinus Ierosolimitanus rex"
    (Baldwin I of Jerusalem, reigned 1100-1118) and the only Baldwin on
    your shortlist has dates 1126-1135, that is a DIFFERENT person.
    Record as unmatched_named_persons. Do not use the lifespan-
    mismatched candidate as a placeholder.

# OUTPUT SCHEMA

For each matched person (one JSONL line). Use the `doc_id` value shown
in `# THE DOCUMENT` section below for every record you emit:

  {{
    "doc_id":            "<doc_id from THE DOCUMENT section>",
    "person_id":         "<from shortlist>",
    "quoted_latin":      "<exact Latin substring from transcription>",
    "quoted_french":     "<French equivalent from analyse, or empty>",
    "role":              "<one of: beneficiary | requestor | subject_or_mention | addressee>",
    "confidence":        "<high | medium | low>",
    "reasoning":         "<1-2 sentences explaining the match decision>",
    "inferred_subjects": ["<zero or more of: marriage, excommunication, inheritance, dispute, crusade, clerical_discipline, ecclesiastical_property>"]
  }}

After all match records, ONE closing summary line:

  {{
    "doc_id":                   "<doc_id from THE DOCUMENT section>",
    "_summary":                 true,
    "n_matches":                <integer>,
    "unmatched_named_persons":  ["<latin or french name>", ...],
    "notes":                    "<optional: anything notable about this doc>"
  }}

If the doc has no peerage references at all (saint cult, parish dispute,
purely clerical matter), emit ONLY the summary line with n_matches=0
and a notes string explaining why.

# WORKED EXAMPLE

Suppose the analyse is:
  "Le pape Innocent IV demande au comte Hugo IV de Bourgogne d'aider
  l'archevêque Robert de Lyon contre l'évêque de Mâcon."

And the Latin includes:
  "...dilecto filio nobili viro Hugoni duci Burgundiae...assistat
  venerabili fratri Roberto Lugdunensi archiepiscopo..."

And the shortlist includes:
  p10118.htm#i101175|Hugues IV de Bourgogne, Duc de Bourgogne|M|1212-1271|Norman_Ducal

The correct output is:

  {{"doc_id": "EX", "person_id": "p10118.htm#i101175", "quoted_latin": "Hugoni duci Burgundiae", "quoted_french": "Hugo IV de Bourgogne", "role": "addressee", "confidence": "high", "reasoning": "Doc addresses Hugo Duke of Burgundy directly; title (duci Burgundiae) and name match candidate 1212-1271.", "inferred_subjects": ["dispute"]}}
  {{"doc_id": "EX", "_summary": true, "n_matches": 1, "unmatched_named_persons": ["Roberto Lugdunensi archiepiscopo"], "notes": "Robert of Lyon is an archbishop (clerical), so flagged as unmatched only out of caution; standard exclusion."}}

Note: the archbishop "Roberto Lugdunensi" is recorded as unmatched
because no Robert candidate on this doc's shortlist matches both name
and lifespan for Lyon in this period. If a peerage Robert had been on
the shortlist with appropriate dates, the correct action would be to
match him -- peerage clerics (archbishops, cardinals, prince-bishops)
appear on the shortlist when they are members of royal/noble dynasties,
and should be matched normally.

# COUNTER-EXAMPLE (THIS IS THE WRONG BEHAVIOR -- DO NOT DO THIS)

Suppose the Latin reads:
  "contra Manfredum, Friderici olim Romani imperatoris filium"

And the shortlist does NOT contain Frederick II von Hohenstaufen
(because his death date 1250 is outside the doc's +/-15 year window).
The shortlist DOES contain, among others, a different king named
Alexander III of Scotland (1241-1285).

WRONG response (violates Rule 1(b) -- substitutes a different person):

  {{"doc_id": "EX2", "person_id": "p10223.htm#i102227", "quoted_latin": "Friderici olim Romani imperatoris", "role": "subject_or_mention", "confidence": "medium", "reasoning": "Frederick II is outside the window; matching to another king on the shortlist."}}

This is incorrect: Alexander III of Scotland is a different individual
from Frederick II. You cannot use a candidate as a placeholder for
someone they are not.

RIGHT response (no match record emitted for the Frederick reference;
recorded as unmatched instead):

  {{"doc_id": "EX2", "_summary": true, "n_matches": <count of OTHER valid matches>, "unmatched_named_persons": ["Friderici olim Romani imperatoris"], "notes": "Frederick II named as Manfred's father but outside +/-15 year window so not on shortlist; recorded as unmatched."}}

# WORK CAREFULLY

Take your time. Scan the analyse for explicit names first; they are
high-quality signals. Then scan the transcription for Latin name forms.

Before emitting each match, perform a final identity-verification step:

  1. Restate to yourself: who does this quoted_latin actually name?
  2. Does the candidate I am about to emit have BOTH a name (in any
     language) AND a lifespan that match that specific historical
     person?
  3. If no candidate fits BOTH checks, do NOT emit a match. Record the
     reference in `unmatched_named_persons` instead.

When in doubt, emit nothing. Empty match lists are always acceptable.
A doc with zero matches and 5 unmatched_named_persons entries is a
GOOD output -- it tells us the shortlist was incomplete, not that
you failed.

Prefer fewer high-confidence matches over many low-confidence ones.

# THE DOCUMENT

doc_id:        {DOC_ID}
year:          {YEAR}{YEAR_IMPUTED_NOTE}
pope:          {POPE}
region:        {REGION}
genre:         {GENRE}

## Analyse (French summary)
{ANALYSE}

## Transcription (Latin, first {TRANSCRIPTION_LEN} chars{TRUNCATION_NOTICE})
{TRANSCRIPTION}

# CANDIDATE SHORTLIST ({N_CANDIDATES} persons)

Format: {FORMAT_LINE}

{CANDIDATE_TABLE}

# WRITE YOUR OUTPUT TO

{OUTPUT_PATH}

Use the Write tool to create that file. Each line must be a valid JSON
object. Emit match records first (zero or more), then exactly one
summary line.

In your response, return ONLY a one-line confirmation in this exact
format:

  doc {DOC_ID}: wrote N matches, M unmatched_named_persons

(where N and M are integers)
"""


def render_candidate_table(candidates: list[dict], compress: bool = False) -> str:
    """Pipe-delimited candidate table, one row per candidate.

    compress=True drops spaces around the `|` separators (~15% shortlist
    token reduction; no information loss).
    """
    sep = "|" if compress else " | "
    return "\n".join(
        f"{c['id']}{sep}{c['name']}{sep}{c['sex']}{sep}"
        f"{c['b']}-{c['d']}{sep}{c['dyn']}"
        for c in candidates
    )


def build_subagent_prompt(doc_payload: dict, output_path: str,
                          *, v3: bool = False) -> str:
    """Render the full prompt for processing one doc.

    v3=True applies the +Royal shortlist filter AND the compressed
    candidate row format AND emits the strengthened template. The shared
    preamble is byte-identical across docs, enabling prompt caching.
    """
    p = doc_payload
    candidates = p.get("candidates", [])

    if v3:
        doc_text_for_filter = ((p.get("analyse") or "") + " "
                                + (p.get("transcription") or ""))
        candidates = filter_shortlist(
            candidates, doc_text_for_filter,
            prefix_len=4, include_royal=True, include_ducal=False,
        )

    compress = v3
    format_line = ("person_id|name|sex|birth-death|dynasty" if compress
                   else "person_id | name | sex | birth-death | dynasty")

    transcription = p.get("transcription", "")
    truncation_notice = " — TRUNCATED" if p.get("transcription_truncated") else ""
    year_imputed_note = "  (imputed)" if p.get("year_imputed") else ""
    region = p.get("region") or "(not set)"
    genre = p.get("genre") or "(not set)"
    pope = p.get("pope") or "(not set)"
    analyse = p.get("analyse") or "(no analyse field)"

    return PROMPT_TEMPLATE.format(
        DOC_ID=p["doc_id"],
        YEAR=p["year"],
        YEAR_IMPUTED_NOTE=year_imputed_note,
        POPE=pope,
        REGION=region,
        GENRE=genre,
        ANALYSE=analyse,
        TRANSCRIPTION=transcription if transcription else "(empty)",
        TRANSCRIPTION_LEN=len(transcription),
        TRUNCATION_NOTICE=truncation_notice,
        N_CANDIDATES=len(candidates),
        FORMAT_LINE=format_line,
        CANDIDATE_TABLE=render_candidate_table(candidates, compress=compress),
        OUTPUT_PATH=output_path,
    )


# Smoke test when run directly
if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parent.parent
    DOCS = ROOT / "output" / "batches_reextract" / "docs"
    VERDICTS = ROOT / "output" / "batches_reextract" / "verdicts"
    sample = next(DOCS.glob("doc_*.json"))
    with open(sample, encoding="utf-8") as f:
        payload = json.load(f)
    out_path = str(VERDICTS / f"verdicts_{payload['doc_id']}.jsonl")
    prompt = build_subagent_prompt(payload, out_path, v3=True)
    print(f"=== Prompt for {sample.name} (v3) ===")
    print(f"  total chars: {len(prompt):,}")
    print(f"  approx tokens (chars/4): {len(prompt) // 4:,}")
    print(f"  n_candidates (post-filter): "
          f"{sum(1 for l in prompt.split('CANDIDATE SHORTLIST', 1)[1].splitlines() if l.startswith('p'))}")
    print()
    print("=== FIRST 2000 chars ===")
    print(prompt[:2000])
    print()
    print("=== LAST 1500 chars ===")
    print(prompt[-1500:])
