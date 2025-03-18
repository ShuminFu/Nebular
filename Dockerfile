FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    VIRTUAL_ENV=/app/.venv \
    PATH="$VIRTUAL_ENV/bin:$PATH"

# 安装 uv
RUN pip install --no-cache-dir uv

# 安装curl用于调试
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 复制 pyproject.toml 和 README.md 文件
COPY pyproject.toml README.md ./

# 先创建 src 目录结构以确保 hatchling 能够找到它
RUN mkdir -p src

# 安装依赖，使用官方 PyPI 源
RUN uv pip install --system .

# 复制项目代码
COPY . .

# 创建日志目录
RUN mkdir -p logs

# 设置容器启动命令
CMD ["python", "-m", "src.core.entrypoints.bots_main"] 