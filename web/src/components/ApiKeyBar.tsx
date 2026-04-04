import { useState } from "react";
import { Key, Check, X } from "lucide-react";
import { getUserGeminiKey, setUserGeminiKey, hasUserGeminiKey } from "../lib/userKeys";

export default function ApiKeyBar() {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(getUserGeminiKey);
  const hasKey = hasUserGeminiKey();

  const save = () => {
    setUserGeminiKey(value);
    setEditing(false);
  };

  const clear = () => {
    setUserGeminiKey("");
    setValue("");
    setEditing(false);
  };

  if (!editing && hasKey) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="flex items-center gap-1.5 border border-black/15 px-2.5 py-1 text-xs text-gray-500 hover:border-black/30 transition-colors"
        title="已設定 Gemini Key，點擊修改"
      >
        <Key className="h-3 w-3" />
        <span>Key ✓</span>
      </button>
    );
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="flex items-center gap-1.5 border border-orange-300 px-2.5 py-1 text-xs text-orange-600 hover:border-orange-400 transition-colors"
        title="設定您的 Gemini API Key 以啟用 AI 功能"
      >
        <Key className="h-3 w-3" />
        <span>設定 API Key</span>
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <Key className="h-3 w-3 text-gray-400 shrink-0" />
      <input
        type="password"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
        placeholder="AIzaSy..."
        autoFocus
        className="w-40 border border-black/30 px-2 py-0.5 text-xs font-mono"
      />
      <button type="button" onClick={save} className="p-0.5 hover:text-green-700" title="儲存">
        <Check className="h-3.5 w-3.5" />
      </button>
      {hasKey && (
        <button type="button" onClick={clear} className="p-0.5 hover:text-red-600" title="清除">
          <X className="h-3.5 w-3.5" />
        </button>
      )}
      <button type="button" onClick={() => setEditing(false)} className="text-[10px] text-gray-400 hover:text-black">
        取消
      </button>
    </div>
  );
}
