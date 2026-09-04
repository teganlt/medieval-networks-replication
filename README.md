# Replication package — "The Reign of the Saints: Medieval Aristocratic Networks and the Origins of Western Law"

Tegan L. Truitt (Grove City College, truitttl@gcc.edu). The paper (working draft, tex + PDF)
is in [`paper/`](paper/); every table and figure in it is produced by this
pipeline.

The pipeline goes from the raw genealogy scrape and the raw APOSCRIPTA dump to
every number, figure, and table in the draft. `MANIFEST.md` maps each paper
item to the script and output file that produce it.

## Quick start

```
pip install -r requirements.txt
Rscript r_requirements.R
# place data/raw/aposcripta.dataset.json (see Data availability below)
python run_all.py
python verify_against_draft.py     # optional: diff regenerated tables vs paper/draft_8_29_26.tex
```

`python run_all.py --list` prints the full stage plan. The pipeline is
restartable: `--from <stage>` resumes, `--only <stage>` runs one stage.
Per-stage console logs land in `output/logs/`.

## Data availability

**The Peerage.** The genealogy is a scrape (August 2024) of Darryl Lundy's
*The Peerage* (https://www.thepeerage.com), shipped compressed as
`data/raw/thePeerage.csv.gz` (727,753 person records: id, name, sex,
birth/death years where recorded, and parent/spouse/child links; stage 0
decompresses it automatically). The data is © Darryl Lundy and is
**redistributed with the compiler's kind permission** (personal
communication, September 2026) for replication purposes — see
[DATA_NOTICE.md](DATA_NOTICE.md). *The Peerage* is continuously updated and
has grown well past this frozen vintage; the paper's numbers are tied to the
August 2024 scrape (row count checked by stage 0), and anyone wanting current
data should use thepeerage.com itself.

**APOSCRIPTA.** The papal-letter corpus is the APOSCRIPTA database — *Lettres
des papes* (dir. Julien Théry, CIHAM/UMR 5648, éd. électronique TELMA, IRHT),
licensed **CC-BY 4.0**: collection page
https://telma-chartes.irht.cnrs.fr/aposcripta.php; archived deposit
https://doi.org/10.5281/zenodo.6771270.

The full corpus is **not shipped** with this package. Download the corpus
export (JSON) from the TELMA platform and save it as
`data/raw/aposcripta.dataset.json`. The vintage used here (retrieved
2024-08-10) contains 25,289 `datasetItems`; stage 0 verifies the count.
APOSCRIPTA is a living corpus — a later export will contain more letters and
will not reproduce the paper's numbers exactly. If the platform's export
format has changed, contact the author for the exact retrieval procedure.
Short excerpts of APOSCRIPTA letter text do appear inside the frozen research
artifacts (quoted Latin phrases in the extraction verdicts; editorial
*analyses* and truncated transcriptions for the ~350 letters in the audit and
validation files) — these are redistributed under the corpus's CC-BY 4.0
license with attribution, transcriptions truncated by the author; see
DATA_NOTICE.md.

## Environment

- **Python 3.12** with the pinned packages in `requirements.txt`
  (pandas, numpy, matplotlib, python-igraph, scipy, leidenalg).
- **R 4.5.2** with data.table, fixest, fwildclusterboot, ivreg
  (`r_requirements.R` installs and prints versions).
- `Rscript` must be on PATH, or set the `RSCRIPT` environment variable
  (e.g. `RSCRIPT="C:/Program Files/R/R-4.5.2/bin/Rscript.exe"`).
- Disk: ~15 GB free (stage 4.1 writes ~2.7 GB of per-document payloads;
  intermediate tables add several more).
- OS: developed and tested on Windows 11; the code is pure Python/R and
  should run elsewhere, but only Windows has been tested.

## The generative-AI stages and the frozen artifacts

Two pipeline stages called a large language model (Claude Sonnet 4.6) over
the Anthropic API:

1. **Person–letter extraction** (prompts rendered by
   `scripts/09_doc_match_render_prompts.py` from `scripts/doc_match_prompt.py`;
   submitted by `scripts/10_doc_match_batch_submit.py`). Run at default
   temperature — **not reproducible bit-for-bit**. The complete raw verdicts
   ship frozen in `data/frozen/verdicts_sonnet-4-6.zip` (24,130 JSONL files),
   and stage 4 rebuilds every downstream table deterministically from them.
