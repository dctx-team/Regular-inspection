"""
认证模块 - 处理不同的认证方式
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from playwright.async_api import Page, BrowserContext
import re
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


class EmailAuthenticator(Authenticator):
    """邮箱密码认证"""

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用邮箱密码登录"""
        try:
            print(f"ℹ️ Starting Email authentication")

            # 访问登录页
            await page.goto(self.provider_config.get_login_url())
            await page.wait_for_load_state("domcontentloaded")
            # 等待页面主要内容渲染
            await page.wait_for_timeout(1500)

            # 如有“邮箱登录”tab，优先点击
            for sel in [
                'button:has-text("邮箱")',
                'a:has-text("邮箱")',
                'button:has-text("Email")',
                'a:has-text("Email")',
                'text=邮箱登录',
                'text=Email Login',
            ]:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        await el.click()
                        await page.wait_for_timeout(800)
                        break
                except:
                    pass

            # 智能等待页面稳定
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(2000)  # 等待动态内容加载

            # 多次尝试关闭弹窗，直到没有可见的弹窗
            max_attempts = 3
            for attempt in range(max_attempts):
                popup_closed = False

                try:
                    # 检测并关闭各种弹窗
                    popup_selectors = [
                        '.semi-modal-portal',
                        '.semi-modal',
                        '[role="dialog"]',
                        '.modal',
                        '.popup',
                        '.overlay',
                        '[class*="modal"]',
                        '[class*="popup"]',
                        '[class*="overlay"]'
                    ]

                    for popup_sel in popup_selectors:
                        try:
                            popups = await page.query_selector_all(popup_sel)
                            for popup in popups:
                                if await popup.is_visible():
                                    print(f"🔍 发现弹窗: {popup_sel}")

                                    # 查找关闭按钮
                                    close_selectors = [
                                        '.semi-modal-close',
                                        'button[aria-label="Close"]',
                                        'button[aria-label="关闭"]',
                                        '[class*="close"]',
                                        'button:has-text("关闭")',
                                        'button:has-text("Close")',
                                        'button:has-text("×")',
                                        'button:has-text("✕")'
                                    ]

                                    for close_sel in close_selectors:
                                        try:
                                            close_btn = await popup.query_selector(close_sel)
                                            if close_btn and await close_btn.is_visible():
                                                await close_btn.click()
                                                await page.wait_for_timeout(800)
                                                print(f"✅ 关闭了弹窗: {close_sel}")
                                                popup_closed = True
                                                break
                                        except:
                                            continue

                                    # 如果没找到关闭按钮，尝试ESC键
                                    if not popup_closed:
                                        try:
                                            await page.keyboard.press('Escape')
                                            await page.wait_for_timeout(500)
                                            print(f"✅ 使用ESC关闭了弹窗")
                                            popup_closed = True
                                        except:
                                            pass

                                    break  # 处理完一个弹窗后跳出
                        except:
                            continue

                    if not popup_closed:
                        print(f"✅ 第{attempt + 1}次检查完成，未发现弹窗")
                        break

                    # 等待页面重新稳定
                    await page.wait_for_timeout(1000)

                except Exception as e:
                    print(f"⚠️ 处理弹窗时出现异常: {e}")
                    pass

            # 智能查找邮箱输入框，增加重试机制
            email_selectors = [
                'input[name="username"]',
                'input[type="email"]',
                'input[name="email"]',
                'input[name="account"]',
                'input[id*="email" i]',
                'input[placeholder*="邮箱" i]',
                'input[placeholder*="Email" i]',
                'input[placeholder*="用户名" i]',
                'input[placeholder*="账号" i]',
                'input[autocomplete="username"]',
                'input[type="text"]',  # 最后尝试所有文本输入框
            ]

            email_input = None

            # 多次尝试查找输入框
            for attempt in range(3):
                print(f"🔍 第{attempt + 1}次查找邮箱输入框...")

                # 等待可能的动态加载
                await page.wait_for_timeout(1000)

                for sel in email_selectors:
                    try:
                        elements = await page.query_selector_all(sel)
                        for element in elements:
                            if await element.is_visible():
                                # 检查元素是否可用
                                input_name = await element.get_attribute('name')
                                input_type = await element.get_attribute('type')
                                input_placeholder = await element.get_attribute('placeholder')

                                print(f"  找到输入框: name={input_name}, type={input_type}, placeholder={input_placeholder}")

                                email_input = element
                                break
                        if email_input:
                            break
                    except:
                        continue

                if email_input:
                    print(f"✅ 找到可用的邮箱输入框")
                    break
                else:
                    print(f"⚠️ 第{attempt + 1}次未找到输入框，尝试刷新或等待")
                    # 尝试滚动页面
                    await page.keyboard.press('Home')
                    await page.wait_for_timeout(500)

            if not email_input:
                # 调试信息：查看页面状态
                try:
                    current_url = page.url
                    page_title = await page.title()
                    print(f"🔍 当前页面: {current_url}")
                    print(f"🔍 页面标题: {page_title}")

                    all_inputs = await page.query_selector_all('input')
                    print(f"🔍 页面上共有 {len(all_inputs)} 个输入框:")
                    for i, inp in enumerate(all_inputs):
                        input_type = await inp.get_attribute('type')
                        input_name = await inp.get_attribute('name')
                        input_id = await inp.get_attribute('id')
                        input_placeholder = await inp.get_attribute('placeholder')
                        input_visible = await inp.is_visible()
                        print(f"  {i+1}. type={input_type}, name={input_name}, id={input_id}, placeholder={input_placeholder}, visible={input_visible}")
                except Exception as debug_e:
                    print(f"🔍 调试失败: {debug_e}")

                return {"success": False, "error": "Email input field not found"}

            # 查找密码输入框
            password_input = await page.query_selector('input[type="password"]')
            if not password_input:
                return {"success": False, "error": "Password input field not found"}

            # 填写邮箱和密码
            await email_input.fill(self.auth_config.username)
            await password_input.fill(self.auth_config.password)

            # 查找并点击登录按钮
            login_selectors = [
                'button[type="submit"]',
                'button:has-text("登录")',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'button:has-text("Sign In")',
                'button.semi-button:has-text("登录")',
            ]
            login_button = None
            for sel in login_selectors:
                try:
                    login_button = await page.query_selector(sel)
                    if login_button:
                        break
                except:
                    continue

            if not login_button:
                return {"success": False, "error": "Login button not found"}

            await login_button.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

            # 检查是否登录成功
            current_url = page.url
            if "login" in current_url.lower():
                # 检查是否有错误提示
                error_msg = await page.query_selector('.error, .alert-danger, [class*="error"]')
                if error_msg:
                    error_text = await error_msg.inner_text()
                    return {"success": False, "error": f"Login failed: {error_text}"}
                return {"success": False, "error": "Login failed - still on login page"}

            # 获取 cookies
            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            return {"success": True, "cookies": cookies_dict}

        except Exception as e:
            return {"success": False, "error": f"Email auth failed: {str(e)}"}


