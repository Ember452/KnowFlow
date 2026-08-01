/**
 * 研究报告: 创建 → 六阶段流水线进度(全局轮询, 跨页面不丢失) → AI 工作日志 → 产物预览 → 飞书发布.
 * 任务状态存于 ReportContext(App 顶层), 切换页面轮询不中断.
 * 引用溯源: 章节正文 [n] 渲染为可点击角标, 点击定位右侧证据包对应条目.
 */

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Card, EmptyState, ErrorAlert, PageHeader, Spinner, StatusBadge } from "../components/common";
import { useReports, type ReportTaskState } from "../stores/ReportContext";
import { REPORT_STAGES, type EvidenceOut, type ReportOut } from "../types/api";

const EXAMPLE_QUERIES = [
  "基于知识库总结报销与差旅制度并给出优化建议",
  "调研 A/B/C 三款产品的定位差异并输出对比报告",
];

const STAGE_LABELS: Record<string, string> = {
  planning: "规划",
  research: "调研",
  synthesis: "综合",
  writing: "撰写",
  review: "核查",
  done: "完成",
  failed: "失败",
};

const STAGE_DOT_COLORS: Record<string, string> = {
  planning: "bg-blue-400",
  research: "bg-green-400",
  synthesis: "bg-purple-400",
  writing: "bg-amber-400",
  review: "bg-red-400",
  done: "bg-green-500",
  failed: "bg-red-500",
};

function PipelineSteps({ report }: { report: ReportOut }) {
  const stageIdx = REPORT_STAGES.indexOf(report.stage as (typeof REPORT_STAGES)[number]);
  return (
    <div>
      <div className="flex items-center gap-1">
        {REPORT_STAGES.map((stage, i) => {
          const done = stageIdx > i || report.status === "completed";
          const current = stageIdx === i && report.status === "running";
          const failed = report.status === "failed" && stage === "failed";
          return (
            <div key={stage} className="flex flex-1 flex-col items-center gap-1">
              <div
                className={`flex h-7 w-full items-center justify-center rounded-full border text-[10px] font-medium ${
                  failed
                    ? "border-red-300 bg-red-50 text-red-600 dark:text-red-300"
                    : current
                      ? "animate-pulse border-blue-400 bg-blue-600 text-white"
                      : done
                        ? "border-green-300 bg-green-50 text-green-700 dark:text-green-300"
                        : "border-gray-200 bg-gray-50 text-gray-400"
                }`}
              >
                {STAGE_LABELS[stage]}
              </div>
              {i < REPORT_STAGES.length - 1 && <div className="h-px w-full bg-gray-200" />}
            </div>
          );
        })}
      </div>
      <div className="mt-2 text-center text-xs text-gray-500">
        {report.status === "failed" ? (
          <span className="text-red-600 dark:text-red-400">{report.error ?? "报告生成失败"}</span>
        ) : report.status === "completed" ? (
          "报告已完成"
        ) : (
          report.detail || `当前阶段: ${STAGE_LABELS[report.stage] ?? report.stage}`
        )}
      </div>
    </div>
  );
}

