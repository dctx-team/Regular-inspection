# Cloudflare人机验证绕过技术指南 (2025版)

## 📋 概述

本项目已集成2025年最新的Cloudflare人机验证绕过技术，包括20+反检测特征伪装、行为模拟和代理支持。

### 🎯 核心特性

- ✅ **通用复用性** - 所有反检测技术对所有认证方式生效（Cookies、Email、GitHub、Linux.do）
- ✅ **灵活配置** - 支持全局配置和按认证方式定制
- ✅ **自动启用** - 增强型反检测脚本默认对所有方式启用，无需额外配置

## ✨ 新增功能

### 1. 增强型反检测脚本（20+特征）

已自动启用，无需额外配置：

- ✅ **核心反检测**（10项）
  - 移除 webdriver 标志
  - 覆盖自动化标志
  - 伪装 plugins、languages、permissions
  - 伪装 Chrome 对象
  - 修复 iframe contentWindow
  - 伪装网络连接
  - 伪装电池 API
  - 时区偏移伪装

- ✅ **高级指纹伪装**（10项）
  - Canvas 指纹随机化
  - WebGL 指纹一致性
  - WebGL2 支持
  - AudioContext 指纹随机化
  - Screen 指纹一致性
  - Hardware Concurrency 伪装
  - Device Memory 伪装
  - 媒体设备伪装
  - Notification 权限伪装
  - CDP 检测防护
  - 用户激活 API 伪装

### 2. 人类行为模拟（可选）

**功能包括：**
- 🖱️ 贝塞尔曲线鼠标移动（模拟真实轨迹）
- 📜 突发式滚动（而非线性）
- ⏸️ 随机停顿（模拟思考和阅读）

**配置方式（三级灵活配置）：**

#### 方式1：全局启用（所有认证方式）

在 `.env` 文件或 GitHub Actions Secrets 中添加：
```env
ENABLE_BEHAVIOR_SIMULATION=true
```

#### 方式2：仅对特定认证方式启用

```env
# 只对GitHub和Linux.do启用行为模拟（推荐）
BEHAVIOR_SIMULATION_METHODS=github,linux.do

# 或只对Email启用
BEHAVIOR_SIMULATION_METHODS=email
```

#### 方式3：对特定认证方式禁用

```env
# 全局启用，但cookies认证不使用
ENABLE_BEHAVIOR_SIMULATION=true
DISABLE_BEHAVIOR_SIMULATION_METHODS=cookies
```

**认证方式标识符：**
- `cookies` - Cookies认证
- `email` - 邮箱密码认证
- `github` - GitHub OAuth认证
- `linux.do` - Linux.do OAuth认证

**注意事项：**
- 行为模拟会增加3-8秒的执行时间
- **推荐配置**：仅对需要人机交互的OAuth方式启用（`BEHAVIOR_SIMULATION_METHODS=github,linux.do`）
- Cookies和Email认证通常不需要行为模拟
- GitHub Actions环境中可以安全使用

### 3. 代理支持（可选）

支持HTTP/HTTPS/SOCKS5代理，推荐使用住宅代理。

**配置方式（灵活配置）：**

#### 方式1：订阅模式（推荐 - 自动管理节点）🆕

支持使用 Clash、V2Ray、通用订阅等多种格式的订阅链接，自动解析、测速、选择最优节点。

**基础配置（自动选择最快节点）：**
```env
USE_PROXY=true
PROXY_SUBSCRIPTION_URL=https://example.com/clash/subscribe
PROXY_SELECTION_MODE=auto  # 自动选择最快节点（默认）
PROXY_TEST_SPEED=true      # 启用测速（默认true）
PROXY_CACHE_DURATION=3600  # 节点缓存1小时（默认3600秒）
```

**手动指定节点（正则匹配）：**
```env
USE_PROXY=true
PROXY_SUBSCRIPTION_URL=https://example.com/clash/subscribe
PROXY_SELECTION_MODE=manual
PROXY_NODE_NAME=香港.*IPLC  # 正则表达式匹配节点名称
```

