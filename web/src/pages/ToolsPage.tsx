/**
 * 工具治理: 治理指标卡(总量/可见数/Schema Token/FC 准确率) + 执行域分布 + 逐工具指标表 + Skill 启停.
 * Skill 切换后刷新可见数与指标(治理基线按激活 Skill 静态计算).
 */

import { useCallback, useEffect, useState } from "react";
import { getToolStats, listSkills, toggleSkill } from "../api/endpoints";
import { Card, EmptyState, ErrorAlert, IconButton, PageHeader, Spinner, StatCard, StatusBadge } from "../components/common";
import { Icon } from "../components/icons";
import type { SkillInfo, ToolGovernanceStats } from "../types/api";

const DOMAIN_COLORS: Record<string, string> = {
  direct: "bg-blue-500",
  skill_only: "bg-green-500",
  subagent_only: "bg-purple-500",
  internal: "bg-gray-400",
};

const DOMAIN_LABELS: Record<string, string> = {
  direct: "direct(主 Agent 直连)",
  skill_only: "skill_only(Skill 域)",
  subagent_only: "subagent_only(子 Agent 域)",
  internal: "internal(内部)",
};

function DomainBreakdown({ breakdown }: { breakdown: Record<string, number> }) {
  const entries = Object.entries(breakdown);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  if (total === 0) return <EmptyState text="无工具" />;
  return (
    <div className="space-y-2">
      {entries.map(([domain, count]) => (
        <div key={domain}>
          <div className="mb-0.5 flex justify-between text-xs text-gray-500">
            <span>{DOMAIN_LABELS[domain] ?? domain}</span>
            <span className="font-medium">{count}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-gray-100">
            <div
              className={`h-full rounded-full ${DOMAIN_COLORS[domain] ?? "bg-gray-400"}`}
              style={{ width: `${(count / total) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function SkillSwitches({
  skills,
  onChange,
}: {
  skills: SkillInfo[];
  onChange: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = async (name: string) => {
    setBusy(name);
    setError(null);
    try {
      await toggleSkill(name);
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-1.5">
      {skills.length === 0 && <EmptyState text="暂无 Skill" />}
      {skills.map((s) => (
        <div key={s.name} className="flex items-center justify-between gap-2 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate text-xs font-medium text-gray-700">{s.name}</span>
              <StatusBadge status={s.enabled ? "ok" : "skipped"} />
              {s.enabled ? "已启用" : "已停用"}
            </div>
            <div className="mt-0.5 truncate text-[10px] text-gray-400" title={s.description}>
              {s.description} · {s.tools.join(", ") || "无工具"}
            </div>
          </div>
          <button
            onClick={() => void toggle(s.name)}
            disabled={busy === s.name}
            className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
              s.enabled
                ? "border-red-200 bg-surface text-red-600 hover:bg-red-50 dark:border-red-500/40 dark:text-red-400 dark:hover:bg-red-500/10"
                : "border-green-200 bg-surface text-green-700 hover:bg-green-50 dark:border-green-500/40 dark:text-green-400 dark:hover:bg-green-500/10"
            } disabled:opacity-50`}
          >
            {busy === s.name ? "切换中…" : s.enabled ? "停用" : "启用"}
          </button>
        </div>
      ))}
      {error && <div className="pt-1"><ErrorAlert message={error} /></div>}
    </div>
  );
}

export default function ToolsPage() {
  const [stats, setStats] = useState<ToolGovernanceStats | null>(null);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, sk] = await Promise.all([getToolStats(), listSkills()]);
      setStats(s);
      setSkills(sk);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (loading && !stats) return <Spinner text="加载工具治理数据…" />;
  if (error && !stats) return <ErrorAlert message={error} onRetry={() => void refresh()} />;

  return (
    <div className="flex h-full flex-col gap-4">
      <PageHeader title="工具治理" desc="治理指标与 Skill 启停" />
      {error && <ErrorAlert message={error} />}
      {/* 指标卡 */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="工具总量" value={stats?.total_tools ?? 0} sub="注册工具数" />
        <StatCard label="主 Agent 可见工具" value={stats?.visible_tools ?? 0} sub="激活 Skill 下的可见工具" accent="text-blue-600" />
        <StatCard label="注入 Schema Token" value={(stats?.schema_tokens ?? 0).toLocaleString()} sub="全部可见工具 Schema 合计" accent="text-purple-600" />
        <StatCard
          label="FC 准确率"
          value={stats ? `${(stats.accuracy * 100).toFixed(1)}%` : "-"}
          sub="运行时工具调用统计"
          accent="text-green-600"
        />
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-2 gap-4">
        <Card title="执行域分布" className="h-full">
          {stats && <DomainBreakdown breakdown={stats.domain_breakdown} />}
        </Card>
        <Card
          title={`Skill 启停 (${skills.length})`}
          className="h-full"
          actions={
            <IconButton onClick={() => void refresh()} title="刷新">
              <Icon name="refresh" className="h-4 w-4" />
            </IconButton>
          }
        >
          <SkillSwitches skills={skills} onChange={() => void refresh()} />
        </Card>
      </div>

      {/* 逐工具指标表 */}
      <Card title="逐工具调用指标" className="min-h-0 flex-1">
        {!stats || stats.metrics.length === 0 ? (
          <EmptyState text="暂无工具调用记录" hint="发起对话触发工具调用后此处展示指标" />
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs text-gray-400">
                  <th className="pb-2 pr-2 font-medium">工具</th>
                  <th className="pb-2 pr-2 font-medium">执行域</th>
                  <th className="pb-2 pr-2 font-medium">调用次数</th>
                  <th className="pb-2 pr-2 font-medium">成功率</th>
                  <th className="pb-2 pr-2 font-medium">平均耗时</th>
                  <th className="pb-2 font-medium">Token 消耗</th>
                </tr>
              </thead>
              <tbody>
                {stats.metrics.map((m) => (
                  <tr key={m.tool} className="border-b border-gray-100 text-gray-600">
                    <td className="py-2 pr-2 font-mono text-xs font-medium text-gray-800">{m.tool}</td>
                    <td className="py-2 pr-2 text-xs">{m.domain}</td>
                    <td className="py-2 pr-2">{m.calls}</td>
                    <td className="py-2 pr-2">
                      <span className={m.success_rate >= 0.9 ? "text-green-600" : m.success_rate >= 0.5 ? "text-yellow-600" : "text-red-600"}>
                        {(m.success_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2 pr-2">{m.avg_latency_ms.toFixed(1)} ms</td>
                    <td className="py-2">{m.token_count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
