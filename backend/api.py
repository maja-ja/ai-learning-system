import os
import json
import time
import hmac
import hashlib
import base64
from pathlib import Path
from typing import Optional, List, Tuple, Any, Dict

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from . import ai_decode
from . import decoder_batch
from . import handout_gen
from . import handout_html
from . import knowledge_export
from . import database as db
from .model_router import resolve_task_config
from .schemas import (
    LearnerContextUpsertBody,
    AhaHookRecommendQuery,
    AhaEventIngestBody,
    AhaEventBatchIngestBody,
    MaintenanceBackfillVariantBody,
    ClickEventsBatchBody,
)

app = FastAPI(title="AI 教育工作站 - Cloud Core")

_cors_allow_custom = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip()
_cors_origins = [
    "https://etymon-decoder.com",
    "https://www.etymon-decoder.com",
    "https://api.etymon-decoder.com",
    "null",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]
for _o in os.getenv("CORS_EXTRA_ORIGINS", "").split(","):
    _o = _o.strip()
    if _o and _o not in _cors_origins:
        _cors_origins.append(_o)

# Cloudflare / etymon-decoder.com：允許任意子網域（如 Pages 預覽、Tunnel）
_rx_ety = os.getenv(
    "CORS_ETYMON_REGEX",
    r"^https://([a-z0-9-]+\.)*etymon-decoder\.com$",
).strip()
# 本機開發任意埠
_rx_local = r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$"

_cors_parts: List[str] = []
if _cors_allow_custom:
    _cors_parts.append(f"({_cors_allow_custom})")
if os.getenv("CORS_RELAX_LOCAL", "true").strip().lower() in (
    "1", "true", "yes", "on",
):
    _cors_parts.append(f"({_rx_local})")
if os.getenv("CORS_INCLUDE_ETYMON_REGEX", "true").strip().lower() in (
    "1", "true", "yes", "on",
):
    _cors_parts.append(f"({_rx_ety})")

_cors_regex = "|".join(_cors_parts) if _cors_parts else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 預設開放 AI，設 LOCK_AI_FEATURES=true 可關閉（與舊 Streamlit 行為一致）
AI_FEATURE_LOCKED = os.getenv("LOCK_AI_FEATURES", "false").strip().lower() in {
    "1", "true", "yes", "on",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
SPA_DIST = REPO_ROOT / "web" / "dist"
SERVE_WEB_DIST = os.getenv("SERVE_WEB_DIST", "").strip().lower() in (
    "1", "true", "yes", "on",
)
KNOWLEDGE_FS_ROOT = REPO_ROOT / "知識"


def _resolve_roots_json_path() -> Path:
    """Prefer knowledge/assets locations, keep legacy Streamlit path as fallback."""
    candidates = [
        REPO_ROOT / "知識" / "語言" / "英語" / "字根" / "hs_english_roots.json",
        REPO_ROOT / "assets" / "hs_english_roots.json",
        REPO_ROOT / "streamlit_app" / "data" / "hs_english_roots.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]


ROOTS_JSON_PATH = _resolve_roots_json_path()
EXAM_TOKEN_SECRET = os.getenv("EXAM_TOKEN_SECRET", "dev-exam-secret-change-me")
APP_PASSWORD = os.getenv("APP_PASSWORD", "abcd")
exam_bearer = HTTPBearer(auto_error=False)
maintenance_bearer = HTTPBearer(auto_error=False)
MAINTENANCE_TOKEN = os.getenv("MAINTENANCE_TOKEN", "").strip()

# 核心欄位定義
CORE_COLS = [
    'word', 'category', 'roots', 'breakdown', 'definition',
    'meaning', 'native_vibe', 'example', 'synonym_nuance',
    'usage_warning', 'memory_hook', 'phonetic'
]


def _create_exam_token() -> str:
    exp = int(time.time()) + 86400 * 7
    exp_s = str(exp)
    mac = hmac.new(
        EXAM_TOKEN_SECRET.encode(), exp_s.encode(), hashlib.sha256
    ).hexdigest()
    return f"{exp_s}.{mac}"


def _verify_exam_token(token: str) -> bool:
    try:
        exp_s, mac = token.split(".", 1)
        exp = int(exp_s)
        if time.time() > exp:
            return False
        expect = hmac.new(
            EXAM_TOKEN_SECRET.encode(), exp_s.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expect, mac)
    except (ValueError, AttributeError):
        return False


def require_exam_auth(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(exam_bearer),
) -> None:
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="需要學測區憑證")
    if not _verify_exam_token(cred.credentials):
        raise HTTPException(status_code=401, detail="憑證無效或已過期")


def require_maintenance_auth(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(maintenance_bearer),
) -> None:
    if not MAINTENANCE_TOKEN:
        raise HTTPException(status_code=503, detail="維運功能未啟用（缺少 MAINTENANCE_TOKEN）")
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="需要維運權杖")
    if cred.credentials != MAINTENANCE_TOKEN:
        raise HTTPException(status_code=401, detail="維運權杖無效")


