import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  InputNumber,
  Space,
  Typography,
  Tag,
  Tooltip,
  Spin,
} from 'antd';
import {
  ReloadOutlined,
  ApartmentOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  CompressOutlined,
} from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { knowledgeApi } from '@/api/knowledge';
import type { GraphData, GraphNode, GraphEdge } from '@/types';

const { Text, Title } = Typography;

/** 实体类型 → 品牌色系映射 */
const TYPE_COLOR: Record<string, string> = {
  person: '#c96442',
  org: '#3996ae',
  organization: '#3996ae',
  product: '#7b8c5a',
  concept: '#934828',
  location: '#6d5d8a',
  event: '#b8860b',
  default: '#9b9890',
};
const colorFor = (t: string) => TYPE_COLOR[t.toLowerCase()] ?? TYPE_COLOR.default;

interface SimNode {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  node: GraphNode;
  fixed: boolean;
}

const W = 1000;
const H = 600;

/** 初始化力导向模拟节点（圆周分布） */
function initSim(nodes: GraphNode[]): SimNode[] {
  const n = nodes.length;
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) / 3;
  return nodes.map((node, i) => ({
    id: node.id,
    node,
    x: cx + R * Math.cos((2 * Math.PI * i) / Math.max(n, 1)),
    y: cy + R * Math.sin((2 * Math.PI * i) / Math.max(n, 1)),
    vx: 0,
    vy: 0,
    r: 14,
    fixed: false,
  }));
}

/** 单步力导向迭代：斥力 + 弹簧 + 中心引力 + 阻尼 */
function step(
  sims: SimNode[],
  edges: GraphEdge[],
  idx: Map<number, number>,
  draggingId: number | null,
) {
  const N = sims.length;
  const kRepel = 4500;
  const kSpring = 0.025;
  const restLen = 130;
  const kCenter = 0.004;
  const damping = 0.86;
  const cx = W / 2;
  const cy = H / 2;

  // 斥力（库仑）
  for (let i = 0; i < N; i++) {
    for (let j = i + 1; j < N; j++) {
      let dx = sims[i].x - sims[j].x;
      let dy = sims[i].y - sims[j].y;
      let d2 = dx * dx + dy * dy;
      if (d2 < 1) {
        d2 = 1;
        dx = Math.random() - 0.5;
        dy = Math.random() - 0.5;
      }
      const d = Math.sqrt(d2);
      const f = kRepel / d2;
      const fx = (dx / d) * f;
      const fy = (dy / d) * f;
      sims[i].vx += fx;
      sims[i].vy += fy;
      sims[j].vx -= fx;
      sims[j].vy -= fy;
    }
  }
  // 弹簧引力（胡克）
  for (const e of edges) {
    const ai = idx.get(e.source);
    const bi = idx.get(e.target);
    if (ai === undefined || bi === undefined) continue;
    const a = sims[ai];
    const b = sims[bi];
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const d = Math.sqrt(dx * dx + dy * dy) || 1;
    const f = kSpring * (d - restLen);
    const fx = (dx / d) * f;
    const fy = (dy / d) * f;
    a.vx += fx;
    a.vy += fy;
    b.vx -= fx;
    b.vy -= fy;
  }
  // 中心引力 + 位置更新
  for (const s of sims) {
    s.vx += (cx - s.x) * kCenter;
    s.vy += (cy - s.y) * kCenter;
    s.vx *= damping;
    s.vy *= damping;
    if (!s.fixed && s.id !== draggingId) {
      s.x += s.vx;
      s.y += s.vy;
      s.x = Math.max(24, Math.min(W - 24, s.x));
      s.y = Math.max(24, Math.min(H - 24, s.y));
    }
  }
}

