# 重构建议

> 基于安全审计报告的重构方向和具体建议

---

## 1. 模块职责划分

### 1.1 checkin.py 拆分建议

当前 `checkin.py` 承担了过多职责（47KB），建议按功能拆分：

```
checkin/
├── __init__.py          # 导出 CheckIn 类
├── core.py              # CheckIn 类核心逻辑：execute(), _checkin_with_auth()
├── browser.py           # 浏览器环境签到：_do_checkin_in_browser(), _get_user_info_in_browser()
├── http_client.py       # HTTP 客户端签到：_do_checkin(), _get_user_info()
├── balance.py           # 余额管理：_calculate_balance_change(), _save_balance_data()
└── response_handlers.py # 响应处理：_handle_200_response(), _handle_401_response() 等
```

**预期效果**：
- 每个文件 200-400 行，可读性提升
- 职责单一，更容易测试
- 浏览器/HTTP 签到策略可独立演进

### 1.2 auth 模块优化

当前状态良好，建议微调：
- `base.py` 的 `_validate_url_security()` 可提取为独立的安全验证工具

---

## 2. 代码重复消除

### 2.1 签到/用户信息的浏览器 fetch 逻辑

`_do_checkin_in_browser()` 和 `_get_user_info_in_browser()` 中的 JavaScript fetch 代码高度相似。

**建议**：提取通用的 `_browser_fetch()` 方法：

```python
async def _browser_fetch(self, page, url, method="GET", headers=None):
    """通用浏览器 fetch 封装"""
    result = await page.evaluate("""
        async ({url, method, headers}) => {
            try {
                const response = await fetch(url, {
                    method, headers, credentials: 'include'
                });
                const contentType = response.headers.get('content-type');
                const data = contentType?.includes('json')
                    ? await response.json() : await response.text();
                return { status: response.status, ok: response.ok, contentType, data };
            } catch (error) {
                return { status: 0, ok: false, error: error.message };
            }
        }
    """, {"url": url, "method": method, "headers": headers or {}})
    return result
```

### 2.2 请求头构建

`_prepare_checkin_headers()` 和 `_prepare_user_info_headers()` 共享大部分逻辑。

**建议**：提取 `_prepare_api_headers(extra_headers=None)` 基础方法。

---

## 3. 性能优化建议

### 3.1 速率限制器

当前使用 `random.uniform(RATE_LIMIT_DELAY_MIN, RATE_LIMIT_DELAY_MAX)` 做简单延迟。

**建议**：实现令牌桶算法的 `RateLimiter` 类，支持：
- 全局速率控制
- 自适应延迟（根据连续失败次数递增）
- 按 Provider 独立限流

### 3.2 并发控制

多账号签到时可考虑：
- 使用 `asyncio.Semaphore` 限制并发浏览器实例数
- 避免同时对同一 Provider 发起过多请求

### 3.3 日志脱敏优化

当前 `sanitizer.py` 在需要时手动调用。

**建议**：在 `logger.py` 中添加 `SanitizingFilter`，自动拦截所有日志消息并脱敏，避免遗漏。

---

## 4. 测试增强建议

### 4.1 集成测试

- 添加端到端签到流程的 mock 测试
- 测试多 Provider 并发签到场景
- 测试网络错误恢复能力

### 4.2 安全测试

- 测试路径遍历防护
- 测试 cookie 注入防护
- 测试 SSL 验证不可绕过

---

## 5. 实施优先级

| 优先级 | 建议 | 预估工作量 | 影响范围 |
|--------|------|-----------|---------|
| **高** | 添加速率限制器 | 2h | checkin.py |
| **高** | 日志集成脱敏过滤器 | 1h | logger.py |
| **中** | checkin.py 拆分 | 4h | checkin/ 目录 |
| **中** | 提取通用 browser_fetch | 1h | checkin.py |
| **低** | 移除 XOR 兼容代码 | 0.5h | session_cache.py |
| **低** | 集成测试增强 | 4h | tests/ |
