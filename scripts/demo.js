'use strict';
/* KnowFlow 轻量演示前端 · 零依赖原生 JS（配合 demo.html）
   覆盖：SSE 对话 / 检索引用 / 工具调用 / 知识库 / 工具治理 / 记忆 / 可观测 / 评测 / Agent / 会话历史 */

/* ─────────────────── 工具函数 ─────────────────── */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const USER_ID = 'demo'; // X-User-Id 头：记忆/会话按用户隔离
const state = { sessionId: null, chunks: [], tools: [], running: false, abort: null };

const fmtTime = (iso) => {
  if (!iso) return '-';
  const d = new Date(iso);
  return isNaN(d) ? String(iso) : d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
};
const fmtSize = (b) => {
  if (b == null) return '-';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(1) + ' MB';
};
const fmtNum = (n) => (n ?? 0).toLocaleString('zh-CN');
const pct = (n) => ((n ?? 0) * 100).toFixed(1) + '%';

function toast(msg, ms = 2400) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove('show'), ms);
}

/* ─────────────────── API 封装 ─────────────────── */
let BASE = localStorage.getItem('kf_demo_base') || 'http://localhost:8000/api/v1';
const setBase = (v) => { BASE = v.replace(/\/+$/, ''); localStorage.setItem('kf_demo_base', BASE); };

async function api(path, opts = {}) {
  const { method = 'GET', body, headers = {}, isForm = false } = opts;
  const init = { method, headers: { Accept: 'application/json', ...headers } };
  if (body !== undefined && !isForm) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  } else if (body !== undefined) {
    init.body = body; // FormData 由浏览器设置 boundary
  }
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || j.message || msg; } catch { /* 非 JSON */ }
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') || '';
  if (!ct.includes('application/json')) return res.text();
  const j = await res.json();
  // 统一信封 {code,message,data} 解包；其余端点直接返回数据体
  if (j && typeof j === 'object' && 'code' in j && 'message' in j && 'data' in j) return j.data;
  return j;
}

/* SSE 流式对话：fetch ReadableStream 手动解析 event:/data: 帧（心跳注释行自动跳过） */
async function* sseChat(body, signal) {
  const res = await fetch(BASE + '/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', 'X-User-Id': USER_ID },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error('SSE 连接失败: HTTP ' + res.status);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '', ev = 'message';
  let lines = [];
  function* flush() {
    if (!lines.length) return;
    const raw = lines.join('\n');
    lines = [];
    let data = raw;
    try { data = JSON.parse(raw); } catch { /* 非 JSON 保留原文 */ }
    yield { event: ev, data };
  }
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf('\n')) !== -1) {
      const line = buf.slice(0, idx).replace(/\r$/, '');
      buf = buf.slice(idx + 1);
      if (line === '') { yield* flush(); ev = 'message'; continue; }
      if (line.startsWith(':')) continue; // 心跳
      if (line.startsWith('event:')) ev = line.slice(6).trim();
      else if (line.startsWith('data:')) lines.push(line.slice(5).replace(/^ /, ''));
    }
  }
  yield* flush();
}

