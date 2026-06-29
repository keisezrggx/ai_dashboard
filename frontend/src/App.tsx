import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 h-full flex flex-col items-center justify-center">
      <h2 className="text-3xl font-bold text-gray-800 mb-4">{title}</h2>
      <p className="text-gray-500">This page is currently being migrated to React.</p>
    </div>
  );
}

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<PlaceholderPage title="Dashboard" />} />
        <Route path="/overview" element={<PlaceholderPage title="Overview" />} />
        <Route path="/sampling" element={<PlaceholderPage title="Sampling" />} />
        <Route path="/agent-sample" element={<PlaceholderPage title="Agent Sample" />} />
        <Route path="/audio-sample" element={<PlaceholderPage title="Audio Sample" />} />
        <Route path="/performance" element={<PlaceholderPage title="Performance" />} />
        <Route path="/hotline-calibration" element={<PlaceholderPage title="Hotline Calibration" />} />
      </Routes>
    </Layout>
  );
}

export default App;
