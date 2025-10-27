"""
认证模块 - 处理不同的认证方式
"""

import os
import asyncio
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

            print(f"🔍 [{self.auth_config.username}] 访问登录页: {self.provider_config.get_login_url()}")
            # 访问登录页
            await page.goto(self.provider_config.get_login_url())
            await page.wait_for_load_state("domcontentloaded")
            # 等待页面主要内容渲染
            await page.wait_for_timeout(1500)

            # 尝试关闭可能的弹窗
            try:
                await page.keyboard.press('Escape')
                await page.wait_for_timeout(300)
                close_selectors = [
                    '.semi-modal .semi-modal-close',
                    '[aria-label="Close"]',
                    'button:has-text("关闭")',
                    'button:has-text("我知道了")',
                    'button:has-text("取消")',
                ]
                for sel in close_selectors:
                    try:
                        close_btn = await page.query_selector(sel)
                        if close_btn:
                            await close_btn.click()
                            await page.wait_for_timeout(300)
                            break
                    except:
                        continue
            except:
                pass

            # 如有"邮箱登录"tab，优先点击
            print(f"🔍 [{self.auth_config.username}] 查找邮箱登录选项...")
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
                        print(f"✅ [{self.auth_config.username}] 找到邮箱登录选项: {sel}")
                        await el.click()
                        await page.wait_for_timeout(800)
                        break
                except:
                    continue

            # 等待登录表单加载
            await page.wait_for_timeout(2000)

            # 查找邮箱输入框
            print(f"🔍 [{self.auth_config.username}] 查找邮箱输入框...")
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[name="username"]',
                'input[name="account"]',
                'input[id*="email" i]',
                'input[placeholder*="邮箱" i]',
                'input[placeholder*="Email" i]',
                'input[placeholder*="用户名" i]',
                'input[autocomplete="username"]',
            ]
            email_input = None
            found_selector = None
            for sel in email_selectors:
                try:
                    email_input = await page.query_selector(sel)
                    if email_input:
                        found_selector = sel
                        print(f"✅ [{self.auth_config.username}] 找到邮箱输入框: {sel}")
                        break
                except:
                    continue

            if not email_input:
                # 调试信息：输出页面当前内容
                try:
                    page_title = await page.title()
                    page_url = page.url
                    print(f"❌ [{self.auth_config.username}] 邮箱输入框未找到")
                    print(f"   当前页面: {page_title}")
                    print(f"   当前URL: {page_url}")

                    # 查找所有输入框
                    all_inputs = await page.query_selector_all('input')
                    print(f"   页面共有 {len(all_inputs)} 个输入框")
                    for i, inp in enumerate(all_inputs[:5]):  # 只显示前5个
                        try:
                            inp_type = await inp.get_attribute('type')
                            inp_name = await inp.get_attribute('name')
                            inp_placeholder = await inp.get_attribute('placeholder')
                            print(f"     输入框{i+1}: type={inp_type}, name={inp_name}, placeholder={inp_placeholder}")
                        except:
                            print(f"     输入框{i+1}: 无法获取属性")
                except Exception as e:
                    print(f"   调试信息获取失败: {e}")

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

            print(f"🔑 [{self.auth_config.username}] 点击登录按钮...")
            await login_button.click()

            # 等待页面跳转或响应
            try:
                # 等待页面变化，可能是跳转或内容更新
                await page.wait_for_load_state("networkidle", timeout=10000)
                await page.wait_for_timeout(2000)  # 额外等待确保页面稳定
            except Exception:
                print(f"⚠️ [{self.auth_config.username}] 页面加载超时，继续检查登录状态...")

            # 多种方式检查登录是否成功
            current_url = page.url
            print(f"🔍 [{self.auth_config.username}] 登录后URL: {current_url}")

            # 方法1: 检查URL变化
            if "login" not in current_url.lower():
                print(f"✅ [{self.auth_config.username}] URL已变化，登录可能成功")
            else:
                print(f"⚠️ [{self.auth_config.username}] 仍在登录页面，检查其他登录指标...")

            # 方法2: 检查页面标题变化
            try:
                page_title = await page.title()
                print(f"🔍 [{self.auth_config.username}] 页面标题: {page_title}")
                if "login" not in page_title.lower() and "console" in page_title.lower():
                    print(f"✅ [{self.auth_config.username}] 页面标题显示已登录")
                else:
                    print(f"⚠️ [{self.auth_config.username}] 页面标题未显示登录")
            except:
                pass

            # 方法3: 检查是否有用户信息相关元素
            try:
                user_elements = await page.query_selector_all('[class*="user"], [class*="avatar"], [class*="profile"], button:has-text("退出"), button:has-text("Logout")')
                if user_elements:
                    print(f"✅ [{self.auth_config.username}] 找到用户界面元素，登录成功")
                else:
                    print(f"⚠️ [{self.auth_config.username}] 未找到用户界面元素")
            except:
                pass

            # 方法4: 检查是否有错误提示
            try:
                error_selectors = ['.error', '.alert-danger', '[class*="error"]', '.toast-error', '[role="alert"]']
                error_found = False
                for sel in error_selectors:
                    error_msg = await page.query_selector(sel)
                    if error_msg:
                        try:
                            error_text = await error_msg.inner_text()
                            if error_text.strip():
                                print(f"❌ [{self.auth_config.username}] 登录错误: {error_text}")
                                return {"success": False, "error": f"Login failed: {error_text}"}
                        except:
                            pass
                        error_found = True
                        break

                if error_found:
                    return {"success": False, "error": "Login failed - error message found"}
            except:
                pass

            # 最终判断：如果还在登录页，但没找到明确错误，可能是验证码或其他问题
            if "login" in current_url.lower():
                print(f"❌ [{self.auth_config.username}] 仍在登录页面，可能需要验证码或登录失败")
                return {"success": False, "error": "Login failed - still on login page (may need captcha)"}

            # 获取 cookies
            print(f"🍪 [{self.auth_config.username}] 获取登录cookies...")
            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            # 检查是否有session cookie
            if "session" not in cookies_dict and "sessionid" not in cookies_dict:
                print(f"⚠️ [{self.auth_config.username}] 未找到session cookie，但继续尝试...")

            print(f"✅ [{self.auth_config.username}] 邮箱认证完成，获取到 {len(cookies_dict)} 个cookies")
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
                    print("🔐 GitHub 2FA required - attempting to handle")
                    if not await self._handle_2fa(page):
                        return {"success": False, "error": "2FA authentication failed"}

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

    async def _handle_2fa(self, page: Page) -> bool:
        """处理 GitHub 2FA 认证"""
        try:
            print("🔐 处理 GitHub 2FA 认证...")

            # 等待 2FA 输入框出现
            await page.wait_for_selector('input[name="otp"]', timeout=10000)

            # 方法1: 从环境变量获取预先生成的 2FA 代码
            otp_code = os.getenv('GITHUB_2FA_CODE')
            if otp_code:
                print("📱 使用环境变量中的 2FA 代码")
                await page.fill('input[name="otp"]', otp_code)
                await page.click('button[type="submit"]', timeout=5000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                return True

            # 方法2: 使用 TOTP 密钥生成代码
            totp_secret = os.getenv('GITHUB_TOTP_SECRET')
            if totp_secret:
                print("🔑 使用 TOTP 密钥生成 2FA 代码")
                try:
                    import pyotp
                    totp = pyotp.TOTP(totp_secret)
                    otp_code = totp.now()
                    print(f"🔢 生成的 2FA 代码: {otp_code}")
                    await page.fill('input[name="otp"]', otp_code)
                    await page.click('button[type="submit"]', timeout=5000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    return True
                except ImportError:
                    print("❌ 需要安装 pyotp 库: pip install pyotp")
                except Exception as e:
                    print(f"❌ TOTP 生成失败: {e}")

            # 方法3: 尝试常见的备用恢复代码
            recovery_codes_str = os.getenv('GITHUB_RECOVERY_CODES')
            if recovery_codes_str:
                recovery_codes = recovery_codes_str.split(',')
                print(f"🔄 尝试使用恢复代码 (剩余 {len(recovery_codes)} 个)")
                for i, code in enumerate(recovery_codes):
                    try:
                        await page.fill('input[name="otp"]', code.strip())
                        await page.click('button[type="submit"]', timeout=5000)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        print(f"✅ 恢复代码 {i+1} 验证成功")
                        return True
                    except:
                        print(f"❌ 恢复代码 {i+1} 验证失败，尝试下一个...")
                        await page.wait_for_timeout(1000)
                        continue

            print("❌ 无法自动处理 2FA，请手动处理或配置以下环境变量:")
            print("   - GITHUB_2FA_CODE: 预先生成的 2FA 代码")
            print("   - GITHUB_TOTP_SECRET: TOTP 密钥")
            print("   - GITHUB_RECOVERY_CODES: 恢复代码列表 (逗号分隔)")
            return False

        except Exception as e:
            print(f"❌ 2FA 处理异常: {e}")
            return False


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

            # 查找并点击 LinuxDO 登录按钮（增强匹配）
            print(f"🔍 [{self.auth_config.username}] 查找LinuxDO登录按钮...")
            linux_button = None
            found_selector = None

            # 扩展的登录按钮选择器
            selectors = [
                # 精确匹配
                'button:has-text("LinuxDO")',
                'a:has-text("LinuxDO")',
                'button:has-text("Linux.do")',
                'button:has-text("LinuxDO 登录")',
                'a:has-text("使用 LinuxDO")',
                'text=使用 LinuxDO',
                'button:has-text("LinuxDO 账号登录")',

                # 模糊匹配
                'button:has-text("Linux")',
                'a:has-text("Linux")',
                'button:has-text("DO")',
                'a:has-text("DO")',

                # 链接匹配
                'a[href*="linux.do"]',
                'a[href*="linuxdo"]',
                'button[onclick*="linux"]',

                # 图标或类名匹配
                '[class*="linux"]',
                '[class*="linuxdo"]',
                '[data-provider*="linux"]',

                # 第三方OAuth通用匹配
                'button:has-text("第三方登录")',
                'button:has-text("其他登录方式")',
                'button:has-text("更多登录")',
                '.oauth-login button',
                '.third-party-login button',
            ]

            # 先等待页面完全加载
            await page.wait_for_timeout(2000)

            for sel in selectors:
                try:
                    linux_button = await page.query_selector(sel)
                    if linux_button:
                        found_selector = sel
                        print(f"✅ [{self.auth_config.username}] 找到LinuxDO登录选项: {sel}")
                        break
                except:
                    continue

            if not linux_button:
                # 调试信息：输出页面当前内容
                try:
                    page_title = await page.title()
                    page_url = page.url
                    print(f"❌ [{self.auth_config.username}] LinuxDO登录按钮未找到")
                    print(f"   当前页面: {page_title}")
                    print(f"   当前URL: {page_url}")

                    # 查找所有按钮和链接
                    all_buttons = await page.query_selector_all('button, a[href]')
                    print(f"   页面共有 {len(all_buttons)} 个按钮/链接")

                    # 显示前几个按钮的文本
                    for i, btn in enumerate(all_buttons[:8]):
                        try:
                            btn_text = await btn.inner_text()
                            btn_tag = await btn.evaluate('el => el.tagName.toLowerCase()')
                            if btn_text and btn_text.strip():
                                print(f"     {btn_tag}: {btn_text.strip()[:50]}")
                        except:
                            print(f"     按钮{i+1}: 无法获取文本")

                    # 如果仍然没找到，尝试点击可能的登录区域
                    login_containers = await page.query_selector_all('.login, .auth, .oauth, .third-party')
                    if login_containers:
                        print(f"   找到 {len(login_containers)} 个可能的登录容器")
                        for i, container in enumerate(login_containers[:2]):
                            try:
                                # 尝试点击容器内的第一个按钮
                                first_btn = await container.query_selector('button, a')
                                if first_btn:
                                    btn_text = await first_btn.inner_text()
                                    print(f"   尝试点击容器内按钮: {btn_text.strip()[:30]}")
                                    await first_btn.click()
                                    await page.wait_for_timeout(2000)

                                    # 检查是否跳转到Linux.do
                                    if "linux.do" in page.url:
                                        print(f"✅ [{self.auth_config.username}] 通过容器按钮成功跳转到Linux.do")
                                        linux_button = first_btn
                                        found_selector = f"container button ({btn_text.strip()[:20]})"
                                        break
                            except:
                                continue
                except Exception as e:
                    print(f"   调试信息获取失败: {e}")

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
