#!/usr/bin/env python3
"""
测试 cloudscraper 集成功能
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.auth.base import CloudscraperHelper
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_cloudscraper_basic():
    """测试 cloudscraper 基础功能"""
    logger.info("=" * 60)
    logger.info("测试 1: CloudscraperHelper 基础功能")
    logger.info("=" * 60)

    # 测试一个简单的网站（没有 Cloudflare）
    test_url = "https://httpbin.org/cookies"

    try:
        logger.info(f"🔍 测试 URL: {test_url}")
        cookies = await CloudscraperHelper.get_cf_cookies(test_url)

        if cookies:
            logger.info(f"✅ 成功获取 {len(cookies)} 个 cookies")
            for name, value in cookies.items():
                logger.info(f"   - {name}: {value[:20]}..." if len(value) > 20 else f"   - {name}: {value}")
        else:
            logger.warning("⚠️ 未获取到任何 cookies（可能是正常的）")

        return True
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return False


async def test_cloudscraper_with_proxy():
    """测试 cloudscraper 代理功能"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: CloudscraperHelper 代理功能")
    logger.info("=" * 60)

    test_url = "https://httpbin.org/ip"
    proxy = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")

    if not proxy:
        logger.info("ℹ️ 未配置代理，跳过此测试")
        logger.info("   提示: 可通过环境变量 HTTP_PROXY 或 HTTPS_PROXY 配置代理")
        return True

    try:
        logger.info(f"🔍 测试 URL: {test_url}")
        logger.info(f"🌐 使用代理: {proxy}")

        cookies = await CloudscraperHelper.get_cf_cookies(test_url, proxy=proxy)

        if cookies is not None:  # 允许空字典
            logger.info(f"✅ 代理测试通过（获取 {len(cookies)} 个 cookies）")
            return True
        else:
            logger.error("❌ 代理测试失败")
            return False
    except Exception as e:
        logger.error(f"❌ 代理测试异常: {e}")
        return False


async def test_cloudscraper_import():
    """测试 cloudscraper 是否正确安装"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 0: 检查 cloudscraper 安装")
    logger.info("=" * 60)

    try:
        import cloudscraper
        logger.info(f"✅ cloudscraper 已安装")
        logger.info(f"   版本: {cloudscraper.__version__ if hasattr(cloudscraper, '__version__') else 'Unknown'}")
        return True
    except ImportError:
        logger.error("❌ cloudscraper 未安装")
        logger.info("   请运行: pip install cloudscraper>=1.2.71")
        return False


async def main():
    """运行所有测试"""
    logger.info("🚀 开始测试 cloudscraper 集成...")
    logger.info("")

    results = []

    # 测试 0: 检查安装
    result = await test_cloudscraper_import()
    results.append(("安装检查", result))

    if not result:
        logger.error("\n❌ cloudscraper 未安装，无法继续测试")
        logger.info("   请先安装: pip install cloudscraper>=1.2.71")
        return

    # 测试 1: 基础功能
    result = await test_cloudscraper_basic()
    results.append(("基础功能", result))

    # 测试 2: 代理功能
    result = await test_cloudscraper_with_proxy()
    results.append(("代理功能", result))

    # 输出测试总结
    logger.info("\n" + "=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name:15} - {status}")

    all_passed = all(result for _, result in results)
    logger.info("")
    if all_passed:
        logger.info("🎉 所有测试通过！cloudscraper 集成正常工作")
    else:
        logger.warning("⚠️ 部分测试失败，请检查配置或安装")


if __name__ == "__main__":
    asyncio.run(main())
