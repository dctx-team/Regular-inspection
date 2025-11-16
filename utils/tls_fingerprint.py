#!/usr/bin/env python3
"""
TLS 指纹伪装模块 - 使用 curl-cffi 绕过高级 TLS 指纹检测

2025 年 Cloudflare 已开始检测 TLS 指纹（JA3/JA4），传统的 requests/httpx 库容易被识别。
curl-cffi 使用真实的 curl impersonate 技术，可以完美模拟 Chrome/Firefox 的 TLS 指纹。

环境变量配置：
    - ENABLE_TLS_FINGERPRINT=true     启用 TLS 指纹伪装（默认禁用）
    - TLS_BROWSER_TYPE=chrome131      指定浏览器类型（chrome131/chrome120/firefox/edge）

依赖安装：
    pip install curl-cffi>=0.6.0

注意：
    - curl-cffi 在某些系统上可能需要编译依赖
    - Windows 系统需要安装 Visual C++ Build Tools
    - Linux 系统需要 libcurl-dev
"""

import os
import asyncio
from typing import Dict, Optional, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)


class TLSFingerprintHelper:
    """TLS 指纹伪装辅助类（可选增强）"""

    # 支持的浏览器类型映射（curl-cffi impersonate 参数）
    BROWSER_TYPES = {
        "chrome131": "chrome131",      # Chrome 131（2025 最新）
        "chrome120": "chrome120",      # Chrome 120
        "chrome116": "chrome116",      # Chrome 116
        "edge101": "edge101",          # Edge 101
        "safari15_5": "safari15_5",    # Safari 15.5
        "firefox": "firefox109",       # Firefox 109
    }

    @staticmethod
    def is_available() -> bool:
        """检查 curl-cffi 是否可用"""
        try:
            import curl_cffi
            return True
        except ImportError:
            return False

    @staticmethod
    def is_enabled() -> bool:
        """检查是否启用 TLS 指纹伪装"""
        return os.getenv("ENABLE_TLS_FINGERPRINT", "false").lower() == "true"

    @staticmethod
    def get_browser_type() -> str:
        """获取配置的浏览器类型"""
        browser_type = os.getenv("TLS_BROWSER_TYPE", "chrome131").lower()
        return TLSFingerprintHelper.BROWSER_TYPES.get(browser_type, "chrome131")

    @staticmethod
    async def get_cookies_with_tls_fingerprint(
        url: str,
        proxy: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        timeout: int = 60
    ) -> Dict[str, str]:
        """
        使用 TLS 指纹伪装获取 cookies

        Args:
            url: 目标网站 URL
            proxy: 代理地址（可选），格式：http://host:port 或 socks5://host:port
            custom_headers: 自定义请求头（可选）
            timeout: 超时时间（秒）

        Returns:
            Dict[str, str]: cookies 字典
        """
        # 检查是否启用和可用
        if not TLSFingerprintHelper.is_enabled():
            logger.debug("ℹ️ TLS 指纹伪装未启用（设置 ENABLE_TLS_FINGERPRINT=true 启用）")
            return {}

        if not TLSFingerprintHelper.is_available():
            logger.warning("⚠️ curl-cffi 未安装，无法使用 TLS 指纹伪装")
            logger.warning("   提示：运行 'pip install curl-cffi>=0.6.0' 安装")
            return {}

        def _sync_get_cookies():
            """同步获取 cookies（在线程池中运行）"""
            try:
                from curl_cffi import requests as cffi_requests

                # 获取浏览器类型
                browser = TLSFingerprintHelper.get_browser_type()
                logger.info(f"🔐 使用 TLS 指纹伪装（浏览器类型: {browser}）")

                # 构造请求头（2025 最新 Chrome 131）
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'sec-ch-ua': '"Chromium";v="131", "Not_A Brand";v="24"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-User': '?1',
                    'Sec-Fetch-Dest': 'document',
                }

                # 合并自定义请求头
                if custom_headers:
                    headers.update(custom_headers)

                # 配置代理
                proxies = None
                if proxy:
                    proxies = {
                        'http': proxy,
                        'https': proxy
                    }

                # 发送请求（使用 impersonate 参数模拟真实浏览器）
                response = cffi_requests.get(
                    url,
                    headers=headers,
                    proxies=proxies,
                    timeout=timeout,
                    allow_redirects=True,
                    impersonate=browser,  # 关键参数：模拟真实浏览器的 TLS 指纹
                    verify=False  # 在某些环境下可能需要禁用证书验证
                )

                # 检查响应状态
                if response.status_code != 200:
                    logger.debug(f"⚠️ TLS 指纹请求返回状态码 {response.status_code}")
                    return {}

                # 提取 cookies
                cookies = dict(response.cookies)

                # 检查是否成功获取关键 cookies
                cf_cookies = ["cf_clearance", "__cf_bm", "cf_chl_2"]
                found_cf = [name for name in cf_cookies if name in cookies]
                if found_cf:
                    logger.info(f"✅ TLS 指纹成功获取 Cloudflare cookies: {', '.join(found_cf)}")
                else:
                    logger.debug(f"⚠️ TLS 指纹未获取到 Cloudflare 关键 cookies")

                return cookies

            except ImportError:
                logger.warning("⚠️ curl-cffi 未安装，无法使用 TLS 指纹伪装")
                return {}
            except Exception as e:
                logger.debug(f"⚠️ TLS 指纹获取失败: {e}")
                return {}

        # 在线程池中运行同步代码
        try:
            loop = asyncio.get_event_loop()
            cookies = await loop.run_in_executor(None, _sync_get_cookies)
            return cookies
        except Exception as e:
            logger.debug(f"⚠️ TLS 指纹执行异常: {e}")
            return {}


