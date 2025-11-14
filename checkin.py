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
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple, Optional, Any
from functools import wraps

import httpx
from playwright.async_api import async_playwright, Page, BrowserContext

from utils.config import AccountConfig, ProviderConfig, AuthConfig
from utils.auth import get_authenticator
from utils.auth_method import AuthMethod
from utils.logger import setup_logger
from utils.session_cache import SessionCache
from utils.ci_config import CIConfig
from utils.constants import (
    DEFAULT_USER_AGENT,
    BROWSER_USER_AGENT,
    KEY_COOKIE_NAMES,
    BROWSER_LAUNCH_ARGS,
    BROWSER_VIEWPORT,
    HTTP_TIMEOUT,
    BROWSER_PAGE_LOAD_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_RETRY_BACKOFF,
    QUOTA_TO_DOLLAR_RATE,
    WAF_COOKIE_NAMES,
    RATE_LIMIT_DELAY_MIN,
    RATE_LIMIT_DELAY_MAX,
)
from utils.enhanced_stealth import EnhancedStealth, ProxyManager, StealthConfig


def performance_monitor(func):
    """性能监控装饰器 - 追踪函数执行时间"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger = setup_logger(__name__)
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"⏱️ {func.__name__} 执行时间: {duration:.2f}秒")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ {func.__name__} 失败 (耗时 {duration:.2f}秒): {e}")
            raise
    return wrapper


def retry_async(max_retries=DEFAULT_MAX_RETRIES, delay=DEFAULT_RETRY_DELAY, backoff=DEFAULT_RETRY_BACKOFF):
    """异步重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = setup_logger(__name__)
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        logger.error(f"❌ 重试 {max_retries} 次后仍然失败: {e}")
                        raise e
                    wait_time = delay * (backoff ** attempt)
                    logger.warning(f"⚠️ 尝试 {attempt + 1}/{max_retries} 失败，{wait_time}秒后重试: {e}")
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
        self.logger = setup_logger(__name__)
        self._playwright = None
        self.session_cache = SessionCache()  # 添加会话缓存实例

    async def __aenter__(self):
        """进入上下文时初始化浏览器"""
        self.logger.info(f"🚀 [{self.account.name}] 初始化浏览器实例...")
        self._playwright = await async_playwright().start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时清理浏览器资源"""
        if self._playwright:
            try:
                await self._playwright.stop()
                self.logger.info(f"🔒 [{self.account.name}] Playwright已停止")
            except Exception as e:
                self.logger.warning(f"⚠️ [{self.account.name}] 停止Playwright时出现警告: {e}")
        return False

    def _build_request_headers(self, api_user: Optional[str] = None) -> Dict[str, str]:
        """构建统一的HTTP请求头"""
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": self.provider.base_url,
            "Referer": f"{self.provider.base_url}/",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if api_user:
            headers["New-Api-User"] = str(api_user)
        return headers

    async def execute(self) -> List[Tuple[str, bool, Optional[Dict[str, Any]]]]:
        """
        执行签到流程

        Returns:
            List[(auth_method, success, user_info)]
        """
        results = []

        # 尝试所有配置的认证方式
        for auth_config in self.account.auth_configs:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"📝 [{self.account.name}] 尝试使用 {auth_config.method.display_name} 认证")
            self.logger.info(f"{'='*60}")

            try:
                success, user_info = await self._checkin_with_auth(auth_config)
                results.append((auth_config.method.value, success, user_info))

                if success:
                    self.logger.info(f"✅ [{self.account.name}] {auth_config.method.display_name} 认证成功")
                else:
                    error_msg = user_info.get("error", "Unknown error") if user_info else "Unknown error"
                    self.logger.error(f"❌ [{self.account.name}] {auth_config.method.display_name} 认证失败: {error_msg}")

            except Exception as e:
                self.logger.error(f"❌ [{self.account.name}] {auth_config.method.display_name} 异常: {str(e)}")
                results.append((auth_config.method.value, False, {"error": str(e)}))

        return results

    async def _checkin_with_auth(self, auth_config: AuthConfig) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """使用指定的认证方式进行签到"""
        # OAuth 缓存降级逻辑已经在 OAuthWithCookieFallback 和各个 Authenticator 内部处理
        # 这里不再重复实现缓存检查，直接使用认证器的 authenticate 方法

        # 使用 CIConfig 统一检测 CI 环境
        is_ci = CIConfig.is_ci_environment()

        # 在CI环境中，如果是需要人机验证的方式，提前警告并可能跳过
        if is_ci and auth_config.method.requires_human_verification:
            # 使用 CIConfig 检查是否应该跳过此认证方式
            if CIConfig.should_skip_auth_method(auth_config.method.value):
                self.logger.warning(f"⚠️ [{self.account.name}] CI环境跳过 {auth_config.method.value} 认证（通过 CI_DISABLED_AUTH_METHODS 配置）")
                return False, {"error": f"{auth_config.method.value} skipped in CI (CI_DISABLED_AUTH_METHODS)"}
            else:
                self.logger.warning(f"⚠️ [{self.account.name}] CI环境中的 {auth_config.method.value} 认证可能失败（需要人机验证）")
        
        # 为每次认证创建独立的临时目录和浏览器上下文
        with tempfile.TemporaryDirectory() as temp_dir:
            # 对于需要人机验证的登录方式（GitHub、Linux.do），使用非headless模式
            # 但在 CI 环境中必须使用 headless 模式
            needs_human_verification = auth_config.method.requires_human_verification

            if is_ci:
                headless_mode = True
                self.logger.info(f"ℹ️ [{self.account.name}] 检测到 CI 环境，强制使用 headless 模式")
            else:
                headless_mode = not needs_human_verification
                # 如果环境变量强制指定，则覆盖默认设置
                force_non_headless = os.getenv("FORCE_NON_HEADLESS", "false").lower() == "true"
                if force_non_headless:
                    headless_mode = False
                    self.logger.info(f"ℹ️ [{self.account.name}] 强制使用非headless模式（FORCE_NON_HEADLESS=true）")
                elif needs_human_verification:
                    self.logger.info(f"ℹ️ [{self.account.name}] {auth_config.method.value} 认证使用非headless模式")
            
            # 启动独立的浏览器上下文（使用不同的临时目录防止cookie冲突）
            try:
                # 动态调整超时时间（CI环境中使用倍增器）
                timeout_base = 60000  # 基础超时60秒
                if is_ci:
                    timeout_multiplier = CIConfig.get_ci_timeout_multiplier()
                    timeout_base = int(timeout_base * timeout_multiplier)
                    self.logger.info(f"ℹ️ [{self.account.name}] CI环境超时调整为 {timeout_base/1000}秒 (倍增器: {timeout_multiplier})")

                # 获取代理配置（如果启用，支持订阅模式）
                proxy_config = None
                if ProxyManager.should_use_proxy():
                    # 优先使用异步方法（支持订阅），回退到同步方法（直接配置）
                    proxy_config = await ProxyManager.get_proxy_config_async()
                    if proxy_config:
                        self.logger.info(f"🌐 [{self.account.name}] 启用代理: {proxy_config['server']}")

                # 使用增强的浏览器参数
                browser_args = EnhancedStealth.get_enhanced_browser_args()

                context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=temp_dir,
                    headless=headless_mode,
                    user_agent=BROWSER_USER_AGENT,
                    viewport=BROWSER_VIEWPORT,
                    args=browser_args,
                    slow_mo=100 if not is_ci else 0,  # CI 环境不需要减速
                    timeout=timeout_base,
                    proxy=proxy_config,  # 添加代理支持
                )
                self.logger.info(f"✅ [{self.account.name}] 浏览器上下文启动成功 (headless={headless_mode}, proxy={bool(proxy_config)})")
            except Exception as e:
                self.logger.error(f"❌ [{self.account.name}] 浏览器上下文启动失败: {e}")
                return False, {"error": f"Browser launch failed: {str(e)}"}

            try:
                page = await context.new_page()
                self.logger.debug(f"✅ [{self.account.name}] 新页面创建成功")

                # 注入增强版反检测脚本（2025版，20+特征）
                self.logger.debug(f"🔧 [{self.account.name}] 注入增强版反检测脚本...")
                await EnhancedStealth.inject_stealth_scripts(page)
                self.logger.info(f"✅ [{self.account.name}] 增强版反检测脚本注入成功（20+特征）")
            except Exception as e:
                self.logger.error(f"❌ [{self.account.name}] 创建页面失败: {e}")
                await context.close()
                return False, {"error": f"Page creation failed: {str(e)}"}

            try:
                # 步骤 1: 对于 AgentRouter 跳过 WAF cookies
                waf_cookies = {}
                if self.provider.name.lower() != "agentrouter":
                    waf_cookies = await self._get_waf_cookies(page, context)
                    if not waf_cookies:
                        self.logger.warning(f"⚠️ [{self.account.name}] 未获取到 WAF cookies，继续尝试")
                else:
                    self.logger.info(f"ℹ️ [{self.account.name}] AgentRouter 不需要 WAF cookies，跳过")

                # 步骤 1.5: 可选的人类行为模拟（支持全局和按认证方式定制）
                if StealthConfig.should_enable_behavior_simulation(auth_config.method.value):
                    self.logger.info(f"🤖 [{self.account.name}] 开始模拟人类行为（{auth_config.method.value}）...")
                    try:
                        await EnhancedStealth.simulate_reading_behavior(page)
                        self.logger.info(f"✅ [{self.account.name}] 人类行为模拟完成")
                    except Exception as e:
                        self.logger.warning(f"⚠️ [{self.account.name}] 行为模拟失败: {e}")

                # 步骤 2: 执行认证
                authenticator = get_authenticator(self.account.name, auth_config, self.provider)
                auth_result = await authenticator.authenticate(page, context)

                if not auth_result["success"]:
                    return False, {"error": auth_result.get("error", "Authentication failed")}

                # 获取认证后的 cookies 和用户信息
                auth_cookies = auth_result.get("cookies", {})
                auth_user_id = auth_result.get("user_id")
                auth_username = auth_result.get("username")

                # 更新 auth_config 中的用户标识（优先使用真实获取的）
                if auth_user_id:
                    auth_config.api_user = auth_user_id
                    self.logger.info(f"✅ [{self.account.name}] 认证成功，用户ID: {auth_user_id}")
                elif auth_username:
                    auth_config.api_user = auth_username
                    self.logger.info(f"✅ [{self.account.name}] 认证成功，用户名: {auth_username}")
                else:
                    self.logger.info(f"✅ [{self.account.name}] 认证成功，获取到 cookies")

                # 步骤 3: 执行签到（AgentRouter通过查询用户信息完成）
                if self.provider.name.lower() == "agentrouter":
                    # AgentRouter: 查询用户信息即可完成签到
                    self.logger.info(f"ℹ️ [{self.account.name}] AgentRouter 通过查询用户信息自动签到")
                    user_info = await self._get_user_info(auth_cookies, auth_config)
                    if user_info and user_info.get("success"):
                        # 计算余额变化
                        balance_change = self._calculate_balance_change(
                            self.account.name,
                            auth_config.method.value,
                            user_info
                        )
                        user_info["balance_change"] = balance_change

                        # 保存余额数据
                        self._save_balance_data(self.account.name, auth_config.method.value, user_info)

                        return True, user_info
                    else:
                        return False, {"error": "Failed to get user info for AgentRouter"}
                else:
                    # AnyRouter: 需要显式调用签到接口
                    checkin_result = await self._do_checkin(auth_cookies, auth_config)
                    if not checkin_result["success"]:
                        return False, {"error": checkin_result.get("message", "Check-in failed")}

                    self.logger.info(f"✅ [{self.account.name}] 签到成功: {checkin_result.get('message', '')}")

                    # 步骤 4: 获取用户信息和余额
                    user_info = await self._get_user_info(auth_cookies, auth_config)
                    if user_info and user_info.get("success"):
                        # 计算余额变化
                        balance_change = self._calculate_balance_change(
                            self.account.name,
                            auth_config.method.value,
                            user_info
                        )
                        user_info["balance_change"] = balance_change

                        # 保存余额数据
                        self._save_balance_data(self.account.name, auth_config.method.value, user_info)

                        return True, user_info
                    else:
                        return True, {"success": True, "message": "Check-in successful but failed to get user info"}

            except asyncio.TimeoutError as e:
                self.logger.error(f"❌ [{self.account.name}] 签到超时: {str(e)}")
                return False, {"error": f"Timeout during check-in: {str(e)}"}
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                self.logger.error(f"❌ [{self.account.name}] 网络请求异常: {type(e).__name__}: {str(e)}")
                return False, {"error": f"Network error during check-in: {str(e)}"}
            except (KeyError, TypeError, AttributeError) as e:
                self.logger.error(f"❌ [{self.account.name}] 数据处理异常: {type(e).__name__}: {str(e)}")
                return False, {"error": f"Data processing error: {str(e)}"}
            except Exception as e:
                # 捕获所有其他未预期的异常（包括 Playwright 异常）
                self.logger.error(f"❌ [{self.account.name}] 签到过程异常: {type(e).__name__}: {str(e)}")
                return False, {"error": f"Unexpected error during check-in: {str(e)}"}

            finally:
                # 安全关闭页面和上下文
                try:
                    if page and not page.is_closed():
                        await page.close()
                        self.logger.debug(f"🔒 [{self.account.name}] 页面已关闭")
                except Exception as e:
                    self.logger.warning(f"⚠️ [{self.account.name}] 关闭页面时出现警告: {e}")

                try:
                    await context.close()
                    self.logger.debug(f"🔒 [{self.account.name}] 浏览器上下文已关闭")
                except Exception as e:
                    self.logger.warning(f"⚠️ [{self.account.name}] 关闭浏览器上下文时出现警告: {e}")

                # 清理临时目录
                try:
                    if temp_dir and os.path.exists(temp_dir):
                        import shutil
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        self.logger.debug(f"🗑️ [{self.account.name}] 临时目录已清理: {temp_dir}")
                except Exception as e:
                    self.logger.debug(f"⚠️ [{self.account.name}] 清理临时目录失败: {e}")

    async def _get_waf_cookies(self, page: Page, context: BrowserContext) -> Dict[str, str]:
        """获取 WAF cookies"""
        try:
            self.logger.info(f"ℹ️ [{self.account.name}] 正在获取 WAF cookies...")

            # 访问登录页面以触发 WAF
            await page.goto(self.provider.get_login_url(), wait_until="domcontentloaded", timeout=BROWSER_PAGE_LOAD_TIMEOUT)

            # 等待页面加载
            try:
                await page.wait_for_function('document.readyState === "complete"', timeout=5000)
            except:
                await page.wait_for_timeout(3000)

            # 提取 WAF cookies
            cookies = await context.cookies()
            waf_cookies = {}
            for cookie in cookies:
                if cookie["name"] in WAF_COOKIE_NAMES:
                    waf_cookies[cookie["name"]] = cookie["value"]

            if waf_cookies:
                self.logger.info(f"✅ [{self.account.name}] 获取到 {len(waf_cookies)} 个 WAF cookies")
            else:
                self.logger.warning(f"⚠️ [{self.account.name}] 未获取到 WAF cookies")

            return waf_cookies

        except (asyncio.TimeoutError, Exception) as e:
            self.logger.warning(f"⚠️ [{self.account.name}] 获取 WAF cookies 失败: {str(e)}")
            return {}

    def _check_key_cookies(self, cookies: Dict[str, str]) -> None:
        """检查关键cookies并打印调试信息"""
        self.logger.info(f"🍪 [{self.account.name}] 输入cookies数量: {len(cookies)}")

        found_key_cookies = []
        for cookie_name in KEY_COOKIE_NAMES:
            if cookie_name in cookies:
                found_key_cookies.append(cookie_name)
                self.logger.info(f"   ✅ 找到关键cookie: {cookie_name}")

        if not found_key_cookies:
            self.logger.warning(f"   ⚠️ 未找到标准认证cookie，尝试所有可用cookies")
            for cookie_name in list(cookies.keys())[:5]:
                self.logger.info(f"   📄 可用cookie: {cookie_name}")

    def _prepare_checkin_headers(self, auth_config: AuthConfig) -> Dict[str, str]:
        """准备签到请求头"""
        api_user = auth_config.api_user
        if not api_user:
            api_user = self._infer_api_user(self.account.name)
            self.logger.info(f"🔍 [{self.account.name}] 从账号名称推断API User: {api_user}")

        headers = self._build_request_headers(api_user)
        headers.update({
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        })

        if api_user:
            self.logger.info(f"🔑 [{self.account.name}] 使用签到API User: {api_user}")
        else:
            self.logger.warning(f"⚠️ [{self.account.name}] 签到无法确定API User")

        return headers


    async def _handle_checkin_response(self, response: httpx.Response, client: httpx.AsyncClient, headers: Dict[str, str]) -> Dict[str, Any]:
        """处理签到响应"""
        self.logger.info(f"📊 [{self.account.name}] 签到响应: HTTP {response.status_code}")

        # 检查响应头
        response_headers = dict(response.headers)
        if 'set-cookie' in response_headers:
            self.logger.info(f"🍪 [{self.account.name}] 响应包含新cookies: {response_headers['set-cookie'][:100]}...")

        # 使用策略模式处理不同状态码
        checkin_handlers = {
            200: lambda: self._handle_200_response(response),
            401: lambda: self._handle_401_response(client),
            403: lambda: self._handle_403_response(),
            404: lambda: self._handle_404_response(client, headers),
        }

        handler = checkin_handlers.get(response.status_code)
        if handler:
            return await handler()
        else:
            return self._handle_other_response(response)

    async def _handle_200_response(self, response: httpx.Response) -> Dict[str, Any]:
        """处理200响应"""
        try:
            data = response.json()
            self.logger.info(f"📋 [{self.account.name}] 签到API响应: success={data.get('success')}")

            if data.get("success"):
                return {"success": True, "message": data.get("message", "签到成功")}
            else:
                error_msg = data.get("message", "签到失败")
                self.logger.error(f"❌ [{self.account.name}] 签到失败: {error_msg}")
                return {"success": False, "message": error_msg}
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"❌ [{self.account.name}] 解析签到响应失败: {e}")
            self.logger.info(f"📄 [{self.account.name}] 原始响应: {response.text[:200]}...")
            if "html" in response.headers.get("content-type", "").lower():
                self.logger.info(f"🔄 [{self.account.name}] 检测到HTML响应，可能需要重新登录")
            return {"success": False, "message": "响应解析失败"}

    async def _handle_401_response(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """处理401认证失败响应"""
        self.logger.error(f"❌ [{self.account.name}] 签到认证失败 (401)")
        self.logger.info(f"🔍 [{self.account.name}] 检查cookies有效性...")

        try:
            page_response = await client.get(self.provider.base_url)
            if "login" in page_response.text.lower():
                self.logger.info(f"🔄 [{self.account.name}] 检测到需要重新登录")
            return {"success": False, "message": "认证已过期，需要重新登录"}
        except:
            return {"success": False, "message": "认证已过期，需要重新登录"}

    def _handle_403_response(self) -> Dict[str, Any]:
        """处理403禁止访问响应"""
        self.logger.error(f"❌ [{self.account.name}] 访问被禁止 (403) - 权限不足")
        return {"success": False, "message": "访问被禁止"}

    async def _handle_404_response(self, client: httpx.AsyncClient, headers: Dict[str, str]) -> Dict[str, Any]:
        """处理404响应 - 尝试查询用户信息作为保活"""
        self.logger.info(f"🔍 [{self.account.name}] 签到接口返回404，尝试查询用户信息进行保活...")
        try:
            user_resp = await client.get(
                self.provider.get_user_info_url(),
                headers={"Accept": "application/json", "User-Agent": headers["User-Agent"]}
            )
            if user_resp.status_code == 200:
                data = user_resp.json()
                if data.get("success"):
                    self.logger.info(f"✅ [{self.account.name}] 用户信息查询成功，账号已保活")
                    return {"success": True, "message": "签到接口不存在，但账号状态正常"}
                else:
                    self.logger.warning(f"⚠️ [{self.account.name}] 用户信息查询失败: {data.get('message', 'Unknown error')}")
            else:
                self.logger.warning(f"⚠️ [{self.account.name}] 用户信息接口返回 {user_resp.status_code}")
        except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError) as e:
            self.logger.warning(f"⚠️ [{self.account.name}] 用户信息查询异常: {e}")

        self.logger.error(f"❌ [{self.account.name}] 签到接口和用户信息查询都失败")
        return {"success": False, "message": "签到接口404，用户信息查询也失败"}

    def _handle_other_response(self, response: httpx.Response) -> Dict[str, Any]:
        """处理其他HTTP响应"""
        self.logger.error(f"❌ [{self.account.name}] 签到请求失败: HTTP {response.status_code}")
        self.logger.info(f"📄 [{self.account.name}] 响应内容: {response.text[:100]}...")
        return {"success": False, "message": f"HTTP {response.status_code}"}

    @performance_monitor
    @retry_async(max_retries=3, delay=2, backoff=2)
    async def _do_checkin(self, cookies: Dict[str, str], auth_config: AuthConfig) -> Dict[str, Any]:
        """执行签到请求（带重试机制和速率限制保护）"""
        try:
            # 添加随机延迟，避免触发速率限制
            import random
            delay = random.uniform(RATE_LIMIT_DELAY_MIN, RATE_LIMIT_DELAY_MAX)
            self.logger.debug(f"⏱️ [{self.account.name}] 速率限制保护延迟 {delay:.2f}秒")
            await asyncio.sleep(delay)

            self.logger.info(f"📡 [{self.account.name}] 开始签到请求...")

            # 检查关键cookies
            self._check_key_cookies(cookies)

            # 准备请求头
            headers = self._prepare_checkin_headers(auth_config)

            self.logger.info(f"🎯 [{self.account.name}] 请求URL: {self.provider.get_checkin_url()}")

            # 创建HTTP客户端并发送请求
            async with httpx.AsyncClient(
                cookies=cookies,
                timeout=HTTP_TIMEOUT,
                trust_env=False,
                verify=True,  # 强制启用SSL验证，确保安全
                follow_redirects=True,
                headers=headers
            ) as client:
                self.logger.info(f"📤 [{self.account.name}] 发送POST请求...")
                response = await client.post(self.provider.get_checkin_url())

                # 处理响应
                return await self._handle_checkin_response(response, client, headers)

        except (httpx.HTTPError, httpx.TimeoutException, ConnectionError) as e:
            self.logger.error(f"❌ [{self.account.name}] 网络请求异常: {type(e).__name__}: {str(e)}")
            return {"success": False, "message": f"网络请求异常: {str(e)}"}
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"❌ [{self.account.name}] 数据解析异常: {type(e).__name__}: {str(e)}")
            return {"success": False, "message": f"响应数据异常: {str(e)}"}
        except Exception as e:
            self.logger.error(f"❌ [{self.account.name}] 未知异常: {type(e).__name__}: {str(e)}")
            return {"success": False, "message": f"请求异常: {str(e)}"}


    def _prepare_user_info_headers(self, auth_config: AuthConfig) -> Dict[str, str]:
        """准备用户信息查询请求头"""
        api_user = auth_config.api_user
        if not api_user:
            api_user = self._infer_api_user(self.account.name)
            self.logger.info(f"🔍 [{self.account.name}] 从账号名称推断API User: {api_user}")

        headers = self._build_request_headers(api_user)
        headers["X-Requested-With"] = "XMLHttpRequest"

        if api_user:
            self.logger.info(f"🔑 [{self.account.name}] 使用API User: {api_user}")
        else:
            self.logger.warning(f"⚠️ [{self.account.name}] 无法确定API User")

        return headers

    def _parse_user_info_response(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析用户信息响应数据"""
        if data.get("success") and data.get("data"):
            user_data = data["data"]
            # 使用Decimal进行精确货币计算
            quota = Decimal(str(user_data.get("quota", 0))) / Decimal(str(QUOTA_TO_DOLLAR_RATE))
            used_quota = Decimal(str(user_data.get("used_quota", 0))) / Decimal(str(QUOTA_TO_DOLLAR_RATE))

            # 四舍五入到2位小数
            quota_rounded = float(quota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            used_rounded = float(used_quota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

            self.logger.info(f"✅ [{self.account.name}] 用户信息获取成功!")
            return {
                "success": True,
                "quota": quota_rounded,
                "used": used_rounded,
                "display": f"余额: ${quota_rounded:.2f}, 已用: ${used_rounded:.2f}"
            }
        else:
            error_msg = data.get("message", "未知错误")
            self.logger.error(f"❌ [{self.account.name}] API返回失败: {error_msg}")
            return None

    async def _handle_user_info_response(self, response: httpx.Response) -> Optional[Dict[str, Any]]:
        """处理用户信息响应"""
        self.logger.info(f"📊 [{self.account.name}] 用户信息响应: HTTP {response.status_code}")

        # 使用策略模式处理不同状态码
        if response.status_code == 200:
            try:
                data = response.json()
                self.logger.info(f"📋 [{self.account.name}] API响应: success={data.get('success')}")
                return self._parse_user_info_response(data)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                self.logger.error(f"❌ [{self.account.name}] 解析响应失败: {e}")
                self.logger.info(f"📄 [{self.account.name}] 原始响应: {response.text[:200]}...")
                return None

        # 处理错误状态码
        error_messages = {
            401: "认证失败 (401)",
            403: "访问被禁止 (403)",
            404: "用户信息接口不存在 (404)",
        }

        error_msg = error_messages.get(response.status_code)
        if error_msg:
            if response.status_code == 404:
                self.logger.warning(f"⚠️ [{self.account.name}] {error_msg}")
            else:
                self.logger.error(f"❌ [{self.account.name}] {error_msg}")
        else:
            self.logger.error(f"❌ [{self.account.name}] HTTP错误: {response.status_code}")
            self.logger.info(f"📄 [{self.account.name}] 响应内容: {response.text[:100]}...")

        return None

    @performance_monitor
    @retry_async(max_retries=3, delay=2, backoff=2)
    async def _get_user_info(self, cookies: Dict[str, str], auth_config: AuthConfig) -> Optional[Dict[str, Any]]:
        """获取用户信息和余额（带重试机制）"""
        try:
            self.logger.info(f"📡 [{self.account.name}] 开始用户信息查询...")

            # 检查关键cookies（复用方法）
            self._check_key_cookies(cookies)

            # 准备请求头
            headers = self._prepare_user_info_headers(auth_config)

            self.logger.info(f"🎯 [{self.account.name}] 请求URL: {self.provider.get_user_info_url()}")

            # 创建HTTP客户端并发送请求
            async with httpx.AsyncClient(
                cookies=cookies,
                timeout=HTTP_TIMEOUT,
                trust_env=False,
                verify=True,  # 强制启用SSL验证，确保安全
                follow_redirects=True,
                headers=headers
            ) as client:
                response = await client.get(self.provider.get_user_info_url())
                return await self._handle_user_info_response(response)

        except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError) as e:
            self.logger.warning(f"⚠️ [{self.account.name}] 获取用户信息失败: {str(e)}")
            return None

    def _calculate_balance_change(self, account_name: str, auth_method: str, current_info: Dict[str, Any]) -> Dict[str, Any]:
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

                    # 使用Decimal进行精确计算
                    old_quota = Decimal(str(old_info.get("quota", 0)))
                    old_used = Decimal(str(old_info.get("used", 0)))
                    current_quota = Decimal(str(current_info.get("quota", 0)))
                    current_used = Decimal(str(current_info.get("used", 0)))

                    # 计算变化
                    total_change = (current_quota + current_used) - (old_quota + old_used)
                    used_change = current_used - old_used
                    quota_change = current_quota - old_quota

                    # 四舍五入到2位小数并转换为float
                    change["recharge"] = float(total_change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                    change["used_change"] = float(used_change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                    change["quota_change"] = float(quota_change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        except (IOError, OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.warning(f"⚠️ 计算余额变化失败: {str(e)}")

        return change

    def _save_balance_data(self, account_name: str, auth_method: str, current_info: Dict[str, Any]) -> None:
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

        except (IOError, OSError, json.JSONDecodeError) as e:
            self.logger.warning(f"⚠️ 保存余额数据失败: {str(e)}")

    def _infer_api_user(self, account_name: str) -> Optional[str]:
        """从账号名称推断API User"""
        import re
        # 尝试从账号名称提取数字ID
        numbers = re.findall(r'\d+', account_name)
        if numbers:
            return numbers[0]  # 使用第一个找到的数字
        else:
            # 使用账号名称作为备用方案
            return account_name.replace("-", "_").replace(".", "")
