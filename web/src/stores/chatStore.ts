import { create } from 'zustand';
import { chatApi } from '@/api/chat';
import type {
  ChatMessage,
  Citation,
  MessageItem,
  RetrievalChunk,
  SessionItem,
  ToolCall,
} from '@/types';

let msgSeq = 0;
const nextId = () => `m${Date.now()}_${msgSeq++}`;

/** 当前流式请求的取消控制器与助手消息 id（模块级，同一时刻只有一路流） */
let activeAbort: AbortController | null = null;
let activeAssistantId: string | null = null;

/** 判断是否为用户主动停止触发的 AbortError（不按错误展示） */
function isAbortError(e: unknown): boolean {
  return e instanceof DOMException
    ? e.name === 'AbortError'
    : e instanceof Error && e.name === 'AbortError';
}

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  /** 当前会话 id；为空表示新会话（首次发送时由后端创建） */
  sessionId?: number;
  /** 当前用户的历史会话列表 */
  sessions: SessionItem[];
  loadingSessions: boolean;
  loadingSession: boolean;
  error?: string;
  send: (message: string, userId: string) => Promise<void>;
  stop: () => void;
  clear: () => void;
  /** 拉取用户历史会话列表 */
  loadSessions: (userId: string) => Promise<void>;
  /** 载入某历史会话的消息并切换为当前会话 */
  loadSession: (sessionId: number) => Promise<void>;
}

/** 在数组中按 id 更新单条消息 */
function updateMessage(
  messages: ChatMessage[],
  id: string,
  patch: (m: ChatMessage) => ChatMessage,
): ChatMessage[] {
  return messages.map((m) => (m.id === id ? patch(m) : m));
}

/** 后端 MessageItem → 前端 ChatMessage（citations JSON 解包） */
function toChatMessage(m: MessageItem): ChatMessage {
  const cit = m.citations as { citations?: Citation[]; tool_calls?: ToolCall[] } | null;
  return {
    id: `db_${m.id}`,
    role: m.role === 'assistant' ? 'assistant' : 'user',
    content: m.content,
    created_at: new Date(m.created_at ?? Date.now()).getTime(),
    citations: cit?.citations,
    tool_calls: cit?.tool_calls,
  };
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  sessionId: undefined,
  sessions: [],
  loadingSessions: false,
  loadingSession: false,
  error: undefined,

  send: async (message, userId) => {
    if (get().isStreaming) return;
    set({ error: undefined });
    // 续接当前会话（若有），否则后端新建会话
    const currentSessionId = get().sessionId;

    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: message,
      created_at: Date.now(),
    };
    const assistantId = nextId();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      created_at: Date.now(),
      streaming: true,
      tool_calls: [],
      retrieval: [],
    };

    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      isStreaming: true,
    }));

    activeAbort = new AbortController();
    activeAssistantId = assistantId;

    try {
      const stream = chatApi.stream(
        { user_id: userId, message, session_id: currentSessionId },
        userId,
        activeAbort.signal,
      );
      for await (const ev of stream) {
        const data = ev.data as Record<string, unknown>;

        switch (ev.event) {
          case 'retrieval':
            set((s) => ({
              messages: updateMessage(s.messages, assistantId, (m) => ({
                ...m,
                retrieval: (data.chunks as RetrievalChunk[]) ?? [],
              })),
            }));
            break;

          case 'progress':
            set((s) => ({
              messages: updateMessage(s.messages, assistantId, (m) => ({
                ...m,
                delegated: (data.delegated as boolean) ?? false,
                subtasks: (data.subtasks as string[]) ?? m.subtasks,
                run_id: (data.run_id as number) ?? m.run_id,
              })),
            }));
            break;

          case 'tool_start':
            set((s) => ({
              messages: updateMessage(s.messages, assistantId, (m) => ({
                ...m,
                tool_calls: [
                  ...(m.tool_calls ?? []),
                  {
                    tool: data.tool as string,
                    call_id: data.call_id as string | undefined,
                    args: data.args as Record<string, unknown>,
                    status: 'running',
                  } satisfies ToolCall,
                ],
              })),
            }));
            break;

          case 'tool_end':
            set((s) => ({
              messages: updateMessage(s.messages, assistantId, (m) => ({
                ...m,
                tool_calls: (m.tool_calls ?? []).map((t) => {
                  const callId = data.call_id as string | undefined;
                  const matched =
                    t.status === 'running' &&
                    (callId !== undefined
                      ? t.call_id === callId
                      : t.tool === (data.tool as string));
                  return matched
                    ? {
                        ...t,
                        result: data.result as string,
                        success: (data.success as boolean) ?? true,
                        status: 'success',
                        latency_ms: data.latency_ms as number,
                      }
                    : t;
                }),
              })),
            }));
            break;

          case 'token':
            set((s) => ({
              messages: updateMessage(s.messages, assistantId, (m) => ({
                ...m,
                content: m.content + (data.delta as string),
              })),
            }));
            break;

          case 'done':
            set((s) => ({
              sessionId: Number(data.session_id),
              messages: updateMessage(s.messages, assistantId, (m) => ({
                ...m,
                streaming: false,
                citations: (data.citations as Citation[]) ?? [],
              })),
            }));
            break;

          case 'error':
            set((s) => ({
              // 后端 error 事件载荷为 {error} 或 {message}，两种都兼容
              error: (data.message as string) ?? (data.error as string) ?? '流式对话出错',
              messages: updateMessage(s.messages, assistantId, (m) => ({
                ...m,
                streaming: false,
                content: m.content || '（生成失败）',
              })),
            }));
            break;
        }
      }
    } catch (e) {
      // 用户主动停止时中断流（AbortError），不展示错误，由 stop() 负责标记
      if (!isAbortError(e)) {
        set((s) => ({
          error: e instanceof Error ? e.message : '对话请求失败',
          messages: updateMessage(s.messages, assistantId, (m) => ({
            ...m,
            streaming: false,
            content: m.content || '（连接失败，请检查后端服务）',
          })),
        }));
      }
    } finally {
      activeAbort = null;
      activeAssistantId = null;
      set((s) => ({
        isStreaming: false,
        messages: updateMessage(s.messages, assistantId, (m) =>
          m.streaming ? { ...m, streaming: false } : m,
        ),
      }));
      // 对话落库后刷新会话列表（新会话会出现在列表中）
      get()
        .loadSessions(userId)
        .catch(() => {});
    }
  },

  loadSessions: async (userId) => {
    set({ loadingSessions: true });
    try {
      const page = await chatApi.listSessions(userId);
      set({ sessions: page.items, loadingSessions: false });
    } catch {
      set({ loadingSessions: false });
    }
  },

  loadSession: async (sessionId) => {
    set({ loadingSession: true, error: undefined });
    try {
      const items = await chatApi.getSessionMessages(sessionId);
      set({
        messages: items.map(toChatMessage),
        sessionId,
        loadingSession: false,
      });
    } catch (e) {
      set({
        loadingSession: false,
        error: e instanceof Error ? e.message : '加载历史失败',
      });
    }
  },

  stop: () => {
    // 真正中断底层 fetch 连接（后端 is_disconnected 会同步取消生成器）
    const controller = activeAbort;
    const assistantId = activeAssistantId;
    if (controller) controller.abort();
    set((s) => ({
      isStreaming: false,
      messages: updateMessage(s.messages, assistantId ?? '', (m) =>
        m.streaming
          ? { ...m, streaming: false, stopped: true, content: m.content || '（已停止）' }
          : m,
      ),
    }));
  },

  clear: () => set({ messages: [], sessionId: undefined, error: undefined }),
}));
