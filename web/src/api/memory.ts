import { request } from './client';
import type { LongTermMemory, SedimentResult } from '@/types';

export const memoryApi = {
  /** 用户长期记忆列表 */
  list: (userId: string) => request<LongTermMemory[]>(`/memory/${userId}`),

  /** 删除单条记忆 */
  remove: (userId: string, memoryId: number) =>
    request<void>(`/memory/${userId}/${memoryId}`, { method: 'DELETE' }),

  /** 手动触发记忆沉淀（短期 → 压缩 → 长期）；session_id 指定要沉淀的会话短期记忆 */
  sediment: (userId: string, sessionId: number) =>
    request<SedimentResult>(`/memory/${userId}/sediment`, {
      method: 'POST',
      body: { session_id: sessionId },
    }),
};