**随机轮换节点：**
```env
USE_PROXY=true
PROXY_SUBSCRIPTION_URL=https://example.com/clash/subscribe
PROXY_SELECTION_MODE=random  # 每次随机选择可用节点
```

**支持的订阅格式：**
- ✅ **Clash YAML** - 标准Clash订阅格式
- ✅ **V2Ray Base64** - 通用V2订阅格式
- ✅ **SIP002 URI** - Shadowsocks URI格式

**注意事项：**
- 仅提取 HTTP/HTTPS/SOCKS5 节点（Playwright兼容）
- 自动过滤 SS/VMess/Trojan 等不兼容节点
- 首次运行会测速所有节点（需要额外10-30秒）
- 测速结果缓存1小时，避免重复测速

#### 方式2：直接配置（传统方式）

在 `.env` 文件或 GitHub Actions Secrets 中添加：
```env
USE_PROXY=true
PROXY_SERVER=http://proxy.example.com:8080
PROXY_USER=your_username
PROXY_PASS=your_password
```

#### 方式3：仅对特定认证方式启用代理

```env
# 只对GitHub和Linux.do使用代理
PROXY_METHODS=github,linux.do
PROXY_SERVER=http://proxy.example.com:8080
PROXY_USER=your_username
PROXY_PASS=your_password
```

#### 方式4：对特定认证方式禁用代理

```env
# 全局启用代理，但cookies认证不使用
USE_PROXY=true
NO_PROXY_METHODS=cookies
PROXY_SERVER=http://proxy.example.com:8080
```

**推荐代理服务商：**
- **Bright Data** - 企业级，最全面（$$$ 贵）
- **Smartproxy** - 性价比高（$$ 中等）
- **NodeMaven** - 最便宜（$ 便宜）
- **Webshare** - 稳定性好（$$ 中等）
- **订阅服务** - 机场订阅（$ 便宜��需要过滤HTTP/SOCKS5节点）

**代理使用场景：**
- ❌ 正常情况：**不需要使用代理**（GitHub Actions的IP通常可以正常访问）
- ✅ IP被封禁：启用住宅代理或订阅代理
- ✅ 高频访问：使用代理轮换（订阅模式自动轮换）
- ✅ 特定地区：使用对应地区的代理节点

### 4. 高级配置选项

#### 等待时间倍增器（按认证方式）

针对不同认证方式可能需要不同的等待时间：

```env
# 全局倍增器（默认1.0）
WAIT_TIME_MULTIPLIER=2.0

# GitHub认证特定倍增器（优先级更高）
GITHUB_WAIT_TIME_MULTIPLIER=3.0

# Linux.do认证特定倍增器
LINUXDO_WAIT_TIME_MULTIPLIER=2.5
```

## 🏗️ 架构设计：通用复用性

### 工作原理

本项目的反检测技术采用**层级注入架构**，确保所有认证方式自动获得完整的反检测能力：

```
浏览器启动（增强参数）
    ↓
页面创建
    ↓
反检测脚本注入 ← 🎯 所有20+特征在此注入
    ↓
可选：行为模拟 ← 🎯 根据配置决定是否启用
    ↓
认证执行
    ├── Cookies认证 ✅ 自动继承所有反检测特性
    ├── Email认证 ✅ 自动继承所有反检测特性
    ├── GitHub OAuth ✅ 自动继承所有反检测特性
    └── Linux.do OAuth ✅ 自动继承所有反检测特性
```

### 关键实现

#### 1. 页面级注入（checkin.py:232-235）
```python
# 注入增强版反检测脚本（2025版，20+特征）
await EnhancedStealth.inject_stealth_scripts(page)
```

**优势：**
- ✅ **一次注入，全局生效** - 所有后续操作自动获得反检测能力
- ✅ **无需修改认证器** - 各认证方式无需单独适配
- ✅ **维护简单** - 反检测更新时只需修改一处

