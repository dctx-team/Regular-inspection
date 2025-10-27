# Router平台定时签到/登录 (重构版)

基于 Python + Playwright 实现的自动签到脚本，支持 AnyRouter、AgentRouter 等多平台多账号自动签到保活。

## ✨ 新版特性 (v2.0)

### 🎯 核心改进
- ✅ **模块化架构** - 全新的代码结构，更易维护和扩展
- ✅ **类型安全** - 使用数据类 (dataclass) 进行配置管理
- ✅ **多认证方式** - 支持 Cookies、邮箱密码、GitHub OAuth、Linux.do OAuth
- ✅ **Provider 抽象** - 统一的平台接口，支持自定义 Provider
- ✅ **智能重试** - 自动尝试所有配置的认证方式
- ✅ **余额跟踪** - 详细的余额变化监控和通知

### 📦 功能特点
- ✅ 支持 anyrouter.top 和 agentrouter.org 多平台
- ✅ 支持 Cookies、邮箱密码、GitHub、Linux.do 四种登录方式
- ✅ 自动绕过 WAF/Cloudflare 保护
- ✅ 余额监控和变化通知
- ✅ 多种通知方式（邮件、钉钉、飞书、企业微信、ServerChan、PushPlus）
- ✅ GitHub Actions 自动定时执行
- ✅ 详细的执行日志和报告
- ✅ 支持自定义 Provider 配置

## 支持的平台

