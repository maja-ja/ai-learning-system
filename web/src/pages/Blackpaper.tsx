import { useState, useMemo } from "react";
import { AlertTriangle, ChevronDown, ExternalLink, Radio, Thermometer } from "lucide-react";

// ── Data ──

type HeatLevel = 1 | 2 | 3 | 4 | 5;

type Paper = {
  id: string;
  code: string;
  title: string;
  authors: string;
  year: number;
  journal?: string;
  doi?: string;
  heat: HeatLevel;
  tags: string[];
  tldr: string;
  whySilenced: string;
  implication: string;
  status: "retracted" | "buried" | "ignored" | "controversial" | "replicated-failure";
};

type Dossier = {
  id: string;
  label: string;
  description: string;
  papers: Paper[];
};

const STATUS_LABEL: Record<Paper["status"], string> = {
  "retracted": "已撤回",
  "buried": "被埋沒",
  "ignored": "被忽略",
  "controversial": "爭議中",
  "replicated-failure": "複製失敗",
};

const DOSSIERS: Dossier[] = [
  {
    id: "replication",
    label: "複製危機",
    description: "過半心理學經典實驗無法重現——整個領域的地基在搖。",
    papers: [
      {
        id: "rp-osf",
        code: "BP-2015-OSF",
        title: "Estimating the Reproducibility of Psychological Science",
        authors: "Open Science Collaboration",
        year: 2015,
        journal: "Science",
        doi: "10.1126/science.aac4716",
        heat: 5,
        tags: ["心理學", "複製危機", "方法論"],
        tldr: "100 篇心理學論文只有 36% 能被成功複製。這不是少數壞蘋果，是系統性問題。",
        whySilenced: "直接挑戰了數十年來「發表即為真」的學術信仰。許多教授的畢生研究被暗示為不可靠。",
        implication: "教科書級的「經典效應」可能有一半不存在。你學的心理學，有一半可能是錯的。",
        status: "controversial",
      },
      {
        id: "rp-ego",
        code: "BP-2016-EGO",
        title: "A Multi-Lab Pre-Registered Replication of the Ego-Depletion Effect",
        authors: "Hagger et al.",
        year: 2016,
        journal: "Perspectives on Psychological Science",
        heat: 4,
        tags: ["心理學", "自我損耗", "意志力"],
        tldr: "23 個實驗室同時測試「意志力會耗盡」這個著名效應——效果量趨近於零。",
        whySilenced: "自我損耗理論撐起了整個自制力研究分支、無數暢銷書、和 TED 演講。承認它不存在代價太大。",
        implication: "「意志力像肌肉會累」可能是學界最成功的都市傳說之一。",
        status: "replicated-failure",
      },
    ],
  },
  {
    id: "pharma",
    label: "藥廠與發表偏差",
    description: "負面結果消失了——因為沒人有興趣發表「這個藥沒用」。",
    papers: [
      {
        id: "ph-turner",
        code: "BP-2008-SSRI",
        title: "Selective Publication of Antidepressant Trials and Its Influence on Apparent Efficacy",
        authors: "Turner et al.",
        year: 2008,
        journal: "New England Journal of Medicine",
        doi: "10.1056/NEJMsa065779",
        heat: 5,
        tags: ["藥學", "發表偏差", "抗憂鬱藥"],
        tldr: "FDA 資料庫顯示 94% 的正面 SSRI 試驗被發表，但負面試驗只有 14% 被發表。",
        whySilenced: "揭露了藥廠系統性地隱藏不利數據。整個抗憂鬱藥產業的效果被嚴重高估。",
        implication: "你讀到的臨床試驗文獻，是被篩選過的勝利者集合——失敗者從未被看見。",
        status: "buried",
      },
      {
        id: "ph-ioannidis",
        code: "BP-2005-FALSE",
        title: "Why Most Published Research Findings Are False",
        authors: "John P.A. Ioannidis",
        year: 2005,
        journal: "PLOS Medicine",
        doi: "10.1371/journal.pmed.0020124",
        heat: 5,
        tags: ["方法論", "統計", "元科學"],
        tldr: "用數學證明：在多數研究領域中，超過一半的已發表結論是錯的。",
        whySilenced: "這篇論文本身成為了史上被引用最多的醫學方法論文章——但它的結論仍然被大多數研究者「知道但忽略」。",
        implication: "科學的自我修正機制比我們以為的慢得多。錯誤結論可以在文獻中存活數十年。",
        status: "ignored",
      },
    ],
  },
  {
    id: "nutrition",
    label: "營養學黑歷史",
    description: "糖業花錢買論文、脂肪被冤枉了半世紀。",
    papers: [
      {
        id: "nt-sugar",
        code: "BP-2016-SUGAR",
        title: "Sugar Industry and Coronary Heart Disease Research: A Historical Analysis",
        authors: "Kearns, Schmidt, Glantz",
        year: 2016,
        journal: "JAMA Internal Medicine",
        doi: "10.1001/jamainternmed.2016.5394",
        heat: 5,
        tags: ["營養學", "利益衝突", "心血管"],
        tldr: "1960 年代糖業協會付錢給哈佛學者，讓他們把心臟病的矛頭從糖指向脂肪。",
        whySilenced: "這個騙局成功了 50 年。整個低脂飲食運動、食物金字塔、和一整代人的飲食習慣都建立在被操縱的科學上。",
        implication: "你爸媽那一代被教導「脂肪是敵人」——這個信念的源頭是一筆賄賂。",
        status: "buried",
      },
    ],
  },
  {
    id: "academic-system",
    label: "學術體制缺陷",
    description: "發表或滅亡——這個系統本身就在製造垃圾科學。",
    papers: [
      {
        id: "ac-sokal",
        code: "BP-2018-HOAX",
        title: "Academic Grievance Studies and the Corruption of Scholarship",
        authors: "Lindsay, Boghossian, Pluckrose",
        year: 2018,
        heat: 4,
        tags: ["學術倫理", "同儕審查", "惡作劇"],
        tldr: "三位學者寫了 20 篇故意荒謬的假論文投稿，7 篇被接受發表。其中一篇把《我的奮鬥》改寫成女性主義論文。",
        whySilenced: "暴露了某些領域的同儕審查形同虛設。但討論這件事會被指控為「攻擊學術自由」。",
        implication: "「經過同儕審查」不等於「是真的」。審查的品質取決於審查者的動機。",
        status: "controversial",
      },
      {
        id: "ac-phack",
        code: "BP-2011-PHACK",
        title: "False-Positive Psychology: Undisclosed Flexibility in Data Collection and Analysis",
        authors: "Simmons, Nelson, Simonsohn",
        year: 2011,
        journal: "Psychological Science",
        doi: "10.1177/0956797611417632",
        heat: 4,
        tags: ["統計", "p-hacking", "方法論"],
        tldr: "示範了如何用完全合法的「研究者自由度」讓任何假設都能達到 p<0.05——包括證明聽披頭四會讓你變年輕。",
        whySilenced: "很多研究者知道自己在做類似的事，但承認等於否定自己的成果。",
        implication: "統計顯著性 ≠ 真實存在。p 值是可以被操縱的，而且操縱成本很低。",
        status: "controversial",
      },
    ],
  },
  {
    id: "ai-silence",
    label: "AI 與科技巨頭",
    description: "某些研究結論對公司市值不太方便。",
    papers: [
      {
        id: "ai-stochastic",
        code: "BP-2021-PARROT",
        title: "On the Dangers of Stochastic Parrots: Can Language Models Be Too Big?",
        authors: "Bender, Gebru, McMillan-Major, Shmitchell",
        year: 2021,
        journal: "FAccT",
        doi: "10.1145/3442188.3445922",
        heat: 5,
        tags: ["AI", "倫理", "大型語言模型"],
        tldr: "質疑大型語言模型的環境成本、訓練資料偏見、和「理解」的幻覺。",
        whySilenced: "共同作者 Timnit Gebru 因此論文被 Google 解僱。學界得到一個訊號：批評大公司的 AI 有職業風險。",
        implication: "AI 研究的方向正在被企業利益塑造。不方便的真相會被壓下來。",
        status: "controversial",
      },
    ],
  },
];

