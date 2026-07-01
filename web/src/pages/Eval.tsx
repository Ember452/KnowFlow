import { useState } from 'react';
import { Row, Col, Card, Table, Button, Space, Select, Typography, message } from 'antd';
import {
  ThunderboltOutlined,
  ReloadOutlined,
  ArrowRightOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
} from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { EvalStatusTag } from '@/components/StatusTag';
import { useAsync } from '@/hooks/useAsync';
import { evalApi } from '@/api/eval';
import { formatMs, formatPct, formatTime } from '@/lib/format';
import type { EvalRun, EvalStatus, EvalMetrics } from '@/types';

const { Text } = Typography;

/** 评测指标定义：label / 说明 / 格式化 / 方向（higherIsBetter） */
const METRICS: Array<{
  key: keyof EvalMetrics;
  label: string;
  desc: string;
  format: (v?: number) => string;
  higherIsBetter: boolean;
}> = [
  { key: 'recall_at_10', label: 'Recall@10', desc: '召回率', format: formatPct, higherIsBetter: true },
  { key: 'mrr', label: 'MRR', desc: '平均倒数排名', format: formatPct, higherIsBetter: true },
  { key: 'ndcg', label: 'NDCG', desc: '归一化折损累积增益', format: formatPct, higherIsBetter: true },
  { key: 'tool_accuracy', label: '工具准确率', desc: 'Function Calling 准确率', format: formatPct, higherIsBetter: true },
  { key: 'latency_ms', label: '延迟', desc: '端到端耗时', format: formatMs, higherIsBetter: false },
];

const DATASET_OPTIONS = [
  { value: 'knowledge_qa_eval.jsonl', label: 'knowledge_qa_eval.jsonl' },
  { value: 'tool_calling_eval.jsonl', label: 'tool_calling_eval.jsonl' },
];

/** 提升是否为正面：latency 下降为正面，其余上升为正面 */
function isPositive(key: keyof EvalMetrics, imp: number): boolean {
  return key === 'latency_ms' ? imp < 0 : imp > 0;
}

/** 对比表行数据 */
interface CmpRow {
  key: string;
  label: string;
  desc: string;
  baseline: string;
  graphrag: string;
  improvement?: number;
  higherIsBetter: boolean;
}