- [AnyRouter](https://anyrouter.top/register?aff=hgT6) - AI API 聚合平台
- [AgentRouter](https://agentrouter.org/register?aff=7Stf) - AI Coding 公益平台

## 快速开始

### 方式一：GitHub Actions（推荐）

1. **Fork 本仓库**

2. **配置 Secrets**

   进入 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

   **配置方式 A：分平台配置（向后兼容）**

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

   **配置方式 B：统一配置（推荐，支持多种认证）**

   ```json
   ACCOUNTS=[
     {
       "name": "我的AnyRouter账号",
       "provider": "anyrouter",
       "cookies": {"session": "xxx"},
       "api_user": "12345"
     },
     {
       "name": "邮箱登录",
       "provider": "anyrouter",
       "email": {
         "username": "your@email.com",
         "password": "yourpassword"
       }
     },
     {
       "name": "我的AgentRouter账号",
       "provider": "agentrouter",
       "github": {
         "username": "myuser",
         "password": "mypass"
       }
     },
     {
       "name": "Linux.do登录",
       "provider": "agentrouter",
       "linux.do": {
         "username": "user",
         "password": "pass"
       }
     }
   ]
   ```

3. **配置通知（推荐：ServerChan）**

   **[ServerChan](https://sct.ftqq.com/r/18665)（推荐）** - 微信通知，配置简单稳定

   a. 访问 [ServerChan](https://sct.ftqq.com/r/18665) 使用微信登录

   b. 复制你的 SendKey（格式：`SCTxxxxx...`）

   c. 在 GitHub Secrets 中添加：
      - Name: `SERVERPUSHKEY`
      - Value: 你的 SendKey

   **其他通知方式（可选）**：
   - `EMAIL_USER` + `EMAIL_PASS` + `EMAIL_TO` - 邮件通知
   - `DINGDING_WEBHOOK` - 钉钉机器人
   - `FEISHU_WEBHOOK` - 飞书机器人
   - `WEIXIN_WEBHOOK` - 企业微信
   - `PUSHPLUS_TOKEN` - PushPlus

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

### 认证方式详解

本脚本支持四种认证方式，可以为同一账号配置多种认证方式作为备份：

#### 方式 1：Cookies 认证（推荐，最稳定）

**优点**：最快速，最稳定
**缺点**：Session 可能过期（通常1个月）

**获取步骤：**

1. **获取 Session Cookie：**
   - 打开浏览器，访问网站并登录
     - AnyRouter: 使用邮箱密码登录
     - AgentRouter: 点击"使用 GitHub 继续"或"使用 LinuxDO 继续"
   - 按 F12 打开开发者工具
   - 切换到 `Application` → `Cookies`
   - 找到 `session` 字段，复制其值

2. **获取 API User ID：**
   - 开发者工具切换到 `Network` 标签
   - 刷新页面或进行操作
   - 找到任意 API 请求，查看请求头中的 `New-Api-User` 字段值
   - 或者查看控制台页面 URL 中的数字ID

**配置示例：**
```json
{
  "name": "我的账号",
  "provider": "anyrouter",
  "cookies": {"session": "your_session_cookie"},
  "api_user": "12345"
}
```

#### 方式 2：邮箱密码认证（AnyRouter）

**优点**：无需手动获取 Cookie，直接使用账号密码
**缺点**：依赖平台登录接口稳定性

**适用平台**：AnyRouter（支持邮箱密码直接登录）

**配置示例：**
```json
{
  "name": "邮箱登录",
  "provider": "anyrouter",
  "email": {
    "username": "your@email.com",
    "password": "your_password"
  }
}
```

#### 方式 3：GitHub OAuth 认证（AgentRouter）

**优点**：无需手动更新 Cookie
**缺点**：需要 GitHub 账号密码，首次登录可能需要 2FA

**配置示例：**
```json
{
  "name": "GitHub登录",
  "provider": "agentrouter",
  "github": {
    "username": "your_github_username",
    "password": "your_github_password"
  }
}
```

#### 方式 4：Linux.do OAuth 认证（AgentRouter）

**优点**：无需手动更新 Cookie
**缺点**：需要 Linux.do 账号

**配置示例：**
```json
{
  "name": "Linux.do登录",
  "provider": "agentrouter",
  "linux.do": {
    "username": "your_linux_do_username",
    "password": "your_linux_do_password"
  }
}
```

### 多认证方式配置（推荐）

可以为同一账号配置多种认证方式，脚本会依次尝试，提高成功率：

```json
{
  "name": "我的AnyRouter账号（多认证备份）",
  "provider": "anyrouter",
  "cookies": {"session": "xxx"},
  "api_user": "12345",
  "email": {
    "username": "your@email.com",
    "password": "your_password"
  }
}
```

或者 AgentRouter 的多认证配置：

```json
{
  "name": "我的AgentRouter账号",
  "provider": "agentrouter",
  "cookies": {"session": "xxx"},
  "api_user": "12345",
  "github": {
    "username": "myuser",
    "password": "mypass"
  },
  "linux.do": {
    "username": "user",
    "password": "pass"
  }
}
```

### 自定义 Provider

如果你有其他使用 newapi 架构的平台，可以添加自定义 Provider：

```json
PROVIDERS='{
  "custom": {
    "name": "自定义平台",
    "base_url": "https://custom.example.com",
    "login_url": "https://custom.example.com/login",
    "checkin_url": "https://custom.example.com/api/user/checkin",
    "user_info_url": "https://custom.example.com/api/user/self"
  }
}'
```

然后在账号配置中使用：
```json
{
  "name": "自定义平台账号",
  "provider": "custom",
  "cookies": {"session": "xxx"},
  "api_user": "12345"
}
```

### 环境变量配置

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `ANYROUTER_ACCOUNTS` | AnyRouter 账号配置（JSON数组） | 否* |
| `AGENTROUTER_ACCOUNTS` | AgentRouter 账号配置（JSON数组） | 否* |
| `ACCOUNTS` | 统一账号配置（支持多 Provider）| 否* |
| `PROVIDERS` | 自定义 Provider 配置 | 否 |
| `EMAIL_USER` | 邮件发送地址 | 否 |
| `EMAIL_PASS` | 邮件密码/授权码 | 否 |
| `EMAIL_TO` | 邮件接收地址 | 否 |
| `CUSTOM_SMTP_SERVER` | 自定义 SMTP 服务器 | 否 |
| `SERVERPUSHKEY` | Server酱 SendKey（[获取](https://sct.ftqq.com/r/18665)） | 否 |
| `PUSHPLUS_TOKEN` | PushPlus Token | 否 |
| `DINGDING_WEBHOOK` | 钉钉机器人 Webhook | 否 |
| `FEISHU_WEBHOOK` | 飞书机器人 Webhook | 否 |
| `WEIXIN_WEBHOOK` | 企业微信 Webhook | 否 |

*至少需要配置一种账号配置方式

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

## 🆕 最新修复 (v2.1.0)

### ✅ 关键问题修复

- **🔧 AgentRouter 404 错误** - 修正签到接口配置，解决 `HTTP 404` 问题
- **🔐 GitHub 2FA 支持** - 完整实现 3 种 2FA 处理方式（TOTP、恢复代码、预生成代码）
- **🔄 智能重试机制** - 网络请求自动重试，提高稳定性
- **📝 统一日志系统** - 彩色日志输出，便于问题排查
- **✅ 配置验证工具** - 自动检测配置错误，提供修复建议

### 🚀 快速开始

```bash
# 1. 安装新依赖
pip install pyotp

# 2. 配置 GitHub 2FA（如果需要）
export GITHUB_2FA_CODE="123456"  # 当前 2FA 代码

# 3. 测试修复效果
python test_fixes.py

# 4. 正常使用
python main.py
```

详细修复说明请查看：[修复指南](./FIXES_GUIDE.md)

## 项目结构

```
Regular-inspection/
├── main.py                    # 主程序入口
├── checkin.py                 # 签到核心逻辑（含重试机制）
├── test_fixes.py              # 修复验证测试脚本
├── utils/
│   ├── config.py              # 配置管理（数据类）
│   ├── auth.py                # 认证实现（含 2FA 支持）
│   ├── notify.py              # 通知模块
│   ├── logger.py              # 统一日志系统（新增）
│   └── validator.py           # 配置验证工具（新增）
├── requirements.txt           # Python 依赖（新增 pyotp）
├── pyproject.toml             # 项目配置
├── .env.example               # 环境变量模板
├── FIXES_GUIDE.md             # 详细修复指南（新增）
├── QUICK_FIXES.md             # 快速修复指南（新增）
├── .github/
│   └── workflows/
│       └── auto-checkin.yml   # GitHub Actions 配置
├── Dockerfile                 # Docker 镜像
└── docker-compose.yml         # Docker Compose 配置
```

## 故障排查

**遇到问题？** 查看详细的 [故障排查指南](./TROUBLESHOOTING.md) 📖

### 快速参考

1. **页面超时错误** - 已优化，支持多 URL fallback
2. **401 认证失败** - 重新获取 session cookie
3. **WAF 拦截** - 脚本自动处理
4. **通知未收到** - 检查配置，默认仅失败、首次运行或余额变化时通知
5. **Actions 未执行** - 启用工作流，注意延迟正常

> 💡 **提示：** "签到成功" 表示账号登录有效，已完成保活操作！

详细解决方案请查看 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

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
