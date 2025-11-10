FROM python:3.11-slim

# 设置元数据
LABEL maintainer="your@email.com"
LABEL description="Router平台自动签到脚本 - 支持 AnyRouter、AgentRouter"

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd -m -u 1000 -s /bin/bash appuser

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器
RUN playwright install chromium && \
    playwright install-deps chromium

# 复制应用代码
COPY . .

# 创建缓存目录
RUN mkdir -p /app/.cache/sessions && \
    chown -R appuser:appuser /app

# 切换到非 root 用户
USER appuser

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 健康检查
HEALTHCHECK --interval=6h --timeout=30s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# 运行脚本
CMD ["python", "main.py"]
