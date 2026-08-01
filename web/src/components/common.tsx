/**
 * 公共 UI 组件: 按钮/状态徽标/加载/骨架/空态/错误提示/JSON 查看器/统计卡/面板容器/页头.
 */

import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";

// ── 按钮 ──

type ButtonVariant = "primary" | "outline" | "ghost" | "danger" | "dangerOutline";
type ButtonSize = "sm" | "md";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-blue-600 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400 disabled:hover:bg-gray-100 dark:disabled:bg-gray-800 dark:disabled:text-gray-600 dark:disabled:hover:bg-gray-800",
  outline:
    "border border-gray-300 bg-surface text-gray-700 hover:border-gray-400 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:border-gray-500 dark:hover:bg-gray-800",
  ghost: "text-gray-600 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 dark:text-gray-300 dark:hover:bg-gray-800",
  danger: "text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 dark:text-red-400 dark:hover:bg-red-500/10",
  dangerOutline:
    "border border-red-200 bg-surface text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-500/40 dark:text-red-400 dark:hover:bg-red-500/10",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-xs",
  md: "h-9 px-4 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
}) {
  return (
    <button
      type="button"
      className={`inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]} ${className}`}
      {...rest}
    />
  );
}

export function IconButton({
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:text-gray-500 dark:hover:bg-gray-800 dark:hover:text-gray-300 ${className}`}
      {...rest}
    />
  );
}

// ── 状态徽标(对齐设计文档: idle灰/running蓝/completed绿/failed红/pending黄) ──

const STATUS_STYLE: Record<string, { dot: string; text: string }> = {
  idle: { dot: "bg-gray-400", text: "text-gray-500 dark:text-gray-400" },
  running: { dot: "bg-blue-500 animate-pulse", text: "text-blue-700 dark:text-blue-300" },
  in_progress: { dot: "bg-blue-500 animate-pulse", text: "text-blue-700 dark:text-blue-300" },
  pending: { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-300" },
  indexing: { dot: "bg-blue-500 animate-pulse", text: "text-blue-700 dark:text-blue-300" },
  ready: { dot: "bg-green-500", text: "text-green-700 dark:text-green-300" },
  completed: { dot: "bg-green-500", text: "text-green-700 dark:text-green-300" },
  success: { dot: "bg-green-500", text: "text-green-700 dark:text-green-300" },
  ok: { dot: "bg-green-500", text: "text-green-700 dark:text-green-300" },
  failed: { dot: "bg-red-500", text: "text-red-700 dark:text-red-300" },
  error: { dot: "bg-red-500", text: "text-red-700 dark:text-red-300" },
  created: { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-300" },
  delegated: { dot: "bg-indigo-500", text: "text-indigo-700 dark:text-indigo-300" },
  skipped: { dot: "bg-gray-400", text: "text-gray-500 dark:text-gray-400" },
  degraded: { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-300" },
  simple: { dot: "bg-gray-400", text: "text-gray-500 dark:text-gray-400" },
  complex: { dot: "bg-indigo-500", text: "text-indigo-700 dark:text-indigo-300" },
  uncertain: { dot: "bg-orange-500", text: "text-orange-700 dark:text-orange-300" },
};

export function StatusBadge({ status, className = "" }: { status: string; className?: string }) {
  const style = STATUS_STYLE[status.toLowerCase()] ?? { dot: "bg-gray-400", text: "text-gray-500 dark:text-gray-400" };
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${style.text} ${className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {status}
    </span>
  );
}

// ── 加载/骨架/空态/错误 ──

export function Spinner({ text = "加载中…" }: { text?: string }) {
  return (
    <div className="flex items-center gap-2.5 py-4 text-sm text-gray-500">
      <svg className="h-4 w-4 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-20" />
        <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      </svg>
      {text}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-gray-200 ${className}`} />;
}

export function SkeletonLines({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2.5 py-2 ${className}`}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={i === lines - 1 && lines > 1 ? "h-4 w-2/3" : "h-4 w-full"} />
      ))}
    </div>
  );
}

export function EmptyState({ text, hint, icon }: { text: string; hint?: string; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 py-10 text-center">
      {icon && <div className="mb-1 text-gray-300">{icon}</div>}
      <div className="text-sm text-gray-400">{text}</div>
      {hint && <div className="text-xs text-gray-400">{hint}</div>}
    </div>
  );
}

export function ErrorAlert({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      <span className="break-all">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 rounded border border-red-300 px-2 py-0.5 text-xs hover:bg-red-100"
        >
          重试
        </button>
      )}
    </div>
  );
}

// ── JSON 查看器(可折叠) ──

export function JsonViewer({
  data,
  defaultCollapsed = false,
  maxHeight = 320,
}: {
  data: unknown;
  defaultCollapsed?: boolean;
  maxHeight?: number;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const text = JSON.stringify(data, null, 2);
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="flex w-full items-center justify-between px-3 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100"
      >
        <span>{collapsed ? "展开" : "收起"} JSON</span>
        <span className="font-mono">{text.length} 字符</span>
      </button>
      {!collapsed && (
        <pre
          className="overflow-auto px-3 pb-2 font-mono text-xs leading-relaxed text-gray-700"
          style={{ maxHeight }}
        >
          {text}
        </pre>
      )}
    </div>
  );
}

// ── 面板容器 / 统计卡 / 页头 ──

export function Card({
  title,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col overflow-hidden rounded-xl border border-gray-200 bg-surface shadow-sm ${className}`}>
      {(title || actions) && (
        <div className="flex min-h-10 shrink-0 items-center justify-between gap-3 border-b border-gray-100 px-4 py-2">
          <div className="text-[13px] font-semibold text-gray-800 dark:text-gray-100">{title}</div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className="min-h-0 flex-1 p-4">{children}</div>
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  accent = "text-gray-900",
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-surface px-4 py-3.5 shadow-sm">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums tracking-tight ${accent}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-gray-400">{sub}</div>}
    </div>
  );
}

/** 页面级标题行: 页面名 + 一句话说明 + 右侧操作区. */
export function PageHeader({
  title,
  desc,
  actions,
}: {
  title: ReactNode;
  desc?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold tracking-tight text-gray-900">{title}</h1>
        {desc && <p className="mt-0.5 text-xs text-gray-500">{desc}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

/** 页面级错误(如后端 503 依赖未就绪)统一展示. */
export function PageError({ title, message }: { title: string; message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <div className="text-lg font-semibold text-gray-700">{title}</div>
      <div className="max-w-lg text-sm text-gray-500">{message}</div>
    </div>
  );
}
