"""Validate the public synthetic fixture and its manifest without dependencies."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = REPO_ROOT / "data" / "demo_derived.json"
MANIFEST_FILE = REPO_ROOT / "data" / "manifest.json"
PRODUCT_IDS = {"demo-tws-a", "demo-tws-b"}
ASPECTS = {
    "noise_cancellation",
    "call_quality",
    "connection",
    "comfort",
    "battery",
    "sound_quality",
}
STANCES = {"support", "oppose", "mixed"}


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_public_fixture(
    data_file: Path = DATA_FILE, manifest_file: Path = MANIFEST_FILE
) -> dict[str, int]:
    data = _read_json(data_file)
    manifest = _read_json(manifest_file)
    errors: list[str] = []

    if data.get("is_synthetic") is not True:
        errors.append("demo fixture must declare is_synthetic=true")
    if manifest.get("data_class") != "synthetic_demo_cache":
        errors.append("manifest data_class must be synthetic_demo_cache")
    if not data.get("disclaimer_zh") or not manifest.get("disclaimer_zh"):
        errors.append("fixture and manifest both require a Chinese disclosure")

    products = data.get("products")
    evidence = data.get("evidence")
    if not isinstance(products, list) or not isinstance(evidence, list):
        raise ValueError("fixture must contain products[] and evidence[]")
    product_ids = {item.get("id") for item in products if isinstance(item, dict)}
    if product_ids != PRODUCT_IDS:
        errors.append(f"unexpected product IDs: {sorted(product_ids)}")

    seen_ids: set[str] = set()
    coverage: Counter[tuple[str, str]] = Counter()
    for index, item in enumerate(evidence):
        prefix = f"evidence[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        evidence_id = item.get("id")
        if not isinstance(evidence_id, str) or not evidence_id.startswith("ev-demo-"):
            errors.append(f"{prefix}.id is not an explicit demo ID")
        elif evidence_id in seen_ids:
            errors.append(f"duplicate evidence id: {evidence_id}")
        seen_ids.add(evidence_id)
        product_id = item.get("product_id")
        aspect = item.get("aspect")
        if product_id not in PRODUCT_IDS:
            errors.append(f"{prefix}.product_id is invalid")
        if aspect not in ASPECTS:
            errors.append(f"{prefix}.aspect is invalid")
        if item.get("stance") not in STANCES:
            errors.append(f"{prefix}.stance is invalid")
        if item.get("source_kind") != "demo_cache":
            errors.append(f"{prefix} must remain demo_cache")
        if not str(item.get("source_ref", "")).startswith("synthetic:"):
            errors.append(f"{prefix}.source_ref must declare synthetic origin")
        if not str(item.get("quote", "")).startswith("Synthetic demo quote:"):
            errors.append(f"{prefix}.quote must remain visibly synthetic")
        forbidden = {"user_id", "reviewer_id", "profile_name"}.intersection(item)
        if forbidden:
            errors.append(f"{prefix} contains forbidden identifiers: {sorted(forbidden)}")
        coverage[(product_id, aspect)] += 1

    missing = [key for key in sorted((p, a) for p in PRODUCT_IDS for a in ASPECTS) if coverage[key] == 0]
    if missing:
        errors.append(f"missing product/aspect coverage: {missing}")

    declared_files = manifest.get("files") or []
    declared_count = declared_files[0].get("evidence_count") if declared_files else None
    if declared_count != len(evidence):
        errors.append(f"manifest evidence_count={declared_count}, actual={len(evidence)}")
    if errors:
        raise ValueError("Public demo data validation failed:\n- " + "\n- ".join(errors))
    return {"products": len(products), "evidence": len(evidence), "coverage_cells": len(coverage)}


def main() -> None:
    summary = validate_public_fixture()
    print(
        "Public synthetic fixture valid: "
        f"{summary['products']} products, {summary['evidence']} evidence items, "
        f"{summary['coverage_cells']} product/aspect cells."
    )


if __name__ == "__main__":
    main()