// ── Component ──

const heatBar = (level: HeatLevel) => (
  <span className="text-[10px] tracking-wider text-gray-400" title={`爭議指數 ${level}/5`}>
    {"●".repeat(level)}{"○".repeat(5 - level)}
  </span>
);

function PaperCard({ paper }: { paper: Paper }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`border group transition-all ${open ? "border-black/40" : "border-black/12 hover:border-black/25"}`}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full text-left px-4 py-3 flex items-start gap-3 transition-colors"
      >
        <div className="shrink-0 pt-0.5">
          <Radio className="h-3.5 w-3.5 text-gray-400 group-hover:text-black transition-colors" />
        </div>
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-[10px] font-mono text-gray-400">{paper.code}</code>
            <span className={`text-[10px] px-1.5 py-0.5 font-medium
              ${paper.status === "retracted" ? "border-l-2 border-l-red-400 pl-1.5 text-gray-600" :
                paper.status === "buried" ? "border-l-2 border-l-gray-400 pl-1.5 text-gray-500" :
                paper.status === "replicated-failure" ? "border-l-2 border-l-orange-400 pl-1.5 text-gray-600" :
                "border-l-2 border-l-black/25 pl-1.5 text-gray-500"
              }`}
            >
              {STATUS_LABEL[paper.status]}
            </span>
            {heatBar(paper.heat)}
          </div>
          <p className="text-sm font-medium leading-snug">{paper.title}</p>
          <p className="text-xs text-gray-500">
            {paper.authors} · {paper.year}
            {paper.journal && <span> · <em>{paper.journal}</em></span>}
          </p>
        </div>
        <ChevronDown className={`h-4 w-4 text-gray-400 shrink-0 mt-1 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-black/8">
          <div className="pt-3 space-y-2.5">
            <div>
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1">摘要</h4>
              <p className="text-sm leading-relaxed">{paper.tldr}</p>
            </div>
            <div>
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1">
                <AlertTriangle className="inline h-3 w-3 mr-1 -mt-0.5" />
                為何不被大講
              </h4>
              <p className="text-sm leading-relaxed text-gray-700">{paper.whySilenced}</p>
            </div>
            <div>
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1">
                <Thermometer className="inline h-3 w-3 mr-1 -mt-0.5" />
                對你的意義
              </h4>
              <p className="text-sm leading-relaxed font-medium">{paper.implication}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {paper.tags.map((t) => (
              <span key={t} className="text-[10px] border border-black/10 px-2 py-0.5 text-gray-400">{t}</span>
            ))}
          </div>
          {paper.doi && (
            <a
              href={`https://doi.org/${paper.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-black transition-colors"
            >
              <ExternalLink className="h-3 w-3" />
              DOI: {paper.doi}
            </a>
          )}
        </div>
      )}
    </div>
  );
}

