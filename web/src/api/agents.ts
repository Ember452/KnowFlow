import { request } from './client';
import type { AgentRunDetail } from '@/types';

export const agentsApi = {
  /** 父子 run 记录 + 委派链（状态机可见性） */
  getRun: (runId: number) => request<AgentRunDetail>(`/agents/runs/${runId}`),
};
