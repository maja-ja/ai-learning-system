import os
import json
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from supabase import create_client, Client

app = FastAPI(title="AI 教育工作站 - Cloud Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://etymon-decoder.com", 
        "null", # 允許直接從電腦打開 HTML 檔案呼叫
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔑 設定金鑰 (建議改用環境變數)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyC8AWQCEpA37bpXc60__JObYgjg9ROt-eg")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://qbplbwjietrapboriarn.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_GuY10yKKTqPyypbcwW1vUQ_6mp9Suly")
AI_FEATURE_LOCKED = os.getenv("LOCK_AI_FEATURES", "true").strip().lower() in {"1", "true", "yes", "on"}
# 初始化 Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 核心欄位定義
CORE_COLS =[
    'word', 'category', 'roots', 'breakdown', 'definition', 
    'meaning', 'native_vibe', 'example', 'synonym_nuance', 
    'usage_warning', 'memory_hook', 'phonetic'
]

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

class KnowledgeCard(BaseModel):
    word: str = Field(description="核心概念名稱")
    category: str = Field(description="領域分類")
    roots: str = Field(description="底層邏輯或公式")
    breakdown: str = Field(description="結構拆解")
    definition: str = Field(description="直覺定義")
    meaning: str = Field(description="本質意義")
    native_vibe: str = Field(description="專家心法")
    example: str = Field(description="應用實例")
    synonym_nuance: str = Field(description="相似辨析")
    usage_warning: str = Field(description="使用誤區")
    memory_hook: str = Field(description="記憶金句")
    phonetic: str = Field(description="音標或詞源")

@app.post("/decode")
async def decode_note(note: NoteInput):
    if AI_FEATURE_LOCKED:
        raise HTTPException(status_code=503, detail="AI feature is temporarily locked for optimization")

    if not note.text.strip():
        raise HTTPException(status_code=400, detail="Empty content")

    try:
        # 1. AI 解碼
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"將此筆記轉化為深度知識卡：\n{note.text}"
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=KnowledgeCard,
            )
        )
        parsed_data = json.loads(response.text)

        # 2. 🔥 寫入 Supabase (雲端)
        # upsert: 有就更新，沒有就新增 (依據 word 欄位)
        supabase.table("knowledge").upsert(parsed_data, on_conflict="word").execute()

        return {"status": "success", "data": parsed_data}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/notes")
def list_notes():
    try:
        result = supabase.table("notes").select("id,title,content,tags").order("id", desc=True).execute()
        rows = result.data or []
        data = [{"id": n["id"], "title": n.get("title", ""), "content": n.get("content", ""), "tags": n.get("tags", ""), "created_at": n.get("created_at"), "updated_at": n.get("updated_at")} for n in rows]
        return {"data": data}
    except Exception as e:
        print(f"List notes error: {e}")
        raise HTTPException(status_code=500, detail="Could not load notes")

@app.post("/notes")
def create_note(note: RawNoteCreate):
    try:
        payload = {
            "title": note.title or "",
            "content": note.content or "",
            "tags": note.tags or ""
        }
        result = supabase.table("notes").insert(payload).execute()
        rows = result.data or []
        if not rows:
            raise HTTPException(status_code=500, detail="Create note returned empty result")
        created = rows[0]
        return {"data": {"id": created.get("id"), "title": created.get("title", ""), "content": created.get("content", ""), "tags": created.get("tags", ""), "created_at": created.get("created_at"), "updated_at": created.get("updated_at")}}
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

        result = supabase.table("notes").update(data).eq("id", note_id).execute()
        rows = result.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="Note not found")
        updated = rows[0]
        return {"data": {"id": updated.get("id"), "title": updated.get("title", ""), "content": updated.get("content", ""), "tags": updated.get("tags", ""), "created_at": updated.get("created_at"), "updated_at": updated.get("updated_at")}}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Update note error: {e}")
        raise HTTPException(status_code=500, detail="Could not update note")

@app.delete("/notes/{note_id}")
def delete_note(note_id: int):
    try:
        supabase.table("notes").delete().eq("id", note_id).execute()
        return {"data": {"id": note_id}}
    except Exception as e:
        print(f"Delete note error: {e}")
        raise HTTPException(status_code=500, detail="Could not delete note")

@app.get("/health")
def health_check():
    return {"status": "ok", "db": "Supabase"}