/* ─────────────────── 轻量 Markdown 渲染（先转义防注入，引用 [n] 转为可点击徽标） ─────────────────── */
function renderMarkdown(text) {
  let s = esc(text);
  const blocks = [];
  s = s.replace(/```[^\n]*\n([\s\S]*?)```/g, (m, code) => { blocks.push(code); return '\x00CB' + (blocks.length - 1) + '\x00'; });
  s = s.replace(/\[(\d{1,2})\]/g, '<span class="cite-chip" data-cite="$1">[$1]</span>');
  const inline = (x) => x
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>')
    .replace(/\*([^*\n]+)\*/g, '<i>$1</i>');
  const out = [];
  let para = [], list = false, tblHead = null, tblRows = [];
  const flushP = () => { if (para.length) { out.push('<p>' + para.map(inline).join('<br>') + '</p>'); para = []; } };
  const flushList = () => { if (list) { out.push('</ul>'); list = false; } };
  const flushTable = () => {
    if (!tblHead) return;
    out.push('<table><thead><tr>' + tblHead.map((h) => '<th>' + inline(h) + '</th>').join('') + '</tr></thead><tbody>' +
      tblRows.map((r) => '<tr>' + r.map((c) => '<td>' + inline(c) + '</td>').join('') + '</tr>').join('') + '</tbody></table>');
    tblHead = null; tblRows = [];
  };
  for (const ln of s.split('\n')) {
    const cell = ln.match(/^\s*\|(.+)\|\s*$/);
    if (cell) {
      const parts = cell[1].split('|').map((x) => x.trim());
      if (parts.every((p) => /^:?-{2,}:?$/.test(p))) continue; // 分隔行
      if (!tblHead) { flushP(); flushList(); tblHead = parts; } else tblRows.push(parts);
      continue;
    }
    if (tblHead) flushTable();
    const h = ln.match(/^(#{1,3})\s+(.+)/);
    if (h) { flushP(); flushList(); out.push('<h' + h[1].length + '>' + inline(h[2]) + '</h' + h[1].length + '>'); continue; }
    const li = ln.match(/^\s*[-*]\s+(.+)/);
    if (li) { if (!list) { flushP(); flushTable(); list = true; out.push('<ul>'); } out.push('<li>' + inline(li[1]) + '</li>'); continue; }
    if (list) { flushList(); }
    if (ln.trim() === '') { flushP(); flushTable(); continue; }
    para.push(ln);
  }
  flushP(); flushList(); flushTable();
  return out.join('').replace(/\x00CB(\d+)\x00/g, (m, i) => '<pre><code>' + blocks[i] + '</code></pre>');
}

/* ─────────────────── 主题（亮/暗） ─────────────────── */
function applyTheme(dark) {
  document.body.classList.toggle('dark', dark);
  $('#themeBtn').title = dark ? '切换到亮色' : '切换到暗色';
  localStorage.setItem('kf_demo_theme', dark ? 'dark' : 'light');
}

function initTheme() {
  const saved = localStorage.getItem('kf_demo_theme');
  // 未手动设置过时跟随系统偏好
  const dark = saved ? saved === 'dark' : !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  applyTheme(dark);
}

/* ─────────────────── 连接检测 / 依赖状态 ─────────────────── */
async function checkConn() {
  try {
    await api('/healthz');
    $('#connDot').className = 'dot ok';
    $('#connText').textContent = '已连接';
    loadReadyz();
  } catch {
    $('#connDot').className = 'dot err';
    $('#connText').textContent = '连接失败';
    $('#depsBar').innerHTML = '';
  }
}

async function loadReadyz() {
  try {
    const d = await api('/readyz');
    const deps = d?.deps || {};
    $('#depsBar').innerHTML = Object.entries(deps).map(([k, v]) =>
      `<span class="dep-badge ${v === 'ok' ? 'ok' : 'err'}" title="${esc(v)}">${k}: ${v === 'ok' ? '正常' : '降级'}</span>`).join('');
  } catch { /* 忽略 */ }
}

/* ─────────────────── 对话模块 ─────────────────── */
const PRESETS = [
  '张三负责什么工作？',
  '员工报销流程是什么？',
  '年假怎么规定的？',
  '帮我算一下：差旅费 2680 元加交通费 450 元，报销总额多少？',
  'VPN 申请流程是什么？',
];

function addUserMsg(text, time) {
  $('#chatMessages .empty')?.remove();
  const m = document.createElement('div');
  m.className = 'msg user';
  m.innerHTML = `<div><div class="bubble">${esc(text)}</div><div class="meta">${fmtTime(time || new Date().toISOString())}</div></div>`;
  $('#chatMessages').appendChild(m);
  scrollChat();
}

function addAssistantMsg() {
  const m = document.createElement('div');
  m.className = 'msg assistant';
  m.innerHTML = '<div><div class="bubble">思考中…</div><div class="meta"></div></div>';
  $('#chatMessages').appendChild(m);
  scrollChat();
  return m.querySelector('.bubble');
}

const scrollChat = () => { $('#chatMessages').scrollTop = $('#chatMessages').scrollHeight; };

/* 新建会话：重置 session_id 并清空对话界面（仅影响前端状态，后端按需新建） */
function newSession() {
  state.abort?.abort(); // 如有生成中的流先停止
  state.sessionId = null;
  state.chunks = [];
  state.tools = [];
  $('#chatMessages').innerHTML = '<div class="empty">新会话已创建，输入问题开始对话…</div>';
  $('#citePanel').innerHTML = '<div class="empty">发送问题后展示检索命中的知识片段</div>';
  $('#toolPanel').innerHTML = '<div class="empty">工具编排执行记录</div>';
  $('#citeCount').textContent = '';
  $('#toolCount').textContent = '';
  $('#chatStats').innerHTML = '<span class="muted">暂无数据</span>';
  const b = $('#chatSessionBadge');
  b.textContent = '新会话';
  b.className = 'badge';
}

function renderCites(chunks, latency, query) {
  $('#citeCount').textContent = chunks.length ? `${chunks.length} 条 · ${(latency ?? 0).toFixed(0)}ms` : '';
  if (!chunks.length) { $('#citePanel').innerHTML = '<div class="empty">无检索命中</div>'; return; }
  $('#citePanel').innerHTML = chunks.map((c, i) =>
    `<div class="cite-item" data-chunk="${c.chunk_id}">
       <b>[${i + 1}]</b> ${esc((c.content || '').slice(0, 200))}${(c.content || '').length > 200 ? '…' : ''}
       <div class="src"><span class="badge primary">${esc(c.source || 'hybrid')}</span>
       <span>score ${(c.score ?? 0).toFixed(3)}</span><span>chunk #${c.chunk_id}</span><span class="muted">${esc(c.source || '')}</span></div>
     </div>`).join('');
}

function renderTools() {
  $('#toolCount').textContent = state.tools.length ? `${state.tools.length} 次调用` : '';
  if (!state.tools.length) { $('#toolPanel').innerHTML = '<div class="empty">暂无工具调用</div>'; return; }
  $('#toolPanel').innerHTML = state.tools.map((t) => {
    const icon = t.status === 'running' ? '<span class="spinner"></span>' : t.status === 'ok' ? '<span style="color:var(--ok)">✓</span>' : '<span style="color:var(--err)">✗</span>';
    const meta = t.status === 'running' ? '执行中' : t.status === 'ok' ? `${t.latency ?? 0}ms` : esc(t.error || '失败');
    return `<div class="tool-item">${icon}<span class="tname">${esc(t.tool)}</span><span class="muted">${esc(JSON.stringify(t.args ?? {}))}</span><span class="muted" style="margin-left:auto">${meta}</span></div>`;
  }).join('');
}

function renderFinal(bubble, d) {
  bubble.innerHTML = renderMarkdown(bubble.textContent);
  bubble.classList.remove('streaming');
  const meta = bubble.closest('.msg').querySelector('.meta');
  meta.textContent = `session #${d.session_id ?? '-'} · ${(d.latency_ms ?? 0).toFixed(0)}ms · ${d.tokens ?? 0} tokens · 引用 ${(d.citations || []).length} 条`;
  $('#chatStats').innerHTML = [
    ['会话', d.session_id ?? '-'],
    ['延迟', (d.latency_ms ?? 0).toFixed(0) + 'ms'],
    ['Token', fmtNum(d.tokens)],
    ['引用', (d.citations || []).length + ' 条'],
    ['工具调用', (d.tool_calls || []).length + ' 次'],
  ].map(([k, v]) => `<span class="kv"><b>${k}</b> ${esc(v)}</span>`).join('');
}

async function doChat(text) {
  if (!text.trim() || state.running) return;
  state.running = true;
  $('#chatSend').disabled = true;
  $('#chatStop').style.display = '';
  $('#chatInput').value = '';
  addUserMsg(text);
  const bubble = addAssistantMsg();
  state.chunks = []; state.tools = [];
  $('#citePanel').innerHTML = '<div class="empty">检索中…</div>';
  $('#toolPanel').innerHTML = '<div class="empty">等待编排…</div>';
  $('#citeCount').textContent = ''; $('#toolCount').textContent = '';
  $('#chatStats').innerHTML = '<span class="muted">生成中…</span>';
  const ctrl = new AbortController();
  state.abort = ctrl;
  try {
    for await (const ev of sseChat({ message: text, session_id: state.sessionId, user_id: USER_ID, stream: true }, ctrl.signal)) {
      switch (ev.event) {
        case 'retrieval':
          state.chunks = ev.data?.chunks || [];
          renderCites(state.chunks, ev.data?.latency_ms, ev.data?.query);
          break;
        case 'tool_start':
          state.tools.push({ call_id: ev.data?.call_id, tool: ev.data?.tool, args: ev.data?.args, status: 'running' });
          renderTools();
          break;
        case 'tool_end': {
          const t = state.tools.find((x) => x.call_id === ev.data?.call_id);
          if (t) { t.status = ev.data.success ? 'ok' : 'err'; t.latency = ev.data.latency_ms; t.error = ev.data.error; }
          renderTools();
          break;
        }
        case 'token':
          if (ev.data?.delta) {
            const cur = bubble.textContent;
            bubble.textContent = cur === '思考中…' ? ev.data.delta : cur + ev.data.delta;
          }
          break;
        case 'progress':
          toast('Multi-Agent 编排：委派 ' + (ev.data?.delegated ?? 0) + ' 个子任务并发执行');
          break;
        case 'done':
          if (ev.data?.session_id) {
            state.sessionId = ev.data.session_id;
            const b = $('#chatSessionBadge');
            b.textContent = '会话 #' + state.sessionId;
            b.className = 'badge primary';
          }
          renderFinal(bubble, ev.data || {});
          break;
        case 'error':
          throw new Error(ev.data?.error || '未知错误');
      }
      scrollChat();
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      bubble.textContent = (bubble.textContent || '') + '\n\n（已停止生成）';
    } else {
      bubble.textContent = '出错：' + e.message;
    }
    bubble.classList.remove('streaming');
  } finally {
    state.running = false;
    $('#chatSend').disabled = false;
    $('#chatStop').style.display = 'none';
  }
}

/* ─────────────────── 知识库模块 ─────────────────── */
const DOC_STATUS = { pending: '等待索引', indexing: '索引中', ready: '已就绪', failed: '失败' };

async function loadDocs() {
  try {
    const d = await api('/documents?limit=100', { headers: { 'X-User-Id': USER_ID } });
    const items = d?.items || [];
    $('#docTotal').textContent = `共 ${items.length} 篇`;
    if (!items.length) { $('#docList').innerHTML = '<div class="empty">暂无文档，点击上方"上传文档"开始</div>'; return; }
    $('#docList').innerHTML = items.map((doc) => `
      <div class="doc-item">
        <div class="info">
          <div class="title">${esc(doc.title)}</div>
          <div class="muted">${esc(doc.file_type || '')} · ${fmtSize(doc.size_bytes)} · ${fmtTime(doc.created_at)}</div>
        </div>
        <span class="badge ${doc.status === 'ready' ? 'ok' : doc.status === 'failed' ? 'err' : 'warn'}">${DOC_STATUS[doc.status] || esc(doc.status)}</span>
        <button class="btn ghost" data-act="reindex" data-id="${doc.id}" style="padding:2px 10px;font-size:12px">重建</button>
        <button class="btn ghost" data-act="del" data-id="${doc.id}" style="padding:2px 10px;font-size:12px">删除</button>
      </div>`).join('');
  } catch (e) {
    $('#docList').innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`;
  }
}

async function uploadDocs(files) {
  if (!files.length) return;
  const fd = new FormData();
  [...files].forEach((f) => fd.append('file', f));
  try {
    const r = await api('/documents/upload', { method: 'POST', body: fd, isForm: true, headers: { 'X-User-Id': USER_ID } });
    toast(r?.duplicated ? `已秒传去重：${r.title}` : `已接收 ${r.title}（${DOC_STATUS[r.status] || r.status}），Worker 将异步索引`);
    loadDocs();
  } catch (e) {
    toast('上传失败：' + e.message, 4000);
  }
}

async function docAction(act, id) {
  try {
    if (act === 'del') {
      await api(`/documents/${id}`, { method: 'DELETE' });
      toast(`已删除文档 #${id}`);
    } else {
      const r = await api(`/documents/${id}/reindex`, { method: 'POST' });
      toast(`已投递重建索引任务：${r.message}`);
    }
    loadDocs();
  } catch (e) { toast('操作失败：' + e.message, 4000); }
}

async function doSearch() {
  const q = $('#searchBox').value.trim();
  if (!q) return;
  const topK = +$('#searchTopK').value;
  $('#searchResult').innerHTML = '<div class="empty"><span class="spinner"></span> 检索中…</div>';
  try {
    const d = await api('/knowledge/search', { method: 'POST', body: { query: q, top_k: topK, with_rerank: true } });
    if (!d?.chunks?.length) { $('#searchResult').innerHTML = '<div class="empty">无检索命中</div>'; return; }
    $('#searchResult').innerHTML = `
      <div class="muted" style="margin-bottom:8px">命中 ${d.total} 条 · 延迟 ${(d.latency_ms ?? 0).toFixed(0)}ms ${d.cache_hit ? '· 缓存命中' : ''}</div>` +
      d.chunks.map((c, i) => `
        <div class="cite-item">
          <b>[${i + 1}]</b> ${esc(c.content)}
          <div class="src"><span class="badge primary">${esc(c.source || 'hybrid')}</span>
          <span>score ${(c.score ?? 0).toFixed(3)}</span><span>chunk #${c.chunk_id}</span></div>
        </div>`).join('');
  } catch (e) {
    $('#searchResult').innerHTML = `<div class="empty">检索失败：${esc(e.message)}</div>`;
  }
}

/* ─────────────────── 工具治理模块 ─────────────────── */
const DOMAIN_LABEL = { direct: 'direct 恒可见', skill_only: 'skill_only 按激活', subagent_only: 'subagent_only 按角色', internal: 'internal 不可见' };
const DOMAIN_COLOR = { direct: '#3d9a5f', skill_only: '#3d7ea6', subagent_only: '#c98a2d', internal: '#c0392b' };

async function loadTools() {
  try {
    const s = await api('/tools/stats');
    const cut = s.total_tools ? (1 - s.visible_tools / s.total_tools) * 100 : 0;
    const cards = [
      ['工具总量', fmtNum(s.total_tools)],
      ['主 Agent 可见', `${fmtNum(s.visible_tools)}（裁剪 ${cut.toFixed(1)}%）`],
      ['注入 Schema Token', fmtNum(s.schema_tokens)],
      ['FC 准确率', s.accuracy ? pct(s.accuracy) : '-'],
    ];
    $('#toolStats').innerHTML = cards.map(([l, v]) => `<div class="stat"><div class="num">${v}</div><div class="label">${l}</div></div>`).join('');
    const bd = s.domain_breakdown || {};
    const total = Object.values(bd).reduce((a, b) => a + b, 0) || 1;
    $('#domainBreakdown').innerHTML = `
      <div class="domain-bar">${Object.entries(bd).map(([k, v]) => `<span style="width:${(v / total * 100).toFixed(1)}%;background:${DOMAIN_COLOR[k] || '#8a857d'}" title="${DOMAIN_LABEL[k] || k}: ${v}"></span>`).join('')}</div>
      <div class="legend">${Object.entries(bd).map(([k, v]) => `<span><i style="background:${DOMAIN_COLOR[k] || '#8a857d'}"></i>${DOMAIN_LABEL[k] || esc(k)}（${v}）</span>`).join('')}</div>`;
    const metrics = s.metrics || [];
    $('#toolMetricHint').textContent = metrics.length ? 'orchestrator 运行时采集' : '尚无运行时调用数据，先在对话页触发工具调用';
    $('#toolMetricTable').innerHTML = metrics.length ? `
      <table><thead><tr><th>工具</th><th>执行域</th><th>调用次数</th><th>成功率</th><th>平均延迟</th><th>Token</th></tr></thead><tbody>
      ${metrics.map((m) => `<tr><td>${esc(m.tool)}</td><td>${esc(m.domain)}</td><td>${fmtNum(m.calls)}</td>
        <td>${pct(m.success_rate)}</td><td>${(m.avg_latency_ms ?? 0).toFixed(0)}ms</td><td>${fmtNum(m.token_count)}</td></tr>`).join('')}
      </tbody></table>` : '<div class="empty">暂无调用指标</div>';
    loadSkills();
  } catch (e) {
    $('#toolStats').innerHTML = `<div class="empty">工具治理不可用：${esc(e.message)}</div>`;
  }
}

async function loadSkills() {
  try {
    const skills = await api('/skills');
    if (!skills?.length) { $('#skillList').innerHTML = '<div class="empty">无 Skill</div>'; return; }
    $('#skillList').innerHTML = skills.map((s) => `
      <div class="mem-item">
        <div style="display:flex;align-items:center;gap:8px">
          <b>${esc(s.name)}</b>
          <span class="badge ${s.enabled ? 'ok' : ''}">${s.enabled ? '已启用' : '已停用'}</span>
          <span class="muted" style="margin-left:auto">${esc(s.domain || 'skill_only')}</span>
          <button class="btn ghost" data-skill="${esc(s.name)}" data-on="${s.enabled ? 1 : 0}" style="padding:2px 10px;font-size:12px">${s.enabled ? '停用' : '启用'}</button>
        </div>
        <div class="muted">${esc(s.description || '')}</div>
        <div class="foot">工具：${esc((s.tools || []).join(', ') || '-')}${s.dependencies?.length ? ` · 依赖：${esc(s.dependencies.join(', '))}` : ''}</div>
      </div>`).join('');
  } catch (e) {
    $('#skillList').innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`;
  }
}

async function toggleSkill(name) {
  try {
    const r = await api(`/skills/${encodeURIComponent(name)}/toggle`, { method: 'PUT' });
    toast(`Skill ${r.name} 已${r.enabled ? '启用' : '停用'}`);
    loadTools();
  } catch (e) { toast('操作失败：' + e.message, 4000); }
}

/* ─────────────────── 记忆模块 ─────────────────── */
async function loadMemory() {
  const user = $('#memoryUser').value.trim() || USER_ID;
  $('#memoryList').innerHTML = '<div class="empty"><span class="spinner"></span> 加载中…</div>';
  try {
    const items = await api(`/memory/${encodeURIComponent(user)}`);
    if (!items?.length) { $('#memoryList').innerHTML = '<div class="empty">暂无长期记忆。多轮对话后自动沉淀，或输入会话号手动沉淀</div>'; return; }
    $('#memoryList').innerHTML = items.map((m) => `
      <div class="mem-item">
        <div>${esc(m.content)}</div>
        <div class="muted">${m.summary ? '摘要：' + esc(m.summary) : ''}</div>
        <div class="foot">
          <span class="badge ${m.importance >= 7 ? 'primary' : ''}">importance ${(m.importance ?? 0).toFixed(1)}</span>
          <span>session #${m.session_id}</span><span>${fmtTime(m.created_at)}</span>
          ${m.last_recall ? `<span>最近召回 ${fmtTime(m.last_recall)}</span>` : ''}
          <span style="margin-left:auto"><button class="btn ghost" data-mem-del="${m.id}" style="padding:1px 10px;font-size:11px">删除</button></span>
        </div>
      </div>`).join('');
  } catch (e) {
    $('#memoryList').innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`;
  }
}

async function sedimentMemory() {
  const user = $('#memoryUser').value.trim() || USER_ID;
  const sid = $('#sedimentSession').value.trim();
  if (!sid) { toast('请先输入会话号'); return; }
  try {
    const r = await api(`/memory/${encodeURIComponent(user)}/sediment`, { method: 'POST', body: { session_id: +sid } });
    toast(`沉淀完成：新增 ${r.saved ?? 0} 条长期记忆`);
    loadMemory();
  } catch (e) { toast('沉淀失败：' + e.message, 4000); }
}

async function deleteMemory(id) {
  const user = $('#memoryUser').value.trim() || USER_ID;
  try {
    await api(`/memory/${encodeURIComponent(user)}/${id}`, { method: 'DELETE' });
    toast(`已删除记忆 #${id}`);
    loadMemory();
  } catch (e) { toast('删除失败：' + e.message, 4000); }
}

/* ─────────────────── 可观测模块 ─────────────────── */
async function loadObsStats() {
  try {
    const s = await api('/traces/stats?hours=24');
    if (!s) return;
    const cards = [
      ['24h 对话', fmtNum(s.dialogs)],
      ['24h Trace', fmtNum(s.traces)],
      ['工具调用', `${fmtNum(s.tool_calls)}（成功率 ${pct(s.tool_success_rate)}）`],
      ['平均延迟', s.avg_latency_ms?.total ? (s.avg_latency_ms.total).toFixed(0) + 'ms' : '-'],
    ];
    $('#obsStats').innerHTML = cards.map(([l, v]) => `<div class="stat"><div class="num">${v}</div><div class="label">${l}</div></div>`).join('');
  } catch { /* 忽略 */ }
}

async function loadTrace() {
  const sid = $('#traceSession').value.trim();
  if (!sid) return;
  $('#traceTree').innerHTML = '<div class="empty"><span class="spinner"></span> 查询中…</div>';
  try {
    const t = await api(`/traces/${sid}`);
    if (!t?.roots?.length) { $('#traceTree').innerHTML = '<div class="empty">无 Trace 记录</div>'; return; }
    $('#traceTree').innerHTML = t.roots.map((r) => renderSpan(r, 0)).join('');
  } catch (e) {
    $('#traceTree').innerHTML = `<div class="empty">查询失败：${esc(e.message)}</div>`;
  }
}

function renderSpan(sp, depth) {
  const meta = [`${sp.span_type || 'span'}`, sp.latency_ms != null ? `${sp.latency_ms}ms` : '', `#${sp.id}`].filter(Boolean).join(' · ');
  const kids = (sp.children || []).map((c) => renderSpan(c, depth + 1)).join('');
  return `<div class="tree-item">
    <span class="tag" style="color:var(--primary)">${esc(sp.name)}</span>
    <span class="muted">${esc(meta)}</span>
    ${sp.input ? `<div class="muted">in: ${esc(JSON.stringify(sp.input).slice(0, 120))}</div>` : ''}
    ${kids ? `<div class="tree-node">${kids}</div>` : ''}
  </div>`;
}

/* ─────────────────── 评测模块 ─────────────────── */
async function runEval() {
  const ds = $('#evalDataset').value;
  $('#evalHint').textContent = '运行中…';
  $('#evalResult').innerHTML = '<div class="empty"><span class="spinner"></span> 静态评测执行中（无需外部模型）…</div>';
  try {
    const r = await api('/eval/run', { method: 'POST', body: { dataset: ds, mode: 'static', top_k: 10 } });
    $('#evalHint').textContent = `run #${r.run_id} · ${r.status}`;
    const rows = Object.entries(r.summary || {});
    $('#evalResult').innerHTML = `
      <div class="row">${rows.map(([k, v]) => `<div class="stat"><div class="num">${(typeof v === 'number' ? v * 100 : Number(v) * 100).toFixed(1)}%</div><div class="label">${esc(k)}</div></div>`).join('')}</div>
      <table><thead><tr><th>#</th><th>查询</th><th>指标</th></tr></thead><tbody>
      ${(r.results || []).map((d, i) => `<tr><td>${i + 1}</td><td>${esc(d.query || '-')}</td><td class="muted">${esc(JSON.stringify(Object.fromEntries(Object.entries(d).filter(([k]) => k !== 'query'))))}</td></tr>`).join('')}
      </tbody></table>`;
  } catch (e) {
    $('#evalHint').textContent = '';
    $('#evalResult').innerHTML = `<div class="empty">评测失败：${esc(e.message)}</div>`;
  }
}

/* ─────────────────── Agent 编排模块 ─────────────────── */
async function loadAgentRun() {
  const rid = $('#agentRunInput').value.trim();
  if (!rid) return;
  $('#agentTree').innerHTML = '<div class="empty"><span class="spinner"></span> 查询中…</div>';
  try {
    const d = await api(`/agents/runs/${rid}`);
    const r = d.run;
    $('#agentTree').innerHTML = `
      <div class="tree-item"><span class="badge ${r.agent_type === 'main' ? 'primary' : ''}">${esc(r.agent_type)}</span>
        <span class="tag">run #${r.id}</span> · session #${r.session_id} ·
        <span class="badge ${r.status === 'completed' ? 'ok' : r.status === 'failed' ? 'err' : 'warn'}">${esc(r.status)}</span>
        <span class="muted">${fmtTime(r.started_at)} → ${fmtTime(r.completed_at)}</span></div>
      ${(d.delegations || []).map((dg) => `
        <div class="tree-node"><div class="tree-item">
          委派 <span class="tag">#${dg.id}</span> → <b>${esc(dg.task)}</b>
          <span class="badge ${dg.status === 'completed' ? 'ok' : 'warn'}">${esc(dg.status)}</span>
          ${dg.child_run_id ? `<span class="muted">子 run #${dg.child_run_id}</span>` : ''}
          ${dg.checkpoint_id ? `<span class="muted">checkpoint ${esc(dg.checkpoint_id.slice(0, 8))}…</span>` : ''}
        </div>
        ${dg.child_run_id ? (d.children || []).filter((c) => c.id === dg.child_run_id).map((c) =>
          `<div class="tree-node"><div class="tree-item"><span class="badge">sub</span> run #${c.id} · <span class="badge ${c.status === 'completed' ? 'ok' : 'warn'}">${esc(c.status)}</span> · <span class="muted">${fmtTime(c.started_at)}</span></div></div>`).join('') : ''}
        </div>`).join('') || '<div class="muted">（无委派记录）</div>'}`;
  } catch (e) {
    $('#agentTree').innerHTML = `<div class="empty">查询失败：${esc(e.message)}</div>`;
  }
}

/* ─────────────────── 会话历史模块 ─────────────────── */
async function loadSessions() {
  try {
    const d = await api('/chat/sessions?limit=50', { headers: { 'X-User-Id': USER_ID } });
    const items = d?.items || [];
    if (!items.length) { $('#sessionList').innerHTML = '<div class="empty">暂无会话，先在对话页提问</div>'; return; }
    $('#sessionList').innerHTML = items.map((s) => `
      <div class="doc-item" style="cursor:pointer" data-session="${s.id}">
        <div class="info">
          <div class="title">#${s.id} ${esc(s.title || '（无标题会话）')}</div>
          <div class="muted">${fmtTime(s.created_at)} · 更新 ${fmtTime(s.updated_at)}</div>
        </div>
        <span class="badge ${s.status === 'active' ? 'ok' : ''}">${esc(s.status)}</span>
        <button class="btn ghost" data-continue="${s.id}" style="padding:2px 10px;font-size:12px">继续对话</button>
      </div>`).join('');
  } catch (e) {
    $('#sessionList').innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`;
  }
}

async function loadSessionMessages(sid) {
  $('#sessionMessages').innerHTML = '<div class="empty"><span class="spinner"></span> 加载中…</div>';
  try {
    const msgs = await api(`/chat/sessions/${sid}/messages`);
    if (!msgs?.length) { $('#sessionMessages').innerHTML = '<div class="empty">无消息</div>'; return; }
    $('#sessionMessages').innerHTML = msgs.map((m) => `
      <div class="msg ${m.role}"><div class="bubble">${m.role === 'assistant' ? renderMarkdown(m.content) : esc(m.content)}</div>
      <div class="meta">${esc(m.role)} · ${fmtTime(m.created_at)} · ${m.tokens ?? 0} tokens</div></div>`).join('');
  } catch (e) {
    $('#sessionMessages').innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`;
  }
}

/* 在对话页继续历史会话：切到对话 Tab 并载入该会话消息，后续提问自动延续 */
async function continueSession(sid) {
  state.abort?.abort();
  try {
    const msgs = await api(`/chat/sessions/${sid}/messages`);
    state.sessionId = String(sid);
    state.chunks = [];
    state.tools = [];
    switchTab('chat');
    $('#chatMessages').innerHTML = '';
    for (const m of msgs || []) {
      if (m.role === 'user') {
        addUserMsg(m.content, m.created_at);
      } else {
        const b = addAssistantMsg();
        b.innerHTML = renderMarkdown(m.content || '');
        b.closest('.msg').querySelector('.meta').textContent =
          `${esc(m.role)} · ${fmtTime(m.created_at)} · ${m.tokens ?? 0} tokens`;
      }
    }
    if (!msgs?.length) $('#chatMessages').innerHTML = '<div class="empty">该会话暂无消息，可直接提问</div>';
    const b = $('#chatSessionBadge');
    b.textContent = '会话 #' + sid;
    b.className = 'badge primary';
    $('#citePanel').innerHTML = '<div class="empty">发送问题后展示检索命中的知识片段</div>';
    $('#toolPanel').innerHTML = '<div class="empty">工具编排执行记录</div>';
    $('#citeCount').textContent = '';
    $('#toolCount').textContent = '';
    $('#chatStats').innerHTML = '<span class="muted">已载入历史会话 #' + sid + '，继续提问将延续该会话</span>';
    scrollChat();
  } catch (e) {
    toast('载入会话失败：' + e.message, 4000);
  }
}

/* ─────────────────── 事件绑定与初始化 ─────────────────── */
function switchTab(name) {
  $$('#tabNav button').forEach((x) => x.classList.toggle('active', x.dataset.tab === name));
  $$('.tab').forEach((x) => x.classList.toggle('active', x.id === 'tab-' + name));
}

function bindEvents() {
  // Tab 切换
  $$('#tabNav button').forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.tab)));

  // 连接
  $('#connBtn').addEventListener('click', () => { setBase($('#apiBase').value); checkConn(); });
  $('#apiBase').addEventListener('keydown', (e) => { if (e.key === 'Enter') { setBase($('#apiBase').value); checkConn(); } });
  $('#themeBtn').addEventListener('click', () => applyTheme(!document.body.classList.contains('dark')));

  // 对话
  $('#chatSend').addEventListener('click', () => doChat($('#chatInput').value));
  $('#newChatBtn').addEventListener('click', newSession);
  $('#chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doChat($('#chatInput').value); }
  });
  $('#chatStop').addEventListener('click', () => { state.abort?.abort(); });
  $('#presetQs').innerHTML = PRESETS.map((p) => `<button data-q="${esc(p)}">${esc(p)}</button>`).join('');
  $('#presetQs').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-q]');
    if (btn) doChat(btn.dataset.q);
  });
  // 引用徽标点击 → 高亮右侧对应片段
  $('#chatMessages').addEventListener('click', (e) => {
    const chip = e.target.closest('.cite-chip');
    if (!chip) return;
    const i = +chip.dataset.cite - 1;
    const item = $$('#citePanel .cite-item')[i];
    if (item) {
      item.scrollIntoView({ behavior: 'smooth', block: 'center' });
      item.classList.add('hl');
      setTimeout(() => item.classList.remove('hl'), 1500);
    }
  });

  // 知识库
  $('#uploadBtn').addEventListener('click', () => $('#uploadInput').click());
  $('#uploadInput').addEventListener('change', (e) => { uploadDocs(e.target.files); e.target.value = ''; });
  $('#refreshDocs').addEventListener('click', loadDocs);
  $('#searchBtn').addEventListener('click', doSearch);
  $('#searchBox').addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });
  $('#docList').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-act]');
    if (btn) docAction(btn.dataset.act, +btn.dataset.id);
  });

  // 工具治理
  $('#skillList').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-skill]');
    if (btn) toggleSkill(btn.dataset.skill);
  });

  // 记忆
  $('#refreshMemory').addEventListener('click', loadMemory);
  $('#sedimentBtn').addEventListener('click', sedimentMemory);
  $('#memoryList').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-mem-del]');
    if (btn) deleteMemory(+btn.dataset.memDel);
  });

  // 可观测
  $('#traceBtn').addEventListener('click', loadTrace);
  $('#traceSession').addEventListener('keydown', (e) => { if (e.key === 'Enter') loadTrace(); });

  // 评测
  $('#evalBtn').addEventListener('click', runEval);

  // Agent
  $('#agentBtn').addEventListener('click', loadAgentRun);
  $('#agentRunInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') loadAgentRun(); });

  // 会话历史
  $('#sessionList').addEventListener('click', (e) => {
    const cont = e.target.closest('[data-continue]');
    if (cont) { continueSession(+cont.dataset.continue); return; }
    const item = e.target.closest('[data-session]');
    if (item) loadSessionMessages(+item.dataset.session);
  });
}

function init() {
  $('#apiBase').value = BASE;
  initTheme();
  bindEvents();
  checkConn();
  loadDocs();
  loadTools();
  loadMemory();
  loadObsStats();
  loadSessions();
  setInterval(() => { if (document.visibilityState === 'visible') checkConn(); }, 30000); // 每 30s 自动刷新连接状态
}

document.addEventListener('DOMContentLoaded', init);
