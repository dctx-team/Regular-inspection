"""
Linux.do OAuth 认证器 - 使用 Linux.do OAuth 进行第三方登录
"""

import os
from typing import Dict, Any, Optional
from playwright.async_api import Page, BrowserContext

from utils.auth.base import Authenticator, logger
from utils.sanitizer import sanitize_exception
from utils.session_cache import SessionCache
from utils.ci_config import CIConfig
from utils.constants import DEFAULT_USER_AGENT, TimeoutConfig

# 会话缓存实例
session_cache = SessionCache()


class LinuxDoAuthenticator(Authenticator):
    """Linux.do OAuth 认证"""
    
    def _should_skip_in_ci(self) -> bool:
        """检查是否应该在 CI 环境中跳过 Linux.do 认证"""
        return CIConfig.should_skip_auth_method("linux.do")

    async def _get_auth_client_id(self, cookies: Dict[str, str], page: Page = None) -> Optional[Dict[str, Any]]:
        """获取 LinuxDO OAuth 客户端 ID"""
        try:
            import httpx
            headers = {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "application/json",
                "Referer": self.provider_config.base_url,
                "Origin": self.provider_config.base_url,
                self.provider_config.api_user_key: "-1"  # 使用-1表示未登录用户
            }

            # 优先尝试通过浏览器获取（绕过 Cloudflare）
            if page:
                logger.info(f"🌐 [{self.auth_config.username}] 尝试通过浏览器直接获取 client_id...")
                try:
                    # 使用浏览器的 evaluate 来发送 API 请求
                    status_result = await page.evaluate(f"""
                        async () => {{
                            try {{
                                const response = await fetch('{self.provider_config.get_status_url()}', {{
                                    method: 'GET',
                                    headers: {{
                                        'Accept': 'application/json',
                                        '{self.provider_config.api_user_key}': '-1'
                                    }},
                                    credentials: 'include'
                                }});
                                if (!response.ok) {{
                                    return {{ success: false, error: `HTTP ${{response.status}}` }};
                                }}
                                
                                // 检查响应类型是否为 JSON
                                const contentType = response.headers.get('content-type');
                                if (!contentType || !contentType.includes('application/json')) {{
                                    const text = await response.text();
                                    const preview = text.substring(0, 100);
                                    return {{ success: false, error: `Not JSON response (got ${{contentType}}): ${{preview}}` }};
                                }}
                                
                                const data = await response.json();
                                return {{ success: true, data: data }};
                            }} catch (e) {{
                                return {{ success: false, error: e.toString() }};
                            }}
                        }}
                    """)
                    
                    if status_result and status_result.get('success'):
                        data = status_result.get('data')
                        logger.info(f"✅ [{self.auth_config.username}] 通过浏览器成功获取 API 响应")
                        
                        if data.get("success"):
                            status_data = data.get("data", {})
                            if status_data.get("linuxdo_oauth", False):
                                client_id = status_data.get("linuxdo_client_id", "")
                                if client_id:
                                    logger.info(f"✅ [{self.auth_config.username}] 获取到 LinuxDO client_id: {client_id}")
                                    return {"client_id": client_id}
                    
                    error_msg = status_result.get('error', 'Unknown error') if status_result else 'No result'
                    logger.error(f"❌ [{self.auth_config.username}] 浏览器方式失败: {error_msg}")
                    return None
                except Exception as browser_error:
                    logger.error(f"❌ [{self.auth_config.username}] 浏览器 API 请求异常: {browser_error}")
                    return None
            
            # 如果没有 page 对象，返回错误（不再使用 httpx 回退，因为会被 Cloudflare 阻止）
            logger.error(f"❌ [{self.auth_config.username}] 需要浏览器 page 对象来绕过 Cloudflare，无法使用 httpx")
            return None
        except Exception as e:
            logger.error(f"❌ [{self.auth_config.username}] 获取 client_id 异常: {e}")
            return None

    async def _get_auth_state(self, cookies: Dict[str, str], page: Page = None) -> Optional[Dict[str, Any]]:
        """获取 OAuth 认证状态"""
        try:
            # 强制使用浏览器获取（避免 httpx 被 Cloudflare 阻止）
            if page:
                logger.info(f"🌐 [{self.auth_config.username}] 通过浏览器直接获取 auth_state...")
                try:
                    state_result = await page.evaluate(f"""
                        async () => {{
                            try {{
                                const response = await fetch('{self.provider_config.get_auth_state_url()}', {{
                                    method: 'GET',
                                    headers: {{
                                        'Accept': 'application/json',
                                        '{self.provider_config.api_user_key}': '-1'
                                    }},
                                    credentials: 'include'
                                }});
                                if (!response.ok) {{
                                    return {{ success: false, error: `HTTP ${{response.status}}` }};
                                }}
                                
                                // 检查响应类型是否为 JSON
                                const contentType = response.headers.get('content-type');
                                if (!contentType || !contentType.includes('application/json')) {{
                                    const text = await response.text();
                                    const preview = text.substring(0, 100);
                                    return {{ success: false, error: `Not JSON response (got ${{contentType}}): ${{preview}}` }};
                                }}
                                
                                const data = await response.json();
                                return {{ success: true, data: data }};
                            }} catch (e) {{
                                return {{ success: false, error: e.toString() }};
                            }}
                        }}
                    """)
                    
                    if state_result and state_result.get('success'):
                        data = state_result.get('data')
                        if data.get("success"):
                            auth_data = data.get("data")
                            logger.info(f"✅ [{self.auth_config.username}] 获取到 auth_state: {auth_data}")
                            # 浏览器方式不需要额外 cookies，直接返回
                            return {
                                "auth_data": auth_data,
                                "cookies": []  # 浏览器已经有所有需要的 cookies
                            }
                    
                    error_msg = state_result.get('error', 'Unknown error') if state_result else 'No result'
                    logger.error(f"❌ [{self.auth_config.username}] 浏览器方式失败: {error_msg}")
                    return None
                except Exception as browser_error:
                    logger.error(f"❌ [{self.auth_config.username}] 浏览器 API 请求异常: {browser_error}")
                    return None
            
            # 如果没有 page 对象，返回错误
            logger.error(f"❌ [{self.auth_config.username}] 需要浏览器 page 对象来绕过 Cloudflare，无法使用 httpx")
            return None
        except Exception as e:
            logger.error(f"❌ [{self.auth_config.username}] 获取 auth_state 异常: {e}")
            return None

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用 Linux.do 登录"""
        try:
            logger.info(f"ℹ️ Starting Linux.do authentication")
            
            # 检查是否在 CI 环境中应该跳过
            if self._should_skip_in_ci():
                logger.warning(f"⚠️ [{self.auth_config.username}] CI 环境已配置跳过 Linux.do 认证")
                return {
                    "success": False,
                    "error": "Linux.do authentication skipped in CI environment (configured via CI_DISABLED_AUTH_METHODS)"
                }

            # 尝试加载缓存的会话
            cache_data = session_cache.load(self.account_name, self.provider_config.name)
            if cache_data:
                logger.info(f"🔄 [{self.auth_config.username}] 尝试使用缓存的会话...")
                try:
                    # 恢复cookies
                    cached_cookies = cache_data.get("cookies", [])
                    if cached_cookies:
                        await context.add_cookies(cached_cookies)
                        logger.info(f"✅ [{self.auth_config.username}] 已恢复 {len(cached_cookies)} 个缓存cookies")
                        
                        # 直接检查会话是否有效
                        cookies_dict = {cookie["name"]: cookie["value"] for cookie in cached_cookies}
                        user_id = cache_data.get("user_id")
                        username = cache_data.get("username")
                        
                        if user_id:
                            logger.info(f"✅ [{self.auth_config.username}] 缓存会话有效，跳过登录")
                            return {
                                "success": True,
                                "cookies": cookies_dict,
                                "user_id": user_id,
                                "username": username
                            }
                except Exception as e:
                    logger.warning(f"⚠️ [{self.auth_config.username}] 缓存会话恢复失败: {e}")
                    logger.info(f"ℹ️ [{self.auth_config.username}] 将执行新的登录流程")

            if not await self._init_page_and_check_cloudflare(page):
                return {"success": False, "error": "Cloudflare verification timeout"}

            # 第一步：等待额外时间确保 Cloudflare 验证完全通过
            # 在 CI 环境中增加等待时间
            is_ci = CIConfig.is_ci_environment()
            wait_time = 15000 if is_ci else 10000
            logger.info(f"⏳ [{self.auth_config.username}] 等待Cloudflare验证完全通过（{wait_time/1000}秒）...")
            await page.wait_for_timeout(wait_time)

            # 第二步：获取通过 Cloudflare 验证后的 cookies
            # 如果 Playwright 获取失败，尝试使用 cloudscraper 降级
            logger.info(f"🔑 [{self.auth_config.username}] 获取初始cookies...")
            initial_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in initial_cookies}

            # 如果 cookies 数量太少，尝试使用 cloudscraper 增强
            if len(cookies_dict) < 2:
                logger.warning(f"⚠️ [{self.auth_config.username}] Playwright 获取的 cookies 较少({len(cookies_dict)}个)，尝试 cloudscraper 增强...")
                enhanced_cookies = await self._get_waf_cookies(page, context, use_cloudscraper=True)
                if enhanced_cookies and len(enhanced_cookies) > len(cookies_dict):
                    cookies_dict = enhanced_cookies
                    logger.info(f"✅ [{self.auth_config.username}] Cloudscraper 增强成功，现有 {len(cookies_dict)} 个cookies")
            else:
                logger.info(f"🍪 [{self.auth_config.username}] 获取到 {len(cookies_dict)} 个cookies用于API请求")

            # 第三步：获取 OAuth client_id（带重试）
            max_retries = 3
            client_id_result = None
            
            for retry in range(max_retries):
                logger.info(f"🔑 [{self.auth_config.username}] 获取 LinuxDO OAuth client_id... (尝试 {retry + 1}/{max_retries})")
                
                # 每次重试前等待递增的时间，并采取不同的策略
                if retry > 0:
                    wait_time = 10000 * retry  # 10s, 20s (增加等待时间)
                    logger.info(f"⏳ 等待 {wait_time/1000}秒 后重试...")
                    await page.wait_for_timeout(wait_time)
                    
                    # 策略1：刷新页面
                    if retry == 1:
                        try:
                            logger.info(f"🔄 [{self.auth_config.username}] 刷新页面尝试...")
                            await page.reload(wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_timeout(5000)
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
                            await page.wait_for_timeout(10000)  # 增加到10秒
                        except Exception as e:
                            logger.warning(f"⚠️ [{self.auth_config.username}] 重新访问登录页失败: {e}")
                
                # 获取最新cookies
                current_cookies = await context.cookies()
                cookies_dict = {cookie["name"]: cookie["value"] for cookie in current_cookies}
                logger.info(f"🍪 [{self.auth_config.username}] 当前有 {len(cookies_dict)} 个cookies")
                
                client_id_result = await self._get_auth_client_id(cookies_dict, page)
                if client_id_result:
                    logger.info(f"✅ [{self.auth_config.username}] client_id获取成功")
                    break
                elif retry < max_retries - 1:
                    logger.warning(f"⚠️ [{self.auth_config.username}] 第 {retry + 1} 次尝试失败，继续重试...")
                else:
                    logger.error(f"❌ [{self.auth_config.username}] 所有重试均失败")
                    # 最后尝试：使用 cloudscraper 增强 cookies 后再试一次
                    logger.info(f"🔄 [{self.auth_config.username}] 最后尝试：使用 cloudscraper 增强...")
                    enhanced_cookies = await self._get_waf_cookies(page, context, use_cloudscraper=True)
                    if enhanced_cookies:
                        cookies_dict.update(enhanced_cookies)
                        client_id_result = await self._get_auth_client_id(cookies_dict, page)
                        if client_id_result:
                            logger.info(f"✅ [{self.auth_config.username}] Cloudscraper 增强后 client_id获取成功")
                            break
                    logger.error(f"❌ [{self.auth_config.username}] Cloudscraper 增强后仍然失败")
                
            if not client_id_result:
                # 在 CI 环境中提供更详细的错误信息
                is_ci = CIConfig.is_ci_environment()
                error_msg = f"Failed to get LinuxDO client_id after {max_retries} retries"
                if is_ci:
                    error_msg += " (CI environment detected - Linux.do authentication may require manual setup or disabling via CI_DISABLED_AUTH_METHODS=linux.do)"
                return {"success": False, "error": error_msg}

            client_id = client_id_result["client_id"]

            # 第三步：获取 auth_state
            logger.info(f"🔑 [{self.auth_config.username}] 获取 OAuth auth_state...")
            auth_state_result = await self._get_auth_state(cookies_dict, page)
            if not auth_state_result:
                return {"success": False, "error": "Failed to get OAuth auth_state"}

            auth_state = auth_state_result["auth_data"]
            auth_cookies = auth_state_result["cookies"]

            # 设置从API获取的cookies
            if auth_cookies:
                await context.add_cookies(auth_cookies)
                logger.info(f"✅ [{self.auth_config.username}] 设置了 {len(auth_cookies)} 个auth cookies")

            # 第四步：构造完整的OAuth URL并直接访问
            oauth_url = f"https://connect.linux.do/oauth2/authorize?response_type=code&client_id={client_id}&state={auth_state}"
            logger.info(f"🔗 [{self.auth_config.username}] 访问 LinuxDO OAuth URL...")
            logger.info(f"   URL: {oauth_url}")

            await page.goto(oauth_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # 第五步：检查页面状态
            current_url = page.url
            logger.info(f"🔍 [{self.auth_config.username}] 当前URL: {current_url}")

            # 检查是否需要登录
            if "linux.do" in current_url and "/login" in current_url:
                # 需要登录
                logger.info(f"🔐 [{self.auth_config.username}] 需要登录到 Linux.do...")

                # 等待 Cloudflare 验证完成
                logger.info(f"⏳ [{self.auth_config.username}] 等待 Cloudflare 验证完成...")
                await page.wait_for_timeout(5000)

                # 多次尝试查找登录表单元素（使用多种选择器）
                username_input = None
                password_input = None

                # 定义多种可能的选择器
                username_selectors = [
                    'input[id="login-account-name"]',
                    'input[name="login"]',
                    'input[type="text"]',
                    'input.username',
                    '#login-account-name'
                ]

                password_selectors = [
                    'input[id="login-account-password"]',
                    'input[name="password"]',
                    'input[type="password"]',
                    'input.password',
                    '#login-account-password'
                ]

                # 尝试最多3次查找登录表单
                for attempt in range(3):
                    logger.info(f"🔍 [{self.auth_config.username}] 登录表单查找尝试 {attempt + 1}/3...")

                    # 尝试查找用户名输入框
                    for selector in username_selectors:
                        try:
                            username_input = await page.wait_for_selector(selector, timeout=3000)
                            if username_input:
                                logger.info(f"✅ [{self.auth_config.username}] 找到用户名输入框: {selector}")
                                break
                        except:
                            continue

                    # 尝试查找密码输入框
                    for selector in password_selectors:
                        try:
                            password_input = await page.wait_for_selector(selector, timeout=3000)
                            if password_input:
                                logger.info(f"✅ [{self.auth_config.username}] 找到密码输入框: {selector}")
                                break
                        except:
                            continue

                    # 如果找到了用户名和密码输入框，跳出循环
                    if username_input and password_input:
                        logger.info(f"✅ [{self.auth_config.username}] 成功找到完整登录表单")
                        break

                    # 未找到表单，检查页面状态
                    if attempt < 2:
                        logger.warning(f"⚠️ [{self.auth_config.username}] 未找到登录表单，等待后重试...")
                        await page.wait_for_timeout(3000)

                        # 检查是否有 Cloudflare 验证
                        page_content = await page.content()
                        if 'challenge-platform' in page_content or 'cf-challenge' in page_content or 'ray id' in page_content.lower():
                            logger.warning(f"⚠️ [{self.auth_config.username}] 检测到 Cloudflare 验证页面，额外等待5秒...")
                            await page.wait_for_timeout(5000)

                # 最终检查是否找到表单
                if not username_input or not password_input:
                    # 记录详细调试信息
                    page_content = await page.content()
                    page_title = await page.title()

                    logger.error(f"❌ [{self.auth_config.username}] 未找到登录表单")
                    logger.error(f"   页面标题: {page_title}")
                    logger.error(f"   页面URL: {current_url}")
                    logger.error(f"   页面内容长度: {len(page_content)}")

                    # 检查是否被 Cloudflare 拦截
                    if 'challenge-platform' in page_content or 'cf-challenge' in page_content:
                        logger.error(f"❌ [{self.auth_config.username}] 被 Cloudflare 拦截")
                        return {"success": False, "error": "Blocked by Cloudflare verification"}

                    # 检查是否有其他验证
                    if 'ray id' in page_content.lower() or 'cloudflare' in page_content.lower():
                        logger.error(f"❌ [{self.auth_config.username}] 可能被 Cloudflare 拦截（Ray ID 存在）")

                    # 保存页面截图和内容用于调试（如果不在CI环境）
                    try:
                        if not CIConfig.is_ci_environment():
                            screenshot_path = f"debug_login_form_{self.auth_config.username}.png"
                            await page.screenshot(path=screenshot_path)
                            logger.info(f"   已保存截图: {screenshot_path}")

                            html_path = f"debug_login_form_{self.auth_config.username}.html"
                            with open(html_path, 'w', encoding='utf-8') as f:
                                f.write(page_content)
                            logger.info(f"   已保存HTML: {html_path}")
                    except Exception as debug_error:
                        logger.warning(f"   无法保存调试文件: {debug_error}")

                    return {"success": False, "error": "Login form not found after 3 attempts"}

                if username_input and password_input:
                    # 添加人性化延迟
                    await username_input.fill(self.auth_config.username)
                    await page.wait_for_timeout(1000)

                    error = await self._fill_password(password_input)
                    if error:
                        return {"success": False, "error": error}

                    await page.wait_for_timeout(1000)

                    login_button = await page.query_selector('button[id="login-button"]')
                    if login_button:
                        await login_button.click()
                        logger.info(f"✅ [{self.auth_config.username}] 点击登录按钮")
                        
                        # 增加等待时间，处理可能的验证 (从25秒增加到35秒，并分段检测)
                        logger.info(f"⏳ [{self.auth_config.username}] 等待登录完成（可能需要处理验证）...")
                        
                        # 分段等待，每5秒检测一次是否已经跳转
                        for i in range(7):  # 7次检测 = 35秒
                            await page.wait_for_timeout(5000)
                            current_check_url = page.url
                            # 如果已经不在登录页或challenge页，说明可能成功了
                            if "/login" not in current_check_url and "/challenge" not in current_check_url:
                                logger.info(f"✅ [{self.auth_config.username}] 检测到URL变化，可能登录成功: {current_check_url}")
                                break
                            if i < 6:  # 不是最后一次
                                logger.info(f"   ⏳ 继续等待... ({(i+1)*5}秒/{35}秒)")
                        
                        # 检查是否有 Cloudflare 验证或其他挑战
                        current_url_after_login = page.url
                        logger.info(f"🔍 [{self.auth_config.username}] 登录后URL: {current_url_after_login}")
                        
                        # 检查是否在 challenge 页面
                        if "/challenge" in current_url_after_login or "challenge" in current_url_after_login.lower():
                            logger.warning(f"⚠️ [{self.auth_config.username}] 检测到验证挑战（challenge页面），等待120秒...")
                            try:
                                # 等待授权按钮出现或者URL变化（表示验证通过）- 从90秒增加到120秒
                                await page.wait_for_url(lambda url: "/challenge" not in url.lower(), timeout=120000)
                                logger.info(f"✅ [{self.auth_config.username}] 已离开验证挑战页面")
                                await page.wait_for_timeout(5000)  # 增加到5秒
                                current_url_after_login = page.url
                                logger.info(f"🔍 [{self.auth_config.username}] 新URL: {current_url_after_login}")
                            except:
                                logger.error(f"❌ [{self.auth_config.username}] 验证挑战超时（120秒）")
                                # 在CI环境中，如果超时且是headless模式，提供更友好的错误信息
                                is_ci = os.getenv("CI", "false").lower() == "true"
                                if is_ci:
                                    return {"success": False, "error": "Challenge timeout in CI - Linux.do requires human verification in headless mode"}
                                return {"success": False, "error": "Challenge verification timeout - may need manual intervention"}
                        
                        # 检查是否仍在登录页面
                        if "/login" in current_url_after_login:
                            # 先快速检查是否有授权按钮（说明其实已经登录了，只是在OAuth授权页）
                            try:
                                allow_btn_check = await page.wait_for_selector(
                                    'a[href^="/oauth2/approve"]',
                                    timeout=5000
                                )
                                if allow_btn_check:
                                    logger.info(f"✅ [{self.auth_config.username}] 检测到授权按钮，登录成功")
                                    # 登录成功，跳过错误检查
                                else:
                                    raise Exception("No authorize button found after 5s")
                            except:
                                # 没有授权按钮，进行详细检查
                                page_title = await page.title()
                                page_content = await page.content()
                                
                                logger.warning(f"⚠️ [{self.auth_config.username}] 未检测到授权按钮，开始详细检查...")
                                
                                # 检查是否包含登录失败的特征
                                error_keywords = ["invalid", "incorrect", "failed", "wrong", "error"]
                                has_error = any(keyword in page_content.lower() for keyword in error_keywords)
                                
                                # 同时检查是否有输入框，有输入框且有错误关键词才算真正失败
                                has_login_form = await page.query_selector('input[id="login-account-name"]')
                                
                                if has_error and has_login_form:
                                    logger.error(f"❌ [{self.auth_config.username}] 检测到登录失败关键词")
                                    # 尝试提取具体错误信息
                                    try:
                                        error_elem = await page.query_selector('.alert-error, .error, [class*="error"]:not([class*="error-boundary"])')
                                        if error_elem:
                                            error_text = await error_elem.inner_text()
                                            if error_text and len(error_text.strip()) > 0:
                                                logger.error(f"   错误详情: {error_text.strip()}")
                                                return {"success": False, "error": f"Login failed: {error_text.strip()}"}
                                    except:
                                        pass
                                    
                                    # CI环境特殊提示
                                    is_ci = os.getenv("CI", "false").lower() == "true"
                                    if is_ci:
                                        return {"success": False, "error": "Login failed in CI - Linux.do may require human verification"}
                                    return {"success": False, "error": "Login failed - check credentials"}
                                elif has_error:
                                    logger.warning(f"⚠️ [{self.auth_config.username}] 检测到错误关键词但无登录表单，可能是误判，继续...")
                                else:
                                    logger.warning(f"⚠️ [{self.auth_config.username}] 仍在登录页但未检测到明显错误，可能正在加载...")
                                
                                # 检查是否需要验证码
                                captcha_keywords = ["captcha", "recaptcha", "hcaptcha", "verify", "verification"]
                                has_captcha = any(keyword in page_content.lower() for keyword in captcha_keywords)
                                if has_captcha:
                                    try:
                                        captcha_elem = await page.query_selector('[class*="captcha"], [id*="captcha"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]')
                                        if captcha_elem:
                                            logger.error(f"❌ [{self.auth_config.username}] 需要验证码，无法自动处理")
                                            return {"success": False, "error": "Login requires CAPTCHA verification"}
                                    except:
                                        pass
                                
                                # 检查账号密码输入框是否还存在（说明登录未成功）
                                try:
                                    username_still = await page.query_selector('input[id="login-account-name"]')
                                    password_still = await page.query_selector('input[id="login-account-password"]')
                                    if username_still and password_still:
                                        logger.warning(f"⚠️ [{self.auth_config.username}] 登录表单仍然存在，登录可能失败")
                                        logger.warning(f"⚠️ [{self.auth_config.username}] 这可能是由于：凭据错误、需要人工验证、或网络问题")
                                        logger.info(f"   页面标题: {page_title}")
                                        
                                        # 如果没有明显错误，可能是网络慢，再等待10秒
                                        logger.warning(f"⚠️ [{self.auth_config.username}] 未检测到明显错误，再等待10秒...")
                                        await page.wait_for_timeout(10000)
                                        
                                        # 再次检查是否有授权按钮
                                        try:
                                            allow_btn_retry = await page.query_selector('a[href^="/oauth2/approve"]')
                                            if allow_btn_retry:
                                                logger.info(f"✅ [{self.auth_config.username}] 延迟后检测到授权按钮，登录成功")
                                                # 继续后续流程
                                            else:
                                                raise Exception("Still no authorize button after retry")
                                        except:
                                            # 仍然没有授权按钮
                                            logger.warning(f"⚠️ [{self.auth_config.username}] 继续尝试查找授权按钮...")
                                except:
                                    pass

            # 第六步：等待授权按钮并点击
            try:
                logger.info(f"⏳ [{self.auth_config.username}] 等待授权按钮...")
                
                # 先检查当前URL
                current_check_url = page.url
                logger.info(f"🔍 [{self.auth_config.username}] 当前URL: {current_check_url}")
                
                # 如果还在登录页面，先尝试等待一下授权按钮，可能登录成功了但URL未变化
                if "/login" in current_check_url:
                    logger.info(f"ℹ️ [{self.auth_config.username}] 当前在登录页面，尝试查找授权按钮...")
                    try:
                        # 等待最多15秒看是否出现授权按钮 (从10秒增加到15秒)
                        await page.wait_for_selector('a[href^="/oauth2/approve"]', timeout=15000)
                        logger.info(f"✅ [{self.auth_config.username}] 找到授权按钮，登录应该成功了")
                    except:
                        # 15秒后还没有授权按钮，说明登录确实失败了
                        logger.error(f"❌ [{self.auth_config.username}] 仍在登录页面且未找到授权按钮，登录失败")
                        logger.error(f"💡 [{self.auth_config.username}] 可能原因：凭据错误、需要验证码、或网站需要人工验证")
                        
                        # 尝试获取页面内容用于调试
                        try:
                            page_title = await page.title()
                            logger.info(f"   页面标题: {page_title}")
                            
                            # 检查是否有明显的错误提示
                            error_messages = await page.query_selector_all('.alert, [class*="error"], .error-message')
                            if error_messages:
                                for msg_elem in error_messages[:3]:  # 只显示前3个
                                    try:
                                        msg_text = await msg_elem.inner_text()
                                        if msg_text and msg_text.strip():
                                            logger.info(f"   错误提示: {msg_text.strip()}")
                                    except:
                                        pass
                        except:
                            pass
                        
                        return {"success": False, "error": "Still on login page - credentials may be invalid or CAPTCHA required"}
                else:
                    # 不在登录页面，正常等待授权按钮（增加到90秒，CI环境使用倍增器）
                    is_ci = CIConfig.is_ci_environment()
                    timeout = 180000 if is_ci else 90000  # CI环境180秒，本地90秒
                    await page.wait_for_selector('a[href^="/oauth2/approve"]', timeout=timeout)

                allow_btn = await page.query_selector('a[href^="/oauth2/approve"]')
                if allow_btn:
                    logger.info(f"✅ [{self.auth_config.username}] 找到授权按钮，点击授权...")
                    await allow_btn.click()
                else:
                    return {"success": False, "error": "Authorization button not found"}

            except Exception as e:
                logger.error(f"❌ [{self.auth_config.username}] 等待授权按钮超时: {e}")

                # 检查是否已经跳转到回调页面（可能授权已完成）
                current_url = page.url
                logger.info(f"   当前URL: {current_url}")

                # 检查URL是否包含OAuth回调或已跳转到目标域名
                provider_domain = self.provider_config.base_url.replace('https://', '').replace('http://', '')
                if 'oauth/callback' in current_url or '/oauth/' in current_url or provider_domain in current_url:
                    logger.info(f"✅ [{self.auth_config.username}] 检测到已跳转到回调页面，授权可能已完成")
                    # 继续执行后续流程（等待OAuth回调）
                else:
                    # 获取更多调试信息
                    try:
                        page_title = await page.title()
                        logger.info(f"   页面标题: {page_title}")

                        # 检查是否需要登录
                        if 'linux.do/login' in current_url:
                            logger.error(f"❌ [{self.auth_config.username}] 页面跳转到登录页，可能会话已过期")
                            return {"success": False, "error": "Session expired - redirected to login page"}

                        # 检查页面上是否有其他可用元素
                        buttons = await page.query_selector_all('button, a.btn')
                        logger.info(f"   页面上找到 {len(buttons)} 个按钮元素")
                    except Exception as debug_error:
                        logger.warning(f"   无法获取调试信息: {debug_error}")

                    return {"success": False, "error": f"Authorization button timeout: {sanitize_exception(e)}"}

            # 第七步：等待OAuth回调
            logger.info(f"⏳ [{self.auth_config.username}] 等待OAuth回调...")
            try:
                await page.wait_for_url(f"**{self.provider_config.base_url}/oauth/**", timeout=30000)
            except Exception as e:
                logger.warning(f"⚠️ [{self.auth_config.username}] OAuth回调等待超时，检查当前URL...")
                current_url = page.url
                if "/oauth/" in current_url:
                    logger.info(f"✅ [{self.auth_config.username}] 已在OAuth回调页面")
                else:
                    return {"success": False, "error": f"OAuth callback timeout: {sanitize_exception(e)}"}

            # 第八步：等待cookies设置完成
            logger.info(f"🔄 [{self.auth_config.username}] OAuth回调完成，等待cookies设置...")
            await page.wait_for_timeout(3000)
            await self._wait_for_session_cookies(context, max_wait_seconds=10)

            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            self._log_cookies_info(cookies_dict, final_cookies, "LinuxDO")

            # 第九步：提取用户信息
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
            return {"success": False, "error": f"Linux.do auth failed: {sanitize_exception(e)}"}


