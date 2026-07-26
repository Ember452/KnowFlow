# KnowFlow 部署说明

> 两套部署方案：**docker-compose（本地/单机）** 与 **Kubernetes（集群）**。
> 所有配置通过环境变量管理（前缀 `KNOWFLOW_`），见 `.env.example`。

## 一、Docker Compose 本地部署

### 1.1 依赖容器

`docker-compose.yml` 编排 6 个服务：PostgreSQL 16 / Redis 7 / MinIO / etcd / Milvus 2.4 / Milvus 内部 MinIO。

```bash
# 启动全部依赖（后台）
docker compose up -d

# 查看状态（全部 healthy 后再继续）
docker compose ps

# 停止 / 清理数据
docker compose down
docker compose down -v   # 连同数据卷一起删除
```

### 1.2 配置与初始化

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env: 填写 KNOWFLOW_LLM_API_KEY 等

# 2. 初始化数据库（建库 + Alembic 迁移到最新版本）
make init-db

# 3. 初始化 Milvus collection
make init-milvus

# 4. 检查依赖连通性（可选）
make check-env
```

### 1.3 启动服务

```bash
make dev       # API（热重载）: http://localhost:8000
make worker    # 索引 Worker（消费 Redis Stream，另开终端）
```

验证：`curl http://localhost:8000/health` → `{"status": "ok"}`；`/docs` 打开交互式文档。

### 1.4 构建应用镜像（可选）

```bash
docker build -t knowflow:latest .
docker run --rm -p 8000:8000 --env-file .env knowflow:latest
```

> 镜像为 multi-stage 构建（builder 装依赖 → runtime 精简 + 非 root + healthcheck），
> 运行时需通过 `--env-file` 或环境变量注入 `KNOWFLOW_*` 配置。

## 二、Kubernetes 集群部署

### 2.1 清单文件（deploy/k8s/）

| 文件 | 说明 |
|---|---|
| `namespace.yaml` | 命名空间 `knowflow` |
| `configmap.yaml` | 非敏感配置（连接串/模型/队列参数） |
| `secrets.example.yaml` | 敏感配置模板（DB 密码/LLM Key/MinIO Key） |
| `api-deployment.yaml` | API Deployment（2 副本，资源配额 + 就绪/存活探针） |
| `api-service.yaml` | ClusterIP Service（80 → 8000） |
| `worker-deployment.yaml` | 索引 Worker Deployment（1 副本） |
| `hpa.yaml` | 水平扩缩容（CPU 70% / 内存 80%，2-6 副本） |

### 2.2 部署步骤

```bash
# 0. 前置：集群已有 PostgreSQL/Redis/Milvus/MinIO（或配置外部地址）
#    集群未部署这些中间件时，可先用 docker-compose 在 VM 上跑依赖，再在 ConfigMap 中指向其地址

# 1. 创建命名空间与配置
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml

# 2. 创建 Secret（替换真实值）
cp deploy/k8s/secrets.example.yaml deploy/k8s/secrets.yaml
# 编辑 secrets.yaml 填入真实值
kubectl apply -f deploy/k8s/secrets.yaml
# 注意: 不要将 secrets.yaml 提交到 git(.gitignore 已忽略? 默认请手动确认)

# 3. 部署 API / Worker / Service / HPA
kubectl apply -f deploy/k8s/api-deployment.yaml
kubectl apply -f deploy/k8s/api-service.yaml
kubectl apply -f deploy/k8s/worker-deployment.yaml
kubectl apply -f deploy/k8s/hpa.yaml

# 4. 验证
kubectl -n knowflow get pods          # 全部 Running/Ready
kubectl -n knowflow port-forward svc/knowflow-api 8000:80
curl http://localhost:8000/health
```

### 2.3 镜像说明

API 与 Worker 共用同一镜像（`Dockerfile`），Worker 以 `python -m worker.main` 启动。
镜像地址在 `api-deployment.yaml` / `worker-deployment.yaml` 中按实际 registry 替换；
CD 流水线（`.github/workflows/cd.yml`）在 main 合并后自动构建并推送 `ghcr.io`。

## 三、配置速查（KNOWFLOW_*）

| 组 | 关键项 |
|---|---|
| 应用 | `KNOWFLOW_ENV` / `KNOWFLOW_DEBUG` / `KNOWFLOW_LOG_LEVEL` / `KNOWFLOW_API_PREFIX` |
| PostgreSQL | `KNOWFLOW_POSTGRES_HOST/PORT/USER/PASSWORD/DB` |
| Redis | `KNOWFLOW_REDIS_URL` |
| Milvus | `KNOWFLOW_MILVUS_URI` |
| MinIO | `KNOWFLOW_MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY/BUCKET/SECURE` |
| LLM | `KNOWFLOW_LLM_API_KEY/BASE_URL/MODEL` + `KNOWFLOW_EMBEDDING_MODEL/RERANKER_MODEL` |
| 检索 | `KNOWFLOW_CHUNK_SIZE/OVERLAP/RETRIEVAL_TOP_K/RRF_K` |
| 上下文 | `KNOWFLOW_CONTEXT_BUDGET_TOKENS/SPILL_THRESHOLD_TOKENS/WINDOW_MAX_TURNS` |
| 队列 | `KNOWFLOW_TASK_STREAM_INDEX/DLQ/CONSUMER_*` |
| Agent | `KNOWFLOW_AGENT_TIMEOUT_SECONDS/MAX_SUBTASKS` |
| MCP | `KNOWFLOW_MCP_SERVERS`（JSON 数组，声明 stdio MCP Server，见 3.1） |

### 3.1 MCP 与 Skill 接入（自主扩展）

平台支持用户零代码接入外部工具与技能，均为**启动时注册**（改配置/加文件后重启生效）：

**MCP Server**：在 `.env` 配置 `KNOWFLOW_MCP_SERVERS`（JSON 数组），每项声明一个 stdio 协议 Server：

```json
KNOWFLOW_MCP_SERVERS=[{"id": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"], "domain": "skill_only"}]
```

- `id` 逻辑名（工具名前缀 `mcp_<id>_*`）；`command`/`args` 为 Server 启动命令；`domain` 决定执行域（`direct` 恒可见 / `skill_only` 需 Skill 激活 / `subagent_only` 仅子 Agent 可见）
- 启动时自动连接 Server → `list_tools` 拉取工具清单 → 适配器包装为本地工具注册进统一注册表，与内置工具同等接受执行域治理与调用追踪
- 单个 Server 连接失败仅告警降级，不阻塞启动；改配置后需重启生效

**Skill**：在 `skills/<名称>/SKILL.md` 以 YAML frontmatter 声明（`name/description/domain/tools/dependencies/enabled`），重启后自动加载；运行时可 `PUT /api/v1/skills/{name}/toggle` 启停。注意 Skill 只声明工具的组织方式，引用的工具必须已在注册表（内置工具或 MCP 接入的工具）。

## 四、常见问题

| 现象 | 处理 |
|---|---|
| Milvus 内存不足（要求 ≥8GB） | 降低 Milvus 配置或改用 PG 向量替代（见开发计划风险表） |
| Embedding 模型下载慢 | 首次手动预下载：`uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"` |
| `/readyz` 不通过 | `make check-env` 定位具体依赖；确认容器全部 healthy 后再初始化 |
| Worker 未消费任务 | 确认 `make worker` 已启动；Redis Stream 消费组 `knowflow-indexer` 已创建 |
