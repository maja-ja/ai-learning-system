import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  BookMarked, Clock, FileText, Loader2, Plus,
  Printer, RotateCcw, Sparkles, StickyNote, Trash2, X,
} from "lucide-react";
import {
  createNote, decodeNote, deleteMemberStorage, deleteNote,
  fetchHandoutPreviewHtml, fetchMemberStorage, fetchNotes,
  generateHandoutMarkdown, type CloudNote, type MemberStorageRecord,
} from "../lib/api";
import type { ContributionMode, KnowledgeRow } from "../types";
import { Skeleton } from "../components/Skeleton";
import GenerationPaywall from "../components/GenerationPaywall";
import { useMembership } from "../membership";

// ── local history (browser) ──────────────────────────────────────────────────
type LocalEntry = { title: string; md: string; ts: number };
type HistoryEntry = {
  id: string; title: string; md: string; ts: number;
  source: "local" | "cloud"; contributionMode?: ContributionMode;
};
const HISTORY_KEY = "handout_history";

function addLocal(entry: { title: string; md: string }) {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const list: LocalEntry[] = raw ? JSON.parse(raw) : [];
    list.unshift({ ...entry, ts: Date.now() });
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, 20)));
  } catch { /* ignore */ }
}
function getLocal(): LocalEntry[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); }
  catch { return []; }
}

const TEMPLATES = [
  {
    label: "概念精講",
    content: `# 概念名稱\n\n## 核心定義\n請描述概念本質…\n\n## 邏輯推導\n1. 步驟一\n2. 步驟二\n\n## 應用案例\n- 案例 A\n\n## 常見誤區\n注意事項…`,
  },
  {
    label: "公式推導",
    content: `# 公式名稱\n\n## 前提條件\n- 條件 A\n\n## 推導過程\n$$\n\\\\text{公式} = \\\\frac{A}{B}\n$$\n\n## 典型例題\n**題目：** …\n\n**解答：** …`,
  },
  {
    label: "比較對照",
    content: `# A vs B\n\n## 共同點\n- 共同點 1\n\n## 差異\n\n| 面向 | A | B |\n|------|---|---|\n| 特點 | … | … |`,
  },
];

type TabKey = "decode" | "studio" | "notes" | "history";

