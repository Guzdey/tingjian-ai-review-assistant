"""Build a private, traceable six-aspect evidence file with local rules.

This is a deterministic baseline, not a trained classifier. Its output must be
described as rule-derived evidence and should later be manually audited or
replaced by a validated model-assisted annotation pass.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

from common import data_path, iter_jsonl, normalize_space, safe_float, safe_int, write_json


ASPECTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "noise_cancellation": (
        "降噪",
        (
            "noise cancel", "noise cancellation", "anc", "outside noise",
            "background noise", "block out", "noise isolat", "ambient noise",
        ),
    ),
    "call_quality": (
        "通话",
        (
            "phone call", "calls", "calling", "microphone", " mic ",
            "voice", "meeting", "zoom", "caller", "hear me",
        ),
    ),
    "connection": (
        "连接",
        (
            "connect", "pair", "bluetooth", "disconnect", "sync",
            "signal", "range", "drop out", "cut out",
        ),
    ),
    "comfort": (
        "舒适度",
        (
            "comfort", " fit", "ear pain", "hurt", "fall out", "fell out",
            "stay in", "secure", "ear tip", "small ears", "large ears",
        ),
    ),
    "battery": (
        "续航",
        (
            "battery", "charge", "charging", "playtime", "hours", "charger",
            "charging case", "low power",
        ),
    ),
    "sound_quality": (
        "音质",
        (
            "sound", "bass", "treble", "audio", "music", "volume",
            "sound quality", "loud", "clarity",
        ),
    ),
}

POSITIVE = (
    "great", "good", "excellent", "love", "clear", "comfortable", "stable",
    "easy", "quick", "strong", "amazing", "perfect", "reliable", "well",
    "impressive", "recommend", "secure", "long lasting",
)
NEGATIVE = (
    "not ", "don't", "doesn't", "didn't", "won't", "poor", "bad", "worse",
    "issue", "problem", "fail", "stopped", "disconnect", "hurt",
    "uncomfortable", "weak", "terrible", "awful", "disappointed", "broken",
    "static", "died", "dead", "fall out", "fell out", "too low", "too quiet",
)
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|<br\s*/?>", re.IGNORECASE)
ASPECT_CODE = {
    "noise_cancellation": "noise",
    "call_quality": "call",
    "connection": "conn",
    "comfort": "comfort",
    "battery": "battery",
    "sound_quality": "sound",
}


def matched_excerpt(title: str, text: str, keywords: tuple[str, ...]) -> str:
    candidates = [title, *SENTENCE_BREAK.split(text)]
    matched = [normalize_space(item) for item in candidates if any(key in f" {item.casefold()} " for key in keywords)]
    excerpt = " ".join(dict.fromkeys(item for item in matched if item))
    return excerpt[:320].rstrip()


def stance(excerpt: str, rating: float | None) -> str:
    lowered = excerpt.casefold()
    positive = any(token in lowered for token in POSITIVE)
    negative = any(token in lowered for token in NEGATIVE)
    if positive and negative:
        return "mixed"
    if negative:
        return "oppose"
    if positive:
        return "support"
    if rating is not None and rating <= 2:
        return "oppose"
    if rating is not None and rating >= 4:
        return "support"
    return "mixed"


def summary_zh(aspect: str, direction: str) -> str:
    label = ASPECTS[aspect][0]
    direction_label = {"support": "正向", "oppose": "负向", "mixed": "正负并存"}[direction]
    return f"规则标注：该评论在{label}方面表达{direction_label}观点，建议结合英文原句复核。"


def evidence_id(product_id: str, aspect: str, source_id: str, quote: str) -> str:
    digest = hashlib.sha256(
        f"{product_id}\n{aspect}\n{source_id}\n{quote}".encode("utf-8")
    ).hexdigest()[:14]
    alias = product_id.removeprefix("demo-tws-")
    return f"ev-{alias}-{ASPECT_CODE[aspect]}-{digest}"


def build(args: argparse.Namespace) -> None:
    evidence: list[dict[str, Any]] = []
    counts: Counter[tuple[str, str, str]] = Counter()
    input_counts: Counter[str] = Counter()

    for _, row in iter_jsonl(args.input):
        product_id = normalize_space(row.get("product_id"))
        if product_id not in {"demo-tws-a", "demo-tws-b"}:
            continue
        input_counts[product_id] += 1
        title = normalize_space(row.get("title"))
        text = normalize_space(row.get("text"))
        source_id = normalize_space(row.get("evidence_id"))
        rating = safe_float(row.get("rating"))
        for aspect, (_, keywords) in ASPECTS.items():
            excerpt = matched_excerpt(title, text, keywords)
            if not excerpt:
                continue
            direction = stance(excerpt, rating)
            item_id = evidence_id(product_id, aspect, source_id, excerpt)
            evidence.append(
                {
                    "id": item_id,
                    "product_id": product_id,
                    "aspect": aspect,
                    "stance": direction,
                    "quote": excerpt,
                    "summary_zh": summary_zh(aspect, direction),
                    "rating": int(rating) if rating is not None and rating.is_integer() else None,
                    "helpful_votes": max(0, safe_int(row.get("helpful_vote"))),
                    "verified_purchase": row.get("verified_purchase")
                    if isinstance(row.get("verified_purchase"), bool)
                    else None,
                    "source_kind": "derived_dataset",
                    "source_ref": f"private-clean:{source_id}"[:120],
                }
            )
            counts[(product_id, aspect, direction)] += 1

    if not evidence:
        raise ValueError("No aspect evidence was produced")
    evidence.sort(key=lambda item: (item["product_id"], item["aspect"], item["id"]))
    products = [
        {
            "id": product_id,
            "display_name": f"样本耳机 {product_id[-1].upper()}",
            "description": "由公开英文评论生成的匿名私有派生样本；商品身份不在公开仓库展示。",
            "source_kind": "derived_dataset",
        }
        for product_id in ("demo-tws-a", "demo-tws-b")
    ]
    write_json(
        args.output,
        {
            "schema_version": "1.0.0",
            "data_class": "private_rule_derived_dataset",
            "is_synthetic": False,
            "disclaimer_zh": (
                "证据来自公开英文评论的私有匿名样本；主题和倾向由本地规则标注，"
                "不等于人工事实核验，也不证明评论真实性。"
            ),
            "products": products,
            "evidence": evidence,
        },
    )
    coverage = []
    for product_id in ("demo-tws-a", "demo-tws-b"):
        for aspect in ASPECTS:
            directions = {
                direction: counts[(product_id, aspect, direction)]
                for direction in ("support", "oppose", "mixed")
            }
            coverage.append(
                {
                    "product_id": product_id,
                    "aspect": aspect,
                    **directions,
                    "total": sum(directions.values()),
                }
            )
    write_json(
        args.report,
        {
            "schema_version": "1.0.0",
            "method": "deterministic_keyword_and_rating_rules",
            "manual_audit_required": True,
            "input_reviews": dict(sorted(input_counts.items())),
            "evidence_count": len(evidence),
            "coverage": coverage,
            "limitations": [
                "A review may contribute evidence to more than one aspect.",
                "Sentiment rules can miss negation, sarcasm, or aspect-specific contrast.",
                "Sparse cells must remain evidence-insufficient in the product UI.",
            ],
        },
    )
    print(f"Wrote {len(evidence)} rule-derived evidence items to {args.output}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--input", type=Path, default=data_path("work", "cleaned_reviews.jsonl")
    )
    result.add_argument(
        "--output", type=Path, default=data_path("processed", "private_derived.json")
    )
    result.add_argument(
        "--report", type=Path, default=data_path("processed", "rule_coverage.json")
    )
    return result


if __name__ == "__main__":
    build(parser().parse_args())