/** AI 工作日志: 按时间序展示各阶段 AI 的思考与产出(来自后端 progress_log). */
function ProgressLog({ log }: { log: ReportOut["progress_log"] }) {
  if (log.length === 0) return <EmptyState text="暂无工作日志" />;
  return (
    <div className="relative space-y-2 pl-4">
      <div className="absolute bottom-1 left-[5px] top-1 w-px bg-gray-200" />
      {log.map((item, i) => (
        <div key={i} className="relative flex items-start gap-2">
          <span
            className={`absolute -left-4 top-1 h-2.5 w-2.5 rounded-full border-2 border-white dark:border-gray-800 ${
              STAGE_DOT_COLORS[item.stage] ?? "bg-gray-400"
            }`}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-xs">
              <span className="shrink-0 font-medium text-gray-500">
                {STAGE_LABELS[item.stage] ?? item.stage}
              </span>
              <span className="shrink-0 text-[10px] text-gray-300">
                {item.ts ? new Date(item.ts).toLocaleTimeString() : ""}
              </span>
            </div>
            <div className="mt-0.5 break-all text-xs leading-relaxed text-gray-600">{item.detail}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/** 章节正文渲染: [n] 引用标注 → 可点击角标(联动证据包). */
function ChapterBody({ body, onCite }: { body: string; onCite: (n: number) => void }) {
  return (
    <div className="md-body text-sm leading-relaxed text-gray-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          text: ({ children }) => {
            const text = String(children);
            const parts = text.split(/(\[\d+\])/g);
            if (parts.length === 1) return <>{text}</>;
            return (
              <>
                {parts.map((p, i) => {
                  const m = p.match(/\[(\d+)\]/);
                  if (m) {
                    const n = Number(m[1]);
                    return (
                      <button
                        key={i}
                        onClick={() => onCite(n - 1)}
                        className="mx-0.5 rounded bg-blue-100 px-1 text-[10px] font-bold text-blue-700 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-300 dark:hover:bg-blue-800"
                        title={`跳转证据 ${n}`}
                      >
                        [{n}]
                      </button>
                    );
                  }
                  return <span key={i}>{p}</span>;
                })}
              </>
            );
          },
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}

function EvidencePanel({
  evidence,
  activeIdx,
  onSelect,
}: {
  evidence: EvidenceOut[];
  activeIdx: number | null;
  onSelect: (i: number) => void;
}) {
  return (
    <div className="space-y-2">
      {evidence.length === 0 && <EmptyState text="暂无证据" />}
      {evidence.map((ev, i) => (
        <div
          key={i}
          onClick={() => onSelect(i)}
          className={`cursor-pointer rounded-lg border p-2.5 transition-colors ${
            activeIdx === i ? "border-blue-400 bg-blue-50 dark:border-blue-500 dark:bg-blue-500/10" : "border-gray-200 bg-gray-50 hover:border-blue-200 dark:hover:border-blue-500/50"
          }`}
        >
          <div className="mb-1 flex items-center gap-2 text-[10px]">
            <span className="font-bold text-blue-600 dark:text-blue-400">[{i + 1}]</span>
            <span className="text-gray-500">{ev.title || ev.source}</span>
            <span className="rounded bg-surface px-1 py-0.5 text-gray-400">{ev.source}</span>
          </div>
          <div className="line-clamp-3 text-xs text-gray-600">{ev.content}</div>
        </div>
      ))}
    </div>
  );
}

function TaskDetail({ task }: { task: ReportTaskState }) {
  const { publishTask } = useReports();
  const [evidenceHighlight, setEvidenceHighlight] = useState<number | null>(null);

  if (task.report.status === "completed" && task.result) {
    return (
      <Card
        title={task.result.title ?? "产物预览"}
        className="min-h-0 flex-1"
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={task.result.review_passed ? "completed" : "failed"} />
            {task.result.review_passed
              ? "事实核查通过"
              : `核查未通过(${task.result.issues.length} 项问题)`}
            <button
              onClick={() => void publishTask(task.report.run_id)}
              className="rounded-lg bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700"
            >
              发布到飞书
            </button>
          </div>
        }
      >
        <div className="flex h-full gap-4">
          <div className="min-w-0 flex-1 space-y-4 overflow-auto pr-1">
            {task.result.chapters.map((ch, i) => (
              <div key={i}>
                <h3 className="mb-2 text-sm font-bold text-gray-800">{ch.title}</h3>
                <ChapterBody body={ch.body} onCite={(n) => setEvidenceHighlight(n - 1)} />
              </div>
            ))}
            {task.result.references.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-bold text-gray-800">参考文献</h3>
                <ol className="list-inside list-decimal space-y-1 text-xs text-gray-600">
                  {task.result.references.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ol>
              </div>
            )}
            {!task.result.review_passed && task.result.issues.length > 0 && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-500/40">
                <div className="mb-1 text-xs font-semibold text-red-700 dark:text-red-300">审查问题清单</div>
                <ul className="list-inside list-disc space-y-0.5 text-xs text-red-600 dark:text-red-400">
                  {task.result.issues.map((issue, i) => (
                    <li key={i}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <div className="w-72 shrink-0 overflow-auto">
            <div className="mb-2 text-xs font-semibold text-gray-500">证据包 ({task.result.evidence.length})</div>
            <EvidencePanel
              evidence={task.result.evidence}
              activeIdx={evidenceHighlight}
              onSelect={(i) => setEvidenceHighlight(i)}
            />
          </div>
        </div>
      </Card>
    );
  }

  // 运行中/失败: 展示阶段进度 + AI 工作日志
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <Card title="流水线进度">
        <PipelineSteps report={task.report} />
      </Card>
      <Card title="AI 工作日志" className="min-h-0 flex-1">
        <div className="max-h-full overflow-auto">
          <ProgressLog log={task.report.progress_log} />
        </div>
      </Card>
      {task.publish && (
        <Card title="发布结果">
          {task.publish.published ? (
            <div className="flex items-center gap-2 text-sm text-green-700">
              <span>✓ 已发布到飞书云文档:</span>
              <a href={task.publish.doc_url} target="_blank" rel="noreferrer" className="text-blue-600 underline">
                {task.publish.doc_url}
              </a>
            </div>
          ) : (
            <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-700 dark:border-yellow-500/40 dark:text-yellow-300">
              {task.publish.message}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

export default function ReportsPage() {
  const { tasks, createTask } = useReports();
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState<number | null>(null);

  const submit = async (text?: string) => {
    const q = (text ?? query).trim();
    if (!q || creating) return;
    setCreating(true);
    setCreateError(null);
    try {
      const report = await createTask(q);
      setQuery("");
      setActiveIdx(0);
      // 新任务插到列表头部, 保持选中
      setActiveIdx(tasks.findIndex((t) => t.report.run_id === report.run_id));
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  };

  const activeTask = activeIdx !== null ? tasks[activeIdx] : null;

  return (
    <div className="flex h-full flex-col gap-4">
      <PageHeader title="研究报告" desc="创建报告任务，跟踪流水线进度与证据溯源" />
      <div className="flex min-h-0 flex-1 gap-4">
        {/* 左侧: 创建 + 任务列表(全局状态, 切页不丢) */}
        <div className="flex w-96 shrink-0 flex-col gap-4">
          <Card title="创建研究报告">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => submit(q)}
                disabled={creating}
                className="rounded-full border border-gray-200 bg-surface px-2.5 py-1 text-xs text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-600 disabled:opacity-50 dark:hover:border-blue-500 dark:hover:text-blue-400"
              >
                {q}
              </button>
            ))}
          </div>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入报告需求描述(不少于 3 字)…"
            rows={3}
            className="w-full resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
          />
          <button
            onClick={() => submit()}
            disabled={creating || query.trim().length < 3}
            className="mt-2 h-9 w-full rounded-lg bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {creating ? "创建中…" : "创建报告"}
          </button>
          {createError && <div className="mt-2"><ErrorAlert message={createError} /></div>}
        </Card>
        <Card title={`报告任务 (${tasks.length})`} className="min-h-0 flex-1">
          <div className="space-y-3 overflow-auto">
            {tasks.length === 0 && <EmptyState text="暂无任务" hint="创建后切换页面任务不丢失" />}
            {tasks.map((t, i) => (
              <div
                key={t.report.run_id}
                onClick={() => setActiveIdx(i)}
                className={`cursor-pointer rounded-lg border p-3 transition-colors ${
                  activeIdx === i ? "border-blue-400 bg-blue-50/50 dark:border-blue-500 dark:bg-blue-500/10" : "border-gray-200 hover:border-blue-200 dark:hover:border-blue-500/50"
                }`}
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="truncate text-xs font-medium text-gray-700">{t.report.query}</span>
                  <StatusBadge status={t.report.status} />
                </div>
                <PipelineSteps report={t.report} />
                {t.error && <div className="mt-1 text-[10px] text-red-500">{t.error}</div>}
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* 右侧: 详情 */}
      <div className="min-w-0 flex-1">
        {!activeTask ? (
          <Card className="h-full">
            <EmptyState text="选择左侧任务查看详情" />
          </Card>
        ) : (
          <TaskDetail task={activeTask} />
        )}
      </div>
      </div>
    </div>
  );
}
