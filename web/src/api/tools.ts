import { request } from './client';
import type { ToolGovernanceStats } from '@/types';

export const toolsApi = {
  /** 工具治理统计：可见工具数 / Schema Token / 执行域分布 / 逐工具指标 */
  stats: () => request<ToolGovernanceStats>('/tools/stats'),
};