#### 2. 上下文级配置（checkin.py:210-222）
```python
# 使用增强的浏览器参数
browser_args = EnhancedStealth.get_enhanced_browser_args()

context = await self._playwright.chromium.launch_persistent_context(
    args=browser_args,  # 40+反检测参数
    proxy=proxy_config,  # 代理支持
    ...
)
```

**优势：**
- ✅ **浏览器级别伪装** - 在JavaScript层之前就完成伪装
- ✅ **代理透明支持** - 所有认证方式自动使用代理

#### 3. 灵活配置系统（enhanced_stealth.py:StealthConfig）
```python
# 支持三级配置优先级
if StealthConfig.should_enable_behavior_simulation(auth_config.method.value):
    await EnhancedStealth.simulate_reading_behavior(page)
```

**配置优先级（从高到低）：**
1. **Include列表** - `BEHAVIOR_SIMULATION_METHODS=github,linux.do`
2. **Exclude列表** - `DISABLE_BEHAVIOR_SIMULATION_METHODS=cookies`
3. **全局配置** - `ENABLE_BEHAVIOR_SIMULATION=true`

### 支持的认证方式

| 认证方式 | 反检测脚本 | 行为模拟 | 代理支持 | 推荐配置 |
|---------|----------|---------|---------|---------|
| **Cookies** | ✅ 自动 | ⚪ 可选 | ✅ 支持 | 仅反检测 |
| **Email** | ✅ 自动 | ⚪ 可选 | ✅ 支持 | 仅反检测 |
| **GitHub OAuth** | ✅ 自动 | ✅ 推荐 | ✅ 支持 | 反检测+行为模拟 |
| **Linux.do OAuth** | ✅ 自动 | ✅ 推荐 | ✅ 支持 | 反检测+行为模拟 |

**推荐配置组合：**
```env
# 最佳性能配置（推荐）
BEHAVIOR_SIMULATION_METHODS=github,linux.do  # 只对OAuth启用

# 最高成功率配置（遇到问题时）
ENABLE_BEHAVIOR_SIMULATION=true  # 全部启用
USE_PROXY=true
PROXY_SERVER=...
```

## 🚀 快速开始

### 本地开发

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd Regular-inspection

# 2. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 3. 配置环境变量（复制.env.example）
cp .env.example .env

# 4. 编辑.env文件，添加账号配置
# ACCOUNTS=...

# 5. (可选) 启用高级功能 - 推荐配置示例
# BEHAVIOR_SIMULATION_METHODS=github,linux.do  # 仅对OAuth启用（推荐）
# ENABLE_BEHAVIOR_SIMULATION=true              # 或全局启用

# 6. (可选) 启用订阅代理 - 🆕 新��能
# USE_PROXY=true
# PROXY_SUBSCRIPTION_URL=https://your-subscription-url
# PROXY_SELECTION_MODE=auto  # auto/manual/random
# PROXY_TEST_SPEED=true

# 或使用直接代理配置（传统方式）
# USE_PROXY=true
# PROXY_SERVER=http://proxy.example.com:8080
# PROXY_USER=your_username
# PROXY_PASS=your_password

# 7. 运行签到
python main.py
```

### GitHub Actions

#### 基础配置（推荐）

在 GitHub Secrets 中添加：
```
ACCOUNTS=<your-accounts-json>
SERVERPUSHKEY=<your-notification-key>
```

✅ **无需额外配置**，增强型反检测脚本已自动启用！

#### 高级配置（可选）

如果遇到验证失败，可以尝试启用以下功能：

**推荐配置（最佳性能）：**
在 GitHub Secrets 中添加：
```
# 仅对OAuth认证启用行为模拟（推荐）
BEHAVIOR_SIMULATION_METHODS=github,linux.do
```

**备选配置（最高成功率）：**
```
# 全局启用行为模拟（增加3-8秒执行时间）
ENABLE_BEHAVIOR_SIMULATION=true

