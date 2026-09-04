"""
03_named_anchor_dynasty.py
===========================

Stage 3 of the replication pipeline.

Assigns each peerage person to a dynasty using the hand-curated
"named-anchor" scheme. There are 21 named medieval dynasties, each
defined by 2-7 historically-named anchor figures (e.g., the Capetian
dynasty is anchored by Hugh Capet, Robert II, Henry I, etc.).

Algorithm:
  1. Locate each anchor by name match in persons_imputed.csv. Multi-
     matches (same name belonging to multiple persons) are filtered by
     birth-year window ANCHOR_BIRTH_MIN..ANCHOR_BIRTH_MAX to suppress
     namesake collisions from later centuries.
  2. Multi-source BFS from all anchors over the (undirected) parent-
     child adjacency, depth cap BFS_DEPTH=6. Each visited person
     inherits the closest anchor's dynasty; ties broken by descending
     count of located anchors per dynasty, then first-arrival.
  3. Bilineal closest-ancestor extension: for unvisited persons, walk
     up parent0/parent1 to find the nearest assigned ancestor; inherit
     their dynasty. Father (parent0) preferred on ties. Iterate to
     fixed point (max MAX_PROP_DEPTH=30).

Inputs (in output/):
  persons_imputed.csv
  parent_order.csv

Outputs (in output/):
  named_dynasty_assignment.csv      one row per person: id, dynasty
                                    (dynasty empty if not reached)
  dynasty_anchor_audit.csv          one row per (dynasty, anchor name,
                                    candidate id, kept/dropped, reason)
  dynasty_assignment_summary.csv    one row per dynasty: n_anchors_named,
                                    n_anchors_located, n_bfs_reached,
                                    n_bilineal_only, n_total

Anchor scheme provenance (changes from the 5_8 pipeline, documented for
replicators):
  - Multi-match anchors filtered to birth in [800, 1050]. Removes:
      * a 1175-1206 and a 1445-1511 'Hedwig von Sachsen' that were
        silently joining Capetian
      * a 1410-1465 'Angharad ferch Hywel' joining Welsh_Dinefwr
  - Rollo Ragnvaldsson removed from Blois_Burgundy (he founded
    Normandy; was creating BFS leakage into Norman_Ducal descendants).
  - Rurikid_Kiev renamed to Eastern_Europe (the bloc spans Rurikid +
    Byzantine + Bulgarian royal lines via Vladimir I's marriage; the
    broader label is honest about the inclusion).
  - Brienne trimmed from 4 generations (Engilbert I-II-III-IV) to 2
    (Engilbert I-II); descendants III and IV were extending BFS reach
    inappropriately without representing distinct founder origins.
  - 'Hadwig' removed from Capetian (no match in the source).
  - Salian added as a new 21st dynasty (3 anchors: Henry of Speyer,
    Conrad II HRE, Gisela of Swabia). Previously the Salian HRE
    emperors (Conrad II through Heinrich V, 1024-1125) were getting
    assigned to Norman_Ducal via distant maternal ancestry.

Known gap: the Hohenstaufens are NOT anchored. The dynasty doesn't
emerge until the late 11th century (Friedrich I of Swabia, born 1063),
which is past the anchor birth-year window. Hohenstaufen descendants
including Frederick I Barbarossa are still mis-assigned (typically to
Norman_Ducal). Treated as a documented limitation.
"""

from __future__ import annotations
import csv
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

BFS_DEPTH = 6
MAX_PROP_DEPTH = 30
ANCHOR_BIRTH_MIN = 800
ANCHOR_BIRTH_MAX = 1050


