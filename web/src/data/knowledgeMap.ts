export interface MapNode {
  id: string;
  label: string;
  layer: number;
  description?: string;
}

export interface MapEdge {
  from: string;
  to: string;
}

export interface MapDomain {
  id: string;
  label: string;
  accent: string;
  nodes: MapNode[];
  edges: MapEdge[];
}

export const LAYER_LABELS: Record<number, string> = {
  0: "公理",
  1: "基礎",
  2: "理論",
  3: "應用",
  4: "領域",
};

export const KNOWLEDGE_MAP: MapDomain[] = [
  {
    id: "math",
    label: "數學",
    accent: "#6366f1",
    nodes: [
      { id: "math-axiom",    label: "公理系統",    layer: 0 },
      { id: "math-set",      label: "集合論",      layer: 1 },
      { id: "math-logic",    label: "形式邏輯",    layer: 1 },
      { id: "math-analysis", label: "數學分析",    layer: 2 },
      { id: "math-algebra",  label: "代數結構",    layer: 2 },
      { id: "math-geo",      label: "幾何學",      layer: 2 },
      { id: "math-prob",     label: "機率論",      layer: 3 },
      { id: "math-calc",     label: "微積分",      layer: 3 },
      { id: "math-linalg",   label: "線性代數",    layer: 3 },
      { id: "math-ml",       label: "機器學習",    layer: 4 },
      { id: "math-qm",       label: "量子力學",    layer: 4 },
      { id: "math-cg",       label: "電腦圖形學",  layer: 4 },
    ],
    edges: [
      { from: "math-axiom",    to: "math-set" },
      { from: "math-axiom",    to: "math-logic" },
      { from: "math-set",      to: "math-analysis" },
      { from: "math-set",      to: "math-algebra" },
      { from: "math-set",      to: "math-geo" },
      { from: "math-logic",    to: "math-analysis" },
      { from: "math-logic",    to: "math-algebra" },
      { from: "math-analysis", to: "math-prob" },
      { from: "math-analysis", to: "math-calc" },
      { from: "math-algebra",  to: "math-linalg" },
      { from: "math-geo",      to: "math-calc" },
      { from: "math-prob",     to: "math-ml" },
      { from: "math-calc",     to: "math-ml" },
      { from: "math-calc",     to: "math-qm" },
      { from: "math-linalg",   to: "math-ml" },
      { from: "math-linalg",   to: "math-cg" },
      { from: "math-qm",       to: "math-cg" },
    ],
  },
  {
    id: "science",
    label: "自然科學",
    accent: "#10b981",
    nodes: [
      { id: "sci-axiom",   label: "公理系統", layer: 0 },
      { id: "sci-physics", label: "物理定律", layer: 1 },
      { id: "sci-chem",    label: "化學定律", layer: 1 },
      { id: "sci-mech",    label: "力學",     layer: 2 },
      { id: "sci-em",      label: "電磁學",   layer: 2 },
      { id: "sci-thermo",  label: "熱力學",   layer: 2 },
      { id: "sci-qm",      label: "量子力學", layer: 3 },
      { id: "sci-rel",     label: "相對論",   layer: 3 },
      { id: "sci-eng",     label: "工程學",   layer: 4 },
      { id: "sci-mat",     label: "材料科學", layer: 4 },
    ],
    edges: [
      { from: "sci-axiom",   to: "sci-physics" },
      { from: "sci-axiom",   to: "sci-chem" },
      { from: "sci-physics", to: "sci-mech" },
      { from: "sci-physics", to: "sci-em" },
      { from: "sci-physics", to: "sci-thermo" },
      { from: "sci-chem",    to: "sci-thermo" },
      { from: "sci-mech",    to: "sci-qm" },
      { from: "sci-em",      to: "sci-qm" },
      { from: "sci-em",      to: "sci-rel" },
      { from: "sci-thermo",  to: "sci-qm" },
      { from: "sci-qm",      to: "sci-eng" },
      { from: "sci-qm",      to: "sci-mat" },
      { from: "sci-rel",     to: "sci-eng" },
    ],
  },
  {
    id: "humanities",
    label: "人文社會",
    accent: "#f59e0b",
    nodes: [
      { id: "hum-axiom",   label: "公理系統", layer: 0 },
      { id: "hum-logic",   label: "邏輯",     layer: 1 },
      { id: "hum-ethics",  label: "倫理學",   layer: 1 },
      { id: "hum-econ",    label: "經濟學",   layer: 2 },
      { id: "hum-soc",     label: "社會學",   layer: 2 },
      { id: "hum-psych",   label: "心理學",   layer: 2 },
      { id: "hum-pol",     label: "政治學",   layer: 3 },
      { id: "hum-law",     label: "法學",     layer: 3 },
      { id: "hum-edu",     label: "教育學",   layer: 3 },
      { id: "hum-policy",  label: "政策",     layer: 4 },
      { id: "hum-inst",    label: "制度",     layer: 4 },
      { id: "hum-culture", label: "文化",     layer: 4 },
    ],
    edges: [
      { from: "hum-axiom",  to: "hum-logic" },
      { from: "hum-axiom",  to: "hum-ethics" },
      { from: "hum-logic",  to: "hum-econ" },
      { from: "hum-logic",  to: "hum-soc" },
      { from: "hum-ethics", to: "hum-econ" },
      { from: "hum-ethics", to: "hum-soc" },
      { from: "hum-ethics", to: "hum-psych" },
      { from: "hum-econ",   to: "hum-pol" },
      { from: "hum-econ",   to: "hum-law" },
      { from: "hum-soc",    to: "hum-pol" },
      { from: "hum-soc",    to: "hum-edu" },
      { from: "hum-psych",  to: "hum-edu" },
      { from: "hum-pol",    to: "hum-policy" },
      { from: "hum-pol",    to: "hum-inst" },
      { from: "hum-law",    to: "hum-policy" },
      { from: "hum-law",    to: "hum-inst" },
      { from: "hum-edu",    to: "hum-culture" },
      { from: "hum-inst",   to: "hum-culture" },
    ],
  },
];
