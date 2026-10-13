import httpx
from fastapi.testclient import TestClient

from app.factory import create_app
from app.services import sens
from tests.conftest import ADMIN, at, login, settings


def member(c, nick, phone="010-1234-5678", consent=True):
    h = login(c, nick)
    c.patch("/api/members/me", headers=h, json={"phone": phone, "marketing_consent": consent})
    return h


def body(grades=("신규",), text="안녕하세요 이벤트 안내"):
    return {"grades": list(grades), "body": text}


def test_signature_matches_sens_spec():
    # HMAC-SHA256(secret, "POST {uri}\n{timestamp}\n{accessKey}") → base64
    import base64, hashlib, hmac
    msg = b"POST /sms/v2/services/svc/messages\n1700000000000\nkey"
    expected = base64.b64encode(hmac.new(b"secret", msg, hashlib.sha256).digest()).decode()
    assert sens.signature("secret", "POST", "/sms/v2/services/svc/messages", "1700000000000", "key") == expected


def test_sms_lms_split_and_ad_wrapping():
    assert sens.msg_type("짧은 문자") == "SMS" and sens.msg_type("가" * 50) == "LMS"
    with TestClient(create_app(settings(), sms_clock=at(14))) as c:
        text = c.post("/admin/api/marketing/sms/preview", headers=ADMIN, json=body()).json()["content"]
        assert text.startswith("(광고)역전할머니맥주\n") and "무료수신거부 080-000-0000" in text.splitlines()[-1]


def test_dry_run_send_logs_and_counts_usage():
    with TestClient(create_app(settings(), sms_clock=at(14))) as c:
        member(c, "가"); member(c, "나")
        p = c.post("/admin/api/marketing/sms/preview", headers=ADMIN, json=body()).json()
        assert p["ok"] and p["targets"] == 2 and p["dry_run"] is True
        r = c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=body())
        assert r.status_code == 200 and r.json()["count"] == 2 and r.json()["request_id"].startswith("dryrun-")
        usage = c.get("/admin/api/marketing/sms/usage", headers=ADMIN).json()
        assert usage["month"] == "2026-10" and sum(usage["used"].values()) == 2
        logs = c.get("/admin/api/marketing/sms/logs", headers=ADMIN).json()
        assert logs[0]["status"] == "dry_run" and logs[0]["target_count"] == 2


def test_targets_exclude_no_consent_no_phone_and_opted_out():
    with TestClient(create_app(settings(), sms_clock=at(14))) as c:
        member(c, "대상")
        member(c, "미동의", consent=False)
        login(c, "번호없음")
        out = member(c, "거부")
        assert c.post("/admin/api/marketing/sms/preview", headers=ADMIN, json=body()).json()["targets"] == 2
        assert c.post("/api/members/me/opt-out", headers=out).json()["opted_out"] is True
        assert c.post("/admin/api/marketing/sms/preview", headers=ADMIN, json=body()).json()["targets"] == 1
        # 다시 동의하면 수신거부가 풀린다
        c.patch("/api/members/me", headers=out, json={"marketing_consent": True})
        assert c.post("/admin/api/marketing/sms/preview", headers=ADMIN, json=body()).json()["targets"] == 2


def test_night_block_empty_body_no_targets_and_quota():
    with TestClient(create_app(settings(sms_monthly_limit=1, lms_monthly_limit=1), sms_clock=at(22))) as c:
        member(c, "가"); member(c, "나")
        p = c.post("/admin/api/marketing/sms/preview", headers=ADMIN, json=body(text=" ")).json()
        assert not p["ok"] and any("야간" in x for x in p["problems"]) and any("비어" in x for x in p["problems"])
        r = c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=body())
        assert r.status_code == 409 and r.json()["detail"]["problems"]
    with TestClient(create_app(settings(sms_monthly_limit=1, lms_monthly_limit=1), sms_clock=at(14))) as c:
        member(c, "가"); member(c, "나")
        r = c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=body())
        assert r.status_code == 409 and "무료 잔여" in r.json()["detail"]["problems"][0]
        assert c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=body(["단골"])).status_code == 409  # 대상 없음
        assert c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=body(["없는등급"])).status_code == 422


