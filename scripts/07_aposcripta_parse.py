"""
07_aposcripta_parse.py
=======================

Stage 7 of the replication pipeline.

Parse APOSCRIPTA's 25,289 papal documents into a per-document table with
year, pope, region, genre, mandement flag, publication status, and
subject classification flags.

Behaviour:
  - Subject classification searches `analyse + regeste + transcription`
    (the transcription is the actual Latin text and has 99.1% coverage;
    adding it more than doubles the subject-hit rate vs analyse+regeste
    alone).
  - Region classification uses 8 buckets (Crusader_States, Iberia,
    Eastern_Europe, Scandinavia, Italy, HRE, England, France).
    Most-specific buckets checked first; first match wins.
  - Undated docs (~9% of total) get a year via pope-reign midpoint,
    parsed from the `pape` field. Marked with year_imputed=1.
  - Items dated < 50 CE (19 obvious editorial errors) are filtered.
  - itemStatus exposed as is_published flag (not filtered).
  - Broader mandement detection (is_canapis) flags both the strict
    `Mandement (littere cum filo canapis)` genre AND the related
    `Lettre, general (apres 1198, littere cum filo canapis)` genre,
    which share the same parchment type.
  - Source text is HTML-unescaped and stripped of simple XML tags
    before regex matching.

Inputs:
  ../data/aposcripta.dataset.json

Output (in output/):
  aposcripta_per_doc.csv  one row per filtered doc:
    id, year, year_imputed, pape, genre, is_mandement, is_canapis,
    is_published, region, has_analyse_text,
    is_marriage, is_excommunication, is_inheritance, is_dispute,
    is_crusade, is_clerical_discipline, is_ecclesiastical_property
"""

from __future__ import annotations
import csv
import html
import json
import re
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APO_JSON = ROOT / "data" / "raw" / "aposcripta.dataset.json"
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

MANDEMENT_GENRE_STRICT = "Mandement (littere cum filo canapis)"
CANAPIS_PATTERN = re.compile(r"littere cum filo canapis", re.IGNORECASE)
YEAR_FILTER_MIN = 50  # drop items dated 0-49 CE (editorial errors)


