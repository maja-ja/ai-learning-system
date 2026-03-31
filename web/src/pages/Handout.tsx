import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  BookMarked, Clock, FileText, Loader2, Plus, Printer,
  RotateCcw, StickyNote, Sparkles, Trash2, X,
} from "lucide-react";
import {
  createNote, decodeNote, deleteNote, fetchHandoutPreviewHtml,
  fetchNotes, generateHandoutMarkdown, type CloudNote,
} from "../lib/api";
import type { KnowledgeRow } from "../types";
import { Skeleton } from "../components/Skeleton";

const TEMPLATES: { label: string; content: string }[] = [
  {
    label: "概念精講",
    content: `# 概念名稱\n\n## 核心定義\n請在此描述概念的本質…\n\n## 邏輯推導\n1. 步驟一\n2. 步驟二\n3. 步驟三\n\n## 應用案例\n- 案例 A\n- 案例 B\n\n## 常見誤區\n注意事項…\n\n## 記憶口訣\n一句話記憶…`,
  },
  {
    label: "公式推導",
    content: `# 公式名稱\n\n## 前提條件\n- 條件 A\n- 條件 B\n\n## 推導過程\n$$\n\\\\text{公式} = \\\\frac{A}{B}\n$$\n\n## 物理意義\n說明公式代表的實際意義…\n\n## 典型例題\n**題目：** …\n\n**解答：** …`,
  },
  {
    label: "比較對照",
    content: `# A vs B 比較\n\n## 共同點\n- 共同點 1\n- 共同點 2\n\n## 關鍵差異\n\n| 面向 | A | B |\n|------|---|---|\n| 特點 | … | … |\n| 應用 | … | … |\n\n## 選擇建議\n在什麼情況下用哪個…`,
  },
];

type HistoryEntry = { title: string; md: string; ts: number };
const HISTORY_KEY = "handout_history";

function addToHistory(entry: { title: string; md: string }) {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const list: HistoryEntry[] = raw ? JSON.parse(raw) : [];
    list.unshift({ ...entry, ts: Date.now() });
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, 20)));
  } catch { /* ignore */ }
}

function getHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

