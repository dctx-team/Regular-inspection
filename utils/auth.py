"""
认证模块 - 处理不同的认证方式
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
    EMAIL_INPUT_SELECTORS,
    PASSWORD_INPUT_SELECTORS,
    LOGIN_BUTTON_SELECTORS,
    POPUP_CLOSE_SELECTORS,
    GITHUB_BUTTON_SELECTORS,
    LINUXDO_BUTTON_SELECTORS,
)

# 模块级logger
logger = setup_logger(__name__)


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
                "user_id": str,   # 用户ID（可选）
                "username": str,  # 用户名（可选）
                "error": str      # 错误信息（如果失败）
            }
        """
        pass

    async def _wait_for_cloudflare_challenge(self, page: Page, max_wait_seconds: int = 30) -> bool:
        """等待Cloudflare验证完成"""
        try:
            logger.info(f"🛡️ 检测到可能的Cloudflare验证，等待完成...")
            start_time = asyncio.get_event_loop().time()

            while asyncio.get_event_loop().time() - start_time < max_wait_seconds:
                current_url = page.url
                page_title = await page.title()

                # 检查是否是Cloudflare验证页
                if "verification" in page_title.lower() or "checking" in page_title.lower():
                    logger.info(f"   ⏳ Cloudflare验证中，继续等待... ({int(asyncio.get_event_loop().time() - start_time)}s)")
                    await page.wait_for_timeout(2000)
                    continue

                # 检查是否已经通过验证
                if "login" in current_url.lower() and "verification" not in page_title.lower():
                    logger.info(f"✅ Cloudflare验证完成")
                    return True

                # 检查按钮数量
                buttons = await page.query_selector_all('button, a[href]')
                if len(buttons) > 2:  # 如果有交互元素，说明可能已通过
                    logger.info(f"✅ 检测到交互元素，验证可能已完成")
                    return True

                await page.wait_for_timeout(2000)

            logger.warning(f"⚠️ Cloudflare验证等待超时({max_wait_seconds}s)")
            return False

        except Exception as e:
            logger.warning(f"⚠️ Cloudflare验证检测异常: {e}")
            return False

    def _get_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc

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
        except Exception as e:
            logger.warning(f"⚠️ 提取用户信息失败: {e}")
        return None, None

    async def _init_page_and_check_cloudflare(self, page: Page) -> bool:
        """初始化页面并检查Cloudflare"""
        await page.goto(self.provider_config.get_login_url())
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1500)

        page_title = await page.title()
        if "verification" in page_title.lower() or "checking" in page_title.lower():
            return await self._wait_for_cloudflare_challenge(page)
        return True

    def _log_cookies_info(self, cookies_dict: Dict[str, str], final_cookies: list, auth_type: str):
        """统一的cookies信息日志"""
        logger.info(f"🍪 [{self.auth_config.username}] {auth_type} OAuth认证完成，获取到 {len(cookies_dict)} 个cookies")

        found_key_cookies = [name for name in KEY_COOKIE_NAMES if name in cookies_dict]
        if found_key_cookies:
            for name in found_key_cookies:
                logger.info(f"   ✅ 找到关键cookie: {name}")
        else:
            logger.warning(f"   ⚠️ 未找到标准认证cookie")
            for i, name in enumerate(list(cookies_dict.keys())[:5]):
                logger.info(f"      {name}: ***")
            if len(cookies_dict) > 5:
                logger.info(f"      ... 还有 {len(cookies_dict) - 5} 个cookies")

    async def _fill_password(self, password_input, error_prefix: str = "Password input failed") -> Optional[str]:
        """安全填写密码"""
        try:
            await password_input.fill(self.auth_config.password)
            return None
        except Exception as e:
            return f"{error_prefix}: {sanitize_exception(e)}"


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

            # 尝试从用户信息API获取真实的用户标识
            user_id, username = await self._extract_user_info(page, cookies_dict)

            return {
                "success": True,
                "cookies": cookies_dict,
                "user_id": user_id,
                "username": username
            }

        except Exception as e:
            return {"success": False, "error": f"Cookies auth failed: {sanitize_exception(e)}"}


