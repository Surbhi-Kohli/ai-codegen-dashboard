import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";

function Placeholder({ title }: { title: string }) {
  return <h2 className="text-xl font-semibold">{title}</h2>;
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<Placeholder title="Overview" />} />
        <Route path="/delivery" element={<Placeholder title="Delivery" />} />
        <Route path="/bottlenecks" element={<Placeholder title="Bottlenecks" />} />
        <Route path="/ai-impact" element={<Placeholder title="AI Impact" />} />
        <Route path="/ai-quality" element={<Placeholder title="AI Quality" />} />
        <Route path="/issues/:jiraKey" element={<Placeholder title="Issue Detail" />} />
      </Route>
    </Routes>
  );
}
