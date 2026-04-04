import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { API_BASE } from "../lib/api";

type GraphNode = {
  id: string;
  label: string;
  category?: string;
  type: "word" | "category";
};
type GraphEdge = { from: string; to: string };
type GraphData = { nodes: GraphNode[]; edges: GraphEdge[]; total: number };

async function fetchGraph(): Promise<GraphData> {
  const base = API_BASE || "";
  const r = await fetch(`${base}/api/knowledge/graph`);
  if (!r.ok) throw new Error("無法載入知識圖譜");
  return r.json();
}

const PALETTE = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#14b8a6",
];

function colorForCategory(cat: string, cats: string[]): string {
  const idx = cats.indexOf(cat);
  return PALETTE[idx % PALETTE.length];
}

export default function KnowledgeMapView() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [activeCat, setActiveCat] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["knowledge-graph"],
    queryFn: fetchGraph,
  });

  const categories = useMemo(() => {
    if (!data) return [];
    return data.nodes
      .filter((n) => n.type === "category")
      .map((n) => n.label)
      .sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return { nodes: [], edges: [] };
    const sq = search.trim().toLowerCase();
    let nodes = data.nodes;
    let edges = data.edges;

    if (activeCat) {
      const catNode = nodes.find((n) => n.type === "category" && n.label === activeCat);
      const catId = catNode?.id;
      const wordIds = new Set(
        edges.filter((e) => e.from === catId).map((e) => e.to),
      );
      if (catId) wordIds.add(catId);
      nodes = nodes.filter((n) => wordIds.has(n.id));
      edges = edges.filter((e) => wordIds.has(e.from) || wordIds.has(e.to));
    }

    if (sq) {
      const matching = new Set(
        nodes.filter((n) => n.label.toLowerCase().includes(sq)).map((n) => n.id),
      );
      // also include category parents
      edges.forEach((e) => {
        if (matching.has(e.to)) matching.add(e.from);
      });
      nodes = nodes.filter((n) => matching.has(n.id));
      edges = edges.filter((e) => matching.has(e.from) && matching.has(e.to));
    }

    return { nodes, edges };
  }, [data, activeCat, search]);

  const onNodeClick = (node: GraphNode) => {
    if (node.type === "category") {
      setActiveCat((prev) => (prev === node.label ? null : node.label));
    } else {
      navigate("/handout", {
        state: { draft: `# ${node.label}\n\n`, title: node.label },
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-500">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        載入知識圖譜…
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-black/20 p-4 text-sm text-red-600">
        {error instanceof Error ? error.message : "載入失敗"}
      </div>
    );
  }

  if (!data || data.total === 0) {
    return (
      <div className="border border-black/20 p-6 text-center text-sm text-gray-500">
        知識庫尚無資料。請先在「批量解碼」tab 生成知識卡。
      </div>
    );
  }

  // Layout: category nodes at top, word nodes flowing below
  const catNodes = filtered.nodes.filter((n) => n.type === "category");
  const wordNodes = filtered.nodes.filter((n) => n.type === "word");

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜尋概念…"
            className="w-full border border-black/30 pl-8 pr-3 py-1.5 text-xs"
          />
        </div>
        <span className="text-xs text-gray-400">
          {filtered.nodes.filter((n) => n.type === "word").length} / {data.total} 概念
        </span>
      </div>

      {/* Category filter chips */}
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setActiveCat(null)}
          className={[
            "border px-3 py-1 text-xs font-medium",
            !activeCat ? "border-2 border-black" : "border border-black/20 text-gray-400",
          ].join(" ")}
        >
          全部
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setActiveCat((prev) => (prev === cat ? null : cat))}
            className={[
              "flex items-center gap-1.5 border px-3 py-1 text-xs font-medium",
              activeCat === cat
                ? "border-2 border-black"
                : "border border-black/20 text-gray-500 hover:border-black/40",
            ].join(" ")}
          >
            <span
              className="h-2 w-2 rounded-full shrink-0"
              style={{ background: colorForCategory(cat, categories) }}
            />
            {cat}
          </button>
        ))}
      </div>

      <p className="text-xs text-gray-400">
        點擊領域篩選；點擊概念節點進入講義拆解。
      </p>

      {/* Grid of category groups */}
      <div className="space-y-4">
        {catNodes.map((catNode) => {
          const color = colorForCategory(catNode.label, categories);
          const children = wordNodes.filter(
            (w) => w.category === catNode.label || filtered.edges.some(
              (e) => e.from === catNode.id && e.to === w.id,
            ),
          );
          if (!children.length) return null;

          return (
            <div key={catNode.id} className="border border-black/15 p-3 space-y-2">
              <div className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full shrink-0"
                  style={{ background: color }}
                />
                <span className="text-sm font-bold">{catNode.label}</span>
                <span className="text-xs text-gray-400 ml-auto">{children.length} 個概念</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {children.map((word) => (
                  <button
                    key={word.id}
                    type="button"
                    onClick={() => onNodeClick(word)}
                    className="border border-black/20 px-3 py-1.5 text-xs hover:border-black hover:bg-black hover:text-white transition-colors"
                    style={{ borderLeftColor: color, borderLeftWidth: 3 }}
                  >
                    {word.label}
                  </button>
                ))}
              </div>
            </div>
          );
        })}

        {/* Words without a matching category in filtered view */}
        {wordNodes.filter((w) => !catNodes.some((c) =>
          filtered.edges.some((e) => e.from === c.id && e.to === w.id)
        )).length > 0 && !activeCat && (
          <div className="border border-black/15 p-3 space-y-2">
            <span className="text-sm font-bold text-gray-400">其他</span>
            <div className="flex flex-wrap gap-1.5">
              {wordNodes
                .filter((w) => !catNodes.some((c) =>
                  filtered.edges.some((e) => e.from === c.id && e.to === w.id)
                ))
                .map((word) => (
                  <button
                    key={word.id}
                    type="button"
                    onClick={() => onNodeClick(word)}
                    className="border border-black/20 px-3 py-1.5 text-xs hover:border-black hover:bg-black hover:text-white transition-colors"
                  >
                    {word.label}
                  </button>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
