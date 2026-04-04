import { useEffect, useMemo, useState } from "react";
import { CreditCard, LockKeyhole, Wallet } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useMembership } from "../membership";
import type { CreditPack } from "../types";

type Props = {
  title?: string;
  description?: string;
};

export default function GenerationPaywall({
  title = "生成已鎖定",
  description = "登入並購買點數後即可生成。每次生成扣 5 元，用完再買。",
}: Props) {
  const location = useLocation();
  const membership = useMembership();
  const defaultPack = useMemo(
    () => membership.packs.find((p) => p.recommended)?.key || membership.packs[0]?.key || "",
    [membership.packs],
  ) || "";
  const [selectedPack, setSelectedPack] = useState(defaultPack);
  const [busy, setBusy] = useState<"linepay" | "paypal" | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedPack && defaultPack) setSelectedPack(defaultPack);
  }, [defaultPack, selectedPack]);

  const pack: CreditPack | undefined = membership.packs.find((p) => p.key === selectedPack);

  const start = async (provider: "linepay" | "paypal") => {
    if (!selectedPack) return;
    setBusy(provider);
    setErr(null);
    try {
      await membership.startCheckout(provider, selectedPack, `${location.pathname}${location.search}`);
    } catch (error) {
      setErr(error instanceof Error ? error.message : "付款流程啟動失敗");
      setBusy(null);
    }
  };

  return (
    <div className="border-2 border-black p-4 space-y-4">
      <div className="flex items-start gap-3">
        <LockKeyhole className="h-5 w-5 mt-0.5 shrink-0" />
        <div className="space-y-0.5">
          <p className="text-sm font-semibold">{title}</p>
          <p className="text-sm text-gray-600">{description}</p>
        </div>
      </div>

      {!membership.signedIn ? (
        <button
          type="button"
          onClick={membership.openSignIn}
          className="inline-flex items-center gap-2 border border-black px-4 py-2 text-sm font-medium"
        >
          <CreditCard className="h-4 w-4" />
          先登入會員
        </button>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Wallet className="h-4 w-4" />
            目前餘額 <strong className="text-black">{membership.walletCredits} 次</strong>
          </div>

          {/* 方案選擇 */}
          <div className="flex flex-wrap gap-2">
            {membership.packs.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => setSelectedPack(p.key)}
                className={[
                  "border px-3 py-2 text-xs text-left",
                  selectedPack === p.key
                    ? "border-2 border-black font-semibold"
                    : "border border-black/30",
                ].join(" ")}
              >
                <span className="block font-medium">{p.label}</span>
                <span className="block text-gray-500">NT${p.amountTwd} · {p.credits} 次</span>
              </button>
            ))}
          </div>

          {/* 付款按鈕 */}
          {pack && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => start("linepay")}
                className="border border-black px-4 py-2 text-sm font-medium disabled:opacity-40"
              >
                {busy === "linepay"
                  ? "前往中…"
                  : `Line Pay  NT$${pack.amountTwd}`}
              </button>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => start("paypal")}
                className="border border-black px-4 py-2 text-sm font-medium disabled:opacity-40"
              >
                {busy === "paypal"
                  ? "前往中…"
                  : `PayPal  NT$${pack.amountTwd}`}
              </button>
            </div>
          )}
        </div>
      )}

      {membership.error && <p className="text-xs text-red-600">{membership.error}</p>}
      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  );
}
