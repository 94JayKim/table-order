def test_store_info_is_served_on_both_paths(client):
    r = client.get("/api/v1/store")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] and body["branch"] and {"slogan", "tables"} <= body.keys()
    assert client.get("/api/store").json() == body  # 기존 경로도 같은 응답
