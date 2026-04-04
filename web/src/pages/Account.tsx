import { useCallback, useEffect, useState } from "react";
import { Loader2, Printer, Trash2, Wallet } from "lucide-react";
import { SignInButton, SignedOut } from "@clerk/clerk-react";
import {
  deleteMemberStorage,
  fetchHandoutPreviewHtml,
  fetchMemberStorage,
  type MemberStorageRecord,
} from "../lib/api";
import { useMembership } from "../membership";
import type { KnowledgeRow } from "../types";

type Tab = "overview" | "decode" | "handout";

function TopUpButtons() {
  const membership = useMembership();
  const [busy, setBusy] = useState<string | null>(null);
  const [sel, setSel] = useState(() => membership.packs[0]?.key || "");
  const [err, setErr] = useState<string | null>(null);

  const start = async (provider: "linepay" | "paypal") => {
    if (!sel) return;
    setBusy(provider);
    setErr(null);
    try { await membership.startCheckout(provider, sel, "/account"); }
    catch (e) { setErr(e instanceof Error ? e.message : "付款失敗"); setBusy(null); }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {membership.packs.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => setSel(p.key)}
            className={`border px-3 py-1.5 text-xs ${
              sel === p.key ? "border-2 border-black font-semibold" : "border border-black/30"
            }`}
          >
            {p.label} · NT${p.amountTwd} / {p.credits} 次
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!sel || busy !== null}
          onClick={() => start("linepay")}
          className="border border-black px-4 py-2 text-xs font-medium disabled:opacity-40"
        >
          {busy === "linepay" ? "前往中…" : "Line Pay 充值"}
        </button>
        <button
          type="button"
          disabled={!sel || busy !== null}
          onClick={() => start("paypal")}
          className="border border-black px-4 py-2 text-xs font-medium disabled:opacity-40"
        >
          {busy === "paypal" ? "前往中…" : "PayPal 充值"}
        </button>
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  );
}

export default function Account() {
  const membership = useMembership();
  const [tab, setTab] = useState<Tab>("overview");

  if (!membership.clerkEnabled) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">帳戶</h1>
        <p className="text-sm text-gray-500">尚未設定 VITE_CLERK_PUBLISHABLE_KEY，會員功能未啟用。</p>
      </div>
    );
  }

  if (!membership.signedIn) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">帳戶</h1>
        <p className="text-sm text-gray-600">登入後可查看點數餘額與生成紀錄。</p>
        <SignedOut>
          <SignInButton mode="modal">
            <button type="button" className="border-2 border-black px-4 py-2 text-sm font-medium">
              登入會員
            </button>
          </SignInButton>
        </SignedOut>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">帳戶</h1>

      {/* 概覽卡片 */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="border-2 border-black p-4 space-y-1">
          <p className="text-xs text-gray-500 uppercase font-medium">點數餘額</p>
          <p className="text-3xl font-bold">{membership.walletCredits}</p>
          <p className="text-xs text-gray-400">次生成</p>
        </div>
        <div className="border border-black/20 p-4 space-y-1">
          <p className="text-xs text-gray-500 uppercase font-medium">帳戶</p>
          <p className="text-sm font-medium truncate">{membership.profile?.displayName || "—"}</p>
          <p className="text-xs text-gray-400 truncate">{membership.profile?.email || "—"}</p>
        </div>
        <div className="border border-black/20 p-4 space-y-1">
          <p className="text-xs text-gray-500 uppercase font-medium">方案</p>
          <p className="text-sm font-medium">{membership.subscription?.planKey || "free"}</p>
          <p className="text-xs text-gray-400">{membership.subscription?.status || "—"}</p>
        </div>
      </div>

      {/* 充值 */}
      {membership.walletCredits === 0 ? (
        <div className="border-2 border-black p-4 space-y-2">
          <p className="text-sm font-semibold">點數不足，無法生成</p>
          <p className="text-xs text-gray-500">每次生成 NT$5，最低購買 NT$50（10 次）</p>
          <TopUpButtons />
        </div>
      ) : (
        <div className="border border-black/20 p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Wallet className="h-4 w-4 shrink-0" />
            <p className="text-sm">剩餘 <strong>{membership.walletCredits}</strong> 次，用完可再購買</p>
          </div>
          <TopUpButtons />
        </div>
      )}

      {/* 紀錄 tab */}
      <div className="flex gap-1 border-b border-black/20">
        {([
          ["overview", "總覽"],
          ["decode",   "解碼紀錄"],
          ["handout",  "講義紀錄"],
        ] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm border-b-2 -mb-px ${
              tab === key ? "border-black font-semibold" : "border-transparent text-gray-500"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewPanel />}
      {tab === "decode"   && <RecordPanel feature="decode_note" emptyText="尚無解碼紀錄" />}
      {tab === "handout"  && <HandoutRecordPanel />}
    </div>
  );
}

function OverviewPanel() {
  const [decodeCount, setDecodeCount] = useState<number | null>(null);
  const [handoutCount, setHandoutCount] = useState<number | null>(null);

  useEffect(() => {
    fetchMemberStorage("decode_note").then((r) => setDecodeCount(r.length)).catch(() => setDecodeCount(0));
    fetchMemberStorage("handout_generate").then((r) => setHandoutCount(r.length)).catch(() => setHandoutCount(0));
  }, []);

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="border border-black/20 p-4 space-y-1">
        <p className="text-sm font-medium">解碼紀錄</p>
        <p className="text-2xl font-bold">{decodeCount ?? "…"}</p>
        <p className="text-xs text-gray-400">筆 — 點「解碼紀錄」tab 查看</p>
      </div>
      <div className="border border-black/20 p-4 space-y-1">
        <p className="text-sm font-medium">講義紀錄</p>
        <p className="text-2xl font-bold">{handoutCount ?? "…"}</p>
        <p className="text-xs text-gray-400">份 — 點「講義紀錄」tab 查看</p>
      </div>
    </div>
  );
}