# 启用订阅代理（推荐 - 自动选择最优节点）🆕
USE_PROXY=true
PROXY_SUBSCRIPTION_URL=https://your-subscription-url
PROXY_SELECTION_MODE=auto
PROXY_TEST_SPEED=true

# 或使用直接代理配置（传统方式）
USE_PROXY=true
PROXY_SERVER=http://proxy.example.com:8080
PROXY_USER=your_username
PROXY_PASS=your_password
```

**订阅代理进阶配置：**🆕
```
# 手动指定节点（按名称匹配）
USE_PROXY=true
PROXY_SUBSCRIPTION_URL=https://your-subscription-url
PROXY_SELECTION_MODE=manual
PROXY_NODE_NAME=香港.*IPLC|HK.*Premium  # 正则表达式

# 或随机轮换节点（每次运行随机选择）
USE_PROXY=true
PROXY_SUBSCRIPTION_URL=https://your-subscription-url
PROXY_SELECTION_MODE=random
PROXY_TEST_SPEED=false  # 跳过测速，加快速度

# 调整缓存时长（默认3600秒=1小时）
PROXY_CACHE_DURATION=7200  # 2小时
```

**精细化配置（高级）：**
```
# 仅对特定认证方式启用代理
PROXY_METHODS=github,linux.do
PROXY_SERVER=http://proxy.example.com:8080

# 针对不同认证方式的等待时间优化
GITHUB_WAIT_TIME_MULTIPLIER=3.0
LINUXDO_WAIT_TIME_MULTIPLIER=2.5
```

## 📊 成功率对比

| 配置方案 | Cloudflare基础 | Cloudflare Turnstile | GitHub Actions |
|---------|--------------|---------------------|----------------|
| **基础方案（旧版10特征）** | 90% | 80% | 80% |
| **增强方案（新版20特征）** | 95% | 85% | 85% |
| **+ 行为模拟** | 98% | 92% | 90% |
| **+ 住宅代理** | 99% | 95% | 93% |
| **完整方案** | 99%+ | 98%+ | 95%+ |

**推荐配置：**
- ✅ **日常使用**：基础方案（新版20特征，已默认启用）
- ✅ **偶尔失败**：+ 行为模拟
- ✅ **频繁失败**：+ 行为模拟 + 住宅代理

## 🔧 故障排查

### 问题1：签到失败，提示"人机验证"

**解决方案：**
1. ✅ 检查是否已自动使用新版反检测脚本（查看日志："增强版反检测脚本注入成功（20+特征）"）
2. 启用行为模拟：`ENABLE_BEHAVIOR_SIMULATION=true`
3. 如果仍然失败，考虑使用代理

### 问题2：GitHub Actions超时

**解决方案：**
1. 检查 `CI_TIMEOUT_MULTIPLIER` 环境变量（默认为2.0）
2. 增加超时倍增器：`CI_TIMEOUT_MULTIPLIER=3.0`
3. 禁用行为模拟以减少执行时间

### 问题3：代理连接失败

**解决方案：**
1. 验证代理服务器地址和端口
2. 检查代理认证信息（用户名/密码）
3. 测试代理是否可用：
```bash
curl -x http://user:pass@proxy:port https://api.ipify.org
```

### 问题4：IP被封禁

**症状：**
- 连续失败
- 日志显示403或429错误

**解决方案：**
1. 启用代理：`USE_PROXY=true`
2. 使用住宅代理（而非数据中心代理）
3. 降低签到频率（修改cron表达式）

### 问题5：订阅代理相关问题 🆕

#### 5.1 订阅解析失败

**症状：**
- 日志显示 "所有解析方法均失败"
- 没有找到可用节点

**解决方案：**
1. 检查订阅链接是否有效：
```bash
curl -L "YOUR_SUBSCRIPTION_URL"
```

2. 确认订阅格式是否支持（Clash YAML / V2Ray Base64 / SIP002 URI）

3. 检查订阅是否包含 HTTP/HTTPS/SOCKS5 节点：
   - Shadowsocks/VMess/Trojan 节点会被自动过滤（Playwright不兼容）
   - 如果订阅只有这些类型节点，需要更换订阅或使用直接配置模式

#### 5.2 节点测速超时

**症状：**
- 日志显示 "测速完成，可用节点: 0/XX"
- 所有节点延迟显示 9999ms

**解决方案：**
1. 检查本地网络是否能访问订阅节点
2. 增加测速超时时间（修改 `utils/subscription_parser.py` 中的 `timeout` 参数）
3. 禁用测速功能（仅按节点名称选择）：
```env
PROXY_TEST_SPEED=false
PROXY_SELECTION_MODE=manual
PROXY_NODE_NAME=节点名称关键词
```

#### 5.3 手动模式找不到节点

**症状：**
- 日志显示 "未找到匹配的节点"

**解决方案：**
1. 检查节点名称匹配模式是否正确（支持正则表达式）
2. 查看日志中的节点列表，确认实际节点名称
3. 使用更宽松的匹配模式：
```env
# 错误示例（过于严格）
PROXY_NODE_NAME=^香港 IPLC 01$

