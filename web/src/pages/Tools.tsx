import { useState } from 'react';
import { Row, Col, Card, Table, Tag, Switch, Progress, Space, Typography, Button, message } from 'antd';
import {
  ToolOutlined,
  NodeIndexOutlined,
  ApiOutlined,
  CheckCircleFilled,
  ReloadOutlined,
} from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import StatCard from '@/components/StatCard';
import { DomainTag } from '@/components/StatusTag';
import { useAsync } from '@/hooks/useAsync';
import { skillsApi } from '@/api/skills';
import { toolsApi } from '@/api/tools';
import { formatMs, formatPct } from '@/lib/format';
import type { SkillDefinition, ExecutionDomain } from '@/types';

const { Text } = Typography;

/** 执行域展示顺序与配色（对齐 StatusTag PALETTE） */
const DOMAINS: ExecutionDomain[] = ['direct', 'skill_only', 'subagent_only', 'internal'];
const DOMAIN_COLOR: Record<ExecutionDomain, string> = {
  direct: '#4f5d3a',
  skill_only: '#934828',
  subagent_only: '#b0562f',
  internal: 'var(--kf-text-2)',
};

export default function Tools() {
  const [msgApi, ctx] = message.useMessage();
  const [toggling, setToggling] = useState<string | null>(null);

  const stats = useAsync(() => toolsApi.stats(), []);
  const skills = useAsync(() => skillsApi.list(), []);

  const handleToggle = async (name: string, enabled: boolean) => {
    setToggling(name);
    try {
      await skillsApi.toggle(name, enabled);
      msgApi.success(`已${enabled ? '启用' : '停用'} Skill · ${name}`);
      skills.reload();
    } catch (e) {
      msgApi.error((e as Error).message);
      skills.reload(); // 失败回滚开关状态
    } finally {
      setToggling(null);
    }
  };

  const s = stats.data;
  const breakdown = s?.domain_breakdown;
  const domainTotal = breakdown
    ? DOMAINS.reduce((sum, d) => sum + (breakdown[d] ?? 0), 0)
    : 0;

  return (
    <div className="kf-fade-in">
      {ctx}
      <PageHeader
        title="工具治理"
        subtitle="执行域隔离 · Schema 动态注入 · Skill 启停与工具调用指标"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              stats.reload();
              skills.reload();
            }}
          >
            刷新
          </Button>
        }
      />

      {/* 治理统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} md={12} lg={6}>
          <StatCard
            title="总工具数"
            value={s?.total_tools ?? 0}
            icon={<ToolOutlined />}
            loading={stats.loading}
          />
        </Col>
        <Col xs={12} md={12} lg={6}>
          <StatCard
            title="单轮可见工具数"
            value={s?.visible_tools ?? 0}
            trend={-34.2}
            trendLabel="执行域隔离后"
            icon={<NodeIndexOutlined />}
            invertTrend
            loading={stats.loading}
          />
        </Col>
        <Col xs={12} md={12} lg={6}>
          <StatCard
            title="Schema Token"
            value={s?.schema_tokens ?? 0}
            trend={-32.6}
            trendLabel="动态注入后"
            icon={<ApiOutlined />}
            invertTrend
            loading={stats.loading}
          />
        </Col>
        <Col xs={12} md={12} lg={6}>
          {/* accuracy 为 0-1 分数，按百分比展示 */}
          <StatCard
            title="Function Calling 准确率"
            value={(s?.accuracy ?? 0) * 100}
            suffix="%"
            precision={1}
            icon={<CheckCircleFilled />}
            loading={stats.loading}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* Skill 列表 */}
        <Col xs={24} lg={16}>
          <Card title="Skill 列表" bordered={false} style={{ height: '100%' }}>
            <Table
              rowKey="name"
              size="small"
              loading={skills.loading}
              dataSource={skills.data ?? []}
              scroll={{ x: 960 }}
              pagination={{ pageSize: 8, showSizeChanger: false }}
              columns={[
                {
                  title: '名称',
                  dataIndex: 'name',
                  width: 160,
                  render: (v: string) => <Text strong>{v}</Text>,
                },
                {
                  title: '描述',
                  dataIndex: 'description',
                  render: (v: string) => (
                    <Text type="secondary" style={{ fontSize: 13 }}>
                      {v}
                    </Text>
                  ),
                },
                {
                  title: '执行域',
                  dataIndex: 'domain',
                  width: 180,
                  render: (d: ExecutionDomain) => <DomainTag domain={d} />,
                },
                {
                  title: '工具',
                  dataIndex: 'tools',
                  width: 220,
                  render: (tools: string[]) => (
                    <Space wrap size={[4, 4]}>
                      {tools.length === 0 ? (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          -
                        </Text>
                      ) : (
                        tools.map((t) => (
                          <Tag key={t} style={{ borderRadius: 6, margin: 0 }}>
                            {t}
                          </Tag>
                        ))
                      )}
                    </Space>
                  ),
                },
                {
                  title: '依赖',
                  dataIndex: 'dependencies',
                  width: 180,
                  render: (deps: string[]) =>
                    deps.length === 0 ? (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        -
                      </Text>
                    ) : (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {deps.join(', ')}
                      </Text>
                    ),
                },
                {
                  title: '启用',
                  dataIndex: 'enabled',
                  width: 72,
                  fixed: 'right',
                  render: (enabled: boolean, record: SkillDefinition) => (
                    <Switch
                      checked={enabled}
                      loading={toggling === record.name}
                      onChange={(checked) => handleToggle(record.name, checked)}
                    />
                  ),
                },
              ]}
            />
          </Card>
        </Col>

        {/* 执行域分布 */}
        <Col xs={24} lg={8}>
          <Card title="执行域分布" bordered={false} style={{ height: '100%' }}>
            {!breakdown ? (
              <EmptyState description="暂无分布数据 · 后端 /tools/stats 不可用" />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size={14}>
                {DOMAINS.map((d) => {
                  const count = breakdown[d] ?? 0;
                  const pct = domainTotal > 0 ? (count / domainTotal) * 100 : 0;
                  return (
                    <div key={d}>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: 6,
                        }}
                      >
                        <DomainTag domain={d} />
                        <Text style={{ fontSize: 13 }}>
                          {count} 工具 · {Math.round(pct)}%
                        </Text>
                      </div>
                      <Progress
                        percent={Math.round(pct)}
                        strokeColor={DOMAIN_COLOR[d]}
                        size="small"
                        showInfo={false}
                      />
                    </div>
                  );
                })}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  共 {domainTotal} 个工具，按执行域隔离可见性
                </Text>
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      {/* 工具调用指标 */}
      <Card title="工具调用指标" bordered={false} style={{ marginTop: 16 }}>
        <Table
          rowKey="tool"
          size="small"
          loading={stats.loading}
          dataSource={s?.metrics ?? []}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          columns={[
            {
              title: '工具名',
              dataIndex: 'tool',
              width: 180,
              render: (v: string) => <Text strong>{v}</Text>,
            },
            {
              title: '调用次数',
              dataIndex: 'calls',
              width: 100,
              render: (v: number) => v,
            },
            {
              title: '成功率',
              dataIndex: 'success_rate',
              width: 180,
              render: (rate: number) => (
                <Progress
                  percent={Math.round(rate * 100)}
                  size="small"
                  strokeColor="#788c5d"
                  format={() => formatPct(rate)}
                />
              ),
            },
            {
              title: '平均耗时',
              dataIndex: 'avg_latency_ms',
              width: 110,
              render: (ms: number) => formatMs(ms),
            },
            {
              title: 'Token',
              dataIndex: 'token_count',
              width: 100,
              render: (v: number) => v,
            },
            {
              title: '执行域',
              dataIndex: 'domain',
              width: 180,
              render: (d: ExecutionDomain) => <DomainTag domain={d} />,
            },
          ]}
        />
      </Card>
    </div>
  );
}
