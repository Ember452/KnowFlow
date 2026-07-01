import { request } from './client';
import type { TraceTreeResponse, TraceStats, ReplayResult } from '@/types';

export const tracesApi = {
  /** 嵌套 span 树 */
  get: (sessionId: number) => request<TraceTreeResponse>(`/traces/${sessionId}`),

  /** 近 N 小时聚合统计（对话数/耗时/工具成功率） */
  stats: (hours = 24) => request<TraceStats>('/traces/stats', { query: { hours } }),

  /** checkpoint + trace 重放 */
  replay: (sessionId: number, checkpointId?: string) =>
    request<ReplayResult>('/traces/replay', {
      method: 'POST',
      body: checkpointId ? { session_id: sessionId, checkpoint_id: checkpointId } : { session_id: sessionId },
    }),
};
