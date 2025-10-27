#!/usr/bin/env python3
"""
API认证调试工具
用于诊断cookies和API调用问题
"""

import asyncio
import os
import json
import httpx
from utils.config import AppConfig, load_accounts


async def debug_cookies_and_api():
    """调试cookies和API认证问题"""
    print("🔍 API认证调试工具")
    print("=" * 50)

    # 加载配置
    app_config = AppConfig.load_from_env()
    accounts = load_accounts()

    if not accounts:
        print("❌ 未找到账号配置")
        return

    # 选择第一个有认证配置的账号进行调试
    test_account = None
    test_auth = None

    for account in accounts:
        if account.auth_configs:
            test_account = account
            test_auth = account.auth_configs[0]  # 使用第一个认证方式
            break

    if not test_account:
        print("❌ 未找到有效的认证配置")
        return

    provider = app_config.get_provider(test_account.provider)
    print(f"🎯 调试账号: {test_account.name} ({test_account.provider})")
    print(f"🔧 认证方式: {test_auth.method}")
    print(f"🌐 平台URL: {provider.base_url}")

    # 模拟API调用
    await test_api_calls(provider, test_auth)


async def test_api_calls(provider, auth_config):
    """测试API调用和cookies问题"""
    print(f"\n📡 测试API调用...")

    # 模拟不同类型的cookies
    test_scenarios = [
        {
            "name": "空cookies",
            "cookies": {}
        },
        {
            "name": "模拟session cookie",
            "cookies": {
                "session": "test_session_value_12345",
                "sessionid": "test_sessionid_67890"
            }
        },
        {
            "name": "模拟JWT token",
            "cookies": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
                "auth": "Bearer test_token"
            }
        },
        {
            "name": "完整cookies集合",
            "cookies": {
                "session": "test_session_value_12345",
                "sessionid": "test_sessionid_67890",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
                "auth": "Bearer test_token",
                "user_id": "12345",
                "csrf_token": "test_csrf_abcde"
            }
        }
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": f"{provider.base_url}/",
        "Origin": provider.base_url,
    }

    # 添加API User（如果有）
    if auth_config.api_user:
        headers["New-Api-User"] = str(auth_config.api_user)
        print(f"🔑 使用API User: {auth_config.api_user}")

    for scenario in test_scenarios:
        print(f"\n🧪 测试场景: {scenario['name']}")
        print(f"🍪 Cookies数量: {len(scenario['cookies'])}")

        try:
            async with httpx.AsyncClient(
                cookies=scenario['cookies'],
                timeout=15.0,
                follow_redirects=True,
                headers=headers
            ) as client:

                # 测试用户信息API
                print(f"   📡 请求用户信息API...")
                response = await client.get(provider.get_user_info_url())
                print(f"   📊 响应状态: HTTP {response.status_code}")

                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"   ✅ API响应成功: success={data.get('success')}")
                        if data.get('success'):
                            print(f"   🎉 找到有效配置！")
                            print(f"   📋 响应数据: {json.dumps(data, indent=2)[:300]}...")
                        else:
                            print(f"   ⚠️ API返回失败: {data.get('message', '未知错误')}")
                    except:
                        print(f"   ❌ JSON解析失败")
                        print(f"   📄 响应内容: {response.text[:200]}...")

                elif response.status_code == 401:
                    print(f"   ❌ 认证失败 (401)")
                    print(f"   🔍 可能原因:")
                    print(f"      - Cookies无效或过期")
                    print(f"      - 缺少必要的认证cookie")
                    print(f"      - API User不正确")

                elif response.status_code == 403:
                    print(f"   ❌ 访问被禁止 (403)")
                    print(f"   🔍 可能原因:")
                    print(f"      - 权限不足")
                    print(f"      - API调用频率限制")

                elif response.status_code == 404:
                    print(f"   ⚠️ 接口不存在 (404)")
                    print(f"   🔍 可能原因:")
                    print(f"      - API路径不正确")
                    print(f"      - 平台已取消该接口")

                else:
                    print(f"   ❌ 其他错误: HTTP {response.status_code}")
                    print(f"   📄 响应内容: {response.text[:100]}...")

                # 测试签到API
                print(f"   📡 请求签到API...")
                checkin_response = await client.post(provider.get_checkin_url())
                print(f"   📊 签到响应: HTTP {checkin_response.status_code}")

        except Exception as e:
            print(f"   ❌ 请求异常: {e}")


async def analyze_real_cookies():
    """分析真实账号的cookies（如果有的话）"""
    print(f"\n🔍 分析真实账号配置...")

    accounts = load_accounts()
    for account in accounts[:2]:  # 只分析前2个账号
        print(f"\n📋 账号: {account.name} ({account.provider})")

        for auth in account.auth_configs:
            print(f"   🔧 认证方式: {auth.method}")

            if auth.method == "cookies" and auth.cookies:
                print(f"   🍪 配置的cookies:")
                for name, value in auth.cookies.items():
                    masked_value = value[:10] + "..." if len(value) > 10 else value
                    print(f"      {name}: {masked_value}")

                # 检查关键的认证cookie
                key_cookies = ["session", "sessionid", "token", "auth", "jwt"]
                found_keys = [name for name in key_cookies if name in auth.cookies]
                print(f"   🔑 关键认证cookies: {found_keys}")

            if auth.api_user:
                print(f"   🎫 API User: {auth.api_user}")


async def main():
    """主调试函数"""
    print("🚀 开始API认证调试...")

    # 1. 分析真实配置
    await analyze_real_cookies()

    # 2. 测试API调用
    await debug_cookies_and_api()

    print(f"\n💡 调试建议:")
    print(f"   1. 检查OAuth认证后获取的cookies是否包含session信息")
    print(f"   2. 确认API User ID是否正确配置")
    print(f"   3. 验证cookies的域名匹配性")
    print(f"   4. 检查API接口是否有变化")
    print(f"   5. 确认SSL证书和网络安全设置")


if __name__ == "__main__":
    asyncio.run(main())