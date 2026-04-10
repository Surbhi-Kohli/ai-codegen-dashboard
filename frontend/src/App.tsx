import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import OverviewPage from "./pages/OverviewPage";
import AiImpactPage from "./pages/AiImpactPage";
import AiQualityPage from "./pages/AiQualityPage";
import IssueDetailPage from "./pages/IssueDetailPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/delivery" element={<Navigate to="/overview" replace />} />
        <Route path="/bottlenecks" element={<Navigate to="/overview" replace />} />
        <Route path="/ai-impact" element={<AiImpactPage />} />
        <Route path="/ai-quality" element={<AiQualityPage />} />
        <Route path="/issues/:jiraKey" element={<IssueDetailPage />} />
      </Route>
    </Routes>
  );
}
