# CI 环境人类行为模拟功能说明

## 概述

为了提高在 CI headless 环境下的 Cloudflare 人机验证通过率，本项目新增了人类行为模拟功能。该功能会在 CI 环境下自动模拟真实用户的浏览行为，包括鼠标移动、页面滚动、逐字符打字等。

## 功能特性

### 1. 基础行为模拟
- **鼠标移动**：随机移动鼠标到不同位置，模拟用户浏览页面
- **页面滚动**：上下滚动页面，模拟阅读内容
- **阅读延迟**：在操作之间添加自然的停顿时间

### 2. 交互行为模拟
- **逐字符打字**：以人类打字速度逐字符输入文本（带随机延迟）
- **自然点击**：点击前先移动鼠标到目标元素
- **表单填写**：模拟真实的表单填写流程

### 3. 智能集成点
- **页面加载后**：自动触发行为模拟
- **Cloudflare 检测时**：在等待验证时添加额外的行为模拟
- **关键操作前**：在登录、点击按钮等操作前添加行为模拟

## 配置选项

### 环境变量控制

#### 1. `CI_ENABLE_BEHAVIOR_SIMULATION`
控制是否启用行为模拟功能。

- **默认值**：`true`（在 CI 环境下默认启用）
- **可选值**：`true` / `false`
- **示例**：
  ```bash
  export CI_ENABLE_BEHAVIOR_SIMULATION=true
  ```

#### 2. `CI_BEHAVIOR_INTENSITY`
控制行为模拟的强度级别。

- **默认值**：`medium`
- **可选值**：
  - `light`：轻度模拟（仅基本行为，最快）
  - `medium`：中度模拟（默认，平衡性能和效果）
  - `heavy`：重度模拟（更多行为和延迟，最慢但最像真人）
- **示例**：
  ```bash
  export CI_BEHAVIOR_INTENSITY=heavy
  ```

## 使用方式

### 自动启用

在 CI 环境中，行为模拟功能会自动启用，无需额外配置。只要设置了以下任一环境变量，即被视为 CI 环境：

- `CI=true`
- `GITHUB_ACTIONS=true`
- `GITLAB_CI=true`
- `CIRCLECI=true`

### 手动控制

如果需要在 CI 环境中禁用行为模拟：

```bash
export CI_ENABLE_BEHAVIOR_SIMULATION=false
```

### GitHub Actions 配置示例

```yaml
name: Auto Check-in

on:
  schedule:
    - cron: '0 0 * * *'

jobs:
  checkin:
    runs-on: ubuntu-latest
    env:
      CI_ENABLE_BEHAVIOR_SIMULATION: true  # 启用行为模拟
      CI_BEHAVIOR_INTENSITY: medium        # 中度模拟强度
    steps:
      - uses: actions/checkout@v3
      - name: Run check-in
        run: python checkin.py
```

## 代码使用示例

### 在认证器中使用

基类 `Authenticator` 已经集成了行为模拟功能，子类可以直接使用：

```python
from utils.auth.base import Authenticator

class MyAuthenticator(Authenticator):
    async def authenticate(self, page, context):
        # 使用带行为模拟的页面访问
        await self._goto_with_behavior(
            page,
            "https://example.com/login",
            wait_until="domcontentloaded"
        )

        # 使用带行为模拟的输入
        await self._simulate_human_typing(
            page,
            'input[name="email"]',
            self.auth_config.username
        )

        # 使用带行为模拟的点击
        await self._simulate_human_click(
            page,
            'button[type="submit"]'
        )
```

### 直接使用工具函数

也可以在任何地方直接使用 `human_behavior` 模块的工具函数：

```python
from utils.human_behavior import (
    simulate_human_behavior,
    simulate_page_interaction,
    simulate_typing,
    simulate_click_with_behavior,
)

# 模拟基本浏览行为
await simulate_human_behavior(page, logger)

# 模拟完整的页面交互
await simulate_page_interaction(page, logger)

# 模拟打字
await simulate_typing(page, 'input[name="username"]', "myemail@example.com", logger)

# 模拟自然点击
await simulate_click_with_behavior(page, 'button.submit', logger)
```

## 工作原理

### 行为模拟时机

1. **页面初始加载**（`_init_page_and_check_cloudflare`）
   - 访问登录页面后立即触发
   - 模拟用户查看页面内容