NAMED_ANCHORS = {
    "Ottonian": [
        "Heinrich I von Sachsen, Holy Roman Emperor",
        "Otto I von Sachsen, Holy Roman Emperor",
        "Otto II von Sachsen, Holy Roman Emperor",
        "Mathilda von Ringelheim",
        "Dietrich Graf von Ringelheim",
        "Mathilde von Sachsen",
        "Liudolf, Duke of Swabia",
    ],
    "Capetian": [
        "Hugues de Paris, Roi des Francs ",
        "Hugues of Neustria, Comte de Paris",
        "Hedwig von Sachsen",
        "Frédéric I, Duc de Lorraine",
        "Beatrice Capet",
    ],
    "West_Saxon": [
        "Eadweard I, King of Wessex",
        "Eadgar 'the Peaceful', King of England",
        "Æthelred II 'the Unready', King of England",
        "Eadmund I, King of England",
        "Eadwig, King of England",
        "Ælfthryth, Princess of Wessex",
    ],
    "Norman_Ducal": [
        "Richard I, 3rd Duc de Normandie",
        "Richard II, 4th Duc de Normandie",
        "Gunnor de Crêpon",
        "Hedwig de Normandie",
        "Godfrey de Bretagne, Duc de Bretagne",
    ],
    "Angevin": [
        "Fulk II d'Anjou, Comte d'Anjou ",
        "Geoffrey I d'Anjou, 4th Comte d'Anjou ",
        "Gerberge de Tours",
        "Adelais de Vermandois",
        "Roselle de Loch",
    ],
    "Blois_Burgundy": [
        "Bertha de Bourgogne",
        "Eudes I, Comte de Blois",
        "Luitgarda de Vermandois",
        "Poppa of Normandy de Valois",
    ],
    "Carolingian_Lotharingian": [
        "Gerberge von Sachsen",
        "Reginar I Comte de Hainaut Herzog von Lothringen",
        "Alberade von Kleve",
        "Louis IV d'Outre-Mer, Roi des Francs",
        "Lothair, Roi des Francs",
    ],
    "Brienne": [
        "Engilbert, Comte de Brienne",
        "Engilbert II, Comte de Brienne",
    ],
    "Flanders_Hamaland": [
        "Adela 'de Wrede' Gravin van Hamaland",
        "Arnulfus 'de Grote' Graaf van Vlaanderen Comte d'Artois "
        "Boulogne Ternois et Saint-Pol",
        "Eahlwið, Princess of Mercia",
        "Adèle de Vermandois",
        "Hildegarde van Vlaanderen",
    ],
    "Luxemburg": [
        "Siegfried von Luxemburg Graf von Moselgau",
        "Hedwige d'Alsace-Nordgau",
        "Arnulf 'Gandensis' Graaf in Hollant en West Friesland",
        "Friedrich I von Luxemburg Graf im Moselgau",
        "Ermentrude von der Wetterau Gräfin von Gleiberg",
    ],
    "Alba_Scottish": [
        "Kenneth III, King of Alba ",
        "Malcolm II, King of Alba",
        "Kenneth II, King of Alba ",
        "Malcolm I, King of Alba ",
        "Duff 'the Black', King of Alba ",
    ],
    "Welsh_Dinefwr": [
        "Hywel 'Dda' ap Cadell, King of the Britons",
        "Owain ap Hywel",
        "Elen of Dyfed",
        "Angharad ferch Hywel",
        "Dingad ap Tudor Trefor",
    ],
    "Bavarian_Welf": [
        "Heinrich Herzog von Unter-Bayern",
        "Rudolph II Graf von Altdorf",
        "Rudolph Herzog von Unter-Bayern",
        "Itha von Öninge",
        "Atha Gräfin von Hohenwart",
    ],
    "Proto_Habsburg": [
        "Lanzelin I von Muri",
        "Luitgard von Thurgau",
        "Hugh III Graf von Hohenburg",
        "Berthold I Gräfin von Breisgau",
        "Luitgard von Nellenburg",
    ],
    "Ostphalian_Saxon": [
        "Dietrich I Graf in Hassenga",
        "Dedi I Graf in Hassenga",
        "Dedi Graf in Hassenga",
        "Tietburga von Haldensleben",
    ],
    "Piast_Polish": [
        "Mieszko I, Duke of Poland",
        "Dubrawka von Böhmen",
        "Boleslaw I Herzog von Böhmen",
        "Boleslaw I, King of Poland",
    ],
    "Jelling_Danish": [
        "Sveyn I 'Forkbeard' Haraldsson, King of Denmark and England",
        "Harald I 'Bluetooth' Gormsson, King of Denmark",
        "Gunhilda of Poland",
        "Sigrid 'the Haughty' (?)",
        "Gyrid Olafsdottir",
    ],
    "Yngling_Norwegian": [
        "Harald I, King of Norway",
        "Harald Grenske, King of Westfold ",
        "Eirik I, King of Norway and Northumbria",
        "Asta Gudbransdotter",
        "Olav, King in Vigen",
    ],
    "Ivrea_Italy": [
        "Berengar II d'Ivrea, King of Italy ",
        "Willa di Toscana",
        "Rozela d'Ivrea",
        "Hugh d'Arles, King of Italy ",
    ],
    "Eastern_Europe": [
        "St. Vladimir I, Grand Duke of Kiev",
        "Svyatolslav I, Grand Duke of Kiev",
        "Romanus II, Emperor of Constantinople",
        "Simeon I, King of Bulgaria",
    ],
    "Salian": [
        "Henry, Count of Speyer",
        "Conrad II, Holy Roman Emperor",
        "Gisela of Swabia",
    ],
}


