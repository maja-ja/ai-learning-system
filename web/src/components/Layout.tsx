import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Beaker, BookOpen, FileWarning, Leaf, Sparkles, FileText, User } from "lucide-react";
import { useEffect, useState } from "react";
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/clerk-react";
import { initTracker, getSessionId } from "../lib/tracker";
import { fetchClickPrediction, type ClickPrediction } from "../lib/api";
import { SITE_NAME, SITE_ORIGIN } from "../site";
import { useMembership } from "../membership";
import ApiKeyBar from "./ApiKeyBar";

function actionToLabel(action: string, label: string): string {
  return label.trim() || action;
}

const nav = [
  { to: "/knowledge", label: "知識庫", icon: Sparkles },
  { to: "/roots",     label: "字根",   icon: Leaf },
  { to: "/lab",       label: "實驗室", icon: Beaker },
  { to: "/exam",      label: "學測",   icon: BookOpen },
  { to: "/handout",     label: "講義",     icon: FileText },
  { to: "/blackpaper", label: "Blackpaper", icon: FileWarning },
  { to: "/account",    label: "帳戶",     icon: User },
];

const activeClass = "border-black font-semibold text-black";
const idleClass   = "border-black/20 text-black";

export default function Layout() {
  const location = useLocation();
  const [predictions, setPredictions] = useState<ClickPrediction[]>([]);
  const membership = useMembership();

  useEffect(() => { initTracker(); }, []);

  useEffect(() => {
    let cancelled = false;
    fetchClickPrediction(getSessionId(), 5).then((p) => {
      if (!cancelled) setPredictions(p);
    });
    return () => { cancelled = true; };
  }, [location.pathname]);

  useEffect(() => {
    if (location.search.includes("billing=")) {
      membership.refreshMembership().catch(() => undefined);
    }
  }, [location.search, membership.refreshMembership]);

  return (
    <div className="min-h-screen flex flex-col bg-white text-black">
      <header className="sticky top-0 z-50 border-b-2 border-black bg-white">

        {/* Desktop */}
        <div className="hidden md:flex mx-auto max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <NavLink to="/" className="text-base font-bold tracking-tight">
            {SITE_NAME}
          </NavLink>
          <nav className="flex items-center gap-0">
            {nav.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                data-track={`nav${to}`}
                className={({ isActive }) =>
                  `px-3 py-1.5 text-sm border-b-2 ${isActive ? activeClass : idleClass}`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3 text-xs">
            <ApiKeyBar />
            {membership.clerkEnabled ? (
              <>
                <span className="border border-black/20 px-2.5 py-1 text-gray-600">
                  餘額 {membership.walletCredits} 次
                </span>
                <SignedOut>
                  <SignInButton mode="modal">
                    <button type="button" className="border border-black px-3 py-1.5 text-xs font-medium">
                      登入
                    </button>
                  </SignInButton>
                </SignedOut>
                <SignedIn><UserButton /></SignedIn>
              </>
            ) : (
              <span className="border border-black/20 px-2.5 py-1 text-gray-400 text-xs">
                會員未設定
              </span>
            )}
          </div>
        </div>

        {/* Mobile top bar: site name + login */}
        <div className="flex md:hidden items-center justify-between px-4 py-3">
          <NavLink to="/" className="text-base font-bold tracking-tight">
            {SITE_NAME}
          </NavLink>
          <div className="flex items-center gap-2 text-xs">
            {membership.clerkEnabled ? (
              <>
                <span className="text-gray-500">餘額 {membership.walletCredits} 次</span>
                <SignedOut>
                  <SignInButton mode="modal">
                    <button type="button" className="border border-black px-3 py-1.5 text-xs font-medium">
                      登入
                    </button>
                  </SignInButton>
                </SignedOut>
                <SignedIn><UserButton /></SignedIn>
              </>
            ) : null}
          </div>
        </div>

        {/* Mobile nav */}
        <div className="flex md:hidden overflow-x-auto border-t border-black/10 scrollbar-none">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              data-track={`nav${to}`}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-1.5 px-3 py-2 text-xs border-b-2 ${isActive ? activeClass : idleClass}`
              }
            >
              <Icon className="h-3 w-3" />
              {label}
            </NavLink>
          ))}
        </div>
      </header>

      <main key={location.key} className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 page-enter">
        <Outlet />
        {location.search.includes("billing=success") && (
          <div className="mt-6 border-2 border-black px-4 py-3 text-sm font-medium">
            付款完成，會員額度已刷新。
          </div>
        )}
        {location.search.includes("billing=failed") && (
          <div className="mt-6 border border-red-600 px-4 py-3 text-sm text-red-600">
            付款未完成，請再試一次。
          </div>
        )}
        {location.search.includes("billing=cancelled") && (
          <div className="mt-6 border border-black/30 px-4 py-3 text-sm text-gray-600">
            付款已取消。
          </div>
        )}
      </main>

      {predictions.length > 0 && (
        <div className="border-t border-black/10 py-2 px-4">
          <div className="mx-auto max-w-5xl flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <span className="text-gray-400">猜你接下來想看</span>
            {predictions.slice(0, 4).map((p) => {
              const displayLabel = actionToLabel(p.action, p.label);
              const navEntry = nav.find((n) => p.action.includes(n.to) || p.label === n.label);
              return navEntry ? (
                <NavLink
                  key={p.action}
                  to={navEntry.to}
                  data-track={`predict_hint${navEntry.to}`}
                  className="border border-black/20 px-2 py-0.5 text-gray-600"
                >
                  {displayLabel}
                  <span className="ml-1 text-gray-300">{Math.round(p.prob * 100)}%</span>
                </NavLink>
              ) : (
                <span key={p.action} className="border border-black/10 px-2 py-0.5 text-gray-500">
                  {displayLabel}
                </span>
              );
            })}
          </div>
        </div>
      )}

      <footer className="border-t-2 border-black py-4 text-center text-xs text-gray-400 space-y-1">
        <div>
          <a
            href={SITE_ORIGIN}
            className="font-medium text-gray-600 underline-offset-2 hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            {SITE_ORIGIN.replace(/^https:\/\//, "")}
          </a>
        </div>
        {import.meta.env.DEV && (
          <div>本機 API: <code className="font-mono">127.0.0.1:8000</code></div>
        )}
      </footer>
    </div>
  );
}
