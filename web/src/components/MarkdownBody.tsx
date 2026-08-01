/**
 * Markdown 渲染(react-markdown + GFM 表格), 内置基础排版样式.
 * 用于对话回答与报告章节正文.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownBody({ content }: { content: string }) {
  return (
    <div className="md-body text-sm leading-relaxed text-gray-800">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
