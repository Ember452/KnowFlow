import { request, getAuthHeaders } from './client';
import type { KnowDocument, UploadResult } from '@/types';

export const documentsApi = {
  /** 文档列表（按用户隔离，需 X-User-Id） */
  list: (userId?: string) =>
    request<KnowDocument[]>('/documents', { headers: getAuthHeaders(userId) }),

  /** 上传文档（pdf/docx/md/txt ≤50MB），入队异步索引；归属当前用户 */
  upload: (file: File, userId?: string) => {
    const form = new FormData();
    form.append('file', file);
    return request<UploadResult>('/documents/upload', {
      method: 'POST',
      body: form,
      headers: getAuthHeaders(userId),
    });
  },

  /** 删除文档与索引 */
  remove: (docId: number) =>
    request<void>(`/documents/${docId}`, { method: 'DELETE' }),

  /** 重新索引 */
  reindex: (docId: number) =>
    request<UploadResult>(`/documents/${docId}/reindex`, { method: 'POST' }),
};
