# Cloudflare 绕过能力优化 - 环境变量配置指南

## 概述

本项目集成了 2025 年最新的 Cloudflare 绕过技术，包括：

1. **增强的反检测脚本**（自动启用）
   - TLS/HTTP2 指纹伪装
   - sec-ch-ua 系列请求头注入
   - WebGL 指纹一致性增强
   - Fetch/XHR API 拦截

2. **关键 Cloudflare Cookies 检测**（自动启用）
   - cf_clearance
   - __cf_bm
   - cf_chl_2

3. **分段 Cloudflare 验证检测**（自动启用）
   - 每 5 秒检测一次验证状态
   - 智能识别 Cloudflare 验证页面

4. **可配置的等待时间倍增器**（可选）
5. **Cloudscraper 降级方案**（自动启用）
6. **TLS 指纹伪装**（可选，需要额外依赖）

---

## 环境变量配置

### 1. Linux.do 特定等待时间倍增器

**用途**：为 Linux.do OAuth 认证配置更长的等待时间，以应对 Cloudflare 验证。

```bash
# 全局等待时间倍增器（默认 1.0）
WAIT_TIME_MULTIPLIER=1.5

# Linux.do 特定倍增器（覆盖全局配置）
LINUXDO_WAIT_TIME_MULTIPLIER=2.0

# GitHub 特定倍增器
GITHUB_WAIT_TIME_MULTIPLIER=1.5
```

**说明**：
- 倍增器会应用到所有等待时间（初始等待、重试等待等）
- 推荐值：1.5 - 3.0
- CI 环境建议使用 2.0 或更高

**示例计算**：
- 基础等待时间（CI 环境）：15 秒
- 倍增器：2.0
- 实际等待时间：15 × 2.0 = 30 秒

---

### 2. TLS 指纹伪装（可选）

**用途**：使用 curl-cffi 模拟真实浏览器的 TLS 指纹，绕过高级 TLS 指纹检测（JA3/JA4）。

```bash
# 启用 TLS 指纹伪装
ENABLE_TLS_FINGERPRINT=true

# 指定浏览器类型（默认 chrome131）
TLS_BROWSER_TYPE=chrome131

# 可选值：
# - chrome131  (推荐，最新版本)
# - chrome120
# - chrome116
# - edge101
# - firefox
# - safari15_5
```

**依赖安装**：
```bash
# 标准安装
pip install curl-cffi>=0.6.0

# Windows 系统可能需要
# 1. 安装 Visual C++ Build Tools
# 2. 或使用预编译轮包：pip install curl-cffi --only-binary :all:

# Linux 系统可能需要
sudo apt-get install libcurl4-openssl-dev python3-dev
pip install curl-cffi>=0.6.0
```

**注意**：
- TLS 指纹伪装是可选功能，安装失败不影响基础功能
- 在 Playwright 和 cloudscraper 都失败时才会尝试 TLS 指纹
- CI 环境中可能需要额外配置（如预安装依赖）

---

### 3. 代理配置（可选）

**用途**：配置 HTTP/HTTPS 代理，可用于所有 Cloudflare 绕过方案。

```bash
# HTTP 代理
HTTP_PROXY=http://127.0.0.1:7890

# HTTPS 代理（推荐与 HTTP_PROXY 保持一致）
HTTPS_PROXY=http://127.0.0.1:7890
```

**说明**：
- 代理配置会自动应用到 cloudscraper 和 TLS 指纹伪装
- 支持 HTTP、HTTPS、SOCKS5 代理
- 不影响 Playwright 的代理配置（需在浏览器启动时配置）

---

### 4. 跳过 Cloudflare 验证检查（调试用）

**用途**：跳过 Cloudflare 验证检查（仅用于调试，不推荐生产环境使用）。

```bash
# 跳过 Cloudflare 验证检查
SKIP_CLOUDFLARE_CHECK=true
```

**警告**：启用此选项可能导致认证失败，仅在确认目标网站没有 Cloudflare 保护时使用。

---

## 完整配置示例

### 本地开发环境（推荐配置）

```bash
# .env 文件
# Linux.do 等待时间倍增器（本地环境使用默认值 1.0 即可）
LINUXDO_WAIT_TIME_MULTIPLIER=1.5

# 如果本地有代理（可选）
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890

# TLS 指纹伪装（可选，需先安装 curl-cffi）
# ENABLE_TLS_FINGERPRINT=true
# TLS_BROWSER_TYPE=chrome131
```

### CI 环境（GitHub Actions）

```yaml
# .github/workflows/checkin.yml
env:
  # Linux.do 等待时间倍增器（CI 环境建议 2.0 或更高）
  LINUXDO_WAIT_TIME_MULTIPLIER: 2.5
  GITHUB_WAIT_TIME_MULTIPLIER: 2.0

  # CI 环境通常不需要代理
  # HTTP_PROXY: ${{ secrets.PROXY_SERVER }}
  # HTTPS_PROXY: ${{ secrets.PROXY_SERVER }}

  # TLS 指纹伪装（可选）
  # 注意：需要在 CI 环境中预安装 curl-cffi
  # ENABLE_TLS_FINGERPRINT: true
  # TLS_BROWSER_TYPE: chrome131
```

### 高难度环境（频繁被拦截）

