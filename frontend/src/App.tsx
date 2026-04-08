import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import OverviewPage from "./pages/OverviewPage";
import DeliveryPage from "./pages/DeliveryPage";
import BottlenecksPage from "./pages/BottlenecksPage";
import AiImpactPage from "./pages/AiImpactPage";
import AiQualityPage from "./pages/AiQualityPage";
import IssueDetailPage from "./pages/IssueDetailPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/delivery" element={<DeliveryPage />} />
        <Route path="/bottlenecks" element={<BottlenecksPage />} />
        <Route path="/ai-impact" element={<AiImpactPage />} />
        <Route path="/ai-quality" element={<AiQualityPage />} />
        <Route path="/issues/:jiraKey" element={<IssueDetailPage />} />
      </Route>
    </Routes>
  );
}
