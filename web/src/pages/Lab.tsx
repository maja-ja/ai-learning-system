import { useCallback, useEffect, useRef, useState } from "react";
import { BarChart3, FlaskConical, Loader2, Map, Save, Sparkles, StopCircle, Upload } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { suggestTopics, API_BASE, fetchMemberStorage } from "../lib/api";
import type { ContributionMode } from "../types";
import GenerationPaywall from "../components/GenerationPaywall";
import { useMembership } from "../membership";
import { getMemberToken } from "../lib/memberToken";
import { getUserGeminiKey } from "../lib/userKeys";
import KnowledgeMapView from "../components/KnowledgeMapView";
import CategoryPicker, { ALL_CATEGORIES } from "../components/CategoryPicker";
import BatchProgress, { type BatchItem } from "../components/BatchProgress";

type LabTab = "batch" | "map" | "stats";

const QUEUE_KEY = "etymon_topic_queue";

export default function Lab() {
  const membership = useMembership();
  const [tab, setTab] = useState<LabTab>("batch");
  const [primary, setPrimary] = useState(ALL_CATEGORIES[0] ?? "英語辭源");
  const [aux, setAux] = useState<string[]>([]);
  const [lines, setLines] = useState(() => {
    try { return localStorage.getItem(QUEUE_KEY) || ""; } catch { return ""; }
  });
  const [force, setForce] = useState(false);

  // Persist topic queue to localStorage
  useEffect(() => {
    try { localStorage.setItem(QUEUE_KEY, lines); } catch { /* noop */ }
  }, [lines]);
  const [delay, setDelay] = useState(0.8);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string | null>(null);
  const [contributionMode, setContributionMode] = useState<ContributionMode>("private_use");

  // SSE streaming state
  const [streaming, setStreaming] = useState(false);
  const [streamItems, setStreamItems] = useState<BatchItem[]>([]);
  const [streamComplete, setStreamComplete] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const onSuggest = async () => {
    setLog(null);
    setBusy(true);
    try {
      const topics = await suggestTopics(primary, aux, 5);
      setLines(topics.join("\n"));
    } catch (e) {
      setLog(e instanceof Error ? e.message : "取得靈感失敗（需 GEMINI_API_KEY）");
    } finally {
      setBusy(false);
    }
  };

  const onStreamBatch = useCallback(async () => {
    const words = lines
      .split(/[\n,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 30);
    if (!words.length) {
      setLog("請在文字框輸入主題，每行一個。");
      return;
    }
    setLog(null);
    setStreamItems([]);
    setStreamComplete(false);
    setStreaming(true);
    setBusy(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const token = getMemberToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;
      const gk = getUserGeminiKey();
      if (gk) headers["X-User-Gemini-Key"] = gk;

      const url = API_BASE ? `${API_BASE}/api/decode/batch-stream` : "/api/decode/batch-stream";
      const resp = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify({
          words,
          primary_category: primary,
          aux_categories: aux,
          force_refresh: force,
          delay_sec: delay,
          contribution_mode: contributionMode,
        }),
        signal: ctrl.signal,
      });

      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        throw new Error((j as { detail?: string }).detail || `HTTP ${resp.status}`);
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No readable stream");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const stripped = line.replace(/^data:\s*/, "").trim();
          if (!stripped) continue;
          try {
            const data = JSON.parse(stripped);
            if (data.status === "complete") {
              setStreamComplete(true);
            } else {
              setStreamItems((prev) => {
                const idx = prev.findIndex((p) => p.i === data.i);
                if (idx >= 0) {
                  const next = [...prev];
                  next[idx] = data as BatchItem;
                  return next;
                }
                return [...prev, data as BatchItem];
              });
            }
          } catch {
            /* skip malformed */
          }
        }
      }
      setStreamComplete(true);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setLog(e instanceof Error ? e.message : "串流解碼失敗");
      }
    } finally {
      setStreaming(false);
      setBusy(false);
      abortRef.current = null;
    }
  }, [lines, primary, aux, force, delay, contributionMode]);

  const onCancel = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setBusy(false);
    setStreamComplete(true);
    setLog("已中途取消。");
  };

  const streamTotal = streamItems.length > 0 ? streamItems[0]?.total ?? 0 : 0;

  const btnBase = "inline-flex items-center gap-2 border border-black px-3 py-2 text-xs font-medium disabled:opacity-40";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-3">
          <FlaskConical className="h-7 w-7 shrink-0" />
          解碼實驗室
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          批量流程使用 Gemini；結果即時串流回傳，可中途取消。
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex border-b-2 border-black/10">
        <button
          type="button"
          onClick={() => setTab("batch")}
          className={[
            "flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-[2px] transition-colors",
            tab === "batch"
              ? "border-black text-black"
              : "border-transparent text-black/40 hover:text-black",
          ].join(" ")}
        >
          <Sparkles className="h-4 w-4" />
          批量解碼
        </button>
        <button
          type="button"
          onClick={() => setTab("map")}
          className={[
            "flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-[2px] transition-colors",
            tab === "map"
              ? "border-black text-black"
              : "border-transparent text-black/40 hover:text-black",
          ].join(" ")}
        >
          <Map className="h-4 w-4" />
          知識地圖
        </button>
        <button
          type="button"
          onClick={() => setTab("stats")}
          className={[
            "flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-[2px] transition-colors",
            tab === "stats"
              ? "border-black text-black"
              : "border-transparent text-black/40 hover:text-black",
          ].join(" ")}
        >
          <BarChart3 className="h-4 w-4" />
          歷史統計
        </button>
      </div>

      {tab === "map" && <KnowledgeMapView />}

      {tab === "stats" && <LabStats />}

      {tab === "batch" && (
        <>
          {!membership.canGenerate && <GenerationPaywall title="實驗室生成已鎖定" />}

          <div className="border border-black p-5 space-y-5">
            {/* Category picker */}
            <CategoryPicker
              primary={primary}
              aux={aux}
              onPrimaryChange={setPrimary}
              onAuxChange={setAux}
            />

            <button
              type="button"
              disabled={busy || !membership.canGenerate}
              onClick={onSuggest}
              className={`${btnBase} text-sm`}
            >
              <Sparkles className="h-3.5 w-3.5" />
              隨機靈感（5 則中文主題）
            </button>

            <textarea
              value={lines}
              onChange={(e) => setLines(e.target.value)}
              rows={8}
              placeholder="每行一個概念，例如：熵增定律"
              className="w-full border border-black p-4 text-sm font-mono"
            />

            <div className="flex flex-wrap gap-4 items-center text-sm text-gray-600">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={force}
                  onChange={(e) => setForce(e.target.checked)}
                  className="border border-black"
                />
                強制覆寫已存在主題
              </label>
              <label className="flex items-center gap-2">
                請求間隔（秒）
                <input
                  type="number"
                  min={0}
                  max={3}
                  step={0.1}
                  value={delay}
                  onChange={(e) => setDelay(Number(e.target.value))}
                  className="w-20 border border-black px-2 py-1"
                />
              </label>
            </div>

            {/* Contribution mode */}
            <div className="border border-black/30 p-3 space-y-2 text-sm">
              <p className="text-xs font-medium uppercase">生成後處理方式</p>
              <div className="flex flex-wrap gap-2">
                {([
                  ["private_use", "自己收著用"],
                  ["named_contribution", `具名貢獻（${membership.contributorLabel || "會員名稱"}）`],
                ] as const).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setContributionMode(value)}
                    className={[
                      "border px-3 py-1.5 text-xs",
                      contributionMode === value
                        ? "border-2 border-black font-semibold"
                        : "border border-black/30",
                    ].join(" ")}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-gray-500">具名貢獻寫入公開知識庫；自己收著用存到個人存儲不公開。</p>
            </div>

            {/* Launch button */}
            <div className="flex gap-3">
              <button
                type="button"
                disabled={busy || !membership.canGenerate}
                onClick={onStreamBatch}
                className="inline-flex items-center gap-2 border-2 border-black px-6 py-3 text-sm font-medium disabled:opacity-40"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                啟動串流解碼（最多 30 則）
              </button>
              {streaming && (
                <button
                  type="button"
                  onClick={onCancel}
                  className="inline-flex items-center gap-2 border border-red-600 text-red-600 px-4 py-3 text-sm font-medium"
                >
                  <StopCircle className="h-4 w-4" />
                  取消
                </button>
              )}
            </div>

            {log && <p className="text-sm text-gray-700">{log}</p>}

            {/* SSE Progress */}
            {streamItems.length > 0 && (
              <BatchProgress
                items={streamItems}
                total={streamTotal}
                complete={streamComplete}
                onCancel={streaming ? onCancel : undefined}
              />
            )}

            {/* Queue controls */}
            <div className="flex flex-wrap gap-2 pt-2 border-t border-black/10">
              <button
                type="button"
                onClick={() => setLines("")}
                disabled={!lines.trim()}
                className="inline-flex items-center gap-1.5 border border-black/30 px-3 py-1.5 text-xs disabled:opacity-30"
              >
                清空佇列
              </button>
              <label className="inline-flex items-center gap-1.5 border border-black/30 px-3 py-1.5 text-xs cursor-pointer hover:border-black">
                <Upload className="h-3.5 w-3.5" />
                匯入 TXT/CSV
                <input
                  type="file"
                  accept=".txt,.csv"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const reader = new FileReader();
                    reader.onload = () => {
                      const text = reader.result as string;
                      setLines((prev) => (prev ? prev + "\n" : "") + text.trim());
                    };
                    reader.readAsText(file);
                    e.target.value = "";
                  }}
                />
              </label>
              <button
                type="button"
                onClick={() => {
                  const blob = new Blob([lines], { type: "text/plain" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url; a.download = "topic_queue.txt"; a.click();
                  URL.revokeObjectURL(url);
                }}
                disabled={!lines.trim()}
                className="inline-flex items-center gap-1.5 border border-black/30 px-3 py-1.5 text-xs disabled:opacity-30"
              >
                <Save className="h-3.5 w-3.5" />
                匯出佇列
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}


function LabStats() {
  const membership = useMembership();
  const { data, isLoading } = useQuery({
    queryKey: ["lab-stats"],
    queryFn: () => fetchMemberStorage("decode_note"),
    enabled: membership.signedIn,
  });

  if (!membership.signedIn) {
    return (
      <div className="border border-black/20 p-6 text-center text-sm text-gray-500">
        登入後可查看學習統計。
      </div>
    );
  }

  if (isLoading) {
    return <div className="text-sm text-gray-500 py-8 text-center">載入中…</div>;
  }

  const records = data ?? [];
  const byDateObj: Record<string, number> = {};
  const byCatObj: Record<string, number> = {};

  for (const r of records) {
    const date = (r.created_at || "").slice(0, 10);
    if (date) byDateObj[date] = (byDateObj[date] || 0) + 1;
    const cat = String((r.metadata as Record<string, unknown>)?.category || r.feature || "其他");
    byCatObj[cat] = (byCatObj[cat] || 0) + 1;
  }

  const dates = Object.entries(byDateObj).sort((a, b) => a[0].localeCompare(b[0])).slice(-14);
  const cats = Object.entries(byCatObj).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const uniqueDates = Object.keys(byDateObj).length;
  const uniqueCats = Object.keys(byCatObj).length;
  const maxCount = Math.max(...dates.map((d) => d[1]), 1);

  return (
    <div className="space-y-6">
      <div className="border border-black p-5 space-y-4">
        <h2 className="text-sm font-bold uppercase">解碼總覽</h2>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="border border-black/10 p-3">
            <p className="text-2xl font-bold">{records.length}</p>
            <p className="text-xs text-gray-500">總解碼數</p>
          </div>
          <div className="border border-black/10 p-3">
            <p className="text-2xl font-bold">{uniqueDates}</p>
            <p className="text-xs text-gray-500">活躍天數</p>
          </div>
          <div className="border border-black/10 p-3">
            <p className="text-2xl font-bold">{uniqueCats}</p>
            <p className="text-xs text-gray-500">涉及領域</p>
          </div>
        </div>

        {/* Daily bar chart */}
        {dates.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 uppercase mb-2">近 14 天解碼量</h3>
            <div className="flex items-end gap-1 h-24">
              {dates.map(([date, count]) => (
                <div key={date} className="flex-1 flex flex-col items-center gap-0.5">
                  <div
                    className="w-full bg-black min-h-[2px]"
                    style={{ height: `${(count / maxCount) * 100}%` }}
                    title={`${date}: ${count}`}
                  />
                  <span className="text-[9px] text-gray-400">{date.slice(5)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Category distribution */}
        {cats.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 uppercase mb-2">領域分布</h3>
            <div className="space-y-1">
              {cats.map(([cat, count]) => (
                <div key={cat} className="flex items-center gap-2 text-xs">
                  <span className="w-20 truncate text-gray-600">{cat}</span>
                  <div className="flex-1 bg-gray-100 h-3">
                    <div className="bg-black h-full" style={{ width: `${(count / records.length) * 100}%` }} />
                  </div>
                  <span className="text-gray-500 w-6 text-right">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {records.length === 0 && (
          <p className="text-sm text-gray-500 text-center py-4">尚無解碼紀錄。開始批量解碼後，統計資料會出現在這裡。</p>
        )}
      </div>
    </div>
  );
}
