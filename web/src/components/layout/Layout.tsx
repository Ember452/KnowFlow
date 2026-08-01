/**
 * 整体布局: 深色侧边导航(SVG 图标) + 顶栏(健康状态轮询/用户 ID) + 主内容区.
 */

import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { readyz } from "../../api/endpoints";
import { Button, IconButton } from "../common";
import { Icon, type IconName } from "../icons";
import { usePolling } from "../../hooks/usePolling";
import { useSession } from "../../stores/SessionContext";
import { useTheme } from "../../hooks/useTheme";
import type { ReadyzData } from "../../types/api";

const NAV_ITEMS: { to: string; label: string; icon: IconName }[] = [
  { to: "/chat", label: "对话", icon: "chat" },
  { to: "/agent", label: "Agent 编排", icon: "agent" },
  { to: "/reports", label: "研究报告", icon: "report" },
  { to: "/knowledge", label: "知识库", icon: "knowledge" },
  { to: "/tools", label: "工具治理", icon: "tools" },
  { to: "/memory", label: "记忆管理", icon: "memory" },
  { to: "/observability", label: "可观测", icon: "observability" },
  { to: "/eval", label: "评测中心", icon: "eval" },
];

function HealthIndicator() {
  const { data, error } = usePolling<ReadyzData>(
    async () => {
      const resp = await readyz();
      if (!resp.data) throw new Error("readyz 无数据");
      return resp.data;
    },
    10_000
  );

  const [showDetail, setShowDetail] = useState(false);
  const healthy = data?.status === "ok";
  const deps: Record<string, string> = data?.deps ?? {};

  return (
    <div className="relative flex items-center gap-2">
      <button
        onClick={() => setShowDetail((v) => !v)}
        className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
          error
            ? "border-red-200 bg-red-50 text-red-600 dark:border-red-300/40 dark:text-red-400"
            : healthy
              ? "border-green-200 bg-green-50 text-green-700 dark:border-green-300/40 dark:text-green-300"
              : "border-yellow-200 bg-yellow-50 text-yellow-700 dark:border-yellow-300/40 dark:text-yellow-300"
        }`}
      >
        <span
          className={`h-2 w-2 rounded-full ${
            error ? "bg-red-500" : healthy ? "bg-green-500" : "bg-yellow-500"
          }`}
        />
        {error ? "服务不可达" : healthy ? "依赖就绪" : "部分依赖降级"}
      </button>
      {showDetail && (
        <div className="absolute right-0 top-9 z-50 w-64 rounded-xl border border-gray-200 bg-surface p-3 shadow-lg">
          <div className="mb-2 text-xs font-semibold text-gray-500">依赖探测 (readyz)</div>
          {Object.keys(deps).length === 0 ? (
            <div className="text-xs text-gray-400">无探测结果</div>
          ) : (
            <div className="space-y-1">
              {Object.entries(deps).map(([name, status]) => (
                <div key={name} className="flex items-center justify-between text-xs">
                  <span className="text-gray-600">{name}</span>
                  <span
                    className={
                      status === "ok" ? "text-green-600 dark:text-green-400" : "max-w-[60%] truncate text-red-500 dark:text-red-400"
                    }
                    title={status}
                  >
                    {status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Sidebar() {
  return (
    <aside className="flex w-52 shrink-0 flex-col border-r border-slate-800 bg-slate-900 dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500 text-sm font-bold text-white">
          KF
        </div>
        <div>
          <div className="text-sm font-bold text-white">KnowFlow</div>
          <div className="text-[10px] text-slate-400">企业知识库 Agent 平台</div>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 px-2 py-2">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              }`
            }
          >
            <Icon name={item.icon} className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-slate-800 px-4 py-3 text-[10px] leading-relaxed text-slate-500">
        Python + FastAPI · LangGraph
        <br />
        Milvus · PostgreSQL · MinIO · Redis
      </div>
    </aside>
  );
}

function Topbar() {
  const { userId, updateUserId } = useSession();
  const { theme, toggle } = useTheme();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(userId);
  const navigate = useNavigate();

  const commit = () => {
    updateUserId(draft);
    setEditing(false);
    navigate("/chat");
  };

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-gray-200 bg-surface px-4">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-gray-800">控制台</span>
        <span className="h-3 w-px bg-gray-200" />
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="text-xs text-blue-600 hover:underline dark:text-blue-400"
        >
          OpenAPI 文档
        </a>
      </div>
      <div className="flex items-center gap-3">
        <IconButton onClick={toggle} title={theme === "dark" ? "切换到亮色模式" : "切换到暗色模式"}>
          <Icon name={theme === "dark" ? "sun" : "moon"} className="h-4 w-4" />
        </IconButton>
        <HealthIndicator />
        {editing ? (
          <div className="flex items-center gap-1.5">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && commit()}
              className="h-7 w-36 rounded-md border border-gray-300 px-2 text-xs outline-none focus:border-blue-500"
              placeholder="用户 ID"
              autoFocus
            />
            <Button size="sm" onClick={commit}>
              确定
            </Button>
          </div>
        ) : (
          <button
            onClick={() => {
              setDraft(userId);
              setEditing(true);
            }}
            className="flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-100"
            title="点击修改用户 ID(记忆隔离)"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
            X-User-Id: {userId}
          </button>
        )}
      </div>
    </header>
  );
}

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-100 font-sans text-gray-900">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="min-h-0 flex-1 overflow-auto p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