```bash
# .env 文件
# 使用最高等待时间倍增器
LINUXDO_WAIT_TIME_MULTIPLIER=3.0
GITHUB_WAIT_TIME_MULTIPLIER=2.5

# 启用 TLS 指纹伪装
ENABLE_TLS_FINGERPRINT=true
TLS_BROWSER_TYPE=chrome131

# 配置代理（如果有）
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

---

## 降级方案优先级

### WAF Cookies 获取优先级

1. **Playwright**（默认，最可靠）
   - 使用真实浏览器获取 cookies
   - 完整的 JavaScript 执行环境
   - 支持所有反检测脚本

2. **TLS 指纹伪装**（可选，最强）
   - 模拟真实浏览器的 TLS 指纹
   - 绕过 JA3/JA4 检测
   - 需要 `ENABLE_TLS_FINGERPRINT=true` 和 `curl-cffi`

3. **Cloudscraper**（自动降级）
   - 不需要浏览器
   - 轻量级，适合服务器环境
   - 已内置在 `requirements.txt` 中

4. **空 cookies**（最终降级）
   - 不阻塞后续流程
   - 可能导致认证失败

### 触发条件

- **Playwright 失败**：网络错误、超时、页面加载失败
- **TLS 指纹伪装**：Playwright 失败 + 启用 TLS 指纹 + curl-cffi 可用
- **Cloudscraper**：Playwright 失败 + TLS 指纹失败（或未启用）

---

## 验证配置

运行以下命令验证配置是否生效：

```bash
# 1. 验证 cloudscraper 是否可用
python -c "import cloudscraper; print('cloudscraper 可用')"

# 2. 验证 TLS 指纹伪装是否可用（可选）
python -c "from utils.tls_fingerprint import TLSFingerprintHelper; print('TLS 指纹可用' if TLSFingerprintHelper.is_available() else 'TLS 指纹不可用')"

# 3. 检查环境变量
python -c "import os; print('LINUXDO_WAIT_TIME_MULTIPLIER:', os.getenv('LINUXDO_WAIT_TIME_MULTIPLIER', '1.0'))"
python -c "import os; print('ENABLE_TLS_FINGERPRINT:', os.getenv('ENABLE_TLS_FINGERPRINT', 'false'))"
```

---

## 常见问题

### Q1: 为什么建议 CI 环境使用更高的等待时间倍增器？

**A**: CI 环境通常是 headless 模式，更容易被 Cloudflare 检测。更长的等待时间可以：
- 让 Cloudflare 验证有更多时间完成
- 降低被识别为机器人的风险
- 提高认证成功率

### Q2: TLS 指纹伪装一定要用吗？

**A**: 不一定。TLS 指纹伪装是**可选**的增强功能，仅在以下情况推荐使用：
- Playwright 和 cloudscraper 都失败
- 目标网站有高级 TLS 指纹检测
- 需要最高级别的绕过能力

大多数情况下，Playwright + cloudscraper 已经足够。

### Q3: curl-cffi 安装失败怎么办？

**A**: curl-cffi 安装失败不影响基础功能，可以：
1. 忽略安装失败，使用 Playwright + cloudscraper
2. 参考官方文档安装编译依赖
3. 使用预编译轮包：`pip install curl-cffi --only-binary :all:`

### Q4: 如何确认配置生效？

**A**: 查看日志输出：
- 看到 `等待Cloudflare验证完全通过（XX秒，倍增器=YY）` 说明倍增器生效
- 看到 `检测到 Cloudflare cookies: cf_clearance, __cf_bm` 说明 cookies 检测生效
- 看到 `TLS 指纹获取成功` 说明 TLS 指纹伪装生效
- 看到 `Cloudscraper 增强成功` 说明 cloudscraper 降级生效

---

## 性能影响

| 功能 | 额外时间开销 | CPU 开销 | 内存开销 |
|------|------------|---------|---------|
| 反检测脚本 | ~100ms | 极低 | 极低 |
| Cloudflare cookies 检测 | ~50ms | 极低 | 极低 |
| 等待时间倍增器 | 可配置 | 无 | 无 |
| Cloudscraper 降级 | ~5-10s | 低 | 低 |
| TLS 指纹伪装 | ~3-8s | 低 | 低 |

**总结**：大部分优化的开销都很小，只有在降级方案触发时才会有明显的时间开销。

---

## 安全建议

1. **不要在日志中输出敏感信息**
   - cookies 值已自动隐藏
   - 密码输入已混淆

2. **代理配置**
   - 使用 GitHub Secrets 存储代理地址
   - 不要在代码中硬编码代理凭证

3. **TLS 指纹伪装**
   - 定期更新 curl-cffi 版本
   - 使用最新的浏览器类型（chrome131）

---

## 更新日志

### 2025-11-16 - v1.0

- ✅ 添加 Linux.do 特定等待时间倍增器
- ✅ 增强反检测脚本（sec-ch-ua、WebGL 一致性）
- ✅ 添加关键 Cloudflare cookies 检测
- ✅ 优化 Cloudflare 验证分段检测（45 秒）
- ✅ 增强 CloudscraperHelper（Chrome 131 请求头）
- ✅ 添加 TLS 指纹伪装支持（可选）
- ✅ 三重降级方案（Playwright → TLS → Cloudscraper）

---

**文档版本**: 1.0
**最后更新**: 2025-11-16
**适用版本**: Regular-inspection v2.0+