function RecordPanel({ feature, emptyText }: { feature: string; emptyText: string }) {
  const [records, setRecords] = useState<MemberStorageRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [sel, setSel] = useState<MemberStorageRecord | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRecords(await fetchMemberStorage(feature)); }
    catch { setRecords([]); }
    finally { setLoading(false); }
  }, [feature]);

  useEffect(() => { load(); }, [load]);

  const remove = async (id: string) => {
    await deleteMemberStorage(id);
    setRecords((prev) => prev.filter((r) => r.id !== id));
    if (sel?.id === id) setSel(null);
  };

  if (loading) return <p className="text-sm text-gray-400">載入中…</p>;
  if (!records.length) return <p className="text-sm text-gray-400">{emptyText}</p>;

  const card = sel ? (JSON.parse(JSON.stringify(sel.output_json || {}))) as KnowledgeRow : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-1 max-h-[65vh] overflow-y-auto">
        {records.map((r) => (
          <div
            key={r.id}
            onClick={() => setSel(r)}
            className={`flex items-start justify-between border px-3 py-2.5 cursor-pointer text-sm ${
              sel?.id === r.id ? "border-2 border-black" : "border border-black/20"
            }`}
          >
            <div className="min-w-0">
              <p className="font-medium truncate">{r.title || "(無標題)"}</p>
              <p className="text-xs text-gray-400">
                {new Date(r.created_at).toLocaleString("zh-TW")} ·{" "}
                {r.contribution_mode === "named_contribution" ? "具名貢獻" : "私人"}
              </p>
            </div>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); remove(r.id); }}
              className="ml-2 p-1 shrink-0 text-gray-400"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
      <div className="border border-black/20 p-4 max-h-[65vh] overflow-y-auto">
        {!sel ? (
          <p className="text-sm text-gray-400">點選左側一筆查看詳情</p>
        ) : card ? (
          <div className="space-y-3 text-sm">
            <p className="text-xs text-gray-400">{sel.title}</p>
            {Object.entries(card).map(([k, v]) =>
              v && typeof v === "string" ? (
                <div key={k}>
                  <p className="text-xs font-medium uppercase text-gray-400 mb-0.5">{k}</p>
                  <p className="whitespace-pre-wrap text-sm">{v}</p>
                </div>
              ) : null
            )}
            {sel.input_text && (
              <div>
                <p className="text-xs font-medium uppercase text-gray-400 mb-0.5">原始輸入</p>
                <pre className="text-xs text-gray-600 whitespace-pre-wrap border border-black/10 p-2">{sel.input_text}</pre>
              </div>
            )}
          </div>
        ) : (
          <pre className="text-xs text-gray-600 whitespace-pre-wrap">{sel.input_text}</pre>
        )}
      </div>
    </div>
  );
}

function HandoutRecordPanel() {
  const [records, setRecords] = useState<MemberStorageRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [sel, setSel] = useState<MemberStorageRecord | null>(null);
  const [previewing, setPreviewing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRecords(await fetchMemberStorage("handout_generate")); }
    catch { setRecords([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (id: string) => {
    await deleteMemberStorage(id);
    setRecords((prev) => prev.filter((r) => r.id !== id));
    if (sel?.id === id) setSel(null);
  };

  const preview = async () => {
    if (!sel?.output_text) return;
    setPreviewing(true);
    try {
      const html = await fetchHandoutPreviewHtml(sel.title, sel.output_text, null, 80);
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } finally { setPreviewing(false); }
  };

  if (loading) return <p className="text-sm text-gray-400">載入中…</p>;
  if (!records.length) return <p className="text-sm text-gray-400">尚無講義紀錄</p>;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-1 max-h-[65vh] overflow-y-auto">
        {records.map((r) => (
          <div
            key={r.id}
            onClick={() => setSel(r)}
            className={`flex items-start justify-between border px-3 py-2.5 cursor-pointer text-sm ${
              sel?.id === r.id ? "border-2 border-black" : "border border-black/20"
            }`}
          >
            <div className="min-w-0">
              <p className="font-medium truncate">{r.title || "(無標題)"}</p>
              <p className="text-xs text-gray-400">
                {new Date(r.created_at).toLocaleString("zh-TW")} ·{" "}
                {r.contribution_mode === "named_contribution" ? "具名貢獻" : "私人"}
              </p>
            </div>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); remove(r.id); }}
              className="ml-2 p-1 shrink-0 text-gray-400"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
      <div className="border border-black/20 p-4 max-h-[65vh] overflow-y-auto space-y-3">
        {!sel ? (
          <p className="text-sm text-gray-400">點選左側一份查看內容</p>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <p className="font-semibold text-sm">{sel.title}</p>
              <button
                type="button"
                disabled={previewing}
                onClick={preview}
                className="inline-flex items-center gap-1.5 border border-black px-3 py-1.5 text-xs font-medium disabled:opacity-40"
              >
                {previewing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Printer className="h-3.5 w-3.5" />}
                列印預覽
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-xs font-mono text-gray-700 border border-black/10 p-3 overflow-x-auto">
              {sel.output_text || "（無內容）"}
            </pre>
          </>
        )}
      </div>
    </div>
  );
}
