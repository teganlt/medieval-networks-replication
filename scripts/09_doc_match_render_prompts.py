"""
09_doc_match_render_prompts.py
===============================

Stage 9: render the per-doc v3 prompts.

For each doc payload in output/batches_reextract/docs/, this script
renders the full v3 prompt and writes it to
output/batches_reextract/prompts_v3/prompt_<doc_id>.txt.

The v3 variant:
  - Applies the +Royal-tier shortlist filter (drops candidates whose
    name does not appear in the doc text, but always retains
    royal-tier candidates).
  - Uses the compressed pipe-delimited candidate row format.
  - Emits the strengthened prompt template (Rule 1 two-check version,
    Rule 4 peerage-cleric clarification, FP (h) wrong-candidate
    substitution, counter-example, identity-verification checklist).
  - Shared preamble is byte-identical across all docs, enabling
    Anthropic prompt caching at submission time.

The expected output path written into each prompt assumes it is read
by a Claude-Code-style subagent with Write-tool access. The API batch
submitter (10_doc_match_batch_submit.py) automatically replaces the
Write-tool instructions with direct-output instructions before
submission.

CLI:
  python 09_doc_match_render_prompts.py render
      Render all v3 prompts to disk.

  python 09_doc_match_render_prompts.py status
      Report number of prompts rendered and number of verdicts produced
      (in the canonical verdicts_sonnet-4-6/ directory).

  python 09_doc_match_render_prompts.py list-pending [N]
      Print up to N doc_ids without a verdict yet.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_match_prompt import build_subagent_prompt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
BATCHES_DIR = OUT / "batches_reextract"
DOCS_DIR = BATCHES_DIR / "docs"
PROMPTS_V3_DIR = BATCHES_DIR / "prompts_v3"
VERDICTS_DIR = BATCHES_DIR / "verdicts_sonnet-4-6"


def _verdicts_path(doc_id: str) -> Path:
    return VERDICTS_DIR / f"verdicts_{doc_id}.jsonl"


def _prompt_path(doc_id: str) -> Path:
    return PROMPTS_V3_DIR / f"prompt_{doc_id}.txt"


def _doc_payload(doc_id: str) -> dict:
    with open(DOCS_DIR / f"doc_{doc_id}.json", encoding="utf-8") as f:
        return json.load(f)


def _all_doc_ids() -> list[str]:
    return sorted(p.stem.removeprefix("doc_")
                  for p in DOCS_DIR.glob("doc_*.json"))


def render_all() -> None:
    """Render every per-doc v3 prompt to disk."""
    doc_ids = _all_doc_ids()
    PROMPTS_V3_DIR.mkdir(exist_ok=True)
    print(f"Rendering {len(doc_ids)} v3 prompts -> {PROMPTS_V3_DIR}",
          flush=True)
    n_chars_total = 0
    n_chars_max = 0
    n_chars_max_doc = ""
    n_cand_before = 0
    n_cand_after = 0
    for i, did in enumerate(doc_ids, start=1):
        payload = _doc_payload(did)
        out_path = str(_verdicts_path(did))
        prompt = build_subagent_prompt(payload, out_path, v3=True)
        _prompt_path(did).write_text(prompt, encoding="utf-8")
        n_chars_total += len(prompt)
        if len(prompt) > n_chars_max:
            n_chars_max = len(prompt)
            n_chars_max_doc = did
        n_cand_before += payload.get("n_candidates", 0)
        shortlist_marker = "# CANDIDATE SHORTLIST"
        section = (prompt.split(shortlist_marker, 1)[1]
                   if shortlist_marker in prompt else "")
        n_cand_after += sum(1 for ln in section.splitlines()
                            if ln.startswith("p"))
        if i % 2500 == 0:
            print(f"  ... {i:,}/{len(doc_ids):,} rendered", flush=True)
    n = len(doc_ids)
    print(f"  total chars:   {n_chars_total:,}  "
          f"(~{n_chars_total//4:,} tokens)")
    print(f"  mean prompt:   {n_chars_total // n:,} chars  "
          f"(~{n_chars_total // n // 4:,} tokens)")
    print(f"  max prompt:    {n_chars_max:,} chars  "
          f"(~{n_chars_max // 4:,} tokens)  (doc {n_chars_max_doc})")
    print(f"  total candidates in shortlists: "
          f"{n_cand_before:,} -> {n_cand_after:,} "
          f"({100*n_cand_after/max(n_cand_before, 1):.1f}%)")


def status() -> None:
    doc_ids = _all_doc_ids()
    n_prompted = sum(1 for d in doc_ids if _prompt_path(d).exists())
    n_verdict = sum(1 for d in doc_ids if _verdicts_path(d).exists())
    print(f"Status:")
    print(f"  payloads on disk:   {len(doc_ids):,}")
    print(f"  prompts rendered:   {n_prompted:,}")
    print(f"  verdicts available: {n_verdict:,}")
    if n_verdict:
        n_matches = 0
        n_summary = 0
        for d in doc_ids:
            vp = _verdicts_path(d)
            if not vp.exists():
                continue
            with open(vp, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("_summary"):
                            n_summary += 1
                        else:
                            n_matches += 1
                    except json.JSONDecodeError:
                        pass
        print(f"  total match records:   {n_matches:,}")
        print(f"  total summary records: {n_summary:,}")


def list_pending(n: int = 50) -> None:
    doc_ids = _all_doc_ids()
    pending = [d for d in doc_ids if not _verdicts_path(d).exists()]
    print(f"{len(pending)} pending doc_ids (showing up to {n}):")
    for d in pending[:n]:
        print(f"  {d}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "render":
        render_all()
    elif cmd == "status":
        status()
    elif cmd == "list-pending":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        list_pending(n)
    else:
        print(f"unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
