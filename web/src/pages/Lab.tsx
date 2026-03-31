import { useState } from "react";
import { FlaskConical, Loader2, Sparkles } from "lucide-react";
import {
  batchDecode,
  suggestTopics,
  upsertLearnerContext,
  recommendAhaHooks,
  ingestAhaEvent,
  type AhaHookRecommendItem,
} from "../lib/api";

const CATEGORIES: Record<string, string[]> = {
  "語言與邏輯": ["英語辭源", "語言邏輯", "符號學", "修辭學"],
  "科學與技術": [
    "物理科學",
    "生物醫學",
    "神經科學",
    "量子力學",
    "人工智慧",
    "數學邏輯",
  ],
  "人文與社會": [
    "歷史文明",
    "政治法律",
    "社會心理",
    "哲學宗教",
    "軍事戰略",
    "古希臘神話",
    "考古發現",
  ],
  "商業與職場": [
    "商業商戰",
    "金融投資",
    "產品設計",
    "數位行銷",
    "職場政治",
    "管理學",
    "賽局理論",
  ],
  "生活與藝術": [
    "餐飲文化",
    "社交禮儀",
    "藝術美學",
    "影視文學",
    "運動健身",
    "流行文化",
    "心理療癒",
  ],
};

const FLAT = Object.values(CATEGORIES).flat();
const AGE_BANDS = ["13_15", "16_18", "19_22", "23_plus"] as const;
const REGIONS = ["TW-TPE", "TW-NWT", "TW-TXG", "TW-KHH", "HK", "SG"];

