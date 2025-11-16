"""
人类行为模拟工具 - 用于在 CI 环境下提高 Cloudflare 验证通过率
"""

import random
import asyncio
from typing import Optional
from playwright.async_api import Page
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def simulate_human_behavior(page: Page, logger_instance=None) -> None:
    """模拟人类浏览行为

    在 CI headless 环境下模拟真实用户的鼠标移动、滚动等行为，
    以提高 Cloudflare 人机验证的通过率。

    Args:
        page: Playwright 页面对象
        logger_instance: 可选的日志记录器实例
    """
    log = logger_instance or logger

    try:
        # 随机鼠标移动（模拟用户浏览页面）
        move_count = random.randint(2, 5)
        log.debug(f"开始模拟鼠标移动 ({move_count} 次)")

        for i in range(move_count):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))

        # 随机滚动页面（模拟阅读）
        scroll_amount = random.randint(100, 500)
        log.debug(f"模拟页面滚动 ({scroll_amount}px)")
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(0.5, 1.0))

        # 回到顶部（模拟查看完整页面）
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(random.uniform(0.3, 0.6))

        log.debug("行为模拟完成")

    except Exception as e:
        log.debug(f"行为模拟失败（非致命）: {e}")


async def simulate_reading_delay() -> None:
    """模拟阅读延迟

    模拟用户阅读页面内容的时间延迟。
    """
    await asyncio.sleep(random.uniform(1.0, 2.5))


async def simulate_typing(
    page: Page,
    selector: str,
    text: str,
    logger_instance=None
) -> bool:
    """模拟人类打字

    以逐字符的方式模拟人类打字行为，增加随机延迟。

    Args:
        page: Playwright 页面对象
        selector: 输入框选择器
        text: 要输入的文本
        logger_instance: 可选的日志记录器实例

    Returns:
        bool: 是否成功模拟打字
    """
    log = logger_instance or logger

    try:
        element = await page.query_selector(selector)
        if element:
            log.debug(f"开始模拟打字: {selector}")
            for char in text:
                # 每个字符间随机延迟 50-150ms（模拟人类打字速度）
                await element.type(char, delay=random.randint(50, 150))
            log.debug(f"模拟打字完成: {selector}")
            return True
        else:
            log.warning(f"未找到元素，降级到普通 fill: {selector}")
            await page.fill(selector, text)
            return False
    except Exception as e:
        log.warning(f"模拟打字失败，降级到普通 fill: {e}")
        try:
            await page.fill(selector, text)
            return False
        except Exception as fill_error:
            log.error(f"填充文本失败: {fill_error}")
            return False


async def simulate_mouse_movement_to_element(
    page: Page,
    selector: str,
    logger_instance=None
) -> bool:
    """模拟鼠标移动到指定元素

    以自然的轨迹移动鼠标到指定元素，而不是直接点击。

    Args:
        page: Playwright 页面对象
        selector: 目标元素选择器
        logger_instance: 可选的日志记录器实例

    Returns:
        bool: 是否成功移动到元素
    """
    log = logger_instance or logger

    try:
        element = await page.query_selector(selector)
        if not element:
            log.warning(f"未找到目标元素: {selector}")
            return False

        # 获取元素位置
        box = await element.bounding_box()
        if not box:
            log.warning(f"无法获取元素位置: {selector}")
            return False

        # 计算元素中心点
        target_x = box['x'] + box['width'] / 2
        target_y = box['y'] + box['height'] / 2

        # 模拟曲线移动（分多步移动到目标）
        steps = random.randint(3, 6)
        current_x, current_y = 0, 0

        for step in range(steps):
            # 计算中间点（添加随机偏移）
            progress = (step + 1) / steps
            x = current_x + (target_x - current_x) * progress + random.randint(-20, 20)
            y = current_y + (target_y - current_y) * progress + random.randint(-20, 20)

            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.05, 0.15))

        # 最终精确移动到目标
        await page.mouse.move(target_x, target_y)
        log.debug(f"鼠标已移动到元素: {selector}")
        return True

    except Exception as e:
        log.warning(f"模拟鼠标移动失败: {e}")
        return False