class GitHubAuthenticator(Authenticator):
    """GitHub OAuth 认证"""

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用 GitHub 登录"""
        try:
            print(f"ℹ️ Starting GitHub authentication")

            # 访问登录页
            await page.goto(self.provider_config.get_login_url())
            await page.wait_for_load_state("domcontentloaded")

            # 查找并点击 GitHub 登录按钮（扩展匹配）
            github_button = None
            for sel in [
                'button:has-text("GitHub")',
                'a:has-text("GitHub")',
                'text=使用 GitHub',
                'a[href*="github.com"]',
            ]:
                try:
                    github_button = await page.query_selector(sel)
                    if github_button:
                        break
                except:
                    continue

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
            # 等待回调到目标站点（使用正则匹配，避免不支持的 lambda 谓词）
            target_pattern = re.compile(rf"^{re.escape(self.provider_config.base_url)}.*")
            await page.wait_for_url(target_pattern, timeout=20000)

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

            # 尝试关闭可能的遮罩/公告弹窗
            try:
                await page.keyboard.press('Escape')
                await page.wait_for_timeout(300)
                close_btn = await page.query_selector('.semi-modal .semi-modal-close, [aria-label="Close"], button:has-text("关闭"), button:has-text("我知道了")')
                if close_btn:
                    await close_btn.click()
                    await page.wait_for_timeout(300)
            except:
                pass

            # 查找并点击 LinuxDO 登录按钮（扩展匹配）
            linux_button = None
            for sel in [
                'button:has-text("LinuxDO")',
                'a:has-text("LinuxDO")',
                'button:has-text("Linux.do")',
                'button:has-text("LinuxDO 登录")',
                'a[href*="linux.do"]',
                'text=使用 LinuxDO',
            ]:
                try:
                    linux_button = await page.query_selector(sel)
                    if linux_button:
                        break
                except:
                    continue

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
            # 等待回调到目标站点（使用正则匹配，避免不支持的 lambda 谓词）
            target_pattern = re.compile(rf"^{re.escape(self.provider_config.base_url)}.*")
            await page.wait_for_url(target_pattern, timeout=20000)

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
    elif auth_config.method == "email":
        return EmailAuthenticator(auth_config, provider_config)
    elif auth_config.method == "github":
        return GitHubAuthenticator(auth_config, provider_config)
    elif auth_config.method == "linux.do":
        return LinuxDoAuthenticator(auth_config, provider_config)
    else:
        raise ValueError(f"Unknown auth method: {auth_config.method}")