export default function Handout() {
  const location = useLocation();
  const locState = location.state as { draft?: string; title?: string } | null;
  const [tab, setTab] = useState<"decode" | "studio" | "notes" | "history">(
    locState?.draft ? "studio" : "decode"
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">講義與解碼</h1>
        <p className="mt-1 text-ink-400 text-sm">
          單筆解碼可選 Claude／Gemini；講義 AI 生成與 A4 預覽使用{" "}
          <strong className="text-ink-300">Gemini</strong>（需{" "}
          <code className="text-ink-500">GEMINI_API_KEY</code>）。
        </p>
      </div>

      <div className="flex flex-wrap rounded-xl bg-ink-900/60 p-1 border border-white/10 gap-1">
        {(
          [
            ["decode",  "單筆解碼", Sparkles],
            ["studio",  "講義生成", FileText],
            ["notes",   "本機筆記", StickyNote],
            ["history", "歷史紀錄", Clock],
          ] as const
        ).map(([key, label, Icon]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-150 ${
              tab === key
                ? "bg-white/10 text-white shadow"
                : "text-ink-500 hover:text-ink-300 hover:bg-white/5"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === "decode"  && <div className="animate-fade-up"><DecodePanel /></div>}
      {tab === "studio"  && (
        <div className="animate-fade-up">
          <StudioPanel initialDraft={locState?.draft} initialTitle={locState?.title} />
        </div>
      )}
      {tab === "notes"   && <div className="animate-fade-up"><NotesPanel /></div>}
      {tab === "history" && <div className="animate-fade-up"><HistoryPanel /></div>}
    </div>
  );
}

function StudioPanel({
  initialDraft,
  initialTitle,
}: { initialDraft?: string; initialTitle?: string }) {
  const [template, setTemplate] = useState<number>(-1);
  const [manual,   setManual]   = useState(initialDraft ?? "");
  const [instr,    setInstr]    = useState("");
  const [imgDataUrl, setImgDataUrl] = useState<string | null>(null);
  const [rotation, setRotation] = useState(0);
  const [md,       setMd]       = useState("");
  const [title,    setTitle]    = useState(initialTitle ?? "專題講義");
  const [busy,     setBusy]     = useState(false);
  const [err,      setErr]      = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const rotate = () => setRotation((r) => (r + 90) % 360);

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) { setImgDataUrl(null); return; }
    const reader = new FileReader();
    reader.onload = () => setImgDataUrl(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(f);
    setRotation(0);
  };

  const getRotatedDataUrl = (): Promise<string | null> =>
    new Promise((resolve) => {
      if (!imgDataUrl) return resolve(null);
      if (rotation === 0) return resolve(imgDataUrl);
      const img = new Image();
      img.onload = () => {
        const swap = rotation === 90 || rotation === 270;
        const canvas = document.createElement("canvas");
        canvas.width  = swap ? img.height : img.width;
        canvas.height = swap ? img.width  : img.height;
        const ctx = canvas.getContext("2d")!;
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate((rotation * Math.PI) / 180);
        ctx.drawImage(img, -img.width / 2, -img.height / 2);
        resolve(canvas.toDataURL("image/jpeg", 0.9));
      };
      img.src = imgDataUrl;
    });

  const applyTemplate = (idx: number) => {
    setTemplate(idx);
    if (idx >= 0) setManual(TEMPLATES[idx].content);
  };

  const runGen = async () => {
    setErr(null); setBusy(true);
    try {
      const rotated = await getRotatedDataUrl();
      const out = await generateHandoutMarkdown(manual, instr, rotated);
      setMd(out);
      addToHistory({ title, md: out });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "生成失敗");
    } finally { setBusy(false); }
  };

  const openPreview = async () => {
    if (!md.trim()) { setErr("請先產生或貼上 Markdown"); return; }
    setErr(null); setBusy(true);
    try {
      const rotated = await getRotatedDataUrl();
      const html = await fetchHandoutPreviewHtml(title, md, rotated, 80);
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "預覽失敗");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-panel p-5 space-y-4">
          <h2 className="text-lg font-semibold text-white">素材與指令</h2>
          <div>
            <label className="text-xs text-ink-500 uppercase mb-1 block">快速套用模板</label>
            <div className="flex flex-wrap gap-2">
              {TEMPLATES.map((t, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => applyTemplate(i)}
                  className={`rounded-lg border px-3 py-1.5 text-xs transition ${
                    template === i
                      ? "border-accent/50 bg-accent/15 text-accent-glow"
                      : "border-white/10 text-ink-400 hover:border-white/25 hover:text-ink-200"
                  }`}
                >
                  {t.label}
                </button>
              ))}
              {template >= 0 && (
                <button
                  type="button"
                  onClick={() => { setTemplate(-1); setManual(""); }}
                  className="rounded-lg border border-white/5 px-2 py-1.5 text-xs text-ink-600 hover:text-ink-400"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>
          <textarea
            value={manual}
            onChange={(e) => setManual(e.target.value)}
            placeholder="原始講義草稿、大綱或段落…"
            rows={8}
            className="w-full rounded-xl border border-white/10 bg-ink-950/60 p-3 text-sm text-white"
          />
          <input
            type="text"
            value={instr}
            onChange={(e) => setInstr(e.target.value)}
            placeholder="排版要求（選填）"
            className="w-full rounded-xl border border-white/10 bg-ink-950/60 px-3 py-2 text-sm text-white"
          />
          <div className="space-y-2">
            <label className="text-xs text-ink-500">參考圖（選填）</label>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              onChange={onFile}
              className="block w-full text-sm text-ink-400"
            />
            {imgDataUrl && (
              <div className="flex items-center gap-3">
                <img
                  src={imgDataUrl}
                  alt="preview"
                  style={{ transform: `rotate(${rotation}deg)`, maxHeight: 80 }}
                  className="rounded border border-white/10 object-contain transition-transform duration-200"
                />
                <button
                  type="button"
                  onClick={rotate}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-ink-300 hover:bg-white/5"
                >
                  <RotateCcw className="h-3.5 w-3.5" />旋轉 90°
                </button>
                <button
                  type="button"
                  onClick={() => { setImgDataUrl(null); if (fileRef.current) fileRef.current.value = ""; }}
                  className="rounded-lg border border-white/10 px-2 py-1.5 text-xs text-ink-600 hover:text-red-300"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={runGen}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            AI 生成講義 Markdown
          </button>
        </div>

        <div className="glass-panel p-5 space-y-4">
          <h2 className="text-lg font-semibold text-white">編輯與預覽</h2>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="講義標題"
            className="w-full rounded-xl border border-white/10 bg-ink-950/60 px-3 py-2 text-sm text-white"
          />
          <textarea
            value={md}
            onChange={(e) => setMd(e.target.value)}
            placeholder="生成的 Markdown 可在此修改…"
            rows={14}
            className="w-full rounded-xl border border-white/10 bg-ink-950/60 p-3 text-sm font-mono text-ink-100"
          />
          <button
            type="button"
            disabled={busy}
            onClick={openPreview}
            className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-4 py-2.5 text-sm text-white hover:bg-white/15 disabled:opacity-50"
          >
            <Printer className="h-4 w-4" />
            開啟列印預覽（新分頁，含 MathJax／匯 PDF）
          </button>
          <p className="text-xs text-ink-500">預覽頁使用瀏覽器列印或 html2pdf 下載。</p>
        </div>
      </div>
      {err && <p className="text-sm text-red-300">{err}</p>}
    </div>
  );
}

function HistoryPanel() {
  const [list, setList] = useState<HistoryEntry[]>([]);
  const [sel, setSel]   = useState<HistoryEntry | null>(null);

  useEffect(() => { setList(getHistory()); }, []);

  const clear = () => {
    localStorage.removeItem(HISTORY_KEY); setList([]); setSel(null);
  };
  const remove = (ts: number) => {
    const next = list.filter((e) => e.ts !== ts);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
    setList(next);
    if (sel?.ts === ts) setSel(null);
  };

  if (!list.length) {
    return (
      <div className="glass-panel p-6 text-center text-sm text-ink-500">
        尚無歷史紀錄。在「講義生成」頁 AI 生成後會自動存入。
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="glass-panel p-4 space-y-2 max-h-[65vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-ink-500">{list.length} 則</span>
          <button type="button" onClick={clear}
            className="text-xs text-red-400/70 hover:text-red-300 hover:underline">全部清除</button>
        </div>
        {list.map((e) => (
          <div
            key={e.ts}
            className={`flex items-center justify-between rounded-lg border px-3 py-2.5 cursor-pointer text-sm transition ${
              sel?.ts === e.ts ? "border-accent/40 bg-accent/10 text-white" : "border-white/5 text-ink-300 hover:bg-white/5"
            }`}
            onClick={() => setSel(e)}
          >
            <div>
              <div className="font-medium truncate max-w-[180px]">{e.title}</div>
              <div className="text-xs text-ink-500">{new Date(e.ts).toLocaleString("zh-TW")}</div>
            </div>
            <button type="button" onClick={(ev) => { ev.stopPropagation(); remove(e.ts); }}
              className="ml-2 p-1 rounded hover:bg-red-500/10 text-ink-600 hover:text-red-300">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
      <div className="glass-panel p-5 max-h-[65vh] overflow-y-auto">
        {!sel ? (
          <p className="text-sm text-ink-500">點選左側一則以預覽</p>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-white">{sel.title}</h3>
              <button type="button"
                onClick={async () => {
                  const html = await fetchHandoutPreviewHtml(sel.title, sel.md, null, 80);
                  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
                  const url = URL.createObjectURL(blob);
                  window.open(url, "_blank", "noopener,noreferrer");
                  setTimeout(() => URL.revokeObjectURL(url), 60_000);
                }}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-ink-200 hover:bg-white/10">
                <Printer className="h-3.5 w-3.5" />預覽 PDF
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-xs font-mono text-ink-300 bg-ink-900/50 rounded-xl p-4 overflow-x-auto">
              {sel.md}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

function DecodePanel() {
  const [text, setText]           = useState("");
  const [busy, setBusy]           = useState(false);
  const [err, setErr]             = useState<string | null>(null);
  const [card, setCard]           = useState<KnowledgeRow | null>(null);
  const [savedTo, setSavedTo]     = useState<string | null>(null);
  const [aiProvider, setAiProvider] = useState<string | null>(null);

  const run = async () => {
    if (!text.trim()) { setErr("請輸入要解碼的內容"); return; }
    setErr(null); setBusy(true); setCard(null); setSavedTo(null); setAiProvider(null);
    try {
      const r = await decodeNote(text);
      setCard(r.data); setSavedTo(r.saved_to ?? null); setAiProvider(r.ai_provider ?? null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "解碼失敗");
    } finally { setBusy(false); }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="glass-panel p-5 space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <BookMarked className="h-5 w-5 text-accent-glow" />輸入筆記或主題
        </h2>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="貼上段落、單字或講義草稿…"
          rows={14}
          className="w-full rounded-xl border border-white/10 bg-ink-950/60 p-4 text-sm text-ink-100 placeholder:text-ink-600 focus:border-accent/40 focus:outline-none focus:ring-1 focus:ring-accent/30"
        />
        {err && <p className="text-sm text-red-300">{err}</p>}
        <button
          type="button"
          disabled={busy}
          onClick={run}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent to-indigo-600 px-5 py-3 text-sm font-medium text-white shadow-lg shadow-indigo-900/40 disabled:opacity-50"
        >
          {busy ? <><Loader2 className="h-4 w-4 animate-spin" />解碼中…</> : <><Sparkles className="h-4 w-4" />送出解碼</>}
        </button>
        <p className="text-xs text-ink-500 leading-relaxed">
          <strong className="text-ink-400">Claude：</strong>設定 <code className="text-ink-400">ANTHROPIC_API_KEY</code> ｜{" "}
          <strong className="text-ink-400">Gemini：</strong>設定 <code className="text-ink-400">GEMINI_API_KEY</code>
        </p>
      </div>
      <div className="glass-panel p-5 min-h-[320px]">
        {!card ? (
          <p className="text-sm text-ink-500">解碼結果會顯示在此。</p>
        ) : (
          <div className="space-y-4">
            {(savedTo || aiProvider) && (
              <p className="text-xs text-emerald-300/90 space-x-2">
                {aiProvider && <span>模型：{aiProvider === "claude" ? "Claude" : "Gemini"}</span>}
                {savedTo && <span>· 已儲存：{savedTo === "local" ? "本機 SQLite" : savedTo}</span>}
              </p>
            )}
            <h3 className="text-2xl font-bold text-white">{card.word}</h3>
            <p className="text-sm text-ink-400">{card.category}</p>
            <div className="space-y-3 text-sm text-ink-200">
              <Field label="定義" value={card.definition} />
              <Field label="本質" value={card.meaning} />
              <Field label="字根／原理" value={card.roots} mono />
              <Field label="拆解" value={card.breakdown} />
              <Field label="例句" value={card.example} />
              <Field label="記憶鉤" value={card.memory_hook} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value?: string; mono?: boolean }) {
  if (!value?.trim()) return null;
  return (
    <div>
      <div className="text-xs font-medium text-ink-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={`whitespace-pre-wrap rounded-lg bg-ink-800/40 px-3 py-2 border border-white/5 ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </div>
    </div>
  );
}

function NotesPanel() {
  const [notes, setNotes]       = useState<CloudNote[]>([]);
  const [loading, setLoading]   = useState(true);
  const [err, setErr]           = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [creating, setCreating] = useState(false);
  const [showNew, setShowNew]   = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const d = await fetchNotes();
      setNotes(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "載入失敗");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onCreate = async () => {
    if (!newTitle.trim() && !newContent.trim()) return;
    setCreating(true);
    try {
      await createNote({ title: newTitle, content: newContent, tags: "" });
      setNewTitle(""); setNewContent(""); setShowNew(false);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "建立失敗");
    } finally { setCreating(false); }
  };

  const onDelete = async (id: number) => {
    if (!confirm("確定刪除此筆記？")) return;
    try { await deleteNote(id); load(); } catch { setErr("刪除失敗"); }
  };

  if (loading) {
    return (
      <div className="glass-panel p-5 space-y-3">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} height="h-16" />)}
      </div>
    );
  }

  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-400">共 {notes.length} 則本機筆記</p>
        <button type="button" onClick={() => setShowNew((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-ink-200 hover:bg-white/5">
          <Plus className="h-3.5 w-3.5" />新增
        </button>
      </div>
      {err && <p className="text-xs text-red-300">{err}</p>}
      {showNew && (
        <div className="rounded-xl border border-white/10 bg-ink-900/40 p-4 space-y-3">
          <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="標題"
            className="w-full rounded-lg border border-white/10 bg-ink-950/60 px-3 py-2 text-sm text-white" />
          <textarea value={newContent} onChange={(e) => setNewContent(e.target.value)} placeholder="內容" rows={4}
            className="w-full rounded-lg border border-white/10 bg-ink-950/60 px-3 py-2 text-sm text-white font-mono" />
          <div className="flex gap-2">
            <button type="button" disabled={creating} onClick={onCreate}
              className="rounded-lg bg-emerald-700/80 px-4 py-2 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
              {creating ? "儲存中…" : "儲存"}
            </button>
            <button type="button" onClick={() => setShowNew(false)}
              className="rounded-lg border border-white/10 px-4 py-2 text-xs text-ink-400 hover:text-ink-200">
              取消
            </button>
          </div>
        </div>
      )}
      <ul className="space-y-3 max-h-[60vh] overflow-y-auto">
        {notes.map((n) => (
          <li key={n.id} className="rounded-xl border border-white/10 bg-ink-900/40 p-4 group">
            <div className="flex items-start justify-between">
              <div className="font-medium text-white">{n.title || "(無標題)"}</div>
              <button type="button" onClick={() => onDelete(n.id)}
                className="opacity-0 group-hover:opacity-100 ml-2 p-1 rounded hover:bg-red-500/10 text-ink-600 hover:text-red-300 transition">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
            {n.tags && <div className="text-xs text-ink-500 mt-1">標籤：{n.tags}</div>}
            <pre className="mt-2 text-xs text-ink-300 whitespace-pre-wrap font-sans max-h-40 overflow-y-auto">
              {n.content || "（空白）"}
            </pre>
          </li>
        ))}
      </ul>
    </div>
  );
}