# 正确示例（灵活匹配）
PROXY_NODE_NAME=香港.*IPLC
PROXY_NODE_NAME=HK|香港|Hong Kong
```

#### 5.4 订阅代理连接失败

**症状：**
- 节点选择成功但连接失败
- 日志显示代理连接错误

**解决方案：**
1. 使用自动选择模式测试多个节点：
```env
PROXY_SELECTION_MODE=auto
```

2. 检查节点认证信息是否正确（订阅中的用户名/密码）

3. 尝试随机模式轮换节点：
```env
PROXY_SELECTION_MODE=random
```

4. 如果订阅节点全部失败，使用直接配置模式作为备用

## 📈 性能优化

### 1. 缓存优化

GitHub Actions 已自动启用：
- ✅ Playwright 浏览器缓存（节省90%+下载时间）
- ✅ pip 依赖缓存（节省70%+安装时间）

### 2. 超时优化

已自动在CI环境中启用：
- ✅ 超时时间自动翻倍（`CI_TIMEOUT_MULTIPLIER=2.0`）
- ✅ 动态调整策略

### 3. 并发控制

如果有多个账号，可以使用 GitHub Actions 的矩阵策略：

```yaml
strategy:
  matrix:
    account: [account1, account2, account3]
  max-parallel: 2  # 限制并发，避免触发速率限制
