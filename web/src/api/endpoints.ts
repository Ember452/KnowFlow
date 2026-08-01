/**
 * 后端 API 调用函数 - 对齐 src/knowflow/api/v1/endpoints 全部接口契约.
 * 注意: 部分接口带 ApiResponse{code,message,data} 信封, 部分直接返回模型, 此处按契约逐一 unwrap.
 */

import { request, RequestOptions } from "./client";
import type {
  AgentRunDetail,
  ApiResponse as ApiResponseType,
  ChatResponse,
  DeleteResponse,
  DocumentInfo,
  EvalRunInfo,
  MemoryItem,
  MessageOut,
  PageResponse,
  PublishResultOut,
  ReadyzData,
  ReindexResponse,
  ReplayResponse,
  ReportOut,
  ReportResultOut,
  SearchResponse,
  SessionOut,
  SkillInfo,
  SkillToggleResponse,
  ToolGovernanceStats,
  TraceStats,
  TraceTree,
  UploadResponse,
} from "../types/api";

// ── 健康 ──

export async function healthz(): Promise<ApiResponseType<Record<string, string>>> {
  return request("/healthz");
}

export async function readyz(): Promise<ApiResponseType<ReadyzData>> {
  return request("/readyz");
}

// ── 对话(chat 与 stream 无信封, 直接返回模型) ──

export async function chat(body: {
  session_id?: number | null;
  message: string;
  user_id?: string | null;
}): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(body) });
}

/** SSE 流式对话: 返回原始 Response, 由调用方经 parseSSE 消费. */
export async function chatStream(body: {
  session_id?: number | null;
  message: string;
  user_id?: string | null;
}): Promise<Response> {
  const userId = body.user_id ?? undefined;
  const resp = await fetch(`/api/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": userId || localStorage.getItem("knowflow.user_id") || "demo",
    },
    body: JSON.stringify({ ...body, stream: true }),
  });
  if (!resp.ok) {
    throw new Error(`对话流启动失败: HTTP ${resp.status}`);
  }
  return resp;
}

export async function listSessions(limit = 50): Promise<SessionOut[]> {
  const resp = await request<ApiResponseType<PageResponse<SessionOut>>>(
    `/chat/sessions?limit=${limit}`
  );
  return resp.data?.items ?? [];
}

export async function listMessages(sessionId: number): Promise<MessageOut[]> {
  const resp = await request<ApiResponseType<MessageOut[]>>(`/chat/sessions/${sessionId}/messages`);
  return resp.data ?? [];
}

// ── 文档 ──

export async function uploadDocument(file: File, options?: RequestOptions): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const resp = await request<ApiResponseType<UploadResponse>>("/documents/upload", {
    method: "POST",
    body: form,
    ...options,
  });
  if (!resp.data) throw new Error("上传响应为空");
  return resp.data;
}

export async function listDocuments(limit = 100, offset = 0): Promise<PageResponse<DocumentInfo>> {
  const resp = await request<ApiResponseType<PageResponse<DocumentInfo>>>(
    `/documents?limit=${limit}&offset=${offset}`
  );
  return (
    resp.data ?? { items: [], total: 0, limit, offset }
  );
}

export async function deleteDocument(docId: number): Promise<DeleteResponse> {
  const resp = await request<ApiResponseType<DeleteResponse>>(`/documents/${docId}`, {
    method: "DELETE",
  });
  if (!resp.data) throw new Error("删除响应为空");
  return resp.data;
}

export async function reindexDocument(docId: number): Promise<ReindexResponse> {
  const resp = await request<ApiResponseType<ReindexResponse>>(`/documents/${docId}/reindex`, {
    method: "POST",
  });
  if (!resp.data) throw new Error("重建索引响应为空");
  return resp.data;
}

// ── 知识检索 ──

export async function searchKnowledge(body: {
  query: string;
  top_k?: number | null;
  with_rerank?: boolean;
}): Promise<SearchResponse> {
  const resp = await request<ApiResponseType<SearchResponse>>("/knowledge/search", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!resp.data) throw new Error("检索响应为空");
  return resp.data;
}

// ── Agent 编排(无信封) ──

export async function getAgentRun(runId: number): Promise<AgentRunDetail> {
  return request<AgentRunDetail>(`/agents/runs/${runId}`);
}

// ── Skill / 工具治理(无信封) ──

export async function listSkills(): Promise<SkillInfo[]> {
  return request<SkillInfo[]>("/skills");
}

export async function toggleSkill(name: string): Promise<SkillToggleResponse> {
  return request<SkillToggleResponse>(`/skills/${encodeURIComponent(name)}/toggle`, {
    method: "PUT",
  });
}

export async function getToolStats(): Promise<ToolGovernanceStats> {
  return request<ToolGovernanceStats>("/tools/stats");
}

// ── 记忆(无信封) ──

export async function listMemory(userId: string): Promise<MemoryItem[]> {
  return request<MemoryItem[]>(`/memory/${encodeURIComponent(userId)}`);
}

export async function deleteMemory(userId: string, memoryId: number): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/memory/${encodeURIComponent(userId)}/${memoryId}`, {
    method: "DELETE",
  });
}

export async function sedimentMemory(
  userId: string,
  sessionId: number
): Promise<{ saved: number }> {
  return request<{ saved: number }>(`/memory/${encodeURIComponent(userId)}/sediment`, {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

// ── Trace / Replay(无信封) ──

export async function getTraceStats(hours = 24): Promise<TraceStats> {
  return request<TraceStats>(`/traces/stats?hours=${hours}`);
}

export async function getTraceTree(sessionId: number): Promise<TraceTree> {
  return request<TraceTree>(`/traces/${sessionId}`);
}

export async function replayTrace(
  sessionId: number,
  checkpointId?: string | null
): Promise<ReplayResponse> {
  return request<ReplayResponse>("/traces/replay", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, checkpoint_id: checkpointId ?? null }),
  });
}

// ── 评测(无信封) ──

export async function runEval(body: {
  dataset: string;
  mode?: string;
  top_k?: number;
}): Promise<EvalRunInfo> {
  return request<EvalRunInfo>("/eval/run", { method: "POST", body: JSON.stringify(body) });
}

export async function getEvalRun(runId: number): Promise<EvalRunInfo> {
  return request<EvalRunInfo>(`/eval/runs/${runId}`);
}

// ── 报告 ──

export async function createReport(body: {
  query: string;
  session_id?: number | null;
}): Promise<ReportOut> {
  const resp = await request<ApiResponseType<ReportOut>>("/reports", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!resp.data) throw new Error("创建报告响应为空");
  return resp.data;
}

export async function getReport(runId: string): Promise<ReportOut> {
  const resp = await request<ApiResponseType<ReportOut>>(`/reports/${encodeURIComponent(runId)}`);
  if (!resp.data) throw new Error("报告状态响应为空");
  return resp.data;
}

export async function getReportResult(runId: string): Promise<ReportResultOut> {
  const resp = await request<ApiResponseType<ReportResultOut>>(
    `/reports/${encodeURIComponent(runId)}/result`
  );
  if (!resp.data) throw new Error("报告产物响应为空");
  return resp.data;
}

export async function publishReport(runId: string): Promise<PublishResultOut> {
  const resp = await request<ApiResponseType<PublishResultOut>>(
    `/reports/${encodeURIComponent(runId)}/publish`,
    { method: "POST" }
  );
  if (!resp.data) throw new Error("发布响应为空");
  return resp.data;
}
