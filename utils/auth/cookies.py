"""
Cookies 认证器 - 使用预设的 Cookies 进行认证
"""

import asyncio
from typing import Dict, Any, Tuple, Optional
from playwright.async_api import Page, BrowserContext

from utils.auth.base import Authenticator, logger
from utils.sanitizer import sanitize_exception


class CookiesAuthenticator(Authenticator):
    """Cookies 认证"""

    async def _validate_cookies_with_precheck(
        self,
        page: Page,
        cookies_dict: Dict[str, str]
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Cookies 有效性预检机制（增强版）

        Returns:
            Tuple[bool, Optional[str], Optional[str], Optional[str]]:
                (是否有效, 用户ID, 用户名, 错误信息)
        """
        try:
            # 步骤1: 先访问登录页，检查是否被 Cloudflare 拦截
            logger.info(f"🔍 [{self.account_name}] 步骤1: 访问登录页检测 Cloudflare...")
            await page.goto(
                f"{self.provider_config.base_url}/login",
                wait_until="domcontentloaded",
                timeout=30000
            )
            await asyncio.sleep(2)  # 等待页面加载完成

            # 获取页面内容
            page_content = await page.content()
            current_url = page.url

            # 步骤2: 检测 Cloudflare 拦截特征
            cf_indicators = [
                'Checking your browser',
                'Just a moment',
                'cf-challenge',
                'challenge-platform',
                'cloudflare',
                'ddos protection'
            ]

            has_cf_challenge = any(
                indicator.lower() in page_content.lower()
                for indicator in cf_indicators
            )

            if has_cf_challenge:
                logger.warning(f"⚠️ [{self.account_name}] 检测到 Cloudflare 拦截，等待验证完成...")

                # 等待 Cloudflare 验证完成（最多15秒）
                verification_passed = await self._wait_for_cloudflare_bypass(page, max_wait=15)

                if not verification_passed:
                    return False, None, None, "Cloudflare challenge not passed"

                # 重新获取页面内容
                page_content = await page.content()
                current_url = page.url

            # 步骤3: 检查是否在登录页（说明 cookies 失效）
            if '/login' in current_url and any(
                keyword in page_content for keyword in ['登录', 'Login', 'Sign in', 'Email', 'Password']
            ):
                logger.warning(f"⚠️ [{self.account_name}] Cookies 已失效，页面停留在登录页")
                return False, None, None, "Cookies expired (redirected to login)"

            # 步骤4: 尝试 API 请求验证
            logger.info(f"🔍 [{self.account_name}] 步骤2: 通过 API 验证 Cookies...")

            try:
                import httpx
                from utils.constants import DEFAULT_USER_AGENT

                headers = {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": "application/json",
                    "Referer": self.provider_config.base_url
                }

                async with httpx.AsyncClient(
                    cookies=cookies_dict,
                    timeout=10.0,
                    verify=True,
                    follow_redirects=False  # 不自动跟随重定向
                ) as client:
                    response = await client.get(
                        self.provider_config.get_user_info_url(),
                        headers=headers
                    )

                    # 检查状态码
                    if response.status_code == 401:
                        logger.warning(f"⚠️ [{self.account_name}] API 返回 401，Cookies 已失效")
                        return False, None, None, "Cookies expired (API 401)"

                    # 检查是否被重定向到登录页
                    if response.status_code in [301, 302, 303, 307, 308]:
                        location = response.headers.get('location', '')
                        if 'login' in location.lower():
                            logger.warning(f"⚠️ [{self.account_name}] API 重定向到登录页，Cookies 已失效")
                            return False, None, None, "Cookies expired (redirected to login)"

                    # 检查响应内容类型
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' not in content_type:
                        logger.warning(
                            f"⚠️ [{self.account_name}] API 返回非 JSON 内容: {content_type}"
                        )

                        # 检查是否是 HTML（可能是 Cloudflare 拦截页或登录页）
                        if 'text/html' in content_type:
                            response_text = response.text[:500]  # 只取前500字符分析

                            if any(indicator in response_text for indicator in cf_indicators):
                                logger.warning(f"⚠️ [{self.account_name}] API 被 Cloudflare 拦截")
                                return False, None, None, "API blocked by Cloudflare"

                            if any(keyword in response_text for keyword in ['登录', 'Login', 'Sign in']):
                                logger.warning(f"⚠️ [{self.account_name}] API 返回登录页，Cookies 已失效")
                                return False, None, None, "Cookies expired (API returned login page)"

                        return False, None, None, f"API returned non-JSON content: {content_type}"

                    # 解析 JSON 响应
                    if response.status_code == 200:
                        try:
                            data = response.json()

                            if data.get("success") and data.get("data"):
                                user_data = data["data"]
                                user_id = (
                                    user_data.get("id") or
                                    user_data.get("user_id") or
                                    user_data.get("userId")
                                )
                                username = (
                                    user_data.get("username") or
                                    user_data.get("name") or
                                    user_data.get("email")
                                )

                                if user_id or username:
                                    logger.info(
                                        f"✅ [{self.account_name}] Cookies 预检通过: "
                                        f"ID={user_id}, 用户名={username}"
                                    )
                                    return True, str(user_id) if user_id else None, username, None

                            logger.warning(f"⚠️ [{self.account_name}] API 响应格式异常: {data}")
                            return False, None, None, "API response format invalid"

                        except Exception as json_error:
                            logger.warning(
                                f"⚠️ [{self.account_name}] JSON 解析失败: {json_error}"
                            )
                            return False, None, None, f"JSON parse error: {json_error}"

                    logger.warning(
                        f"⚠️ [{self.account_name}] API 返回异常状态码: {response.status_code}"
                    )
                    return False, None, None, f"API returned status {response.status_code}"

            except httpx.TimeoutException:
                logger.warning(f"⚠️ [{self.account_name}] API 请求超时")
                return False, None, None, "API request timeout"
            except Exception as api_error:
                logger.warning(f"⚠️ [{self.account_name}] API 请求失败: {api_error}")
                # API 失败不一定是 cookies 问题，尝试从页面提取
                pass

            # 步骤5: API 失败，尝试从页面提取用户信息
            logger.info(f"🔍 [{self.account_name}] 步骤3: 从页面提取用户信息作为后备方案...")
            user_id, username = await self._extract_user_from_page(page)

            if user_id or username:
                logger.info(
                    f"✅ [{self.account_name}] 从页面提取到用户信息: "
                    f"ID={user_id}, 用户名={username}"
                )
                return True, user_id, username, None

            # 完全无法验证
            logger.warning(f"⚠️ [{self.account_name}] 无法通过任何方式验证 Cookies")
            return False, None, None, "Unable to validate cookies through any method"

        except Exception as e:
            logger.error(f"❌ [{self.account_name}] Cookies 预检异常: {e}")
            return False, None, None, f"Validation error: {sanitize_exception(e)}"

    async def _wait_for_cloudflare_bypass(
        self,
        page: Page,
        max_wait: int = 15
    ) -> bool:
        """
        等待 Cloudflare 验证完成

        Args:
            page: Playwright 页面对象
            max_wait: 最大等待秒数

        Returns:
            bool: 是否通过验证
        """
        try:
            start_time = asyncio.get_event_loop().time()

            while asyncio.get_event_loop().time() - start_time < max_wait:
                page_content = await page.content()
                current_url = page.url

                # 检查是否还有 Cloudflare 标记
                has_cloudflare = any(
                    marker in page_content.lower()
                    for marker in [
                        "just a moment",
                        "checking your browser",
                        "cf-challenge",
                        "challenge-platform"
                    ]
                )

                # 如果没有 Cloudflare 标记，且不在验证页，说明通过了
                if not has_cloudflare:
                    page_title = await page.title()
                    if "verification" not in page_title.lower():
                        logger.info(f"✅ [{self.account_name}] Cloudflare 验证已通过")
                        return True

                # 检查是否已跳转到正常页面
                if '/login' in current_url and not has_cloudflare:
                    logger.info(f"✅ [{self.account_name}] 已跳转到登录页，验证通过")
                    return True

                # 继续等待
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                logger.info(f"   ⏳ 等待 Cloudflare 验证... ({elapsed}s/{max_wait}s)")
                await asyncio.sleep(2)

            logger.warning(f"⚠️ [{self.account_name}] Cloudflare 验证超时")
            return False

        except Exception as e:
            logger.warning(f"⚠️ [{self.account_name}] Cloudflare 等待异常: {e}")
            return False

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用 Cookies 认证（增强版 - 带预检机制）"""
        try:
            # 设置 cookies
            cookies = self.auth_config.cookies
            if not cookies:
                return {"success": False, "error": "No cookies provided"}

            # 将 cookies 字典转换为 Playwright 格式
            cookie_list = []
            for name, value in cookies.items():
                cookie_list.append({
                    "name": name,
                    "value": value,
                    "domain": self._get_domain(self.provider_config.base_url),
                    "path": "/"
                })

            await context.add_cookies(cookie_list)

            # 获取cookies字典用于验证
            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            # 🔥 核心改进：使用预检机制验证 Cookies
            logger.info(f"🔍 [{self.account_name}] 开始 Cookies 有效性预检...")
            is_valid, user_id, username, error_msg = await self._validate_cookies_with_precheck(
                page, cookies_dict
            )

            if is_valid:
                logger.info(f"✅ [{self.account_name}] Cookies 验证成功")
                return {
                    "success": True,
                    "cookies": cookies_dict,
                    "user_id": user_id,
                    "username": username
                }
            else:
                logger.error(f"❌ [{self.account_name}] Cookies 验证失败: {error_msg}")
                return {"success": False, "error": error_msg or "Cookies validation failed"}

        except Exception as e:
            error_msg = sanitize_exception(e)
            logger.error(f"❌ [{self.account_name}] Cookies 认证异常: {error_msg}")
            return {"success": False, "error": f"Cookies auth failed: {error_msg}"}
