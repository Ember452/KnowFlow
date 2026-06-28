# 如何开发一个新 Skill

> KnowFlow 的 Skill 是"零侵入"扩展点：新建一个目录 + 一个 SKILL.md 即可注册，无需改任何代码。
> 运行时启停通过 `PUT /api/v1/skills/{name}/toggle` 或 `SkillManager` 控制。

## 1. Skill 是什么

Skill = **YAML frontmatter（元信息） + Markdown 正文（执行指引）**，声明该技能激活时可见的工具集。

对话链路中，ToolOrchestrator 按意图识别激活对应 Skill，经 **VisibilityCalculator** 计算可见工具集（direct 恒可见 + skill_only 按激活 + subagent_only 按角色 + internal 永不可见），再把可见工具的 JSON Schema 注入 LLM prompt。

## 2. 目录结构

```
skills/
└── my_skill/              # 目录名 = Skill 名（需与 frontmatter.name 一致）
    └── SKILL.md
```

## 3. SKILL.md 格式

```markdown
---
name: my_skill                  # Skill 名（唯一，与目录名一致）
description: 一句话描述技能用途   # 意图识别用
domain: skill_only              # 执行域: direct / skill_only / subagent_only / internal
tools:
  - calculator                  # 该技能激活时可见的工具（必须已注册）
  - file_read_tool
dependencies:
  - data_analysis               # 可选：依赖的其他 Skill（拓扑解析，循环依赖会报错）
enabled: true                   # 默认启停状态
---

# 技能名

当用户需要 XXX 时激活此技能。

## 适用场景

- "帮我做 XXX"
- "对 YYY 进行 ZZZ"

## 工具链

1. `calculator`：安全数学表达式求值
2. `file_read_tool`：读取沙盒数据文件
```

### frontmatter 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 唯一标识，`^[a-z][a-z0-9_]*$`，与目录名一致 |
| `description` | 是 | 意图识别关键词来源，写清"何时激活" |
| `domain` | 是 | 执行域，四选一（见上） |
| `tools` | 是 | 工具名列表，引用 `tools/registry.py` 中已注册的工具 |
| `dependencies` | 否 | 依赖 Skill 名列表；缺失依赖加载失败，循环依赖抛错 |
| `enabled` | 否 | 默认 `true` |

## 4. 注册与校验

`SkillManager` 启动时扫描 `skills/` 目录（配置项 `KNOWFLOW_SKILLS_DIR`）：

```bash
# 校验全部 SKILL.md 格式与依赖（开发期验证）
uv run python -c "
from knowflow.tools.skill_manager import SkillManager
m = SkillManager()
print([(s.name, s.enabled) for s in m.list_skills()])
"
```

校验规则（`tools/skill_schema.py`）：name 合法、description 非空、tools 非空、domain 合法、dependencies 可解析。

## 5. 开发步骤（以 "report" 技能为例）

```bash
# 1. 创建目录与 SKILL.md
mkdir -p skills/report

# 2. 若需要新工具: 在 tools/builtin/ 实现并注册
#    - 继承 BaseTool, 实现 execute(), 输出 ToolResult
#    - 在 build_default_registry() 中 register

# 3. 重启 API(或热加载)后验证
curl http://localhost:8000/api/v1/skills          # 列表含 report
curl -X PUT http://localhost:8000/api/v1/skills/report/toggle  # 启停

# 4. 对话触发验证
curl -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "message": "帮我生成一份报告"}'
# 响应 tool_calls 中可见 report 技能激活的工具
```

## 6. 最佳实践

1. **description 写"场景"不写"能力"**：意图识别靠 description 关键词匹配，写"当用户要汇总/导出/计算时"比"提供计算能力"更有效
2. **工具最小化**：只声明该技能需要的工具——工具越少，注入的 Schema Token 越少（这是核心指标 -45.2% 的来源）
3. **依赖显式化**：跨技能复用工具时声明 dependencies，不要重复声明
4. **沙盒路径约定**：文件读写类工具使用 `/workspace/` 虚拟路径，禁止绝对路径
5. **subagent_only 场景**：如 code_review（子 Agent 角色专用），主 Agent 对话中不可见
