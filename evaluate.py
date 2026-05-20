#!/usr/bin/env python3
"""
Evaluate prompts in unified_chats.jsonl using an LLM via OpenRouter.

Usage:
    python3 evaluate.py
    python3 evaluate.py --input unified_chats.jsonl --output evaluated_prompts.jsonl
    python3 evaluate.py --limit 50
    python3 evaluate.py --resume
"""

import asyncio
import json
import os
import sys
import argparse
from pathlib import Path

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4-0324"

SYSTEM_PROMPT = """You are a prompt quality evaluator. Score each user prompt on four dimensions:

- clarity (1-5): Is intent unambiguous? 1=completely unclear, 5=crystal clear
- specificity (1-5): Concrete constraints vs vague ask? 1=no constraints, 5=fully specified
- intent (1-5): Is goal explicitly stated? 1=no goal apparent, 5=goal stated precisely
- filler_penalty (0-3): Count hedging/filler phrases like "just", "basically", "kind of", "maybe", "I was wondering", "could you perhaps". 0=none, 1=light, 2=moderate, 3=heavy

Return ONLY a JSON array, one object per prompt, in the same order as input:
[
  {"clarity_score": 4, "specificity_score": 3, "intent_score": 5, "filler_penalty": 0, "notes": "one-line explanation"},
  ...
]

No extra text. No markdown fences. Just the JSON array."""


def build_user_message(batch: list[dict]) -> str:
    parts = []
    for i, record in enumerate(batch):
        preview = record["user_prompt"][:600]
        parts.append(f"[{i}] {preview}")
    return "Score these prompts:\n\n" + "\n\n".join(parts)


def composite_score(scores: dict) -> float:
    mean = (scores["clarity_score"] + scores["specificity_score"] + scores["intent_score"]) / 3
    return round(mean - 0.2 * scores["filler_penalty"], 3)


def extract_json_array(text: str) -> str:
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


async def evaluate_batch(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    batch: list[dict],
    sem: asyncio.Semaphore,
) -> list[dict]:
    async with sem:
        resp = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_message(batch)},
                ],
                "max_tokens": 2048,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        if content is None:
            raise ValueError("Model returned null content")
        raw = content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        raw = extract_json_array(raw)
        scores = json.loads(raw)
        results = []
        for record, score in zip(batch, scores):
            results.append({
                "session_id": record["session_id"],
                "turn_index": record["turn_index"],
                "platform": record["platform"],
                "clarity_score": score["clarity_score"],
                "specificity_score": score["specificity_score"],
                "intent_score": score["intent_score"],
                "filler_penalty": score["filler_penalty"],
                "composite_score": composite_score(score),
                "notes": score.get("notes", ""),
            })
        return results


async def run(
    input_path: str,
    output_path: str,
    limit: int | None,
    resume: bool,
    batch_size: int,
    concurrency: int,
    model: str,
) -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    records = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if limit:
        records = records[:limit]

    already_done: set[tuple] = set()
    if resume and Path(output_path).exists():
        with open(output_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    already_done.add((r["session_id"], r["turn_index"]))
        records = [r for r in records if (r["session_id"], r["turn_index"]) not in already_done]
        print(f"Resume: {len(already_done)} already done, {len(records)} remaining")

    if not records:
        print("Nothing to evaluate.")
        return

    batches = [records[i : i + batch_size] for i in range(0, len(records), batch_size)]
    print(f"Evaluating {len(records)} turns across {len(batches)} batches (concurrency={concurrency}, model={model})")

    sem = asyncio.Semaphore(concurrency)
    completed = 0
    errors = 0
    abort = asyncio.Event()

    write_mode = "a" if resume else "w"
    async with httpx.AsyncClient() as client:
        with open(output_path, write_mode, encoding="utf-8") as out:
            tasks = [evaluate_batch(client, api_key, model, b, sem) for b in batches]
            for coro in asyncio.as_completed(tasks):
                if abort.is_set():
                    break
                try:
                    results = await coro
                    for r in results:
                        out.write(json.dumps(r) + "\n")
                    out.flush()
                    completed += len(results)
                    print(f"  {completed}/{len(records)}", end="\r", flush=True)
                except httpx.HTTPStatusError as e:
                    errors += 1
                    print(f"\nBatch error: {e}", file=sys.stderr)
                    if e.response.status_code in (401, 403):
                        print("Auth error — check OPENROUTER_API_KEY. Aborting.", file=sys.stderr)
                        abort.set()
                        break
                except Exception as e:
                    errors += 1
                    print(f"\nBatch error: {e}", file=sys.stderr)

    print(f"\nDone: {completed} evaluated, {errors} batch errors → {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate prompts via OpenRouter")
    parser.add_argument("--input", default="unified_chats.jsonl")
    parser.add_argument("--output", default="evaluated_prompts.jsonl")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=None, help="Evaluate first N turns only")
    parser.add_argument("--resume", action="store_true", help="Skip already-evaluated turns")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: {args.input} not found. Run generate_dashboard.py first.")
        sys.exit(1)

    asyncio.run(run(args.input, args.output, args.limit, args.resume, args.batch_size, args.concurrency, args.model))


if __name__ == "__main__":
    main()
