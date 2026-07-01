import { request } from './client';
import type { EvalRun, EvalRunSummary } from '@/types';

export const evalApi = {
  /** 触发一次评测运行 */
  run: (dataset = 'knowledge_qa_eval.jsonl') =>
    request<{ run_id: number }>('/eval/run', { method: 'POST', body: { dataset } }),

  /** 查询评测结果（baseline vs GraphRAG 对比） */
  getRun: (runId: number) => request<EvalRun>(`/eval/runs/${runId}`),

  /** 评测运行列表（如后端支持） */
  runs: () => request<EvalRunSummary[]>('/eval/runs').catch(() => [] as EvalRunSummary[]),
};
