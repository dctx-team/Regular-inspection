"""
配置管理模块 - 使用数据类进行类型安全的配置管理
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from utils.logger import setup_logger

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
    method: str  # 'cookies' | 'email' | 'github' | 'linux.do'
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
                method="cookies",
                cookies=data["cookies"],
                api_user=data.get("api_user")
            ))

        # Email 认证
        if "email" in data:
            email_config = data["email"]
            auth_configs.append(AuthConfig(
                method="email",
                username=email_config.get("username") or email_config.get("email"),
                password=email_config.get("password")
            ))

        # GitHub 认证
        if "github" in data:
            github_config = data["github"]
            auth_configs.append(AuthConfig(
                method="github",
                username=github_config.get("username"),
                password=github_config.get("password")
            ))

        # Linux.do 认证
        if "linux.do" in data:
            linux_config = data["linux.do"]
            auth_configs.append(AuthConfig(
                method="linux.do",
                username=linux_config.get("username"),
                password=linux_config.get("password")
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
                status_url="https://anyrouter.top/api/user/status",
                auth_state_url="https://anyrouter.top/api/oauth/auth-state"
            ),
            "agentrouter": ProviderConfig(
                name="AgentRouter",
                base_url="https://agentrouter.org",
                login_url="https://agentrouter.org/login",
                # AgentRouter 使用 sign_in 接口，如果404则自动查询用户信息进行保活
                checkin_url="https://agentrouter.org/api/user/sign_in",
                user_info_url="https://agentrouter.org/api/user/self",
                status_url="https://agentrouter.org/api/user/status",
                auth_state_url="https://agentrouter.org/api/oauth/auth-state"
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


def validate_account(account: AccountConfig, index: int) -> bool:
    """验证账号配置"""
    if not account.auth_configs:
        logger.error(f"❌ Account {index + 1} ({account.name}): No authentication method configured")
        return False

    for auth in account.auth_configs:
        if auth.method == "cookies":
            if not auth.cookies:
                logger.error(f"❌ Account {index + 1} ({account.name}): Cookies auth requires cookies")
                return False
            # api_user 现在是可选的，可以从认证后的用户信息API自动获取
            if not auth.api_user:
                logger.info(f"ℹ️  Account {index + 1} ({account.name}): api_user 未配置，将从认证后自动获取")
        elif auth.method in ["email", "github", "linux.do"]:
            if not auth.username or not auth.password:
                logger.error(f"❌ Account {index + 1} ({account.name}): {auth.method} auth requires username and password")
                return False

    return True
