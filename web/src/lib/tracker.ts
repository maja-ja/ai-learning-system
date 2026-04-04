/**
 * 全域點擊序列追蹤器
 *
 * - 以 sessionStorage 保存匿名 session_id（關閉分頁後失效）
 * - 監聽 document click，提取 action 識別碼後排隊
 * - 每 6 秒或頁面隱藏時批次送出至 POST /api/tracking/clicks
 * - action 格式：{page}/{element_type}/{label}
 *   例：knowledge/nav、roots/tab/字根列表、lab/button/推薦Hook
 *
 * 使用方式：
 *   import { initTracker, getSessionId } from "./tracker"
 *   initTracker()          // 在 App 根元件 mount 時呼叫一次
 */

import { sendClickEvents } from "./api";

// --------------------------------------------------------------------------
// Session ID
// --------------------------------------------------------------------------

const SESSION_KEY = "_tracker_sid";

function generateId(): string {
  if (crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export function getSessionId(): string {
  let sid = sessionStorage.getItem(SESSION_KEY);
  if (!sid) {
    sid = generateId();
    sessionStorage.setItem(SESSION_KEY, sid);
  }
  return sid;
}

// --------------------------------------------------------------------------
// Action extraction
// --------------------------------------------------------------------------

/** 取得元素距頁面根最近的 [data-track] 屬性值（允許父層標記子層點擊）。 */
function getDataTrack(el: Element | null): string | null {
  let cur: Element | null = el;
  for (let i = 0; i < 6 && cur && cur !== document.body; i++) {
    const v = cur.getAttribute("data-track");
    if (v) return v;
    cur = cur.parentElement;
  }
  return null;
}

/** 擷取元素的人類可讀標籤（最多 40 字）。 */
function extractLabel(el: Element | null): string {
  if (!el) return "";
  const candidates = [
    el.getAttribute("aria-label"),
    el.getAttribute("title"),
    el.getAttribute("data-track-label"),
    (el as HTMLInputElement).value?.slice(0, 40),
    el.textContent?.trim().slice(0, 40),
  ];
  return candidates.find(Boolean) ?? "";
}

/** 由 target element 推導 action 字串。 */
function deriveAction(
  target: EventTarget | null,
  page: string
): { action: string; label: string } | null {
  if (!(target instanceof Element)) return null;
  const el = target as Element;

  // 優先取 data-track 屬性（開發者主動標記）
  const track = getDataTrack(el);
  if (track) {
    const label = extractLabel(el);
    return { action: `${page}/${track}`, label };
  }

  // 導覽連結
  const anchor = el.closest("a[href]") as HTMLAnchorElement | null;
  if (anchor) {
    const href = anchor.getAttribute("href") ?? "";
    // 只追蹤內部路由
    if (href.startsWith("/")) {
      const label = extractLabel(anchor);
      return { action: `${page}/nav${href}`, label: label || href };
    }
    return null;
  }

  // 按鈕
  const btn = el.closest("button") as HTMLButtonElement | null;
  if (btn) {
    const label = extractLabel(btn);
    if (!label) return null;
    return { action: `${page}/button/${label.slice(0, 40)}`, label };
  }

  return null;
}

// --------------------------------------------------------------------------
// Queue & flush
// --------------------------------------------------------------------------

export interface ClickEvent {
  action: string;
  action_label: string;
  page: string;
  seq: number;
}

let _queue: ClickEvent[] = [];
let _seq = 0;
let _initialized = false;

function currentPage(): string {
  return window.location.pathname;
}

function flush() {
  if (_queue.length === 0) return;
  const batch = _queue.splice(0);
  const sid = getSessionId();
  sendClickEvents(sid, batch).catch(() => {
    // 靜默失敗；追蹤不應影響使用者體驗
  });
}

function handleClick(e: MouseEvent) {
  const page = currentPage();
  const derived = deriveAction(e.target, page);
  if (!derived) return;

  _queue.push({
    action: derived.action,
    action_label: derived.label,
    page,
    seq: _seq++,
  });
}

/** 初始化追蹤器（只需呼叫一次）。 */
export function initTracker() {
  if (_initialized) return;
  _initialized = true;

  // 恢復 seq 計數（同 session 連頁）
  const stored = sessionStorage.getItem("_tracker_seq");
  if (stored) _seq = parseInt(stored, 10) || 0;

  document.addEventListener("click", handleClick, { capture: true, passive: true });

  setInterval(() => {
    sessionStorage.setItem("_tracker_seq", String(_seq));
    flush();
  }, 6000);

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      sessionStorage.setItem("_tracker_seq", String(_seq));
      flush();
    }
  });
}