class EmailAuthenticator(Authenticator):
    """邮箱密码认证"""

    async def _close_popups(self, page: Page):
        """关闭可能的弹窗"""
        try:
            await page.keyboard.press('Escape')
            await page.wait_for_timeout(300)
            for sel in POPUP_CLOSE_SELECTORS:
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

    async def _find_and_click_email_tab(self, page: Page) -> bool:
        """查找并点击邮箱登录选项"""
        logger.info(f"🔍 [{self.auth_config.username}] 查找邮箱登录选项...")

        # 等待页面交互元素就绪
        try:
            await page.wait_for_timeout(1500)
        except:
            pass

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
                    logger.info(f"✅ [{self.auth_config.username}] 找到邮箱登录选项: {sel}")
                    await el.click()
                    await page.wait_for_timeout(800)
                    return True
            except:
                continue
        return False

    async def _find_email_input(self, page: Page):
        """查找邮箱输入框"""
        logger.info(f"🔍 [{self.auth_config.username}] 查找邮箱输入框...")
        email_input = None
        for sel in EMAIL_INPUT_SELECTORS:
            try:
                email_input = await page.query_selector(sel)
                if email_input:
                    logger.info(f"✅ [{self.auth_config.username}] 找到邮箱输入框: {sel}")
                    return email_input
            except:
                continue

        # 调试信息
        if not email_input:
            await self._debug_page_inputs(page)
        return None

    async def _debug_page_inputs(self, page: Page):
        """输出调试信息"""
        try:
            page_title = await page.title()
            page_url = page.url
            logger.error(f"❌ [{self.auth_config.username}] 邮箱输入框未找到")
            logger.info(f"   当前页面: {page_title}")
            logger.info(f"   当前URL: {page_url}")

            # 查找所有输入框
            all_inputs = await page.query_selector_all('input')
            logger.info(f"   页面共有 {len(all_inputs)} 个输入框")
            for i, inp in enumerate(all_inputs[:5]):  # 只显示前5个
                try:
                    inp_type = await inp.get_attribute('type')
                    inp_name = await inp.get_attribute('name')
                    inp_placeholder = await inp.get_attribute('placeholder')
                    logger.info(f"     输入框{i+1}: type={inp_type}, name={inp_name}, placeholder={inp_placeholder}")
                except:
                    logger.info(f"     输入框{i+1}: 无法获取属性")
        except Exception as e:
            logger.info(f"   调试信息获取失败: {e}")

    async def _find_and_click_login_button(self, page: Page):
        """查找并点击登录按钮"""
        for sel in LOGIN_BUTTON_SELECTORS:
            try:
                login_button = await page.query_selector(sel)
                if login_button:
                    return login_button
            except:
                continue
        return None

    async def _check_login_success(self, page: Page) -> Tuple[bool, Optional[str]]:
        """检查登录是否成功"""
        current_url = page.url
        logger.info(f"🔍 [{self.auth_config.username}] 登录后URL: {current_url}")

        # 方法1: 检查URL变化
        if "login" not in current_url.lower():
            logger.info(f"✅ [{self.auth_config.username}] URL已变化，登录可能成功")
            return True, None

        logger.warning(f"⚠️ [{self.auth_config.username}] 仍在登录页面，检查其他登录指标...")

        # 方法2: 检查页面标题
        try:
            page_title = await page.title()
            logger.info(f"🔍 [{self.auth_config.username}] 页面标题: {page_title}")
            if "login" not in page_title.lower() and "console" in page_title.lower():
                logger.info(f"✅ [{self.auth_config.username}] 页面标题显示已登录")
                return True, None
        except:
            pass

        # 方法3: 检查用户界面元素
        try:
            user_elements = await page.query_selector_all(
                '[class*="user"], [class*="avatar"], [class*="profile"], button:has-text("退出"), button:has-text("Logout")'
            )
            if user_elements:
                logger.info(f"✅ [{self.auth_config.username}] 找到用户界面元素，登录成功")
                return True, None
        except:
            pass

        # 方法4: 检查错误提示
        error_msg = await self._check_error_messages(page)
        if error_msg:
            return False, error_msg

        # 仍在登录页
        if "login" in current_url.lower():
            return False, "Login failed - still on login page (may need captcha)"

        return True, None

    async def _check_error_messages(self, page: Page) -> Optional[str]:
        """检查错误提示信息"""
        try:
            error_selectors = ['.error', '.alert-danger', '[class*="error"]', '.toast-error', '[role="alert"]']
            for sel in error_selectors:
                error_msg = await page.query_selector(sel)
                if error_msg:
                    try:
                        error_text = await error_msg.inner_text()
                        if error_text and error_text.strip():
                            # 检查是否是成功消息
                            success_keywords = ['成功', 'success', '登录成功', 'login success']
                            error_keywords = ['失败', '错误', 'error', 'invalid', 'incorrect', '验证码', 'captcha']

                            error_text_lower = error_text.lower()
                            is_success = any(keyword in error_text_lower for keyword in success_keywords)
                            is_real_error = any(keyword in error_text_lower for keyword in error_keywords)

                            if is_real_error:
                                logger.error(f"❌ [{self.auth_config.username}] 登录错误: {error_text}")
                                return f"Login failed: {error_text}"
                            elif is_success:
                                logger.info(f"✅ [{self.auth_config.username}] 检测到成功消息: {error_text}")
                            else:
                                logger.warning(f"⚠️ [{self.auth_config.username}] 检测到消息: {error_text}")
                    except:
                        pass
        except:
            pass
        return None

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用邮箱密码登录"""
        try:
            logger.info(f"ℹ️ Starting Email authentication")

            if not await self._init_page_and_check_cloudflare(page):
                return {"success": False, "error": "Cloudflare verification timeout"}

            await self._close_popups(page)
            await self._find_and_click_email_tab(page)
            await page.wait_for_timeout(2000)

            email_input = await self._find_email_input(page)
            if not email_input:
                return {"success": False, "error": "Email input field not found"}

            password_input = await page.query_selector('input[type="password"]')
            if not password_input:
                return {"success": False, "error": "Password input field not found"}

            await email_input.fill(self.auth_config.username)

            error = await self._fill_password(password_input)
            if error:
                return {"success": False, "error": error}

            login_button = await self._find_and_click_login_button(page)
            if not login_button:
                return {"success": False, "error": "Login button not found"}

            logger.info(f"🔑 [{self.auth_config.username}] 点击登录按钮...")
            await login_button.click()

            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
                await page.wait_for_timeout(2000)
            except Exception:
                logger.warning(f"⚠️ [{self.auth_config.username}] 页面加载超时，继续检查登录状态...")

            success, error_msg = await self._check_login_success(page)
            if not success:
                return {"success": False, "error": error_msg}

            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            if "session" not in cookies_dict and "sessionid" not in cookies_dict:
                logger.warning(f"⚠️ [{self.auth_config.username}] 未找到session cookie")

            logger.info(f"✅ [{self.auth_config.username}] 邮箱认证完成，获取到 {len(cookies_dict)} 个cookies")
            user_id, username = await self._extract_user_info(page, cookies_dict)

            return {"success": True, "cookies": cookies_dict, "user_id": user_id, "username": username}

        except Exception as e:
            return {"success": False, "error": f"Email auth failed: {sanitize_exception(e)}"}


class GitHubAuthenticator(Authenticator):
    """GitHub OAuth 认证"""

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用 GitHub 登录"""
        try:
            logger.info(f"ℹ️ Starting GitHub authentication")

            if not await self._init_page_and_check_cloudflare(page):
                return {"success": False, "error": "Cloudflare verification timeout"}

            github_button = None
            for sel in GITHUB_BUTTON_SELECTORS:
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

            if "github.com" in page.url:
                username_input = await page.query_selector('input[name="login"]')
                password_input = await page.query_selector('input[name="password"]')

                if username_input and password_input:
                    await username_input.fill(self.auth_config.username)
                    error = await self._fill_password(password_input)
                    if error:
                        return {"success": False, "error": error}

                    submit_button = await page.query_selector('input[type="submit"]')
                    if submit_button:
                        await submit_button.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)

                if "two-factor" in page.url or "2fa" in page.url.lower():
                    logger.info("🔐 GitHub 2FA required")
                    if not await self._handle_2fa(page):
                        return {"success": False, "error": "2FA authentication failed"}

                authorize_button = await page.query_selector('button[name="authorize"]')
                if authorize_button:
                    await authorize_button.click()
                    await page.wait_for_load_state("networkidle", timeout=10000)

            target_pattern = re.compile(rf"^{re.escape(self.provider_config.base_url)}.*")
            await page.wait_for_url(target_pattern, timeout=20000)

            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            self._log_cookies_info(cookies_dict, final_cookies, "GitHub")
            user_id, username = await self._extract_user_info(page, cookies_dict)

            return {"success": True, "cookies": cookies_dict, "user_id": user_id, "username": username}

        except Exception as e:
            return {"success": False, "error": f"GitHub auth failed: {sanitize_exception(e)}"}

    async def _handle_2fa(self, page: Page) -> bool:
        """处理 GitHub 2FA 认证"""
        try:
            logger.info("🔐 处理 GitHub 2FA 认证...")

            # 等待 2FA 输入框出现
            await page.wait_for_selector('input[name="otp"]', timeout=10000)

            # 方法1: 从环境变量获取预先生成的 2FA 代码
            otp_code = os.getenv('GITHUB_2FA_CODE')
            if otp_code:
                logger.info("📱 使用环境变量中的 2FA 代码")
                await page.fill('input[name="otp"]', otp_code)
                await page.click('button[type="submit"]', timeout=5000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                return True

            # 方法2: 使用 TOTP 密钥生成代码
            totp_secret = os.getenv('GITHUB_TOTP_SECRET')
            if totp_secret:
                logger.info("🔑 使用 TOTP 密钥生成 2FA 代码")
                try:
                    import pyotp
                    totp = pyotp.TOTP(totp_secret)
                    otp_code = totp.now()
                    logger.info(f"🔢 生成的 2FA 代码: {otp_code}")
                    await page.fill('input[name="otp"]', otp_code)
                    await page.click('button[type="submit"]', timeout=5000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    return True
                except ImportError:
                    logger.error("❌ 需要安装 pyotp 库: pip install pyotp")
                except Exception as e:
                    logger.error(f"❌ TOTP 生成失败: {e}")

            # 方法3: 尝试常见的备用恢复代码
            recovery_codes_str = os.getenv('GITHUB_RECOVERY_CODES')
            if recovery_codes_str:
                recovery_codes = recovery_codes_str.split(',')
                logger.info(f"🔄 尝试使用恢复代码 (剩余 {len(recovery_codes)} 个)")
                for i, code in enumerate(recovery_codes):
                    try:
                        await page.fill('input[name="otp"]', code.strip())
                        await page.click('button[type="submit"]', timeout=5000)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info(f"✅ 恢复代码 {i+1} 验证成功")
                        return True
                    except:
                        logger.error(f"❌ 恢复代码 {i+1} 验证失败，尝试下一个...")
                        await page.wait_for_timeout(1000)
                        continue

            logger.error("❌ 无法自动处理 2FA，请手动处理或配置以下环境变量:")
            logger.info("   - GITHUB_2FA_CODE: 预先生成的 2FA 代码")
            logger.info("   - GITHUB_TOTP_SECRET: TOTP 密钥")
            logger.info("   - GITHUB_RECOVERY_CODES: 恢复代码列表 (逗号分隔)")
            return False

        except Exception as e:
            logger.error(f"❌ 2FA 处理异常: {e}")
            return False


class LinuxDoAuthenticator(Authenticator):
    """Linux.do OAuth 认证"""

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用 Linux.do 登录"""
        try:
            logger.info(f"ℹ️ Starting Linux.do authentication")

            if not await self._init_page_and_check_cloudflare(page):
                return {"success": False, "error": "Cloudflare verification timeout"}

            try:
                await page.keyboard.press('Escape')
                await page.wait_for_timeout(300)
                close_btn = await page.query_selector('.semi-modal .semi-modal-close, [aria-label="Close"], button:has-text("关闭"), button:has-text("我知道了")')
                if close_btn:
                    await close_btn.click()
                    await page.wait_for_timeout(300)
            except:
                pass

            logger.info(f"🔍 [{self.auth_config.username}] 查找LinuxDO登录按钮...")
            linux_button = None
            await page.wait_for_timeout(2000)

            for sel in LINUXDO_BUTTON_SELECTORS:
                try:
                    linux_button = await page.query_selector(sel)
                    if linux_button:
                        logger.info(f"✅ [{self.auth_config.username}] 找到LinuxDO登录选项: {sel}")
                        break
                except:
                    continue

            if not linux_button:
                try:
                    page_title = await page.title()
                    logger.error(f"❌ [{self.auth_config.username}] LinuxDO登录按钮未找到")
                    logger.info(f"   当前页面: {page_title}, URL: {page.url}")

                    all_buttons = await page.query_selector_all('button, a[href]')
                    logger.info(f"   页面共有 {len(all_buttons)} 个按钮/链接")

                    for i, btn in enumerate(all_buttons[:8]):
                        try:
                            btn_text = await btn.inner_text()
                            if btn_text and btn_text.strip():
                                logger.info(f"     {await btn.evaluate('el => el.tagName.toLowerCase()')}: {btn_text.strip()[:50]}")
                        except:
                            pass

                    login_containers = await page.query_selector_all('.login, .auth, .oauth, .third-party')
                    if login_containers:
                        logger.info(f"   找到 {len(login_containers)} 个可能的登录容器")
                        for container in login_containers[:2]:
                            try:
                                first_btn = await container.query_selector('button, a')
                                if first_btn:
                                    btn_text = await first_btn.inner_text()
                                    logger.info(f"   尝试点击容器内按钮: {btn_text.strip()[:30]}")
                                    await first_btn.click()
                                    await page.wait_for_timeout(2000)

                                    if "linux.do" in page.url:
                                        logger.info(f"✅ [{self.auth_config.username}] 通过容器按钮成功跳转到Linux.do")
                                        linux_button = first_btn
                                        break
                            except:
                                continue
                except Exception as e:
                    logger.info(f"   调试信息获取失败: {e}")

            if not linux_button:
                return {"success": False, "error": "LinuxDO login button not found"}

            await linux_button.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

            if "linux.do" in page.url:
                username_input = await page.query_selector('input[id="login-account-name"]')
                password_input = await page.query_selector('input[id="login-account-password"]')

                if username_input and password_input:
                    await username_input.fill(self.auth_config.username)
                    error = await self._fill_password(password_input)
                    if error:
                        return {"success": False, "error": error}

                    login_button = await page.query_selector('button[id="login-button"]')
                    if login_button:
                        await login_button.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)

            target_pattern = re.compile(rf"^{re.escape(self.provider_config.base_url)}.*")
            await page.wait_for_url(target_pattern, timeout=20000)

            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            self._log_cookies_info(cookies_dict, final_cookies, "LinuxDO")
            user_id, username = await self._extract_user_info(page, cookies_dict)

            return {"success": True, "cookies": cookies_dict, "user_id": user_id, "username": username}

        except Exception as e:
            return {"success": False, "error": f"Linux.do auth failed: {sanitize_exception(e)}"}


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