def test_real_send_calls_sens_with_signed_request_and_logs_failure():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(202, json={"requestId": "REQ-1"}) if len(calls) == 1 else httpx.Response(500, text="boom")

    fake = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = settings(sms_provider="sens", sms_dry_run=False, sens_service_id="svc", sens_access_key="ak", sens_secret_key="sk",
                   sens_sender_number="02-123-4567", sens_opt_out_number="080-111-2222")
    with TestClient(create_app(cfg, sms_clock=at(14), sms_http=fake)) as c:
        member(c, "가", "010-1111-2222")
        r = c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=body())
        assert r.status_code == 200 and r.json() == {"request_id": "REQ-1", "count": 1, "dry_run": False, "scheduled_at": None}
        req = calls[0]
        assert req.url.path == "/sms/v2/services/svc/messages" and req.headers["x-ncp-iam-access-key"] == "ak"
        assert req.headers["x-ncp-apigw-signature-v2"] == sens.signature(
            "sk", "POST", req.url.path, req.headers["x-ncp-apigw-timestamp"], "ak")
        import json
        payload = json.loads(req.content)
        assert payload["contentType"] == "AD" and payload["from"] == "021234567"
        assert payload["messages"] == [{"to": "01011112222"}] and "080-111-2222" in payload["content"]
        # 두 번째 호출은 서버 오류 → 409 로 거절하고 failed 로그, 한도 사용량에는 포함되지 않음
        assert c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=body()).status_code == 409
        statuses = [l["status"] for l in c.get("/admin/api/marketing/sms/logs", headers=ADMIN).json()]
        assert statuses == ["failed", "sent"]
        used = c.get("/admin/api/marketing/sms/usage", headers=ADMIN).json()["used"]
        assert sum(used.values()) == 1


def test_real_send_requires_sens_settings():
    with TestClient(create_app(settings(sms_provider="sens", sms_dry_run=False), sms_clock=at(14))) as c:
        member(c, "가")
        p = c.post("/admin/api/marketing/sms/preview", headers=ADMIN, json=body()).json()
        assert not p["ok"] and any("SENS 설정" in x for x in p["problems"])


def test_real_send_requires_solapi_settings():
    with TestClient(create_app(settings(sms_dry_run=False), sms_clock=at(14))) as c:
        member(c, "가")
        p = c.post("/admin/api/marketing/sms/preview", headers=ADMIN, json=body()).json()
        assert not p["ok"] and any("솔라피 설정" in x for x in p["problems"])


def test_solapi_auth_header_matches_sdk_rule():
    import hashlib, hmac
    h = sens.solapi_auth("KEY", "SECRET", "2026-10-13T12:00:00+00:00", "salt1")
    sig = hmac.new(b"SECRET", b"2026-10-13T12:00:00+00:00salt1", hashlib.sha256).hexdigest()
    assert h == f"HMAC-SHA256 ApiKey=KEY, Date=2026-10-13T12:00:00+00:00, salt=salt1, signature={sig}"


def test_real_send_via_solapi_and_failure_logged():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, json={"groupInfo": {"groupId": "G1", "count": {"total": 1, "registeredFailed": 0}}})
        return httpx.Response(400, json={"errorCode": "SenderIdNotFound", "errorMessage": "발신번호 미등록"})

    fake = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = settings(sms_dry_run=False, solapi_api_key="ak", solapi_api_secret="sk",
                   solapi_sender_number="010-9999-8888", sens_opt_out_number="080-111-2222")
    with TestClient(create_app(cfg, sms_clock=at(14), sms_http=fake)) as c:
        member(c, "가", "010-1111-2222")
        r = c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=body())
        assert r.status_code == 200 and r.json() == {"request_id": "G1", "count": 1, "dry_run": False, "scheduled_at": None}
        req = calls[0]
        assert req.url.path == "/messages/v4/send-many/detail"
        assert req.headers["authorization"].startswith("HMAC-SHA256 ApiKey=ak, Date=")
        import json
        m = json.loads(req.content)["messages"][0]
        assert m["to"] == "01011112222" and m["from"] == "01099998888" and m["type"] == "SMS"
        assert m["text"].startswith("(광고)") and "080-111-2222" in m["text"]
        bad = c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=body())
        assert bad.status_code == 409 and "SenderIdNotFound" in bad.json()["detail"]["problems"][0]
        assert [l["status"] for l in c.get("/admin/api/marketing/sms/logs", headers=ADMIN).json()] == ["failed", "sent"]


