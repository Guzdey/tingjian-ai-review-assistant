"""Discover likely earbud products from bounded Amazon Reviews range samples.

This is candidate discovery only. A keyword hit is never proof that an item is
a comparable TWS product; every candidate must be manually checked before it
is added to the private selection file.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from common import data_path, normalize_space, write_json
from hf_range_sample import MIB, SOURCE_URL, bounded_range, complete_lines, source_size


TWS_MENTION = re.compile(
    r"\b(true\s+wireless|wireless\s+earbuds?|bluetooth\s+earbuds?|"
    r"ear\s*buds?|tws)\b",
    re.IGNORECASE,
)


def discover(args: argparse.Namespace) -> None:
    if not 64 * 1024 <= args.chunk_bytes <= 2 * MIB:
        raise ValueError("--chunk-bytes must be between 64 KiB and 2 MiB")
    budget = args.max_transfer_mb * MIB
    if not args.chunk_bytes <= budget <= 50 * MIB:
        raise ValueError("Transfer budget must cover one chunk and be <= 50 MiB")
    if args.limit < 1:
        raise ValueError("--limit must be positive")

    total = source_size(args.url, args.timeout)
    rng = random.Random(args.seed)
    starts = [0]
    while len(starts) * args.chunk_bytes < budget:
        starts.append(rng.randrange(0, max(1, total - args.chunk_bytes)))

    candidates: dict[str, dict] = {}
    transferred = parsed = invalid = 0
    for start in starts:
        payload = bounded_range(args.url, start, args.chunk_bytes, total, args.timeout)
        transferred += len(payload)
        end = min(start + len(payload), total) - 1
        for line in complete_lines(payload, start, end, total):
            try:
                row = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                invalid += 1
                continue
            if not isinstance(row, dict):
                invalid += 1
                continue
            parsed += 1
            title = normalize_space(row.get("title"))
            text = normalize_space(row.get("text"))
            if not TWS_MENTION.search(title + " " + text):
                continue
            parent_asin = normalize_space(row.get("parent_asin"))
            if not parent_asin:
                continue
            item = candidates.setdefault(
                parent_asin,
                {"parent_asin": parent_asin, "keyword_hits": 0, "snippets": []},
            )
            item["keyword_hits"] += 1
            if len(item["snippets"]) < 2:
                item["snippets"].append((title + " — " + text)[:240])

    ranked = sorted(
        candidates.values(), key=lambda item: (-item["keyword_hits"], item["parent_asin"])
    )[: args.limit]
    write_json(
        args.output,
        {
            "schema_version": "1.0.0",
            "purpose": "candidate_discovery_only",
            "manual_verification_required": True,
            "warning_zh": "关键词命中不等于商品已确认是真无线耳机，也不代表样本具有统计代表性。",
            "sampling": {
                "seed": args.seed,
                "bytes_transferred": transferred,
                "rows_parsed": parsed,
                "invalid_rows": invalid,
            },
            "candidates": ranked,
        },
    )
    print(f"Wrote {len(ranked)} candidates from {transferred / MIB:.1f} MiB")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--output", type=Path, default=data_path("work", "range_candidates.json")
    )
    result.add_argument("--url", default=SOURCE_URL)
    result.add_argument("--chunk-bytes", type=int, default=MIB)
    result.add_argument("--max-transfer-mb", type=int, default=16)
    result.add_argument("--limit", type=int, default=30)
    result.add_argument("--seed", type=int, default=20260918)
    result.add_argument("--timeout", type=float, default=60.0)
    return result


if __name__ == "__main__":
    discover(parser().parse_args())
