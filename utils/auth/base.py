"""
认证器基类 - 提供所有认证方式的通用功能
"""

import os
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from playwright.async_api import Page, BrowserContext
import re

from utils.config import AuthConfig, ProviderConfig
from utils.logger import setup_logger
from utils.sanitizer import sanitize_exception
from utils.constants import (
    DEFAULT_USER_AGENT,
    KEY_COOKIE_NAMES,
    TimeoutConfig,
)

# 模块级logger
logger = setup_logger(__name__)


class Authenticator(ABC):
    """认证器基类"""

    def __init__(self, account_name: str, auth_config: AuthConfig, provider_config: ProviderConfig):
        self.account_name = account_name
        self.auth_config = auth_config
        self.provider_config = provider_config

    @abstractmethod
    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """
        执行认证

        Returns:
            dict: {
                "success": bool,
                "cookies": dict,  # 认证后的 cookies
                "user_id": str,   # 用户ID（可选）
                "username": str,  # 用户名（可选）
                "error": str      # 错误信息（如果失败）
            }
        """
        pass

    async def _wait_for_cloudflare_challenge(
        self,
        page: Page,
        max_wait_seconds: int = 60,
        max_retries: int = 3
    ) -> bool:
        """等待Cloudflare验证完成（优化版 - 支持重试机制）

        Args:
            page: Playwright页面对象
            max_wait_seconds: 单次等待最大秒数
            max_retries: 最大重试次数

        Returns:
            bool: 是否通过验证
        """
        try:
            # 检查是否跳过Cloudflare验证
            if os.getenv("SKIP_CLOUDFLARE_CHECK", "false").lower() == "true":
                logger.info(f"ℹ️ 已配置跳过Cloudflare验证检查")
                return True

            for retry in range(max_retries):
                # 计算本次重试的等待时间（指数退避）
                current_wait_time = max_wait_seconds * (1.5 ** retry)  # 60s, 90s, 135s
                current_wait_time = min(current_wait_time, 180)  # 最多180秒

                if retry > 0:
                    logger.info(f"🔄 Cloudflare验证重试 {retry}/{max_retries-1}（等待时间: {int(current_wait_time)}秒）")

                    # 重试策略1: 刷新页面
                    if retry == 1:
                        try:
                            logger.info(f"🔄 策略1: 刷新页面")
                            await page.reload(wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_timeout(TimeoutConfig.LONG_WAIT_20)
                        except Exception as e:
                            logger.warning(f"⚠️ 刷新页面失败: {e}")

                    # 重试策略2: 重新访问登录页
                    elif retry == 2:
                        try:
                            logger.info(f"🔄 策略2: 重新访问登录页")
                            await page.goto(
                                self.provider_config.get_login_url(),
                                wait_until="domcontentloaded",
                                timeout=30000
                            )
                            await page.wait_for_timeout(TimeoutConfig.MEDIUM_WAIT_10)
                        except Exception as e:
                            logger.warning(f"⚠️ 重新访问失败: {e}")
                else:
                    logger.info(f"🛡️ 检测到可能的Cloudflare验证，等待完成（最多{int(current_wait_time)}秒）...")

                # 开始等待验证通过
                start_time = asyncio.get_event_loop().time()
                verification_passed = False

                while asyncio.get_event_loop().time() - start_time < current_wait_time:
                    current_url = page.url
                    page_title = await page.title()

                    # 更智能的检测：检查页面内容而不仅仅是标题
                    page_content = await page.content()
                    has_cloudflare_markers = any(marker in page_content.lower() for marker in [
                        "just a moment",
                        "checking your browser",
                        "cloudflare",
                        "ddos protection"
                    ])

                    # 检查是否是Cloudflare验证页
                    if has_cloudflare_markers and ("verification" in page_title.lower() or "checking" in page_title.lower()):
                        elapsed = int(asyncio.get_event_loop().time() - start_time)
                        logger.info(f"   ⏳ Cloudflare验证中，继续等待... ({elapsed}s/{int(current_wait_time)}s)")

                        # 超过20秒后降低检测频率
                        wait_time = TimeoutConfig.RETRY_WAIT_MEDIUM if elapsed > 20 else TimeoutConfig.RETRY_WAIT_SHORT
                        await page.wait_for_timeout(wait_time)
                        continue

                    # 检查是否已经通过验证
                    if "login" in current_url.lower() and not has_cloudflare_markers:
                        logger.info(f"✅ Cloudflare验证完成（第 {retry + 1} 次尝试）")
                        verification_passed = True
                        break

                    # 检查登录页面特征（更可靠的判断）
                    try:
                        login_indicators = await page.query_selector_all(
                            'input[type="email"], input[type="password"], input[name="login"], '
                            'button:has-text("登录"), button:has-text("Login")'
                        )
                        if len(login_indicators) > 0:
                            logger.info(f"✅ 检测到登录表单，验证已完成（第 {retry + 1} 次尝试）")
                            verification_passed = True
                            break
                    except:
                        pass

                    # 更短的等待时间
                    await page.wait_for_timeout(1000)

                # 如果本次尝试通过验证，直接返回成功
                if verification_passed:
                    return True

                # 如果是最后一次重试，给出警告后尝试继续
                if retry == max_retries - 1:
                    logger.warning(
                        f"⚠️ Cloudflare验证在 {max_retries} 次尝试后仍未通过"
                        f"（总等待时间约 {int(sum(max_wait_seconds * (1.5 ** i) for i in range(max_retries)))}秒），"
                        f"尝试继续..."
                    )
                    # 超时后不直接返回False，而是尝试继续（可能是误判）
                    return True
                else:
                    logger.warning(f"⚠️ 第 {retry + 1} 次验证尝试超时，准备重试...")

            # 所有重试都失败，但仍尝试继续（可能是误判）
            return True

        except Exception as e:
            logger.warning(f"⚠️ Cloudflare验证检测异常: {e}，尝试继续...")
            return True  # 发生异常时也尝试继续

    def _get_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc

    async def _wait_for_session_cookies(self, context: BrowserContext, max_wait_seconds: int = 10) -> bool:
        """等待会话cookies出现"""
        try:
            logger.info(f"⏳ 等待会话cookies设置...")
            start_time = asyncio.get_event_loop().time()

            while asyncio.get_event_loop().time() - start_time < max_wait_seconds:
                cookies = await context.cookies()
                cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies}

                # 检查是否有会话相关的cookies
                found_session = any(name in cookies_dict for name in KEY_COOKIE_NAMES)
                if found_session:
                    logger.info(f"✅ 检测到会话cookies")
                    return True

                await asyncio.sleep(0.5)  # 每500ms检查一次

            logger.warning(f"⚠️ 等待会话cookies超时({max_wait_seconds}s)")
            return False

        except Exception as e:
            logger.warning(f"⚠️ 等待会话cookies异常: {e}")
            return False

    async def _extract_user_info(self, page: Page, cookies: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """从用户信息API提取用户ID和用户名"""
        try:
            import httpx
            headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
            async with httpx.AsyncClient(cookies=cookies, timeout=10.0, verify=True) as client:
                response = await client.get(self.provider_config.get_user_info_url(), headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("data"):
                        user_data = data["data"]
                        user_id = user_data.get("id") or user_data.get("user_id") or user_data.get("userId")
                        username = user_data.get("username") or user_data.get("name") or user_data.get("email")
                        if user_id or username:
                            logger.info(f"✅ 提取到用户标识: ID={user_id}, 用户名={username}")
                            return str(user_id) if user_id else None, username
                else:
                    logger.warning(f"⚠️ 用户信息API返回 {response.status_code}，尝试从页面提取")
                    # 当API返回401时，尝试从当前页面URL提取user_id
                    return await self._extract_user_from_page(page)
        except Exception as e:
            logger.warning(f"⚠️ 提取用户信息失败: {e}，尝试从页面提取")
            return await self._extract_user_from_page(page)
        return None, None

    async def _extract_user_from_page(self, page: Page) -> Tuple[Optional[str], Optional[str]]:
        """从页面URL或内容提取用户标识"""
        try:
            current_url = page.url
            logger.info(f"🔍 尝试从页面提取用户信息: {current_url}")

            # 尝试从URL路径提取（如 /user/12345）
            user_match = re.search(r'/user/(\w+)', current_url)
            if user_match:
                user_id = user_match.group(1)
                logger.info(f"✅ 从URL提取到用户ID: {user_id}")
                return user_id, None

            # 尝试查找页面中的用户信息
            try:
                # 查找可能包含用户ID的元素
                user_elements = await page.query_selector_all('[data-user-id], [data-userid], [id*="user"]')
                for elem in user_elements[:5]:
                    user_id = await elem.get_attribute('data-user-id') or await elem.get_attribute('data-userid')
                    if user_id and user_id.isdigit():
                        logger.info(f"✅ 从页面元素提取到用户ID: {user_id}")
                        return user_id, None
            except:
                pass

            logger.warning(f"⚠️ 无法从页面提取用户信息")
        except Exception as e:
            logger.warning(f"⚠️ 从页面提取用户信息异常: {e}")

        return None, None

    async def _extract_user_from_localstorage(self, page: Page) -> Tuple[Optional[str], Optional[str]]:
        """从localStorage提取用户标识"""
        try:
            logger.info(f"🔍 尝试从localStorage提取用户信息")

            # 等待5秒，确保localStorage已更新
            await page.wait_for_timeout(TimeoutConfig.MEDIUM_WAIT)

            user_data = await page.evaluate("() => localStorage.getItem('user')")
            if user_data:
                import json
                user_obj = json.loads(user_data)
                user_id = user_obj.get("id")
                username = user_obj.get("username") or user_obj.get("name") or user_obj.get("email")

                if user_id:
                    logger.info(f"✅ 从localStorage提取到用户ID: {user_id}")
                    return str(user_id), username
                else:
                    logger.warning(f"⚠️ localStorage中未找到用户ID")
            else:
                logger.warning(f"⚠️ localStorage中未找到用户数据")
        except Exception as e:
            logger.warning(f"⚠️ 从localStorage提取用户信息异常: {e}")

        return None, None

    async def _init_page_and_check_cloudflare(self, page: Page) -> bool:
        """初始化页面并检查Cloudflare"""
        try:
            await page.goto(self.provider_config.get_login_url(), wait_until="domcontentloaded", timeout=TimeoutConfig.PAGE_LOAD)
            await page.wait_for_timeout(TimeoutConfig.SHORT_WAIT_3)

            page_title = await page.title()
            page_content = await page.content()

            # 更准确地检测Cloudflare验证页
            is_cloudflare = any(marker in page_content.lower() for marker in [
                "just a moment",
                "checking your browser",
                "cloudflare"
            ]) or ("verification" in page_title.lower() or "checking" in page_title.lower())

            if is_cloudflare:
                logger.info(f"🛡️ 检测到Cloudflare验证页面，等待通过...")
                return await self._wait_for_cloudflare_challenge(page)
            return True
        except Exception as e:
            logger.warning(f"⚠️ 页面初始化异常: {e}，尝试继续...")
            return True  # 即使初始化失败也尝试继续

    def _log_cookies_info(self, cookies_dict: Dict[str, str], final_cookies: list, auth_type: str):
        """统一的cookies信息日志"""
        logger.info(f"🍪 [{self.auth_config.username}] {auth_type} OAuth认证完成，获取到 {len(cookies_dict)} 个cookies")

        found_key_cookies = [name for name in KEY_COOKIE_NAMES if name in cookies_dict]
        if found_key_cookies:
            for name in found_key_cookies:
                logger.info(f"   ✅ 找到关键cookie: {name}")
        else:
            logger.warning(f"   ⚠️ 未找到标准认证cookie")
            for i, cookie in enumerate(final_cookies[:5]):
                cookie_domain = cookie.get('domain', 'N/A')
                logger.info(f"      {cookie['name']}: *** (domain: {cookie_domain})")
            if len(cookies_dict) > 5:
                logger.info(f"      ... 还有 {len(cookies_dict) - 5} 个cookies")

    async def _fill_password(self, password_input, error_prefix: str = "Password input failed") -> Optional[str]:
        """安全填写密码 - 模拟人类逐字符输入"""
        try:
            import random
            # 模拟人类逐字符输入，增加随机延迟
            for char in self.auth_config.password:
                await password_input.type(char, delay=50 + random.randint(0, 50))
            return None
        except Exception as e:
            return f"{error_prefix}: {sanitize_exception(e)}"

    async def _retry_with_strategies(
        self,
        page: Page,
        context: BrowserContext,
        operation_func,
        operation_name: str,
        max_retries: int = 3
    ):
        """
        通用重试方法 - 支持多种重试策略

        Args:
            page: Playwright页面对象
            context: 浏览器上下文
            operation_func: 要执行的异步操作函数
            operation_name: 操作名称（用于日志）
            max_retries: 最大重试次数

        Returns:
            操作函数的返回值，失败则返回None
        """
        result = None

        for retry in range(max_retries):
            logger.info(f"🔑 [{self.auth_config.username}] {operation_name}... (尝试 {retry + 1}/{max_retries})")

            # 每次重试前等待递增的时间，并采取不同的策略
            if retry > 0:
                wait_time = TimeoutConfig.RETRY_WAIT_10S * retry  # 10s, 20s
                logger.info(f"⏳ 等待 {wait_time/1000}秒 后重试...")
                await page.wait_for_timeout(wait_time)

                # 策略1：刷新页面
                if retry == 1:
                    try:
                        logger.info(f"🔄 [{self.auth_config.username}] 刷新页面尝试...")
                        await page.reload(wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(TimeoutConfig.MEDIUM_WAIT)
                    except Exception as e:
                        logger.warning(f"⚠️ [{self.auth_config.username}] 刷新页面失败: {e}")

                # 策略2：重新访问登录页
                elif retry == 2:
                    try:
                        logger.info(f"🔄 [{self.auth_config.username}] 重新访问登录页...")
                        await page.goto(
                            self.provider_config.get_login_url(),
                            wait_until="domcontentloaded",
                            timeout=30000
                        )
                        await page.wait_for_timeout(TimeoutConfig.MEDIUM_WAIT_10)
                    except Exception as e:
                        logger.warning(f"⚠️ [{self.auth_config.username}] 重新访问登录页失败: {e}")

            # 获取最新cookies（如果需要的话，operation_func可以在内部处理）
            current_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in current_cookies}
            logger.info(f"🍪 [{self.auth_config.username}] 当前有 {len(cookies_dict)} 个cookies")

            # 执行操作
            result = await operation_func(cookies_dict, page)
            if result:
                logger.info(f"✅ [{self.auth_config.username}] {operation_name}成功")
                break
            elif retry < max_retries - 1:
                logger.warning(f"⚠️ [{self.auth_config.username}] 第 {retry + 1} 次尝试失败，继续重试...")
            else:
                logger.error(f"❌ [{self.auth_config.username}] 所有重试均失败")

        return result
