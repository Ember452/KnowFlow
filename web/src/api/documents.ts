import { request } from './client';
import type { KnowDocument, UploadResult } from '@/types';

export const documentsApi = {
  /** 文档列表 */
  list: () => request<KnowDocument[]>('/documents'),

  /** 上传文档（pdf/docx/md/txt ≤50MB），入队异步索引 */
  upload: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<UploadResult>('/documents/upload', { method: 'POST', body: form });
  },

  /** 删除文档与索引 */
  remove: (docId: number) =>
    request<void>(`/documents/${docId}`, { method: 'DELETE' }),

  /** 重新索引 */
  reindex: (docId: number) =>
    request<UploadResult>(`/documents/${docId}/reindex`, { method: 'POST' }),
};
