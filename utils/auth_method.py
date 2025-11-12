"""
认证方式枚举定义
"""

from enum import Enum


class AuthMethod(str, Enum):
    """认证方式枚举（继承str以支持JSON序列化）"""

    COOKIES = "cookies"
    EMAIL = "email"
    GITHUB = "github"
    LINUX_DO = "linux.do"

    @property
    def requires_human_verification(self) -> bool:
        """是否需要人机验证"""
        return self in (AuthMethod.GITHUB, AuthMethod.LINUX_DO)

    @property
    def display_name(self) -> str:
        """显示名称"""
        display_names = {
            AuthMethod.COOKIES: "Cookies",
            AuthMethod.EMAIL: "Email/Password",
            AuthMethod.GITHUB: "GitHub OAuth",
            AuthMethod.LINUX_DO: "Linux.do OAuth"
        }
        return display_names.get(self, self.value)

    @classmethod
    def from_string(cls, value: str) -> "AuthMethod":
        """从字符串转换（兼容旧配置）"""
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Unknown auth method: {value}. Valid options: {', '.join([m.value for m in cls])}")