// ── Main ─────────────────────────────────────────────────────────────────────
export default function Handout() {
  const location = useLocation();
  const locState = location.state as { draft?: string; title?: string } | null;
  const [tab, setTab] = useState<TabKey>(locState?.draft ? "studio" : "decode");

  const tabs: [TabKey, string, typeof Sparkles][] = [
    ["decode",  "單筆解碼", Sparkles],
    ["studio",  "講義生成", FileText],
    ["notes",   "本機筆記", StickyNote],
    ["history", "歷史紀錄", Clock],
  ];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">講義與解碼</h1>
        <p className="mt-1 text-sm text-gray-500">
          單筆解碼：Claude / Gemini；講義生成：Gemini（需 <code>GEMINI_API_KEY</code>）
        </p>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-black/20">
        {tabs.map(([key, label, Icon]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm border-b-2 -mb-px ${
              tab === key ? "border-black font-semibold" : "border-transparent text-gray-500"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === "decode"  && <DecodePanel />}
      {tab === "studio"  && <StudioPanel initialDraft={locState?.draft} initialTitle={locState?.title} />}
      {tab === "notes"   && <NotesPanel />}
      {tab === "history" && <HistoryPanel />}
    </div>
  );
}

// ── Decode Panel ─────────────────────────────────────────────────────────────
function DecodePanel() {
  const membership = useMembership();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [card, setCard] = useState<KnowledgeRow | null>(null);
  const [meta, setMeta] = useState<{ savedTo: string; provider: string } | null>(null);
  const [mode, setMode] = useState<ContributionMode>("private_use");

  const run = async () => {
    if (!text.trim()) { setErr("請輸入要解碼的內容"); return; }
    setErr(null); setBusy(true); setCard(null); setMeta(null);
    try {
      const r = await decodeNote(text, mode);
      setCard(r.data);
      setMeta({ savedTo: r.saved_to ?? "", provider: r.ai_provider ?? "" });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "解碼失敗");
    } finally { setBusy(false); }
  };

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {/* 左側輸入 */}
      <div className="space-y-3">
        {!membership.canGenerate && <GenerationPaywall />}
        <label className="text-xs font-medium uppercase text-gray-500">輸入筆記或主題</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="貼上段落、單字或講義草稿…"
          rows={12}
          className="w-full border border-black p-3 text-sm font-mono"
        />
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase text-gray-500">存儲方式</p>
          <div className="flex gap-2">
            {(["private_use", "named_contribution"] as ContributionMode[]).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setMode(v)}
                className={`border px-3 py-1.5 text-xs ${
                  mode === v ? "border-2 border-black font-semibold" : "border border-black/30"
                }`}
              >
                {v === "private_use" ? "自己收著用" : `具名貢獻（${membership.contributorLabel || "會員名稱"}）`}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-400">具名貢獻寫入公開知識庫；自己收著用存到個人帳戶。</p>
        </div>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button
          type="button"
          disabled={busy || !membership.canGenerate}
          onClick={run}
          className="inline-flex items-center gap-2 border-2 border-black px-5 py-2.5 text-sm font-medium disabled:opacity-40"
        >
          {busy ? <><Loader2 className="h-4 w-4 animate-spin" />解碼中…</> : <><Sparkles className="h-4 w-4" />送出解碼</>}
        </button>
        <p className="text-xs text-gray-400">
          設 <code>ANTHROPIC_API_KEY</code> 用 Claude；設 <code>GEMINI_API_KEY</code> 用 Gemini
        </p>
      </div>

      {/* 右側結果 */}
      <div className="border border-black/20 p-5 min-h-[280px]">
        {!card ? (
          <p className="text-sm text-gray-400">解碼結果顯示在此。</p>
        ) : (
          <div className="space-y-3">
            {meta && (
              <p className="text-xs text-gray-400">
                {meta.provider && `模型：${meta.provider === "claude" ? "Claude" : "Gemini"}`}
                {meta.savedTo && ` · 儲存：${meta.savedTo === "local" ? "公開知識庫" : "個人存儲"}`}
              </p>
            )}
            <div className="flex items-center gap-2">
              <BookMarked className="h-5 w-5 shrink-0" />
              <h3 className="text-xl font-bold">{card.word}</h3>
            </div>
            <p className="text-xs text-gray-500">{card.category}</p>
            <div className="space-y-2 text-sm">
              {([
                ["定義", card.definition],
                ["本質", card.meaning],
                ["字根／原理", card.roots],
                ["拆解", card.breakdown],
                ["例句", card.example],
                ["記憶鉤", card.memory_hook],
              ] as [string, string | undefined][]).map(([label, val]) =>
                val?.trim() ? (
                  <div key={label}>
                    <p className="text-xs font-medium text-gray-400 uppercase mb-0.5">{label}</p>
                    <p className="whitespace-pre-wrap border border-black/10 px-3 py-2">{val}</p>
                  </div>
                ) : null
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Studio Panel ─────────────────────────────────────────────────────────────
function StudioPanel({ initialDraft, initialTitle }: { initialDraft?: string; initialTitle?: string }) {
  const membership = useMembership();
  const [tmpl, setTmpl] = useState(-1);
  const [manual, setManual] = useState(initialDraft ?? "");
  const [instr, setInstr] = useState("");
  const [imgDataUrl, setImgDataUrl] = useState<string | null>(null);
  const [rotation, setRotation] = useState(0);
  const [md, setMd] = useState("");
  const [title, setTitle] = useState(initialTitle ?? "專題講義");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<ContributionMode>("private_use");
  const fileRef = useRef<HTMLInputElement>(null);

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) { setImgDataUrl(null); return; }
    const reader = new FileReader();
    reader.onload = () => setImgDataUrl(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(f);
    setRotation(0);
  };

  const rotatedDataUrl = (): Promise<string | null> =>
    new Promise((resolve) => {
      if (!imgDataUrl || rotation === 0) return resolve(imgDataUrl ?? null);
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

  const runGen = async () => {
    setErr(null); setBusy(true);
    try {
      const out = await generateHandoutMarkdown(title, manual, instr, mode, await rotatedDataUrl());
      setMd(out);
      addLocal({ title, md: out });
    } catch (e) { setErr(e instanceof Error ? e.message : "生成失敗"); }
    finally { setBusy(false); }
  };

  const openPreview = async () => {
    if (!md.trim()) { setErr("請先生成或貼上 Markdown"); return; }
    setErr(null); setBusy(true);
    try {
      const html = await fetchHandoutPreviewHtml(title, md, await rotatedDataUrl(), 80);
      const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) { setErr(e instanceof Error ? e.message : "預覽失敗"); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      {!membership.canGenerate && <GenerationPaywall />}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* 左側 */}
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase text-gray-500">素材與指令</p>

          {/* 模板 */}
          <div className="flex flex-wrap gap-1.5">
            {TEMPLATES.map((t, i) => (
              <button
                key={i}
                type="button"
                onClick={() => { setTmpl(i); setManual(t.content); }}
                className={`border px-3 py-1 text-xs ${
                  tmpl === i ? "border-2 border-black font-semibold" : "border border-black/30"
                }`}
              >
                {t.label}
              </button>
            ))}
            {tmpl >= 0 && (
              <button type="button" onClick={() => { setTmpl(-1); setManual(""); }}
                className="border border-black/20 px-2 py-1 text-xs">
                <X className="h-3 w-3" />
              </button>
            )}
          </div>

          <textarea
            value={manual}
            onChange={(e) => setManual(e.target.value)}
            placeholder="講義草稿、大綱或段落…"
            rows={8}
            className="w-full border border-black p-3 text-sm"
          />
          <input
            type="text"
            value={instr}
            onChange={(e) => setInstr(e.target.value)}
            placeholder="排版要求（選填）"
            className="w-full border border-black px-3 py-2 text-sm"
          />

          {/* 存儲方式 */}
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase text-gray-500">存儲方式</p>
            <div className="flex flex-wrap gap-2">
              {(["private_use", "named_contribution"] as ContributionMode[]).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setMode(v)}
                  className={`border px-3 py-1.5 text-xs ${
                    mode === v ? "border-2 border-black font-semibold" : "border border-black/30"
                  }`}
                >
                  {v === "private_use" ? "自己收著用" : `具名貢獻（${membership.contributorLabel || "會員名稱"}）`}
                </button>
              ))}
            </div>
          </div>

          {/* 圖片 */}
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase text-gray-500">參考圖（選填）</p>
            <input ref={fileRef} type="file" accept="image/*" onChange={onFile} className="block w-full text-sm" />
            {imgDataUrl && (
              <div className="flex items-center gap-3">
                <img
                  src={imgDataUrl}
                  alt="preview"
                  style={{ transform: `rotate(${rotation}deg)`, maxHeight: 72 }}
                  className="border border-black/20 object-contain"
                />
                <button type="button" onClick={() => setRotation((r) => (r + 90) % 360)}
                  className="inline-flex items-center gap-1 border border-black/30 px-2 py-1 text-xs">
                  <RotateCcw className="h-3 w-3" />旋轉
                </button>
                <button type="button"
                  onClick={() => { setImgDataUrl(null); if (fileRef.current) fileRef.current.value = ""; }}
                  className="border border-black/20 px-2 py-1 text-xs">
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            )}
          </div>

          <button
            type="button"
            disabled={busy || !membership.canGenerate}
            onClick={runGen}
            className="inline-flex items-center gap-2 border-2 border-black px-4 py-2.5 text-sm font-medium disabled:opacity-40"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            AI 生成講義 Markdown
          </button>
        </div>

        {/* 右側 */}
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase text-gray-500">編輯與預覽</p>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="講義標題"
            className="w-full border border-black px-3 py-2 text-sm font-semibold"
          />
          <textarea
            value={md}
            onChange={(e) => setMd(e.target.value)}
            placeholder="生成的 Markdown 可在此編輯…"
            rows={16}
            className="w-full border border-black p-3 text-sm font-mono"
          />
          <button
            type="button"
            disabled={busy}
            onClick={openPreview}
            className="inline-flex items-center gap-2 border border-black px-4 py-2.5 text-sm disabled:opacity-40"
          >
            <Printer className="h-4 w-4" />
            開啟列印預覽（含 MathJax · 可匯 PDF）
          </button>
          <p className="text-xs text-gray-400">使用瀏覽器列印或另存 PDF。</p>
        </div>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
    </div>
  );
}

// ── History Panel ─────────────────────────────────────────────────────────────
function HistoryPanel() {
  const membership = useMembership();
  const [list, setList] = useState<HistoryEntry[]>([]);
  const [sel, setSel] = useState<HistoryEntry | null>(null);

  useEffect(() => {
    let cancelled = false;
    const local = getLocal().map((e) => ({
      id: `local-${e.ts}`, title: e.title, md: e.md, ts: e.ts, source: "local" as const,
    }));
    const load = async () => {
      if (!membership.signedIn) { if (!cancelled) setList(local); return; }
      try {
        const cloud = await fetchMemberStorage("handout_generate");
        if (cancelled) return;
        const mapped = cloud.map((r: MemberStorageRecord) => ({
          id: r.id, title: r.title, md: r.output_text || "",
          ts: Date.parse(r.created_at), source: "cloud" as const,
          contributionMode: r.contribution_mode,
        }));
        setList([...mapped, ...local].sort((a, b) => b.ts - a.ts));
      } catch { if (!cancelled) setList(local); }
    };
    load();
    return () => { cancelled = true; };
  }, [membership.signedIn]);

  const remove = async (entry: HistoryEntry) => {
    if (entry.source === "cloud") await deleteMemberStorage(entry.id);
    else {
      const next = getLocal().filter((e) => e.ts !== entry.ts);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
    }
    setList((prev) => prev.filter((e) => e.id !== entry.id));
    if (sel?.id === entry.id) setSel(null);
  };

  if (!list.length) {
    return <p className="text-sm text-gray-400">尚無紀錄。AI 生成講義後會自動存入。</p>;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-1 max-h-[65vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-2 text-xs text-gray-400">
          <span>{list.length} 份</span>
          <button type="button" onClick={() => {
            localStorage.removeItem(HISTORY_KEY);
            setList((prev) => prev.filter((e) => e.source === "cloud"));
          }}>清空本機</button>
        </div>
        {list.map((e) => (
          <div
            key={e.id}
            onClick={() => setSel(e)}
            className={`flex items-start justify-between border px-3 py-2.5 cursor-pointer text-sm ${
              sel?.id === e.id ? "border-2 border-black" : "border border-black/20"
            }`}
          >
            <div className="min-w-0">
              <p className="font-medium truncate">{e.title}</p>
              <p className="text-xs text-gray-400">
                {new Date(e.ts).toLocaleString("zh-TW")} · {e.source === "cloud" ? "會員存儲" : "本機"}
              </p>
            </div>
            <button type="button" onClick={async (ev) => { ev.stopPropagation(); await remove(e); }}
              className="ml-2 p-1 text-gray-400 shrink-0">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
      <div className="border border-black/20 p-4 max-h-[65vh] overflow-y-auto">
        {!sel ? (
          <p className="text-sm text-gray-400">點選左側一份以預覽</p>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-sm">{sel.title}</p>
              <button
                type="button"
                onClick={async () => {
                  const html = await fetchHandoutPreviewHtml(sel.title, sel.md, null, 80);
                  const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
                  window.open(url, "_blank", "noopener,noreferrer");
                  setTimeout(() => URL.revokeObjectURL(url), 60_000);
                }}
                className="inline-flex items-center gap-1.5 border border-black px-3 py-1.5 text-xs"
              >
                <Printer className="h-3.5 w-3.5" />預覽 PDF
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-xs font-mono text-gray-700 border border-black/10 p-3 overflow-x-auto">
              {sel.md}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Notes Panel ───────────────────────────────────────────────────────────────
function NotesPanel() {
  const [notes, setNotes] = useState<CloudNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [creating, setCreating] = useState(false);
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try { setNotes(await fetchNotes()); }
    catch (e) { setErr(e instanceof Error ? e.message : "載入失敗"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onCreate = async () => {
    if (!newTitle.trim() && !newContent.trim()) return;
    setCreating(true);
    try {
      await createNote({ title: newTitle, content: newContent, tags: "" });
      setNewTitle(""); setNewContent(""); setShowNew(false);
      load();
    } catch (e) { setErr(e instanceof Error ? e.message : "建立失敗"); }
    finally { setCreating(false); }
  };

  const onDelete = async (id: number) => {
    if (!confirm("確定刪除？")) return;
    try { await deleteNote(id); load(); } catch { setErr("刪除失敗"); }
  };

  if (loading) return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} height="h-16" />)}
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">共 {notes.length} 則本機筆記</p>
        <button type="button" onClick={() => setShowNew((v) => !v)}
          className="inline-flex items-center gap-1.5 border border-black px-3 py-1.5 text-xs">
          <Plus className="h-3.5 w-3.5" />新增
        </button>
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      {showNew && (
        <div className="border border-black/30 p-4 space-y-3">
          <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="標題"
            className="w-full border border-black px-3 py-2 text-sm" />
          <textarea value={newContent} onChange={(e) => setNewContent(e.target.value)} placeholder="內容" rows={4}
            className="w-full border border-black p-3 text-sm font-mono" />
          <div className="flex gap-2">
            <button type="button" disabled={creating} onClick={onCreate}
              className="border-2 border-black px-4 py-2 text-xs font-medium disabled:opacity-40">
              {creating ? "儲存中…" : "儲存"}
            </button>
            <button type="button" onClick={() => setShowNew(false)}
              className="border border-black/30 px-4 py-2 text-xs">取消</button>
          </div>
        </div>
      )}
      <ul className="space-y-2 max-h-[60vh] overflow-y-auto">
        {notes.map((n) => (
          <li key={n.id} className="border border-black/20 p-4 group">
            <div className="flex items-start justify-between">
              <p className="font-medium text-sm">{n.title || "(無標題)"}</p>
              <button type="button" onClick={() => onDelete(n.id)}
                className="ml-2 p-1 text-gray-400">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
            {n.tags && <p className="text-xs text-gray-400 mt-0.5">標籤：{n.tags}</p>}
            <pre className="mt-2 text-xs text-gray-600 whitespace-pre-wrap max-h-32 overflow-y-auto">
              {n.content || "（空白）"}
            </pre>
          </li>
        ))}
      </ul>
    </div>
  );
}
