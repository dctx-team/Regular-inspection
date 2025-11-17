"""
配置管理模块 - 使用数据类进行类型安全的配置管理
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from utils.logger import setup_logger
from utils.auth_method import AuthMethod

logger = setup_logger(__name__)


@dataclass
class ProviderConfig:
    """Provider 配置数据类"""
    name: str
    base_url: str
    login_url: str
    checkin_url: str
    user_info_url: str
    status_url: str = None  # API 状态接口，用于获取 client_id
    auth_state_url: str = None  # OAuth 认证状态接口
    api_user_key: str = "New-Api-User"  # API User header 键名

    def get_login_url(self) -> str:
        """获取登录URL"""
        return self.login_url

    def get_checkin_url(self) -> str:
        """获取签到URL"""
        return self.checkin_url

    def get_user_info_url(self) -> str:
        """获取用户信息URL"""
        return self.user_info_url
    
    def get_status_url(self) -> str:
        """获取状态URL"""
        return self.status_url or f"{self.base_url}/api/user/status"
    
    def get_auth_state_url(self) -> str:
        """获取认证状态URL"""
        return self.auth_state_url or f"{self.base_url}/api/user/auth_state"


@dataclass
class AuthConfig:
    """认证配置"""
    method: AuthMethod  # 认证方式枚举
    username: Optional[str] = None
    password: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None
    api_user: Optional[str] = None


@dataclass
class AccountConfig:
    """账号配置数据类"""
    name: str
    provider: str
    auth_configs: List[AuthConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict, index: int) -> "AccountConfig":
        """从字典创建 AccountConfig"""
        name = data.get("name", f"Account {index + 1}")
        provider = data.get("provider", "anyrouter")

        # 解析所有可能的认证方式
        auth_configs = []

        # Cookies 认证
        if "cookies" in data and data["cookies"]:
            auth_configs.append(AuthConfig(
                method=AuthMethod.COOKIES,
                cookies=data["cookies"],
                api_user=data.get("api_user")
            ))

        # Email 认证
        if "email" in data:
            email_config = data["email"]
            auth_configs.append(AuthConfig(
                method=AuthMethod.EMAIL,
                username=email_config.get("username") or email_config.get("email"),
                password=email_config.get("password")
            ))

        return cls(name=name, provider=provider, auth_configs=auth_configs)

    def get_display_name(self, index: int) -> str:
        """获取显示名称"""
        return self.name or f"Account {index + 1}"


@dataclass
class AppConfig:
    """应用配置"""
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)

    @classmethod
    def load_from_env(cls) -> "AppConfig":
        """从环境变量加载配置"""
        # 内置 Provider 配置
        default_providers = {
            "anyrouter": ProviderConfig(
                name="AnyRouter",
                base_url="https://anyrouter.top",
                login_url="https://anyrouter.top/login",
                checkin_url="https://anyrouter.top/api/user/sign_in",
                user_info_url="https://anyrouter.top/api/user/self",
                status_url="https://anyrouter.top/api/status",
                auth_state_url="https://anyrouter.top/api/oauth/state"
            ),
            "agentrouter": ProviderConfig(
                name="AgentRouter",
                base_url="https://agentrouter.org",
                login_url="https://agentrouter.org/login",
                # AgentRouter 使用 sign_in 接口，如果404则自动查询用户信息进行保活
                checkin_url="https://agentrouter.org/api/user/sign_in",
                user_info_url="https://agentrouter.org/api/user/self",
                status_url="https://agentrouter.org/api/status",
                auth_state_url="https://agentrouter.org/api/oauth/state"
            )
        }

        # 从环境变量加载自定义 Providers
        custom_providers_str = os.getenv("PROVIDERS")
        if custom_providers_str:
            try:
                custom_providers_data = json.loads(custom_providers_str)
                for name, config in custom_providers_data.items():
                    default_providers[name] = ProviderConfig(
                        name=config.get("name", name),
                        base_url=config["base_url"],
                        login_url=config["login_url"],
                        checkin_url=config["checkin_url"],
                        user_info_url=config["user_info_url"]
                    )
            except Exception as e:
                logger.warning(f"⚠️ Failed to load custom providers: {e}")

        return cls(providers=default_providers)

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """获取 Provider 配置"""
        return self.providers.get(name)


def load_accounts() -> Optional[List[AccountConfig]]:
    """从环境变量加载所有账号配置"""
    all_accounts = []

    # 加载 AnyRouter 账号
    anyrouter_str = os.getenv("ANYROUTER_ACCOUNTS")
    if anyrouter_str:
        try:
            anyrouter_data = json.loads(anyrouter_str)
            if isinstance(anyrouter_data, list):
                for i, account_data in enumerate(anyrouter_data):
                    account_data["provider"] = "anyrouter"
                    all_accounts.append(AccountConfig.from_dict(account_data, len(all_accounts)))
        except Exception as e:
            logger.error(f"❌ Failed to load ANYROUTER_ACCOUNTS: {e}")

    # 加载 AgentRouter 账号
    agentrouter_str = os.getenv("AGENTROUTER_ACCOUNTS")
    if agentrouter_str:
        try:
            agentrouter_data = json.loads(agentrouter_str)
            if isinstance(agentrouter_data, list):
                for i, account_data in enumerate(agentrouter_data):
                    account_data["provider"] = "agentrouter"
                    all_accounts.append(AccountConfig.from_dict(account_data, len(all_accounts)))
        except Exception as e:
            logger.error(f"❌ Failed to load AGENTROUTER_ACCOUNTS: {e}")

    # 加载统一的 ACCOUNTS 配置（支持多 Provider）
    accounts_str = os.getenv("ACCOUNTS")
    if accounts_str:
        try:
            accounts_data = json.loads(accounts_str)
            if isinstance(accounts_data, list):
                for i, account_data in enumerate(accounts_data):
                    all_accounts.append(AccountConfig.from_dict(account_data, len(all_accounts)))
        except Exception as e:
            logger.error(f"❌ Failed to load ACCOUNTS: {e}")

    return all_accounts if all_accounts else None


def validate_password_strength(password: str, account_name: str, index: int) -> tuple[bool, Optional[str]]:
    """验证密码强度

    Args:
        password: 密码
        account_name: 账号名称
        index: 账号索引

    Returns:
        (is_valid, error_message): 验证结果和错误消息

    环境变量:
        SKIP_PASSWORD_VALIDATION: 设置为 'true' 可跳过密码强度验证（不推荐，仅用于测试账号）
    """
    # 检查是否跳过密码验证
    if os.getenv('SKIP_PASSWORD_VALIDATION', 'false').lower() == 'true':
        logger.warning(f"⚠️ Account {index + 1} ({account_name}): 密码强度验证已跳过（SKIP_PASSWORD_VALIDATION=true）")
        return True, None

    # 检查密码最小长度
    if len(password) < 6:
        return False, f"密码长度不足（当前 {len(password)} 字符，最少需要 6 字符）"

    # 检查是否为常见弱密码（严重安全风险，必须拒绝）
    common_weak_passwords = [
        "123456", "password", "123456789", "12345678", "12345", "111111",
        "qwerty", "abc123", "password123", "admin", "letmein", "welcome",
        "monkey", "1234567890", "qwerty123", "123123", "000000", "654321"
    ]

    if password.lower() in common_weak_passwords:
        return False, f"密码过于简单（'{password}' 是常见弱密码，存在严重安全风险）"

    # 检查密码复杂度（建议但不强制）
    has_uppercase = bool(re.search(r'[A-Z]', password))
    has_lowercase = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'\d', password))
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;/`~]', password))

    complexity_count = sum([has_uppercase, has_lowercase, has_digit, has_special])

    # 如果密码较短（6-7字符）但复杂度不足，给出警告
    if len(password) < 8 and complexity_count < 3:
        logger.warning(
            f"⚠️ Account {index + 1} ({account_name}): 密码较短且复杂度不足 "
            f"(长度 {len(password)}，建议至少 8 字符并包含大写、小写、数字、特殊字符中的 3 种)"
        )

    # 如果密码足够长（8+字符）但仅包含单一字符类型，给出警告
    if len(password) >= 8 and complexity_count < 2:
        logger.warning(
            f"⚠️ Account {index + 1} ({account_name}): 密码复杂度不足 "
            f"(建议包含大写、小写、数字、特殊字符中的至少 2 种)"
        )

    # 检查是否为纯数字或纯字母（长度>=8时仅警告，长度<8时警告但不拒绝）
    if password.isdigit() and len(password) < 8:
        logger.warning(
            f"⚠️ Account {index + 1} ({account_name}): 密码为纯数字且长度 < 8，安全性较低 "
            f"(提示: 可设置 SKIP_PASSWORD_VALIDATION=true 跳过验证)"
        )

    if password.isalpha() and len(password) < 8:
        logger.warning(
            f"⚠️ Account {index + 1} ({account_name}): 密码为纯字母且长度 < 8，安全性较低 "
            f"(提示: 可设置 SKIP_PASSWORD_VALIDATION=true 跳过验证)"
        )

    # 检查重复字符（如 "111111", "aaaaaa"）
    if len(set(password)) <= 2 and len(password) >= 6:
        return False, f"密码过于简单（重复字符过多，存在安全风险）"

    # 检查连续字符（如 "123456", "abcdef"）
    consecutive_patterns = [
        "0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl"
    ]
    for pattern in consecutive_patterns:
        if password.lower() in pattern and len(password) >= 5:
            return False, f"密码过于简单（包含连续字符序列，存在安全风险）"

    return True, None


def validate_account(account: AccountConfig, index: int) -> bool:
    """验证账号配置（增强版）"""
    if not account.auth_configs:
        logger.error(f"❌ Account {index + 1} ({account.name}): No authentication method configured")
        return False

    for auth in account.auth_configs:
        if auth.method == AuthMethod.COOKIES:
            if not auth.cookies:
                logger.error(f"❌ Account {index + 1} ({account.name}): Cookies auth requires cookies")
                return False

            # 添加详细的cookies验证
            if not isinstance(auth.cookies, dict):
                logger.error(f"❌ Account {index + 1} ({account.name}): Cookies must be a dictionary")
                return False

            if len(auth.cookies) == 0:
                logger.error(f"❌ Account {index + 1} ({account.name}): Cookies dictionary cannot be empty")
                return False

            # api_user 现在是可选的，可以从认证后的用户信息API自动获取
            if not auth.api_user:
                logger.info(f"ℹ️  Account {index + 1} ({account.name}): api_user 未配置，将从认证后自动获取")

        elif auth.method == AuthMethod.EMAIL:
            if not auth.username or not auth.password:
                logger.error(f"❌ Account {index + 1} ({account.name}): {auth.method.value} auth requires username and password")
                return False

            # 添加用户名格式检查
            if not isinstance(auth.username, str) or len(auth.username.strip()) == 0:
                logger.error(f"❌ Account {index + 1} ({account.name}): Username must be a non-empty string")
                return False

            # 使用增强的密码强度验证
            is_valid, error_msg = validate_password_strength(auth.password, account.name, index)
            if not is_valid:
                logger.error(f"❌ Account {index + 1} ({account.name}): {error_msg}")
                return False

        else:
            logger.error(f"❌ Account {index + 1} ({account.name}): Unknown auth method '{auth.method.value}'")
            return False

    return True
