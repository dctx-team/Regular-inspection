# Router 平台自动签到 - 快速使用指南

## 📦 获取账号配置信息

### 1. 登录网站

访问 https://anyrouter.top/register?aff=hgT6 或 https://agentrouter.org/register?aff=7Stf 并登录您的账号。

### 2. 获取 Session Cookie

1. 按 `F12` 打开浏览器开发者工具
2. 切换到 `Application` (Chrome) 或 `存储` (Firefox) 标签
3. 左侧找到 `Cookies` → 选择对应网站
4. 找到 `session` 字段，复制其 Value 值

### 3. 获取 API User ID

1. 开发者工具切换到 `Network` (网络) 标签
2. 刷新页面或进行任意操作
3. 选择任意一个 API 请求
4. 查看 `Request Headers` (请求头)
5. 找到 `new-api-user` 或 `New-Api-User` 字段，复制其值

## 🚀 GitHub Actions 部署（推荐）

### 步骤 1: Fork 仓库

点击右上角 Fork 按钮

### 步骤 2: 配置 Environment

1. 进入仓库 `Settings` → `Environments`
2. 点击 `New environment`
3. 创建名为 `production` 的环境

### 步骤 3: 添加 Secrets

在 `production` 环境中添加以下 Secrets：

#### AnyRouter 配置

**Secret Name:** `ANYROUTER_ACCOUNTS`

**Secret Value:**
```json
[
  {
    "name": "我的主账号",
    "cookies": {
      "session": "你的session值"
    },
    "api_user": "你的api_user值"
  }
]
```

#### AgentRouter 配置

**Secret Name:** `AGENTROUTER_ACCOUNTS`

**Secret Value:**
```json
[
  {
    "name": "我的主账号",
    "cookies": {
      "session": "你的session值"
    },
    "api_user": "你的api_user值"
  }
]
```

#### 通知配置（推荐：ServerChan）