2. **Cloudflare 验证检测**（`_wait_for_cloudflare_challenge`）
   - 检测到 Cloudflare 验证页面时触发
   - 使用更全面的页面交互模拟

3. **密码输入**（`_fill_password`）
   - CI 环境下使用更长的随机延迟（80-160ms）
   - 非 CI 环境使用标准延迟（50-100ms）

### 行为模拟内容

#### 基础模拟（`simulate_human_behavior`）
- 2-5 次随机鼠标移动
- 向下滚动 100-500px
- 等待 0.5-1.0 秒
- 返回页面顶部

#### 完整交互（`simulate_page_interaction`）
- 3-7 次随机鼠标移动
- 2-4 次向下滚动
- 阅读停顿 1-2 秒
- 向上滚动一点
- 返回顶部

## 性能影响

### 时间开销

- **Light 模式**：每次行为模拟约增加 2-3 秒
- **Medium 模式**：每次行为模拟约增加 3-5 秒
- **Heavy 模式**：每次行为模拟约增加 5-8 秒

### 建议

- 对于时间敏感的 CI 任务：使用 `light` 模式或禁用
- 对于频繁遇到 Cloudflare 验证的场景：使用 `medium` 或 `heavy` 模式
- 默认 `medium` 模式在性能和效果之间取得了良好平衡

## 故障排除

### 问题：行为模拟没有生效

**检查清单**：
1. 确认在 CI 环境中（检查环境变量 `CI=true`）
2. 确认未禁用行为模拟（`CI_ENABLE_BEHAVIOR_SIMULATION` 不是 `false`）
3. 检查日志中是否有 "🤖 CI 环境：..." 的输出

### 问题：验证仍然失败

**可能的解决方案**：
1. 增加模拟强度：`CI_BEHAVIOR_INTENSITY=heavy`
2. 增加超时时间：调整 `TimeoutConfig` 相关配置
3. 检查是否需要其他反检测措施（User-Agent、浏览器参数等）

### 问题：CI 运行时间过长

**优化建议**：
1. 降低模拟强度：`CI_BEHAVIOR_INTENSITY=light`
2. 部分禁用：只在特定账号或服务上启用
3. 完全禁用：`CI_ENABLE_BEHAVIOR_SIMULATION=false`

## 技术细节

### 新增文件

- **`utils/human_behavior.py`**：行为模拟工具模块
  - 包含所有行为模拟函数
  - 独立模块，易于测试和维护

### 修改文件

1. **`utils/auth/base.py`**：
   - 在 `Authenticator` 类初始化中添加 `is_ci` 和 `enable_behavior_simulation` 属性
   - 新增 `_simulate_human_click()` 方法
   - 新增 `_simulate_human_typing()` 方法
   - 新增 `_goto_with_behavior()` 方法
   - 在 `_wait_for_cloudflare_challenge()` 中集成行为模拟
   - 在 `_init_page_and_check_cloudflare()` 中集成行为模拟
   - 在 `_fill_password()` 中增强 CI 环境下的延迟

2. **`utils/ci_config.py`**：
   - 新增 `should_enable_behavior_simulation()` 方法
   - 新增 `get_behavior_simulation_intensity()` 方法

### 设计原则

1. **非侵入式**：不影响非 CI 环境的正常运行
2. **可配置**：通过环境变量灵活控制
3. **容错性**：行为模拟失败不影响主流程
4. **渐进式**：可选择不同的模拟强度

## 后续改进建议

1. **动态调整**：根据验证失败次数自动调整模拟强度
2. **学习优化**：记录成功的行为模式，优化模拟策略
3. **多样化**：增加更多行为类型（如右键点击、双击等）
4. **智能识别**：自动识别需要行为模拟的场景

## 相关文档

- [Cloudflare 验证机制说明](./CLOUDFLARE_BYPASS.md)
- [CI 环境配置指南](./CI_CONFIGURATION.md)
- [认证器开发指南](./AUTH_DEVELOPMENT.md)

## 更新日志

- **2025-01-XX**：初始版本，添加基础行为模拟功能
- 支持鼠标移动、页面滚动、逐字符打字
- 集成到 `Authenticator` 基类
- 添加可配置的开关和强度控制
