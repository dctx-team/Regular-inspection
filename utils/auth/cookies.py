"""
Cookies 认证器 - 使用预设的 Cookies 进行认证
"""

from typing import Dict, Any
from playwright.async_api import Page, BrowserContext

from utils.auth.base import Authenticator, logger
from utils.sanitizer import sanitize_exception


class CookiesAuthenticator(Authenticator):
    """Cookies 认证"""

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用 Cookies 认证"""
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

            # 获取cookies字典用于API验证
            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            # 直接通过API验证cookies有效性（不再依赖页面跳转）
            logger.info(f"🔍 [{self.account_name}] 验证 cookies 有效性...")
            user_id, username = await self._extract_user_info(page, cookies_dict)

            # 如果API返回了有效的用户信息，说明cookies有效
            if user_id or username:
                logger.info(f"✅ [{self.account_name}] Cookies 验证成功")
                return {
                    "success": True,
                    "cookies": cookies_dict,
                    "user_id": user_id,
                    "username": username
                }

            # 如果API验证失败，尝试访问页面检查是否跳转到登录页
            logger.warning(f"⚠️ [{self.account_name}] API验证失败，检查页面状态...")
            await page.goto(self.provider_config.base_url, wait_until="domcontentloaded", timeout=10000)
            await page.wait_for_timeout(2000)

            current_url = page.url
            if "login" in current_url.lower():
                return {"success": False, "error": "Cookies expired or invalid (redirected to login)"}

            # 页面没有跳转但API失败，可能是cookies部分有效
            # 尝试从页面提取用户信息
            user_id, username = await self._extract_user_from_page(page)
            if user_id or username:
                logger.info(f"✅ [{self.account_name}] 从页面提取到用户信息")
                return {
                    "success": True,
                    "cookies": cookies_dict,
                    "user_id": user_id,
                    "username": username
                }

            # 完全无法验证
            return {"success": False, "error": "Cookies validation failed (no user info available)"}

        except Exception as e:
            return {"success": False, "error": f"Cookies auth failed: {sanitize_exception(e)}"}
