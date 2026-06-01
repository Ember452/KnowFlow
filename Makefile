.PHONY: help install dev test test-unit test-integration lint format type check pre-commit up down ps logs clean demo

help: ## 显示所有可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖（uv sync）
	uv sync

dev: ## 启动开发服务器（热重载）
	uv run uvicorn knowflow.main:app --reload --host 0.0.0.0 --port 8000

worker: ## 启动 Worker 进程
	uv run python -m worker.main

test: ## 运行全部测试
	uv run pytest tests -q

test-unit: ## 运行单元测试
	uv run pytest tests/unit -q

test-integration: ## 运行集成测试（需要容器依赖）
	uv run pytest tests/integration -q

lint: ## Ruff lint 检查
	uv run ruff check src/ tests/ scripts/ worker/

format: ## Ruff 格式化
	uv run ruff format src/ tests/ scripts/ worker/

format-check: ## Ruff 格式化检查（不修改）
	uv run ruff format --check src/ tests/ scripts/ worker/

type: ## Mypy 类型检查
	uv run mypy src/ worker/

check: lint format-check type test-unit ## 全量门禁：lint + format + type + unit

pre-commit: ## 运行 pre-commit 全部 hook
	uv run pre-commit run --all-files

up: ## 启动本地依赖容器（postgres/milvus/redis/minio）
	docker compose up -d

down: ## 停止本地依赖容器
	docker compose down

ps: ## 查看容器状态
	docker compose ps

logs: ## 查看容器日志（跟踪）
	docker compose logs -f

init-db: ## 初始化数据库 + 执行迁移
	uv run python scripts/init_db.py

init-milvus: ## 创建 Milvus collection
	uv run python scripts/init_milvus.py

check-env: ## 检查依赖连通性
	uv run python scripts/check_env.py

clean: ## 清理构建产物与缓存
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

demo: ## 一键演示（P11 完善）
	@echo "demo 脚本将在 P11 阶段实现"
