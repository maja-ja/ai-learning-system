import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

const cards = [
  {
    to: "/knowledge",
    title: "單字解碼",
    desc: "瀏覽知識庫、搜尋與閱讀深度知識卡。",
  },
  {
    to: "/lab",
    title: "解碼實驗室",
    desc: "跨領域批量解碼、隨機主題靈感，寫入雲端與本機。",
  },
  {
    to: "/roots",
    title: "高中英文字根",
    desc: "拉丁／希臘字根圖鑑與選擇題小測驗。",
  },
  {
    to: "/exam",
    title: "學測資料庫",
    desc: "密碼解鎖後瀏覽 Markdown 知識目錄、搜尋與新增。",
  },
  {
    to: "/handout",
    title: "講義與解碼",
    desc: "單筆 AI 解碼、講義生成、列印預覽與雲端筆記。",
  },
];

export default function Dashboard() {
  return (
    <div className="space-y-12">
      <section className="space-y-3 pt-2">
        <p className="text-xs font-mono uppercase tracking-widest text-gray-400">
          Etymon · Roots · Exam
        </p>
        <h1 className="text-4xl font-bold text-black leading-tight">
          用現代介面，讀懂字根與知識
        </h1>
        <p className="max-w-xl text-gray-500 text-base">
          清晰導航、響應式排版。資料由 FastAPI + Supabase／本地檔案驅動。
        </p>
      </section>

      <section className="grid gap-px border border-black sm:grid-cols-2">
        {cards.map(({ to, title, desc }, i) => (
          <Link
            key={to}
            to={to}
            className={[
              "group border-black bg-white p-6 transition-colors duration-100",
              "hover:bg-black hover:text-white",
              i === cards.length - 1 && cards.length % 2 !== 0
                ? "sm:col-span-2"
                : "",
              i > 0 ? "border-t border-black" : "",
              i === 1 || i === 3 ? "sm:border-t-0 sm:border-l border-black" : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <h2 className="text-lg font-semibold text-black group-hover:text-white transition-colors duration-100">
              {title}
            </h2>
            <p className="mt-1.5 text-sm text-gray-500 group-hover:text-gray-300 transition-colors duration-100 leading-relaxed">
              {desc}
            </p>
            <span className="mt-4 inline-flex items-center gap-1 text-xs font-mono text-gray-400 group-hover:text-gray-200 transition-all duration-100">
              進入 <ArrowRight className="h-3 w-3" />
            </span>
          </Link>
        ))}
      </section>
    </div>
  );
}
