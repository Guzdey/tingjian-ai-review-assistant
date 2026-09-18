from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "tests" / "need_cases.json").read_text(encoding="utf-8"))
client = TestClient(create_app())


def test_twenty_baseline_need_cases() -> None:
    assert len(CASES) == 20
    failures: list[str] = []
    for case in CASES:
        response = client.post(
            "/api/needs/parse",
            json={
                "text": case["text"],
                "selected_scenes": case["selected_scenes"],
                "selected_aspects": case["selected_aspects"],
            },
        )
        if response.status_code != 200:
            failures.append(f"{case['id']}: HTTP {response.status_code}")
            continue
        need = response.json()["need"]
        scenes = set(need["scenes"])
        aspects = {item["name"] for item in need["aspects"]}
        constraints = {item["code"] for item in need["constraints"]}
        missing = {
            "scenes": set(case["expected_scenes"]) - scenes,
            "aspects": set(case["expected_aspects"]) - aspects,
            "constraints": set(case["expected_constraints"]) - constraints,
        }
        missing = {key: sorted(value) for key, value in missing.items() if value}
        if missing:
            failures.append(f"{case['id']}: missing {missing}")
    assert not failures, "\n".join(failures)