REGION_KEYWORDS = {
    "Crusader_States": [
        r"\bAntioch", r"\bAntiochia", r"\b[ÉE]desse\b", r"\bEdessa\b",
        r"\bTripoli\b", r"\bAcre\b", r"\bSaint[-\s]Jean[-\s]d[''’]Acre\b",
        r"\bTyr\b", r"\bTyre\b", r"\bBeyrouth\b", r"\bBeirut\b",
        r"\bC[eé]sar[eé]e\b", r"\bCaesarea\b", r"\bJ[eé]rusalem\b",
        r"\bJerusalem\b", r"\bIherusalem\b", r"\bterra\s+sancta\b",
        r"\bTerre\s+Sainte\b", r"\bOutremer\b",
    ],
    "Iberia": [
        r"\bCastille\b", r"\bCastilla\b", r"\bCastel{1,2}an\w*",
        r"\bL[eé]on\b", r"\bAragon\b", r"\bPortugal\b",
        r"\bEspagne\b", r"\bHispan", r"\bCompostela\b", r"\bCompostelle\b",
        r"\bTol[eè]de\b", r"\bToledo\b", r"\bToletan",
        r"\bSarago[sz]a\b", r"\bSaragosse\b", r"\bS[eé]ville\b",
        r"\bSeville\b", r"\bValenc[ei]a\b", r"\bCoimbra\b", r"\bBraga\b",
        r"\b[ÉE]vora\b", r"\bTarragona\b", r"\bTarragonan",
        r"\bNavarre\b", r"\bP[aá]mplona\b", r"\bSahag[uú]n\b",
        r"\broi.{0,5}Castille\b", r"\broi.{0,5}Aragon\b",
    ],
    "Eastern_Europe": [
        r"\bPologne\b", r"\bPolonia\b", r"\bPoland\b", r"\bCracovie\b",
        r"\bCracovia\b", r"\bGniezno\b", r"\bGnesen\b",
        r"\bWroc[lł]aw\b", r"\bBreslau\b",
        r"\bHongrie\b", r"\bHungaria\b", r"\bHungar",
        r"\bEsztergom\b", r"\bOstrihom\b", r"\bBuda\b",
        r"\bBoh[eê]m", r"\bBohemia\b", r"\bPrague\b", r"\bPraga\b",
        r"\bOlomouc\b", r"\bOlm[uü]tz\b",
        r"\bLituanie\b", r"\bLithuania\b", r"\bRussie\b", r"\bRussia\b",
        r"\bKiev\b", r"\bKyiv\b", r"\bRussorum\b", r"\bRuthen",
        r"\bBulgar",
        r"\bConstantinople\b", r"\bConstantinopolitan", r"\bByzantin",
    ],
    "Scandinavia": [
        r"\bSu[eè]de\b", r"\bSuecia\b", r"\bSweden\b",
        r"\bNorv[eè]ge\b", r"\bNorvegia\b", r"\bNorway\b",
        r"\bDanemark\b", r"\bDania\b", r"\bDenmark\b",
        r"\bIslande\b", r"\bIslandia\b", r"\bIceland\b",
        r"\bLund\b", r"\bNidaros\b", r"\bTrondheim\b", r"\bSkara\b",
        r"\bUppsala\b", r"\bUpsal\b", r"\bRoskilde\b", r"\bOdense\b",
        r"\bBergen\b", r"\bStavanger\b", r"\bdacien",
    ],
    "Italy": [
        r"\bItalie\b", r"\bItalia\b", r"\bRomain\b", r"\broi\s+de\s+Sicile\b",
        r"\bSicile\b", r"\bSicilia\b", r"\bNaples\b", r"\bMont\s+Cassin\b",
        r"\bMonte\s+Cassino\b", r"\bB[eé]n[eé]vent\b", r"\bBenevento\b",
        r"\bRavenne\b", r"\bMilan\b", r"\bMilanais\b", r"\bG[eê]nes\b",
        r"\bVenise\b", r"\bFlorence\b", r"\bPise\b", r"\bToscane\b",
        r"\bTuscia\b", r"\bLombardie\b", r"\bSalerne\b", r"\bApulie\b",
        r"\bFerrare\b",
    ],
    "HRE": [
        r"\bEmpire\b", r"\bempereur\b", r"\bImperii\b", r"\bAllemagne\b",
        r"\bGermanie\b", r"\bHildesheim\b", r"\bHalberstadt\b",
        r"\bGoslar\b", r"\bCologne\b", r"\bMayence\b", r"\bTrier\b",
        r"\bTr[eè]ves\b", r"\bW[uü]rzburg\b", r"\bRegensburg\b",
        r"\bRatisbonne\b", r"\bMagdeburg\b", r"\bMerseburg\b",
        r"\bRatzeburg\b", r"\bHambourg\b", r"\bBr[eê]me\b", r"\bBamberg\b",
        r"\bMetz\b", r"\bToul\b", r"\bVerdun\b", r"\bPassau\b",
        r"\bFreising\b", r"\bAugsburg\b", r"\bStrasbourg\b", r"\bConstance\b",
        r"\bBrandenburg\b", r"\bMeissen\b", r"\bSachsen\b", r"\bSaxonie\b",
        r"\bSouabe\b", r"\bBavi[eè]re\b", r"\bBayern\b", r"\bFranconie\b",
        r"\bThuringe\b", r"\bAutriche\b", r"\b[OÖ]sterreich\b",
        r"\broi\s+des\s+Romains\b", r"\bSaint[-\s]Empire\b",
    ],
    "England": [
        r"\bAngleterre\b", r"\bAnglie\b", r"\broi\s+d[''’]Angleterre\b",
        r"\bCanterbury\b", r"\bCantuarien\b", r"\bDurham\b",
        r"\bWinchester\b", r"\bLincoln\b", r"\bWorcester\b",
        r"\bGloucester\b", r"\bSalisbury\b", r"\bWells\b", r"\bNorwich\b",
        r"\bEly\b", r"\bRochester\b", r"\bWessex\b", r"\bMercia\b",
        r"\bGwynedd\b", r"\b[ÉEé]cosse\b", r"\bScotia\b",
    ],
    "France": [
        r"\bFrance\b", r"\bfran[çc]ais", r"\broyaume.{0,5}France",
        r"\bParis", r"\bSens\b", r"\bReims\b", r"\bRouen\b",
        r"\bBordeaux\b", r"\bToulouse\b", r"\bLyon", r"\bNarbonne\b",
        r"\bN[iî]mes\b", r"\bOrl[eé]ans\b", r"\bChartres\b",
        r"\bSoissons\b", r"\bLaon\b", r"\bTroyes\b", r"\bAuxerre\b",
        r"\bMeaux\b", r"\bNevers\b", r"\bBourges\b", r"\bPoitiers\b",
        r"\bAngers\b", r"\bTours\b", r"\bLe\s+Mans\b", r"\bBayeux\b",
        r"\bNormandie\b", r"\bAnjou\b", r"\bAquitaine\b", r"\bBourgogne\b",
        r"\bChampagne\b", r"\bProvence\b", r"\bPoitou\b", r"\bBretagne\b",
        r"\bBlois\b", r"\bFlandre\b", r"\bArtois\b", r"\bVermandois\b",
        r"\bValois\b", r"\bBoulogne\b", r"\bFoix\b", r"\bBerry\b",
        r"\bAuvergne\b", r"\bNoyon\b", r"\bCambrai\b", r"\bSaint[-\s]Denis\b",
        r"\bSenlis\b", r"\bSaint[-\s]Hilaire\b", r"\bAlbigeois\b",
        r"\bcomte\s+de\s+Toulouse\b", r"\bRoi\s+de\s+France\b",
        r"\broi\s+des\s+Francs\b", r"\bPicardie\b", r"\bClermont\b",
        r"\bAutun\b", r"\bAmiens\b", r"\bBeauvais\b", r"\bArras\b",
    ],
}
REGION_RE = {r: re.compile("|".join(p), re.IGNORECASE)
             for r, p in REGION_KEYWORDS.items()}