def _request_is_https(request: Request) -> bool:
    xf = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if xf == "https":
        return True
    if xf == "http":
        return False
    return request.url.scheme == "https"


def _exam_edit_allowed(request: Request) -> bool:
    if os.getenv("EXAM_ALLOW_HTTPS_EDIT", "").strip().lower() in (
        "1", "true", "yes", "on",
    ):
        return True
    return not _request_is_https(request)


def _persist_knowledge_row(parsed_data: dict) -> None:
    """寫入本機 SQLite 知識庫。"""
    db.knowledge_upsert(parsed_data)


def _safe_note_path(subject: str, chapter: str, unit: str) -> Path:
    for part in (subject, chapter, unit):
        if not part or ".." in part or "/" in part or "\\" in part:
            raise HTTPException(status_code=400, detail="路徑不合法")
    base = KNOWLEDGE_FS_ROOT.resolve()
    p = (KNOWLEDGE_FS_ROOT / subject / chapter / unit / "note.md").resolve()
    if not str(p).startswith(str(base)):
        raise HTTPException(status_code=400, detail="路徑不合法")
    return p


class NoteInput(BaseModel):
    text: str

class RawNoteCreate(BaseModel):
    title: Optional[str] = ""
    content: Optional[str] = ""
    tags: Optional[str] = ""

class RawNoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None


class ExamPasswordBody(BaseModel):
    password: str


class ExamCreateNoteBody(BaseModel):
    subject: str
    chapter: str
    unit: str
    content: str = ""


class BatchDecodeBody(BaseModel):
    words: List[str] = Field(..., max_length=30)
    primary_category: str
    aux_categories: List[str] = Field(default_factory=list)
    force_refresh: bool = False
    delay_sec: float = Field(0.5, ge=0, le=3)


class SuggestTopicsBody(BaseModel):
    primary_category: str
    aux_categories: List[str] = Field(default_factory=list)
    count: int = Field(5, ge=1, le=15)


class HandoutGenerateBody(BaseModel):
    manual_input: str = ""
    instruction: str = ""
    image_base64: Optional[str] = None


class HandoutHtmlBody(BaseModel):
    title: str = "專題講義"
    markdown: str
    image_base64: Optional[str] = None
    img_width_percent: int = Field(80, ge=20, le=100)


@app.post("/decode")
async def decode_note(note: NoteInput):
    if AI_FEATURE_LOCKED:
        raise HTTPException(status_code=503, detail="AI feature is temporarily locked for optimization")

    if not note.text.strip():
        raise HTTPException(status_code=400, detail="Empty content")

    try:
        parsed_data, ai_used = ai_decode.decode_to_knowledge_card(note.text)
        _persist_knowledge_row(parsed_data)

        return {
            "status": "success",
            "data": parsed_data,
            "saved_to": "local",
            "ai_provider": ai_used,
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/notes")
def list_notes():
    try:
        rows = db.notes_list()
        return {"data": rows}
    except Exception as e:
        print(f"List notes error: {e}")
        raise HTTPException(status_code=500, detail="Could not load notes")

@app.post("/notes")
def create_note(note: RawNoteCreate):
    try:
        created = db.notes_create(
            note.title or "",
            note.content or "",
            note.tags or "",
        )
        if not created:
            raise HTTPException(status_code=500, detail="Create note returned empty result")
        return {"data": created}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Create note error: {e}")
        raise HTTPException(status_code=500, detail="Could not create note")

@app.put("/notes/{note_id}")
def update_note(note_id: int, note: RawNoteUpdate):
    try:
        data = {}
        if note.title is not None:
            data["title"] = note.title
        if note.content is not None:
            data["content"] = note.content
        if note.tags is not None:
            data["tags"] = note.tags

        updated = db.notes_update(note_id, data)
        if not updated:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"data": updated}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Update note error: {e}")
        raise HTTPException(status_code=500, detail="Could not update note")

