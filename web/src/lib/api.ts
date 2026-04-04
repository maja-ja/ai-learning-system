import type {
  ContributionMode,
  ExamSearchHit,
  ExamSubject,
  KnowledgeRow,
  RootEntry,
} from "../types";
import { clearMemberToken, getMemberToken, readMemberTokenClaims } from "./memberToken";
import { getUserGeminiKey } from "./userKeys";

const _base = (import.meta.env.VITE_API_BASE_URL || "").trim().replace(/\/$/, "");

/** 與 Cloudflare / 正式網域橋接時，在 .env.production 設定 VITE_API_BASE_URL */
export const API_BASE = _base;

function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return _base ? `${_base}${p}` : p;
}

const jsonHeaders = { "Content-Type": "application/json" };

function memberHeaders(): HeadersInit {
  const token = getMemberToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function aiHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const gk = getUserGeminiKey();
  if (gk) headers["X-User-Gemini-Key"] = gk;
  return headers;
}

export type KnowledgeFetchResult = {
  rows: KnowledgeRow[];
  source?: string;
};

export async function fetchKnowledge(): Promise<KnowledgeFetchResult> {
  const r = await fetch(apiUrl("/api/knowledge"));
  if (!r.ok) throw new Error("無法載入知識庫");
  const j = await r.json();
  return {
    rows: j.data ?? [],
    source: j.meta?.source as string | undefined,
  };
}

export type DecodeResult = {
  status: string;
  data: KnowledgeRow;
  saved_to?: string;
  ai_provider?: string;
  contribution_mode?: ContributionMode;
};

export async function decodeNote(
  text: string,
  contributionMode: ContributionMode
): Promise<DecodeResult> {
  const r = await fetch(apiUrl("/decode"), {
    method: "POST",
    headers: { ...jsonHeaders, ...memberHeaders(), ...aiHeaders() },
    body: JSON.stringify({
      text,
      contribution_mode: contributionMode,
    }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 || r.status === 403) {
      clearMemberToken();
    }
    const d = (j as { detail?: string }).detail;
    throw new Error(typeof d === "string" ? d : "解碼失敗");
  }
  return j as DecodeResult;
}

export type CloudNote = {
  id: number;
  title: string;
  content: string;
  tags: string;
  created_at?: string;
  updated_at?: string;
};

export async function fetchNotes(): Promise<CloudNote[]> {
  const r = await fetch(apiUrl("/notes"));
  if (!r.ok) throw new Error("無法載入筆記");
  const j = await r.json();
  return j.data ?? [];
}

export async function createNote(note: {
  title: string;
  content: string;
  tags: string;
}): Promise<CloudNote> {
  const r = await fetch(apiUrl("/notes"), {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(note),
  });
  if (!r.ok) throw new Error("建立筆記失敗");
  const j = await r.json();
  return j.data;
}

export async function deleteNote(id: number): Promise<void> {
  const r = await fetch(apiUrl(`/notes/${id}`), { method: "DELETE" });
  if (!r.ok) throw new Error("刪除失敗");
}

export async function fetchRoots(): Promise<RootEntry[]> {
  const r = await fetch(apiUrl("/api/roots"));
  if (!r.ok) throw new Error("無法載入字根");
  const j = await r.json();
  return j.data ?? [];
}

const EXAM_TOKEN_KEY = "exam_token";

export function getExamToken(): string | null {
  return localStorage.getItem(EXAM_TOKEN_KEY);
}

export function setExamToken(token: string) {
  localStorage.setItem(EXAM_TOKEN_KEY, token);
}

export function clearExamToken() {
  localStorage.removeItem(EXAM_TOKEN_KEY);
}

function examHeaders(): HeadersInit {
  const t = getExamToken();
  const h: Record<string, string> = {};
  if (t) h.Authorization = `Bearer ${t}`;
  return h;
}

export async function examLogin(password: string): Promise<{
  token: string;
  examEditAllowed: boolean;
}> {
  const r = await fetch(apiUrl("/api/exam/login"), {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ password }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "登入失敗");
  }
  const j = await r.json();
  const token = j.token as string;
  setExamToken(token);
  return {
    token,
    examEditAllowed: (j as { exam_edit_allowed?: boolean }).exam_edit_allowed !== false,
  };
}