def to_year(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def load_persons():
    persons = {}
    name_to_ids = defaultdict(list)
    name_trim_to_ids = defaultdict(list)
    with open(OUT / "persons_imputed.csv", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            b = to_year(row["birth"])
            d = to_year(row["death"])
            persons[row["id"]] = {"name": row["name"], "sex": row["sex"],
                                  "birth": b, "death": d}
            name_to_ids[row["name"]].append(row["id"])
            name_trim_to_ids[row["name"].strip()].append(row["id"])
    return persons, name_to_ids, name_trim_to_ids


def load_parent_order():
    parent0 = {}
    parent1 = {}
    pc_adj = defaultdict(set)
    parent_pairs = []
    with open(OUT / "parent_order.csv", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            cid = row["child_id"]
            if row["parent0_id"]:
                parent0[cid] = row["parent0_id"]
                parent_pairs.append((cid, row["parent0_id"]))
            if row["parent1_id"]:
                parent1[cid] = row["parent1_id"]
                parent_pairs.append((cid, row["parent1_id"]))
    for c, p in parent_pairs:
        pc_adj[c].add(p)
        pc_adj[p].add(c)
    return parent0, parent1, pc_adj


def locate_anchors(persons, name_to_ids, name_trim_to_ids):
    """Locate anchors, filtering multi-matches by birth year window.

    Returns:
        anchor_to_dynasty: {pid: dynasty}
        located_per_dyn:   {dynasty: [pid, ...]}
        audit_rows:        list of (dynasty, anchor_name, pid, birth,
                            status, reason) tuples for every candidate match,
                            including filtered-out and zero-match anchors.
    """
    anchor_to_dynasty = {}
    located_per_dyn = {}
    audit_rows = []
    print("\nLocating named anchors ...")
    for dyn, names in NAMED_ANCHORS.items():
        located = []
        for nm in names:
            ids = name_to_ids.get(nm, []) or name_trim_to_ids.get(
                nm.strip(), [])
            if not ids:
                audit_rows.append((dyn, nm, "", "", "no_match",
                                    "name not found in persons_imputed"))
                continue
            if len(ids) > 1:
                kept = []
                for pid in ids:
                    b = persons[pid]["birth"]
                    in_window = (b is None
                                 or ANCHOR_BIRTH_MIN <= b <= ANCHOR_BIRTH_MAX)
                    if in_window:
                        kept.append(pid)
                        audit_rows.append((dyn, nm, pid, b or "",
                                            "kept",
                                            "multi-match, within window"))
                    else:
                        audit_rows.append((dyn, nm, pid, b or "",
                                            "filtered_out_of_window",
                                            f"multi-match, birth {b} outside "
                                            f"[{ANCHOR_BIRTH_MIN},"
                                            f"{ANCHOR_BIRTH_MAX}]"))
                ids = kept
            else:
                pid = ids[0]
                b = persons[pid]["birth"]
                audit_rows.append((dyn, nm, pid, b or "",
                                    "kept", "single match"))
            for pid in ids:
                if pid not in anchor_to_dynasty:
                    anchor_to_dynasty[pid] = dyn
                    located.append(pid)
        located_per_dyn[dyn] = located
        print(f"  {dyn:<28} ({len(names)} names): {len(located)} located")

    n_filtered = sum(1 for r in audit_rows
                     if r[4] == "filtered_out_of_window")
    n_no_match = sum(1 for r in audit_rows if r[4] == "no_match")
    if n_filtered:
        print(f"\nFiltered {n_filtered} out-of-window multi-match anchors "
              f"(see dynasty_anchor_audit.csv).")
    if n_no_match:
        print(f"{n_no_match} anchor names had no match in persons_imputed "
              f"(see audit CSV).")

    return anchor_to_dynasty, located_per_dyn, audit_rows


def propagate(persons, parent0, parent1, pc_adj, anchor_to_dynasty,
              located_per_dyn):
    """Two-phase propagation: BFS then bilineal extension.

    Returns:
        assignment:    {pid: dynasty}
        anc_depth:     {pid: depth from nearest anchor}
        bfs_reached:   set of pids assigned by BFS (depth <= BFS_DEPTH)
                       (includes anchors themselves at depth 0)
    """
    print("\nMulti-source BFS depth 6 ...", flush=True)
    assignment = dict(anchor_to_dynasty)
    depth_of = {pid: 0 for pid in assignment}
    # Seed order: anchors of dynasties with MORE located anchors go first
    # (so they win arrival ties).
    seed_order = sorted(anchor_to_dynasty.items(),
                        key=lambda kv: -len(located_per_dyn[kv[1]]))
    q = deque((pid, 0) for pid, _ in seed_order)
    while q:
        cur, d = q.popleft()
        if d >= BFS_DEPTH:
            continue
        for n in pc_adj[cur]:
            if n not in assignment:
                assignment[n] = assignment[cur]
                depth_of[n] = d + 1
                q.append((n, d + 1))
    bfs_reached = set(assignment)
    print(f"  after BFS: {len(assignment):,}")

    print("Bilineal extension to fixed point ...", flush=True)
    order = sorted(persons.keys(),
                   key=lambda p: (persons[p]["birth"] is None,
                                  persons[p]["birth"] or 0))
    anc_depth = {pid: depth_of.get(pid, 0) for pid in assignment}
    for it in range(MAX_PROP_DEPTH):
        prev = len(assignment)
        for cid in order:
            if cid in assignment:
                continue
            p0 = parent0.get(cid)
            p1 = parent1.get(cid)
            cand = []
            if p0 in assignment:
                cand.append((anc_depth[p0] + 1, assignment[p0], "parent0"))
            if p1 in assignment:
                cand.append((anc_depth[p1] + 1, assignment[p1], "parent1"))
            if not cand:
                continue
            best = min(cand, key=lambda t: (t[0],
                                            0 if t[2] == "parent0" else 1))
            assignment[cid] = best[1]
            anc_depth[cid] = best[0]
        if len(assignment) == prev:
            break
    print(f"  after bilineal: {len(assignment):,} of "
          f"{len(persons):,} ({100*len(assignment)/len(persons):.1f}%)")
    return assignment, anc_depth, bfs_reached


def write_audit(audit_rows, located_per_dyn, assignment, bfs_reached):
    with open(OUT / "dynasty_anchor_audit.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dynasty", "anchor_name", "candidate_id", "birth",
                    "status", "reason"])
        for row in audit_rows:
            w.writerow(row)

    counts = Counter(assignment.values())
    bfs_counts = Counter(assignment[p] for p in bfs_reached)
    with open(OUT / "dynasty_assignment_summary.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dynasty", "n_anchors_named", "n_anchors_located",
                    "n_bfs_reached", "n_bilineal_only", "n_total"])
        for dyn in NAMED_ANCHORS:
            n_named = len(NAMED_ANCHORS[dyn])
            n_located = len(located_per_dyn.get(dyn, []))
            n_bfs = bfs_counts.get(dyn, 0)
            n_total = counts.get(dyn, 0)
            n_bilineal = n_total - n_bfs
            w.writerow([dyn, n_named, n_located, n_bfs, n_bilineal, n_total])


def main():
    print("Loading persons + parent_order ...", flush=True)
    persons, n2i, n2it = load_persons()
    parent0, parent1, pc_adj = load_parent_order()
    print(f"  persons: {len(persons):,}", flush=True)

    anchor_to_dyn, located_per_dyn, audit_rows = locate_anchors(
        persons, n2i, n2it)
    assignment, _anc_depth, bfs_reached = propagate(
        persons, parent0, parent1, pc_adj,
        anchor_to_dyn, located_per_dyn)

    print("\nDynasty descendant counts:")
    for dyn, n in sorted(Counter(assignment.values()).items(),
                         key=lambda kv: -kv[1]):
        print(f"  {dyn:<28} {n:>7,}")

    with open(OUT / "named_dynasty_assignment.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "dynasty"])
        for pid in persons:
            w.writerow([pid, assignment.get(pid, "")])

    write_audit(audit_rows, located_per_dyn, assignment, bfs_reached)

    print("\nDone. Stage 3 outputs:")
    print("  output/named_dynasty_assignment.csv")
    print("  output/dynasty_anchor_audit.csv")
    print("  output/dynasty_assignment_summary.csv")


if __name__ == "__main__":
    main()