@app.delete("/notes/{note_id}")
def delete_note(note_id: int):
    try:
        db.notes_delete(note_id)
        return {"data": {"id": note_id}}
    except Exception as e:
        print(f"Delete note error: {e}")
        raise HTTPException(status_code=500, detail="Could not delete note")


def _merge_knowledge_rows() -> Tuple[List[Any], str]:
    """本機 SQLite 知識庫讀取。"""
    try:
        rows = db.knowledge_list()
        return rows, "local"
    except Exception as e:
        print(f"Knowledge read error: {e}")
        return [], "local"


def _tag_match(tags: List[str], value: str) -> bool:
    if not tags:
        return True
    if not value:
        return False
    return value in tags


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


@app.get("/api/knowledge")
def api_list_knowledge():
    try:
        rows, source = _merge_knowledge_rows()
        return {"data": rows, "meta": {"source": source}}
    except Exception as e:
        print(f"Knowledge list error: {e}")
        raise HTTPException(status_code=500, detail="無法載入知識庫")


@app.get("/api/roots")
def api_list_roots():
    if not ROOTS_JSON_PATH.is_file():
        return {"data": []}
    try:
        with open(ROOTS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {"data": data if isinstance(data, list) else []}
    except Exception as e:
        print(f"Roots read error: {e}")
        raise HTTPException(status_code=500, detail="無法讀取字根資料")


@app.post("/api/learner/context")
def api_upsert_learner_context(body: LearnerContextUpsertBody):
    payload = body.model_dump()
    try:
        result = db.learner_context_upsert(payload)
        return {"data": result}
    except Exception as e:
        print(f"Learner context upsert error: {e}")
        raise HTTPException(status_code=500, detail="無法儲存學習者背景")


@app.get("/api/aha/hooks/recommend")
def api_recommend_aha_hooks(
    tenant_id: str,
    profile_id: str,
    topic_key: str,
    limit: int = 5,
):
    q = AhaHookRecommendQuery(
        tenant_id=tenant_id,
        profile_id=profile_id,
        topic_key=topic_key,
        limit=limit,
    )
    try:
        context = (
            db.learner_context_get(q.tenant_id, q.profile_id)
            or {"age_band": "", "region_code": ""}
        )
        age_band = str(context.get("age_band", "") or "")
        region_code = str(context.get("region_code", "") or "")

        hooks = db.aha_hooks_get_active(q.tenant_id, q.topic_key)
        filtered: List[Dict[str, Any]] = []
        for h in hooks:
            age_tags = [str(x) for x in (h.get("age_tags") or [])]
            region_tags = [str(x) for x in (h.get("region_tags") or [])]
            if _tag_match(age_tags, age_band) and _tag_match(region_tags, region_code):
                filtered.append(h)
        if not filtered:
            filtered = hooks

        perf_rows = db.aha_hook_effectiveness_get(
            q.tenant_id,
            q.topic_key,
            age_band if age_band else "unknown",
            region_code if region_code else "unknown",
        )
        perf_map = {
            f"{r.get('hook_type')}::{r.get('hook_variant_id')}": r for r in perf_rows
        }

        ranked = []
        for h in filtered:
            key = f"{h.get('hook_type')}::{h.get('hook_variant_id')}"
            perf = perf_map.get(key, {})
            impressions = max(int(perf.get("impressions") or 0), 0)
            aha_reports = max(int(perf.get("aha_reports") or 0), 0)
            aha_rate = (aha_reports / impressions) if impressions > 0 else 0.0
            lift = _to_float(perf.get("lift"), 0.0)
            tta = _to_float(perf.get("time_to_aha"), 0.0)
            speed_score = 0.5 if tta <= 0 else 1.0 / (1.0 + tta / 60000.0)
            score = (aha_rate * 0.6) + (lift * 0.3) + (speed_score * 0.1)
            ranked.append(
                {
                    **h,
                    "score": round(score, 4),
                    "metrics": {
                        "aha_rate": round(aha_rate, 4),
                        "lift": round(lift, 4),
                        "time_to_aha_ms": int(tta) if tta > 0 else None,
                    },
                }
            )
        ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
        return {
            "data": ranked[: q.limit],
            "meta": {
                "age_band": age_band or "unknown",
                "region_code": region_code or "unknown",
                "pool_size": len(ranked),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Aha hook recommendation error: {e}")
        raise HTTPException(status_code=500, detail="無法推薦 Aha hook")


@app.post("/api/aha/events")
def api_ingest_aha_event(body: AhaEventIngestBody):
    payload = body.model_dump(exclude_none=True)
    try:
        result = db.aha_event_insert(payload)
        return {"data": result}
    except Exception as e:
        print(f"Aha event insert error: {e}")
        raise HTTPException(status_code=500, detail="無法寫入 Aha 事件")


@app.post("/api/aha/events/batch")
def api_ingest_aha_events_batch(body: AhaEventBatchIngestBody):
    events = [e.model_dump(exclude_none=True) for e in body.events]
    if not events:
        return {"inserted": 0, "data": []}
    try:
        rows = db.aha_events_insert_batch(events)
        return {"inserted": len(rows), "data": rows}
    except Exception as e:
        print(f"Aha events batch insert error: {e}")
        raise HTTPException(status_code=500, detail="批次寫入 Aha 事件失敗")


@app.get("/api/admin/db/status", dependencies=[Depends(require_maintenance_auth)])
def api_admin_db_status():
    status = db.db_status_snapshot()
    status["tables"] = {}
    for table_name in ("learner_contexts", "aha_hooks", "learning_attempts", "aha_events"):
        try:
            status["tables"][table_name] = db.table_count(table_name)
        except Exception as ex:
            status["tables"][table_name] = f"error: {ex}"
    return status


@app.post("/api/admin/aha/events/backfill-variant", dependencies=[Depends(require_maintenance_auth)])
def api_admin_backfill_hook_variant(body: MaintenanceBackfillVariantBody):
    try:
        missing_rows = db.aha_events_needing_variant(body.limit, body.tenant_id)
        if not missing_rows:
            return {"scanned": 0, "candidates": 0, "updated": 0, "dry_run": body.dry_run}

        hook_ids = sorted({str(r.get("hook_id")) for r in missing_rows if r.get("hook_id")})
        hooks_rows = db.aha_hooks_get_by_ids(hook_ids)
        hook_map = {
            str(r.get("id")): str(r.get("hook_variant_id") or "").strip()
            for r in hooks_rows
        }
        candidates = []
        for ev in missing_rows:
            hv = hook_map.get(str(ev.get("hook_id")), "")
            if hv:
                candidates.append({"event_id": ev.get("id"), "hook_variant_id": hv})

        if body.dry_run:
            return {
                "scanned": len(missing_rows),
                "candidates": len(candidates),
                "updated": 0,
                "dry_run": True,
                "sample": candidates[:20],
            }

        updated = 0
        for c in candidates:
            db.aha_event_update_variant(c["event_id"], c["hook_variant_id"])
            updated += 1
        return {
            "scanned": len(missing_rows),
            "candidates": len(candidates),
            "updated": updated,
            "dry_run": False,
        }
    except Exception as e:
        print(f"Admin backfill hook variant error: {e}")
        raise HTTPException(status_code=500, detail="回填 hook_variant_id 失敗")


@app.post("/api/exam/login")
def api_exam_login(request: Request, body: ExamPasswordBody):
    if body.password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="密碼錯誤")
    return {
        "token": _create_exam_token(),
        "expires_in_days": 7,
        "exam_edit_allowed": _exam_edit_allowed(request),
    }


@app.get("/api/exam/tree", dependencies=[Depends(require_exam_auth)])
def api_exam_tree(request: Request):
    if not KNOWLEDGE_FS_ROOT.is_dir():
        return {"subjects": [], "exam_edit_allowed": _exam_edit_allowed(request)}
    subjects: List[dict] = []
    for sub in sorted(KNOWLEDGE_FS_ROOT.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue
        chapters: List[dict] = []
        for ch in sorted(sub.iterdir()):
            if not ch.is_dir():
                continue
            units = []
            for u in sorted(ch.iterdir()):
                if u.is_dir() and (u / "note.md").is_file():
                    units.append({"name": u.name})
            if units:
                chapters.append({"name": ch.name, "units": units})
        if chapters:
            subjects.append({"name": sub.name, "chapters": chapters})
    return {"subjects": subjects, "exam_edit_allowed": _exam_edit_allowed(request)}


@app.get("/api/exam/note", dependencies=[Depends(require_exam_auth)])
def api_exam_get_note(
    subject: str,
    chapter: str,
    unit: str,
):
    path = _safe_note_path(subject, chapter, unit)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="找不到 note.md")
    return {"content": path.read_text(encoding="utf-8")}


@app.post("/api/exam/note", dependencies=[Depends(require_exam_auth)])
def api_exam_save_note(
    request: Request,
    body: ExamCreateNoteBody,
):
    if not _exam_edit_allowed(request):
        raise HTTPException(
            status_code=403,
            detail="公開站（HTTPS）僅供瀏覽；請在本機 http://127.0.0.1 編輯，或設定 EXAM_ALLOW_HTTPS_EDIT=true",
        )
    path = _safe_note_path(body.subject, body.chapter, body.unit)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content or "", encoding="utf-8")
    return {"ok": True, "path": str(path.relative_to(REPO_ROOT))}


@app.get("/api/exam/search", dependencies=[Depends(require_exam_auth)])
def api_exam_search(
    q: str,
    subject: Optional[str] = None,
):
    query = (q or "").strip().lower()
    if not query:
        return {"results": []}
    if not KNOWLEDGE_FS_ROOT.is_dir():
        return {"results": []}
    results = []
    for sub in KNOWLEDGE_FS_ROOT.iterdir():
        if not sub.is_dir() or sub.name.startswith("."):
            continue
        if subject and sub.name != subject:
            continue
        for ch in sub.iterdir():
            if not ch.is_dir():
                continue
            for u in ch.iterdir():
                if not u.is_dir():
                    continue
                note = u / "note.md"
                if not note.is_file():
                    continue
                try:
                    text = note.read_text(encoding="utf-8")
                except OSError:
                    continue
                tl = text.lower()
                un = u.name.lower()
                if query in tl or query in un:
                    results.append(
                        {
                            "subject": sub.name,
                            "chapter": ch.name,
                            "unit": u.name,
                            "snippet": text[:200].replace("\n", " "),
                        }
                    )
    return {"results": results[:80]}


@app.get("/api/knowledge/export")
def api_export_knowledge_zip():
    rows, _ = _merge_knowledge_rows()
    data = knowledge_export.knowledge_rows_to_zip_bytes(rows)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="knowledge_markdown.zip"'
        },
    )


