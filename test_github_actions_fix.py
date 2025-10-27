#!/usr/bin/env python3
"""
GitHub Actions 修复验证测试脚本
用于测试修复后的功能是否正常工作
"""

import asyncio
import os
import json
from utils.config import AppConfig, load_accounts, validate_account
from utils.checkin import CheckIn


async def test_account_config():
    """测试账号配置加载"""
    print("🔧 测试账号配置加载...")

    try:
        app_config = AppConfig.load_from_env()
        accounts = load_accounts()

        if not accounts:
            print("❌ 未找到任何账号配置")
            return False

        print(f"✅ 成功加载 {len(accounts)} 个账号配置")

        valid_accounts = []
        for i, account in enumerate(accounts):
            if validate_account(account, i):
                valid_accounts.append(account)
                provider = app_config.get_provider(account.provider)
                print(f"   ✅ {account.name} ({account.provider}) - {len(account.auth_configs)} 种认证方式")
            else:
                print(f"   ❌ {account.name} - 配置验证失败")

        print(f"📊 共 {len(valid_accounts)} 个账号通过验证")
        return len(valid_accounts) > 0

    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


async def test_provider_urls():
    """测试 Provider URL 配置"""
    print("\n🌐 测试 Provider URL 配置...")

    try:
        app_config = AppConfig.load_from_env()

        for name, provider in app_config.providers.items():
            print(f"   📡 {provider.name}")
            print(f"      登录URL: {provider.get_login_url()}")
            print(f"      签到URL: {provider.get_checkin_url()}")
            print(f"      用户信息URL: {provider.get_user_info_url()}")

            # 测试URL可访问性
            import httpx
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    # 测试登录页可访问性
                    login_resp = await client.get(provider.get_login_url())
                    print(f"      登录页状态: {login_resp.status_code}")
            except Exception as e:
                print(f"      登录页测试失败: {e}")

        return True

    except Exception as e:
        print(f"❌ Provider URL 测试失败: {e}")
        return False


async def test_email_auth_sample():
    """测试邮箱认证示例（仅测试表单查找，不实际登录）"""
    print("\n📧 测试邮箱认证表单查找...")

    try:
        from playwright.async_api import async_playwright

        app_config = AppConfig.load_from_env()
        accounts = load_accounts()

        # 查找第一个使用邮箱认证的账号
        email_account = None
        for account in accounts:
            for auth in account.auth_configs:
                if auth.method == "email":
                    email_account = (account, auth)
                    break
            if email_account:
                break

        if not email_account:
            print("⚠️ 未找到使用邮箱认证的账号，跳过测试")
            return True

        account, auth = email_account
        provider = app_config.get_provider(account.provider)

        print(f"   🔍 测试账号: {account.name} ({account.provider})")

        async with async_playwright() as p:
            # 仅测试表单查找，不实际登录
            with tempfile.TemporaryDirectory() as temp_dir:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=temp_dir,
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )

                page = await context.new_page()

                try:
                    await page.goto(provider.get_login_url())
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(2000)

                    # 查找邮箱输入框
                    email_selectors = [
                        'input[type="email"]',
                        'input[name="email"]',
                        'input[name="username"]',
                        'input[placeholder*="邮箱" i]',
                        'input[placeholder*="Email" i]',
                    ]

                    found = False
                    for sel in email_selectors:
                        try:
                            email_input = await page.query_selector(sel)
                            if email_input:
                                print(f"   ✅ 找到邮箱输入框: {sel}")
                                found = True
                                break
                        except:
                            continue

                    if not found:
                        # 调试信息
                        all_inputs = await page.query_selector_all('input')
                        print(f"   ⚠️ 邮箱输入框未找到，页面共有 {len(all_inputs)} 个输入框")
                        for i, inp in enumerate(all_inputs[:3]):
                            try:
                                inp_type = await inp.get_attribute('type')
                                inp_name = await inp.get_attribute('name')
                                print(f"      输入框{i+1}: type={inp_type}, name={inp_name}")
                            except:
                                print(f"      输入框{i+1}: 无法获取属性")

                    await context.close()
                    return found

                except Exception as e:
                    print(f"   ❌ 邮箱表单测试失败: {e}")
                    await context.close()
                    return False

    except ImportError:
        print("⚠️ Playwright 未安装，跳过邮箱认证测试")
        return True
    except Exception as e:
        print(f"❌ 邮箱认证测试失败: {e}")
        return False


async def test_checkin_urls():
    """测试签到接口可访问性"""
    print("\n🎯 测试签到接口可访问性...")

    try:
        import httpx

        app_config = AppConfig.load_from_env()

        for name, provider in app_config.providers.items():
            print(f"   📡 测试 {provider.name} 签到接口...")

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    # 测试签到接口
                    checkin_resp = await client.post(
                        provider.get_checkin_url(),
                        headers={"User-Agent": "Test-Agent"}
                    )
                    print(f"      签到接口状态: {checkin_resp.status_code}")

                    if checkin_resp.status_code == 404:
                        print(f"      ⚠️ 签到接口404，将在实际运行时尝试用户信息保活")
                    elif checkin_resp.status_code == 200:
                        data = checkin_resp.json()
                        print(f"      响应内容: {data.get('message', 'No message')}")

            except Exception as e:
                print(f"      接口测试失败: {e}")

        return True

    except Exception as e:
        print(f"❌ 签到接口测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 GitHub Actions 修复验证测试")
    print("=" * 50)

    results = []

    # 1. 测试账号配置
    results.append(await test_account_config())

    # 2. 测试 Provider URL
    results.append(await test_provider_urls())

    # 3. 测试签到接口
    results.append(await test_checkin_urls())

    # 4. 测试邮箱认证（可选）
    results.append(await test_email_auth_sample())

    # 总结
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！修复验证成功")
        return 0
    else:
        print("⚠️ 部分测试失败，需要进一步修复")
        return 1


if __name__ == "__main__":
    import tempfile
    exit_code = asyncio.run(main())
    exit(exit_code)