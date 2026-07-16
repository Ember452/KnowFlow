/**
 * KnowFlow 类型定义 — 对齐后端 models 与 API 响应结构。
 * 覆盖六大模块：检索 / 工具治理 / Agent 编排 / 上下文 / 沙箱 / 可观测。
 */

/* ============ 通用 ============ */
export interface ApiError {
  code: string;
  message: string;
  details: unknown;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

/** 后端统一响应信封（解包 .data 取业务数据） */
export interface ApiResponse<T> {
  code: string;
  message: string;
  data: T;
}

/** 后端分页响应 */
export interface PageData<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/* ============ 会话历史 ============ */
export interface SessionItem {
  id: number;
  user_id?: string | null;
  title?: string | null;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface MessageItem {
  id: number;
  session_id: number;
  role: string;
  content: string;
  tokens: number;
  citations?: Record<string, unknown> | null;
  created_at?: string;
}

/* ============ 知识图谱 ============ */
export interface GraphNode {
  id: number;
  name: string;
  entity_type: string;
  normalized: string;
  doc_id: number;
  chunk_id: number;
}

export interface GraphEdge {
  id: number;
  source: number;
  target: number;
  relation_type: string;
  confidence: number;
  doc_id: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total: number;
}

/* ============ 健康检查 ============ */
export interface HealthStatus {
  status: 'ok' | 'error';
}

export interface DependencyStatus {
  name: string;
  status: 'ok' | 'error';
  latency_ms?: number;
  detail?: string;
}

export interface ReadyStatus {
  status: 'ok' | 'error';
  dependencies: Record<string, DependencyStatus | 'ok' | 'error'>;
}

/* ============ 文档与索引 ============ */
export type DocumentStatus = 'indexing' | 'ready' | 'failed' | 'reindexing';

export interface KnowDocument {
  id: number;
  filename: string;
  file_type: 'pdf' | 'docx' | 'md' | 'txt';
  size: number;
  status: DocumentStatus;
  chunk_count: number;
  entity_count?: number;
  created_at: string;
  indexed_at?: string;
  message?: string;
}

export interface UploadResult {
  doc_id: number;
  status: 'indexing';
  message: string;
}

/* ============ 检索 ============ */
export type RetrievalSource = 'vector' | 'bm25' | 'hybrid' | 'graph_expand' | 'rerank';

export interface RetrievalChunk {
  chunk_id: number;
  doc_id?: number;
  filename?: string;
  doc_title?: string;
  content: string;
  score: number;
  source: RetrievalSource;
  entities?: Entity[];
}

export interface SearchResponse {
  query: string;
  chunks: RetrievalChunk[];
  latency_ms: number;
  expanded?: boolean;
  entity_hits?: Entity[];
}

export interface Entity {
  id?: number;
  name: string;
  entity_type: string; // person / org / concept / product ...
  normalized?: string;
  doc_id?: number;
  chunk_id?: number;
}

export interface Relation {
  id?: number;
  source_entity: string;
  target_entity: string;
  relation_type: string; // belongs_to / related_to / part_of ...
  confidence?: number;
}

export interface EntityGraph {
  entities: Entity[];
  relations: Relation[];
}

/* ============ 对话 ============ */
export interface Citation {
  chunk_id: number;
  content: string;
  score: number;
  source: RetrievalSource;
  filename?: string;
  doc_id?: number;
  doc_title?: string;
}

export interface ToolCall {
  tool: string;
  /** 后端 tool_start/tool_end 事件携带的唯一标识，用于并发调用时精确匹配 */
  call_id?: string;
  args?: Record<string, unknown>;
  result?: string;
  status?: 'running' | 'success' | 'failed';
  latency_ms?: number;
  domain?: ExecutionDomain;
}

export interface ChatRequest {
  user_id: string;
  message: string;
  session_id?: number;
  top_k?: number;
}

export interface ChatResponse {
  session_id: number;
  answer: string;
  citations: Citation[];
  tool_calls: ToolCall[];
  latency_ms: number;
}

/** SSE 事件联合类型 */
export type SSEEvent =
  | { event: 'retrieval'; data: { query: string; chunks: RetrievalChunk[] } }
  | { event: 'progress'; data: { stage: string; delegated?: boolean; subtasks?: string[]; run_id?: number } }
  | { event: 'tool_start'; data: { tool: string; call_id?: string; args?: Record<string, unknown> } }
  | { event: 'tool_end'; data: { tool: string; call_id?: string; result?: string; success: boolean; latency_ms?: number } }
  | { event: 'token'; data: { delta: string } }
  | { event: 'done'; data: { session_id: number; citations: Citation[]; latency_ms: number } }
  | { event: 'error'; data: { message?: string; error?: string } };

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: number;
  citations?: Citation[];
  tool_calls?: ToolCall[];
  retrieval?: RetrievalChunk[];
  streaming?: boolean;
  /** 用户主动停止导致生成中断 */
  stopped?: boolean;
  delegated?: boolean;
  subtasks?: string[];
  run_id?: number;
}

/* ============ 工具治理 ============ */
export type ExecutionDomain = 'direct' | 'skill_only' | 'subagent_only' | 'internal';

export interface SkillDefinition {
  name: string;
  description: string;
  domain: ExecutionDomain;
  tools: string[];
  dependencies: string[];
  enabled: boolean;
}

export interface ToolDefinition {
  name: string;
  description: string;
  domain: ExecutionDomain;
  parameters_schema?: Record<string, unknown>;
  visible_to_main?: boolean;
  visible_to_sub?: boolean;
}

export interface ToolMetric {
  tool: string;
  calls: number;
  success_rate: number;
  avg_latency_ms: number;
  token_count: number;
  domain: ExecutionDomain;
}

export interface ToolGovernanceStats {
  total_tools: number;
  visible_tools: number;
  schema_tokens: number;
  accuracy: number;
  domain_breakdown: Record<ExecutionDomain, number>;
  metrics: ToolMetric[];
}

export interface ToggleSkillResult {
  name: string;
  enabled: boolean;
}

/* ============ Agent 编排 ============ */
export type AgentType = 'main' | 'sub';
export type RunStatus = 'running' | 'completed' | 'failed' | 'pending';

export interface AgentRun {
  id: number;
  session_id: number;
  agent_type: AgentType;
  parent_run_id: number | null;
  status: RunStatus;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
}

export interface TaskDelegation {
  id: number;
  parent_run_id: number;
  child_run_id: number | null;
  task: string;
  status: RunStatus;
  result?: unknown;
  checkpoint_id?: string;
  created_at: string;
}

export interface AgentRunDetail {
  run: AgentRun;
  children: AgentRun[];
  delegations: TaskDelegation[];
  checkpoint_lineage?: CheckpointNode[];
}

export interface CheckpointNode {
  id: string;
  parent_checkpoint_id: string | null;
  agent_run_id: number;
  created_at: string;
}

/* ============ 记忆 ============ */
export interface LongTermMemory {
  id: number;
  user_id: string;
  session_id: number;
  content: string;
  summary?: string;
  importance: number;
  created_at: string;
  last_recall?: string;
}

export interface SedimentResult {
  sediment_count: number;
  message: string;
}

/* ============ 可观测 ============ */
export type SpanType = 'root' | 'agent_decision' | 'tool_call' | 'retrieval' | 'memory_recall';

export interface TraceSpan {
  id?: number;
  trace_id: string;
  parent_span_id: number | null;
  session_id: number;
  span_type: SpanType;
  name: string;
  input?: unknown;
  output?: unknown;
  started_at: string;
  ended_at?: string;
  latency_ms?: number;
  children?: TraceSpan[];
}

export interface TraceTreeResponse {
  session_id: number;
  roots: TraceSpan[];
}

export interface TraceStats {
  window_hours: number;
  total_conversations: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  tool_success_rate: number;
  retrieval_count: number;
  by_hour?: { hour: string; conversations: number; avg_latency: number }[];
  by_span_type?: Record<SpanType, number>;
}

export interface ReplayResult {
  session_id: number;
  run_id: number;
  checkpoint_id: string;
  state: Record<string, unknown>;
  events: TraceSpan[];
}

/* ============ 评测 ============ */
export type EvalStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface EvalMetrics {
  recall_at_10?: number;
  mrr?: number;
  ndcg?: number;
  tool_accuracy?: number;
  latency_ms?: number;
}

export interface EvalRun {
  run_id: number;
  status: EvalStatus;
  dataset: string;
  started_at: string;
  completed_at?: string;
  baseline: EvalMetrics;
  graphrag: EvalMetrics;
  improvement?: Partial<Record<keyof EvalMetrics, number>>;
}

export interface EvalRunSummary {
  id: number;
  status: EvalStatus;
  dataset: string;
  started_at: string;
}

/* ============ 沙箱 ============ */
export interface WorkspaceFile {
  path: string; // 虚拟路径 /workspace/xxx
  name: string;
  size: number;
  type: 'file' | 'dir';
  modified: string;
  spilled?: boolean; // 是否为工具结果卸载产生
}

export interface QuotaInfo {
  used: number;
  limit: number;
  session_id: number;
}