export default function Blackpaper() {
  const [activeDossier, setActiveDossier] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const sq = search.trim().toLowerCase();
    return DOSSIERS.map((d) => ({
      ...d,
      papers: d.papers.filter((p) => {
        if (activeDossier && d.id !== activeDossier) return false;
        if (!sq) return true;
        return (
          p.title.toLowerCase().includes(sq) ||
          p.tldr.toLowerCase().includes(sq) ||
          p.authors.toLowerCase().includes(sq) ||
          p.tags.some((t) => t.toLowerCase().includes(sq))
        );
      }),
    })).filter((d) => d.papers.length > 0);
  }, [activeDossier, search]);

  const totalPapers = DOSSIERS.reduce((n, d) => n + d.papers.length, 0);

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header — research station style */}
      <div className="border border-black/30 p-5 space-y-3">
        <div className="flex items-center gap-2 text-[10px] font-mono text-gray-400 uppercase tracking-[0.2em]">
          <span className="inline-block h-1.5 w-1.5 border border-black/40 rounded-full" />
          STATION ETYMON · BLACKPAPER ARCHIVE
        </div>
        <h1 className="text-xl font-semibold tracking-tight">
          學界不願大講的論文
        </h1>
        <p className="text-sm text-gray-600 leading-relaxed">
          這些論文動搖了學科地基、揭露了系統性造假、或讓太多人不舒服。
          它們都經過同儕審查、刊登在頂級期刊——但你在教科書裡找不到它們。
        </p>
        <div className="flex items-center gap-4 text-xs text-gray-400 font-mono pt-1 border-t border-black/10">
          <span>{totalPapers} 份檔案</span>
          <span>{DOSSIERS.length} 個資料夾</span>
          <span>CLEARANCE: PUBLIC</span>
        </div>
      </div>

      {/* Search */}
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="搜尋論文、作者、標籤…"
        className="w-full border border-black/25 focus:border-black/50 px-4 py-2.5 text-sm font-mono placeholder:text-gray-300 outline-none transition-colors"
      />

      {/* Dossier filter */}
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setActiveDossier(null)}
          className={`px-3 py-1.5 text-xs font-medium transition-all ${
            !activeDossier ? "border-2 border-black/70" : "border border-black/15 text-gray-500 hover:border-black/30"
          }`}
        >
          全部資料夾
        </button>
        {DOSSIERS.map((d) => (
          <button
            key={d.id}
            type="button"
            onClick={() => setActiveDossier(activeDossier === d.id ? null : d.id)}
            className={`px-3 py-1.5 text-xs font-medium transition-all ${
              activeDossier === d.id ? "border-2 border-black/70" : "border border-black/15 text-gray-500 hover:border-black/30"
            }`}
          >
            {d.label}
            <span className="ml-1 opacity-40">({d.papers.length})</span>
          </button>
        ))}
      </div>

      {/* Dossiers */}
      <div className="space-y-6">
        {filtered.map((dossier) => (
          <section key={dossier.id} className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="h-px flex-1 bg-black/8" />
              <h2 className="text-[11px] font-medium uppercase tracking-widest text-gray-400 shrink-0">
                {dossier.label}
              </h2>
              <div className="h-px flex-1 bg-black/8" />
            </div>
            <p className="text-xs text-gray-500 text-center">{dossier.description}</p>
            <div className="space-y-2">
              {dossier.papers.map((paper) => (
                <PaperCard key={paper.id} paper={paper} />
              ))}
            </div>
          </section>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="border border-black/10 py-12 text-center">
          <p className="text-sm text-gray-400 font-mono">NO MATCHING RECORDS</p>
        </div>
      )}

      {/* Footer */}
      <div className="border-t border-black/10 pt-4 space-y-2 text-xs text-gray-400 font-mono">
        <p>所有論文均可透過 DOI 查閱原文。本頁不代表對任何研究結論的背書或否定。</p>
        <p>「不願大講」不等於「被禁止」——而是學術激勵結構讓這些真相難以被放大。</p>
        <p className="text-[10px] uppercase tracking-widest">END OF TRANSMISSION · STATION ETYMON</p>
      </div>
    </div>
  );
}
