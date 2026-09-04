# Data notice

The MIT license in LICENSE covers the code and documentation in this
repository. The data files carry their own terms:

## The Peerage (data/raw/thePeerage.csv.gz)

The genealogical data is a scrape (August 2024) of Darryl Lundy's
*The Peerage* (https://www.thepeerage.com), © Darryl Lundy, Wellington,
New Zealand. It is redistributed here **with the compiler's permission**
(personal communication, September 2026) for the purpose of replicating the
paper this repository accompanies. It is NOT relicensed: this repository's
MIT license does not apply to it, and it should not be extracted for uses
beyond replication and directly related research without consulting the
compiler. For current data — the site has grown well past this frozen 2024
vintage — use thepeerage.com itself. Note that, exactly as published on
thepeerage.com, roughly 17% of rows describe presumptively living
individuals; the replication-only reuse restriction above is partly motivated
by this.

Citation: Lundy, Darryl. *The Peerage: a genealogical survey of the peerage
of Britain as well as the royal families of Europe*, thepeerage.com
(scraped August 2024).

## APOSCRIPTA (full corpus not included; excerpts CC-BY 4.0)

The papal-letter corpus is the APOSCRIPTA database — *Lettres des papes*
(dir. Julien Théry, CIHAM/UMR 5648, éd. électronique TELMA, IRHT), licensed
**Creative Commons Attribution 4.0 International (CC-BY 4.0)** — see the
archived deposit "APOSCRIPTA database. Unified Corpus of Papal Letters",
https://doi.org/10.5281/zenodo.6771270. The full corpus is not shipped here
(see README "Data availability" for how to obtain it), but excerpts of letter
text are redistributed inside the frozen research artifacts under that
license: quoted Latin phrases across the extraction verdicts
(data/frozen/verdicts_sonnet-4-6.zip), and editorial *analyses*, *regestes*,
and transcriptions truncated at 2,000 characters for roughly 350 letters in
the audit and validation files (validation/, data/frozen/reextract_*).
Modifications: excerpting and truncation by the author. Citation: Théry,
Julien (dir.), *APOSCRIPTA database — Lettres des papes*, TELMA (IRHT),
2017–, https://telma-chartes.irht.cnrs.fr/aposcripta.php.

## Frozen model outputs (data/frozen/)

The extraction verdicts and subject codings are outputs of Anthropic Claude
models run by the author over the two corpora above (see README, "The
generative-AI stages"). They are provided as research artifacts of the paper.
