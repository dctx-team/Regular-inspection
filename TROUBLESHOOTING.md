# 故障排查指南

## 常见问题

### 1. 页面加载超时 - Timeout 30000ms exceeded

**问题表现：**
```
[ERROR] 获取 WAF cookies 失败: Page.goto: Timeout 30000ms exceeded.
```

**原因：**
- GitHub Actions 网络访问受限
- 目标网站响应慢或不可达
- WAF/Cloudflare 防护过严

**解决方案：**

已在最新版本中实现：
- ✅ 多 URL fallback 机制
- ✅ 降低超时时间（20秒）
- ✅ 使用 `domcontentloaded` 替代 `networkidle`
- ✅ 即使无 WAF cookies 也继续尝试

**手动修复：**
如果仍有问题，可以尝试：
1. 手动触发 Actions 多次重试
2. 更换执行时间（避开高峰期）
3. 考虑使用自建服务器运行（Docker 部署）

---

### 2. 401 错误 - 认证失败

**问题表现：**
```
[ERROR] 签到失败: HTTP 401
```

**原因：**
- Session cookie 已过期
- API User ID 不正确
- Cookie 格式错误

**解决方案：**

1. **重新获取 Session Cookie：**
   - 访问网站并登录
   - F12 → Application → Cookies → 复制 `session` 值
   - 更新 GitHub Secret `ANYROUTER_ACCOUNTS` 或 `AGENTROUTER_ACCOUNTS`

2. **验证 API User ID：**
   - F12 → Network → 查看请求头 `new-api-user`
   - 确保是 5 位数字（已登录状态）

3. **检查 JSON 格式：**
   ```json
   [
     {
       "name": "账号名称",
       "cookies": {
         "session": "正确的session值"
       },
       "api_user": "12345"
     }
   ]
   ```

---

### 3. 通知未收到

**问题表现：**
```
[Email]: Message push failed! Reason: Email configuration not set
[DingTalk]: Message push failed! Reason: DingTalk Webhook not configured
```

**原因：**
- 通知配置未设置
- 默认只在失败或余额变化时通知

**解决方案：**

1. **配置通知方式：**

   在 GitHub Environment Secrets 中添加以下任意一种：

   **邮件：**
   - `EMAIL_USER` - 发件邮箱
   - `EMAIL_PASS` - 邮箱密码/授权码
   - `EMAIL_TO` - 收件邮箱

   **钉钉：**
   - `DINGDING_WEBHOOK` - 机器人 Webhook URL
   - 安全设置选择"自定义关键词"：`Router`

   **飞书：**
   - `FEISHU_WEBHOOK` - 机器人 Webhook URL

   **企业微信：**
   - `WEIXIN_WEBHOOK` - 机器人 Webhook URL

2. **通知触发条件：**
   - ❌ 签到失败时
   - 💰 余额变化时
   - ✅ 首次运行时

   **注意：** 全部成功且余额无变化时不会发送通知

---

### 4. GitHub Actions 未自动执行

**问题表现：**
- 定时任务没有运行
- Actions 页面无执行记录

**原因：**
- 工作流未启用
- Cron 表达式错误
- GitHub Actions 延迟（正常现象）

**解决方案：**

1. **启用工作流：**
   - `Actions` → 找到工作流 → `Enable workflow`

2. **检查 Cron 表达式：**
   ```yaml
   schedule:
     - cron: '0 */6 * * *'  # 每6小时
   ```

3. **了解延迟：**
   - GitHub Actions 定时任务通常延迟 1-1.5 小时
   - 这是正常现象，不影响功能

4. **手动触发测试：**
   - `Actions` → 选择工作流 → `Run workflow`

---

### 5. WAF cookies 获取失败但想继续

**问题表现：**
```
[WARN] 所有 URL 均未获取到 WAF cookies，将只使用用户 cookies
```

**说明：**
这是**正常警告**，不是错误！

**处理逻辑：**
1. 尝试获取 WAF cookies（绕过 Cloudflare）
2. 如果失败，使用用户提供的 cookies 继续
3. 如果签到成功，则无需担心

**何时需要关注：**
- 只有当最终签到失败时才需要处理
- 如果签到成功，可以忽略此警告

---

### 6. 签到成功但显示"保活成功（无签到接口）"

**问题表现：**
```
✓ [AgentRouter] 账号名: 保活成功（无签到接口）
```

**说明：**
- AgentRouter 可能没有签到接口（404）
- 脚本改为验证登录状态（获取余额）
- 只要能获取到余额，就算保活成功

**是否正常：**
✅ 完全正常！说明：
- 您的登录状态有效
- 能够正常访问 API
- 账号保持活跃

---

### 7. 多账号配置问题

**错误示例：**
```json
{
  "name": "账号1",
  "cookies": {"session": "xxx"},
  "api_user": "12345"
}
```

**正确格式：**
```json
[
  {
    "name": "账号1",
    "cookies": {"session": "xxx"},
    "api_user": "12345"
  },
  {
    "name": "账号2",
    "cookies": {"session": "yyy"},
    "api_user": "67890"
  }
]
```

**要点：**
- ✅ 必须用方括号 `[]` 包裹（数组格式）
- ✅ 多个账号用逗号分隔
- ✅ `name` 字段可选但推荐填写
- ✅ 注意 JSON 格式：引号、逗号、括号

---

### 8. Docker 部署问题

**问题：容器运行失败**

```bash
# 查看日志
docker-compose logs -f

# 重新构建
docker-compose down
docker-compose build --no-cache
docker-compose up
```

**问题：Playwright 浏览器安装失败**

在 Dockerfile 中已包含：
```dockerfile
RUN playwright install chromium && \
    playwright install-deps chromium
```

如果仍有问题，尝试：
```bash
docker-compose exec router-checkin playwright install chromium
```

---

### 9. 本地测试

**快速测试脚本：**

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 配置环境
export AGENTROUTER_ACCOUNTS='[{"name":"测试","cookies":{"session":"xxx"},"api_user":"12345"}]'

# 3. 运行
python main.py
```

**调试模式：**

修改 `checkin.py` 中的 `headless=True` → `headless=False` 可以看到浏览器操作过程。

---

## 获取帮助

如果以上方法都无法解决问题，请：

1. **收集信息：**
   - 完整的错误日志
   - 使用的部署方式（Actions/Docker/本地）
   - GitHub Actions 的完整运行日志
   - 隐藏敏感信息（session、token等）

2. **提交 Issue：**
   - 访问 https://github.com/dctx-team/Regular-inspection/issues
   - 点击 `New Issue`
   - 详细描述问题和已尝试的解决方法

3. **检查更新：**
   - 定期 `git pull` 获取最新代码
   - 查看 Commit 历史了解修复内容

---

## 调试技巧

### 查看详细日志

GitHub Actions 日志：
- `Actions` → 选择运行记录 → 查看详细步骤

### 下载 Artifacts

```
Actions → 运行记录 → Artifacts → 下载 balance-hash
```

### 测试配置格式

使用在线 JSON 验证器检查配置：
https://jsonlint.com/

---

## 预防措施

1. **定期更新 Cookie（每月一次）**
2. **配置至少一种通知方式**
3. **首次运行手动触发测试**
4. **保留备用账号配置**
5. **关注 GitHub 通知和 Issue**

---

## 性能优化建议

1. **减少账号数量**
   - 建议每个平台 2-3 个账号

2. **调整执行频率**
   - 默认 6 小时一次已足够
   - 过于频繁可能被限制

3. **使用自建服务器**
   - Docker 部署更稳定
   - 网络环境更可控

---

最后更新：2025-10-15