export async function fetchExamTree(): Promise<{
  subjects: ExamSubject[];
  examEditAllowed: boolean;
}> {
  const r = await fetch(apiUrl("/api/exam/tree"), { headers: examHeaders() });
  if (r.status === 401) {
    clearExamToken();
    throw new Error("UNAUTHORIZED");
  }
  if (!r.ok) throw new Error("無法載入目錄");
  const j = await r.json();
  return {
    subjects: (j as { subjects?: ExamSubject[] }).subjects ?? [],
    examEditAllowed: (j as { exam_edit_allowed?: boolean }).exam_edit_allowed !== false,
  };
}

export async function fetchExamNote(
  subject: string,
  chapter: string,
  unit: string
): Promise<string> {
  const q = new URLSearchParams({ subject, chapter, unit });
  const r = await fetch(apiUrl(`/api/exam/note?${q}`), { headers: examHeaders() });
  if (r.status === 401) {
    clearExamToken();
    throw new Error("UNAUTHORIZED");
  }
  if (!r.ok) throw new Error("無法讀取筆記");
  const j = await r.json();
  return j.content ?? "";
}

export async function saveExamNote(
  subject: string,
  chapter: string,
  unit: string,
  content: string
) {
  const r = await fetch(apiUrl("/api/exam/note"), {
    method: "POST",
    headers: { ...jsonHeaders, ...examHeaders() },
    body: JSON.stringify({ subject, chapter, unit, content }),
  });
  if (r.status === 401) {
    clearExamToken();
    throw new Error("UNAUTHORIZED");
  }
  if (!r.ok) throw new Error("儲存失敗");
}

export async function exportKnowledgeZip(): Promise<Blob> {
  const r = await fetch(apiUrl("/api/knowledge/export"));
  if (!r.ok) throw new Error("匯出 ZIP 失敗");
  return r.blob();
}

export type BatchDecodeResponse = {
  saved: { word: string; saved_to: string }[];
  skipped: string[];
  errors: { word: string; detail: string }[];
};