# ============================================
# 集成到现有认证流程的示例
# ============================================

async def enhanced_waf_cookies_with_tls(
    url: str,
    proxy: Optional[str] = None,
    use_tls_fingerprint: bool = True,
    use_cloudscraper: bool = True
) -> Dict[str, str]:
    """
    增强版 WAF cookies 获取 - 支持 TLS 指纹 + cloudscraper 双重降级

    优先级：
    1. TLS 指纹伪装（curl-cffi）
    2. cloudscraper
    3. 返回空字典

    Args:
        url: 目标 URL
        proxy: 代理地址
        use_tls_fingerprint: 是否尝试 TLS 指纹伪装
        use_cloudscraper: 是否尝试 cloudscraper

    Returns:
        Dict[str, str]: cookies 字典
    """
    # 方案 A：TLS 指纹伪装（最强）
    if use_tls_fingerprint and TLSFingerprintHelper.is_enabled():
        logger.info("🔐 尝试使用 TLS 指纹伪装...")
        cookies = await TLSFingerprintHelper.get_cookies_with_tls_fingerprint(url, proxy)
        if cookies:
            return cookies

    # 方案 B：cloudscraper（次选）
    if use_cloudscraper:
        logger.info("ℹ️ 降级使用 cloudscraper...")
        try:
            from utils.auth.base import CloudscraperHelper
            cookies = await CloudscraperHelper.get_cf_cookies(url, proxy)
            if cookies:
                return cookies
        except Exception as e:
            logger.debug(f"⚠️ Cloudscraper 失败: {e}")

    # 方案 C：返回空字典（不阻塞流程）
    logger.warning("⚠️ 所有 WAF cookies 获取方案均失败，使用空 cookies 继续")
    return {}


# ============================================
# 使用示例
# ============================================

async def example_usage():
    """使用示例"""
    # 1. 检查是否可用
    if TLSFingerprintHelper.is_available():
        logger.info("✅ curl-cffi 可用")
    else:
        logger.warning("⚠️ curl-cffi 不可用，请安装：pip install curl-cffi>=0.6.0")

    # 2. 获取 cookies
    cookies = await TLSFingerprintHelper.get_cookies_with_tls_fingerprint(
        url="https://linux.do",
        proxy="http://127.0.0.1:7890",  # 可选
    )

    logger.info(f"获取到的 cookies: {cookies}")


if __name__ == "__main__":
    # 测试运行
    asyncio.run(example_usage())
