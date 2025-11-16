# Cloudscraper 集成说明

## 概述

本项目已成功集成 **cloudscraper** 库，以增强 Cloudflare WAF 绕过能力。新的实现采用**双重降级机制**：优先使用 Playwright（更可靠），失败时自动降级到 cloudscraper。

## 主要改进

### 1. 架构设计

- **基础设施层** (`utils/auth/base.py`)
  - 新增 `CloudscraperHelper` 类：封装 cloudscraper 功能，支持异步调用
  - 新增 `_get_waf_cookies()` 方法：实现 Playwright → cloudscraper 双重降级逻辑

- **认证层** (`utils/auth/github.py` 和 `utils/auth/linuxdo.py`)
  - 在初始 cookies 获取阶段集成 cloudscraper 增强
  - 在重试失败后使用 cloudscraper 作为最后降级方案

### 2. 降级策略

```
┌─────────────────────────────────────────────────────────────┐
│                    WAF Cookies 获取流程                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. 优先方案：Playwright 获取 cookies                          │
│     ├─ 访问目标页面                                            │
│     ├─ 等待 Cloudflare 验证完成                                │
│     └─ 提取 browser cookies                                   │
│                                                               │
│  2. 降级方案：Cloudscraper 获取 cookies（仅在 Playwright 失败时）│
│     ├─ 创建 cloudscraper 实例                                  │
│     ├─ 模拟浏览器特征（Chrome/Windows）                         │
│     ├─ 访问目标页面并自动处理 JS Challenge                      │
│     ├─ 提取 HTTP cookies                                       │
│     └─ 注入到 Playwright context                               │
│                                                               │
│  3. 兜底方案：空 cookies 继续（不阻塞后续流程）                  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 3. 关键代码片段

#### CloudscraperHelper 类

```python
class CloudscraperHelper:
    """cloudscraper 辅助类 - 用于获取绕过 Cloudflare 的初始 cookies（降级方案）"""

    @staticmethod
    async def get_cf_cookies(url: str, proxy: Optional[str] = None) -> Dict[str, str]:
        """使用 cloudscraper 获取绕过 Cloudflare 的 cookies"""
        def _sync_get_cookies():
            try:
                import cloudscraper
                scraper = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'desktop': True
                    }
                )
                response = scraper.get(url, proxies=proxies, timeout=30)
                cookies = {cookie.name: cookie.value for cookie in scraper.cookies}
                return cookies
            except ImportError:
                logger.debug("⚠️ cloudscraper 未安装，跳过此降级方案")
                return {}

        # 在线程池中运行同步代码（保持异步架构）
        loop = asyncio.get_event_loop()
        cookies = await loop.run_in_executor(None, _sync_get_cookies)
        return cookies
```

#### 双重降级逻辑（GitHub 认证器示例）

```python
# 初始 cookies 获取阶段
initial_cookies = await context.cookies()
cookies_dict = {cookie["name"]: cookie["value"] for cookie in initial_cookies}

# 如果 cookies 数量太少，尝试使用 cloudscraper 增强
if len(cookies_dict) < 2:
    logger.warning(f"⚠️ Playwright 获取的 cookies 较少，尝试 cloudscraper 增强...")
    enhanced_cookies = await self._get_waf_cookies(page, context, use_cloudscraper=True)
    if enhanced_cookies and len(enhanced_cookies) > len(cookies_dict):
        cookies_dict = enhanced_cookies
        logger.info(f"✅ Cloudscraper 增强成功")

# 重试失败后的最后降级
if retry == max_retries - 1 and not oauth_params:
    logger.info(f"🔄 最后尝试：使用 cloudscraper 增强...")
    enhanced_cookies = await self._get_waf_cookies(page, context, use_cloudscraper=True)
    if enhanced_cookies:
        cookies_dict.update(enhanced_cookies)
        oauth_params = await self._get_github_oauth_params(cookies_dict, page)
```

## 安装依赖

### 方法 1：使用主 requirements.txt（推荐）

```bash
pip install -r requirements.txt
```

已自动包含 `cloudscraper>=1.2.71`

### 方法 2：仅安装 cloudscraper

```bash
pip install cloudscraper>=1.2.71
```

## 使用说明

### 1. 默认行为

集成后无需任何配置，脚本会自动使用双重降级机制：

```bash
python main.py
```

**工作流程：**
- Playwright 优先获取 cookies
- 如果 cookies 少于 2 个，自动尝试 cloudscraper
- 如果重试失败，最后再次尝试 cloudscraper

### 2. 配置代理（可选）

Cloudscraper 支持通过环境变量配置代理：

```bash
# Windows
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890

