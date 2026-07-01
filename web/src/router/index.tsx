import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import MainLayout from '@/layouts/MainLayout';

// 路由级懒加载：按页面拆包，首屏只加载当前页面
const Dashboard = lazy(() => import('@/pages/Dashboard'));
const Chat = lazy(() => import('@/pages/Chat'));
const Knowledge = lazy(() => import('@/pages/Knowledge'));
const Graph = lazy(() => import('@/pages/Graph'));
const Retrieval = lazy(() => import('@/pages/Retrieval'));
const Agents = lazy(() => import('@/pages/Agents'));
const Tools = lazy(() => import('@/pages/Tools'));
const Memory = lazy(() => import('@/pages/Memory'));
const Observability = lazy(() => import('@/pages/Observability'));
const Eval = lazy(() => import('@/pages/Eval'));
const Sandbox = lazy(() => import('@/pages/Sandbox'));
const System = lazy(() => import('@/pages/System'));

export default function AppRoutes() {
  return (
    <Suspense
      fallback={
        <div style={{ height: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Spin size="large" />
        </div>
      }
    >
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/graph" element={<Graph />} />
          <Route path="/retrieval" element={<Retrieval />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/tools" element={<Tools />} />
          <Route path="/memory" element={<Memory />} />
          <Route path="/observability" element={<Observability />} />
          <Route path="/eval" element={<Eval />} />
          <Route path="/sandbox" element={<Sandbox />} />
          <Route path="/system" element={<System />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
