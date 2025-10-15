# Router平台定时签到/登录

基于 Python + Playwright 实现的自动签到脚本，支持 anyrouter.top 和 agentrouter.org 多账号自动签到保活。

## 功能特点

- ✅ 支持 anyrouter.top 和 agentrouter.org 多账号
- ✅ 自动绕过 WAF/Cloudflare 保护
- ✅ Cookie 持久化，智能登录
- ✅ 余额监控和变化通知
- ✅ 多种通知方式（邮件、钉钉、飞书、企业微信等）
- ✅ GitHub Actions 自动定时执行
- ✅ 详细的执行日志和报告
- ✅ 失败自动重试机制

## 支持的平台

- [AnyRouter](https://anyrouter.top/) - AI API 聚合平台
- [AgentRouter](https://agentrouter.org/) - AI Coding 公益平台

## 快速开始

### 方式一：GitHub Actions（推荐）

1. **Fork 本仓库**

2. **配置 Secrets**

   进入 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

   **AnyRouter 配置：**
   ```json
   ANYROUTER_ACCOUNTS=[
     {
       "name": "AnyRouter主账号",
       "cookies": {
         "session": "your_session_cookie"
       },
       "api_user": "12345"
     }
   ]
   ```

   **AgentRouter 配置：**
   ```json
   AGENTROUTER_ACCOUNTS=[
     {
       "name": "AgentRouter主账号",
       "cookies": {
         "session": "your_session_cookie"
       },
       "api_user": "12345"
     }
   ]
   ```

3. **配置通知（可选）**

   添加以下任一通知方式的环境变量：
   - `EMAIL_USER` + `EMAIL_PASS` + `EMAIL_TO` - 邮件通知
   - `DINGDING_WEBHOOK` - 钉钉机器人
   - `FEISHU_WEBHOOK` - 飞书机器人
   - `WEIXIN_WEBHOOK` - 企业微信
   - `PUSHPLUS_TOKEN` - PushPlus
   - `SERVERPUSHKEY` - Server酱

4. **启用 Actions**

   进入 `Actions` → 选择工作流 → `Enable workflow`

### 方式二：本地运行

```bash
# 1. 克隆仓库
git clone <repo_url>
cd Regular-inspection

# 2. 安装依赖（使用 uv）
uv sync

# 3. 安装浏览器
playwright install chromium

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入账号信息

# 5. 运行脚本
uv run python main.py
```

### 方式三：Docker 部署

```bash
# 1. 复制配置文件
cp .env.example .env

# 2. 编辑配置
vim .env

# 3. 构建并运行
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 手动执行
docker-compose run --rm router-checkin
```

## 配置说明

### 获取账号信息

#### AnyRouter / AgentRouter

1. **获取 Session Cookie：**
   - 打开浏览器，访问网站并登录
   - 按 F12 打开开发者工具
   - 切换到 `Application` → `Cookies`
   - 找到 `session` 字段，复制其值

2. **获取 API User ID：**
   - 开发者工具切换到 `Network` 标签
   - 刷新页面或进行操作
   - 找到任意请求，查看请求头中的 `New-Api-User` 字段值

### 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `ANYROUTER_ACCOUNTS` | AnyRouter 账号配置（JSON数组） | 否 |
| `AGENTROUTER_ACCOUNTS` | AgentRouter 账号配置（JSON数组） | 否 |
| `EMAIL_USER` | 邮件发送地址 | 否 |
| `EMAIL_PASS` | 邮件密码/授权码 | 否 |
| `EMAIL_TO` | 邮件接收地址 | 否 |
| `DINGDING_WEBHOOK` | 钉钉机器人 Webhook | 否 |
| `FEISHU_WEBHOOK` | 飞书机器人 Webhook | 否 |
| `WEIXIN_WEBHOOK` | 企业微信 Webhook | 否 |
| `PUSHPLUS_TOKEN` | PushPlus Token | 否 |
| `SERVERPUSHKEY` | Server酱 SendKey | 否 |

## 定时设置

默认执行时间：
- 每 6 小时执行一次
- 可在 `.github/workflows/auto-checkin.yml` 中修改 cron 表达式

常用时间配置：
```yaml
schedule:
  - cron: '0 */6 * * *'   # 每6小时
  - cron: '0 0 * * *'     # 每天0点
  - cron: '0 0,12 * * *'  # 每天0点和12点
```

## 项目结构

```
Regular-inspection/
├── main.py              # 主程序入口
├── checkin.py           # 签到核心逻辑
├── notify.py            # 通知模块
├── config.py            # 配置管理
├── requirements.txt     # Python依赖
├── pyproject.toml       # 项目配置
├── .env.example         # 环境变量模板
├── .github/
│   └── workflows/
│       └── auto-checkin.yml  # GitHub Actions配置
├── Dockerfile           # Docker镜像
└── docker-compose.yml   # Docker Compose配置
```

## 故障排查

### 常见问题

1. **签到失败 - 401 错误**
   - Session cookie 已过期，重新获取
   - API User ID 不正确

2. **签到失败 - WAF 拦截**
   - 脚本会自动使用 Playwright 绕过
   - 确保网络环境正常

3. **GitHub Actions 未执行**
   - 检查工作流是否启用
   - 检查 cron 表达式是否正确
   - Actions 可能有延迟（1-1.5小时）

4. **通知未收到**
   - 检查通知配置是否正确
   - 默认只在失败或余额变化时通知

## 注意事项

1. **账号安全**
   - 使用 GitHub Secrets 保护敏感信息
   - 不要在代码中硬编码密码
   - Session cookie 通常有效期 1 个月

2. **使用频率**
   - 建议 6-24 小时执行一次
   - 避免过于频繁导致账号异常

3. **合规使用**
   - 仅用于个人账号保活
   - 遵守平台服务条款

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 鸣谢

本项目整合了以下项目的优秀特性：
- [anyrouter-check-in](https://github.com/millylee/anyrouter-check-in) - WAF绕过技术
- [网站定时登录](https://github.com/xxx/xxx) - Cookie持久化方案
