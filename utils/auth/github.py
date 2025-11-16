"""
GitHub OAuth 认证器 - 使用 GitHub OAuth 进行第三方登录
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


class GitHubAuthenticator(Authenticator):
    """GitHub OAuth 认证"""
    
    def _should_skip_in_ci(self) -> bool:
        """检查是否应该在 CI 环境中跳过 GitHub 认证"""
        return CIConfig.should_skip_auth_method("github")

    async def _get_github_oauth_params(self, cookies: Dict[str, str], page: Page = None) -> Optional[Dict[str, Any]]:
        """获取 GitHub OAuth 参数（client_id 和 auth_state）"""
        try:
            import httpx
            headers = {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "application/json",
                "Referer": self.provider_config.base_url,
                "Origin": self.provider_config.base_url,
                self.provider_config.api_user_key: "-1"
            }

            # 优先尝试通过浏览器获取（绕过 Cloudflare）
            if page:
                logger.info(f"🌐 [{self.auth_config.username}] 尝试通过浏览器直接获取 OAuth 参数...")
                try:
                    # 使用浏览器的 evaluate 来发送 API 请求，这样可以使用浏览器的 Cloudflare cookies
                    oauth_result = await page.evaluate(f"""
                        async () => {{
                            try {{
                                // 获取 status
                                const statusRes = await fetch('{self.provider_config.get_status_url()}', {{
                                    method: 'GET',
                                    headers: {{
                                        'Accept': 'application/json',
                                        '{self.provider_config.api_user_key}': '-1'
                                    }},
                                    credentials: 'include'
                                }});
                                
                                if (!statusRes.ok) {{
                                    return {{ success: false, error: `Status HTTP ${{statusRes.status}}` }};
                                }}
                                
                                // 检查响应类型是否为 JSON
                                const contentType = statusRes.headers.get('content-type');
                                if (!contentType || !contentType.includes('application/json')) {{
                                    const text = await statusRes.text();
                                    const preview = text.substring(0, 100);
                                    return {{ success: false, error: `Not JSON response (got ${{contentType}}): ${{preview}}` }};
                                }}
                                
                                const statusData = await statusRes.json();
                                if (!statusData.success || !statusData.data) {{
                                    return {{ success: false, error: 'Status API returned failure' }};
                                }}
                                
                                const githubEnabled = statusData.data.github_oauth || false;
                                const clientId = statusData.data.github_client_id || '';
                                
                                if (!githubEnabled || !clientId) {{
                                    return {{ success: false, error: 'GitHub OAuth not enabled or client_id empty' }};
                                }}
                                
                                // 获取 auth_state
                                const stateRes = await fetch('{self.provider_config.get_auth_state_url()}', {{
                                    method: 'GET',
                                    headers: {{
                                        'Accept': 'application/json',
                                        '{self.provider_config.api_user_key}': '-1'
                                    }},
                                    credentials: 'include'
                                }});
                                
                                if (!stateRes.ok) {{
                                    return {{ success: false, error: `State HTTP ${{stateRes.status}}` }};
                                }}
                                
                                // 检查响应类型是否为 JSON
                                const stateContentType = stateRes.headers.get('content-type');
                                if (!stateContentType || !stateContentType.includes('application/json')) {{
                                    const text = await stateRes.text();
                                    const preview = text.substring(0, 100);
                                    return {{ success: false, error: `State not JSON (got ${{stateContentType}}): ${{preview}}` }};
                                }}
                                
                                const stateData = await stateRes.json();
                                if (!stateData.success || !stateData.data) {{
                                    return {{ success: false, error: 'State API returned failure' }};
                                }}
                                
                                return {{ 
                                    success: true, 
                                    client_id: clientId,
                                    auth_state: stateData.data
                                }};
                            }} catch (e) {{
                                return {{ success: false, error: e.toString() }};
                            }}
                        }}
                    """)
                    
                    if oauth_result and oauth_result.get('success'):
                        client_id = oauth_result.get('client_id')
                        auth_state = oauth_result.get('auth_state')
                        logger.info(f"✅ [{self.auth_config.username}] 通过浏览器获取到 OAuth 参数")
                        logger.info(f"   client_id: {client_id}")
                        logger.info(f"   auth_state: {auth_state}")
                        return {
                            "client_id": client_id,
                            "auth_state": auth_state
                        }
                    else:
                        error_msg = oauth_result.get('error', 'Unknown error') if oauth_result else 'No result'
                        logger.error(f"❌ [{self.auth_config.username}] 浏览器方式失败: {error_msg}")
                        return None
                except Exception as browser_error:
                    logger.error(f"❌ [{self.auth_config.username}] 浏览器 API 请求异常: {browser_error}")
                    return None
            
            # 如果没有 page 对象，返回错误（不再使用 httpx 回退，因为会被 Cloudflare 阻止）
            logger.error(f"❌ [{self.auth_config.username}] 需要浏览器 page 对象来绕过 Cloudflare，无法使用 httpx")
            return None

        except Exception as e:
            logger.error(f"❌ [{self.auth_config.username}] 获取 GitHub OAuth 参数异常: {e}")
            return None

    async def authenticate(self, page: Page, context: BrowserContext) -> Dict[str, Any]:
        """使用 GitHub 登录"""
        try:
            logger.info(f"ℹ️ Starting GitHub authentication")
            
            # 检查是否在 CI 环境中应该跳过
            if self._should_skip_in_ci():
                logger.warning(f"⚠️ [{self.auth_config.username}] CI 环境已配置跳过 GitHub 认证")
                return {
                    "success": False,
                    "error": "GitHub authentication skipped in CI environment (configured via CI_DISABLED_AUTH_METHODS)"
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

            # 第三步：获取 GitHub OAuth 参数（带重试）
            max_retries = 3
            oauth_params = None
            
            for retry in range(max_retries):
                logger.info(f"🔑 [{self.auth_config.username}] 获取 GitHub OAuth 参数... (尝试 {retry + 1}/{max_retries})")
                
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
                                timeout=60000
                            )
                            await page.wait_for_timeout(10000)  # 增加到10秒
                        except Exception as e:
                            logger.warning(f"⚠️ [{self.auth_config.username}] 重新访问登录页失败: {e}")
                
                # 获取最新cookies
                current_cookies = await context.cookies()
                cookies_dict = {cookie["name"]: cookie["value"] for cookie in current_cookies}
                logger.info(f"🍪 [{self.auth_config.username}] 当前有 {len(cookies_dict)} 个cookies")
                
                oauth_params = await self._get_github_oauth_params(cookies_dict, page)
                if oauth_params:
                    logger.info(f"✅ [{self.auth_config.username}] OAuth参数获取成功")
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
                        oauth_params = await self._get_github_oauth_params(cookies_dict, page)
                        if oauth_params:
                            logger.info(f"✅ [{self.auth_config.username}] Cloudscraper 增强后 OAuth参数获取成功")
                            break
                    logger.error(f"❌ [{self.auth_config.username}] Cloudscraper 增强后仍然失败")

            if not oauth_params:
                # 在 CI 环境中提供更详细的错误信息
                is_ci = CIConfig.is_ci_environment()
                error_msg = f"Failed to get GitHub OAuth parameters after {max_retries} retries"
                if is_ci:
                    error_msg += " (CI environment detected - GitHub authentication may require manual cookie setup or disabling via CI_DISABLED_AUTH_METHODS=github)"
                return {"success": False, "error": error_msg}

            client_id = oauth_params["client_id"]
            auth_state = oauth_params["auth_state"]

            # 第三步：构造 GitHub OAuth URL 并直接访问
            oauth_url = f"https://github.com/login/oauth/authorize?response_type=code&client_id={client_id}&state={auth_state}&scope=user:email"
            logger.info(f"🔗 [{self.auth_config.username}] 访问 GitHub OAuth URL...")

            await page.goto(oauth_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)

            # 第四步：检查是否需要登录 GitHub
            current_url = page.url
            logger.info(f"🔍 [{self.auth_config.username}] 当前URL: {current_url}")

            if "github.com/login" in current_url:
                # 需要登录
                logger.info(f"🔐 [{self.auth_config.username}] 需要登录到 GitHub...")
                
                username_input = await page.query_selector('input[name="login"]')
                password_input = await page.query_selector('input[name="password"]')

                if username_input and password_input:
                    await username_input.fill(self.auth_config.username)
                    await page.wait_for_timeout(500)
                    
                    error = await self._fill_password(password_input)
                    if error:
                        return {"success": False, "error": error}
                    
                    await page.wait_for_timeout(500)

                    submit_button = await page.query_selector('input[type="submit"]')
                    if submit_button:
                        await submit_button.click()
                        logger.info(f"✅ [{self.auth_config.username}] 点击登录按钮")
                        await page.wait_for_timeout(3000)

                # 检查是否需要 2FA
                await page.wait_for_timeout(2000)
                current_url = page.url
                if "two-factor" in current_url or "2fa" in current_url.lower():
                    logger.info("🔐 GitHub 需要 2FA 认证")
                    if not await self._handle_2fa(page):
                        return {"success": False, "error": "2FA authentication failed"}

            # 第五步：检查是否需要授权
            await page.wait_for_timeout(2000)
            current_url = page.url
            
            if "github.com/login/oauth/authorize" in current_url:
                logger.info(f"🔑 [{self.auth_config.username}] 需要授权应用...")
                try:
                    authorize_button = await page.query_selector('button[name="authorize"]')
                    if authorize_button:
                        await authorize_button.click()
                        logger.info(f"✅ [{self.auth_config.username}] 点击授权按钮")
                        await page.wait_for_timeout(2000)
                except Exception as e:
                    logger.warning(f"⚠️ [{self.auth_config.username}] 点击授权按钮失败: {e}")

            # 第六步：等待OAuth回调
            logger.info(f"⏳ [{self.auth_config.username}] 等待OAuth回调...")
            try:
                await page.wait_for_url(f"**{self.provider_config.base_url}/oauth/**", timeout=60000)
            except Exception as e:
                logger.warning(f"⚠️ [{self.auth_config.username}] OAuth回调等待超时，检查当前URL...")
                current_url = page.url
                page_title = await page.title()
                logger.error(f"❌ OAuth 回调超时")
                logger.info(f"  当前URL: {current_url}")
                logger.info(f"  页面标题: {page_title}")

                # 检查是否卡在某个特定页面
                if "/oauth/" in current_url:
                    logger.info(f"✅ [{self.auth_config.username}] 已在OAuth回调页面")
                elif "github.com/login" in current_url:
                    return {"success": False, "error": "OAuth callback timeout: Still on GitHub login page"}
                elif "2fa" in current_url.lower() or "two-factor" in current_url.lower():
                    return {"success": False, "error": "OAuth callback timeout: Stuck on 2FA page"}
                else:
                    return {"success": False, "error": f"OAuth callback timeout: {sanitize_exception(e)}"}

            # 等待cookies传播完成
            logger.info(f"🔄 [{self.auth_config.username}] OAuth回调完成，等待cookies设置...")
            await page.wait_for_timeout(3000)  # 等待3秒让cookies传播
            await self._wait_for_session_cookies(context, max_wait_seconds=10)

            final_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in final_cookies}

            self._log_cookies_info(cookies_dict, final_cookies, "GitHub")

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
            return {"success": False, "error": f"GitHub auth failed: {sanitize_exception(e)}"}

    async def _handle_2fa(self, page: Page) -> bool:
        """处理 GitHub 2FA 认证（支持重试）"""
        import asyncio

        max_2fa_attempts = 2
        for attempt in range(max_2fa_attempts):
            try:
                logger.info(f"🔐 处理 GitHub 2FA 认证（尝试 {attempt + 1}/{max_2fa_attempts}）...")

                # 等待 2FA 输入框出现（增加超时到15秒）
                await page.wait_for_selector('input[name="otp"]', timeout=15000)

                # 方法1: 从环境变量获取预先生成的 2FA 代码
                otp_code = os.getenv('GITHUB_2FA_CODE')
                if otp_code:
                    logger.info("📱 使用环境变量中的 2FA 代码")
                    await page.fill('input[name="otp"]', otp_code)
                    await page.click('button[type="submit"]', timeout=5000)

                    # 等待导航完成（增加超时到30秒）
                    try:
                        await page.wait_for_load_state("networkidle", timeout=30000)
                    except:
                        await page.wait_for_timeout(3000)

                    # 检查是否成功跳转
                    current_url = page.url
                    if "2fa" not in current_url.lower() and "two-factor" not in current_url.lower():
                        logger.info("✅ 2FA 认证成功")
                        return True
                    elif attempt < max_2fa_attempts - 1:
                        logger.warning(f"⚠️ 2FA 尝试 {attempt + 1} 失败（仍在2FA页面），重试...")
                        await asyncio.sleep(2)
                        continue
                    else:
                        raise Exception(f"2FA authentication failed after {max_2fa_attempts} attempts (still on 2FA page)")

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

                        # 等待导航完成（增加超时到30秒）
                        try:
                            await page.wait_for_load_state("networkidle", timeout=30000)
                        except:
                            await page.wait_for_timeout(3000)

                        # 检查是否成功跳转
                        current_url = page.url
                        if "2fa" not in current_url.lower() and "two-factor" not in current_url.lower():
                            logger.info("✅ 2FA 认证成功")
                            return True
                        elif attempt < max_2fa_attempts - 1:
                            logger.warning(f"⚠️ 2FA 尝试 {attempt + 1} 失败（仍在2FA页面），重试...")
                            await asyncio.sleep(2)
                            continue
                        else:
                            raise Exception(f"2FA authentication failed after {max_2fa_attempts} attempts (still on 2FA page)")
                    except ImportError:
                        logger.error("❌ 需要安装 pyotp 库: pip install pyotp")
                    except Exception as e:
                        if "failed after" in str(e):
                            raise
                        logger.error(f"❌ TOTP 生成失败: {e}")
                        if attempt < max_2fa_attempts - 1:
                            logger.warning(f"⚠️ 2FA 尝试 {attempt + 1} 失败，重试...")
                            await asyncio.sleep(2)
                            continue

                # 方法3: 尝试常见的备用恢复代码
                recovery_codes_str = os.getenv('GITHUB_RECOVERY_CODES')
                if recovery_codes_str:
                    recovery_codes = recovery_codes_str.split(',')
                    logger.info(f"🔄 尝试使用恢复代码 (剩余 {len(recovery_codes)} 个)")
                    for i, code in enumerate(recovery_codes):
                        try:
                            await page.fill('input[name="otp"]', code.strip())
                            await page.click('button[type="submit"]', timeout=5000)

                            # 等待导航完成（增加超时到30秒）
                            try:
                                await page.wait_for_load_state("networkidle", timeout=30000)
                            except:
                                await page.wait_for_timeout(3000)

                            # 检查是否成功跳转
                            current_url = page.url
                            if "2fa" not in current_url.lower() and "two-factor" not in current_url.lower():
                                logger.info(f"✅ 恢复代码 {i+1} 验证成功")
                                return True
                        except:
                            logger.error(f"❌ 恢复代码 {i+1} 验证失败，尝试下一个...")
                            await page.wait_for_timeout(1000)
                            continue

                # 如果所有方法都没有配置或失败
                if attempt < max_2fa_attempts - 1:
                    logger.warning(f"⚠️ 2FA 尝试 {attempt + 1} 失败，重试...")
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.error("❌ 无法自动处理 2FA，请手动处理或配置以下环境变量:")
                    logger.info("   - GITHUB_2FA_CODE: 预先生成的 2FA 代码")
                    logger.info("   - GITHUB_TOTP_SECRET: TOTP 密钥")
                    logger.info("   - GITHUB_RECOVERY_CODES: 恢复代码列表 (逗号分隔)")
                    return False

            except Exception as e:
                if attempt < max_2fa_attempts - 1:
                    logger.warning(f"⚠️ 2FA 尝试 {attempt + 1} 失败: {e}，重试...")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"❌ 2FA authentication failed after {max_2fa_attempts} attempts: {e}")
                    return False

        return False


