import { request } from './client';
import type { SkillDefinition, ToggleSkillResult } from '@/types';

export const skillsApi = {
  /** Skill 列表与启停状态 */
  list: () => request<SkillDefinition[]>('/skills'),

  /** 启用/停用 Skill */
  toggle: (name: string, enabled: boolean) =>
    request<ToggleSkillResult>(`/skills/${name}/toggle`, {
      method: 'PUT',
      body: { enabled },
    }),
};
