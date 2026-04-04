"""GET /health 基礎冒煙測試。"""


def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "local_knowledge_rows" in data


def test_health_contains_model_routing(client):
    r = client.get("/health")
    data = r.json()
    assert "model_routing" in data
    assert "decode_note" in data["model_routing"]
