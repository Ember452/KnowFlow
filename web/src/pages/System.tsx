import { Row, Col, Card, Table, Tag, Button, Space, Typography, Alert, Descriptions, List, message } from 'antd';
import {
  ReloadOutlined,
  HeartOutlined,
  ApiOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  CloudServerOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { useAsync } from '@/hooks/useAsync';
import { healthApi } from '@/api/health';
import { formatMs } from '@/lib/format';
import { API_ENDPOINTS, type ApiEndpoint } from '@/generated/apiEndpoints';
import type { HealthStatus, ReadyStatus, DependencyStatus } from '@/types';

const { Text } = Typography;

/** 依赖值可能是对象或字符串 'ok'/'error'，统一判定是否健康 */
function isOk(v: DependencyStatus | 'ok' | 'error' | undefined): boolean {
  if (typeof v === 'string') return v === 'ok';
  return v?.status === 'ok';
}

/** KnowFlow 技术栈（静态展示） */
const TECH_STACK = [
  { label: '后端', value: 'Python 3.13 + FastAPI + LangGraph + LangChain' },
  { label: '向量库', value: 'Milvus' },
  { label: '关系库', value: 'PostgreSQL' },
  { label: '对象存储', value: 'MinIO' },
  { label: '缓存', value: 'Redis' },
  { label: '前端', value: 'React 18 + TypeScript + Vite + Ant Design + zustand' },
];

const METHOD_COLOR: Record<ApiEndpoint['method'], string> = {
  GET: 'blue',
  POST: 'green',
  PUT: 'orange',
  DELETE: 'red',
};

/** 依赖表格行：依赖名 + 原始值（对象或字符串） */
interface DepRow {
  key: string;
  name: string;
  value: DependencyStatus | 'ok' | 'error' | undefined;
}

export default function System() {
  const [msgApi, ctx] = message.useMessage();
  const healthz = useAsync<HealthStatus>(() => healthApi.healthz(), []);
  const readyz = useAsync<ReadyStatus>(() => healthApi.readyz(), []);

  const handleRefresh = () => {
    healthz.reload();
    readyz.reload();
    msgApi.success('已触发探针刷新');
  };

  const depRows: DepRow[] = readyz.data
    ? Object.entries(readyz.data.dependencies ?? {}).map(([name, value]) => ({ key: name, name, value }))
    : [];

  return (
    <div className="kf-fade-in">
      {ctx}
      <PageHeader
        title="系统"
        subtitle="健康检查 · 依赖状态 · 技术栈与 API 端点清单"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={healthz.loading || readyz.loading}
          >
            刷新探针
          </Button>
        }
      />

      {/* 健康检查面板：存活探针 + 就绪探针 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            title={<Space><HeartOutlined style={{ color: '#c96442' }} />存活探针</Space>}
            bordered={false}
            style={{ height: '100%' }}
            extra={<Text type="secondary" style={{ fontSize: 12 }}>GET /healthz</Text>}
          >
            {healthz.loading ? (
              <List loading />
            ) : healthz.error || !healthz.data ? (
              <EmptyState description="无法连接后端 · 请启动 uvicorn" actionText="重试" onAction={healthz.reload} />
            ) : (
              <Alert
                type={healthz.data.status === 'ok' ? 'success' : 'error'}
                showIcon
                message={healthz.data.status === 'ok' ? '进程存活 (Liveness)' : '进程异常'}
                description={
                  <Space>
                    {healthz.data.status === 'ok' ? (
                      <CheckCircleFilled style={{ color: '#788c5d' }} />
                    ) : (
                      <CloseCircleFilled style={{ color: '#d64545' }} />
                    )}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      仅探测进程存活，不检查依赖连通性
                    </Text>
                  </Space>
                }
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            title={<Space><CloudServerOutlined style={{ color: '#c96442' }} />就绪探针</Space>}
            bordered={false}
            style={{ height: '100%' }}
            extra={<Text type="secondary" style={{ fontSize: 12 }}>GET /readyz</Text>}
          >
            {readyz.loading ? (
              <List loading />
            ) : readyz.error || !readyz.data ? (
              <EmptyState description="后端未就绪或无法连接 · 请启动 uvicorn" actionText="重试" onAction={readyz.reload} />
            ) : (
              <Alert
                type={readyz.data.status === 'ok' ? 'success' : 'error'}
                showIcon
                message={readyz.data.status === 'ok' ? '所有依赖就绪 (Readiness)' : '存在异常依赖'}
                description={
                  <Space>
                    {readyz.data.status === 'ok' ? (
                      <CheckCircleFilled style={{ color: '#788c5d' }} />
                    ) : (
                      <CloseCircleFilled style={{ color: '#d64545' }} />
                    )}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      检查 PostgreSQL / Redis / Milvus / MinIO 连通性 · 共 {depRows.length} 项依赖
                    </Text>
                  </Space>
                }
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* 依赖状态表格 */}
      <Card
        title="依赖状态"
        bordered={false}
        style={{ marginTop: 16 }}
        extra={<Text type="secondary" style={{ fontSize: 12 }}>解析 readyz.dependencies</Text>}
      >
        <Table
          rowKey="key"
          loading={readyz.loading}
          dataSource={depRows}
          locale={{ emptyText: <EmptyState description="暂无依赖状态 · 请检查后端 /readyz" /> }}
          pagination={false}
          columns={[
            {
              title: '依赖名',
              dataIndex: 'name',
              width: 180,
              render: (name: string) => <Text strong>{name}</Text>,
            },
            {
              title: '状态',
              width: 110,
              render: (_: unknown, r: DepRow) => {
                const ok = isOk(r.value);
                return (
                  <Tag color={ok ? 'success' : 'error'} style={{ borderRadius: 6, margin: 0 }}>
                    {ok ? 'ok' : 'error'}
                  </Tag>
                );
              },
            },
            {
              title: '延迟',
              width: 120,
              render: (_: unknown, r: DepRow) => {
                const latency = typeof r.value === 'object' ? r.value?.latency_ms : undefined;
                return <Text type="secondary">{formatMs(latency)}</Text>;
              },
            },
            {
              title: '详情',
              render: (_: unknown, r: DepRow) => {
                const detail = typeof r.value === 'object' ? r.value?.detail : undefined;
                return detail
                  ? <Text type="secondary" style={{ fontSize: 12 }}>{detail}</Text>
                  : <Text type="secondary">-</Text>;
              },
            },
          ]}
        />
      </Card>

      {/* 底部：系统信息 + API 端点清单 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={10}>
          <Card
            title={<Space><DatabaseOutlined style={{ color: '#c96442' }} />系统信息</Space>}
            bordered={false}
            style={{ height: '100%' }}
          >
            <Descriptions column={1} size="small" colon labelStyle={{ width: 90, color: '#8c8c8c' }}>
              {TECH_STACK.map((t) => (
                <Descriptions.Item key={t.label} label={t.label}>
                  <Text style={{ fontSize: 13 }}>{t.value}</Text>
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card
            title={<Space><ApiOutlined style={{ color: '#c96442' }} />API 端点清单</Space>}
            bordered={false}
            style={{ height: '100%' }}
            extra={<Text type="secondary" style={{ fontSize: 12 }}>{API_ENDPOINTS.length} 个端点</Text>}
          >
            <Table
              rowKey="path"
              size="small"
              dataSource={API_ENDPOINTS}
              pagination={false}
              scroll={{ y: 420 }}
              columns={[
                {
                  title: '方法',
                  dataIndex: 'method',
                  width: 80,
                  render: (m: ApiEndpoint['method']) => (
                    <Tag color={METHOD_COLOR[m]} style={{ borderRadius: 6, margin: 0 }}>{m}</Tag>
                  ),
                },
                {
                  title: '路径',
                  dataIndex: 'path',
                  render: (p: string) => <Text code style={{ fontSize: 12 }}>{p}</Text>,
                },
                {
                  title: '说明',
                  dataIndex: 'desc',
                  width: 150,
                  render: (d: string) => <Text type="secondary" style={{ fontSize: 12 }}>{d}</Text>,
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
