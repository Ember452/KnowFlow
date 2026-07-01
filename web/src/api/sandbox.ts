import { request } from './client';
import type { WorkspaceFile, QuotaInfo } from '@/types';

export const sandboxApi = {
  /** 会话工作区文件列表（含工具结果卸载产生的 spilled 文件） */
  files: (sessionId: number) => request<WorkspaceFile[]>(`/sandbox/${sessionId}/files`),

  /** 工作区配额使用情况 */
  quota: (sessionId: number) => request<QuotaInfo>(`/sandbox/${sessionId}/quota`),

  /** 清理会话工作区 */
  clear: (sessionId: number) =>
    request<void>(`/sandbox/${sessionId}/files`, { method: 'DELETE' }),
};
