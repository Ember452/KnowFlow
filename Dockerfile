# KnowFlow API 镜像 - multi-stage 构建
# builder: 安装依赖并导出纯净依赖树
# runtime: 精简镜像 + 非 root 用户 + healthcheck

# ── Stage 1: builder ──
FROM python:3.13-slim AS builder

ENV UV_VERSION=0.5 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# uv 安装(独立二进制, 不污染运行时)
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /uvx /bin/

WORKDIR /build

# 先复制依赖清单, 利用层缓存
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --no-editable

# ── Stage 2: runtime ──
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 非 root 用户
RUN groupadd -r knowflow && useradd -r -g knowflow -d /app knowflow

WORKDIR /app

# 从 builder 复制依赖(站点包)与项目源码
COPY --from=builder /build/.venv /app/.venv
COPY src /app/src
COPY worker /app/worker
COPY skills /app/skills
COPY .env.example /app/.env.example

ENV PATH="/app/.venv/bin:$PATH" \
    KNOWFLOW_SKILLS_DIR=/app/skills

USER knowflow

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "knowflow.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
