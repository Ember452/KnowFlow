import { request } from './client';
import type { ApiResponse, GraphData, SearchResponse } from '@/types';

export const knowledgeApi = {
  /** 知识库检索（GraphRAG 全链路：Hybrid 召回 → 一跳扩展 → reranker 精排） */
  search: (query: string, topK = 5) =>
    request<SearchResponse>('/knowledge/search', {
      method: 'POST',
      body: { query, top_k: topK },
    }),

  /** 知识图谱数据：实体节点 + 关系边（doc_id 为空取全库） */
  getGraph: async (docId?: number, limit = 200) => {
    const r = await request<ApiResponse<GraphData>>('/knowledge/graph', {
      query: { doc_id: docId, limit },
    });
    return r.data;
  },
};
