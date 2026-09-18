"""Discover TWS candidates and extract a deterministic review sample.

This script does not download Amazon Reviews 2023. Point it at files that were
obtained separately under the source's current terms of use.
"""

from __future__ import annotations

import argparse
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from common import data_path, iter_jsonl, normalize_space, safe_float, safe_int, write_json, write_jsonl


TWS_TERMS = re.compile(
    r"\b(true\s+wireless|wireless\s+earbuds?|bluetooth\s+earbuds?|tws\b|"
    r"in[- ]ear\s+(?:headphones?|earbuds?))",
    re.IGNORECASE,
)
ACCESSORY_TERMS = re.compile(
    r"\b(case|cover|skin|sleeve|ear\s*tips?|replacement|protector|adapter|"
    r"cable|charger|cleaning\s+kit|lanyard)\b",
    re.IGNORECASE,
)


def discover(args: argparse.Namespace) -> None:
    candidates: dict[str, dict[str, Any]] = {}
    scanned_metadata = 0

    for _, item in iter_jsonl(args.metadata):
        scanned_metadata += 1
        parent_asin = normalize_space(item.get("parent_asin"))
        title = normalize_space(item.get("title"))
        searchable = " ".join(
            (
                title,
                normalize_space(item.get("main_category")),
                " ".join(normalize_space(x) for x in item.get("categories", []) if x),
            )
        )
        if not parent_asin or not TWS_TERMS.search(searchable):
            continue
        if ACCESSORY_TERMS.search(title):
            continue
        candidates[parent_asin] = {
            "parent_asin": parent_asin,
            "title": title,
            "store": normalize_space(item.get("store")) or None,
            "main_category": normalize_space(item.get("main_category")) or None,
            "categories": [
                normalize_space(value)
                for value in item.get("categories", [])
                if normalize_space(value)
            ],
            "metadata_rating_number": safe_int(item.get("rating_number")),
            "metadata_average_rating": safe_float(item.get("average_rating")),
        }

    review_counts: Counter[str] = Counter()
    scanned_reviews = 0
    for _, review in iter_jsonl(args.reviews):
        scanned_reviews += 1
        parent_asin = normalize_space(review.get("parent_asin"))
        if parent_asin in candidates:
            review_counts[parent_asin] += 1

    rows = []
    for parent_asin, candidate in candidates.items():
        review_count = review_counts[parent_asin]
        if review_count < args.min_reviews or review_count > args.max_reviews:
            continue
        rows.append({**candidate, "review_count_in_input_file": review_count})
    rows.sort(
        key=lambda row: (
            -row["review_count_in_input_file"],
            -row["metadata_rating_number"],
            row["parent_asin"],
        )
    )

    report = {
        "schema_version": "1.0.0",
        "purpose": "candidate_discovery_only",
        "source_files": {
            "metadata": str(args.metadata),
            "reviews": str(args.reviews),
        },
        "scan": {
            "metadata_records": scanned_metadata,
            "review_records": scanned_reviews,
            "keyword_candidates_before_review_filter": len(candidates),
        },
        "filters": {
            "min_reviews": args.min_reviews,
            "max_reviews": args.max_reviews,
            "limit": args.limit,
        },
        "manual_review_required": True,
        "warning_zh": (
            "关键词命中不等于已确认是真无线耳机。必须人工核验商品类型、价位和评论归属，"
            "再把恰好两款 parent_asin 写入 selection.json。"
        ),
        "candidates": rows[: args.limit],
    }
    write_json(args.output, report)
    print(f"Wrote {min(len(rows), args.limit)} candidates to {args.output}")


def load_selection(path: Path) -> list[dict[str, str]]:
    import json

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    products = payload.get("products") if isinstance(payload, dict) else None
    if not isinstance(products, list) or len(products) != 2:
        raise ValueError("selection.json must contain exactly two products")

    normalized: list[dict[str, str]] = []
    seen_aliases: set[str] = set()
    seen_asins: set[str] = set()
    for product in products:
        if not isinstance(product, dict):
            raise ValueError("Each selected product must be an object")
        product_id = normalize_space(product.get("product_id"))
        parent_asin = normalize_space(product.get("parent_asin"))
        if product_id not in {"demo-tws-a", "demo-tws-b"}:
            raise ValueError("product_id must be demo-tws-a or demo-tws-b")
        if not parent_asin or parent_asin.startswith("REPLACE_"):
            raise ValueError(f"Replace the placeholder parent_asin for {product_id}")
        if product_id in seen_aliases or parent_asin in seen_asins:
            raise ValueError("Selected aliases and parent_asin values must be unique")
        seen_aliases.add(product_id)
        seen_asins.add(parent_asin)
        normalized.append({"product_id": product_id, "parent_asin": parent_asin})
    return sorted(normalized, key=lambda row: row["product_id"])