@app.post("/api/decode/batch")
def api_batch_decode(body: BatchDecodeBody):
    if AI_FEATURE_LOCKED:
        raise HTTPException(
            status_code=503,
            detail="AI feature is temporarily locked for optimization",
        )
    raw = [w.strip() for w in body.words if str(w).strip()][:30]
    if not raw:
        raise HTTPException(status_code=400, detail="請提供至少一個主題")
    merged, _ = _merge_knowledge_rows()
    existing = {
        str(r.get("word", "")).lower().strip()
        for r in merged
        if r.get("word")
    }
    saved: List[dict] = []
    skipped: List[str] = []
    errors: List[dict] = []
    for i, word in enumerate(raw):
        key = word.lower()
        if key in existing and not body.force_refresh:
            skipped.append(word)
            continue
        try:
            row = decoder_batch.decode_interdisciplinary(
                word, body.primary_category, body.aux_categories
            )
            if not row:
                errors.append({"word": word, "detail": "模型未回傳有效 JSON"})
                continue
            _persist_knowledge_row(row)
            saved.append({"word": word, "saved_to": "local"})
            existing.add(key)
        except Exception as e:
            errors.append({"word": word, "detail": str(e)})
        if i < len(raw) - 1 and body.delay_sec > 0:
            time.sleep(body.delay_sec)
    return {"saved": saved, "skipped": skipped, "errors": errors}