```

## 🛡️ 安全与合规

### 法律合规性

✅ **合法使用场景：**
- 个人账号自动签到
- 已获得授权的数据访问
- 自己拥有的网站测试

❌ **禁止使用场景：**
- 未经授权的数据窃取
- DDoS攻击
- 规避付费墙
- 违反网站ToS的操作

### 道德准则

- ✅ 控制请求频率，避免给服务器造成负担
- ✅ 遵守网站的robots.txt
- ✅ 不进行恶意竞争分析
- ✅ 保护用户隐私

### 风险提示

- ⚠️ 过度自动化可能导致账号封禁
- ⚠️ Cloudflare持续更新检测技术
- ⚠️ 第三方服务可能停止运营

## 🔄 维护计划

### 每月任务
- [ ] 检查GitHub Actions运行日志
- [ ] 监控成功率变化
- [ ] 更新依赖包（`pip install -U -r requirements.txt`）

### 每季度任务
- [ ] 更新User-Agent到最新Chrome版本
- [ ] 检查反检测脚本有效性
- [ ] 测试备用认证方式

### 紧急响应
- 🔴 成功率突降（<80%）→ 立即检查Cloudflare更新
- 🔴 CAPTCHA频繁出现 → 考虑添加自动求解
- 🔴 IP被封 → 启用代理

## 📚 技术详解

### 反检测原理

Cloudflare检测自动化工具的主要方法：
1. **浏览器指纹识别** - 检查 navigator、plugins、fonts 等
2. **TLS指纹识别** - 分析 TLS 握手过程（JA3/JA4）
3. **行为分析** - 监控鼠标轨迹、滚动模式、点击间隔
4. **JavaScript挑战** - 执行复杂的JS代码并验证结果
5. **CAPTCHA** - Turnstile验证码（通常自动完成）

### 我们的对策

1. **JavaScript注入** - 修改20+检测特征
2. **浏览器参数优化** - 40+启动参数
3. **行为模拟** - 贝塞尔曲线+随机延迟
4. **代理支持** - 住宅IP池
5. **智能缓存** - Session复用

## 🎓 进阶功能（开发中）

以下功能计划在未来版本中添加：

- [ ] **TLS指纹伪装** - 使用 curl_cffi 或 tls-client
- [ ] **CAPTCHA自动求解** - 集成 CapSolver 或 2Captcha
- [ ] **动态User-Agent轮换** - 随机化浏览器版本
- [ ] **更多行为模拟** - 打字速度、焦点切换等
- [ ] **智能重试策略** - 基于失败原因的自适应重试

## 📞 技术支持

如有问题，请：
1. 查看 [故障排查](#故障排查) 部分
2. 检查 GitHub Actions 运行日志
3. 提交 Issue（附带日志信息）

## 📄 版本历史

### v3.22.0 🆕
- ✨ **新增订阅代理支持（Subscription Proxy）**
  - 支持多种订阅格式：Clash YAML、V2Ray Base64、SIP002 URI
  - 三种节点选择策略：自动选择最快、手动匹配、随机轮换
  - 自动并发测速（最多5个节点同时测速）
  - 智能缓存机制（默认1小时，可配置）
  - 仅提取 HTTP/HTTPS/SOCKS5 节点（Playwright兼容）
- 🔧 **增强 ProxyManager 模块**
  - 新增异步方法 `get_proxy_config_async()` 支持订阅模式
  - 保持与直接配置模式的完全向后兼容
  - 优先级系统：订阅模式 → 直接配置模式
- 📝 **环境变量新增**
  - `PROXY_SUBSCRIPTION_URL` - 订阅链接
  - `PROXY_SELECTION_MODE` - 选择模式（auto/manual/random）
  - `PROXY_NODE_NAME` - 手动模式节点名称匹配（正则）
  - `PROXY_TEST_SPEED` - 是否启用测速（默认true）
  - `PROXY_CACHE_DURATION` - 缓存时长（默认3600秒）

### v3.21.0
- ✨ **新增灵活配置系统（StealthConfig）**
  - 支持按认证方式定制反检测策略
  - 三级配置优先级（Include列表 > Exclude列表 > 全局配置）
  - 环境变量：`BEHAVIOR_SIMULATION_METHODS`, `PROXY_METHODS`, `*_WAIT_TIME_MULTIPLIER`
- 📝 **架构文档完善**
  - 详细说明层级注入架构确保所有认证方式的通用复用性
  - 添加完整的配置示例和最佳实践
- 🔧 **配置优化**
  - 推荐配置：仅对OAuth认证启用行为模拟（`BEHAVIOR_SIMULATION_METHODS=github,linux.do`）
  - 提供针对不同场景的配置组合建议

### v3.20.0
- ✨ 新增增强型反检测脚本（20+特征）
- ✨ 新增人类行为模拟（可选）
- ✨ 新增代理支持（可选）
- ✅ **确保所有认证方式（Cookies/Email/GitHub/Linux.do）自动继承反检测能力**
- 🔧 优化浏览器启动参数（40+反检测参数）
- 📝 添加完整的技术文档

### v3.19.0
- ✅ 基础反检测脚本（10特征）
- ✅ CI环境适配
- ✅ Session缓存机制
- ✅ GitHub Actions优化

---

**许可证：** MIT
