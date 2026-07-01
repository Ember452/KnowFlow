import { request, streamSSE } from './client';
import type {
  ApiResponse,
  ChatRequest,
  ChatResponse,
  MessageItem,
  PageData,
  SessionItem,
} from '@/types';

export const chatApi = {
  /** 同步对话（检索 + 工具/多 Agent 编排，返回完整答案与引用） */
  chat: (req: ChatRequest) => request<ChatResponse>('/chat', { method: 'POST', body: req }),

  /**
   * SSE 流式对话：事件序列 retrieval → [progress/tool_start/tool_end]* → token* → done。
   * 用法：for await (const ev of chatApi.stream(req, userId)) { ... }
   * signal 用于用户停止时中断连接。
   */
  stream: (req: ChatRequest, userId?: string, signal?: AbortSignal) =>
    streamSSE('/chat/stream', req, userId ? { 'X-User-Id': userId } : undefined, signal) as AsyncGenerator<{
      event: string;
      data: unknown;
    }>,

  /** 列出当前用户的历史会话（按 id 倒序） */
  listSessions: async (userId: string) => {
    const r = await request<ApiResponse<PageData<SessionItem>>>('/chat/sessions', {
      query: { user_id: userId },
    });
    return r.data;
  },

  /** 加载某会话的历史消息（按时间升序） */
  getSessionMessages: async (sessionId: number) => {
    const r = await request<ApiResponse<MessageItem[]>>(`/chat/sessions/${sessionId}/messages`);
    return r.data;
  },
};