export default function Graph() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [docId, setDocId] = useState<number | null>(null);
  const [limit, setLimit] = useState(200);
  const [hovered, setHovered] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);

  const simsRef = useRef<SimNode[]>([]);
  const idxRef = useRef<Map<number, number>>(new Map());
  const svgRef = useRef<SVGSVGElement>(null);
  const rafRef = useRef<number>(0);
  const draggingRef = useRef<number | null>(null);
  const [, setTick] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(undefined);
    try {
      const d = await knowledgeApi.getGraph(docId ?? undefined, limit);
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载图谱失败');
    } finally {
      setLoading(false);
    }
  }, [docId, limit]);

  useEffect(() => {
    load();
  }, [load]);

  // 力导向模拟主循环
  useEffect(() => {
    if (!data || data.nodes.length === 0) return;
    simsRef.current = initSim(data.nodes);
    idxRef.current = new Map(data.nodes.map((n, i) => [n.id, i]));
    const edges = data.edges;
    let frame = 0;
    const loop = () => {
      step(simsRef.current, edges, idxRef.current, draggingRef.current);
      frame++;
      // 每 2 帧刷新一次视图，平衡流畅度与性能
      if (frame % 2 === 0) setTick((t) => (t + 1) % 1000000);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [data]);

  // SVG 坐标转换（屏幕 → viewBox）
  const toSvgPoint = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }, []);

  const handleMouseDown = (e: React.MouseEvent, id: number) => {
    e.preventDefault();
    draggingRef.current = id;
    const node = simsRef.current[idxRef.current.get(id)!];
    if (node) node.fixed = true;
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (draggingRef.current === null) return;
    const { x, y } = toSvgPoint(e.clientX, e.clientY);
    const node = simsRef.current[idxRef.current.get(draggingRef.current)!];
    if (node) {
      node.x = x;
      node.y = y;
      node.vx = 0;
      node.vy = 0;
    }
  };
  const handleMouseUp = () => {
    if (draggingRef.current !== null) {
      const node = simsRef.current[idxRef.current.get(draggingRef.current)!];
      if (node) node.fixed = false;
      draggingRef.current = null;
    }
  };

  // hover 高亮：邻居集合
  const neighbors = new Set<number>();
  if (hovered !== null && data) {
    neighbors.add(hovered);
    for (const e of data.edges) {
      if (e.source === hovered) neighbors.add(e.target);
      if (e.target === hovered) neighbors.add(e.source);
    }
  }

  const sims = simsRef.current;
  const edges = data?.edges ?? [];

  return (
    <div className="kf-fade-in">
      <PageHeader
        title="知识图谱"
        subtitle="实体关系可视化 · 力导向布局 · 一跳关系一目了然"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={load}
            loading={loading}
            className="kf-btn-glow"
            style={{ borderRadius: 10 }}
          >
            刷新
          </Button>
        }
      />

      <Row gutter={16}>
        <Col xs={24} lg={18}>
          <Card
            bordered={false}
            className="kf-glass"
            style={{ borderRadius: 14, overflow: 'hidden' }}
            bodyStyle={{ padding: 0 }}
          >
            {/* 控制栏 */}
            <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(227, 224, 212, 0.6)', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
              <Space size={6}>
                <Text type="secondary" style={{ fontSize: 13 }}>文档 ID</Text>
                <InputNumber
                  size="small"
                  min={1}
                  value={docId}
                  onChange={(v) => setDocId(v ?? null)}
                  placeholder="全部"
                  style={{ width: 100 }}
                />
              </Space>
              <Space size={6}>
                <Text type="secondary" style={{ fontSize: 13 }}>节点上限</Text>
                <InputNumber
                  size="small"
                  min={10}
                  max={1000}
                  value={limit}
                  onChange={(v) => setLimit(v ?? 200)}
                  style={{ width: 90 }}
                />
              </Space>
              <Space size={4}>
                <Tooltip title="放大">
                  <Button size="small" icon={<ZoomInOutlined />} onClick={() => setZoom((z) => Math.min(2, z + 0.15))} style={{ borderRadius: 8 }} />
                </Tooltip>
                <Tooltip title="缩小">
                  <Button size="small" icon={<ZoomOutOutlined />} onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))} style={{ borderRadius: 8 }} />
                </Tooltip>
                <Tooltip title="重置缩放">
                  <Button size="small" icon={<CompressOutlined />} onClick={() => setZoom(1)} style={{ borderRadius: 8 }} />
                </Tooltip>
              </Space>
              <div style={{ marginLeft: 'auto' }}>
                <Space size={12}>
                  <Tag style={{ borderRadius: 6, margin: 0 }}>实体 {data?.total ?? 0}</Tag>
                  <Tag style={{ borderRadius: 6, margin: 0 }}>关系 {data?.edges.length ?? 0}</Tag>
                </Space>
              </div>
            </div>

            {/* 画布 */}
            <div style={{ position: 'relative', background: 'linear-gradient(135deg, var(--kf-graph-bg-a) 0%, var(--kf-graph-bg-b) 100%)', minHeight: 560 }}>
              {loading && (
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2 }}>
                  <Spin tip="加载图谱中…" size="large" />
                </div>
              )}
              {error && (
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2 }}>
                  <Text type="danger">{error}</Text>
                </div>
              )}
              {!loading && !error && data && data.nodes.length === 0 && (
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <EmptyState description="知识库暂无实体关系，上传文档并完成索引后生成" />
                </div>
              )}
              {!loading && !error && data && data.nodes.length > 0 && (
                <svg
                  ref={svgRef}
                  viewBox={`0 0 ${W} ${H}`}
                  style={{ width: '100%', height: 560, display: 'block', cursor: draggingRef.current ? 'grabbing' : 'default' }}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                >
                  <defs>
                    {/* 边方向箭头（默认 / hover 高亮两种颜色） */}
                    <marker id="kf-arrow" viewBox="0 0 10 10" refX="11" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#9b9890" />
                    </marker>
                    <marker id="kf-arrow-hover" viewBox="0 0 10 10" refX="11" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#c96442" />
                    </marker>
                  </defs>
                  <g transform={`translate(${W / 2} ${H / 2}) scale(${zoom}) translate(${-W / 2} ${-H / 2})`}>
                    {/* 边 */}
                    {edges.map((e) => {
                      const ai = idxRef.current.get(e.source);
                      const bi = idxRef.current.get(e.target);
                      if (ai === undefined || bi === undefined) return null;
                      const a = sims[ai];
                      const b = sims[bi];
                      if (!a || !b) return null;
                      const active = hovered === null || neighbors.has(e.source) || neighbors.has(e.target);
                      const linked = hovered !== null && (e.source === hovered || e.target === hovered);
                      return (
                        <g key={e.id} opacity={active ? 0.55 : 0.12}>
                          <line
                            x1={a.x}
                            y1={a.y}
                            x2={b.x}
                            y2={b.y}
                            stroke={linked ? '#c96442' : '#9b9890'}
                            strokeWidth={linked ? 2 : 1.2}
                            markerEnd={linked ? 'url(#kf-arrow-hover)' : 'url(#kf-arrow)'}
                          />
                          {/* 悬停关联边时显示关系类型 */}
                          {linked && (
                            <text
                              x={(a.x + b.x) / 2}
                              y={(a.y + b.y) / 2 - 6}
                              textAnchor="middle"
                              fontSize={10}
                              fontFamily="var(--font-mono)"
                              fill="#c96442"
                              style={{ pointerEvents: 'none', userSelect: 'none' }}
                            >
                              {e.relation_type}
                            </text>
                          )}
                        </g>
                      );
                    })}
                    {/* 节点 */}
                    {sims.map((s) => {
                      const active = hovered === null || neighbors.has(s.id);
                      const isHovered = hovered === s.id;
                      const color = colorFor(s.node.entity_type);
                      return (
                        <g
                          key={s.id}
                          transform={`translate(${s.x} ${s.y})`}
                          opacity={active ? 1 : 0.25}
                          style={{ cursor: 'pointer' }}
                          onMouseEnter={() => setHovered(s.id)}
                          onMouseLeave={() => setHovered(null)}
                          onMouseDown={(e) => handleMouseDown(e, s.id)}
                        >
                          <circle
                            r={isHovered ? s.r + 4 : s.r}
                            fill={color}
                            fillOpacity={0.18}
                            stroke={color}
                            strokeWidth={isHovered ? 2.5 : 1.5}
                            style={{ transition: 'r 0.2s ease' }}
                          />
                          <circle r={4} fill={color} />
                          <text
                            y={s.r + 14}
                            textAnchor="middle"
                            fontSize={11}
                            fontFamily="var(--font-serif)"
                            fill={isHovered ? 'var(--kf-text-1)' : 'var(--kf-text-2)'}
                            fontWeight={isHovered ? 600 : 400}
                            style={{ pointerEvents: 'none', userSelect: 'none' }}
                          >
                            {s.node.name.length > 10 ? `${s.node.name.slice(0, 9)}…` : s.node.name}
                          </text>
                        </g>
                      );
                    })}
                  </g>
                </svg>
              )}
            </div>
          </Card>
        </Col>

        {/* 图例 + 详情 */}
        <Col xs={24} lg={6}>
          <Card title="实体类型" bordered={false} className="kf-glass" style={{ borderRadius: 14, marginBottom: 16 }}>
            <Space wrap size={[8, 8]}>
              {Object.entries(TYPE_COLOR).filter(([k]) => k !== 'default').map(([k, v]) => (
                <Tag key={k} style={{ borderRadius: 6, margin: 0, color: v, borderColor: v }}>
                  <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 4, background: v, marginRight: 6 }} />
                  {k}
                </Tag>
              ))}
            </Space>
            <div style={{ marginTop: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                节点圆环颜色对应实体类型。拖拽节点可调整位置，悬停高亮其一跳邻居。
              </Text>
            </div>
          </Card>

          <Card title="选中实体" bordered={false} className="kf-glass" style={{ borderRadius: 14 }}>
            {hovered === null ? (
              <EmptyState description="悬停或拖拽节点查看详情" />
            ) : (
              (() => {
                const s = sims[idxRef.current.get(hovered)!];
                if (!s) return null;
                const rels = edges.filter((e) => e.source === s.id || e.target === s.id);
                return (
                  <div>
                    <Title level={5} className="kf-serif" style={{ marginBottom: 4 }}>{s.node.name}</Title>
                    <Space size={6} direction="vertical" style={{ width: '100%' }}>
                      <Space size={4}>
                        <Tag color={colorFor(s.node.entity_type)} style={{ borderRadius: 6, margin: 0 }}>{s.node.entity_type}</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>doc #{s.node.doc_id}</Text>
                      </Space>
                      {s.node.normalized !== s.node.name && (
                        <Text type="secondary" style={{ fontSize: 12 }}>归一化：{s.node.normalized}</Text>
                      )}
                      <div style={{ marginTop: 4 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>关系（{rels.length}）</Text>
                        <div style={{ marginTop: 6, maxHeight: 200, overflow: 'auto' }}>
                          {rels.slice(0, 20).map((r) => {
                            const other = r.source === s.id ? r.target : r.source;
                            const oi = idxRef.current.get(other);
                            const on = oi !== undefined ? sims[oi] : undefined;
                            return (
                              <Tag key={r.id} style={{ margin: '0 6px 6px 0', borderRadius: 6 }}>
                                <ApartmentOutlined /> {r.relation_type} → {on?.node.name ?? other}
                              </Tag>
                            );
                          })}
                          {rels.length > 20 && <Text type="secondary" style={{ fontSize: 12 }}>…共 {rels.length} 条</Text>}
                        </div>
                      </div>
                    </Space>
                  </div>
                );
              })()
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