REGION_PRIORITY = ["Crusader_States", "Iberia", "Eastern_Europe",
                   "Scandinavia", "Italy", "HRE", "England", "France"]


SUBJECT_PATTERNS = {
    "marriage": [
        r"\bmatrimoni", r"\bconsanguin", r"\baffinitat",
        r"\bincest", r"\bdivort", r"\bannulla", r"\bnupti",
        r"\bconjug", r"\bconiug", r"\bmariage\b",
        r"\bdispensatio[a-z\s]{0,30}matrimon",
        r"\bgrad[uo][a-z\s]{0,15}consanguin",
        r"\bimpediment[a-z\s]{0,30}matrimon",
        r"\buxor[ie]", r"\bsponsalia",
        r"\bcanonical[a-z\s]{0,30}matrimon",
    ],
    "excommunication": [
        r"\bexcommunicat", r"\bexcomunic", r"\banathemat",
        r"\binterdict", r"\babsolutio[a-z\s]{0,15}excommunic",
        r"\bexcommunication", r"\binterdit",
    ],
    "inheritance": [
        r"\bhered[ie]", r"\bsuccessio", r"\bfeud[oai]",
        r"\bpatrimoni", r"\bdominium", r"\bbonorum",
        r"\bsuccession", r"\bh[eé]ritage",
    ],
    "dispute": [
        r"\bcontroversi", r"\blis\s+inter", r"\bdiscordi",
        r"\barbitri", r"\bcompositio", r"\bquerel", r"\blitig",
        r"\bdissensio", r"\bdiff[eé]rend\b",
        r"\bsentent[a-z\s]{0,15}inter",
    ],
    "crusade": [
        r"\bcrucesignat", r"\bterra sancta", r"\bjerusalem",
        r"\biherusalem", r"\bsaracen", r"\bcrois[aé]",
        r"\bcrux\b", r"\bsancta cruce",
    ],
    "clerical_discipline": [
        r"\bsimoni", r"\bconcubin", r"\binvestit", r"\bnicolaitan",
        r"\bcaelibat", r"\bcoelibat",
    ],
    "ecclesiastical_property": [
        r"\bbenefici[oai]", r"\bpr[eæ]bend", r"\bdecim[aæ]",
        r"\boblation", r"\bredditus eccles",
        r"\bproprietat[a-z\s]{0,20}ecclesi",
    ],
}
SUBJECT_RE = {s: re.compile("|".join(p), re.IGNORECASE)
              for s, p in SUBJECT_PATTERNS.items()}


def _norm_text(v):
    if v is None:
        return ""
    if isinstance(v, list):
        s = " ".join(str(x) for x in v if x is not None)
    else:
        s = str(v)
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    return s


def _norm_year(dg):
    if isinstance(dg, list):
        for d in dg:
            if isinstance(d, dict):
                y = d.get("date_deb_annee")
                if y:
                    try:
                        return int(y)
                    except (TypeError, ValueError):
                        continue
        return None
    if isinstance(dg, dict):
        y = dg.get("date_deb_annee")
        if y:
            try:
                return int(y)
            except (TypeError, ValueError):
                return None
    return None


def _pope_midpoint(pape):
    """Parse '(YYYY-YYYY)' or '(YYYY)' from a pope name string."""
    if not pape:
        return None
    s = str(pape)
    m = re.search(r"\((\d{4})\s*[-–]\s*(\d{4})\)", s)
    if m:
        return (int(m.group(1)) + int(m.group(2))) // 2
    m = re.search(r"\((\d{4})\)", s)
    if m:
        return int(m.group(1))
    return None