def extract(args: argparse.Namespace) -> None:
    selected = load_selection(args.selection)
    by_asin = {row["parent_asin"]: row["product_id"] for row in selected}
    reservoirs: dict[str, list[dict[str, Any]]] = {
        row["product_id"]: [] for row in selected
    }
    seen: Counter[str] = Counter()
    rng = random.Random(args.seed)

    for line_number, review in iter_jsonl(args.reviews):
        parent_asin = normalize_space(review.get("parent_asin"))
        product_id = by_asin.get(parent_asin)
        if product_id is None:
            continue
        seen[product_id] += 1
        staged = {
            "_product_id": product_id,
            "_source_line": line_number,
            "parent_asin": parent_asin,
            "asin": normalize_space(review.get("asin")) or None,
            "rating": safe_float(review.get("rating")),
            "title": normalize_space(review.get("title")),
            "text": normalize_space(review.get("text")),
            "helpful_vote": safe_int(review.get("helpful_vote")),
            "verified_purchase": (
                review.get("verified_purchase")
                if isinstance(review.get("verified_purchase"), bool)
                else None
            ),
            "timestamp": review.get("timestamp"),
        }
        bucket = reservoirs[product_id]
        if len(bucket) < args.max_per_product:
            bucket.append(staged)
        else:
            replacement_index = rng.randrange(seen[product_id])
            if replacement_index < args.max_per_product:
                bucket[replacement_index] = staged

    missing = [product_id for product_id in reservoirs if not reservoirs[product_id]]
    if missing:
        raise ValueError(f"No reviews found for: {', '.join(missing)}")

    extracted = []
    for product_id in sorted(reservoirs):
        extracted.extend(
            sorted(reservoirs[product_id], key=lambda row: row["_source_line"])
        )
    write_jsonl(args.output, extracted)
    report = {
        "schema_version": "1.0.0",
        "input": str(args.reviews),
        "output": str(args.output),
        "seed": args.seed,
        "max_per_product": args.max_per_product,
        "privacy": "user_id and profile fields are intentionally not retained",
        "products": [
            {
                **row,
                "reviews_seen": seen[row["product_id"]],
                "reviews_sampled": len(reservoirs[row["product_id"]]),
            }
            for row in selected
        ],
    }
    write_json(args.report, report)
    print(f"Wrote {len(extracted)} sampled reviews to {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser(
        "discover", help="Find candidate TWS products; manual verification is required"
    )
    discover_parser.add_argument("--metadata", type=Path, required=True)
    discover_parser.add_argument("--reviews", type=Path, required=True)
    discover_parser.add_argument(
        "--output", type=Path, default=data_path("work", "candidates.json")
    )
    discover_parser.add_argument("--min-reviews", type=int, default=300)
    discover_parser.add_argument("--max-reviews", type=int, default=100_000)
    discover_parser.add_argument("--limit", type=int, default=100)
    discover_parser.set_defaults(handler=discover)

    extract_parser = subparsers.add_parser(
        "extract", help="Reservoir-sample the two manually selected products"
    )
    extract_parser.add_argument("--reviews", type=Path, required=True)
    extract_parser.add_argument("--selection", type=Path, required=True)
    extract_parser.add_argument(
        "--output", type=Path, default=data_path("work", "selected_reviews.jsonl")
    )
    extract_parser.add_argument(
        "--report", type=Path, default=data_path("work", "sample_report.json")
    )
    extract_parser.add_argument("--max-per-product", type=int, default=800)
    extract_parser.add_argument("--seed", type=int, default=20260917)
    extract_parser.set_defaults(handler=extract)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if getattr(args, "min_reviews", 0) < 0:
        raise ValueError("--min-reviews cannot be negative")
    if getattr(args, "max_per_product", 1) < 1:
        raise ValueError("--max-per-product must be positive")
    args.handler(args)


if __name__ == "__main__":
    main()