**推荐：[ServerChan](https://sct.ftqq.com/r/18665)** - 微信通知，配置简单稳定

1. 访问 [ServerChan](https://sct.ftqq.com/r/18665)
2. 使用微信扫码登录
3. 复制你的 SendKey
4. 在 GitHub Secrets 中添加 `SERVERPUSHKEY`

**其他通知方式：**

- **邮件通知：** `EMAIL_USER`, `EMAIL_PASS`, `EMAIL_TO`（注意：GitHub Actions 环境可能不稳定）
- **钉钉：** `DINGDING_WEBHOOK`
- **飞书：** `FEISHU_WEBHOOK`
- **企业微信：** `WEIXIN_WEBHOOK`
- **PushPlus：** `PUSHPLUS_TOKEN`

### 步骤 4: 启用 Actions

1. 进入 `Actions` 标签
2. 点击 `I understand my workflows, go ahead and enable them`
3. 找到 `Router 自动签到` 工作流
4. 点击 `Enable workflow`

### 步骤 5: 手动测试

1. 在 `Actions` 页面
2. 选择 `Router 自动签到`
3. 点击 `Run workflow`
4. 查看运行日志

## 🐳 Docker 本地部署

### 步骤 1: 克隆仓库

```bash
git clone <your-repo-url>
cd Regular-inspection
```

### 步骤 2: 配置环境变量

```bash
cp .env.example .env
vim .env  # 或使用其他编辑器
```

填入您的账号信息：

```bash
ANYROUTER_ACCOUNTS='[{"name":"主账号","cookies":{"session":"xxx"},"api_user":"12345"}]'
AGENTROUTER_ACCOUNTS='[{"name":"主账号","cookies":{"session":"xxx"},"api_user":"12345"}]'
```

### 步骤 3: 构建并运行

```bash
# 构建镜像
docker-compose build

# 运行签到
docker-compose up

# 后台运行
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 步骤 4: 设置定时任务

使用 cron 定时执行：

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每6小时执行）
0 */6 * * * cd /path/to/Regular-inspection && docker-compose run --rm router-checkin >> /var/log/router-checkin.log 2>&1
```

## 💻 本地 Python 运行

### 步骤 1: 安装依赖

```bash
# 使用 pip
pip install -r requirements.txt
playwright install chromium

# 或使用 uv (更快)
pip install uv
uv sync
playwright install chromium
```

### 步骤 2: 配置环境变量

```bash
cp .env.example .env
vim .env
```

### 步骤 3: 运行脚本

```bash
# 使用 pip 安装
python main.py

# 使用 uv
uv run python main.py
```

## 📋 多账号配置示例

### 配置多个账号

```json
[
  {
    "name": "账号1",
    "cookies": {
      "session": "session_value_1"
    },
    "api_user": "12345"
  },
  {
    "name": "账号2",
    "cookies": {
      "session": "session_value_2"
    },
    "api_user": "67890"
  }
]
```

### 同时配置两个平台

在 GitHub Secrets 或 .env 中分别配置（任选其一或并用）：
- `ANYROUTER_ACCOUNTS` - AnyRouter 账号（JSON 数组）
- `AGENTROUTER_ACCOUNTS` - AgentRouter 账号（JSON 数组）
- `ACCOUNTS` - 多平台统一账号配置（JSON 数组）
- `PROVIDERS` - 自定义 Provider（JSON 对象，可选）

## ⏰ 定时设置说明

默认每 6 小时执行一次，可修改 `.github/workflows/auto-checkin.yml`：

```yaml
schedule:
  - cron: '0 */6 * * *'   # 每6小时
  - cron: '0 0 * * *'     # 每天午夜
  - cron: '0 0,12 * * *'  # 每天0点和12点
```

## 🔔 通知配置

### ServerChan（推荐）

**优势：**
- ✅ 微信直接接收，无需额外 APP
- ✅ 配置简单，只需 1 个密钥
- ✅ 稳定可靠，专为 GitHub Actions 设计
- ✅ 免费额度充足（5000次/天）

**配置步骤：**

1. **获取 SendKey**
   - 访问：https://sct.ftqq.com/r/18665
   - 使用微信扫码登录
   - 点击 "SendKey" 菜单
   - 复制你的 SendKey（格式：`SCTxxxxx...`）

2. **配置 GitHub Secret**
   - 仓库 Settings → Secrets → Actions
   - 点击 New repository secret
   - Name: `SERVERPUSHKEY`
   - Value: 粘贴你的 SendKey
   - 点击 Add secret

3. **测试**
   - Actions → Router 自动签到 → Run workflow
   - 等待运行完成
   - 打开微信，查看 "Server酱" 公众号消息

### 钉钉机器人

1. 群设置 → 智能群助手 → 添加机器人 → 自定义
2. 安全设置选择"自定义关键词"，输入 `Router`
3. 复制 Webhook URL 到 `DINGDING_WEBHOOK`

### 飞书机器人

1. 群设置 → 群机器人 → 添加机器人 → 自定义机器人
2. 复制 Webhook URL 到 `FEISHU_WEBHOOK`

### 企业微信

1. 群设置 → 群机器人
2. 复制 Webhook URL 到 `WEIXIN_WEBHOOK`

## ❓ 常见问题

### 1. Cookie 过期怎么办？

重新获取 session cookie 并更新配置。Cookie 通常有效期约 1 个月。

### 2. 签到失败 - 401 错误

检查：
- Session cookie 是否正确/过期
- API User ID 是否正确

### 3. 为什么没收到通知？

默认只在以下情况发送通知：
- 签到失败
- 余额变化

所有成功且余额无变化时不会发送通知。

### 4. GitHub Actions 没有执行

- 检查工作流是否启用
- GitHub Actions 定时任务可能延迟 1-1.5 小时
- 可以手动触发测试

## 📝 注意事项

1. **保护隐私：** 不要将 .env 文件提交到 Git
2. **Cookie 安全：** 使用 GitHub Secrets 存储敏感信息
3. **执行频率：** 建议 6-24 小时执行一次
4. **合规使用：** 仅用于个人账号保活

## 🆘 获取帮助

如遇问题请提交 Issue，并提供：
- 错误信息截图
- 日志内容（隐藏敏感信息）
- 使用的部署方式
