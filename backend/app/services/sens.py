"""문자 발송. 발송 규칙은 admin/sens_demo.py 더미에서 검증한 것과 같다.

공급자는 SMS_PROVIDER 로 고른다: solapi(기본) | sens(네이버 클라우드).
SMS_DRY_RUN=true(기본)이면 외부를 호출하지 않고 로그만 남긴다.
"""

import base64
import hashlib
import hmac
import time
import uuid
from datetime import datetime, timezone
from datetime import time as dtime

import httpx

from app.core.settings import Settings
from app.services.grades import KST, grade_of
from app.stores.members import MemberStore
from app.stores.sms_logs import SmsLogStore

SMS_LIMIT_BYTES = 90
NIGHT_START, NIGHT_END = dtime(21, 0), dtime(8, 0)  # 광고성 문자 야간 발송 제한
CHUNK = 100  # SENS 1회 호출당 수신자 수 상한 (콘솔 문서로 현재 값 재확인 필요)
BASE = "https://sens.apigw.ntruss.com"
SOLAPI_BASE = "https://api.solapi.com"
SOLAPI_CHUNK = 1000  # 솔라피 send-many 1회 호출 상한은 10,000건이지만 여유를 둔다


def solapi_auth(api_key: str, api_secret: str, date: str, salt: str) -> str:
    """솔라피 HMAC-SHA256 인증 헤더 (공식 SDK authenticator 와 같은 규칙)."""
    sig = hmac.new(api_secret.encode(), (date + salt).encode(), hashlib.sha256).hexdigest()
    return f"HMAC-SHA256 ApiKey={api_key}, Date={date}, salt={salt}, signature={sig}"


