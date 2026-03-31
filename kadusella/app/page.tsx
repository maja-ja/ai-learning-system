import { Show, SignInButton, UserButton } from "@clerk/nextjs";

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#030712] text-zinc-100">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(56,189,248,0.22),transparent),radial-gradient(ellipse_60%_40%_at_100%_0%,rgba(167,139,250,0.18),transparent),radial-gradient(ellipse_50%_30%_at_0%_100%,rgba(34,211,238,0.12),transparent)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35] [background-image:linear-gradient(rgba(255,255,255,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.06)_1px,transparent_1px)] [background-size:64px_64px] [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]"
      />

      <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-8">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400/20 to-violet-500/30 ring-1 ring-white/10">
            <span className="text-lg font-semibold tracking-tight text-cyan-200">
              K
            </span>
          </span>
          <div>
            <p className="text-sm font-semibold tracking-wide text-white">
              Kadusella
            </p>
            <p className="text-xs text-zinc-500">Generative Learning OS</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Show when="signed-out">
            <SignInButton mode="modal">
              <button
                type="button"
                className="rounded-full bg-white/5 px-4 py-2 text-sm font-medium text-zinc-200 ring-1 ring-white/10 transition hover:bg-white/10"
              >
                登入
              </button>
            </SignInButton>
          </Show>
          <Show when="signed-in">
            <UserButton
              appearance={{
                elements: {
                  avatarBox: "h-9 w-9 ring-1 ring-white/10",
                },
              }}
            />
          </Show>
        </div>
      </header>

      <main className="relative z-10 mx-auto flex max-w-6xl flex-col gap-16 px-6 pb-24 pt-4 md:flex-row md:items-start md:gap-12">
        <section className="flex-1 space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-cyan-200/90 backdrop-blur-md">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-40" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
            </span>
            2026 · 解碼引擎已就緒
          </div>

          <h1 className="max-w-xl text-4xl font-semibold leading-[1.08] tracking-tight text-white md:text-5xl md:leading-[1.05]">
            把知識
            <span className="bg-gradient-to-r from-cyan-200 via-white to-violet-200 bg-clip-text text-transparent">
              {" "}
              解構成可檢索、可收費、可演化的資產
            </span>
          </h1>

          <p className="max-w-lg text-base leading-relaxed text-zinc-400 md:text-lg">
            多租戶資料主權、pgvector 語意檢索、解碼全流程稽核與訂閱紀錄 — 從
            Streamlit 原型邁向可商用的 Edge 架構。
          </p>

          <div className="flex flex-wrap gap-3">
            <Show when="signed-out">
              <SignInButton mode="modal">
                <button
                  type="button"
                  className="rounded-full bg-gradient-to-r from-cyan-500 to-violet-500 px-6 py-3 text-sm font-semibold text-slate-950 shadow-[0_0_40px_-10px_rgba(34,211,238,0.55)] transition hover:brightness-110"
                >
                  啟動控制台
                </button>
              </SignInButton>
            </Show>
            <Show when="signed-in">
              <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-200">
                已連線身分 · 可接軌 Supabase RLS
              </span>
            </Show>
            <a
              href="https://supabase.com/docs/guides/database/extensions/pgvector"
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-white/10 px-5 py-3 text-sm font-medium text-zinc-300 transition hover:border-white/20 hover:text-white"
            >
              向量檢索規格
            </a>
          </div>

          <dl className="grid max-w-lg grid-cols-2 gap-4 pt-4 text-sm text-zinc-500">
            <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-4 backdrop-blur">
              <dt className="text-xs uppercase tracking-wider text-zinc-600">
                Stack
              </dt>
              <dd className="mt-1 font-medium text-zinc-200">
                Next.js 16 · Supabase · Clerk
              </dd>
            </div>
            <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-4 backdrop-blur">
              <dt className="text-xs uppercase tracking-wider text-zinc-600">
                向量維度
              </dt>
              <dd className="mt-1 font-medium text-zinc-200">
                768-d · Gemini embed
              </dd>
            </div>
          </dl>
        </section>

        <aside className="flex w-full flex-1 flex-col gap-4 md:max-w-md">
          <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.04)_inset] backdrop-blur-xl">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
              Generative UI
            </p>
            <h2 className="mt-3 text-lg font-semibold text-white">
              介面隨角色與情境重組
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-zinc-400">
              學生、教師、機構三種租戶視圖預留於資料模型；首頁以流動光譜與玻璃層次呈現
              “活著的產品” 質感。
            </p>
            <ul className="mt-5 space-y-3 text-sm text-zinc-300">
              <li className="flex gap-2">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
                <span>
                  <strong className="text-white">decode</strong> Edge：12
                  欄位解碼 + 寫入{" "}
                  <code className="rounded bg-black/40 px-1.5 py-0.5 text-xs text-cyan-200">
                    decode_runs
                  </code>
                </span>
              </li>
              <li className="flex gap-2">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
                <span>
                  <strong className="text-white">rag-search</strong>：語意
                  ANN + RLS 租戶隔離
                </span>
              </li>
              <li className="flex gap-2">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                <span>
                  <strong className="text-white">handout-generate</strong>
                  ：延續講義大師提示詞管線
                </span>
              </li>
            </ul>
          </div>

          <div className="rounded-3xl border border-dashed border-white/15 bg-gradient-to-br from-white/[0.04] to-transparent p-6">
            <p className="text-xs text-zinc-500">Schema 亮點</p>
            <pre className="mt-3 overflow-x-auto text-[11px] leading-relaxed text-zinc-400">
              {`tenants · profiles · tenant_members
etymon_entries (+ embedding vector(768))
decode_runs · subscriptions · usage_events
match_etymon_entries()`}
            </pre>
          </div>
        </aside>
      </main>
    </div>
  );
}
