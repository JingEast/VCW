# =============================================================================
# VCW Flask Application Dockerfile
# 多阶段构建 / Python 3.12 slim / 非 root 运行
# =============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder — 编译依赖并生成 wheels
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# 安装编译工具（仅构建阶段需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖清单并构建 wheels（缓存层优化）
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Production — 仅复制运行时所需文件
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS production

# 元数据
LABEL maintainer="VCW Team" \
      description="港籍升学热点文案批量生成器 - Web版" \
      version="1.0.0"

# 安装运行时系统依赖（无编译工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户和组
RUN groupadd -r vcw --gid=1000 && \
    useradd -r -g vcw --uid=1000 -s /sbin/nologin -d /app vcw

WORKDIR /app

# 从 builder 阶段复制 wheels 并安装
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# 复制应用代码
COPY --chown=vcw:vcw . .

# 创建数据目录并设置权限
RUN mkdir -p data/edited data/generated logs && \
    chown -R vcw:vcw data logs /app

# 健康检查
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# 切换到非 root 用户
USER vcw

# 暴露端口
EXPOSE 5000

# 默认入口
ENTRYPOINT ["python", "scripts/wait-for-services.py"]
CMD ["python", "wsgi.py"]
