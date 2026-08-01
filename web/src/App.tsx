/**
 * 路由配置: 全部页面 lazy 加载控制首屏体积, Agent 页(ReactFlow)独立 chunk.
 */

import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/layout/Layout";
import { Spinner } from "./components/common";
import { SessionProvider } from "./stores/SessionContext";
import { ReportProvider } from "./stores/ReportContext";

const ChatPage = lazy(() => import("./pages/ChatPage"));
const AgentPage = lazy(() => import("./pages/AgentPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));
const KnowledgePage = lazy(() => import("./pages/KnowledgePage"));
const ToolsPage = lazy(() => import("./pages/ToolsPage"));
const MemoryPage = lazy(() => import("./pages/MemoryPage"));
const ObservabilityPage = lazy(() => import("./pages/ObservabilityPage"));
const EvalPage = lazy(() => import("./pages/EvalPage"));

function PageFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <Spinner text="页面加载中…" />
    </div>
  );
}

export default function App() {
  return (
    <SessionProvider>
      <ReportProvider>
        <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/chat" replace />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/agent" element={<AgentPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/knowledge" element={<KnowledgePage />} />
              <Route path="/tools" element={<ToolsPage />} />
              <Route path="/memory" element={<MemoryPage />} />
              <Route path="/observability" element={<ObservabilityPage />} />
              <Route path="/eval" element={<EvalPage />} />
              <Route path="*" element={<Navigate to="/chat" replace />} />
            </Route>
          </Routes>
        </Suspense>
        </BrowserRouter>
      </ReportProvider>
    </SessionProvider>
  );
}
