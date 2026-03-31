import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Beaker, BookOpen, Leaf, Sparkles, FileText } from "lucide-react";
import { useEffect } from "react";
import { initTracker } from "../lib/tracker";

const nav = [
  { to: "/knowledge", label: "知識庫", icon: Sparkles },
  { to: "/roots",     label: "字根",   icon: Leaf },
  { to: "/lab",       label: "實驗室", icon: Beaker },
  { to: "/exam",      label: "學測",   icon: BookOpen },
  { to: "/handout",   label: "講義",   icon: FileText },
];

export default function Layout() {
  const location = useLocation();

  useEffect(() => {
    initTracker();
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-white text-black">
      <header className="sticky top-0 z-50 border-b-2 border-black bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <NavLink to="/" className="text-base font-bold tracking-tight text-black">
            AI 教育工作站
          </NavLink>
          <nav className="hidden md:flex items-center gap-0">
            {nav.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                data-track={`nav${to}`}
                className={({ isActive }) =>
                  [
                    "px-3 py-1.5 text-sm border-b-2 transition-colors duration-100",
                    isActive
                      ? "border-black font-semibold text-black"
                      : "border-transparent text-gray-500 hover:text-black hover:border-gray-400",
                  ].join(" ")
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex md:hidden overflow-x-auto border-t border-black/10 scrollbar-none">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              data-track={`nav${to}`}
              className={({ isActive }) =>
                [
                  "flex shrink-0 items-center gap-1.5 px-3 py-2 text-xs border-b-2 transition-colors duration-100",
                  isActive
                    ? "border-black font-semibold text-black"
                    : "border-transparent text-gray-400 hover:text-black",
                ].join(" ")
              }
            >
              <Icon className="h-3 w-3" />
              {label}
            </NavLink>
          ))}
        </div>
      </header>
      <main
        key={location.key}
        className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 page-enter"
      >
        <Outlet />
      </main>

      {/* 預測提示條：根據歷史點擊序列推薦下一步 */}
      {predictions.length > 0 && (
        <div className="border-t border-black/10 bg-gray-50 py-2 px-4">
          <div className="mx-auto max-w-5xl flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <span className="font-medium text-gray-400">猜你接下來想看</span>
            {predictions.slice(0, 4).map((p) => {
              const displayLabel = actionToLabel(p.action, p.label);
              const navEntry = nav.find(
                (n) => p.action.includes(n.to) || p.label === n.label
              );
              return navEntry ? (
                <NavLink
                  key={p.action}
                  to={navEntry.to}
                  data-track={`predict_hint${navEntry.to}`}
                  className="rounded border border-black/15 bg-white px-2 py-0.5 text-gray-600 hover:border-black hover:text-black transition-colors"
                >
                  {displayLabel}
                  <span className="ml-1 text-gray-300">{Math.round(p.prob * 100)}%</span>
                </NavLink>
              ) : (
                <span
                  key={p.action}
                  className="rounded border border-black/10 bg-white px-2 py-0.5 text-gray-500"
                >
                  {displayLabel}
                </span>
              );
            })}
          </div>
        </div>
      )}

      <footer className="border-t-2 border-black py-4 text-center text-xs text-gray-400">
        後端 API: <code className="font-mono text-gray-600">127.0.0.1:8000</code>
      </footer>
    </div>
  );
}
