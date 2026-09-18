"""Clean and de-duplicate the two-product review sample."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

from common import (
    data_path,
    iter_jsonl,
    normalize_space,
    safe_float,
    safe_int,
    stable_evidence_id,
    write_json,
    write_jsonl,
)


NON_WORD = re.compile(r"[^a-z0-9\u4e00-\u9fff]+", re.IGNORECASE)


def dedupe_key(text: str) -> str:
    return NON_WORD.sub("", text.casefold())


def cleaned_record(source: dict[str, Any], text: str) -> dict[str, Any]:
    product_id = normalize_space(source.get("_product_id"))
    parent_asin = normalize_space(source.get("parent_asin"))
    return {
        "evidence_id": stable_evidence_id(product_id, parent_asin, text),
        "product_id": product_id,
        "parent_asin": parent_asin,
        "source_asin": normalize_space(source.get("asin")) or None,
        "title": normalize_space(source.get("title")) or None,
        "text": text,
        "rating": safe_float(source.get("rating")),
        "helpful_vote": max(0, safe_int(source.get("helpful_vote"))),
        "verified_purchase": (
            source.get("verified_purchase")
            if isinstance(source.get("verified_purchase"), bool)
            else None
        ),
        "timestamp": source.get("timestamp"),
        "source": {
            "dataset": "Amazon Reviews 2023",
            "input_line": safe_int(source.get("_source_line")),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=data_path("work", "selected_reviews.jsonl")
    )
    parser.add_argument(
        "--output", type=Path, default=data_path("work", "cleaned_reviews.jsonl")
    )
    parser.add_argument(
        "--report", type=Path, default=data_path("work", "clean_report.json")
    )
    parser.add_argument("--min-chars", type=int, default=40)
    parser.add_argument("--max-chars", type=int, default=5_000)
    parser.add_argument("--max-per-product", type=int, default=800)
    args = parser.parse_args()
    if args.min_chars < 1 or args.max_chars < args.min_chars:
        raise ValueError("Require 1 <= --min-chars <= --max-chars")
    if args.max_per_product < 1:
        raise ValueError("--max-per-product must be positive")

    kept: list[dict[str, Any]] = []
    per_product: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    seen_keys: set[tuple[str, str]] = set()

    for _, source in iter_jsonl(args.input):
        product_id = normalize_space(source.get("_product_id"))
        if product_id not in {"demo-tws-a", "demo-tws-b"}:
            rejected["invalid_product_id"] += 1
            continue
        text = normalize_space(source.get("text"))
        if not text:
            rejected["missing_text"] += 1
            continue
        if len(text) < args.min_chars:
            rejected["too_short"] += 1
            continue
        if len(text) > args.max_chars:
            text = text[: args.max_chars].rstrip() + "…"
            rejected["truncated"] += 1
        key = (product_id, dedupe_key(text))
        if key in seen_keys:
            rejected["duplicate"] += 1
            continue
        if per_product[product_id] >= args.max_per_product:
            rejected["over_product_limit"] += 1
            continue
        seen_keys.add(key)
        record = cleaned_record(source, text)
        kept.append(record)
        per_product[product_id] += 1

    if set(per_product) != {"demo-tws-a", "demo-tws-b"}:
        raise ValueError("Cleaning must retain reviews for both selected products")

    kept.sort(key=lambda row: (row["product_id"], row["evidence_id"]))
    write_jsonl(args.output, kept)
    write_json(
        args.report,
        {
            "schema_version": "1.0.0",
            "input": str(args.input),
            "output": str(args.output),
            "kept": dict(sorted(per_product.items())),
            "rejected": dict(sorted(rejected.items())),
            "privacy": (
                "No user_id, reviewer profile, name, email, phone number, or raw image "
                "field is retained."
            ),
            "notes": [
                "De-duplication is exact after case-folding and punctuation removal.",
                "verified_purchase and helpful_vote are evidence-ranking inputs only; they do not prove authenticity.",
            ],
        },
    )
    print(f"Kept {len(kept)} reviews; wrote {args.output}")


if __name__ == "__main__":
    main()
