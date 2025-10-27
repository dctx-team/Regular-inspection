#!/usr/bin/env python3
"""
修复验证测试脚本
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import AppConfig, load_accounts, validate_account
from utils.validator import validate_account_config, validate_environment_variables, print_validation_summary


def test_config_validation():
    """测试配置验证功能"""
    print("🧪 测试配置验证功能...")

    # 验证环境变量
    env_result = validate_environment_variables()
    print_validation_summary(env_result)

    # 加载并验证账号配置
    accounts = load_accounts()
    if accounts:
        print(f"\n📝 验证 {len(accounts)} 个账号配置...")
        for i, account in enumerate(accounts):
            errors = validate_account_config(account)
            if errors:
                print(f"❌ 账号 {i+1} ({account.name}) 验证失败:")
                for error in errors:
                    print(f"   - {error}")
            else:
                print(f"✅ 账号 {i+1} ({account.name}) 验证通过")
    else:
        print("⚠️ 未找到任何账号配置")

    return len(env_result["errors"]) == 0 and (accounts is not None)


def test_provider_config():
    """测试 Provider 配置"""
    print("\n🧪 测试 Provider 配置...")

    try:
        app_config = AppConfig.load_from_env()
        print(f"✅ 成功加载 {len(app_config.providers)} 个 Provider:")

        for name, provider in app_config.providers.items():
            print(f"   - {provider.name} ({name})")
            print(f"     登录URL: {provider.login_url}")
            print(f"     签到URL: {provider.checkin_url}")
            print(f"     用户信息URL: {provider.user_info_url}")

        return True

    except Exception as e:
        print(f"❌ Provider 配置测试失败: {e}")
        return False


def test_2fa_support():
    """测试 2FA 支持配置"""
    print("\n🧪 测试 2FA 支持配置...")

    two_fa_vars = {
        "GITHUB_2FA_CODE": os.getenv("GITHUB_2FA_CODE"),
        "GITHUB_TOTP_SECRET": os.getenv("GITHUB_TOTP_SECRET"),
        "GITHUB_RECOVERY_CODES": os.getenv("GITHUB_RECOVERY_CODES")
    }

    configured = [name for name, value in two_fa_vars.items() if value]

    if configured:
        print(f"✅ 已配置 {len(configured)} 种 2FA 方式:")
        for var_name in configured:
            print(f"   - {var_name}")
        return True
    else:
        print("⚠️ 未配置任何 2FA 方式（GitHub 账号如启用 2FA 将需要）")
        return False


def test_imports():
    """测试模块导入"""
    print("\n🧪 测试模块导入...")

    try:
        # 测试核心模块导入
        from utils.config import AppConfig, AccountConfig, AuthConfig
        from utils.auth import get_authenticator, GitHubAuthenticator, EmailAuthenticator
        from utils.logger import get_account_logger, setup_logger
        from utils.validator import validate_account_config
        from checkin import CheckIn

        print("✅ 所有核心模块导入成功")

        # 测试可选依赖
        try:
            import pyotp
            print("✅ pyotp 模块可用（支持 TOTP 2FA）")
        except ImportError:
            print("⚠️ pyotp 模块未安装（TOTP 2FA 功能不可用）")
            print("   安装命令: pip install pyotp")

        return True

    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def test_authenticators():
    """测试认证器实例化"""
    print("\n🧪 测试认证器实例化...")

    try:
        from utils.config import AuthConfig, ProviderConfig
        from utils.auth import get_authenticator

        # 创建测试配置
        provider = ProviderConfig(
            name="Test",
            base_url="https://example.com",
            login_url="https://example.com/login",
            checkin_url="https://example.com/api/checkin",
            user_info_url="https://example.com/api/user"
        )

        # 测试各种认证器
        auth_configs = [
            AuthConfig(method="cookies", cookies={"session": "test"}, api_user="123"),
            AuthConfig(method="email", username="test@example.com", password="password"),
            AuthConfig(method="github", username="test", password="password"),
            AuthConfig(method="linux.do", username="test", password="password")
        ]

        for auth_config in auth_configs:
            authenticator = get_authenticator(auth_config, provider)
            print(f"✅ {auth_config.method} 认证器创建成功")

        return True

    except Exception as e:
        print(f"❌ 认证器测试失败: {e}")
        return False


async def test_retry_decorator():
    """测试重试装饰器"""
    print("\n🧪 测试重试装饰器...")

    try:
        from checkin import retry_async
        import time

        attempt_count = 0

        @retry_async(max_retries=3, delay=1)
        async def failing_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception(f"模拟失败 {attempt_count}")
            return "成功"

        start_time = time.time()
        result = await failing_function()
        end_time = time.time()

        print(f"✅ 重试装饰器测试成功")
        print(f"   总尝试次数: {attempt_count}")
        print(f"   最终结果: {result}")
        print(f"   耗时: {end_time - start_time:.2f} 秒")

        return True

    except Exception as e:
        print(f"❌ 重试装饰器测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 开始修复验证测试")
    print("=" * 60)

    tests = [
        ("模块导入", test_imports),
        ("配置验证", test_config_validation),
        ("Provider 配置", test_provider_config),
        ("认证器实例化", test_authenticators),
        ("2FA 支持", test_2fa_support),
    ]

    # 同步测试
    sync_results = []
    for test_name, test_func in tests:
        print(f"\n🔄 运行测试: {test_name}")
        try:
            result = test_func()
            sync_results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试 '{test_name}' 异常: {e}")
            sync_results.append((test_name, False))

    # 异步测试
    print(f"\n🔄 运行测试: 重试装饰器")
    try:
        async_result = asyncio.run(test_retry_decorator())
        sync_results.append(("重试装饰器", async_result))
    except Exception as e:
        print(f"❌ 测试 '重试装饰器' 异常: {e}")
        sync_results.append(("重试装饰器", False))

    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    passed = 0
    total = len(sync_results)

    for test_name, result in sync_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {test_name}")
        if result:
            passed += 1

    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")

    if passed == total:
        print("🎉 所有测试通过！修复验证成功")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查相关配置")
        return 1


if __name__ == "__main__":
    sys.exit(main())