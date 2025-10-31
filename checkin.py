#!/usr/bin/env python3
"""
签到核心模块 - 重构版
支持多种认证方式和多平台
"""

import asyncio
import hashlib
import json
import os
import tempfile
from typing import Dict, List, Tuple, Optional
from functools import wraps

import httpx
from playwright.async_api import async_playwright, Page, BrowserContext

from utils.config import AccountConfig, ProviderConfig, AuthConfig
from utils.auth import get_authenticator


def retry_async(max_retries=3, delay=2, backoff=2):
    """异步重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        print(f"❌ 重试 {max_retries} 次后仍然失败: {e}")
                        raise e
                    wait_time = delay * (backoff ** attempt)
                    print(f"⚠️ 尝试 {attempt + 1}/{max_retries} 失败，{wait_time}秒后重试: {e}")
                    await asyncio.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator


class CheckIn:
    """统一的签到管理类"""

    def __init__(self, account: AccountConfig, provider: ProviderConfig):
        self.account = account
        self.provider = provider
        self.balance_data_file = "balance_data.json"

    async def execute(self) -> List[Tuple[str, bool, Optional[Dict]]]:
        """
        执行签到流程

        Returns:
            List[(auth_method, success, user_info)]
        """
        results = []

        # 尝试所有配置的认证方式
        for auth_config in self.account.auth_configs:
            print(f"\n{'='*60}")
            print(f"📝 [{self.account.name}] 尝试使用 {auth_config.method} 认证")
            print(f"{'='*60}")

            try:
                success, user_info = await self._checkin_with_auth(auth_config)
                results.append((auth_config.method, success, user_info))

                if success:
                    print(f"✅ [{self.account.name}] {auth_config.method} 认证成功")
                else:
                    error_msg = user_info.get("error", "Unknown error") if user_info else "Unknown error"
                    print(f"❌ [{self.account.name}] {auth_config.method} 认证失败: {error_msg}")

            except Exception as e:
                print(f"❌ [{self.account.name}] {auth_config.method} 异常: {str(e)}")
                results.append((auth_config.method, False, {"error": str(e)}))

        return results

    async def _checkin_with_auth(self, auth_config: AuthConfig) -> Tuple[bool, Optional[Dict]]:
        """使用指定的认证方式进行签到"""

        async with async_playwright() as p:
            with tempfile.TemporaryDirectory() as temp_dir:
                # 启动浏览器（智能选择启动方式）
                context = None
                browser_strategies = [
                    # 策略1: 尝试使用系统Chrome（本地环境）
                    {
                        "name": "系统Chrome",
                        "executable": "/usr/bin/google-chrome",
                        "headless": True,
                    },
                    # 策略2: 尝试使用Playwright内置浏览器（CI环境）
                    {
                        "name": "Playwright内置浏览器",
                        "executable": None,
                        "headless": True,
                    },
                    # 策略3: 尝试使用chromium
                    {
                        "name": "chromium",
                        "executable": "/usr/bin/chromium-browser",
                        "headless": True,
                    },
                ]

                for strategy in browser_strategies:
                    try:
                        print(f"🔄 尝试使用 {strategy['name']} 启动浏览器...")

                        launch_config = {
                            "user_data_dir": temp_dir,
                            "headless": strategy["headless"],
                            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                            "viewport": {"width": 1920, "height": 1080},
                            "args": [
                                "--disable-blink-features=AutomationControlled",
                                "--disable-dev-shm-usage",
                                "--disable-web-security",
                                "--no-sandbox",
                                "--disable-gpu",
                                "--disable-extensions",
                                "--no-proxy-server",  # 完全禁用代理
                                "--disable-background-networking",
                                "--disable-ntp-network-feature",
                                "--disable-default-apps",
                                "--disable-sync",
                                "--disable-background-timer-throttling",
                                "--disable-renderer-backgrounding",
                                "--disable-backgrounding-occluded-windows",
                                "--disable-component-extensions-with-background-pages",
                                "--disable-background-extensions",
                                "--disable-ipc-flooding-protection",
                                "--disable-logging",  # 禁用日志以减少CI噪音
                                "--silent",  # 静默模式
                            ],
                        }

                        if strategy["executable"]:
                            launch_config["executable_path"] = strategy["executable"]

                        context = await p.chromium.launch_persistent_context(**launch_config)
                        print(f"✅ {strategy['name']} 启动成功")
                        break

                    except Exception as e:
                        print(f"⚠️ {strategy['name']} 启动失败: {str(e)[:100]}...")
                        continue

                if not context:
                    raise Exception("所有浏览器启动策略都失败了")

                page = await context.new_page()

                try:
                    # 步骤 1: 获取 WAF cookies
                    waf_cookies = await self._get_waf_cookies(page, context)
                    if not waf_cookies:
                        print(f"⚠️ [{self.account.name}] 未获取到 WAF cookies，继续尝试")

                    # 步骤 2: 执行认证
                    authenticator = get_authenticator(auth_config, self.provider)
                    auth_result = await authenticator.authenticate(page, context)

                    if not auth_result["success"]:
                        return False, {"error": auth_result.get("error", "Authentication failed")}

                    # 获取认证后的 cookies
                    auth_cookies = auth_result.get("cookies", {})
                    print(f"✅ [{self.account.name}] 认证成功，获取到 cookies")

                    # 步骤 3: 执行签到
                    checkin_result = await self._do_checkin(auth_cookies, auth_config)
                    if not checkin_result["success"]:
                        return False, {"error": checkin_result.get("message", "Check-in failed")}

                    print(f"✅ [{self.account.name}] 签到成功: {checkin_result.get('message', '')}")

                    # 步骤 4: 获取用户信息和余额
                    user_info = await self._get_user_info(auth_cookies, auth_config)
                    if user_info and user_info.get("success"):
                        # 计算余额变化
                        balance_change = self._calculate_balance_change(
                            self.account.name,
                            auth_config.method,
                            user_info
                        )
                        user_info["balance_change"] = balance_change

                        # 保存余额数据
                        self._save_balance_data(self.account.name, auth_config.method, user_info)

                        return True, user_info
                    else:
                        return True, {"success": True, "message": "Check-in successful but failed to get user info"}

                except Exception as e:
                    return False, {"error": f"Exception during check-in: {str(e)}"}

                finally:
                    await page.close()
                    await context.close()

    async def _get_waf_cookies(self, page: Page, context: BrowserContext) -> Dict[str, str]:
        """获取 WAF cookies"""
        try:
            print(f"ℹ️ [{self.account.name}] 正在获取 WAF cookies...")

            # 访问登录页面以触发 WAF
            await page.goto(self.provider.get_login_url(), wait_until="domcontentloaded", timeout=20000)

            # 等待页面加载
            try:
                await page.wait_for_function('document.readyState === "complete"', timeout=5000)
            except:
                await page.wait_for_timeout(3000)

            # 提取 WAF cookies
            cookies = await context.cookies()
            waf_cookies = {}
            for cookie in cookies:
                if cookie["name"] in ["acw_tc", "cdn_sec_tc", "acw_sc__v2"]:
                    waf_cookies[cookie["name"]] = cookie["value"]

            if waf_cookies:
                print(f"✅ [{self.account.name}] 获取到 {len(waf_cookies)} 个 WAF cookies")
            else:
                print(f"⚠️ [{self.account.name}] 未获取到 WAF cookies")

            return waf_cookies

        except Exception as e:
            print(f"⚠️ [{self.account.name}] 获取 WAF cookies 失败: {str(e)}")
            return {}

    @retry_async(max_retries=3, delay=2, backoff=2)
    async def _do_checkin(self, cookies: Dict[str, str], auth_config: AuthConfig) -> Dict:
        """执行签到请求（带重试机制）"""
        try:
            print(f"📡 [{self.account.name}] 开始签到请求...")
            print(f"🍪 [{self.account.name}] 输入cookies数量: {len(cookies)}")

            # 检查关键cookies
            key_cookies = ["session", "sessionid", "token", "auth", "jwt"]
            found_key_cookies = []
            for cookie_name in key_cookies:
                if cookie_name in cookies:
                    found_key_cookies.append(cookie_name)
                    print(f"   ✅ 找到关键cookie: {cookie_name}")

            if not found_key_cookies:
                print(f"   ⚠️ 未找到标准认证cookie，尝试所有可用cookies")
                # 列出所有cookies用于调试
                for cookie_name in list(cookies.keys())[:5]:
                    print(f"   📄 可用cookie: {cookie_name}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Origin": self.provider.base_url,
                "Referer": f"{self.provider.base_url}/",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }

            # 添加API User头（如果存在或可以推断）
            api_user = auth_config.api_user

            # 如果没有配置API User，尝试从账号名称推断
            if not api_user:
                import re
                numbers = re.findall(r'\d+', self.account.name)
                if numbers:
                    api_user = numbers[0]
                    print(f"🔍 [{self.account.name}] 从账号名称推断API User: {api_user}")
                else:
                    api_user = self.account.name.replace("-", "_").replace(".", "")
                    print(f"🔍 [{self.account.name}] 使用账号名作为API User: {api_user}")

            if api_user:
                headers["New-Api-User"] = str(api_user)
                print(f"🔑 [{self.account.name}] 使用签到API User: {api_user}")
            else:
                print(f"⚠️ [{self.account.name}] 签到无法确定API User")

            # SSL验证配置
            verify_opt = False if os.getenv("DISABLE_TLS_VERIFY") == "true" else True

            print(f"🎯 [{self.account.name}] 请求URL: {self.provider.get_checkin_url()}")
            print(f"🔧 [{self.account.name}] SSL验证: {'禁用' if not verify_opt else '启用'}")

            # 创建HTTP客户端，增强配置
            async with httpx.AsyncClient(
                cookies=cookies,
                timeout=30.0,
                trust_env=False,
                verify=verify_opt,
                follow_redirects=True,
                headers=headers
            ) as client:

                print(f"📤 [{self.account.name}] 发送POST请求...")
                response = await client.post(self.provider.get_checkin_url())

                print(f"📊 [{self.account.name}] 签到响应: HTTP {response.status_code}")

                # 检查响应头
                response_headers = dict(response.headers)
                if 'set-cookie' in response_headers:
                    print(f"🍪 [{self.account.name}] 响应包含新cookies: {response_headers['set-cookie'][:100]}...")

                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"📋 [{self.account.name}] 签到API响应: success={data.get('success')}")

                        if data.get("success"):
                            return {"success": True, "message": data.get("message", "签到成功")}
                        else:
                            error_msg = data.get("message", "签到失败")
                            print(f"❌ [{self.account.name}] 签到失败: {error_msg}")
                            return {"success": False, "message": error_msg}
                    except Exception as e:
                        print(f"❌ [{self.account.name}] 解析签到响应失败: {e}")
                        print(f"📄 [{self.account.name}] 原始响应: {response.text[:200]}...")
                        # 检查是否是HTML响应（可能是登录页面跳转）
                        if "html" in response.headers.get("content-type", "").lower():
                            print(f"🔄 [{self.account.name}] 检测到HTML响应，可能需要重新登录")
                        return {"success": False, "message": "响应解析失败"}

                elif response.status_code == 401:
                    print(f"❌ [{self.account.name}] 签到认证失败 (401)")
                    print(f"🔍 [{self.account.name}] 检查cookies有效性...")

                    # 详细诊断401错误
                    for cookie_name in key_cookies:
                        if cookie_name in cookies:
                            cookie_value = cookies[cookie_name]
                            print(f"   🍪 {cookie_name}: {cookie_value[:20]}...")
                        else:
                            print(f"   ❌ 缺少 {cookie_name} cookie")

                    # 尝试获取当前页面信息
                    try:
                        page_response = await client.get(self.provider.base_url)
                        if "login" in page_response.text.lower():
                            print(f"🔄 [{self.account.name}] 检测到需要重新登录")
                        return {"success": False, "message": "认证已过期，需要重新登录"}
                    except:
                        pass

                elif response.status_code == 403:
                    print(f"❌ [{self.account.name}] 访问被禁止 (403) - 权限不足")
                    return {"success": False, "message": "访问被禁止"}

                elif response.status_code == 404:
                    print(f"🔍 [{self.account.name}] 签到接口返回404，尝试查询用户信息进行保活...")
                    # 一些平台无签到接口，直接判断登录态与用户信息
                    try:
                        user_resp = await client.get(
                            self.provider.get_user_info_url(),
                            headers={"Accept": "application/json", "User-Agent": headers["User-Agent"]}
                        )
                        if user_resp.status_code == 200:
                            data = user_resp.json()
                            if data.get("success"):
                                print(f"✅ [{self.account.name}] 用户信息查询成功，账号已保活")
                                return {"success": True, "message": "签到接口不存在，但账号状态正常"}
                            else:
                                print(f"⚠️ [{self.account.name}] 用户信息查询失败: {data.get('message', 'Unknown error')}")
                        else:
                            print(f"⚠️ [{self.account.name}] 用户信息接口返回 {user_resp.status_code}")
                    except Exception as e:
                        print(f"⚠️ [{self.account.name}] 用户信息查询异常: {e}")

                    print(f"❌ [{self.account.name}] 签到接口和用户信息查询都失败")
                    return {"success": False, "message": f"签到接口404，用户信息查询也失败"}

                else:
                    print(f"❌ [{self.account.name}] 签到请求失败: HTTP {response.status_code}")
                    print(f"📄 [{self.account.name}] 响应内容: {response.text[:100]}...")
                    return {"success": False, "message": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "message": f"请求异常: {str(e)}"}

    def _expand_cookies_domain(self, cookies: Dict[str, str]) -> Dict[str, str]:
        """扩展cookies域名匹配"""
        expanded_cookies = {}
        for name, value in cookies.items():
            expanded_cookies[name] = value
            # 为不同域名变体添加cookies
            if self.provider.base_url:
                domain = self.provider.base_url.replace("https://", "").replace("http://", "").split("/")[0]
                expanded_cookies[f"{name}"] = value

        return expanded_cookies

    def _create_subdomain_cookies(self, cookies: Dict[str, str]) -> Dict[str, str]:
        """创建子域名cookies"""
        subdomain_cookies = {}
        for name, value in cookies.items():
            subdomain_cookies[name] = value
            # 为根域名和子域名创建cookies
            subdomain_cookies[name] = value

        return subdomain_cookies

    @retry_async(max_retries=3, delay=2, backoff=2)
    async def _get_user_info(self, cookies: Dict[str, str], auth_config: AuthConfig) -> Optional[Dict]:
        """获取用户信息和余额（带重试机制）"""
        try:
            print(f"📡 [{self.account.name}] 开始用户信息查询...")
            print(f"🍪 [{self.account.name}] 输入cookies数量: {len(cookies)}")

            # 检查关键cookies
            key_cookies = ["session", "sessionid", "token", "auth", "jwt"]
            found_key_cookies = []
            for cookie_name in key_cookies:
                if cookie_name in cookies:
                    found_key_cookies.append(cookie_name)
                    print(f"   ✅ 找到关键cookie: {cookie_name}")

            if not found_key_cookies:
                print(f"   ⚠️ 未找到标准认证cookie，列出所有cookies:")
                for cookie_name in list(cookies.keys())[:5]:
                    print(f"   📄 可用cookie: {cookie_name}")

            # 更完整的请求头设置
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": f"{self.provider.base_url}/",
                "Origin": self.provider.base_url,
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "X-Requested-With": "XMLHttpRequest"
            }

            # 添加API User头（如果存在或可以推断）
            api_user = auth_config.api_user

            # 如果没有配置API User，尝试从账号名称推断（适用于某些平台）
            if not api_user:
                # 尝试从账号名称提取数字ID
                import re
                numbers = re.findall(r'\d+', self.account.name)
                if numbers:
                    api_user = numbers[0]  # 使用第一个找到的数字
                    print(f"🔍 [{self.account.name}] 从账号名称推断API User: {api_user}")
                else:
                    # 使用账号名称作为备用方案
                    api_user = self.account.name.replace("-", "_").replace(".", "")
                    print(f"🔍 [{self.account.name}] 使用账号名作为API User: {api_user}")

            if api_user:
                headers["New-Api-User"] = str(api_user)
                print(f"🔑 [{self.account.name}] 使用API User: {api_user}")
            else:
                print(f"⚠️ [{self.account.name}] 无法确定API User")

            # SSL验证配置
            verify_opt = False if os.getenv("DISABLE_TLS_VERIFY") == "true" else True

            print(f"🎯 [{self.account.name}] 请求URL: {self.provider.get_user_info_url()}")

            # 尝试不同的cookies策略
            cookie_strategies = [
                ("原始cookies", cookies),
                ("扩展域名cookies", self._expand_cookies_domain(cookies)),
                ("子域名cookies", self._create_subdomain_cookies(cookies)),
            ]

            for strategy_name, strategy_cookies in cookie_strategies:
                print(f"🔄 [{self.account.name}] 尝试策略: {strategy_name}")
                print(f"   🍪 使用cookies数量: {len(strategy_cookies)}")

                try:
                    # 创建HTTP客户端
                    async with httpx.AsyncClient(
                        cookies=strategy_cookies,
                        timeout=30.0,
                        trust_env=False,
                        verify=verify_opt,
                        follow_redirects=True,
                        headers=headers
                    ) as client:

                        response = await client.get(self.provider.get_user_info_url())
                        print(f"   📊 用户信息响应: HTTP {response.status_code}")

                        if response.status_code == 200:
                            try:
                                data = response.json()
                                print(f"   📋 API响应: success={data.get('success')}")

                                if data.get("success") and data.get("data"):
                                    user_data = data["data"]
                                    quota = user_data.get("quota", 0) / 500000  # 转换为美元
                                    used_quota = user_data.get("used_quota", 0) / 500000

                                    print(f"   ✅ [{self.account.name}] 用户信息获取成功!")
                                    return {
                                        "success": True,
                                        "quota": round(quota, 2),
                                        "used": round(used_quota, 2),
                                        "display": f"余额: ${quota:.2f}, 已用: ${used_quota:.2f}"
                                    }
                                else:
                                    error_msg = data.get("message", "未知错误")
                                    print(f"   ❌ API返回失败: {error_msg}")
                            except Exception as e:
                                print(f"   ❌ 解析响应失败: {e}")
                                print(f"   📄 原始响应: {response.text[:200]}...")

                        elif response.status_code == 401:
                            print(f"   ❌ 认证失败 (401) - {strategy_name}失败")
                            # 继续尝试下一个策略

                        elif response.status_code == 403:
                            print(f"   ❌ 访问被禁止 (403)")
                            return None

                        elif response.status_code == 404:
                            print(f"   ⚠️ 用户信息接口不存在 (404)")
                            return None

                        else:
                            print(f"   ❌ HTTP错误: {response.status_code}")
                            print(f"   📄 响应内容: {response.text[:100]}...")

                except Exception as e:
                    print(f"   ❌ {strategy_name} 请求异常: {e}")
                    continue

            # 所有策略都失败
            print(f"   💥 [{self.account.name}] 所有cookies策略都失败了")

        except Exception as e:
            print(f"⚠️ [{self.account.name}] 获取用户信息失败: {str(e)}")
            return None

    def _calculate_balance_change(self, account_name: str, auth_method: str, current_info: Dict) -> Dict:
        """计算余额变化"""
        change = {
            "recharge": 0,
            "used_change": 0,
            "quota_change": 0
        }

        try:
            # 读取历史余额数据
            if os.path.exists(self.balance_data_file):
                with open(self.balance_data_file, "r", encoding="utf-8") as f:
                    history_data = json.load(f)

                # 查找历史记录
                key = f"{account_name}_{auth_method}"
                if key in history_data:
                    old_info = history_data[key]
                    old_quota = old_info.get("quota", 0)
                    old_used = old_info.get("used", 0)

                    current_quota = current_info.get("quota", 0)
                    current_used = current_info.get("used", 0)

                    # 计算变化
                    total_change = (current_quota + current_used) - (old_quota + old_used)
                    used_change = current_used - old_used
                    quota_change = current_quota - old_quota

                    change["recharge"] = round(total_change, 2)
                    change["used_change"] = round(used_change, 2)
                    change["quota_change"] = round(quota_change, 2)

        except Exception as e:
            print(f"⚠️ 计算余额变化失败: {str(e)}")

        return change

    def _save_balance_data(self, account_name: str, auth_method: str, current_info: Dict):
        """保存余额数据"""
        try:
            # 读取现有数据
            data = {}
            if os.path.exists(self.balance_data_file):
                with open(self.balance_data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

            # 更新数据
            key = f"{account_name}_{auth_method}"
            data[key] = {
                "quota": current_info.get("quota", 0),
                "used": current_info.get("used", 0),
                "timestamp": __import__("time").time()
            }

            # 保存
            with open(self.balance_data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"⚠️ 保存余额数据失败: {str(e)}")