# Linux/macOS
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
```

### 3. 禁用 cloudscraper 降级（可选）

如果需要禁用 cloudscraper 降级，可以修改代码：

```python
# 在 github.py 或 linuxdo.py 中
enhanced_cookies = await self._get_waf_cookies(page, context, use_cloudscraper=False)
```

## 日志输出示例

### 成功使用 Playwright

```
ℹ️  尝试使用 Playwright 获取 WAF cookies...
✅ Playwright 获取成功: 5 个 cookies
```

### Playwright 失败，降级到 cloudscraper

```
ℹ️  尝试使用 Playwright 获取 WAF cookies...
⚠️  Playwright 获取 WAF cookies 失败: TimeoutError
ℹ️  降级使用 cloudscraper...
✅ Cloudscraper 获取成功: 3 个 cookies
```

### 初始 cookies 少，自动增强

```
🔑 获取初始cookies...
⚠️  Playwright 获取的 cookies 较少(1个)，尝试 cloudscraper 增强...
ℹ️  降级使用 cloudscraper...
✅ Cloudscraper 获取成功: 4 个 cookies
✅ Cloudscraper 增强成功，现有 4 个cookies
```

### 重试失败，最后降级

```
❌ 所有重试均失败
🔄 最后尝试：使用 cloudscraper 增强...
ℹ️  降级使用 cloudscraper...
✅ Cloudscraper 获取成功: 3 个 cookies
✅ Cloudscraper 增强后 OAuth参数获取成功
```

## 兼容性保证

### 1. 向后兼容

- 如果 cloudscraper 未安装，会自动跳过降级方案，不影响现有功能
- 所有错误都有妥善处理，不会导致脚本崩溃

### 2. 异步架构

- 使用 `run_in_executor` 包装同步的 cloudscraper，保持整体异步架构
- 不会阻塞其他异步操作

### 3. 错误处理

```python
# CloudscraperHelper 中的错误处理
except ImportError:
    logger.debug("⚠️ cloudscraper 未安装，跳过此降级方案")
    return {}
except Exception as e:
    logger.debug(f"⚠️ Cloudscraper 获取失败: {e}")
    return {}
```

## 测试建议

### 1. 功能测试

```bash
# 测试基本功能
python main.py

# 测试代理配置
export HTTP_PROXY=http://127.0.0.1:7890
python main.py
```

### 2. 降级测试

模拟 Playwright 失败场景：
- 断开网络连接后再连接
- 使用不稳定的网络环境
- 在 CI 环境中测试（Cloudflare 更严格）

### 3. 性能测试

对比启用/禁用 cloudscraper 的成功率：
- 记录 Playwright 成功率
- 记录 cloudscraper 降级成功率
- 统计总体成功率提升

## 潜在风险与注意事项

### 1. 性能影响

- **风险**：cloudscraper 需要额外的 HTTP 请求，可能增加 2-5 秒延迟
- **缓解**：仅在 Playwright 失败时才触发，不影响正常流程

### 2. 依赖冲突

- **风险**：cloudscraper 依赖 requests 和 requests-toolbelt
- **缓解**：已在 requirements.txt 中指定版本 `>=1.2.71`

### 3. Cloudflare 检测升级

- **风险**：Cloudflare 可能更新检测机制，使 cloudscraper 失效
- **缓解**：保持 cloudscraper 为降级方案，Playwright 仍是主力

### 4. 代理兼容性

- **风险**：某些代理可能不支持 cloudscraper
- **缓解**：代理为可选配置，不影响无代理场景

## 相关文件

- **核心实现**
  - `utils/auth/base.py` - CloudscraperHelper 类和 _get_waf_cookies 方法
  - `utils/auth/github.py` - GitHub 认证器集成
  - `utils/auth/linuxdo.py` - LinuxDO 认证器集成

- **依赖配置**
  - `requirements.txt` - 主依赖文件
  - `requirements_with_cloudscraper.txt.example` - 示例配置（参考）

- **示例代码**
  - `utils/cloudscraper_integration_example.py` - 完整示例代码

## 技术细节

### 同步转异步包装

由于 cloudscraper 是同步库，而项目使用异步架构，需要使用 `run_in_executor` 包装：

```python
async def get_cf_cookies(url: str, proxy: Optional[str] = None) -> Dict[str, str]:
    def _sync_get_cookies():
        # 同步代码
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url)
        return {cookie.name: cookie.value for cookie in scraper.cookies}

    # 在线程池中运行
    loop = asyncio.get_event_loop()
    cookies = await loop.run_in_executor(None, _sync_get_cookies)
    return cookies
```

### Cookie 注入

从 cloudscraper 获取的 cookies 需要注入到 Playwright context：

```python
domain = self._get_domain(url)
for name, value in cf_cookies.items():
    await context.add_cookies([{
        "name": name,
        "value": value,
        "domain": domain,
        "path": "/"
    }])
```

## 更新日志

- **2025-01-XX**: 初始集成 cloudscraper 双重降级机制
- 集成到 `utils/auth/base.py`（基类）
- 集成到 `utils/auth/github.py`（GitHub 认证器）
- 集成到 `utils/auth/linuxdo.py`（LinuxDO 认证器）
- 更新 `requirements.txt` 添加 cloudscraper 依赖

## 反馈与支持

如果遇到问题或有改进建议，请：
1. 查看日志输出，确认 cloudscraper 是否成功触发
2. 检查 cloudscraper 是否正确安装：`pip show cloudscraper`
3. 尝试更新到最新版本：`pip install --upgrade cloudscraper`
4. 提交 Issue 或 Pull Request
