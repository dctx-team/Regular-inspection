"""
统一日志管理模块
"""

import logging
import sys
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
        'RESET': '\033[0m'      # 重置
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


class AccountLogger:
    """账号专用日志记录器"""

    def __init__(self, account_name: str):
        self.account_name = account_name
        self.logger = logging.getLogger(f"account_{account_name}")
        self.logger.setLevel(logging.INFO)

        # 避免重复添加处理器
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = ColoredFormatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
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

    # 避免重复添加处理器
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = ColoredFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def get_account_logger(account_name: str) -> AccountLogger:
    """获取账号日志记录器"""
    return AccountLogger(account_name)


# 创建全局日志记录器
logger = setup_logger()