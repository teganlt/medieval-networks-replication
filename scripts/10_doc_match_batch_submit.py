"""
10_doc_match_batch_submit.py
=============================

Stage 10: submit v3 prompts to the Anthropic Batch API.

Requires ANTHROPIC_API_KEY in env. The Batch API offers a 50% discount
on standard list pricing. Submitting all 24,130 v3 prompts at once
exceeds the 256 MB per-request upload limit, so this script supports
chunked submission via --limit (run multiple times until done).

The actual production run used 5 chunks of 5,000 docs each, with
prompt caching enabled (--use-cache). Total spend was ~$330 against a
$1,600 pre-flight estimate (80% savings from caching + shortlist
filtering + prompt compression).

NOTE FOR REPLICATORS:
  The frozen verdicts_sonnet-4-6/ directory is shipped in this package.
  If you only want to reproduce the post-extraction analysis (regressions,
  figures), you can skip this stage entirely and go straight to
  11_doc_match_build_person_summary.py.

  To re-run the extraction (with your own API key, $330 budget):
    1. ensure ANTHROPIC_API_KEY is set
    2. delete or move the existing output/batches_reextract/verdicts_sonnet-4-6/
    3. run this script 5 times with --limit 5000 and --use-cache

Usage:
  python 10_doc_match_batch_submit.py --estimate
      Pre-flight cost estimate; no submission.

  python 10_doc_match_batch_submit.py \\
      --model claude-sonnet-4-6 --use-cache --limit 5000 --budget 150
      One chunk of up to 5,000 docs with prompt caching.

  python 10_doc_match_batch_submit.py --resume msgbatch_abc123
      Skip submission; poll + parse an existing batch.

Output:
  output/batches_reextract/verdicts_<model-tag>/verdicts_<doc_id>.jsonl
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
BATCHES_DIR = OUT / "batches_reextract"
PROMPTS_V3_DEFAULT = BATCHES_DIR / "prompts_v3"

# Batch API pricing per million tokens (50% off list).
# cache_write = 1.25x base input, cache_read = 0.1x base input,
# both with the 50% batch discount applied.
PRICING_BATCH = {
    "claude-haiku-4-5":  {"in": 0.40, "out": 2.00,
                          "cache_write": 0.50, "cache_read": 0.04},
    "claude-sonnet-4-6": {"in": 1.50, "out": 7.50,
                          "cache_write": 1.875, "cache_read": 0.15},
    "claude-opus-4-7":   {"in": 7.50, "out": 37.50,
                          "cache_write": 9.375, "cache_read": 0.75},
}

OUTPUT_MAX_TOKENS = 5000

# Marker where the shared preamble ends and the doc-specific section
# begins in v3-rendered prompts (must match doc_match_prompt.py).
DOC_SECTION_MARKER = "# THE DOCUMENT"

# Replaces the rendered "Use the Write tool ..." block in each prompt.
# The API has no Write tool; the model must emit JSONL as the response
# body.
API_OUTPUT_INSTRUCTION = """\

# OUTPUT FORMAT

Output your response as JSONL: one JSON object per line. Match records
first (zero or more), then exactly one summary line. Do not include
any other text, commentary, code fences, or markdown formatting. Your
entire response must be parseable line-by-line as JSON.

For each matched person, emit one line of:
  {"doc_id": "...", "person_id": "...", "quoted_latin": "...", "quoted_french": "...", "role": "...", "confidence": "high|medium|low", "reasoning": "...", "inferred_subjects": [...]}

Then exactly one summary line:
  {"doc_id": "...", "_summary": true, "n_matches": N, "unmatched_named_persons": [...], "notes": "..."}

