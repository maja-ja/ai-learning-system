import { CheckCircle2, Loader2, SkipForward, XCircle } from "lucide-react";
import type { KnowledgeRow } from "../types";

export type BatchItem = {
  i: number;
  total: number;
  word: string;
  status: "processing" | "done" | "skipped" | "error";
  detail?: string;
  saved_to?: string;
  row?: KnowledgeRow;
};

type Props = {
  items: BatchItem[];
  total: number;
  complete: boolean;
  onCancel?: () => void;
};

const statusIcon = {
  processing: <Loader2 className="h-4 w-4 animate-spin text-gray-500" />,
  done: <CheckCircle2 className="h-4 w-4 text-green-700" />,
  skipped: <SkipForward className="h-4 w-4 text-gray-400" />,
  error: <XCircle className="h-4 w-4 text-red-600" />,
};

const statusLabel = {
  processing: "解碼中…",
  done: "完成",
  skipped: "跳過",
  error: "錯誤",
};

export default function BatchProgress({ items, total, complete, onCancel }: Props) {
  const done = items.filter((i) => i.status !== "processing").length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="border border-black p-4 space-y-3">
      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <span>{done} / {total}</span>
          <span>{pct}%</span>
        </div>
        <div className="h-2 w-full bg-gray-200">
          <div
            className="h-full bg-black transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Item list */}
      <ul className="space-y-1 max-h-60 overflow-y-auto">
        {items.map((item) => (
          <li key={`${item.word}-${item.i}`} className="flex items-center gap-2 text-sm py-1 px-2 border-b border-black/5 last:border-0">
            {statusIcon[item.status]}
            <span className="font-medium min-w-0 truncate">{item.word}</span>
            <span className="ml-auto text-xs text-gray-500 shrink-0">{statusLabel[item.status]}</span>
            {item.status === "error" && item.detail && (
              <span className="text-xs text-red-500 truncate max-w-[200px]" title={item.detail}>
                {item.detail}
              </span>
            )}
          </li>
        ))}
      </ul>

      {/* Cancel / Complete */}
      {!complete && onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="border border-black px-3 py-1.5 text-xs font-medium"
        >
          中途取消
        </button>
      )}
      {complete && (
        <p className="text-xs text-gray-600">
          批量完成 — {items.filter((i) => i.status === "done").length} 成功
          、{items.filter((i) => i.status === "skipped").length} 跳過
          、{items.filter((i) => i.status === "error").length} 錯誤
        </p>
      )}
    </div>
  );
}
