import { useState } from 'react';
import { Card, Input, InputNumber, Button, Space, Typography, Tag, Row, Col, Table, message } from 'antd';
import { SearchOutlined, NodeIndexOutlined, ApartmentOutlined, StarOutlined, ThunderboltOutlined } from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { knowledgeApi } from '@/api/knowledge';
import { formatMs } from '@/lib/format';
import type { SearchResponse, Entity, RetrievalSource } from '@/types';

const { Text } = Typography;

const SOURCE_COLOR: Record<RetrievalSource, string> = {
  vector: 'blue',
  bm25: 'geekblue',
  hybrid: 'cyan',
  graph_expand: 'purple',
  rerank: 'orange',
};

/** GraphRAG 全链路各阶段卡片 */
const STAGES = [
  { title: 'Hybrid 召回', desc: '向量(Milvus) + BM25(PG tsvector) 双路召回', icon: <SearchOutlined /> },
  { title: 'RRF 融合', desc: 'Reciprocal Rank Fusion 合并双路结果', icon: <NodeIndexOutlined /> },
  { title: '一跳扩展', desc: '基于实体关系 SQL JOIN 召回跨文档 chunk', icon: <ApartmentOutlined /> },
  { title: 'Reranker 精排', desc: 'cross-encoder 对 (query, chunk) 重排', icon: <StarOutlined /> },
];

export default function Retrieval() {
  const [msgApi, ctx] = message.useMessage();
  const [query, setQuery] = useState('员工年假制度');
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResponse | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      setResult(await knowledgeApi.search(query.trim(), topK));
    } catch (e) {
      msgApi.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const sources = result?.chunks ?? [];
  const bySource = sources.reduce<Record<string, number>>((acc, c) => {
    acc[c.source] = (acc[c.source] ?? 0) + 1;
    return acc;
  }, {});
  const entities = result?.entity_hits ?? [];

  return (
    <div className="kf-fade-in">
      {ctx}
      <PageHeader title="检索调试" subtitle="GraphRAG 全链路可视化：Hybrid 召回 → RRF 融合 → 一跳扩展 → 精排" />

      <Card bordered={false} style={{ marginBottom: 16 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="检索查询" onPressEnter={handleSearch} prefix={<SearchOutlined />} />
          <InputNumber min={1} max={20} value={topK} onChange={(v) => setTopK(v ?? 5)} style={{ width: 110 }} addonBefore="top_k" />
          <Button type="primary" loading={loading} onClick={handleSearch} icon={<ThunderboltOutlined />}>执行检索</Button>
        </Space.Compact>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {STAGES.map((s, i) => (
          <Col xs={12} md={6} key={s.title}>
            <Card size="small" bordered={false} style={{ height: '100%', background: 'var(--kf-surface-tint)' }}>
              <Space direction="vertical" size={4}>
                <Space>
                  <span style={{ color: '#c96442' }}>{s.icon}</span>
                  <Text type="secondary" style={{ fontSize: 11 }}>阶段 {i + 1}</Text>
                </Space>
                <Text strong>{s.title}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>{s.desc}</Text>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card
            title="召回结果"
            bordered={false}
            extra={result && <Tag style={{ borderRadius: 6 }}>耗时 {formatMs(result.latency_ms)}</Tag>}
          >
            {!result ? (
              <EmptyState description="执行检索后展示召回片段与分数" />
            ) : (
              <Table
                rowKey="chunk_id"
                dataSource={sources}
                pagination={{ pageSize: 8 }}
                columns={[
                  { title: '#', dataIndex: 'chunk_id', width: 60 },
                  {
                    title: '来源', dataIndex: 'source', width: 120,
                    render: (s: RetrievalSource) => <Tag color={SOURCE_COLOR[s]} style={{ borderRadius: 6, margin: 0 }}>{s}</Tag>,
                  },
                  { title: '分数', dataIndex: 'score', width: 90, render: (v: number) => v.toFixed(3) },
                  { title: '内容', dataIndex: 'content', render: (v: string) => <Text className="kf-serif" style={{ fontSize: 13 }}>{v}</Text> },
                ]}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="来源分布" bordered={false} style={{ marginBottom: 16 }}>
            {Object.keys(bySource).length === 0 ? (
              <EmptyState description="暂无数据" />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }}>
                {Object.entries(bySource).map(([src, n]) => (
                  <div key={src} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Tag color={SOURCE_COLOR[src as RetrievalSource]} style={{ borderRadius: 6, margin: 0 }}>{src}</Tag>
                    <Text>{n} 片段</Text>
                  </div>
                ))}
              </Space>
            )}
          </Card>
          <Card title="命中实体" bordered={false}>
            {entities.length === 0 ? (
              <EmptyState description="无实体命中" />
            ) : (
              <Space wrap>
                {entities.map((e: Entity, i) => (
                  <Tag key={i} color="orange" style={{ borderRadius: 6 }}>
                    {e.name} <Text type="secondary" style={{ fontSize: 11 }}>· {e.entity_type}</Text>
                  </Tag>
                ))}
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