If the doc has no peerage references at all, emit ONLY the summary line
with n_matches=0.
"""

WRITE_BLOCK_MARKER = "# WRITE YOUR OUTPUT TO"


def adapt_prompt(prompt_text: str) -> str:
    """Replace the subagent Write-tool block with API-direct output."""
    idx = prompt_text.find(WRITE_BLOCK_MARKER)
    if idx > 0:
        prompt_text = prompt_text[:idx]
    return prompt_text + API_OUTPUT_INSTRUCTION


def split_v3_for_cache(adapted_text: str) -> tuple[str, str]:
    """Split a v3 prompt into (system_text, user_text) for caching.

    system_text = shared preamble + API_OUTPUT_INSTRUCTION (cached)
    user_text   = doc-specific section (analyse + transcription + shortlist)

    The shared preamble is byte-identical across v3 prompts because
    {DOC_ID} interpolations were removed from the schema example.
    """
    if DOC_SECTION_MARKER not in adapted_text:
        raise ValueError(
            f"Prompt missing '{DOC_SECTION_MARKER}'; cannot split for "
            f"cache. Are you sure --prompts-dir points at v3 prompts?"
        )
    idx = adapted_text.find(DOC_SECTION_MARKER)
    api_idx = adapted_text.find(API_OUTPUT_INSTRUCTION.lstrip())
    if api_idx > idx:
        shared = adapted_text[:idx].rstrip()
        doc_specific = adapted_text[idx:api_idx].rstrip()
        api_instruction = adapted_text[api_idx:]
        system_text = shared + "\n\n" + api_instruction.lstrip()
        user_text = doc_specific
    else:
        shared = adapted_text[:idx].rstrip()
        doc_specific = adapted_text[idx:]
        system_text = shared
        user_text = doc_specific
    return system_text, user_text


def model_tag(model: str) -> str:
    return model.replace("claude-", "")


def list_pending(verdicts_dir: Path, prompts_dir: Path) -> list[Path]:
    out = []
    for p in sorted(prompts_dir.glob("prompt_*.txt")):
        doc_id = p.stem.removeprefix("prompt_")
        if not (verdicts_dir / f"verdicts_{doc_id}.jsonl").exists():
            out.append(p)
    return out


def estimate_cost(prompts: list[Path], model: str,
                  use_cache: bool = False) -> dict:
    """Pre-flight cost estimate. 4 chars/token heuristic; ~3K out per doc."""
    pr = PRICING_BATCH[model]
    n = len(prompts)

    if use_cache and prompts:
        first_adapted = adapt_prompt(
            prompts[0].read_text(encoding="utf-8"))
        sys_text, _ = split_v3_for_cache(first_adapted)
        shared_chars = len(sys_text)
        shared_tokens = shared_chars // 4

        total_chars = sum(p.stat().st_size for p in prompts)
        uncached_chars_per_doc = (total_chars / n) - shared_chars
        uncached_tokens_per_doc = max(0,
                                       int(uncached_chars_per_doc // 4))

        cache_write_tokens = shared_tokens  # one write
        cache_read_tokens = (n - 1) * shared_tokens  # n-1 reads
        uncached_in_tokens = n * uncached_tokens_per_doc
        est_out = n * 3000

        cost_write = cache_write_tokens * pr["cache_write"] / 1_000_000
        cost_read = cache_read_tokens * pr["cache_read"] / 1_000_000
        cost_uncached = uncached_in_tokens * pr["in"] / 1_000_000
        cost_out = est_out * pr["out"] / 1_000_000
        total_cost = cost_write + cost_read + cost_uncached + cost_out

        below_min = shared_tokens < 1024
        return {
            "n_docs": n,
            "use_cache": True,
            "shared_tokens": shared_tokens,
            "uncached_in_tokens_total": uncached_in_tokens,
            "out_tokens_total": est_out,
            "cache_write_cost": cost_write,
            "cache_read_cost": cost_read,
            "uncached_in_cost": cost_uncached,
            "out_cost": cost_out,
            "total_cost": total_cost,
            "cache_below_min_warning": below_min,
        }
    else:
        total_chars = sum(p.stat().st_size for p in prompts)
        est_in = total_chars // 4
        est_out = n * 3000
        cost_in = est_in * pr["in"] / 1_000_000
        cost_out = est_out * pr["out"] / 1_000_000
        return {
            "n_docs": n,
            "use_cache": False,
            "in_tokens_total": est_in,
            "out_tokens_total": est_out,
            "in_cost": cost_in,
            "out_cost": cost_out,
            "total_cost": cost_in + cost_out,
        }


def build_batch_requests(prompts: list[Path], model: str,
                         use_cache: bool = False) -> list[dict]:
    requests = []
    for p in prompts:
        doc_id = p.stem.removeprefix("prompt_")
        prompt_text = p.read_text(encoding="utf-8")
        adapted = adapt_prompt(prompt_text)
        if use_cache:
            sys_text, user_text = split_v3_for_cache(adapted)
            params = {
                "model": model,
                "max_tokens": OUTPUT_MAX_TOKENS,
                "system": [
                    {
                        "type": "text",
                        "text": sys_text,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [{"role": "user", "content": user_text}],
            }
        else:
            params = {
                "model": model,
                "max_tokens": OUTPUT_MAX_TOKENS,
                "messages": [{"role": "user", "content": adapted}],
            }
        requests.append({"custom_id": doc_id, "params": params})
    return requests


def submit_batch(client: anthropic.Anthropic,
                 requests: list[dict]) -> str:
    print(f"Submitting batch of {len(requests):,} requests ...")
    batch = client.messages.batches.create(requests=requests)
    print(f"  batch_id:           {batch.id}")
    print(f"  processing_status:  {batch.processing_status}")
    print(f"  created_at:         {batch.created_at}")
    return batch.id


def poll_batch(client: anthropic.Anthropic, batch_id: str,
               interval: int = 30):
    print(f"\nPolling batch {batch_id} every {interval}s ...")
    print(f"(Anthropic SLA is 24h; small batches finish in 1-2h)")
    start = time.time()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        elapsed = int(time.time() - start)
        rc = batch.request_counts
        print(f"  [{elapsed:>5}s] status={batch.processing_status:<12} "
              f"processing={rc.processing:>4} succeeded={rc.succeeded:>4} "
              f"errored={rc.errored:>3} expired={rc.expired:>3}")
        if batch.processing_status in (
                "ended", "canceling", "cancelled", "expired"):
            return batch
        time.sleep(interval)


def parse_results(client: anthropic.Anthropic, batch_id: str,
                  verdicts_dir: Path) -> dict:
    """Stream results from the batch; write per-doc verdicts JSONL."""
    print(f"\nDownloading + parsing batch results ...")
    verdicts_dir.mkdir(parents=True, exist_ok=True)
    n_ok = n_fail = n_parse_err = 0
    total_in = total_out = 0
    total_cache_create = total_cache_read = 0
    for result in client.messages.batches.results(batch_id):
        doc_id = result.custom_id
        if result.result.type != "succeeded":
            print(f"  FAILED  {doc_id}: type={result.result.type}")
            if hasattr(result.result, "error"):
                print(f"          {result.result.error}")
            n_fail += 1
            continue
        msg = result.result.message
        content = msg.content[0].text
        total_in += msg.usage.input_tokens
        total_out += msg.usage.output_tokens
        cci = getattr(msg.usage, "cache_creation_input_tokens", 0) or 0
        cri = getattr(msg.usage, "cache_read_input_tokens", 0) or 0
        total_cache_create += cci
        total_cache_read += cri

        lines = [ln for ln in content.strip().split("\n") if ln.strip()]
        valid_lines = []
        for ln in lines:
            try:
                json.loads(ln)
                valid_lines.append(ln)
            except json.JSONDecodeError:
                pass
        if not valid_lines:
            n_parse_err += 1
            print(f"  PARSE ERROR  {doc_id}: no valid JSONL lines "
                  f"(raw output len {len(content)})")
            continue
        out_path = verdicts_dir / f"verdicts_{doc_id}.jsonl"
        out_path.write_text("\n".join(valid_lines) + "\n",
                            encoding="utf-8")
        n_ok += 1
    return {
        "n_ok": n_ok, "n_fail": n_fail, "n_parse_err": n_parse_err,
        "total_in": total_in, "total_out": total_out,
        "total_cache_create": total_cache_create,
        "total_cache_read": total_cache_read,
    }


def actual_cost(res: dict, pr: dict) -> float:
    return (
        res["total_in"] * pr["in"]
        + res["total_out"] * pr["out"]
        + res["total_cache_create"] * pr["cache_write"]
        + res["total_cache_read"] * pr["cache_read"]
    ) / 1_000_000


def confirm(prompt: str = "Type YES to proceed: ") -> bool:
    try:
        return input(prompt).strip() == "YES"
    except (EOFError, KeyboardInterrupt):
        return False


def print_estimate(est: dict, pr: dict) -> None:
    print(f"\n=== PRE-FLIGHT COST ESTIMATE ===")
    print(f"  Records:           {est['n_docs']:,}")
    if est["use_cache"]:
        print(f"  Caching:           ENABLED")
        print(f"  Shared preamble:   {est['shared_tokens']:,} tokens "
              f"(cached once, read {est['n_docs']-1:,} times)")
        if est["cache_below_min_warning"]:
            print(f"  WARNING:           preamble < 1024 tokens; "
                  f"Anthropic may not cache.")
        print(f"  Uncached input:    "
              f"{est['uncached_in_tokens_total']:,} tokens")
        print(f"  Output:            {est['out_tokens_total']:,} tokens "
              f"(assumed ~3K per doc)")
        print(f"  ----------------------------")
        print(f"  Cache write:       ${est['cache_write_cost']:.4f}")
        print(f"  Cache reads:       ${est['cache_read_cost']:.4f}")
        print(f"  Uncached input:    ${est['uncached_in_cost']:.4f}")
        print(f"  Output:            ${est['out_cost']:.4f}")
        print(f"  TOTAL:             ${est['total_cost']:.4f}")
    else:
        print(f"  Caching:           disabled")
        print(f"  Est input tokens:  {est['in_tokens_total']:,}")
        print(f"  Est output tokens: {est['out_tokens_total']:,}")
        print(f"  Input cost:        ${est['in_cost']:.4f}")
        print(f"  Output cost:       ${est['out_cost']:.4f}")
        print(f"  TOTAL:             ${est['total_cost']:.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-sonnet-4-6",
                    choices=list(PRICING_BATCH.keys()))
    ap.add_argument("--prompts-dir", type=str, default=None,
                    help="Override default prompts directory. Defaults to "
                         "output/batches_reextract/prompts_v3.")
    ap.add_argument("--use-cache", action="store_true",
                    help="Enable Anthropic prompt caching. Splits each v3 "
                         "prompt at DOC_SECTION_MARKER, routes the shared "
                         "preamble through a `system` message with "
                         "cache_control: ephemeral. Requires v3 prompts.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Submit only first N pending docs (chunked runs).")
    ap.add_argument("--estimate", action="store_true",
                    help="Print cost estimate and exit.")
    ap.add_argument("--budget", type=float, default=10.0,
                    help="Abort if estimate exceeds this dollar cap "
                         "(default $10).")
    ap.add_argument("--resume", type=str, default=None,
                    help="Resume from existing batch_id (poll + parse).")
    ap.add_argument("--poll-interval", type=int, default=30)
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY env var not set.")
        sys.exit(1)

    if args.prompts_dir:
        prompts_dir = Path(args.prompts_dir)
        if not prompts_dir.is_absolute():
            prompts_dir = ROOT / prompts_dir
    else:
        prompts_dir = PROMPTS_V3_DEFAULT
    if not prompts_dir.exists():
        print(f"ERROR: prompts dir does not exist: {prompts_dir}")
        sys.exit(1)

    model = args.model
    verdicts_dir = BATCHES_DIR / f"verdicts_{model_tag(model)}"
    print(f"Model:          {model}")
    print(f"Prompts dir:    {prompts_dir}")
    print(f"Output dir:     {verdicts_dir}")
    print(f"Caching:        {'on' if args.use_cache else 'off'}")
    print(f"Budget cap:     ${args.budget:.2f}")
    print()

    client = anthropic.Anthropic()
    pr = PRICING_BATCH[model]

    # Resume path
    if args.resume:
        print(f"Resuming batch_id={args.resume}")
        batch = poll_batch(client, args.resume, args.poll_interval)
        if batch.processing_status != "ended":
            print(f"\nBatch ended with status {batch.processing_status}.")
        res = parse_results(client, args.resume, verdicts_dir)
        cost = actual_cost(res, pr)
        print(f"\n=== DONE (resume) ===")
        print(f"  Wrote:           {res['n_ok']} verdicts")
        print(f"  Actual cost:     ${cost:.4f}")
        return

    pending = list_pending(verdicts_dir, prompts_dir)
    if args.limit:
        pending = pending[:args.limit]
    print(f"Pending docs to submit: {len(pending):,}")
    if not pending:
        print("Nothing to submit. Existing output already complete.")
        return

    if args.use_cache:
        first_text = pending[0].read_text(encoding="utf-8")
        if DOC_SECTION_MARKER not in first_text:
            print(f"ERROR: --use-cache requires v3 prompts (must contain "
                  f"'{DOC_SECTION_MARKER}'). Prompt at {pending[0]} "
                  f"does not.")
            sys.exit(1)

    est = estimate_cost(pending, model, use_cache=args.use_cache)
    print_estimate(est, pr)

    if est["total_cost"] > args.budget:
        print(f"\nESTIMATE ${est['total_cost']:.4f} EXCEEDS BUDGET "
              f"${args.budget:.2f}. Aborting.")
        print(f"Re-run with --budget "
              f"{est['total_cost'] * 1.5:.2f} to proceed.")
        sys.exit(1)

    if args.estimate:
        print("\n--estimate flag set; not submitting.")
        return

    print()
    if not confirm("Type YES to submit: "):
        print("Aborted (confirmation not received).")
        return

    requests = build_batch_requests(pending, model,
                                    use_cache=args.use_cache)
    batch_id = submit_batch(client, requests)

    print(f"\nBatch submitted. To resume polling later if interrupted:")
    print(f"  python scripts/{Path(__file__).name} "
          f"--model {model} --resume {batch_id}")

    batch = poll_batch(client, batch_id, args.poll_interval)
    if batch.processing_status != "ended":
        print(f"\nBatch ended with status {batch.processing_status}.")
    res = parse_results(client, batch_id, verdicts_dir)
    cost = actual_cost(res, pr)
    print(f"\n=== DONE ===")
    print(f"  Wrote:           {res['n_ok']} verdicts")
    print(f"  Failed:          {res['n_fail']}")
    print(f"  Parse errors:    {res['n_parse_err']}")
    print(f"  Actual cost:     ${cost:.4f}")
    print(f"\nOutput:  {verdicts_dir}")


if __name__ == "__main__":
    main()
