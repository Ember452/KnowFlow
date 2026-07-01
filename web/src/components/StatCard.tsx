import { Card, Statistic } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import type { ReactNode } from 'react';

interface StatCardProps {
  title: string;
  value: number | string;
  suffix?: string;
  precision?: number;
  icon?: ReactNode;
  /** 相对提升/下降，正数绿色向上，负数红色向下 */
  trend?: number;
  trendLabel?: string;
  /** 指标数值越小越好（如耗时/工具数）时传 true：下降显示为正面绿色 */
  invertTrend?: boolean;
  loading?: boolean;
}

/** 指标卡片：悬浮光效 + 图标渐变背景 */
export default function StatCard({
  title,
  value,
  suffix,
  precision,
  icon,
  trend,
  trendLabel = 'vs baseline',
  invertTrend = false,
  loading,
}: StatCardProps) {
  const up = (trend ?? 0) >= 0;
  // 颜色按正负面着色：默认上升为正面；invertTrend 时下降为正面
  const good = invertTrend ? !up : up;
  return (
    <Card
      loading={loading}
      bordered={false}
      className="kf-card-hover"
      style={{ height: '100%', overflow: 'hidden' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Statistic
          title={<span style={{ fontSize: 13 }}>{title}</span>}
          value={value}
          precision={precision}
          suffix={suffix}
          valueStyle={{ fontSize: 28 }}
        />
        {icon && (
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'linear-gradient(135deg, rgba(201, 100, 66, 0.1), rgba(217, 119, 87, 0.06))',
              color: '#c96442',
              fontSize: 17,
              transition: 'transform 0.3s cubic-bezier(0.34, 1.3, 0.64, 1)',
            }}
            className="kf-card-icon"
          >
            {icon}
          </div>
        )}
      </div>
      {trend !== undefined && (
        <div style={{ marginTop: 6, fontSize: 12 }}>
          <span style={{ color: good ? '#788c5d' : '#d64545' }}>
            {up ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(trend).toFixed(1)}%
          </span>
          <span style={{ color: 'var(--kf-text-3)', marginLeft: 6 }}>{trendLabel}</span>
        </div>
      )}
    </Card>
  );
}
