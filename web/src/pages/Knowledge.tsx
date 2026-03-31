import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Download, FileText, RefreshCw, Search, Sparkles, Volume2, X,
} from "lucide-react";
import { Skeleton } from "../components/Skeleton";
import type { KnowledgeRow } from "../types";
import { exportKnowledgeZip, fetchKnowledge } from "../lib/api";

function field(row: KnowledgeRow, key: keyof KnowledgeRow): string {
  const v = row[key];
  return typeof v === "string" ? v.trim() : "";
}

function speakWord(word: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(word);
  utt.lang = "en-US";
  utt.rate = 0.85;
  window.speechSynthesis.speak(utt);
}

function pickRandom<T>(arr: T[], n: number): T[] {
  return [...arr].sort(() => Math.random() - 0.5).slice(0, n);
}

export default function Knowledge() {
  const [rows, setRows]           = useState<KnowledgeRow[]>([]);
  const [loading, setLoading]     = useState(true);
  const [err, setErr]             = useState<string | null>(null);
  const [q, setQ]                 = useState("");
  const [cat, setCat]             = useState<string>("全部");
  const [sel, setSel]             = useState<KnowledgeRow | null>(null);
  const [exporting, setExporting] = useState(false);
  const [spotlightKey, setSpotlightKey] = useState(0);

  const onExport = async () => {
    setExporting(true);
    try {
      const blob = await exportKnowledgeZip();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "knowledge_markdown.zip"; a.click();
      URL.revokeObjectURL(url);
    } catch { alert("匯出失敗"); } finally { setExporting(false); }
  };

  useEffect(() => {
    let ok = true;
    setLoading(true);
    fetchKnowledge()
      .then((d) => { if (ok) setRows(d.rows); })
      .catch((e: Error) => { if (ok) setErr(e.message); })
      .finally(() => { if (ok) setLoading(false); });
    return () => { ok = false; };
  }, []);

  const categories = useMemo(() => {
    const s = new Set<string>();
    rows.forEach((r) => { const c = field(r, "category"); if (c) s.add(c); });
    return ["全部", ...[...s].sort()];
  }, [rows]);

  const filtered = useMemo(() => {
    let list = rows;
    if (cat !== "全部") list = list.filter((r) => field(r, "category") === cat);
    const qq = q.trim().toLowerCase();
    if (!qq) return list;
    return list.filter((r) =>
      [field(r, "word"), field(r, "meaning"), field(r, "definition"), field(r, "category")]
        .join(" ").toLowerCase().includes(qq)
    );
  }, [rows, cat, q]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const spotlight = useMemo(() => pickRandom(rows, 3), [rows, spotlightKey]);

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">單字 · 知識庫</h1>
          <p className="mt-1 text-ink-400 text-sm">
            共 <strong className="text-white">{rows.length}</strong> 筆 ·{" "}
            <strong className="text-white">{categories.length - 1}</strong> 個領域
          </p>
        </div>
        <button
          type="button"
          disabled={exporting || loading}
          onClick={onExport}
          data-track="knowledge/export_zip"
          className="inline-flex items-center gap-2 shrink-0 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-ink-100 hover:bg-white/10 disabled:opacity-50"
        >
          <Download className="h-4 w-4" />
          {exporting ? "打包中…" : "匯出 Markdown ZIP"}
        </button>
      </div>

      {err && (
        <div className="rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-red-200 text-sm">
          {err}
        </div>
      )}

      {/* 今日隨機啟發 */}
      {!loading && rows.length > 0 && !q && cat === "全部" && !sel && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-400 uppercase tracking-wider">今日隨機啟發</h2>
            <button
              type="button"
              onClick={() => setSpotlightKey((k) => k + 1)}
              data-track="knowledge/spotlight_refresh"
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-ink-500 hover:text-ink-200 hover:bg-white/5"
            >
              <RefreshCw className="h-3.5 w-3.5" />換一批
            </button>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {spotlight.map((row, i) => {
              const w = field(row, "word");
              return (
                <button
                  key={`${w}-${i}`}
                  type="button"
                  onClick={() => setSel(row)}
                  data-track="knowledge/card_open"
                  data-track-label={w}
                  className="glass-panel p-4 text-left space-y-1.5 hover:ring-1 hover:ring-accent/30 transition-all duration-150 group"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white group-hover:text-accent-glow transition-colors">{w}</span>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); speakWord(w); }}
                      data-track="knowledge/speak"
                      className="opacity-0 group-hover:opacity-100 rounded p-1 hover:bg-white/10 text-ink-500 hover:text-white"
                    >
                      <Volume2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <p className="text-xs text-ink-500 truncate">{field(row, "category")}</p>
                  <p className="text-xs text-ink-300 line-clamp-2 leading-relaxed">
                    {field(row, "meaning") || field(row, "definition")}
                  </p>
                </button>
              );
            })}
          </div>
        </section>
      )}

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜尋單字、本質、定義…"
            className="w-full rounded-xl border border-white/10 bg-ink-900/60 py-2.5 pl-10 pr-4 text-sm text-white placeholder:text-ink-500 focus:border-accent/50 focus:outline-none focus:ring-1 focus:ring-accent/40"
          />
        </div>
        <select
          value={cat}
          onChange={(e) => setCat(e.target.value)}
          className="rounded-xl border border-white/10 bg-ink-900/60 px-4 py-2.5 text-sm text-white focus:border-accent/50 focus:outline-none"
        >
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="glass-panel p-4 space-y-2">
            {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} height="h-10" />)}
          </div>
          <div className="glass-panel p-6 space-y-4">
            <Skeleton height="h-7" className="max-w-[180px]" />
            <Skeleton height="h-4" rows={4} />
            <Skeleton height="h-20" />
          </div>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="glass-panel max-h-[70vh] overflow-y-auto p-2">
            <div className="px-2 py-1 text-xs text-ink-500">{filtered.length} 筆</div>
            <ul className="space-y-1">
              {filtered.map((row, i) => {
                const w = field(row, "word") || `(未命名 ${i})`;
                const active = sel && field(sel, "word") === field(row, "word");
                return (
                  <li key={`${w}-${i}`}>
                    <button
                      type="button"
                      onClick={() => setSel(row)}
                      data-track="knowledge/word_select"
                      data-track-label={w}
                      className={[
                        "w-full rounded-lg px-3 py-2.5 text-left text-sm transition-all duration-150",
                        active
                          ? "bg-accent/20 text-white ring-1 ring-accent/40"
                          : "text-ink-200 hover:bg-white/5 hover:translate-x-0.5",
                      ].join(" ")}
                    >
                      <div className="font-medium">{w}</div>
                      <div className="text-xs text-ink-500 truncate">
                        {field(row, "category")} · {field(row, "meaning").slice(0, 60)}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="glass-panel min-h-[320px] p-6">
            {!sel ? (
              <div className="flex h-full min-h-[280px] flex-col items-center justify-center gap-3 text-center">
                <div className="rounded-2xl bg-ink-800/50 p-4">
                  <Sparkles className="h-7 w-7 text-ink-600" />
                </div>
                <p className="text-sm text-ink-500">請從左側選擇一筆知識卡。</p>
              </div>
            ) : (
              <Detail row={sel} onClose={() => setSel(null)} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ row, onClose }: { row: KnowledgeRow; onClose: () => void }) {
  const navigate = useNavigate();
  const w = field(row, "word");

  const goHandout = () => {
    const parts = [
      `# ${w}`,
      field(row, "definition") ? `## 定義\n${field(row, "definition")}` : "",
      field(row, "meaning")    ? `## 本質\n${field(row, "meaning")}` : "",
      field(row, "roots")      ? `## 字根／原理\n${field(row, "roots")}` : "",
      field(row, "breakdown")  ? `## 邏輯拆解\n${field(row, "breakdown")}` : "",
      field(row, "example")    ? `## 例句\n${field(row, "example")}` : "",
      field(row, "native_vibe")? `## 專家心法\n${field(row, "native_vibe")}` : "",
      field(row, "memory_hook")? `## 記憶鉤子\n${field(row, "memory_hook")}` : "",
    ].filter(Boolean);
    navigate("/handout", { state: { draft: parts.join("\n\n"), title: w } });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-2xl font-bold text-white">{w || "未命名"}</h2>
          <p className="text-sm text-ink-400 mt-1">
            {field(row, "category")}
            {field(row, "phonetic") ? ` · /${field(row, "phonetic")}/` : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          data-track="knowledge/detail_close"
          className="rounded-lg p-2 text-ink-500 hover:bg-white/10 hover:text-white"
          aria-label="關閉"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => speakWord(w)}
          data-track="knowledge/detail_speak"
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-ink-300 hover:bg-white/10 hover:text-white transition"
        >
          <Volume2 className="h-3.5 w-3.5" />
          朗讀
        </button>
        <button
          type="button"
          onClick={goHandout}
          data-track="knowledge/go_handout"
          className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-900/20 px-3 py-1.5 text-xs text-indigo-300 hover:bg-indigo-900/40 hover:text-indigo-100 transition"
        >
          <FileText className="h-3.5 w-3.5" />
          生成講義
        </button>
      </div>

      {field(row, "breakdown") && (
        <section className="rounded-xl bg-gradient-to-br from-indigo-900/80 to-blue-900/60 p-4 text-sm leading-relaxed text-indigo-50">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-indigo-200/90 mb-2">結構拆解</h3>
          <div className="whitespace-pre-wrap">{field(row, "breakdown")}</div>
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-2">
        <div>
          <h3 className="text-xs font-semibold text-ink-500 uppercase mb-1">直覺定義</h3>
          <p className="text-sm text-ink-100 leading-relaxed whitespace-pre-wrap">{field(row, "definition") || "—"}</p>
        </div>
        <div>
          <h3 className="text-xs font-semibold text-ink-500 uppercase mb-1">本質意義</h3>
          <p className="text-sm text-ink-100 leading-relaxed whitespace-pre-wrap">{field(row, "meaning") || "—"}</p>
        </div>
      </section>

      {field(row, "roots") && (
        <section>
          <h3 className="text-xs font-semibold text-ink-500 uppercase mb-1">核心原理 / 字根</h3>
          <p className="text-sm text-ink-200 whitespace-pre-wrap font-mono">{field(row, "roots")}</p>
        </section>
      )}

      {field(row, "example") && (
        <section className="rounded-lg border border-sky-500/20 bg-sky-950/30 p-3 text-sm text-sky-100">
          <span className="font-medium text-sky-300">例句／實例 · </span>
          {field(row, "example")}
        </section>
      )}

      {field(row, "memory_hook") && (
        <p className="text-sm text-amber-200/90">
          <span className="text-amber-400/80">記憶鉤子 · </span>
          {field(row, "memory_hook")}
        </p>
      )}

      {field(row, "native_vibe") && (
        <section className="rounded-lg border-l-4 border-accent bg-ink-800/40 p-3 text-sm text-ink-200">
          {field(row, "native_vibe")}
        </section>
      )}

      <div className="grid gap-3 sm:grid-cols-2 text-sm text-ink-300">
        <p><span className="text-ink-500">辨析 · </span>{field(row, "synonym_nuance") || "—"}</p>
        <p><span className="text-ink-500">注意 · </span>{field(row, "usage_warning") || "—"}</p>
      </div>
    </div>
  );
}
