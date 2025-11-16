"""
邮箱密码认证器 - 使用用户名和密码进行表单登录
"""

from typing import Dict, Any, Optional, Tuple
from playwright.async_api import Page, BrowserContext

from utils.auth.base import Authenticator, logger
from utils.sanitizer import sanitize_exception
from utils.session_cache import SessionCache
from utils.constants import (
    EMAIL_INPUT_SELECTORS,
    PASSWORD_INPUT_SELECTORS,
    LOGIN_BUTTON_SELECTORS,
    POPUP_CLOSE_SELECTORS,
    TimeoutConfig,
)

# 会话缓存实例
session_cache = SessionCache()


class EmailAuthenticator(Authenticator):
    """邮箱密码认证"""

    async def _close_popups(self, page: Page):
        """关闭可能的弹窗"""
        try:
            await page.keyboard.press('Escape')
            await page.wait_for_timeout(TimeoutConfig.VERY_SHORT_WAIT)
            for sel in POPUP_CLOSE_SELECTORS:
                try:
                    close_btn = await page.query_selector(sel)
                    if close_btn:
                        await close_btn.click()
                        await page.wait_for_timeout(TimeoutConfig.VERY_SHORT_WAIT)
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

    async def _check_login_success(self, page: Page, context: BrowserContext) -> Tuple[bool, Optional[str]]:
        """检查登录是否成功（增强版 - 验证真实 session cookies）"""
        current_url = page.url
        logger.info(f"🔍 [{self.auth_config.username}] 登录后URL: {current_url}")

        # 方法1: 检查URL变化
        login_in_url = "login" in current_url.lower()
        if not login_in_url:
            logger.info(f"✅ [{self.auth_config.username}] URL已变化，登录可能成功")
        else:
            logger.warning(f"⚠️ [{self.auth_config.username}] 仍在登录页面，检查其他登录指标...")

        # 方法2: 检查页面标题
        page_title_indicates_success = False
        try:
            page_title = await page.title()
            logger.info(f"🔍 [{self.auth_config.username}] 页面标题: {page_title}")
            if "login" not in page_title.lower() and "console" in page_title.lower():
                logger.info(f"✅ [{self.auth_config.username}] 页面标题显示已登录")
                page_title_indicates_success = True
        except:
            pass

        # 方法3: 检查用户界面元素
        user_elements_found = False
        try:
            user_elements = await page.query_selector_all(
                '[class*="user"], [class*="avatar"], [class*="profile"], button:has-text("退出"), button:has-text("Logout")'
            )
            if user_elements:
                logger.info(f"✅ [{self.auth_config.username}] 找到用户界面元素")
                user_elements_found = True
        except:
            pass

        # 方法4: 检查错误提示
        error_msg = await self._check_error_messages(page)
        if error_msg:
            return False, error_msg

        # ==================== 增强验证（2025版）：验证真实 session cookies ====================
        # 前面的检查只能验证 UI 层面的登录，不能保证后端 API 认证成功
        # 阿里云 WAF 可能导致前端正常但后端 API 被拦截

        # 等待一段时间，让 session cookies 设置
        await page.wait_for_timeout(TimeoutConfig.SHORT_WAIT_3)

        # 获取当前所有 cookies
        all_cookies = await context.cookies()
        cookies_dict = {cookie["name"]: cookie["value"] for cookie in all_cookies}

        logger.info(f"🍪 [{self.auth_config.username}] 当前 cookies 数量: {len(cookies_dict)}")
        logger.info(f"🍪 [{self.auth_config.username}] Cookie 列表: {list(cookies_dict.keys())}")

        # 检查是否只有 WAF cookies（没有真实 session cookies）
        waf_only_cookies = ['acw_tc', 'cdn_sec_tc', 'acw_sc__v2', '__cf_bm', 'cf_clearance']
        session_cookie_names = ['session', 'sessionid', 'connect.sid', 'JSESSIONID', 'PHPSESSID']

        has_waf_cookies = any(name in cookies_dict for name in waf_only_cookies)
        has_session_cookies = any(name in cookies_dict for name in session_cookie_names)

        if has_waf_cookies:
            waf_cookie_list = [name for name in waf_only_cookies if name in cookies_dict]
            logger.info(f"🛡️ [{self.auth_config.username}] 检测到 WAF cookies: {waf_cookie_list}")

        if not has_session_cookies:
            logger.warning(f"⚠️ [{self.auth_config.username}] 未检测到标准 session cookies")

            # 检查是否只有 WAF cookies（这是 WAF 拦截的典型特征）
            non_waf_cookies = [name for name in cookies_dict.keys() if name not in waf_only_cookies]
            if len(non_waf_cookies) == 0:
                logger.error(f"❌ [{self.auth_config.username}] 只有 WAF cookies，疑似被阿里云 WAF 拦截")
                return False, "Login blocked by WAF - only WAF cookies obtained, no session cookies"
            elif len(non_waf_cookies) < 3:
                logger.warning(f"⚠️ [{self.auth_config.username}] 非 WAF cookies 很少 ({non_waf_cookies})，可能被 WAF 部分拦截")
        else:
            session_cookie_list = [name for name in session_cookie_names if name in cookies_dict]
            logger.info(f"✅ [{self.auth_config.username}] 找到 session cookies: {session_cookie_list}")

        # 方法5: 验证 localStorage 是否有用户数据（阿里云 WAF 拦截时 localStorage 会是空的）
        try:
            await page.wait_for_timeout(TimeoutConfig.SHORT_WAIT_2)
            user_data = await page.evaluate("() => localStorage.getItem('user')")
            if user_data:
                logger.info(f"✅ [{self.auth_config.username}] localStorage 包含用户数据")
            else:
                logger.warning(f"⚠️ [{self.auth_config.username}] localStorage 未包含用户数据（疑似 WAF 拦截）")

                # 如果同时没有 session cookies 和 localStorage 用户数据，很可能是 WAF 拦截
                if not has_session_cookies:
                    logger.error(f"❌ [{self.auth_config.username}] 登录失败：无 session cookies 且 localStorage 为空")
                    return False, "Login blocked by WAF - no session cookies and empty localStorage"
        except Exception as e:
            logger.warning(f"⚠️ [{self.auth_config.username}] localStorage 检查失败: {e}")

        # 综合判断
        if login_in_url:
            return False, "Login failed - still on login page (may need captcha)"

        # 如果 UI 指标正常（URL变化或用户元素）且有真实 cookies，则认为成功
        if (not login_in_url or user_elements_found or page_title_indicates_success):
            if has_session_cookies or len(cookies_dict) > 5:  # 有 session cookies 或 cookies 数量足够多
                logger.info(f"✅ [{self.auth_config.username}] 登录验证通过")
                return True, None
            else:
                logger.warning(f"⚠️ [{self.auth_config.username}] UI 正常但 cookies 不足，可能被 WAF 拦截")

                # ==================== cloudscraper 降级方案（2025版）====================
                # 检测到 WAF 拦截时，尝试使用 cloudscraper 重新获取 cookies
                logger.info(f"🔄 [{self.auth_config.username}] 尝试 cloudscraper 降级方案...")
                try:
                    # 调用 _get_waf_cookies 的 cloudscraper 降级逻辑
                    # 先尝试从当前页面重新获取
                    await page.wait_for_timeout(TimeoutConfig.SHORT_WAIT_3)
                    retry_cookies = await context.cookies()
                    retry_cookies_dict = {cookie["name"]: cookie["value"] for cookie in retry_cookies}

                    # 如果仍然只有 WAF cookies，尝试 cloudscraper
                    if len(retry_cookies_dict) <= 3:
                        logger.info(f"🌐 [{self.auth_config.username}] 调用 cloudscraper 获取真实 session cookies...")

                        # 使用 cloudscraper 访问登录页
                        from utils.auth.base import CloudscraperHelper
                        import os

                        proxy = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
                        cf_cookies = await CloudscraperHelper.get_cf_cookies(
                            self.provider_config.get_login_url(),
                            proxy
                        )

                        if cf_cookies and len(cf_cookies) > 3:
                            logger.info(f"✅ [{self.auth_config.username}] Cloudscraper 获取到 {len(cf_cookies)} 个 cookies")

                            # 注入 cloudscraper 获取的 cookies
                            from urllib.parse import urlparse
                            parsed = urlparse(self.provider_config.get_login_url())
                            domain = parsed.netloc

                            for name, value in cf_cookies.items():
                                try:
                                    await context.add_cookies([{
                                        "name": name,
                                        "value": value,
                                        "domain": domain,
                                        "path": "/"
                                    }])
                                except Exception as cookie_error:
                                    logger.debug(f"⚠️ [{self.auth_config.username}] 注入 cookie {name} 失败: {cookie_error}")

                            # 重新检查 cookies
                            final_cookies = await context.cookies()
                            final_cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

                            if len(final_cookies_dict) > 5:
                                logger.info(f"✅ [{self.auth_config.username}] Cloudscraper 降级成功，现在有 {len(final_cookies_dict)} 个 cookies")
                                return True, None
                            else:
                                logger.warning(f"⚠️ [{self.auth_config.username}] Cloudscraper 降级后仍然 cookies 不足")
                        else:
                            logger.warning(f"⚠️ [{self.auth_config.username}] Cloudscraper 未能获取足够的 cookies")

                except Exception as cs_error:
                    logger.warning(f"⚠️ [{self.auth_config.username}] Cloudscraper 降级失败: {cs_error}")

                # 如果 cloudscraper 降级也失败，返回 WAF 拦截错误
                return False, "Login may be blocked by WAF - insufficient cookies (cloudscraper failed)"

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
            await page.wait_for_timeout(TimeoutConfig.SHORT_WAIT_2)

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

            # ==================== 增强 WAF 绕过（2025版）====================
            # 登录提交后，给予更长的等待时间让服务器设置 session cookies
            # 阿里云 WAF 需要额外时间处理请求

            logger.info(f"⏳ [{self.auth_config.username}] 等待登录响应和 session cookies 设置...")
            try:
                # 方案1: 等待 networkidle（最多10秒）
                await page.wait_for_load_state("networkidle", timeout=TimeoutConfig.MEDIUM_WAIT_10)
                logger.info(f"✅ [{self.auth_config.username}] 页面网络已空闲")
            except Exception:
                logger.warning(f"⚠️ [{self.auth_config.username}] networkidle 超时，继续...")

            # 方案2: 额外等待3-5秒，让 WAF 和服务器设置 cookies
            await page.wait_for_timeout(TimeoutConfig.SHORT_WAIT_3)

            # 方案3: 尝试简单的页面交互，触发可能的 JavaScript 执行
            try:
                logger.info(f"🔄 [{self.auth_config.username}] 尝试页面交互以触发 cookies 设置...")
                await page.mouse.move(100, 100)  # 简单的鼠标移动
                await page.wait_for_timeout(TimeoutConfig.SHORT_WAIT_2)
            except:
                pass

            success, error_msg = await self._check_login_success(page, context)
            if not success:
                return {"success": False, "error": error_msg}

            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            if "session" not in cookies_dict and "sessionid" not in cookies_dict:
                logger.warning(f"⚠️ [{self.auth_config.username}] 未找到session cookie")

            logger.info(f"✅ [{self.auth_config.username}] 邮箱认证完成，获取到 {len(cookies_dict)} 个cookies")

            # 优先从localStorage提取用户ID，失败则尝试API
            user_id, username = await self._extract_user_from_localstorage(page)
            if not user_id:
                logger.info(f"ℹ️ [{self.auth_config.username}] localStorage未获取到用户ID，尝试API")
                user_id, username = await self._extract_user_info(page, cookies_dict)

            # 保存会话缓存
            try:
                session_cache.save(
                    account_name=self.account_name,
                    provider=self.provider_config.name,
                    cookies=final_cookies,
                    user_id=user_id,
                    username=username,
                    expiry_hours=24
                )
                logger.info(f"✅ [{self.auth_config.username}] 会话已缓存（24小时有效）")
            except Exception as cache_error:
                logger.warning(f"⚠️ [{self.auth_config.username}] 缓存保存失败: {cache_error}")

            return {"success": True, "cookies": cookies_dict, "user_id": user_id, "username": username}

        except Exception as e:
            return {"success": False, "error": f"Email auth failed: {sanitize_exception(e)}"}
