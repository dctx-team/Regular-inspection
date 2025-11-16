#!/usr/bin/env python3
"""
Cloudscraper 整合示例
展示如何在现有异步架构中使用 cloudscraper
"""
import asyncio
import cloudscraper
from typing import Dict, Optional


class CloudscraperHelper:
    """cloudscraper 辅助类 - 用于获取绕过 Cloudflare 的初始 cookies"""

    @staticmethod
    async def get_cf_cookies(url: str, proxy: Optional[str] = None) -> Dict[str, str]:
        """
        使用 cloudscraper 获取绕过 Cloudflare 的 cookies

        Args:
            url: 目标网站 URL
            proxy: 代理地址（可选），格式：http://host:port

        Returns:
            Dict[str, str]: cookies 字典
        """
        def _sync_get_cookies():
            """同步获取 cookies（在线程池中运行）"""
            # 创建 scraper 实例
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )

            # 配置代理
            proxies = None
            if proxy:
                proxies = {
                    'http': proxy,
                    'https': proxy
                }

            try:
                # 访问目标网站
                response = scraper.get(url, proxies=proxies, timeout=30)

                # 提取 cookies
                cookies = {cookie.name: cookie.value for cookie in scraper.cookies}
                return cookies

            except Exception as e:
                print(f"❌ Cloudscraper 获取失败: {e}")
                return {}

        # 在线程池中运行同步代码
        loop = asyncio.get_event_loop()
        cookies = await loop.run_in_executor(None, _sync_get_cookies)
        return cookies


# ============================================
# 整合到现有代码的示例
# ============================================

async def enhanced_get_waf_cookies(page, context, provider_url: str, proxy: Optional[str] = None) -> Dict[str, str]:
    """
    增强版 WAF cookies 获取 - 支持 cloudscraper 降级

    优先使用 Playwright（更可靠），失败时降级到 cloudscraper
    """
    try:
        # 方案 A：优先使用 Playwright（当前方案）
        print("ℹ️ 尝试使用 Playwright 获取 WAF cookies...")

        await page.goto(provider_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        cookies = await context.cookies()
        waf_cookies = {cookie["name"]: cookie["value"] for cookie in cookies}

        if waf_cookies:
            print(f"✅ Playwright 获取成功: {len(waf_cookies)} 个 cookies")
            return waf_cookies

    except Exception as e:
        print(f"⚠️ Playwright 失败: {e}")

    # 方案 B：降级到 cloudscraper
    print("ℹ️ 降级使用 cloudscraper...")

    try:
        cf_cookies = await CloudscraperHelper.get_cf_cookies(provider_url, proxy)

        if cf_cookies:
            print(f"✅ Cloudscraper 获取成功: {len(cf_cookies)} 个 cookies")

            # 将 cloudscraper 获取的 cookies 注入到 Playwright context
            for name, value in cf_cookies.items():
                await context.add_cookies([{
                    "name": name,
                    "value": value,
                    "domain": provider_url.split("//")[1].split("/")[0],
                    "path": "/"
                }])

            return cf_cookies

    except Exception as e:
        print(f"❌ Cloudscraper 也失败: {e}")

    return {}


# ============================================
# 使用示例
# ============================================

async def example_usage():
    """使用示例"""
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 获取 WAF cookies（支持 Playwright + cloudscraper 双重降级）
        waf_cookies = await enhanced_get_waf_cookies(
            page,
            context,
            provider_url="https://anyrouter.top",
            proxy="http://127.0.0.1:7890"  # 可选
        )

        print(f"最终获取到的 cookies: {waf_cookies}")

        await browser.close()


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_usage())
