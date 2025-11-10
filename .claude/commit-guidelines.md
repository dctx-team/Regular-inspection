# Git 提交信息规范

## 底层要求

### ❌ 禁止内容
提交信息中**不得包含**以下内容：
- Claude 相关引用
- "Generated with Claude Code" 标识
- "Co-Authored-By: Claude" 署名
- 任何其他 AI 工具的品牌信息

### ✅ 正确格式

```
功能描述 - vX.Y.Z

## 🎯 核心改进
- 改进点1
- 改进点2

## 📋 技术细节
- 实现细节1
- 实现细节2

## 🎬 预期效果
- 效果1
- 效果2
```

### 示例

**❌ 错误示例**：
```
优化认证流程 - v1.0.0

- 改进登录逻辑
- 优化错误处理

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**✅ 正确示例**：
```
优化认证流程 - v1.0.0

## 🎯 核心改进
- 改进登录逻辑
- 优化错误处理

## 📋 技术细节
- 实现重试机制
- 增加详细日志

## 🎬 预期效果
- 提升成功率
- 更好的可观察性
```

## 自动化检查

在提交前，应检查提交信息是否符合规范：
```bash
git log -1 --format=%B | grep -i "claude\|generated with\|co-authored-by: claude"
```

如果有输出，则需要修改提交信息：
```bash
git commit --amend
```