def test_dry_run_schedule_and_cancel_restores_quota():
    with TestClient(create_app(settings(), sms_clock=at(14))) as c:
        member(c, "가"); member(c, "나")
        sched = {**body(), "scheduled_at": "2026-10-13T10:00:00+09:00"}
        p = c.post("/admin/api/marketing/sms/preview", headers=ADMIN, json=sched).json()
        assert p["ok"] and p["scheduled_at"].startswith("2026-10-13T10:00")
        r = c.post("/admin/api/marketing/sms/send", headers=ADMIN, json=sched)
        assert r.status_code == 200 and r.json()["count"] == 2 and r.json()["scheduled_at"]
        log = c.get("/admin/api/marketing/sms/logs", headers=ADMIN).json()[0]
        assert log["status"] == "scheduled" and log["scheduled_at"].startswith("2026-10-13T10:00")
        usage = lambda: sum(c.get("/admin/api/marketing/sms/usage", headers=ADMIN).json()["used"].values())
        assert usage() == 2  # 예약도 한도를 차지한다
        assert c.post(f"/admin/api/marketing/sms/logs/{log['id']}/cancel", headers=ADMIN).json()["status"] == "canceled"
        assert usage() == 0  # 취소하면 복구
        assert c.post(f"/admin/api/marketing/sms/logs/{log['id']}/cancel", headers=ADMIN).status_code == 409
        assert c.post("/admin/api/marketing/sms/logs/999/cancel", headers=ADMIN).status_code == 404


def test_schedule_rules_past_lead_time_and_night():
    with TestClient(create_app(settings(), sms_clock=at(14))) as c:
        member(c, "가")
        def probs(when):
            return c.post("/admin/api/marketing/sms/preview", headers=ADMIN,
                          json={**body(), "scheduled_at": when}).json()["problems"]
        assert any("10분" in x for x in probs("2026-10-12T14:05:00+09:00"))
        assert any("야간" in x for x in probs("2026-10-12T22:00:00+09:00"))
        assert probs("2026-10-12T18:00:00+09:00") == []
        assert probs("2026-10-12T18:00:00") == []  # 시간대 없으면 KST


def test_real_schedule_sends_scheduled_date_and_cancel_calls_solapi():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "DELETE":
            return httpx.Response(200, json={"groupId": "G9"})
        return httpx.Response(200, json={"groupInfo": {"groupId": "G9", "count": {"total": 1, "registeredFailed": 0}}})

    fake = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = settings(sms_dry_run=False, solapi_api_key="ak", solapi_api_secret="sk",
                   solapi_sender_number="010-9999-8888", sens_opt_out_number="080-111-2222")
    with TestClient(create_app(cfg, sms_clock=at(14), sms_http=fake)) as c:
        member(c, "가", "010-1111-2222")
        r = c.post("/admin/api/marketing/sms/send", headers=ADMIN,
                   json={**body(), "scheduled_at": "2026-10-12T18:00:00+09:00"})
        assert r.status_code == 200 and r.json()["request_id"] == "G9"
        import json
        assert json.loads(calls[0].content)["scheduledDate"] == "2026-10-12T09:00:00.000Z"
        log = c.get("/admin/api/marketing/sms/logs", headers=ADMIN).json()[0]
        assert log["status"] == "scheduled"
        assert sum(c.get("/admin/api/marketing/sms/usage", headers=ADMIN).json()["used"].values()) == 1
        assert c.post(f"/admin/api/marketing/sms/logs/{log['id']}/cancel", headers=ADMIN).status_code == 200
        assert calls[1].method == "DELETE" and calls[1].url.path == "/messages/v4/groups/G9/schedule"
        assert sum(c.get("/admin/api/marketing/sms/usage", headers=ADMIN).json()["used"].values()) == 0