export default function Eval() {
  const [msgApi, ctx] = message.useMessage();
  const runs = useAsync(() => evalApi.runs(), []);
  const [dataset, setDataset] = useState('knowledge_qa_eval.jsonl');
  const [running, setRunning] = useState(false);
  const [detail, setDetail] = useState<EvalRun | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadDetail = async (runId: number) => {
    setDetailLoading(true);
    try {
      setDetail(await evalApi.getRun(runId));
    } catch (e) {
      msgApi.error((e as Error).message);
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleRun = async () => {
    setRunning(true);
    try {
      const r = await evalApi.run(dataset);
      msgApi.success(`评测已触发 · run_id = ${r.run_id}`);
      runs.reload();
      await loadDetail(r.run_id);
    } catch (e) {
      msgApi.error((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const runColumns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '数据集', dataIndex: 'dataset' },
    { title: '状态', dataIndex: 'status', width: 100, render: (s: EvalStatus) => <EvalStatusTag status={s} /> },
    { title: '开始时间', dataIndex: 'started_at', width: 180, render: formatTime },
  ];

  const cmpData: CmpRow[] = detail
    ? METRICS.map((m) => ({
        key: m.key,
        label: m.label,
        desc: m.desc,
        baseline: m.format(detail.baseline[m.key]),
        graphrag: m.format(detail.graphrag[m.key]),
        improvement: detail.improvement?.[m.key],
        higherIsBetter: m.higherIsBetter,
      }))
    : [];

  const cmpColumns = [
    { title: '指标', dataIndex: 'label', width: 140 },
    { title: '说明', dataIndex: 'desc', width: 200 },
    { title: 'Baseline', dataIndex: 'baseline', width: 120 },
    { title: 'GraphRAG', dataIndex: 'graphrag', width: 120 },
    {
      title: '提升幅度',
      dataIndex: 'improvement',
      width: 140,
      render: (imp: number | undefined, r: CmpRow) => {
        if (imp === undefined || imp === null) return <Text type="secondary">-</Text>;
        const good = r.higherIsBetter ? imp > 0 : imp < 0;
        return (
          <span style={{ color: good ? '#788c5d' : '#d64545', fontWeight: 500 }}>
            {imp > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(imp).toFixed(1)}%
          </span>
        );
      },
    },
  ];

  return (
    <div className="kf-fade-in">
      {ctx}
      <PageHeader
        title="评测对比"
        subtitle="Baseline vs GraphRAG 指标对比 · 检索召回 / 工具准确率 / 延迟"
        extra={
          <Space wrap>
            <Select
              value={dataset}
              onChange={setDataset}
              style={{ width: 240 }}
              options={DATASET_OPTIONS}
            />
            <Button type="primary" icon={<ThunderboltOutlined />} loading={running} onClick={handleRun}>
              发起评测
            </Button>
            <Button icon={<ReloadOutlined />} onClick={runs.reload}>
              刷新
            </Button>
          </Space>
        }
      />

      {/* 评测运行列表 */}
      <Card title="评测运行列表" bordered={false} style={{ marginBottom: 16 }}>
        <Table
          rowKey="id"
          size="small"
          loading={runs.loading}
          dataSource={runs.data ?? []}
          locale={{ emptyText: <EmptyState description="暂无评测记录 · 点击「发起评测」开始" /> }}
          columns={runColumns}
          onRow={(r) => ({
            onClick: () => loadDetail(r.id),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>

      {/* Baseline vs GraphRAG 对比 */}
      <Card
        title="Baseline vs GraphRAG 对比"
        bordered={false}
        style={{ marginBottom: 16 }}
        loading={detailLoading && !detail}
        extra={
          detail && (
            <Space size="large">
              <Text type="secondary" style={{ fontSize: 12 }}>run #{detail.run_id}</Text>
              <EvalStatusTag status={detail.status} />
              <Text type="secondary" style={{ fontSize: 12 }}>{detail.dataset}</Text>
              {detail.completed_at && (
                <Text type="secondary" style={{ fontSize: 12 }}>完成于 {formatTime(detail.completed_at)}</Text>
              )}
            </Space>
          )
        }
      >
        {!detail ? (
          <EmptyState description={detailLoading ? '加载评测详情...' : '选择一次评测运行查看 Baseline vs GraphRAG 对比'} />
        ) : (
          <>
            {/* 指标对比卡片 */}
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
              {METRICS.map((m) => {
                const imp = detail.improvement?.[m.key];
                const good = imp !== undefined && isPositive(m.key, imp);
                return (
                  <Col xs={24} sm={12} lg={8} key={m.key}>
                    <Card size="small" bordered={false} style={{ height: '100%', background: 'var(--kf-surface-tint)' }}>
                      <div style={{ marginBottom: 12 }}>
                        <Text strong>{m.label}</Text>
                        <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>{m.desc}</Text>
                      </div>
                      <Row align="middle" gutter={8}>
                        <Col span={9}>
                          <Text type="secondary" style={{ fontSize: 12 }}>Baseline</Text>
                          <div style={{ fontSize: 20, fontWeight: 600 }}>{m.format(detail.baseline[m.key])}</div>
                        </Col>
                        <Col span={6} style={{ textAlign: 'center' }}>
                          <ArrowRightOutlined style={{ color: '#c96442', fontSize: 14 }} />
                          {imp !== undefined && (
                            <div style={{ fontSize: 12, marginTop: 4, color: good ? '#788c5d' : '#d64545' }}>
                              {imp > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(imp).toFixed(1)}%
                            </div>
                          )}
                        </Col>
                        <Col span={9}>
                          <Text type="secondary" style={{ fontSize: 12 }}>GraphRAG</Text>
                          <div style={{ fontSize: 20, fontWeight: 600, color: '#c96442' }}>
                            {m.format(detail.graphrag[m.key])}
                          </div>
                        </Col>
                      </Row>
                    </Card>
                  </Col>
                );
              })}
            </Row>

            {/* 指标对比表 */}
            <Table
              rowKey="key"
              dataSource={cmpData}
              columns={cmpColumns}
              pagination={false}
              size="small"
            />
          </>
        )}
      </Card>
    </div>
  );
}
