/**
 * 评测中心: 触发静态评测(可复现) + 指标结果表 + CSV 导出.
 * 对齐后端 /eval/run(static 模式) 与 /eval/runs/{id}.
 */

import { useState } from "react";
import { getEvalRun, runEval } from "../api/endpoints";
import { Button, Card, EmptyState, ErrorAlert, PageHeader, Spinner, StatCard } from "../components/common";
import { Icon } from "../components/icons";
import type { EvalRunInfo } from "../types/api";

const DATASETS = [
  { value: "retrieval_eval", label: "检索评测集 (recall@10 / MRR)" },
  { value: "knowledge_qa_eval", label: "知识问答评测集 (关键点命中率)" },
];

function toCsv(results: EvalRunInfo["results"]): string {
  const keys = results.length > 0 ? Object.keys(results[0]) : [];
  const esc = (v: unknown) => {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const header = ["#", ...keys];
  const rows = results.map((r, i) => [i + 1, ...keys.map((k) => esc(r[k]))]);
  return [header, ...rows].map((row) => row.join(",")).join("\n");
}

export default function EvalPage() {
  const [dataset, setDataset] = useState("retrieval_eval");
  const [topK, setTopK] = useState(10);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvalRunInfo | null>(null);

  const trigger = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const info = await runEval({ dataset, mode: "static", top_k: topK });
      setResult(info);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  const loadResult = async (runId: number) => {
    try {
      const info = await getEvalRun(runId);
      setResult(info);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const exportCsv = () => {
    if (!result || result.results.length === 0) return;
    const csv = toCsv(result.results);
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `eval-${result.run_id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full flex-col gap-4">
      <PageHeader
        title="评测中心"
        desc="固定评测集与确定性组件，结果可复现"
        actions={
          result && (
            <Button variant="outline" size="sm" onClick={exportCsv} disabled={result.results.length === 0}>
              <Icon name="download" className="h-3.5 w-3.5" />
              导出 CSV
            </Button>
          )
        }
      />

      <Card title="触发评测">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
            className="h-9 rounded-lg border border-gray-300 px-2 text-sm outline-none focus:border-blue-500"
          >
            {DATASETS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="h-9 rounded-lg border border-gray-300 px-2 text-sm outline-none focus:border-blue-500"
            title="top_k"
          >
            {[5, 10, 20].map((n) => (
              <option key={n} value={n}>
                top_k = {n}
              </option>
            ))}
          </select>
          <Button onClick={() => void trigger()} disabled={running}>
            {running ? "评测中…" : "触发评测"}
          </Button>
          {result && (
            <Button variant="outline" onClick={() => void loadResult(result.run_id)}>
              重新加载结果
            </Button>
          )}
        </div>
        {error && <div className="mt-2"><ErrorAlert message={error} /></div>}
      </Card>

      {running && <Spinner text="评测执行中…" />}

      {result && (
        <>
          {/* 汇总指标 */}
          <div className="grid grid-cols-3 gap-4">
            <StatCard label="run_id" value={result.run_id} sub={result.dataset} />
            <StatCard label="状态" value={result.status} accent={result.status === "completed" ? "text-green-600 dark:text-green-400" : "text-yellow-600 dark:text-yellow-400"} />
            {Object.entries(result.summary).map(([key, value]) => (
              <StatCard key={key} label={key} value={(value * 100).toFixed(2) + "%"} accent="text-blue-600" />
            ))}
          </div>

          {/* 逐条结果 */}
          <Card title={`逐条结果 (${result.results.length})`} className="min-h-0 flex-1">
            {result.results.length === 0 ? (
              <EmptyState text="无结果" />
            ) : (
              <div className="overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-xs text-gray-500">
                      <th className="pb-2 pr-2 font-medium">#</th>
                      <th className="pb-2 pr-2 font-medium">查询</th>
                      {Object.keys(result.results[0] ?? {}).filter((k) => k !== "query").map((k) => (
                        <th key={k} className="pb-2 pr-2 font-medium">{k}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.results.map((r, i) => (
                      <tr key={i} className="border-b border-gray-100 text-gray-600">
                        <td className="py-2 pr-2">{i + 1}</td>
                        <td className="max-w-96 truncate py-2 pr-2" title={String(r.query ?? "")}>
                          {String(r.query ?? "")}
                        </td>
                        {Object.entries(r).filter(([k]) => k !== "query").map(([k, v]) => (
                          <td key={k} className="py-2 pr-2">
                            {typeof v === "number" ? (v * 100).toFixed(2) + "%" : String(v)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
