import {
  DashboardOutlined,
  MessageOutlined,
  BookOutlined,
  SearchOutlined,
  ApartmentOutlined,
  ToolOutlined,
  DatabaseOutlined,
  MonitorOutlined,
  BarChartOutlined,
  FolderOpenOutlined,
  SettingOutlined,
  ClusterOutlined,
} from '@ant-design/icons';
import type { ReactNode } from 'react';

export interface NavItem {
  key: string;
  path: string;
  label: string;
  icon: ReactNode;
  /** 模块分组 */
  group: '核心交互' | '知识' | '平台' | '系统';
  desc: string;
}

export const NAV_ITEMS: NavItem[] = [
  { key: 'dashboard', path: '/dashboard', label: '总览', icon: <DashboardOutlined />, group: '核心交互', desc: '平台指标与服务健康' },
  { key: 'chat', path: '/chat', label: '智能对话', icon: <MessageOutlined />, group: '核心交互', desc: 'SSE 流式问答与工具进度' },
  { key: 'knowledge', path: '/knowledge', label: '知识库', icon: <BookOutlined />, group: '知识', desc: '文档管理与检索测试' },
  { key: 'graph', path: '/graph', label: '知识图谱', icon: <ClusterOutlined />, group: '知识', desc: '实体关系力导向可视化' },
  { key: 'retrieval', path: '/retrieval', label: '检索调试', icon: <SearchOutlined />, group: '知识', desc: 'GraphRAG 全链路可视化' },
  { key: 'agents', path: '/agents', label: 'Agent 编排', icon: <ApartmentOutlined />, group: '平台', desc: '多 Agent 委派与并发' },
  { key: 'tools', path: '/tools', label: '工具治理', icon: <ToolOutlined />, group: '平台', desc: 'Skill 与执行域隔离' },
  { key: 'memory', path: '/memory', label: '记忆', icon: <DatabaseOutlined />, group: '平台', desc: '长期记忆与沉淀' },
  { key: 'observability', path: '/observability', label: '可观测', icon: <MonitorOutlined />, group: '平台', desc: '全链路 Trace 与 Replay' },
  { key: 'eval', path: '/eval', label: '评测', icon: <BarChartOutlined />, group: '平台', desc: 'Baseline vs GraphRAG 对比' },
  { key: 'sandbox', path: '/sandbox', label: '沙箱', icon: <FolderOpenOutlined />, group: '平台', desc: '会话隔离工作区' },
  { key: 'system', path: '/system', label: '系统', icon: <SettingOutlined />, group: '系统', desc: '健康检查与配置' },
];

export const NAV_GROUPS: NavItem['group'][] = ['核心交互', '知识', '平台', '系统'];

export function findNavItem(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find((i) => pathname.startsWith(i.path));
}
