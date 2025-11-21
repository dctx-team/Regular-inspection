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
        context: BrowserContext,
        cookies_dict: Dict[str, str]
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Cookies 有效性预检机制（增强版）

        Returns:
            Tuple[bool, Optional[str], Optional[str], Optional[str]]:
                (是否有效, 用户ID, 用户名, 错误信息)
        """
        try:
            # 步骤0: 等待 cookies 完全应用
            logger.info(f"🔍 [{self.account_name}] 等待 Cookies 应用到浏览器上下文...")
            await asyncio.sleep(1)

            # 步骤1: 访问用户中心或主页（而非登录页），检查是否自动跳转
            logger.info(f"🔍 [{self.account_name}] 步骤1: 访问用户中心验证 Cookies...")
            try:
                # 优先访问用户中心或仪表板页面
                test_urls = [
                    f"{self.provider_config.base_url}/panel",
                    f"{self.provider_config.base_url}/dashboard",
                    f"{self.provider_config.base_url}/",
                ]

                navigation_success = False
                for test_url in test_urls:
                    try:
                        await page.goto(
                            test_url,
                            wait_until="domcontentloaded",
                            timeout=20000
                        )
                        navigation_success = True
                        logger.info(f"✅ [{self.account_name}] 成功访问: {test_url}")
                        break
                    except Exception as nav_error:
                        logger.debug(f"⚠️ [{self.account_name}] 访问 {test_url} 失败: {nav_error}")
                        continue

                if not navigation_success:
                    logger.warning(f"⚠️ [{self.account_name}] 所有测试 URL 都无法访问")
                    return False, None, None, "Unable to navigate to any test URL"

            except Exception as nav_error:
                logger.warning(f"⚠️ [{self.account_name}] 导航失败: {nav_error}")
                return False, None, None, f"Navigation error: {nav_error}"

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

            # 步骤3: 检查是否被重定向到登录页（说明 cookies 可能失效）
            # 注意：只有当明确在登录页且有登录表单时才判定为失效
            if '/login' in current_url.lower():
                has_login_form = any(
                    keyword in page_content.lower()
                    for keyword in ['<input', 'type="email"', 'type="password"', 'form']
                )
                if has_login_form:
                    logger.warning(f"⚠️ [{self.account_name}] 被重定向到登录页，Cookies 可能已失效")
                    # 不立即返回失败，继续尝试 API 验证
                    logger.info(f"🔍 [{self.account_name}] 继续尝试通过 API 验证...")
                else:
                    logger.info(f"ℹ️ [{self.account_name}] URL 包含 login 但未检测到登录表单，可能是其他页面")

            # 步骤4: 尝试 API 请求验证（优化后的逻辑）
            logger.info(f"🔍 [{self.account_name}] 步骤2: 通过 API 验证 Cookies...")

            api_validation_success = False
            api_user_id = None
            api_username = None

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
                    timeout=15.0,
                    verify=True,
                    follow_redirects=False  # 不自动跟随重定向
                ) as client:
                    response = await client.get(
                        self.provider_config.get_user_info_url(),
                        headers=headers
                    )

                    logger.info(f"📊 [{self.account_name}] API 响应状态: {response.status_code}")

                    # 检查状态码
                    if response.status_code == 401:
                        logger.warning(f"⚠️ [{self.account_name}] API 返回 401，Cookies 可能已失效")
                        # 不立即返回失败，继续尝试从页面提取
                    elif response.status_code in [301, 302, 303, 307, 308]:
                        location = response.headers.get('location', '')
                        if 'login' in location.lower():
                            logger.warning(f"⚠️ [{self.account_name}] API 重定向到登录页，Cookies 可能已失效")
                        else:
                            logger.info(f"ℹ️ [{self.account_name}] API 重定向到: {location}")
                    elif response.status_code == 200:
                        # 检查响应内容类型
                        content_type = response.headers.get('content-type', '').lower()

                        if 'application/json' in content_type:
                            try:
                                data = response.json()

                                if data.get("success") and data.get("data"):
                                    user_data = data["data"]
                                    api_user_id = (
                                        user_data.get("id") or
                                        user_data.get("user_id") or
                                        user_data.get("userId")
                                    )
                                    api_username = (
                                        user_data.get("username") or
                                        user_data.get("name") or
                                        user_data.get("email")
                                    )

                                    if api_user_id or api_username:
                                        logger.info(
                                            f"✅ [{self.account_name}] API 验证通过: "
                                            f"ID={api_user_id}, 用户名={api_username}"
                                        )
                                        api_validation_success = True
                                    else:
                                        logger.warning(f"⚠️ [{self.account_name}] API 响应中未找到用户标识")
                                elif not data.get("success"):
                                    logger.warning(f"⚠️ [{self.account_name}] API 响应 success=false: {data.get('message', 'Unknown')}")
                                else:
                                    logger.warning(f"⚠️ [{self.account_name}] API 响应格式异常")

                            except Exception as json_error:
                                logger.warning(f"⚠️ [{self.account_name}] JSON 解析失败: {json_error}")

                        elif 'text/html' in content_type:
                            logger.warning(f"⚠️ [{self.account_name}] API 返回 HTML 而非 JSON")
                            response_text = response.text[:500]

                            if any(indicator in response_text.lower() for indicator in cf_indicators):
                                logger.warning(f"⚠️ [{self.account_name}] API 可能被 Cloudflare 拦截")
                            elif any(keyword in response_text.lower() for keyword in ['登录', 'login', 'sign in']):
                                logger.warning(f"⚠️ [{self.account_name}] API 返回登录页面")
                        else:
                            logger.warning(f"⚠️ [{self.account_name}] API 返回未知内容类型: {content_type}")
                    else:
                        logger.warning(f"⚠️ [{self.account_name}] API 返回异常状态码: {response.status_code}")

            except httpx.TimeoutException:
                logger.warning(f"⚠️ [{self.account_name}] API 请求超时，尝试从页面提取")
            except Exception as api_error:
                logger.warning(f"⚠️ [{self.account_name}] API 请求异常: {api_error}，尝试从页面提取")

            # 如果 API 验证成功，直接返回
            if api_validation_success:
                return True, str(api_user_id) if api_user_id else None, api_username, None

            # 步骤5: API 失败，尝试从页面提取用户信息（作为最后的后备方案）
            logger.info(f"🔍 [{self.account_name}] 步骤3: 从页面提取用户信息作为后备方案...")

            # 先尝试从 localStorage 提取（更可靠）
            user_id, username = await self._extract_user_from_localstorage(page)

            if not (user_id or username):
                # localStorage 失败，尝试从页面 URL/元素提取
                user_id, username = await self._extract_user_from_page(page)

            if user_id or username:
                logger.info(
                    f"✅ [{self.account_name}] 从页面提取到用户信息: "
                    f"ID={user_id}, 用户名={username}"
                )
                return True, user_id, username, None

            # 步骤6: 如果完全无法验证，但页面不在登录页，则给予宽容判定
            # 但要确保至少有一个标识（不能完全为 None）
            if '/login' not in current_url.lower():
                logger.warning(
                    f"⚠️ [{self.account_name}] 无法通过 API 或页面提取验证用户信息，"
                    f"但当前不在登录页（{current_url}），给予宽容判定"
                )

                # 尝试从 cookies 中提取可能的用户标识
                fallback_id = None
                for cookie in await context.cookies():
                    # 尝试从 cookie 名称中找到可能的用户 ID
                    if 'user' in cookie['name'].lower() or 'id' in cookie['name'].lower():
                        try:
                            # 如果 cookie 值是数字，可能是用户 ID
                            potential_id = str(cookie['value'])
                            if potential_id.isdigit():
                                fallback_id = potential_id
                                logger.info(f"ℹ️ [{self.account_name}] 从 cookie '{cookie['name']}' 提取到可能的用户ID: {fallback_id}")
                                break
                        except:
                            pass

                # 如果没有从 cookie 提取到 ID，使用账号名
                if not fallback_id:
                    fallback_id = self.account_name
                    logger.info(f"ℹ️ [{self.account_name}] 使用账号名作为后备标识: {fallback_id}")

                return True, fallback_id, None, None

            # 完全无法验证
            logger.error(f"❌ [{self.account_name}] 无法通过任何方式验证 Cookies，且页面在登录页")
            return False, None, None, "Unable to validate cookies through any method and page is at login"

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

            # 先访问目标网站，确保域名上下文正确
            logger.info(f"🌐 [{self.account_name}] 预访问目标网站以建立域名上下文...")
            try:
                await page.goto(
                    self.provider_config.base_url,
                    wait_until="domcontentloaded",
                    timeout=15000
                )
                await asyncio.sleep(1)  # 等待页面稳定
            except Exception as nav_error:
                logger.warning(f"⚠️ [{self.account_name}] 预访问失败: {nav_error}，继续尝试设置 cookies")

            # 将 cookies 字典转换为 Playwright 格式
            domain = self._get_domain(self.provider_config.base_url)
            # 移除可能的端口号
            if ':' in domain:
                domain = domain.split(':')[0]

            # 对于子域名，添加前导点以支持所有子域名
            # 例如：api.example.com -> .example.com
            domain_parts = domain.split('.')
            if len(domain_parts) > 2:
                # 使用根域名（支持所有子域名）
                domain = '.' + '.'.join(domain_parts[-2:])
            elif not domain.startswith('.'):
                # 顶级域名也添加前导点
                domain = '.' + domain

            logger.info(f"🍪 [{self.account_name}] 设置 Cookies domain: {domain}")

            cookie_list = []
            for name, value in cookies.items():
                cookie_dict = {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                }

                # 如果是 HTTPS，添加 secure 属性
                if self.provider_config.base_url.startswith('https'):
                    cookie_dict["secure"] = True
                    # 对于跨站 cookies，需要设置 sameSite
                    cookie_dict["sameSite"] = "None"
                else:
                    cookie_dict["sameSite"] = "Lax"

                cookie_list.append(cookie_dict)

            await context.add_cookies(cookie_list)
            logger.info(f"✅ [{self.account_name}] 已添加 {len(cookie_list)} 个 cookies")

            # 获取cookies字典用于验证
            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            # 🔥 核心改进：使用预检机制验证 Cookies
            logger.info(f"🔍 [{self.account_name}] 开始 Cookies 有效性预检...")
            is_valid, user_id, username, error_msg = await self._validate_cookies_with_precheck(
                page, context, cookies_dict
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
