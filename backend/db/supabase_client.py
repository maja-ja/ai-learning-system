"""Supabase REST 客戶端（urllib，不依賴第三方 SDK）。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from urllib import error, parse, request


def supabase_enabled() -> bool:
    return bool(
        os.getenv("SUPABASE_URL", "").strip()
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )


def _headers(*, prefer: Optional[str] = None) -> Dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    headers = {
        "Content-Type": "application/json",
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def supabase_request(
    method: str,
    path: str,
    *,
    query: Optional[Dict[str, Any]] = None,
    payload: Optional[Any] = None,
    prefer: Optional[str] = None,
) -> Any:
    if not supabase_enabled():
        raise RuntimeError("Supabase is not configured")

    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    url = f"{base}/rest/v1/{path.lstrip('/')}"
    if query:
        params = {k: v for k, v in query.items() if v is not None and v != ""}
        if params:
            url = f"{url}?{parse.urlencode(params, doseq=True, safe='(),.*')}"

    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers=_headers(prefer=prefer), method=method)
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Supabase {method} {path} failed: {detail or exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Supabase {method} {path} failed: {exc}") from exc


def supabase_select(
    table: str,
    *,
    select: str = "*",
    filters: Optional[Dict[str, Any]] = None,
    order: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"select": select}
    if filters:
        query.update(filters)
    if order:
        query["order"] = order
    if limit is not None:
        query["limit"] = str(limit)
    rows = supabase_request("GET", table, query=query)
    return rows if isinstance(rows, list) else []


def supabase_insert(
    table: str,
    payload: Any,
    *,
    upsert: bool = False,
    on_conflict: Optional[str] = None,
) -> Any:
    prefer = "return=representation"
    if upsert:
        prefer = "return=representation,resolution=merge-duplicates"
    query = {"on_conflict": on_conflict} if on_conflict else None
    return supabase_request("POST", table, query=query, payload=payload, prefer=prefer)


def supabase_update(
    table: str,
    filters: Dict[str, Any],
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows = supabase_request(
        "PATCH", table, query={**filters, "select": "*"}, payload=payload,
        prefer="return=representation",
    )
    return rows if isinstance(rows, list) else []


def supabase_delete(table: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = supabase_request(
        "DELETE", table, query={**filters, "select": "*"}, prefer="return=representation",
    )
    return rows if isinstance(rows, list) else []


def supabase_rpc(name: str, payload: Dict[str, Any]) -> Any:
    return supabase_request("POST", f"rpc/{name}", payload=payload)