class SmsRejected(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def msg_bytes(text: str) -> int:
    return sum(1 if ord(ch) < 128 else 2 for ch in text)


def msg_type(text: str) -> str:
    return "SMS" if msg_bytes(text) <= SMS_LIMIT_BYTES else "LMS"


def is_night(now: dtime) -> bool:
    return now >= NIGHT_START or now < NIGHT_END


def signature(secret: str, method: str, uri: str, timestamp: str, access_key: str) -> str:
    message = f"{method} {uri}\n{timestamp}\n{access_key}".encode()
    return base64.b64encode(hmac.new(secret.encode(), message, hashlib.sha256).digest()).decode()


class SmsService:
    def __init__(self, settings: Settings, members: MemberStore, logs: SmsLogStore, clock=None, http=None):
        self.s, self.members, self.logs = settings, members, logs
        self.clock = clock or (lambda: datetime.now(KST))
        self.http = http  # 테스트에서 가짜 httpx.Client 주입

    def _configured(self) -> bool:
        s = self.s
        if s.sms_provider == "sens":
            return bool(s.sens_service_id and s.sens_access_key and s.sens_secret_key
                        and s.sens_sender_number and s.sens_opt_out_number)
        return bool(s.solapi_api_key and s.solapi_api_secret and s.solapi_sender_number and s.sens_opt_out_number)

    def build(self, body: str) -> str:
        number = self.s.sens_opt_out_number or "080-000-0000"
        return f"(광고){self.s.store_name}\n{body.strip()}\n무료수신거부 {number}"

    def targets(self, grades: list[str]) -> list[dict]:
        today = self.clock().date()
        rule = {"repeat": self.s.grade_repeat_visits, "regular": self.s.grade_regular_visits,
                "dormant": self.s.grade_dormant_days}
        return [m for m in self.members.all()
                if m["phone"] and m["marketing_consent"] and not m["opted_out"]
                and grade_of(m, today, **rule) in grades]

    def usage(self) -> dict:
        month = self.clock().strftime("%Y-%m")
        used = self.logs.usage(month)
        return {"month": month, "used": used,
                "limit": {"SMS": self.s.sms_monthly_limit, "LMS": self.s.lms_monthly_limit}}

    def preview(self, grades: list[str], body: str) -> dict:
        text = self.build(body)
        kind = msg_type(text)
        usage = self.usage()
        remaining = usage["limit"][kind] - usage["used"][kind]
        targets = self.targets(grades)
        problems = []
        if not body.strip():
            problems.append("본문이 비어 있습니다.")
        if not targets:
            problems.append("발송 대상이 없습니다. (휴대폰 번호 입력 + 수신 동의 + 수신거부 아님)")
        if is_night(self.clock().time()):
            problems.append("야간(21시~08시)에는 광고성 문자를 보낼 수 없습니다.")
        if len(targets) > remaining:
            problems.append(f"이번 달 {kind} 무료 잔여 {max(remaining, 0)}건보다 대상({len(targets)}명)이 많습니다.")
        if not self.s.sms_dry_run and not self._configured():
            if self.s.sms_provider == "sens":
                problems.append("SENS 설정(서비스 ID·키·발신번호·수신거부 번호)이 비어 있습니다.")
            else:
                problems.append("솔라피 설정(API 키·시크릿·발신번호·수신거부 번호)이 비어 있습니다.")
        return {"type": kind, "bytes": msg_bytes(text), "content": text, "targets": len(targets),
                "remaining": remaining, "problems": problems, "ok": not problems, "dry_run": self.s.sms_dry_run}

    def send(self, grades: list[str], body: str) -> dict:
        plan = self.preview(grades, body)
        if not plan["ok"]:
            raise SmsRejected(plan["problems"])
        targets = self.targets(grades)
        month, kind, text = self.clock().strftime("%Y-%m"), plan["type"], plan["content"]
        if self.s.sms_dry_run:
            rid = f"dryrun-{uuid.uuid4().hex[:12]}"
            self.logs.add(month, kind, text, len(targets), "dry_run", rid)
            return {"request_id": rid, "count": len(targets), "dry_run": True}
        sent, ids = 0, []
        solapi = self.s.sms_provider != "sens"
        call, size, label = (self._call_solapi, SOLAPI_CHUNK, "솔라피") if solapi else (self._call_sens, CHUNK, "SENS")
        for i in range(0, len(targets), size):
            chunk = targets[i:i + size]
            try:
                rid = call(kind, text, [m["phone"] for m in chunk])
            except Exception as e:  # 한 묶음이 실패해도 앞서 보낸 것은 기록을 남긴다
                self.logs.add(month, kind, text, len(chunk), "failed", error=str(e)[:300])
                raise SmsRejected([f"{label} 발송 실패: {e}"]) from e
            self.logs.add(month, kind, text, len(chunk), "sent", rid)
            sent += len(chunk)
            ids.append(rid)
        return {"request_id": ",".join(ids), "count": sent, "dry_run": False}

    def _call_sens(self, kind: str, text: str, phones: list[str]) -> str:
        s = self.s
        uri = f"/sms/v2/services/{s.sens_service_id}/messages"
        ts = str(int(time.time() * 1000))
        headers = {"Content-Type": "application/json; charset=utf-8", "x-ncp-apigw-timestamp": ts,
                   "x-ncp-iam-access-key": s.sens_access_key,
                   "x-ncp-apigw-signature-v2": signature(s.sens_secret_key, "POST", uri, ts, s.sens_access_key)}
        payload = {"type": kind, "contentType": "AD", "countryCode": "82",
                   "from": s.sens_sender_number.replace("-", ""), "content": text,
                   "messages": [{"to": p.replace("-", "")} for p in phones]}
        if kind == "LMS":
            payload["subject"] = f"(광고){s.store_name}"[:40]
        client = self.http or httpx.Client(timeout=10)
        r = client.post(BASE + uri, json=payload, headers=headers)
        if r.status_code != 202:
            raise RuntimeError(f"HTTP {r.status_code} {r.text[:200]}")
        return r.json().get("requestId", "")

    def _call_solapi(self, kind: str, text: str, phones: list[str]) -> str:
        """send-many/detail 로 한 묶음을 보내고 그룹 ID 를 돌려준다."""
        s = self.s
        date = datetime.now(timezone.utc).isoformat(timespec="seconds")
        headers = {"Authorization": solapi_auth(s.solapi_api_key, s.solapi_api_secret, date, uuid.uuid4().hex),
                   "Content-Type": "application/json"}
        sender = s.solapi_sender_number.replace("-", "")
        messages = []
        for p in phones:
            m = {"to": p.replace("-", ""), "from": sender, "text": text, "type": kind}
            if kind == "LMS":
                m["subject"] = f"(광고){s.store_name}"[:40]
            messages.append(m)
        client = self.http or httpx.Client(timeout=10)
        r = client.post(SOLAPI_BASE + "/messages/v4/send-many/detail", json={"messages": messages}, headers=headers)
        if r.status_code >= 400:
            try:
                err = r.json()
                raise RuntimeError(f"{err.get('errorCode', r.status_code)} {err.get('errorMessage', '')}".strip())
            except ValueError:
                raise RuntimeError(f"HTTP {r.status_code} {r.text[:200]}") from None
        data = r.json()
        count = (data.get("groupInfo") or {}).get("count") or {}
        if phones and count.get("total") and count.get("total") == count.get("registeredFailed"):
            raise RuntimeError(f"모든 메시지 접수 실패: {str(data.get('failedMessageList'))[:200]}")
        return (data.get("groupInfo") or {}).get("groupId") or data.get("groupId", "")
