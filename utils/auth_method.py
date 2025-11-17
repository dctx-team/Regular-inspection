"""
认证方式枚举定义（主分支稳定版）
"""

from enum import Enum


class AuthMethod(str, Enum):
    """认证方式枚举（继承str以支持JSON序列化）

    主分支仅支持稳定可靠的认证方式：
    - COOKIES: Cookie 认证（最快速、最稳定）
    - EMAIL: 邮箱密码认证（自动获取 Cookie）
    """

    COOKIES = "cookies"
    EMAIL = "email"

    @property
    def requires_human_verification(self) -> bool:
        """是否需要人机验证"""
        return False  # 主分支的认证方式都不需要人机验证

    @property
    def display_name(self) -> str:
        """显示名称"""
        display_names = {
            AuthMethod.COOKIES: "Cookies",
            AuthMethod.EMAIL: "Email/Password",
        }
        return display_names.get(self, self.value)

    @classmethod
    def from_string(cls, value: str) -> "AuthMethod":
        """从字符串转换（兼容旧配置）"""
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Unknown auth method: {value}. Valid options: {', '.join([m.value for m in cls])}")
