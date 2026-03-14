"""
统一日志管理模块
"""

import logging
import re
import sys
from datetime import datetime
from typing import Optional


class SanitizingFilter(logging.Filter):
    """日志脱敏过滤器

    自动拦截日志消息并脱敏敏感信息（密码、token、cookie 等）。
    作为 logging.Filter 挂载到 handler 上，对所有日志消息生效。
    """

    # 需要脱敏的正则模式列表
    PATTERNS = [
        # password=xxx, pwd=xxx
        (
            re.compile(
                r'(password|passwd|pwd)\s*[=:]\s*["\']?([^"\'\s,;&]+)', re.IGNORECASE
            ),
            r"\1=***",
        ),
        # token=xxx, api_key=xxx, secret=xxx
        (
            re.compile(
                r'(token|api_key|apikey|secret|key)\s*[=:]\s*["\']?([^"\'\s,;&]+)',
                re.IGNORECASE,
            ),
            r"\1=***",
        ),
        # Authorization: Bearer xxx
        (
            re.compile(
                r'(Authorization|Bearer)\s*[=:]\s*["\']?([^"\'\s,;&]+)', re.IGNORECASE
            ),
            r"\1=***",
        ),
        # 环境变量格式 VAR_PASSWORD=value
        (
            re.compile(
                r'([A-Z_]+_(PASSWORD|TOKEN|SECRET|KEY))\s*=\s*["\']?([^"\'\s,;&]+)',
                re.IGNORECASE,
            ),
            r"\1=***",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤并脱敏日志记录

        Args:
            record: 日志记录对象

        Returns:
            bool: 始终返回 True（不丢弃日志，只脱敏）
        """
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)

        # 处理 args 中可能包含的敏感信息
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._sanitize_value(v) for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(self._sanitize_value(a) for a in record.args)

        return True

    def _sanitize_value(self, value):
        """脱敏单个值"""
        if isinstance(value, str):
            for pattern, replacement in self.PATTERNS:
                value = pattern.sub(replacement, value)
        return value


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
        "RESET": "\033[0m",  # 重置
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


class AccountLogger:
    """账号专用日志记录器"""

    def __init__(self, account_name: str):
        self.account_name = account_name
        self.logger = logging.getLogger(f"account_{account_name}")
        self.logger.setLevel(logging.INFO)
        # 禁用向上传播，避免与 root logger 重复输出
        self.logger.propagate = False

        # 避免重复添加处理器
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.addFilter(SanitizingFilter())
            formatter = ColoredFormatter(
                "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def info(self, message: str):
        """记录信息日志"""
        self.logger.info(f"[{self.account_name}] {message}")

    def success(self, message: str):
        """记录成功日志"""
        self.logger.info(f"[{self.account_name}] ✅ {message}")

    def warning(self, message: str):
        """记录警告日志"""
        self.logger.warning(f"[{self.account_name}] ⚠️ {message}")

    def error(self, message: str):
        """记录错误日志"""
        self.logger.error(f"[{self.account_name}] ❌ {message}")

    def debug(self, message: str):
        """记录调试日志"""
        self.logger.debug(f"[{self.account_name}] 🔍 {message}")


def setup_logger(name: str = "router_checkin") -> logging.Logger:
    """设置标准日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    # 禁用向上传播，避免与 root logger 重复输出
    logger.propagate = False

    # 避免重复添加处理器
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(SanitizingFilter())
        formatter = ColoredFormatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def get_account_logger(account_name: str) -> AccountLogger:
    """获取账号日志记录器"""
    return AccountLogger(account_name)


# 创建全局日志记录器
logger = setup_logger()
