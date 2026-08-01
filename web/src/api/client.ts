/**
 * fetch 封装: 统一注入 X-User-Id, 错误解析, JSON 解析.
 * 后端响应信封不统一, 具体接口的 unwrap 逻辑在 endpoints.ts 中按契约处理.
 */

const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function getUserId(): string {
  return localStorage.getItem("knowflow.user_id") || "demo";
}

export function setUserId(userId: string): void {
  localStorage.setItem("knowflow.user_id", userId);
}

export interface RequestOptions extends RequestInit {
  userId?: string;
}

/** 统一请求: 注入 X-User-Id / JSON 序列化 / 错误转 ApiError, 返回已解析 JSON(未解信封). */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { userId, headers, body, ...rest } = options;
  const isFormData = body instanceof FormData;
  const resp = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      "X-User-Id": userId ?? getUserId(),
      ...headers,
    },
    body,
  });
  if (!resp.ok) {
    throw await parseError(resp);
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return (await resp.json()) as T;
}

/** 解析非 2xx 响应为 ApiError(兼容信封 ErrorResponse 与 FastAPI HTTPException). */
async function parseError(resp: Response): Promise<ApiError> {
  let code = "HTTP-" + resp.status;
  let message = `请求失败: HTTP ${resp.status}`;
  let details: Record<string, unknown> = {};
  try {
    const body = (await resp.json()) as Record<string, unknown>;
    if (typeof body.code === "string" && typeof body.message === "string") {
      code = body.code;
      message = body.message;
      if (body.details && typeof body.details === "object") {
        details = body.details as Record<string, unknown>;
      }
    } else if (typeof body.detail === "string") {
      message = body.detail;
    }
  } catch {
    // 非 JSON 错误体(如网关错误), 保留默认消息
  }
  return new ApiError(resp.status, code, message, details);
}
