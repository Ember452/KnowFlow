/**
 * API 类型定义 - 对齐后端 src/knowflow/schemas/ 下全部响应模型.
 * 后端响应信封不统一: 部分接口为 ApiResponse{code,message,data}, 部分直接返回模型,
 * 因此在 endpoints.ts 中按接口逐一 unwrap, 本文件只定义最终业务类型.
 */

// ── 通用 ──
export interface ApiResponse<T> {
  code: string;
  message: string;
  data: T | null;
}

export interface PageResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

// ── 健康 ──
export interface ReadyzData {
  status: string;
  deps: Record<string, string>;
}

// ── 对话 ──
export interface Citation {
  chunk_id: number;
  content?: string | null;
  score?: number | null;
  source?: string | null;
  doc_id?: number | null;
  doc_title?: string | null;
}

export interface ChatResponse {
  session_id: number;
  answer: string;
  citations: Citation[];
  tool_calls: ToolCallRecord[];
  latency_ms: number;
}

export interface ToolCallRecord {
  tool: string;
  args?: Record<string, unknown>;
  success: boolean;
  latency_ms: number;
  error?: string | null;
}

export interface SessionOut {
  id: number;
  user_id?: string | null;
  title?: string | null;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface MessageOut {
  id: number;
  session_id: number;
  role: string;
  content: string;
  tokens: number;
  citations: Record<string, unknown> | null;
  created_at?: string | null;
}

// ── SSE 事件(对齐 chat_service.stream_events 的事件载荷) ──
export interface RetrievalEvent {
  query: string;
  chunks: Citation[];
  latency_ms: number;
}

export interface ProgressEvent {
  stage?: string;
  delegated?: boolean;
  subtasks?: (string | number)[];
  run_id?: number | null;
}

export interface ToolStartEvent {
  tool: string;
  args: Record<string, unknown>;
  call_id: string;
  subtask_id?: string | null;
}

export interface ToolEndEvent {
  tool: string;
  call_id: string;
  success: boolean;
  latency_ms: number;
  error?: string | null;
  subtask_id?: string | null;
}

export interface DoneEvent {
  session_id: number;
  citations: Citation[];
  tool_calls: ToolCallRecord[];
  latency_ms: number;
  tokens: number;
}

export interface ErrorEvent {
  error: string;
}

// ── 文档 ──
export interface UploadResponse {
  doc_id: number;
  title: string;
  status: string;
  duplicated: boolean;
  message: string;
}

export interface DocumentInfo {
  id: number;
  title: string;
  file_type: string;
  status: string;
  size_bytes: number;
  content_hash?: string | null;
  user_id?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ReindexResponse {
  doc_id: number;
  status: string;
  message: string;
}

export interface DeleteResponse {
  doc_id: number;
  deleted: boolean;
  message: string;
}

// ── 知识检索 ──
export interface ChunkResult {
  chunk_id: number;
  content: string;
  score: number;
  source: string;
  doc_id?: number | null;
  doc_title?: string | null;
}

export interface SearchResponse {
  query: string;
  chunks: ChunkResult[];
  latency_ms: number;
  cache_hit: boolean;
  total: number;
}

// ── Agent 编排 ──
export interface AgentRunInfo {
  id: number;
  session_id: number;
  agent_type: string;
  parent_run_id?: number | null;
  status: string;
  started_at: string;
  completed_at?: string | null;
}

export interface TaskDelegationInfo {
  id: number;
  parent_run_id: number;
  child_run_id?: number | null;
  task: string;
  status: string;
  result?: Record<string, unknown> | null;
  checkpoint_id?: string | null;
  created_at: string;
}

export interface AgentRunDetail {
  run: AgentRunInfo;
  children: AgentRunInfo[];
  delegations: TaskDelegationInfo[];
}

// ── Skill / 工具治理 ──
export interface SkillInfo {
  name: string;
  description: string;
  tools: string[];
  dependencies: string[];
  domain: string;
  enabled: boolean;
}

export interface SkillToggleResponse {
  name: string;
  enabled: boolean;
}

export interface ToolMetricInfo {
  tool: string;
  calls: number;
  success_rate: number;
  avg_latency_ms: number;
  token_count: number;
  domain: string;
}

export interface ToolGovernanceStats {
  total_tools: number;
  visible_tools: number;
  schema_tokens: number;
  accuracy: number;
  domain_breakdown: Record<string, number>;
  metrics: ToolMetricInfo[];
}

// ── 记忆 ──
export interface MemoryItem {
  id: number;
  user_id: string;
  session_id: number;
  content: string;
  summary?: string | null;
  importance: number;
  created_at?: string | null;
  last_recall?: string | null;
}

// ── Trace / Replay ──
export interface TraceSpanNode {
  id: number;
  trace_id: string;
  parent_span_id?: number | null;
  session_id?: number | null;
  span_type: string;
  name: string;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  started_at: string;
  ended_at?: string | null;
  latency_ms?: number | null;
  children: TraceSpanNode[];
}

export interface TraceTree {
  session_id: number;
  roots: TraceSpanNode[];
}

export interface ReplayEvent {
  ts: string;
  span_id: number;
  parent_span_id?: number | null;
  span_type: string;
  name: string;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  ended_at?: string | null;
}

export interface ReplayResponse {
  session_id: number;
  run_id: number;
  checkpoint_id?: string | null;
  state: Record<string, unknown>;
  events: ReplayEvent[];
}

export interface TraceStats {
  hours: number;
  dialogs: number;
  traces: number;
  span_counts: Record<string, number>;
  avg_latency_ms: Record<string, number>;
  tool_calls: number;
  tool_success_rate: number;
}

// ── 评测 ──
export interface EvalRunInfo {
  run_id: number;
  dataset: string;
  status: string;
  summary: Record<string, number>;
  results: Record<string, unknown>[];
}

// ── 报告 ──
export interface ReportOut {
  run_id: string;
  query: string;
  status: string;
  stage: string;
  detail: string;
  error?: string | null;
  markdown_path: string;
  progress_log: { stage: string; detail: string; ts: string }[];
}

export interface ChapterOut {
  title: string;
  body: string;
}

export interface EvidenceOut {
  source: string;
  content: string;
  title: string;
  doc_id?: number | null;
  url: string;
}

export interface ReportResultOut {
  run_id: string;
  title: string;
  status: string;
  chapters: ChapterOut[];
  evidence: EvidenceOut[];
  references: string[];
  review_passed: boolean;
  issues: string[];
  markdown_path: string;
}

export interface PublishResultOut {
  run_id: string;
  published: boolean;
  doc_url: string;
  message: string;
}

// ── 报告流水线阶段 ──
export const REPORT_STAGES = [
  "planning",
  "research",
  "synthesis",
  "writing",
  "review",
  "done",
  "failed",
] as const;
export type ReportStage = (typeof REPORT_STAGES)[number];
