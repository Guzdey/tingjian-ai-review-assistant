from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "tests" / "need_cases.json").read_text(encoding="utf-8"))
client = TestClient(create_app())


def test_thirty_reports_keep_citations_inside_their_product_evidence() -> None:
    audited = 0
    for case in CASES[:15]:
        parsed = client.post(
            "/api/needs/parse",
            json={
                "text": case["text"],
                "selected_scenes": case["selected_scenes"],
                "selected_aspects": case["selected_aspects"],
            },
        ).json()["need"]
        for product_id in ("demo-tws-a", "demo-tws-b"):
            report_response = client.post(
                "/api/reports", json={"product_id": product_id, "need": parsed}
            )
            assert report_response.status_code == 200
            report = report_response.json()
            all_evidence = client.get(
                f"/api/products/{product_id}/evidence?limit=100"
            ).json()["items"]
            by_id = {item["id"]: item for item in all_evidence}
            preview_by_id = {item["id"]: item for item in report["evidence_preview"]}

            assert set(report["citation_ids"]) <= set(preview_by_id)
            assert set(report["citation_ids"]) <= set(by_id)
            assert all(by_id[item]["product_id"] == product_id for item in report["citation_ids"])

            for aspect in report["aspects"]:
                expected = [item for item in all_evidence if item["aspect"] == aspect["aspect"]]
                assert aspect["support_count"] == sum(item["stance"] == "support" for item in expected)
                assert aspect["oppose_count"] == sum(item["stance"] == "oppose" for item in expected)
                assert aspect["mixed_count"] == sum(item["stance"] == "mixed" for item in expected)
                assert set(aspect["evidence_ids"]) <= {item["id"] for item in expected}
            audited += 1
    assert audited == 30