export default function Lab() {
  const [primary, setPrimary] = useState(FLAT[0] ?? "英語辭源");
  const [aux, setAux] = useState<string[]>([]);
  const [lines, setLines] = useState("");
  const [force, setForce] = useState(false);
  const [delay, setDelay] = useState(0.8);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string | null>(null);
  const [result, setResult] = useState<{
    saved: { word: string; saved_to: string }[];
    skipped: string[];
    errors: { word: string; detail: string }[];
  } | null>(null);
  const [tenantId, setTenantId] = useState("demo-tenant");
  const [profileId, setProfileId] = useState("demo-profile");
  const [ageBand, setAgeBand] = useState<(typeof AGE_BANDS)[number]>("16_18");
  const [regionCode, setRegionCode] = useState("TW-TPE");
  const [topicKey, setTopicKey] = useState("functions_equations");
  const [hooks, setHooks] = useState<AhaHookRecommendItem[]>([]);
  const [selectedHook, setSelectedHook] = useState<AhaHookRecommendItem | null>(null);
  const [hintShownAt, setHintShownAt] = useState<number | null>(null);

  const displayCat = primary + (aux.length ? ` + ${aux.join(" + ")}` : "");

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

  const onBatch = async () => {
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
    setResult(null);
    setBusy(true);
    try {
      const r = await batchDecode({
        words,
        primary_category: primary,
        aux_categories: aux,
        force_refresh: force,
        delay_sec: delay,
      });
      setResult(r);
      setLog(
        `完成：寫入 ${r.saved.length}、跳過 ${r.skipped.length}、錯誤 ${r.errors.length}`
      );
    } catch (e) {
      setLog(e instanceof Error ? e.message : "批量解碼失敗");
    } finally {
      setBusy(false);
    }
  };

  const onSaveContext = async () => {
    setLog(null);
    setBusy(true);
    try {
      await upsertLearnerContext({
        tenant_id: tenantId.trim(),
        profile_id: profileId.trim(),
        age_band: ageBand,
        region_code: regionCode.trim(),
        preferred_language: "zh-TW",
        metadata: { source: "web_lab" },
      });
      setLog("已儲存 learner context。");
    } catch (e) {
      setLog(e instanceof Error ? e.message : "儲存 context 失敗");
    } finally {
      setBusy(false);
    }
  };

  const onRecommend = async () => {
    setLog(null);
    setBusy(true);
    try {
      const list = await recommendAhaHooks({
        tenant_id: tenantId.trim(),
        profile_id: profileId.trim(),
        topic_key: topicKey.trim(),
        limit: 5,
      });
      setHooks(list);
      setSelectedHook(list[0] ?? null);
      setHintShownAt(null);
      setLog(`已取得 ${list.length} 則 Aha hook 推薦。`);
    } catch (e) {
      setLog(e instanceof Error ? e.message : "取得推薦失敗");
    } finally {
      setBusy(false);
    }
  };

  const onMarkHintShown = async () => {
    if (!selectedHook) {
      setLog("請先選擇一則 hook。");
      return;
    }
    setBusy(true);
    try {
      await ingestAhaEvent({
        tenant_id: tenantId.trim(),
        profile_id: profileId.trim(),
        event_type: "hint_shown",
        topic_key: topicKey.trim(),
        hook_id: selectedHook.id,
        hook_variant_id: selectedHook.hook_variant_id,
        metadata: { surface: "lab", source: "manual_mvp_loop" },
      });
      setHintShownAt(Date.now());
      setLog("已記錄 hint_shown。");
    } catch (e) {
      setLog(e instanceof Error ? e.message : "寫入事件失敗");
    } finally {
      setBusy(false);
    }
  };

  const onMarkAha = async () => {
    if (!selectedHook) {
      setLog("請先選擇一則 hook。");
      return;
    }
    setBusy(true);
    try {
      const latency = hintShownAt ? Math.max(Date.now() - hintShownAt, 0) : undefined;
      await ingestAhaEvent({
        tenant_id: tenantId.trim(),
        profile_id: profileId.trim(),
        event_type: "aha_reported",
        topic_key: topicKey.trim(),
        hook_id: selectedHook.id,
        hook_variant_id: selectedHook.hook_variant_id,
        latency_ms: latency,
        self_report_delta: 3,
        metadata: { surface: "lab", source: "manual_mvp_loop" },
      });
      setLog("已記錄 aha_reported。");
    } catch (e) {
      setLog(e instanceof Error ? e.message : "寫入事件失敗");
    } finally {
      setBusy(false);
    }
  };

  const onMarkAnswer = async (isCorrect: boolean) => {
    if (!selectedHook) {
      setLog("請先選擇一則 hook。");
      return;
    }
    setBusy(true);
    try {
      await ingestAhaEvent({
        tenant_id: tenantId.trim(),
        profile_id: profileId.trim(),
        event_type: "question_answered",
        topic_key: topicKey.trim(),
        hook_id: selectedHook.id,
        hook_variant_id: selectedHook.hook_variant_id,
        question_id: `lab-${topicKey.trim()}-${Date.now()}`,
        is_correct: isCorrect,
        metadata: { surface: "lab", source: "manual_mvp_loop" },
      });
      setLog(`已記錄 question_answered（${isCorrect ? "答對" : "答錯"}）。`);
    } catch (e) {
      setLog(e instanceof Error ? e.message : "寫入事件失敗");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <FlaskConical className="h-8 w-8 text-accent-glow" />
          解碼實驗室
        </h1>
        <p className="mt-1 text-ink-400 text-sm">
          對應原 Streamlit「跨領域批量解碼」。批量流程使用{" "}
          <strong className="text-ink-300">Gemini</strong>（
          <code className="text-ink-500">GEMINI_API_KEY</code>
          ）；結果寫入 Supabase 與本機 SQLite。
        </p>
      </div>

      <div className="glass-panel p-5 space-y-4">
        <div className="rounded-xl border border-white/10 bg-ink-900/30 p-4 space-y-3">
          <h2 className="text-sm font-semibold text-ink-200">Aha MVP 打點閉環（今日啟用）</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <input
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              placeholder="tenant_id"
              className="rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm text-white"
            />
            <input
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              placeholder="profile_id"
              className="rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm text-white"
            />
            <input
              value={topicKey}
              onChange={(e) => setTopicKey(e.target.value)}
              placeholder="topic_key"
              className="rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm text-white"
            />
            <select
              value={ageBand}
              onChange={(e) => setAgeBand(e.target.value as (typeof AGE_BANDS)[number])}
              className="rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm text-white"
            >
              {AGE_BANDS.map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
            <select
              value={regionCode}
              onChange={(e) => setRegionCode(e.target.value)}
              className="rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm text-white"
            >
              {REGIONS.map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              {
                step: 1,
                label: "儲存 learner context",
                onClick: onSaveContext,
                disabled: busy,
                cls: "border-white/15 text-ink-200 hover:bg-white/5",
              },
              {
                step: 2,
                label: "取得推薦 hooks",
                onClick: onRecommend,
                disabled: busy,
                cls: "border-white/15 text-ink-200 hover:bg-white/5",
              },
              {
                step: 3,
                label: "記錄 hint_shown",
                onClick: onMarkHintShown,
                disabled: busy || !selectedHook,
                cls: "border-white/15 text-ink-200 hover:bg-white/5",
              },
              {
                step: 4,
                label: "記錄 aha_reported",
                onClick: onMarkAha,
                disabled: busy || !selectedHook,
                cls: "border-white/15 text-ink-200 hover:bg-white/5",
              },
            ].map(({ step, label, onClick, disabled, cls }) => (
              <button
                key={step}
                type="button"
                disabled={disabled}
                onClick={onClick}
                data-track={`lab/step${step}`}
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition disabled:opacity-50 ${cls}`}
              >
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-ink-700 text-[10px] font-bold text-ink-300">
                  {step}
                </span>
                {label}
              </button>
            ))}
            <button
              type="button"
              disabled={busy || !selectedHook}
              onClick={() => onMarkAnswer(true)}
              data-track="lab/answer_correct"
              className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/30 px-3 py-2 text-xs text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50 transition"
            >
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-900/60 text-[10px] font-bold text-emerald-300">
                5
              </span>
              記錄答對
            </button>
            <button
              type="button"
              disabled={busy || !selectedHook}
              onClick={() => onMarkAnswer(false)}
              data-track="lab/answer_wrong"
              className="inline-flex items-center gap-2 rounded-lg border border-rose-500/30 px-3 py-2 text-xs text-rose-300 hover:bg-rose-500/10 disabled:opacity-50 transition"
            >
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-rose-900/60 text-[10px] font-bold text-rose-300">
                5
              </span>
              記錄答錯
            </button>
          </div>
          {hooks.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs text-ink-500">推薦 hook（點選一則作為事件上下文）</div>
              <div className="grid gap-2">
                {hooks.map((h) => (
                  <button
                    key={`${h.id}-${h.hook_variant_id}`}
                    type="button"
                    onClick={() => setSelectedHook(h)}
                    data-track="lab/hook_select"
                    className={[
                      "rounded-lg border px-3 py-2 text-left text-xs",
                      selectedHook?.id === h.id
                        ? "border-accent/50 bg-accent/10 text-white"
                        : "border-white/10 text-ink-300 hover:bg-white/5",
                    ].join(" ")}
                  >
                    <div className="font-medium">
                      {h.hook_type} · {h.hook_variant_id}
                    </div>
                    <div className="text-ink-400 line-clamp-2">{h.hook_text}</div>
                    <div className="text-[11px] text-ink-500">
                      score={h.score ?? 0} / aha_rate={h.metrics?.aha_rate ?? 0} / lift={h.metrics?.lift ?? 0}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-ink-500 uppercase">主核心領域</label>
            <select
              value={primary}
              onChange={(e) => {
                setPrimary(e.target.value);
                setAux((prev) => prev.filter((c) => c !== e.target.value));
              }}
              className="mt-1 w-full rounded-xl border border-white/10 bg-ink-900/60 px-3 py-2 text-sm text-white"
            >
              {FLAT.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-ink-500 uppercase mb-2 block">
              輔助視角（點選切換，可多選）
            </label>
            <div className="flex flex-wrap gap-1.5">
              {FLAT.filter((c) => c !== primary).map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() =>
                    setAux((prev) =>
                      prev.includes(c)
                        ? prev.filter((x) => x !== c)
                        : [...prev, c]
                    )
                  }
                  className={[
                    "rounded-full px-3 py-1 text-xs font-medium border transition-all duration-150",
                    aux.includes(c)
                      ? "border-accent/50 bg-accent/15 text-accent-glow ring-1 ring-accent/20"
                      : "border-white/10 text-ink-400 hover:border-white/25 hover:text-ink-200",
                  ].join(" ")}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        </div>
        <p className="text-sm text-ink-300">
          當前視角：<code className="text-accent-glow">{displayCat}</code>
        </p>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onSuggest}
            data-track="lab/suggest_topics"
            className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-4 py-2 text-sm text-ink-200 hover:bg-white/5 hover:text-white transition disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5 text-accent-glow" />
            隨機靈感（5 則中文主題）
          </button>
        </div>

        <textarea
          value={lines}
          onChange={(e) => setLines(e.target.value)}
          rows={10}
          placeholder="每行一個概念，例如：熵增定律"
          className="w-full rounded-xl border border-white/10 bg-ink-950/60 p-4 text-sm text-white font-mono"
        />

        <div className="flex flex-wrap gap-4 items-center text-sm text-ink-400">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
              className="rounded border-white/20"
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
              className="w-20 rounded-lg border border-white/10 bg-ink-900 px-2 py-1 text-white"
            />
          </label>
        </div>

        <button
          type="button"
          disabled={busy}
          onClick={onBatch}
          data-track="lab/batch_generate"
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-6 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          啟動批量深度解碼（最多 30 則）
        </button>

        {log && <p className="text-sm text-sky-300">{log}</p>}

        {result && (
          <div className="rounded-xl border border-white/10 bg-ink-900/40 p-4 text-sm space-y-2">
            {result.saved.length > 0 && (
              <div>
                <div className="text-emerald-400 font-medium">已寫入</div>
                <ul className="text-ink-300 list-disc pl-5">
                  {result.saved.map((s) => (
                    <li key={s.word}>
                      {s.word} → {s.saved_to}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {result.skipped.length > 0 && (
              <div>
                <div className="text-amber-400 font-medium">跳過（已存在）</div>
                <p className="text-ink-400">{result.skipped.join("、")}</p>
              </div>
            )}
            {result.errors.length > 0 && (
              <div>
                <div className="text-red-400 font-medium">錯誤</div>
                <ul className="text-ink-400 list-disc pl-5">
                  {result.errors.map((e) => (
                    <li key={e.word}>
                      {e.word}: {e.detail}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