async def simulate_click_with_behavior(
    page: Page,
    selector: str,
    logger_instance=None,
    with_movement: bool = True
) -> bool:
    """模拟带有人类行为的点击

    先移动鼠标到元素，然后点击，模拟真实用户操作。

    Args:
        page: Playwright 页面对象
        selector: 要点击的元素选择器
        logger_instance: 可选的日志记录器实例
        with_movement: 是否先模拟鼠标移动

    Returns:
        bool: 是否成功点击
    """
    log = logger_instance or logger

    try:
        if with_movement:
            await simulate_mouse_movement_to_element(page, selector, log)
            await asyncio.sleep(random.uniform(0.2, 0.5))

        # 执行点击
        await page.click(selector)
        log.debug(f"已点击元素: {selector}")

        # 点击后短暂延迟（模拟人类反应时间）
        await asyncio.sleep(random.uniform(0.3, 0.7))
        return True

    except Exception as e:
        log.warning(f"模拟点击失败: {e}")
        return False


async def simulate_form_filling(
    page: Page,
    email_selector: str,
    email_value: str,
    password_selector: str,
    password_value: str,
    logger_instance=None,
    enable_typing: bool = True
) -> bool:
    """模拟表单填写行为

    以自然的顺序和延迟填写表单字段。

    Args:
        page: Playwright 页面对象
        email_selector: 邮箱输入框选择器
        email_value: 邮箱值
        password_selector: 密码输入框选择器
        password_value: 密码值
        logger_instance: 可选的日志记录器实例
        enable_typing: 是否启用逐字符打字模拟

    Returns:
        bool: 是否成功填写
    """
    log = logger_instance or logger

    try:
        # 移动到邮箱输入框
        await simulate_mouse_movement_to_element(page, email_selector, log)
        await asyncio.sleep(random.uniform(0.2, 0.4))

        # 点击邮箱输入框
        await page.click(email_selector)
        await asyncio.sleep(random.uniform(0.3, 0.6))

        # 填写邮箱
        if enable_typing:
            await simulate_typing(page, email_selector, email_value, log)
        else:
            await page.fill(email_selector, email_value)

        # 短暂停顿（模拟思考时间）
        await asyncio.sleep(random.uniform(0.5, 1.0))

        # 移动到密码输入框
        await simulate_mouse_movement_to_element(page, password_selector, log)
        await asyncio.sleep(random.uniform(0.2, 0.4))

        # 点击密码输入框
        await page.click(password_selector)
        await asyncio.sleep(random.uniform(0.3, 0.6))

        # 填写密码
        if enable_typing:
            await simulate_typing(page, password_selector, password_value, log)
        else:
            await page.fill(password_selector, password_value)

        # 填写完成后的短暂延迟
        await asyncio.sleep(random.uniform(0.5, 1.0))

        log.debug("表单填写完成")
        return True

    except Exception as e:
        log.error(f"模拟表单填写失败: {e}")
        return False


async def add_random_mouse_jitter(page: Page, duration_seconds: float = 2.0) -> None:
    """添加随机鼠标抖动

    在指定时间内随机移动鼠标，模拟用户在页面上的自然移动。

    Args:
        page: Playwright 页面对象
        duration_seconds: 抖动持续时间（秒）
    """
    try:
        end_time = asyncio.get_event_loop().time() + duration_seconds

        while asyncio.get_event_loop().time() < end_time:
            x = random.randint(0, 1920)
            y = random.randint(0, 1080)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))

    except Exception as e:
        logger.debug(f"鼠标抖动失败（非致命）: {e}")


async def simulate_page_interaction(page: Page, logger_instance=None) -> None:
    """模拟页面交互

    综合模拟多种用户行为：鼠标移动、滚动、停顿等。
    这是一个更全面的行为模拟函数。

    Args:
        page: Playwright 页面对象
        logger_instance: 可选的日志记录器实例
    """
    log = logger_instance or logger

    try:
        log.debug("开始模拟页面交互")

        # 随机鼠标移动
        for _ in range(random.randint(3, 7)):
            x = random.randint(100, 1800)
            y = random.randint(100, 900)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.15, 0.35))

        # 向下滚动（模拟浏览）
        scroll_steps = random.randint(2, 4)
        for _ in range(scroll_steps):
            scroll_amount = random.randint(150, 400)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(0.6, 1.2))

        # 在页面中间停顿（模拟阅读）
        await asyncio.sleep(random.uniform(1.0, 2.0))

        # 向上滚动一点
        scroll_back = random.randint(50, 200)
        await page.evaluate(f"window.scrollBy(0, -{scroll_back})")
        await asyncio.sleep(random.uniform(0.4, 0.8))

        # 回到顶部
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(random.uniform(0.5, 1.0))

        log.debug("页面交互模拟完成")

    except Exception as e:
        log.debug(f"页面交互模拟失败（非致命）: {e}")