export async function batchDecode(body: {
  words: string[];
  primary_category: string;
  aux_categories?: string[];
  force_refresh?: boolean;
  delay_sec?: number;
  contribution_mode: ContributionMode;
}): Promise<BatchDecodeResponse> {
  const r = await fetch(apiUrl("/api/decode/batch"), {
    method: "POST",
    headers: { ...jsonHeaders, ...memberHeaders(), ...aiHeaders() },
    body: JSON.stringify({
      words: body.words,
      primary_category: body.primary_category,
      aux_categories: body.aux_categories ?? [],
      force_refresh: body.force_refresh ?? false,
      delay_sec: body.delay_sec ?? 0.5,
      contribution_mode: body.contribution_mode,
    }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 || r.status === 403) {
      clearMemberToken();
    }
    const d = (j as { detail?: string }).detail;
    throw new Error(typeof d === "string" ? d : "批量解碼失敗");
  }
  return j as BatchDecodeResponse;
}

export async function suggestTopics(
  primary_category: string,
  aux_categories: string[] = [],
  count = 5
): Promise<string[]> {
  const r = await fetch(apiUrl("/api/decode/suggest-topics"), {
    method: "POST",
    headers: { ...jsonHeaders, ...memberHeaders(), ...aiHeaders() },
    body: JSON.stringify({
      primary_category,
      aux_categories,
      count,
    }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 || r.status === 403) {
      clearMemberToken();
    }
    const d = (j as { detail?: string }).detail;
    throw new Error(typeof d === "string" ? d : "建議主題失敗");
  }
  return (j as { lines?: string[] }).lines ?? [];
}

export async function generateHandoutMarkdown(
  title: string,
  manual_input: string,
  instruction: string,
  contribution_mode: ContributionMode,
  image_base64?: string | null
): Promise<string> {
  const r = await fetch(apiUrl("/api/handout/generate"), {
    method: "POST",
    headers: { ...jsonHeaders, ...memberHeaders(), ...aiHeaders() },
    body: JSON.stringify({
      title,
      manual_input,
      instruction,
      contribution_mode,
      image_base64: image_base64 || undefined,
    }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 || r.status === 403) {
      clearMemberToken();
    }
    const d = (j as { detail?: string }).detail;
    throw new Error(typeof d === "string" ? d : "講義生成失敗");
  }
  return (j as { markdown?: string }).markdown ?? "";
}

export type MemberStorageRecord = {
  id: string;
  feature: string;
  title: string;
  contribution_mode: ContributionMode;
  input_text?: string;
  output_text?: string;
  output_json?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  created_at: string;
};

export async function fetchMemberStorage(feature?: string): Promise<MemberStorageRecord[]> {
  const q = feature ? `?feature=${encodeURIComponent(feature)}` : "";
  const r = await fetch(apiUrl(`/api/member/storage${q}`), {
    headers: memberHeaders(),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 || r.status === 403) {
      clearMemberToken();
    }
    const d = (j as { detail?: string }).detail;
    throw new Error(typeof d === "string" ? d : "載入個人存儲失敗");
  }
  return (j as { data?: MemberStorageRecord[] }).data ?? [];
}

export async function deleteMemberStorage(recordId: string): Promise<void> {
  const r = await fetch(apiUrl("/api/member/storage"), {
    method: "DELETE",
    headers: { ...jsonHeaders, ...memberHeaders(), ...aiHeaders() },
    body: JSON.stringify({ record_id: recordId }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = (j as { detail?: string }).detail;
    throw new Error(typeof d === "string" ? d : "刪除個人存儲失敗");
  }
}

export async function fetchHandoutPreviewHtml(
  title: string,
  markdown: string,
  image_base64?: string | null,
  img_width_percent = 80
): Promise<string> {
  const r = await fetch(apiUrl("/api/handout/preview-html"), {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      title,
      markdown,
      image_base64: image_base64 || undefined,
      img_width_percent,
    }),
  });
  if (!r.ok) throw new Error("預覽 HTML 失敗");
  return r.text();
}

export async function searchExamLocal(
  q: string,
  subject?: string
): Promise<ExamSearchHit[]> {
  const params = new URLSearchParams({ q });
  if (subject) params.set("subject", subject);
  const r = await fetch(apiUrl(`/api/exam/search?${params}`), {
    headers: examHeaders(),
  });
  if (r.status === 401) {
    clearExamToken();
    throw new Error("UNAUTHORIZED");
  }
  if (!r.ok) throw new Error("搜尋失敗");
  const j = await r.json();
  return j.results ?? [];
}

// --------------------------------------------------------------------------
// Click tracking
// --------------------------------------------------------------------------

export interface ClickEventPayload {
  action: string;
  action_label: string;
  page: string;
  seq: number;
}

export async function sendClickEvents(
  session_id: string,
  events: ClickEventPayload[]
): Promise<void> {
  if (!events.length) return;
  const claims = readMemberTokenClaims();
  await fetch(apiUrl("/api/tracking/clicks"), {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      session_id,
      tenant_id: claims?.tenantId,
      profile_id: claims?.profileId,
      events,
    }),
  }).catch(() => {});
}

export type ClickPrediction = {
  action: string;
  label: string;
  count: number;
  prob: number;
};

export async function fetchClickPrediction(
  session_id: string,
  limit = 5
): Promise<ClickPrediction[]> {
  const q = new URLSearchParams({ session_id, limit: String(limit) });
  const r = await fetch(apiUrl(`/api/tracking/predict?${q}`));
  if (!r.ok) return [];
  const j = await r.json().catch(() => ({}));
  return (j as { predictions?: ClickPrediction[] }).predictions ?? [];
}