2. **Subject coding** (`scripts/12_recode_subjects.py`, temperature 0). The
   coded table ships frozen as `data/frozen/matched_docs_coded.csv`, with the
   independent second coding (`agent_coded_overlap.csv`) used for the
   inter-coder agreement table.

`run_all.py` therefore **never calls an API**: stage 0 seeds the frozen
artifacts into `output/` and the pipeline consumes them. The prompt texts are
reproduced verbatim in the paper's appendix. A replicator who wants to re-run
the AI stages needs an Anthropic API key and should expect verdicts that
differ slightly from the frozen ones (and roughly $330 in API charges for the
extraction pass at 2026 prices).

The two marriage-bloc partitions (`data/frozen/patriline_bloc_assignment.csv`
and its pre-1300 counterpart) are also frozen: Louvain community detection is
stochastic across runs and library versions, so the paper's partitions are the
package default. `python run_all.py --rerun-louvain` regenerates both from
scratch (stages 5.2 and 5.11); the paper's robustness appendix shows the
results are not partition-dependent, and a regenerated pre-1300 partition
gives a somewhat larger coefficient (see MANIFEST DISCREPANCIES note 5).

Human-audit inputs (the match-audit verdicts coded by the author and a blind
research assistant, and the hand heiress rulings) ship under `validation/`.
Stage 10 recomputes every audit statistic in the draft from them; stages
10.1–10.2 also regenerate the audit *sample frames* into `validation/*_regen/`
so the sampling design can be checked against the frozen items.

## Approximate runtimes

Measured on a Windows 11 laptop with the data on local disk (clean-room run,
2026-09-03; per-stage wall times in `run_log_reference.txt`): the full
pipeline is roughly **75–90 minutes**. The slow stages are the verdict
aggregation over 24,130 JSONL files (4.2, ~32 min), the payload build (4.1,
~6 min), the conflict-prone flag build (7.1b, ~8 min), and the
bootstrap/Poisson stages (7.5, 7.15, 7.17, ~2–4 min each); everything else runs
in seconds. Running from a cloud-synced folder (OneDrive/Dropbox) can multiply
the stage-4 file-heavy times severalfold.

## Package layout

```
run_all.py                  orchestrator (stage plan: python run_all.py --list)
verify_against_draft.py     numeric diff of regenerated tables vs the draft tex
MANIFEST.md                 paper item -> script -> output map + provenance
LICENSE / DATA_NOTICE.md    MIT for code; separate terms for the data
CITATION.cff                how to cite
requirements.txt            pinned Python dependencies
r_requirements.R            R dependency installer
paper/                      the working draft (tex, PDF, figures, references)
data/raw/                   thePeerage.csv.gz (+ aposcripta.dataset.json, user-supplied)
data/frozen/                frozen AI artifacts (see above)
scripts/                    all pipeline scripts (names keep their project ids)
validation/                 human-audit items/verdicts + hand rulings
output/, figs/, tables/     generated (empty until run)
```

Script filenames keep their project-internal numbering (00–159, v90–v96,
fig_*); `run_all.py` is the execution order. Nothing in `scripts/` is
superfluous: every script produces (or feeds a script that produces) a
number, figure, or table in the draft — see MANIFEST.md, including its list
of what was deliberately excluded.

## Verification

After a full run, `python verify_against_draft.py` compares the numeric rows
of every regenerated table against the corresponding hardcoded block in
`../draft_8_29_26.tex` (caption wording is ignored). Known discrepancies
between the draft text and the reproduction are listed at the bottom of
MANIFEST.md.

## AI-use statement

See the draft's "Statement on generative AI use". In addition to the two data
stages above, much of the regression/figure code was drafted with LLM
assistance and audited by the author; this package itself was assembled with
LLM assistance and verified against the draft as described in MANIFEST.md.

## License

Code and documentation: MIT (see LICENSE). Data: separate terms — The Peerage
data is © Darryl Lundy, redistributed with permission for replication;
APOSCRIPTA is not redistributed. See DATA_NOTICE.md.
