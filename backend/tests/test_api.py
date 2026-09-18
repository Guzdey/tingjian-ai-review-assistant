from fastapi.testclient import TestClient

from backend.app.main import create_app


client = TestClient(create_app())


def parsed_need():
    response = client.post(
        "/api/needs/parse",
        json={"text": "每天坐地铁，也经常开会，连接不能频繁断开"},
    )
    assert response.status_code == 200
    return response.json()["need"]


def test_health_and_products():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["products_loaded"] == 2
    assert health.json()["evidence_loaded"] >= 36
    products = client.get("/api/products").json()["items"]
    assert [item["id"] for item in products] == ["demo-tws-a", "demo-tws-b"]


def test_parse_report_and_evidence_are_traceable():
    need = parsed_need()
    response = client.post(
        "/api/reports", json={"product_id": "demo-tws-a", "need": need}
    )
    assert response.status_code == 200
    report = response.json()
    evidence_ids = {item["id"] for item in report["evidence_preview"]}
    assert set(report["citation_ids"]) <= evidence_ids
    assert report["meta"]["mode"] == "local_rules"
    assert report["meta"]["is_demo_cache"] is True

    evidence = client.get(
        "/api/products/demo-tws-a/evidence?aspect=noise_cancellation"
    )
    assert evidence.status_code == 200
    assert evidence.json()["total"] == 3


def test_compare_and_strict_validation():
    need = parsed_need()
    response = client.post(
        "/api/compare",
        json={"product_ids": ["demo-tws-a", "demo-tws-b"], "need": need},
    )
    assert response.status_code == 200
    assert len(response.json()["products"]) == 2

    invalid = client.post(
        "/api/needs/parse", json={"text": "通勤", "unexpected": True}
    )
    assert invalid.status_code == 422


def test_unknown_product_is_404():
    need = parsed_need()
    response = client.post(
        "/api/reports", json={"product_id": "unknown-product", "need": need}
    )
    assert response.status_code == 404
