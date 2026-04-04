import { lazy, Suspense } from "react";
import { Navigate, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";
import { Skeleton } from "./components/Skeleton";
import Knowledge from "./pages/Knowledge";

const Roots = lazy(() => import("./pages/Roots"));
const Handout = lazy(() => import("./pages/Handout"));
const Lab = lazy(() => import("./pages/Lab"));
const Exam = lazy(() => import("./pages/Exam"));
const Account = lazy(() => import("./pages/Account"));
const Blackpaper = lazy(() => import("./pages/Blackpaper"));

function PageFallback() {
  return (
    <div className="space-y-4 p-4">
      <Skeleton height="h-8" className="max-w-[240px]" />
      <Skeleton height="h-4" rows={6} />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/knowledge" replace />} />
            <Route path="/knowledge" element={<Knowledge />} />
            <Route path="/roots" element={<Roots />} />
            <Route path="/lab" element={<Lab />} />
            <Route path="/exam" element={<Exam />} />
            <Route path="/handout" element={<Handout />} />
            <Route path="/blackpaper" element={<Blackpaper />} />
            <Route path="/account" element={<Account />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
