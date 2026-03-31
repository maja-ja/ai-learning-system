import { useEffect, useMemo, useState } from "react";
import {
  BookOpen, CheckCircle, HelpCircle, RefreshCw, Shuffle, Volume2, XCircle,
} from "lucide-react";
import type { RootEntry } from "../types";
import { fetchRoots } from "../lib/api";
import { Skeleton } from "../components/Skeleton";

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function speakWord(word: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(word);
  utt.lang = "en-US";
  utt.rate = 0.85;
  window.speechSynthesis.speak(utt);
}

export default function Roots() {
  const [tab, setTab]       = useState<"home" | "atlas" | "quiz">("home");
  const [roots, setRoots]   = useState<RootEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr]       = useState<string | null>(null);

  useEffect(() => {
    let ok = true;
    fetchRoots()
      .then((d) => { if (ok) setRoots(d); })
      .catch((e: Error) => { if (ok) setErr(e.message); })
      .finally(() => { if (ok) setLoading(false); });
    return () => { ok = false; };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">高中英文字根</h1>
          <p className="mt-1 text-ink-400">學測常見字根 · 首頁概覽 / 圖鑑 / 小測驗</p>
        </div>
        <div className="flex rounded-xl bg-ink-900/60 p-1 border border-white/10 w-fit">
          {(
            [
              ["home",  "首頁",   BookOpen],
              ["atlas", "字根圖鑑", BookOpen],
              ["quiz",  "小測驗",  HelpCircle],
            ] as const
          ).map(([key, label, Icon]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              data-track={`roots/tab/${key}`}
              className={[
                "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-150",
                tab === key
                  ? "bg-white/10 text-white shadow ring-1 ring-white/10"
                  : "text-ink-400 hover:text-ink-200 hover:bg-white/5",
              ].join(" ")}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {err && (
        <div className="rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-red-200 text-sm">
          {err}
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} height="h-14" className="rounded-2xl" />
          ))}
        </div>
      ) : tab === "home" ? (
        <div className="animate-fade-up"><Home roots={roots} onGo={(t) => setTab(t)} /></div>
      ) : tab === "atlas" ? (
        <div className="animate-fade-up"><Atlas roots={roots} /></div>
      ) : (
        <div className="animate-fade-up"><Quiz roots={roots} /></div>
      )}
    </div>
  );
}

