# Docker 部署指南

## 快速开始

### 1. 使用 Docker Compose（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd Regular-inspection

# 复制配置文件
cp .env.example .env

# 编辑配置文件
vim .env  # 或使用其他编辑器

# 构建并启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止容器
docker-compose down
```

### 2. 手动构建 Docker 镜像

```bash
# 构建镜像
docker build -t router-checkin:latest .

# 运行容器
docker run -d \
  --name router-checkin \
  --env-file .env \
  -v $(pwd)/balance_data.json:/app/balance_data.json \
  -v $(pwd)/balance_hash.txt:/app/balance_hash.txt \
  -v $(pwd)/.cache:/app/.cache \
  -v /dev/shm:/dev/shm \
  -e TZ=Asia/Shanghai \
  router-checkin:latest
```

## 环境变量配置

### 必需环境变量

在 `.env` 文件中配置以下变量：

```bash
# 账号配置（参考 .env.example）
ACCOUNT_1_NAME=account1
ACCOUNT_1_PROVIDER=agentrouter
ACCOUNT_1_AUTH_METHODS=email
ACCOUNT_1_EMAIL=your@email.com
ACCOUNT_1_PASSWORD=your_password
```

### Docker 特定环境变量

```bash
# 时区设置
TZ=Asia/Shanghai

# Python 配置
PYTHONUNBUFFERED=1

# CI 环境标记（Docker 中应设为 false）
CI=false

# Cloudflare 验证（不建议跳过）
SKIP_CLOUDFLARE_CHECK=false
```

## Volume 挂载说明

### 必需挂载

```yaml
volumes:
  # 余额数据文件（会被自动更新）
  - ./balance_data.json:/app/balance_data.json

  # 余额哈希文件（用于变化检测）
  - ./balance_hash.txt:/app/balance_hash.txt

  # 会话缓存目录（保存登录会话，24小时有效）
  - ./.cache:/app/.cache

  # 共享内存（Chromium 需要）
  - /dev/shm:/dev/shm
```

### 为什么需要这些挂载？

1. **balance_data.json** - 存储账号余额历史，用于计算变化
2. **balance_hash.txt** - 存储余额哈希，用于检测变化
3. **.cache/** - 存储会话缓存，避免频繁重新登录
4. **/dev/shm** - Chromium 需要共享内存，提高性能和稳定性

## 认证方式支持

### Email 认证（推荐用于 Docker）

```bash
ACCOUNT_1_AUTH_METHODS=email
ACCOUNT_1_EMAIL=your@email.com
ACCOUNT_1_PASSWORD=your_password
```

✅ **优点**：
- 完全自动化
- 在 headless 模式下稳定运行
- 不需要人工干预

### Cookies 认证（最稳定）

```bash
ACCOUNT_1_AUTH_METHODS=cookies
ACCOUNT_1_COOKIES={"session":"xxx","token":"yyy"}
```

✅ **优点**：
- 跳过登录流程
- 成功率最高
- 适合长期运行

⚠️ **注意**：需要手动获取 cookies

### GitHub OAuth（不推荐用于 Docker）

```bash
ACCOUNT_1_AUTH_METHODS=github
ACCOUNT_1_USERNAME=github_username
ACCOUNT_1_PASSWORD=github_password
```

⚠️ **限制**：
- 可能需要人机验证
- headless 模式下可能失败
- 建议配置 `CI_DISABLED_AUTH_METHODS=github` 跳过

### Linux.do OAuth（不推荐用于 Docker）

```bash
ACCOUNT_1_AUTH_METHODS=linux.do
ACCOUNT_1_USERNAME=linuxdo_username
ACCOUNT_1_PASSWORD=linuxdo_password
```

⚠️ **限制**：
- 需要通过 challenge 验证
- headless 模式下成功率低
- 建议配置 `CI_DISABLED_AUTH_METHODS=linux.do` 跳过

## Docker 环境最佳实践

### 1. 使用会话缓存

确保挂载 `.cache` 目录：

```yaml
volumes:
  - ./.cache:/app/.cache
```

这样容器重启后不需要重新登录（24小时有效期）。

### 2. 配置 CI 禁用认证方式

对于在 Docker 中不稳定的认证方式，建议禁用：

```bash
# 在 .env 中添加
CI_DISABLED_AUTH_METHODS=github,linux.do
```

### 3. 增加超时时间

Docker 环境网络可能较慢：

```bash
CI_TIMEOUT_MULTIPLIER=2.5
CI_RETRY_COUNT=5
```

### 4. 定时任务

使用 cron 或系统定时器定期运行：

```bash
# 每天早上 8 点执行
0 8 * * * cd /path/to/project && docker-compose up
```

或使用 Docker 定时重启：

```yaml
services:
  router-checkin:
    # ... 其他配置
    deploy:
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

## 常见问题

### Q1: Chromium 启动失败

**错误信息**：
```
Failed to launch browser: Executable doesn't exist
```

**解决方案**：
```bash
# 重新构建镜像
docker-compose build --no-cache
```

### Q2: 共享内存不足

**错误信息**：
```
DevToolsActivePort file doesn't exist
```

**解决方案**：
```yaml
volumes:
  - /dev/shm:/dev/shm  # 确保挂载了共享内存
```

或增加共享内存大小：
```yaml
shm_size: 2gb
```

### Q3: 权限问题

**错误信息**：
```
Permission denied: '.cache/sessions/xxx.json'
```

**解决方案**：
```bash
# 确保宿主机目录权限正确
mkdir -p .cache/sessions
chmod -R 755 .cache
```

### Q4: OAuth 认证失败

**错误信息**：
```
Failed to get GitHub OAuth parameters after 3 retries
```

**解决方案**：
1. 使用 Email 或 Cookies 认证替代
2. 或配置跳过 OAuth 方式：
```bash
CI_DISABLED_AUTH_METHODS=github,linux.do
```

## 日志查看

### 实时日志

```bash
docker-compose logs -f
```

### 查看最近日志

```bash
docker-compose logs --tail=100
```

### 导出日志

```bash
docker-compose logs > logs.txt
```

## 性能优化

### 减小镜像大小

当前镜像包含完整的 Chromium，大小约 1GB。如果需要优化：

1. 使用多阶段构建
2. 清理不必要的系统包
3. 使用 Alpine Linux 基础镜像（需要额外配置）

### 减少资源占用

```yaml
services:
  router-checkin:
    # ... 其他配置
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          memory: 512M
```

## 安全建议

1. **不要在 Dockerfile 中硬编码敏感信息**
2. **使用 .env 文件管理配置，不要提交到 Git**
3. **定期更新基础镜像**：
   ```bash
   docker-compose pull
   docker-compose up -d
   ```
4. **使用非 root 用户运行**（已默认配置）

## 更新升级

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启容器
docker-compose up -d
```

## 完全清理

```bash
# 停止并删除容器
docker-compose down

# 删除镜像
docker rmi router-checkin:latest

# 清理缓存
rm -rf .cache

# 清理数据文件（可选）
rm balance_data.json balance_hash.txt
```