def _classify_region(text):
    if not text:
        return ""
    for r in REGION_PRIORITY:
        if REGION_RE[r].search(text):
            return r
    return ""


def main():
    print(f"Loading APOSCRIPTA from {APO_JSON} ...", flush=True)
    t0 = time.time()
    with open(APO_JSON, encoding="utf-8") as f:
        data = json.load(f)
    items = data["datasetItems"]
    print(f"  raw items: {len(items):,}  ({time.time()-t0:.1f}s)",
          flush=True)

    rows = []
    n_year_dg = n_year_pope = n_year_none = 0
    n_filt_old = 0
    for it in items:
        y = _norm_year(it.get("dateGroup"))
        y_imp = 0
        if y is None:
            y = _pope_midpoint(it.get("pape"))
            if y is None:
                n_year_none += 1
                continue
            y_imp = 1
            n_year_pope += 1
        else:
            n_year_dg += 1
        if y < YEAR_FILTER_MIN:
            n_filt_old += 1
            continue

        genre = it.get("genre")
        if isinstance(genre, list):
            genre = " / ".join(str(x) for x in genre)
        else:
            genre = genre or ""
        is_mand = int(genre == MANDEMENT_GENRE_STRICT)
        is_canapis = int(bool(CANAPIS_PATTERN.search(genre)))
        is_published = int(it.get("itemStatus") == "published")
        pape = (it.get("pape") or "").strip()

        dest = _norm_text(it.get("destinataire"))
        analyse = _norm_text(it.get("analyse"))
        regeste = _norm_text(it.get("regeste"))
        transcription = _norm_text(it.get("transcription"))

        text_for_region = dest if dest.strip() else analyse
        region = _classify_region(text_for_region)

        text_for_subjects = (analyse + " " + regeste + " "
                             + transcription).strip()
        has_text = int(bool(text_for_subjects))
        flags = {}
        for s, pattern in SUBJECT_RE.items():
            flags[f"is_{s}"] = (int(bool(pattern.search(text_for_subjects)))
                                if text_for_subjects else 0)

        rows.append({
            "id": it.get("itemIdTELMA"),
            "year": y,
            "year_imputed": y_imp,
            "pape": pape,
            "genre": genre,
            "is_mandement": is_mand,
            "is_canapis": is_canapis,
            "is_published": is_published,
            "region": region,
            "has_analyse_text": has_text,
            **flags,
        })

    print(f"\nYear source breakdown:")
    print(f"  from dateGroup:                {n_year_dg:>6,}")
    print(f"  imputed from pope reign:       {n_year_pope:>6,}")
    print(f"  no year (dropped):             {n_year_none:>6,}")
    print(f"  year < {YEAR_FILTER_MIN} (dropped):               "
          f"{n_filt_old:>6,}")
    print(f"  kept:                          {len(rows):>6,}")

    out_path = OUT / "aposcripta_per_doc.csv"
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows):,} rows to {out_path}")

    n_region = sum(1 for r in rows if r["region"])
    print(f"  with region:    {n_region:>6,}  "
          f"({100*n_region/len(rows):.1f}%)")
    print(f"  is_mandement:   "
          f"{sum(r['is_mandement'] for r in rows):>6,}  "
          f"({100*sum(r['is_mandement'] for r in rows)/len(rows):.1f}%)")
    print(f"  is_canapis:     "
          f"{sum(r['is_canapis'] for r in rows):>6,}  "
          f"({100*sum(r['is_canapis'] for r in rows)/len(rows):.1f}%)")
    print(f"  is_published:   "
          f"{sum(r['is_published'] for r in rows):>6,}  "
          f"({100*sum(r['is_published'] for r in rows)/len(rows):.1f}%)")

    region_counts = Counter(r["region"] for r in rows if r["region"])
    print(f"\nRegion distribution:")
    for r, n in region_counts.most_common():
        print(f"  {r:<22} {n:>6,}  ({100*n/len(rows):.1f}%)")

    print(f"\nSubject hit rates:")
    for s in SUBJECT_PATTERNS:
        n = sum(r[f"is_{s}"] for r in rows)
        print(f"  {s:<26} {n:>6,}  ({100*n/len(rows):.1f}%)")
    n_any = sum(1 for r in rows
                if any(r[f"is_{s}"] for s in SUBJECT_PATTERNS))
    print(f"  ANY subject:               {n_any:>6,}  "
          f"({100*n_any/len(rows):.1f}%)")


if __name__ == "__main__":
    main()
