"""
敏感信息脱敏模块
"""

import re
from typing import Any


# 敏感字段关键词
SENSITIVE_KEYWORDS = [
    'password', 'passwd', 'pwd',
    'secret', 'token', 'key',
    'api_key', 'apikey',
    'auth', 'credential',
    'otp', '2fa', 'totp',
    'cookie', 'session',
]


def sanitize_dict(data: dict, mask: str = "***") -> dict:
    """
    脱敏字典中的敏感信息

    Args:
        data: 需要脱敏的字典
        mask: 替换后的掩码字符串

    Returns:
        脱敏后的字典副本
    """
    if not isinstance(data, dict):
        return data

    sanitized = {}
    for key, value in data.items():
        key_lower = str(key).lower()

        # 检查key是否包含敏感关键词
        is_sensitive = any(keyword in key_lower for keyword in SENSITIVE_KEYWORDS)

        if is_sensitive:
            # 敏感字段用掩码替换
            sanitized[key] = mask
        elif isinstance(value, dict):
            # 递归处理嵌套字典
            sanitized[key] = sanitize_dict(value, mask)
        elif isinstance(value, list):
            # 处理列表
            sanitized[key] = [
                sanitize_dict(item, mask) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


def sanitize_string(text: str, mask: str = "***") -> str:
    """
    脱敏字符串中的敏感信息

    主要处理：
    1. 密码字段 (password=xxx, pwd=xxx)
    2. Token字段 (token=xxx, api_key=xxx)
    3. Cookie值

    Args:
        text: 需要脱敏的字符串
        mask: 替换后的掩码字符串

    Returns:
        脱敏后的字符串
    """
    if not isinstance(text, str):
        return str(text)

    # 脱敏模式列表
    patterns = [
        # password=xxx, pwd=xxx (各种分隔符)
        (r'(password|passwd|pwd)\s*[=:]\s*["\']?([^"\'\s,;&]+)', r'\1=***'),

        # token=xxx, api_key=xxx
        (r'(token|api_key|apikey|secret|key)\s*[=:]\s*["\']?([^"\'\s,;&]+)', r'\1=***'),

        # cookie: name=value
        (r'(cookie[s]?)\s*[=:]\s*\{[^}]*\}', r'\1={sanitized}'),

        # Authorization: Bearer xxx
        (r'(Authorization|Bearer)\s*[=:]\s*["\']?([^"\'\s,;&]+)', r'\1=***'),

        # 环境变量格式 VAR=value
        (r'([A-Z_]+_(PASSWORD|TOKEN|SECRET|KEY))\s*=\s*["\']?([^"\'\s,;&]+)', r'\1=***'),
    ]

    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


def sanitize_exception(exc: Exception) -> str:
    """
    脱敏异常消息和堆栈信息

    Args:
        exc: 异常对象

    Returns:
        脱敏后的异常消息字符串
    """
    # 获取异常消息
    exc_message = str(exc)

    # 脱敏消息
    sanitized_message = sanitize_string(exc_message)

    # 返回异常类型和脱敏后的消息
    return f"{type(exc).__name__}: {sanitized_message}"


def safe_repr(obj: Any, max_length: int = 100) -> str:
    """
    安全的对象表示，自动脱敏

    Args:
        obj: 要表示的对象
        max_length: 最大长度限制

    Returns:
        脱敏并截断后的字符串表示
    """
    try:
        if isinstance(obj, dict):
            obj = sanitize_dict(obj)

        repr_str = repr(obj)

        # 脱敏字符串内容
        repr_str = sanitize_string(repr_str)

        # 截断过长的内容
        if len(repr_str) > max_length:
            repr_str = repr_str[:max_length] + "..."

        return repr_str
    except Exception:
        return "<Unable to represent object safely>"
