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
                # 启动浏览器
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=temp_dir,
                    headless=True,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-web-security",
                        "--no-sandbox",
                    ],
                )

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
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Origin": self.provider.base_url,
                "Referer": f"{self.provider.base_url}/",
            }

            # 添加 api_user header（如果有）
            if auth_config.api_user:
                headers["New-Api-User"] = str(auth_config.api_user)

            # 可选禁用证书校验（仅用于受限环境调试）
            verify_opt = False if os.getenv("DISABLE_TLS_VERIFY") == "true" else True
            async with httpx.AsyncClient(cookies=cookies, timeout=30.0, trust_env=False, verify=verify_opt) as client:
                response = await client.post(
                    self.provider.get_checkin_url(),
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return {"success": True, "message": data.get("message", "签到成功")}
                    else:
                        return {"success": False, "message": data.get("message", "签到失败")}
                elif response.status_code == 404:
                    # 一些平台无签到接口，直接判断登录态与用户信息
                    try:
                        user_resp = await client.get(
                            self.provider.get_user_info_url(),
                            headers={"Accept": "application/json", "User-Agent": headers["User-Agent"]}
                        )
                        if user_resp.status_code == 200:
                            data = user_resp.json()
                            if data.get("success"):
                                return {"success": True, "message": "签到接口不存在，已登录"}
                    except Exception:
                        pass
                    return {"success": False, "message": "HTTP 404"}
                else:
                    return {"success": False, "message": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "message": f"请求异常: {str(e)}"}

    @retry_async(max_retries=3, delay=2, backoff=2)
    async def _get_user_info(self, cookies: Dict[str, str], auth_config: AuthConfig) -> Optional[Dict]:
        """获取用户信息和余额（带重试机制）"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }

            if auth_config.api_user:
                headers["New-Api-User"] = str(auth_config.api_user)

            verify_opt = False if os.getenv("DISABLE_TLS_VERIFY") == "true" else True
            async with httpx.AsyncClient(cookies=cookies, timeout=30.0, trust_env=False, verify=verify_opt) as client:
                response = await client.get(
                    self.provider.get_user_info_url(),
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("data"):
                        user_data = data["data"]
                        quota = user_data.get("quota", 0) / 500000  # 转换为美元
                        used_quota = user_data.get("used_quota", 0) / 500000

                        return {
                            "success": True,
                            "quota": round(quota, 2),
                            "used": round(used_quota, 2),
                            "display": f"余额: ${quota:.2f}, 已用: ${used_quota:.2f}"
                        }

            return None

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
