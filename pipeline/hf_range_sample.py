"""Safely range-sample two products from Amazon Reviews 2023 Electronics.

The source JSONL is roughly 22 GB. This script requires HTTP 206 responses,
validates Content-Range/Content-Length, caps each read at 2 MiB, and caps the
whole run at 50 MiB. It retains no reviewer identifier or image field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import urllib.request
from pathlib import Path
from typing import Any

from common import data_path, normalize_space, write_json, write_jsonl
from sample_products import load_selection


SOURCE_URL = (
    "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/"
    "resolve/main/raw/review_categories/Electronics.jsonl"
)
CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")
MIB = 1024 * 1024


class RangeSafetyError(RuntimeError):
    """The server response failed a bounded-download safety check."""


def source_size(url: str, timeout: float) -> int:
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "tingjian-range-sampler/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        length = response.headers.get("Content-Length", "")
        ranges = response.headers.get("Accept-Ranges", "").lower()
    if not length.isdigit() or "bytes" not in ranges:
        raise RangeSafetyError("Source must expose Content-Length and byte ranges")
    return int(length)


def bounded_range(url: str, start: int, size: int, total: int, timeout: float) -> bytes:
    """Read one exact range; abort before body read if headers are unsafe."""

    end = min(start + size, total) - 1
    expected = end - start + 1
    request = urllib.request.Request(
        url,
        headers={
            "Range": f"bytes={start}-{end}",
            "User-Agent": "tingjian-range-sampler/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        match = CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", ""))
        length = response.headers.get("Content-Length", "")
        if response.status != 206 or not match:
            raise RangeSafetyError("Server did not return a valid HTTP 206 range")
        returned = tuple(map(int, match.groups()))
        if returned != (start, end, total):
            raise RangeSafetyError("Server returned a different byte range")
        if not length.isdigit() or int(length) != expected:
            raise RangeSafetyError("Content-Length differs from requested range")
        payload = response.read(expected + 1)
    if len(payload) != expected:
        raise RangeSafetyError("Response body differs from requested range")
    return payload


def complete_lines(payload: bytes, start: int, end: int, total: int) -> list[bytes]:
    lines = payload.splitlines()
    if start and lines:
        lines = lines[1:]
    if end < total - 1 and payload and not payload.endswith((b"\n", b"\r")) and lines:
        lines = lines[:-1]
    return [line for line in lines if line.strip()]


def sanitized(product_id: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "_product_id": product_id,
        "parent_asin": normalize_space(row.get("parent_asin")),
        "asin": normalize_space(row.get("asin")) or None,
        "rating": row.get("rating"),
        "title": normalize_space(row.get("title")),
        "text": normalize_space(row.get("text")),
        "helpful_vote": row.get("helpful_vote"),
        "verified_purchase": row.get("verified_purchase"),
        "timestamp": row.get("timestamp"),
    }


def run(args: argparse.Namespace) -> int:
    if not 64 * 1024 <= args.chunk_bytes <= 2 * MIB:
        raise ValueError("--chunk-bytes must be between 64 KiB and 2 MiB")
    budget = args.max_transfer_mb * MIB
    if not args.chunk_bytes <= budget <= 50 * MIB:
        raise ValueError("Transfer budget must cover one chunk and be <= 50 MiB")
    if args.max_per_product < 1:
        raise ValueError("--max-per-product must be positive")

    selection = load_selection(args.selection)
    aliases = {item["parent_asin"]: item["product_id"] for item in selection}
    collected: dict[str, list[dict[str, Any]]] = {
        item["product_id"]: [] for item in selection
    }
    fingerprints: set[str] = set()
    total = source_size(args.url, args.timeout)
    rng = random.Random(args.seed)
    starts = [0]
    while len(starts) * args.chunk_bytes < budget:
        starts.append(rng.randrange(0, max(1, total - args.chunk_bytes)))

    transferred = parsed = invalid = chunks = 0
    for start in starts:
        if transferred + args.chunk_bytes > budget:
            break
        payload = bounded_range(args.url, start, args.chunk_bytes, total, args.timeout)
        transferred += len(payload)
        chunks += 1
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
            product_id = aliases.get(normalize_space(row.get("parent_asin")))
            if not product_id or len(collected[product_id]) >= args.max_per_product:
                continue
            review = sanitized(product_id, row)
            if not review["text"]:
                continue
            fingerprint = hashlib.sha256(
                (product_id + "\n" + review["text"].casefold()).encode("utf-8")
            ).hexdigest()
            if fingerprint in fingerprints:
                continue
            fingerprints.add(fingerprint)
            collected[product_id].append(review)
        if all(len(rows) >= args.max_per_product for rows in collected.values()):
            break

    output_rows = [row for key in sorted(collected) for row in collected[key]]
    write_jsonl(args.output, output_rows)
    complete = all(len(rows) >= args.max_per_product for rows in collected.values())
    write_json(
        args.report,
        {
            "schema_version": "1.0.0",
            "purpose": "private_range_sample",
            "source": {
                "dataset": "McAuley-Lab/Amazon-Reviews-2023",
                "category": "Electronics",
                "url": args.url,
                "source_bytes": total,
            },
            "safety": {
                "http_206_required": True,
                "chunk_bytes": args.chunk_bytes,
                "transfer_limit_bytes": budget,
                "bytes_transferred": transferred,
                "raw_chunks_persisted": False,
            },
            "sampling": {
                "seed": args.seed,
                "chunks_used": chunks,
                "rows_parsed": parsed,
                "invalid_partial_or_json_rows": invalid,
                "target_per_product": args.max_per_product,
                "complete": complete,
            },
            "privacy": "user/reviewer identifiers and image fields were not retained",
            "products": [
                {
                    **item,
                    "reviews_collected": len(collected[item["product_id"]]),
                }
                for item in selection
            ],
            "next_step": "Clean the private output with clean_reviews.py.",
        },
    )
    print(
        f"Collected {len(output_rows)} reviews from {transferred / MIB:.1f} MiB; "
        f"complete={complete}; report={args.report}"
    )
    return 0 if complete else 2


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--selection", type=Path, required=True)
    result.add_argument(
        "--output", type=Path, default=data_path("work", "selected_reviews_range.jsonl")
    )
    result.add_argument(
        "--report", type=Path, default=data_path("work", "range_sample_report.json")
    )
    result.add_argument("--url", default=SOURCE_URL)
    result.add_argument("--max-per-product", type=int, default=24)
    result.add_argument("--chunk-bytes", type=int, default=MIB)
    result.add_argument("--max-transfer-mb", type=int, default=40)
    result.add_argument("--seed", type=int, default=20260918)
    result.add_argument("--timeout", type=float, default=60.0)
    return result


def main() -> None:
    raise SystemExit(run(parser().parse_args()))


if __name__ == "__main__":
    main()
