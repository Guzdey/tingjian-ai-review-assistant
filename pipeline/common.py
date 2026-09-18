"""Shared, dependency-free helpers for the Tingjian data pipeline."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Iterator


DEFAULT_DATA_ROOT = Path(
    os.environ.get("TINGJIAN_DATA_ROOT", r"D:\CodexData\tingjian-ai")
)


def data_path(*parts: str) -> Path:
    """Return a path below the external, regenerable data root."""

    return DEFAULT_DATA_ROOT.joinpath(*parts)


def open_text(path: Path, mode: str = "rt"):
    """Open plain text or gzip-compressed text using UTF-8."""

    if "b" in mode:
        raise ValueError("open_text only supports text modes")
    opener = gzip.open if path.suffix.lower() == ".gz" else path.open
    return opener(mode, encoding="utf-8")


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield ``(line_number, object)`` pairs from JSONL or JSONL.GZ."""

    with open_text(path) as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in {path} at line {line_number}: {exc.msg}"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(
                    f"Expected an object in {path} at line {line_number}"
                )
            yield line_number, value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    temporary.replace(path)


def normalize_space(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stable_evidence_id(product_id: str, parent_asin: str, text: str) -> str:
    source = "\n".join((product_id, parent_asin, text)).encode("utf-8")
    return "ev-" + hashlib.sha256(source).hexdigest()[:20]
