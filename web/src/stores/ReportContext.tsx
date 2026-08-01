/**
 * 全局报告任务上下文: 任务列表与轮询提升到 App 顶层, 跨页面切换不丢失.
 * 每个运行中任务独立 2s 轮询 GET /reports/{id}; 完成后拉取产物, 失败停止.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createReport, getReport, getReportResult, publishReport } from "../api/endpoints";
import type { PublishResultOut, ReportOut, ReportResultOut } from "../types/api";

export interface ReportTaskState {
  report: ReportOut;
  result: ReportResultOut | null;
  error: string | null;
  publish?: PublishResultOut;
}

interface ReportContextValue {
  tasks: ReportTaskState[];
  createTask: (query: string) => Promise<ReportOut>;
  publishTask: (runId: string) => Promise<void>;
}

const ReportContext = createContext<ReportContextValue | null>(null);

const POLL_INTERVAL_MS = 2000;

export function ReportProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<ReportTaskState[]>([]);
  const timersRef = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const stopPolling = useCallback((runId: string) => {
    const timer = timersRef.current[runId];
    if (timer) {
      clearInterval(timer);
      delete timersRef.current[runId];
    }
  }, []);

  const refreshTask = useCallback(
    async (runId: string) => {
      try {
        const report = await getReport(runId);
        setTasks((prev) =>
          prev.map((t) => (t.report.run_id === runId ? { ...t, report, error: null } : t))
        );
        if (report.status === "completed") {
          stopPolling(runId);
          try {
            const result = await getReportResult(runId);
            setTasks((prev) =>
              prev.map((t) => (t.report.run_id === runId ? { ...t, result } : t))
            );
          } catch {
            // 产物尚未就绪, 下次刷新重试
          }
        } else if (report.status === "failed") {
          stopPolling(runId);
        }
      } catch (e) {
        setTasks((prev) =>
          prev.map((t) =>
            t.report.run_id === runId
              ? { ...t, error: e instanceof Error ? e.message : String(e) }
              : t
          )
        );
      }
    },
    [stopPolling]
  );

  const createTask = useCallback(
    async (query: string) => {
      const report = await createReport({ query, session_id: null });
      setTasks((prev) => [{ report, result: null, error: null }, ...prev]);
      void refreshTask(report.run_id);
      timersRef.current[report.run_id] = setInterval(
        () => void refreshTask(report.run_id),
        POLL_INTERVAL_MS
      );
      return report;
    },
    [refreshTask]
  );

  const publishTask = useCallback(async (runId: string) => {
    const res = await publishReport(runId);
    setTasks((prev) =>
      prev.map((t) => (t.report.run_id === runId ? { ...t, publish: res } : t))
    );
  }, []);

  // 卸载时清理全部轮询
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      Object.values(timers).forEach(clearInterval);
    };
  }, []);

  const value = useMemo(
    () => ({ tasks, createTask, publishTask }),
    [tasks, createTask, publishTask]
  );
  return <ReportContext.Provider value={value}>{children}</ReportContext.Provider>;
}

export function useReports(): ReportContextValue {
  const ctx = useContext(ReportContext);
  if (!ctx) {
    throw new Error("useReports 必须在 ReportProvider 内使用");
  }
  return ctx;
}
