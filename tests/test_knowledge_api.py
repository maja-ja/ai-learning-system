"""GET /api/knowledge 結構測試。"""


def test_knowledge_returns_list(client):
    r = client.get("/api/knowledge")
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert "meta" in data
    assert "source" in data["meta"]
