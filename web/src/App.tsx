import { Navigate, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Knowledge from "./pages/Knowledge";
import Roots from "./pages/Roots";
import Handout from "./pages/Handout";
import Lab from "./pages/Lab";
import Exam from "./pages/Exam";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/knowledge" replace />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/roots" element={<Roots />} />
        <Route path="/lab" element={<Lab />} />
        <Route path="/exam" element={<Exam />} />
        <Route path="/handout" element={<Handout />} />
      </Route>
    </Routes>
  );
}
