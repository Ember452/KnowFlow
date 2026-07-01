import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AppState {
  /** 暗色模式（Claude 设计系统 .dark token） */
  isDark: boolean;
  /** 侧边栏折叠 */
  collapsed: boolean;
  /** 当前用户标识（记忆隔离用，透传 X-User-Id） */
  userId: string;
  toggleDark: () => void;
  toggleCollapsed: () => void;
  setUserId: (v: string) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      isDark: false,
      collapsed: false,
      userId: 'demo',
      toggleDark: () => set((s) => ({ isDark: !s.isDark })),
      toggleCollapsed: () => set((s) => ({ collapsed: !s.collapsed })),
      setUserId: (userId) => set({ userId }),
    }),
    { name: 'knowflow-app' },
  ),
);