@app.post("/api/decode/suggest-topics")
def api_suggest_topics(body: SuggestTopicsBody):
    if AI_FEATURE_LOCKED:
        raise HTTPException(status_code=503, detail="AI feature is locked")
    try:
        text = decoder_batch.suggest_topics(
            body.primary_category, body.aux_categories, body.count
        )
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return {"lines": lines[: body.count]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/handout/generate")
def api_handout_generate(body: HandoutGenerateBody):
    if AI_FEATURE_LOCKED:
        raise HTTPException(status_code=503, detail="AI feature is locked")
    img_bytes = None
    if body.image_base64:
        try:
            raw = body.image_base64.split(",", 1)[-1]
            img_bytes = base64.b64decode(raw)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"圖片解碼失敗: {e}")
    try:
        md = handout_gen.generate_handout_markdown(
            body.manual_input or "",
            body.instruction or "",
            img_bytes,
        )
        return {"markdown": md}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/handout/preview-html")
def api_handout_preview_html(body: HandoutHtmlBody):
    img = body.image_base64 or ""
    if img and "," in img:
        img = img.split(",", 1)[-1]
    html = handout_html.build_printable_html(
        body.title or "專題講義",
        body.markdown or "",
        img_b64=img,
        img_width_percent=body.img_width_percent,
        auto_download_pdf=False,
    )
    return Response(content=html, media_type="text/html; charset=utf-8")