function Home({ roots, onGo }: { roots: RootEntry[]; onGo: (tab: "atlas" | "quiz") => void }) {
  const nWords = roots.reduce((n, r) => n + (r.words?.length || 0), 0);
  const nLatin = roots.filter((r) => (r.origin || "").includes("Latin")).length;
  const nGreek = roots.filter((r) => (r.origin || "").includes("Greek")).length;
  const [todayRoot, setTodayRoot] = useState<RootEntry | null>(null);

  const refresh = () =>
    setTodayRoot(roots[Math.floor(Math.random() * roots.length)] ?? null);

  useEffect(() => {
    if (roots.length > 0) refresh();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roots.length]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "字根組數", value: roots.length },
          { label: "例字總數", value: nWords },
          { label: "拉丁語源", value: nLatin },
          { label: "希臘語源", value: nGreek },
        ].map(({ label, value }) => (
          <div key={label} className="glass-panel p-4 text-center">
            <div className="text-2xl font-bold text-white">{value}</div>
            <div className="text-xs text-ink-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {todayRoot && (
        <div className="glass-panel p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-400 uppercase tracking-wider">今日一字根</h2>
            <button
              type="button"
              onClick={refresh}
              data-track="roots/today_refresh"
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-ink-500 hover:text-ink-200 hover:bg-white/5"
            >
              <RefreshCw className="h-3.5 w-3.5" />換一個
            </button>
          </div>
          <div className="flex items-baseline gap-3 flex-wrap">
            <span className="font-mono text-3xl text-accent-glow">{todayRoot.root}</span>
            <span className="text-lg text-ink-300">— {todayRoot.meaning}</span>
            <span className="text-xs text-ink-500">{todayRoot.origin}</span>
          </div>
          {todayRoot.note && <p className="text-sm text-ink-300 leading-relaxed">{todayRoot.note}</p>}
          <div className="flex flex-wrap gap-2">
            {(todayRoot.words || []).slice(0, 6).map((w) => (
              <button
                key={w.w}
                type="button"
                onClick={() => speakWord(w.w)}
                className="flex items-center gap-1.5 rounded-lg bg-ink-800/50 border border-white/5 px-3 py-1.5 text-xs text-white hover:bg-ink-700/60 transition"
              >
                <Volume2 className="h-3 w-3 text-ink-500" />
                {w.w}<span className="text-ink-400"> · {w.zh}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid sm:grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => onGo("atlas")}
          data-track="roots/go_atlas"
          className="glass-panel p-5 text-left hover:ring-1 hover:ring-accent/30 transition-all"
        >
          <div className="font-semibold text-white mb-1">字根圖鑑</div>
          <p className="text-sm text-ink-400">依語源篩選 · 搜尋字根變體與例字</p>
        </button>
        <button
          type="button"
          onClick={() => onGo("quiz")}
          data-track="roots/go_quiz"
          className="glass-panel p-5 text-left hover:ring-1 hover:ring-accent/30 transition-all"
        >
          <div className="font-semibold text-white mb-1">小測驗</div>
          <p className="text-sm text-ink-400">字根 → 義 / 單字 → 根 雙模式隨機出題</p>
        </button>
      </div>
    </div>
  );
}

function Atlas({ roots }: { roots: RootEntry[] }) {
  const [origin, setOrigin] = useState("全部");
  const [q, setQ]           = useState("");

  const origins = useMemo(() => {
    const s = new Set(roots.map((r) => r.origin || "其他"));
    return ["全部", ...[...s].sort()];
  }, [roots]);

  const filtered = useMemo(() => {
    let list = roots;
    if (origin !== "全部") list = list.filter((r) => (r.origin || "").includes(origin));
    const qq = q.trim().toLowerCase();
    if (!qq) return list;
    return list.filter((r) => {
      if ((r.root || "").toLowerCase().includes(qq)) return true;
      if ((r.meaning || "").includes(qq)) return true;
      if ((r.variants || []).some((v) => v.toLowerCase().includes(qq))) return true;
      return (r.words || []).some((w) =>
        w.w.toLowerCase().includes(qq) || (w.zh || "").includes(qq)
      );
    });
  }, [roots, origin, q]);

  const nWords = roots.reduce((n, r) => n + (r.words?.length || 0), 0);

  return (
    <div className="space-y-4">
      <div className="text-sm text-ink-400">
        共 <strong className="text-white">{roots.length}</strong> 組字根 ·{" "}
        <strong className="text-white">{nWords}</strong> 個例字
      </div>
      <div className="flex flex-col sm:flex-row gap-3">
        <select
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
          className="rounded-xl border border-white/10 bg-ink-900/60 px-4 py-2.5 text-sm text-white"
        >
          {origins.map((o) => (
            <option key={o} value={o}>{o === "全部" ? "全部語源" : o}</option>
          ))}
        </select>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="搜尋字根、變體、例字…"
          className="flex-1 rounded-xl border border-white/10 bg-ink-900/60 px-4 py-2.5 text-sm text-white placeholder:text-ink-500 focus:border-accent/50 focus:outline-none"
        />
      </div>
      <p className="text-xs text-ink-500">顯示 {filtered.length} 組</p>
      <div className="space-y-2">
        {filtered.map((r) => (
          <details key={r.id} className="group glass-panel overflow-hidden open:ring-1 open:ring-accent/30">
            <summary className="cursor-pointer list-none px-5 py-4 flex items-center justify-between gap-4 hover:bg-white/5">
              <div>
                <span className="font-mono text-lg text-accent-glow">{r.root}</span>
                <span className="text-ink-300 ml-2">— {r.meaning}</span>
              </div>
              <span className="text-xs text-ink-500 shrink-0">{r.origin}</span>
            </summary>
            <div className="border-t border-white/10 px-5 py-4 space-y-3 text-sm text-ink-200">
              {(r.variants || []).length > 0 && (
                <p>
                  <span className="text-ink-500">變體 · </span>
                  {(r.variants || []).map((v) => (
                    <code key={v} className="mr-2 rounded bg-ink-800 px-1.5 py-0.5 text-xs">{v}</code>
                  ))}
                </p>
              )}
              {r.note && <p className="text-ink-300 leading-relaxed">{r.note}</p>}
              <ul className="grid sm:grid-cols-2 gap-2">
                {(r.words || []).map((w) => (
                  <li key={w.w} className="flex items-center justify-between rounded-lg bg-ink-800/50 px-3 py-2 border border-white/5 group/word">
                    <span>
                      <span className="font-medium text-white">{w.w}</span>
                      <span className="text-ink-400"> · {w.zh}</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => speakWord(w.w)}
                      className="opacity-0 group-hover/word:opacity-100 ml-2 p-1 rounded hover:bg-white/10 text-ink-500 hover:text-white transition"
                    >
                      <Volume2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

function Quiz({ roots }: { roots: RootEntry[] }) {
  const entries = useMemo(() => {
    const out: { root: string; w: string; zh: string }[] = [];
    roots.forEach((r) => {
      (r.words || []).forEach((w) => { out.push({ root: r.root, w: w.w, zh: w.zh }); });
    });
    return out;
  }, [roots]);

  const [mode, setMode]   = useState<"meaning" | "word">("meaning");
  const [q, setQ]         = useState<{
    kind: "meaning" | "word";
    correct: string;
    options: string[];
    extra?: RootEntry;
    word?: string;
    zh?: string;
  } | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore]   = useState(0);
  const [total, setTotal]   = useState(0);

  const nextQuestion = () => {
    if (roots.length < 4) return;
    if (mode === "meaning") {
      const correct = roots[Math.floor(Math.random() * roots.length)];
      const wrong = shuffle(roots.filter((r) => r.id !== correct.id)).slice(0, 3);
      const options = shuffle([correct.meaning, ...wrong.map((w) => w.meaning)]).slice(0, 4);
      setQ({ kind: "meaning", correct: correct.meaning, options, extra: correct });
    } else {
      if (entries.length < 4) return;
      const row = entries[Math.floor(Math.random() * entries.length)];
      const pool = [...new Set(roots.map((r) => r.root))].filter((x) => x !== row.root);
      if (pool.length < 3) return;
      const wrong = shuffle(pool).slice(0, 3);
      const options = shuffle([row.root, ...wrong]).slice(0, 4);
      setQ({ kind: "word", correct: row.root, options, word: row.w, zh: row.zh });
    }
    setPicked(null);
  };

  useEffect(() => {
    if (!q && roots.length >= 4) nextQuestion();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roots.length, mode]);

  if (roots.length < 4) return <p className="text-ink-400">字根資料不足，無法出題。</p>;
  if (!q) return <p className="text-ink-400">準備題目…</p>;
  const answered = picked !== null;

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex rounded-lg bg-ink-900/60 p-0.5 border border-white/10">
          {(["meaning", "word"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setQ(null); setPicked(null); }}
              className={`px-3 py-1.5 text-xs rounded-md ${mode === m ? "bg-white/10 text-white" : "text-ink-500"}`}
            >
              {m === "meaning" ? "字根 → 義" : "單字 → 根"}
            </button>
          ))}
        </div>
        <button type="button" onClick={() => nextQuestion()}
          className="flex items-center gap-1 text-xs text-ink-400 hover:text-white">
          <Shuffle className="h-3.5 w-3.5" /> 換題
        </button>
      </div>

      <div className="glass-panel p-6 space-y-4">
        <p className="text-xs text-ink-500 flex items-center gap-2">
          <span className="rounded-full bg-emerald-900/50 border border-emerald-500/30 px-2 py-0.5 text-emerald-300 font-medium">
            答對 {score}
          </span>
          <span className="text-ink-600">／</span>
          作答 {total}
          {total > 0 && <span className="text-ink-600">· {Math.round((score / total) * 100)}%</span>}
        </p>

        {q.kind === "meaning" && q.extra && (
          <>
            <p className="font-mono text-2xl text-accent-glow">{q.extra.root}</p>
            <p className="text-sm text-ink-400">{q.extra.origin}</p>
            <p className="text-sm text-ink-200">選出核心中文義：</p>
          </>
        )}
        {q.kind === "word" && (
          <>
            <div className="flex items-center gap-3">
              <p className="text-2xl font-semibold text-white">{q.word}</p>
              <button
                type="button"
                onClick={() => q.word && speakWord(q.word)}
                className="rounded p-1.5 hover:bg-white/10 text-ink-500 hover:text-white transition"
              >
                <Volume2 className="h-4 w-4" />
              </button>
            </div>
            <p className="text-sm text-ink-400">{q.zh}</p>
            <p className="text-sm text-ink-200">主要相關字根：</p>
          </>
        )}

        <div className="grid gap-2">
          {q.options.map((opt) => {
            let cls = "w-full rounded-xl border px-4 py-3 text-left text-sm transition-all duration-150 ";
            if (!answered) {
              cls += "border-white/10 bg-ink-800/40 hover:border-accent/40 hover:bg-ink-800 hover:-translate-y-px active:translate-y-0";
            } else {
              if (opt === q.correct)  cls += "border-emerald-500/60 bg-emerald-950/40 text-emerald-200";
              else if (opt === picked) cls += "border-red-500/50 bg-red-950/30 text-red-300";
              else                    cls += "border-white/5 opacity-40";
            }
            return (
              <button
                key={opt}
                type="button"
                disabled={answered}
                onClick={() => {
                  if (answered) return;
                  setPicked(opt);
                  setTotal((t) => t + 1);
                  if (opt === q.correct) setScore((s) => s + 1);
                }}
                className={cls}
              >
                {opt}
              </button>
            );
          })}
        </div>

        {answered && (
          <div className="space-y-2 animate-scale-in">
            <div className={`flex items-center gap-2 text-sm font-medium ${picked === q.correct ? "text-emerald-300" : "text-red-300"}`}>
              {picked === q.correct ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
              {picked === q.correct ? "答對了！" : `正確答案是：${q.correct}`}
            </div>
            <button
              type="button"
              onClick={() => nextQuestion()}
              className="w-full rounded-xl bg-accent/90 py-3 text-sm font-medium text-white hover:bg-accent transition-all duration-150"
            >
              下一題
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
