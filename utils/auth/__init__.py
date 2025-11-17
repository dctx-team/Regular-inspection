"""
认证模块 - 处理不同的认证方式（主分支稳定版）
"""

from utils.auth.base import Authenticator
from utils.auth.cookies import CookiesAuthenticator
from utils.auth.email import EmailAuthenticator

from utils.config import AuthConfig, ProviderConfig
from utils.auth_method import AuthMethod


def get_authenticator(account_name: str, auth_config: AuthConfig, provider_config: ProviderConfig) -> Authenticator:
    """获取对应的认证器"""
    if auth_config.method == AuthMethod.COOKIES:
        return CookiesAuthenticator(account_name, auth_config, provider_config)
    elif auth_config.method == AuthMethod.EMAIL:
        return EmailAuthenticator(account_name, auth_config, provider_config)
    else:
        raise ValueError(f"Unknown auth method: {auth_config.method.value}")


__all__ = [
    "Authenticator",
    "CookiesAuthenticator",
    "EmailAuthenticator",
    "get_authenticator",
]
