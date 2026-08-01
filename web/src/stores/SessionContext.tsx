/**
 * 全局上下文: 用户 ID(localStorage 持久化) + 会话列表状态.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getUserId, setUserId } from "../api/client";
import { listSessions } from "../api/endpoints";
import type { SessionOut } from "../types/api";

interface SessionContextValue {
  userId: string;
  updateUserId: (id: string) => void;
  sessions: SessionOut[];
  refreshSessions: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [userId, setUser] = useState<string>(getUserId());
  const [sessions, setSessions] = useState<SessionOut[]>([]);

  const updateUserId = useCallback((id: string) => {
    const trimmed = id.trim() || "anonymous";
    setUserId(trimmed);
    setUser(trimmed);
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const items = await listSessions();
      setSessions(items);
    } catch {
      // 后端不可达时静默保留旧列表
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const value = useMemo(
    () => ({ userId, updateUserId, sessions, refreshSessions }),
    [userId, updateUserId, sessions, refreshSessions]
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession 必须在 SessionProvider 内使用");
  }
  return ctx;
}
