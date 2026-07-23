// 本文件由 scripts/gen-api-list.mjs 从 openapi.json 自动生成，请勿手动修改

export interface ApiEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  path: string;
  desc: string;
}

export const API_ENDPOINTS: ApiEndpoint[] = [
  {
    "method": "GET",
    "path": "/",
    "desc": "Root"
  },
  {
    "method": "GET",
    "path": "/api/v1/agents/runs/{run_id}",
    "desc": "Get Agent Run"
  },
  {
    "method": "POST",
    "path": "/api/v1/chat",
    "desc": "Chat"
  },
  {
    "method": "GET",
    "path": "/api/v1/chat/sessions",
    "desc": "List Sessions"
  },
  {
    "method": "GET",
    "path": "/api/v1/chat/sessions/{session_id}/messages",
    "desc": "List Messages"
  },
  {
    "method": "POST",
    "path": "/api/v1/chat/stream",
    "desc": "Chat Stream"
  },
  {
    "method": "GET",
    "path": "/api/v1/documents",
    "desc": "List Documents"
  },
  {
    "method": "DELETE",
    "path": "/api/v1/documents/{doc_id}",
    "desc": "Delete Document"
  },
  {
    "method": "POST",
    "path": "/api/v1/documents/{doc_id}/reindex",
    "desc": "Reindex Document"
  },
  {
    "method": "POST",
    "path": "/api/v1/documents/upload",
    "desc": "Upload Document"
  },
  {
    "method": "POST",
    "path": "/api/v1/eval/run",
    "desc": "Run Eval"
  },
  {
    "method": "GET",
    "path": "/api/v1/eval/runs/{run_id}",
    "desc": "Get Eval Run"
  },
  {
    "method": "GET",
    "path": "/api/v1/healthz",
    "desc": "Healthz"
  },
  {
    "method": "GET",
    "path": "/api/v1/knowledge/graph",
    "desc": "Get Graph"
  },
  {
    "method": "POST",
    "path": "/api/v1/knowledge/search",
    "desc": "Search"
  },
  {
    "method": "GET",
    "path": "/api/v1/memory/{user_id}",
    "desc": "List Memory"
  },
  {
    "method": "DELETE",
    "path": "/api/v1/memory/{user_id}/{memory_id}",
    "desc": "Delete Memory"
  },
  {
    "method": "POST",
    "path": "/api/v1/memory/{user_id}/sediment",
    "desc": "Sediment Memory"
  },
  {
    "method": "GET",
    "path": "/api/v1/readyz",
    "desc": "Readyz"
  },
  {
    "method": "GET",
    "path": "/api/v1/skills",
    "desc": "List Skills"
  },
  {
    "method": "PUT",
    "path": "/api/v1/skills/{name}/toggle",
    "desc": "Toggle Skill"
  },
  {
    "method": "GET",
    "path": "/api/v1/tools/stats",
    "desc": "Tool Stats"
  },
  {
    "method": "GET",
    "path": "/api/v1/traces/{session_id}",
    "desc": "Get Trace"
  },
  {
    "method": "POST",
    "path": "/api/v1/traces/replay",
    "desc": "Replay"
  },
  {
    "method": "GET",
    "path": "/api/v1/traces/stats",
    "desc": "Get Stats"
  },
  {
    "method": "GET",
    "path": "/health",
    "desc": "Health"
  }
];
