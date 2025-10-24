"""
认证模块 - 处理不同的认证方式
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from playwright.async_api import Page, BrowserContext
from utils.config import AuthConfig, ProviderConfig


class Authenticator(ABC):
    """认证器基类"""

    def __init__(self, auth_config: AuthConfig, provider_config: ProviderConfig):
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
                "error": str      # 错误信息（如果失败）
            }
        """
        pass


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

            # 验证 cookies 是否有效
            await page.goto(self.provider_config.get_user_info_url())
            await page.wait_for_load_state("networkidle", timeout=10000)

            # 检查是否跳转到登录页
            current_url = page.url
            if "login" in current_url.lower():
                return {"success": False, "error": "Cookies expired or invalid"}

            # 获取最新 cookies
            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            return {"success": True, "cookies": cookies_dict}

        except Exception as e:
            return {"success": False, "error": f"Cookies auth failed: {str(e)}"}

    def _get_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc


class GitHubAuthenticator(Authenticator):
    """GitHub OAuth 认证"""

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用 GitHub 登录"""
        try:
            print(f"ℹ️ Starting GitHub authentication")

            # 访问登录页
            await page.goto(self.provider_config.get_login_url())
            await page.wait_for_load_state("domcontentloaded")

            # 查找并点击 GitHub 登录按钮
            github_button = await page.query_selector('button:has-text("GitHub")')
            if not github_button:
                github_button = await page.query_selector('a:has-text("GitHub")')

            if not github_button:
                return {"success": False, "error": "GitHub login button not found"}

            await github_button.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

            # 如果已经在 GitHub 授权页，直接授权
            if "github.com" in page.url:
                # 填写 GitHub 账号密码
                username_input = await page.query_selector('input[name="login"]')
                password_input = await page.query_selector('input[name="password"]')

                if username_input and password_input:
                    await username_input.fill(self.auth_config.username)
                    await password_input.fill(self.auth_config.password)

                    # 提交登录
                    submit_button = await page.query_selector('input[type="submit"]')
                    if submit_button:
                        await submit_button.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)

                # 处理 2FA（如果需要）
                if "two-factor" in page.url or "2fa" in page.url.lower():
                    print("⚠️ GitHub 2FA required - please check logs for OTP link")
                    # 这里可以实现 2FA 处理逻辑
                    # 参考项目有完整实现，可以按需添加
                    return {"success": False, "error": "2FA required - not implemented yet"}

                # 点击授权按钮（如果有）
                authorize_button = await page.query_selector('button[name="authorize"]')
                if authorize_button:
                    await authorize_button.click()
                    await page.wait_for_load_state("networkidle", timeout=10000)

            # 等待回调完成
            await page.wait_for_url(lambda url: self.provider_config.base_url in url, timeout=20000)

            # 获取 cookies
            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            return {"success": True, "cookies": cookies_dict}

        except Exception as e:
            return {"success": False, "error": f"GitHub auth failed: {str(e)}"}


class LinuxDoAuthenticator(Authenticator):
    """Linux.do OAuth 认证"""

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用 Linux.do 登录"""
        try:
            print(f"ℹ️ Starting Linux.do authentication")

            # 访问登录页
            await page.goto(self.provider_config.get_login_url())
            await page.wait_for_load_state("domcontentloaded")

            # 查找并点击 LinuxDO 登录按钮
            linux_button = await page.query_selector('button:has-text("LinuxDO")')
            if not linux_button:
                linux_button = await page.query_selector('a:has-text("LinuxDO")')
            if not linux_button:
                linux_button = await page.query_selector('button:has-text("Linux.do")')

            if not linux_button:
                return {"success": False, "error": "LinuxDO login button not found"}

            await linux_button.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

            # 如果跳转到 Linux.do 登录页
            if "linux.do" in page.url:
                # 填写用户名密码
                username_input = await page.query_selector('input[id="login-account-name"]')
                password_input = await page.query_selector('input[id="login-account-password"]')

                if username_input and password_input:
                    await username_input.fill(self.auth_config.username)
                    await password_input.fill(self.auth_config.password)

                    # 点击登录按钮
                    login_button = await page.query_selector('button[id="login-button"]')
                    if login_button:
                        await login_button.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)

            # 等待回调完成
            await page.wait_for_url(lambda url: self.provider_config.base_url in url, timeout=20000)

            # 获取 cookies
            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            return {"success": True, "cookies": cookies_dict}

        except Exception as e:
            return {"success": False, "error": f"Linux.do auth failed: {str(e)}"}


def get_authenticator(auth_config: AuthConfig, provider_config: ProviderConfig) -> Authenticator:
    """获取对应的认证器"""
    if auth_config.method == "cookies":
        return CookiesAuthenticator(auth_config, provider_config)
    elif auth_config.method == "github":
        return GitHubAuthenticator(auth_config, provider_config)
    elif auth_config.method == "linux.do":
        return LinuxDoAuthenticator(auth_config, provider_config)
    else:
        raise ValueError(f"Unknown auth method: {auth_config.method}")
