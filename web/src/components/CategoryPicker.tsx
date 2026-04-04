import { useState } from "react";
import { ChevronDown, Search } from "lucide-react";

export const CATEGORIES: Record<string, string[]> = {
  "語言與邏輯": ["英語辭源", "語言邏輯", "符號學", "修辭學"],
  "科學與技術": ["物理科學", "生物醫學", "神經科學", "量子力學", "人工智慧", "數學邏輯"],
  "人文與社會": ["歷史文明", "政治法律", "社會心理", "哲學宗教", "軍事戰略", "古希臘神話", "考古發現"],
  "商業與職場": ["商業商戰", "金融投資", "產品設計", "數位行銷", "職場政治", "管理學", "賽局理論"],
  "生活與藝術": ["餐飲文化", "社交禮儀", "藝術美學", "影視文學", "運動健身", "流行文化", "心理療癒"],
};

export const ALL_CATEGORIES = Object.values(CATEGORIES).flat();

type Props = {
  primary: string;
  aux: string[];
  onPrimaryChange: (v: string) => void;
  onAuxChange: (v: string[]) => void;
};

export default function CategoryPicker({ primary, aux, onPrimaryChange, onAuxChange }: Props) {
  const [search, setSearch] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggle = (group: string) =>
    setCollapsed((p) => ({ ...p, [group]: !p[group] }));

  const toggleAux = (c: string) =>
    onAuxChange(aux.includes(c) ? aux.filter((x) => x !== c) : [...aux, c]);

  const sq = search.trim().toLowerCase();
  const displayCat = primary + (aux.length ? ` + ${aux.join(" + ")}` : "");

  return (
    <div className="space-y-3">
      {/* Primary selector */}
      <div>
        <label className="text-xs font-medium uppercase">主核心領域</label>
        <select
          value={primary}
          onChange={(e) => {
            onPrimaryChange(e.target.value);
            onAuxChange(aux.filter((c) => c !== e.target.value));
          }}
          className="mt-1 w-full border border-black px-3 py-2 text-sm"
        >
          {ALL_CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* Aux search */}
      <div>
        <label className="text-xs font-medium uppercase block mb-2">
          輔助視角（可多選）{aux.length > 0 && <span className="ml-1 text-gray-500">· 已選 {aux.length}</span>}
        </label>
        <div className="relative mb-2">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜尋領域…"
            className="w-full border border-black/30 pl-8 pr-3 py-1.5 text-xs"
          />
        </div>

        {/* Grouped accordion */}
        <div className="space-y-1">
          {Object.entries(CATEGORIES).map(([group, items]) => {
            const filtered = items.filter(
              (c) => c !== primary && (!sq || c.toLowerCase().includes(sq)),
            );
            if (!filtered.length) return null;
            const isOpen = !collapsed[group];
            const selectedCount = filtered.filter((c) => aux.includes(c)).length;

            return (
              <div key={group} className="border border-black/10">
                <button
                  type="button"
                  onClick={() => toggle(group)}
                  className="w-full flex items-center justify-between px-3 py-1.5 text-xs font-medium hover:bg-gray-50"
                >
                  <span>
                    {group}
                    {selectedCount > 0 && (
                      <span className="ml-1.5 text-gray-500">({selectedCount})</span>
                    )}
                  </span>
                  <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </button>
                {isOpen && (
                  <div className="flex flex-wrap gap-1.5 px-3 pb-2">
                    {filtered.map((c) => (
                      <button
                        key={c}
                        type="button"
                        onClick={() => toggleAux(c)}
                        className={[
                          "border px-2.5 py-1 text-xs font-medium transition-all",
                          aux.includes(c)
                            ? "border-2 border-black bg-black text-white"
                            : "border border-black/30 hover:border-black/60",
                        ].join(" ")}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <p className="text-sm">
        當前視角：<code className="text-xs bg-gray-100 px-1.5 py-0.5">{displayCat}</code>
      </p>
    </div>
  );
}
