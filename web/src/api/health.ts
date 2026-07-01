import { request } from './client';
import type { HealthStatus, ReadyStatus } from '@/types';

export const healthApi = {
  /** 存活探针（不检查依赖） */
  healthz: () => request<HealthStatus>('/healthz'),
  /** 就绪探针（检查 PG/Redis/Milvus/MinIO） */
  readyz: () => request<ReadyStatus>('/readyz'),
};
