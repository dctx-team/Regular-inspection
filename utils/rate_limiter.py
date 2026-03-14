"""
速率限制器模块 - 令牌桶算法实现
"""

import time
import asyncio
from typing import Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)


class RateLimiter:
    """令牌桶速率限制器

    使用令牌桶算法控制请求频率，防止触发目标网站的速率限制。

    Args:
        rate: 每秒允许的请求数（令牌生成速率）
        max_tokens: 桶的最大容量
        name: 限制器名称（用于日志）
    """

    def __init__(self, rate: float = 1.0, max_tokens: int = 5, name: str = "default"):
        self.rate = rate
        self.max_tokens = max_tokens
        self.name = name
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._consecutive_failures = 0

    def _refill(self) -> None:
        """补充令牌"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self.rate
        self._tokens = min(self.max_tokens, self._tokens + new_tokens)
        self._last_refill = now

    async def acquire(self, timeout: Optional[float] = 30.0) -> bool:
        """获取一个令牌（异步等待直到可用）

        Args:
            timeout: 最大等待时间（秒），None 表示无限等待

        Returns:
            bool: 是否成功获取令牌
        """
        start_time = time.monotonic()

        async with self._lock:
            while True:
                self._refill()

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    logger.debug(
                        f"🎫 [{self.name}] 令牌获取成功（剩余: {self._tokens:.1f}/{self.max_tokens}）"
                    )
                    return True

                # 计算需要等待的时间
                wait_time = (1.0 - self._tokens) / self.rate

                # 检查是否超时
                if timeout is not None:
                    elapsed = time.monotonic() - start_time
                    if elapsed + wait_time > timeout:
                        logger.warning(
                            f"⚠️ [{self.name}] 速率限制等待超时（{timeout}秒）"
                        )
                        return False

                logger.debug(
                    f"⏳ [{self.name}] 等待令牌... ({wait_time:.2f}秒)"
                )
                # 释放锁后等待
                self._lock.release()
                try:
                    await asyncio.sleep(wait_time)
                finally:
                    await self._lock.acquire()

    def record_failure(self) -> None:
        """记录一次失败，用于自适应延迟"""
        self._consecutive_failures += 1
        logger.debug(
            f"📉 [{self.name}] 连续失败次数: {self._consecutive_failures}"
        )

    def record_success(self) -> None:
        """记录一次成功，重置失败计数"""
        if self._consecutive_failures > 0:
            logger.debug(
                f"📈 [{self.name}] 成功，重置失败计数（之前: {self._consecutive_failures}）"
            )
        self._consecutive_failures = 0

    @property
    def consecutive_failures(self) -> int:
        """获取连续失败次数"""
        return self._consecutive_failures


def adaptive_delay(consecutive_failures: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """计算自适应延迟时间

    根据连续失败次数使用指数退避策略计算延迟。

    Args:
        consecutive_failures: 连续失败次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）

    Returns:
        float: 建议的延迟时间（秒）
    """
    if consecutive_failures <= 0:
        return base_delay

    # 指数退避: base * 2^failures
    delay = base_delay * (2 ** min(consecutive_failures, 6))
    delay = min(delay, max_delay)

    logger.info(
        f"⏱️ 自适应延迟: {delay:.1f}秒（连续失败 {consecutive_failures} 次）"
    )
    return delay


# 全局速率限制器实例（供 checkin.py 使用）
global_rate_limiter = RateLimiter(rate=0.5, max_tokens=3, name="global")
