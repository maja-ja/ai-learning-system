from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import error, request

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

membership_bearer = HTTPBearer(auto_error=False)


@dataclass
class MemberContext:
    sub: str
    profile_id: str
    tenant_id: str
    email: str
    display_name: str
    plan_key: str
    subscription_status: str
    credits_balance: int
    can_generate: bool
    exp: int


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode(data + pad)


def verify_membership_token(token: str) -> MemberContext:
    secret = os.getenv("MEMBERSHIP_TOKEN_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="會員驗證未啟用（缺少 MEMBERSHIP_TOKEN_SECRET）")

    try:
        body, sig = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="會員憑證格式錯誤") from exc

    expect = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    got = _b64url_decode(sig)
    if not hmac.compare_digest(expect, got):
        raise HTTPException(status_code=401, detail="會員憑證無效")

    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="會員憑證內容無效") from exc

    exp = int(payload.get("exp") or 0)
    if exp <= int(time.time()):
        raise HTTPException(status_code=401, detail="會員憑證已過期")

    return MemberContext(
        sub=str(payload.get("sub") or ""),
        profile_id=str(payload.get("profileId") or ""),
        tenant_id=str(payload.get("tenantId") or ""),
        email=str(payload.get("email") or ""),
        display_name=str(payload.get("displayName") or ""),
        plan_key=str(payload.get("planKey") or "free"),
        subscription_status=str(payload.get("subscriptionStatus") or "inactive"),
        credits_balance=int(payload.get("creditsBalance") or 0),
        can_generate=bool(payload.get("canGenerate")),
        exp=exp,
    )


def require_member_access(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(membership_bearer),
) -> MemberContext:
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="需要會員憑證")
    member = verify_membership_token(cred.credentials)
    if not member.profile_id or not member.tenant_id:
        raise HTTPException(status_code=403, detail="會員資料不完整")
    return member


def require_member_identity(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(membership_bearer),
) -> MemberContext:
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="需要會員憑證")
    return verify_membership_token(cred.credentials)


def require_member_generation_access(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(membership_bearer),
) -> MemberContext:
    member = require_member_identity(cred)
    live_access = has_generation_access(member)
    member.can_generate = live_access
    if not live_access:
        raise HTTPException(status_code=402, detail="請先完成付款後再生成")
    return member


def _supabase_rpc(name: str, payload: Dict[str, Any]) -> Any:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return None

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{url}/rest/v1/rpc/{name}",
        data=data,
        headers={
          "Content-Type": "application/json",
          "apikey": key,
          "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        raise HTTPException(status_code=503, detail=f"會員扣點失敗：{detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"會員扣點失敗：{exc}") from exc


def consume_generation_credit(
    member: MemberContext,
    request_id: str,
    *,
    units: int = 1,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = _supabase_rpc(
        "consume_generation_credit",
        {
            "p_tenant_id": member.tenant_id,
            "p_profile_id": member.profile_id,
            "p_request_id": request_id,
            "p_units": max(int(units), 1),
            "p_metadata": metadata or {},
        },
    )
    if result is None:
        return {
            "ok": True,
            "remaining": member.credits_balance,
            "mode": "token_only",
        }
    if not bool(result.get("ok")):
        raise HTTPException(status_code=402, detail="會員額度不足，請先充值後再生成")
    return result


def has_generation_access(member: MemberContext) -> bool:
    result = _supabase_rpc(
        "has_generation_access",
        {"p_tenant_id": member.tenant_id},
    )
    if result is None:
        return bool(member.can_generate)
    return bool(result)
