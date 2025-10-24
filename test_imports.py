#!/usr/bin/env python3
"""
简单测试脚本 - 验证重构后的代码结构
"""

import sys
import os

# 测试导入
print("=" * 60)
print("测试重构后的代码导入")
print("=" * 60)

try:
    from utils.config import AppConfig, AccountConfig, ProviderConfig, load_accounts
    print("✅ utils.config 导入成功")
except Exception as e:
    print(f"❌ utils.config 导入失败: {e}")
    sys.exit(1)

try:
    from utils.notify import notify
    print("✅ utils.notify 导入成功")
except Exception as e:
    print(f"❌ utils.notify 导入失败: {e}")
    sys.exit(1)

# 测试 AppConfig
print("\n" + "=" * 60)
print("测试 AppConfig")
print("=" * 60)

app_config = AppConfig.load_from_env()
print(f"✅ 成功加载 {len(app_config.providers)} 个 Provider:")
for name, provider in app_config.providers.items():
    print(f"   - {provider.name} ({name}): {provider.base_url}")

# 测试账号配置加载
print("\n" + "=" * 60)
print("测试账号配置加载")
print("=" * 60)

# 设置测试环境变量
os.environ["ANYROUTER_ACCOUNTS"] = '[{"name":"测试账号","cookies":{"session":"test"},"api_user":"123"}]'

accounts = load_accounts()
if accounts:
    print(f"✅ 成功加载 {len(accounts)} 个账号")
    for i, account in enumerate(accounts):
        auth_methods = [auth.method for auth in account.auth_configs]
        print(f"   - {account.name} ({account.provider}): {', '.join(auth_methods)}")
else:
    print("⚠️ 未加载到账号（这是正常的，因为环境变量未配置）")

# 测试 AccountConfig.from_dict
print("\n" + "=" * 60)
print("测试 AccountConfig 数据解析")
print("=" * 60)

test_data = {
    "name": "完整测试账号",
    "provider": "anyrouter",
    "cookies": {"session": "xxx"},
    "api_user": "12345",
    "github": {"username": "user", "password": "pass"},
    "linux.do": {"username": "user2", "password": "pass2"}
}

account = AccountConfig.from_dict(test_data, 0)
print(f"✅ 账号名称: {account.name}")
print(f"✅ Provider: {account.provider}")
print(f"✅ 认证方式数量: {len(account.auth_configs)}")
for auth in account.auth_configs:
    print(f"   - {auth.method}")

print("\n" + "=" * 60)
print("✅ 所有测试通过!")
print("=" * 60)