# ---------------------------------------------------------------------------
# 點擊序列收集 & Markov 預測
# ---------------------------------------------------------------------------

@app.post("/api/tracking/clicks")
def api_tracking_clicks(body: ClickEventsBatchBody):
    """接收前端送來的點擊事件批次，寫入 click_events 表。"""
    events = [e.model_dump() for e in body.events]
    saved = db.click_events_insert_batch(body.session_id, events)
    return {"ok": True, "saved": saved}


@app.get("/api/tracking/predict")
def api_tracking_predict(session_id: str, limit: int = 5):
    """
    依照 session 最近點擊序列，用一階 Markov chain 預測最可能的下一個動作。
    若 session 無歷史，回傳全站熱門動作。
    """
    limit = max(1, min(limit, 20))
    recent = db.click_recent_actions(session_id, limit=8)
    predictions = db.click_markov_predict(recent, limit=limit)
    return {
        "session_id": session_id,
        "recent_actions": recent,
        "predictions": predictions,
    }


@app.get("/")
def root():
    """SERVE_WEB_DIST=1 且已建置 web/dist 時，根路徑回傳 SPA。"""
    if SERVE_WEB_DIST and (SPA_DIST / "index.html").is_file():
        return FileResponse(SPA_DIST / "index.html")
    return {
        "service": "AI 教育工作站 API",
        "hint": "瀏覽器請開前端（本機通常為 http://127.0.0.1:5173 ）；單埠上線請 SERVE_WEB_DIST=1 並 npm run build",
        "health": "/health",
        "openapi_docs": "/docs",
        "openapi_json": "/openapi.json",
        "examples": {
            "knowledge": "GET /api/knowledge",
            "decode": "POST /decode",
        },
    }


@app.get("/api")
def api_index():
    return {
        "message": "API 路徑需含完整資源名稱",
        "try": ["/api/knowledge", "/api/roots", "/health"],
    }


@app.get("/health")
def health_check():
    try:
        n_local = len(db.knowledge_list())
    except Exception:
        n_local = 0
    return {
        "status": "ok",
        "supabase": False,
        "local_knowledge_rows": n_local,
        "ai_locked": AI_FEATURE_LOCKED,
        "ai_provider_config": ai_decode.resolve_ai_provider(),
        "model_routing": {
            "decode_note": resolve_task_config("decode_note", tier="quality"),
            "decode_batch": resolve_task_config("decode_batch", tier="quality"),
            "suggest_topics": resolve_task_config("suggest_topics", tier="cheap"),
            "handout_generate": resolve_task_config("handout_generate", tier="quality"),
        },
        "has_gemini_key": bool(ai_decode.GEMINI_API_KEY),
        "has_anthropic_key": bool(ai_decode.ANTHROPIC_API_KEY),
    }


# --- 單埠提供 Vite 建置結果（任意機器 + Tunnel 指到 :8000 即可）---
_spa_index = SPA_DIST / "index.html"
if SERVE_WEB_DIST and _spa_index.is_file():
    _assets = SPA_DIST / "assets"
    if _assets.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_assets)),
            name="spa_assets",
        )

    @app.get("/{full_path:path}")
    def spa_history_fallback(full_path: str):
        p = SPA_DIST / full_path
        if p.is_file():
            return FileResponse(p)
        return FileResponse(_spa_index)
