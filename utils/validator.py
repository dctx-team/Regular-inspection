"""
配置验证模块
"""

from typing import List, Dict, Any
from utils.config import AccountConfig, AuthConfig


def validate_account_config(account: AccountConfig) -> List[str]:
    """
    验证账号配置，返回错误列表

    Args:
        account: 账号配置对象

    Returns:
        List[str]: 错误信息列表，空列表表示验证通过
    """
    errors = []

    # 基础信息验证
    if not account.name or account.name.strip() == "":
        errors.append("账号名称不能为空")

    if not account.provider or account.provider.strip() == "":
        errors.append("Provider 不能为空")

    # 认证方式验证
    if not account.auth_configs:
        errors.append("未配置任何认证方式")
        return errors

    # 检查每种认证方式
    for i, auth in enumerate(account.auth_configs):
        auth_errors = _validate_auth_config(auth, i + 1)
        errors.extend(auth_errors)

    return errors


def _validate_auth_config(auth: AuthConfig, auth_index: int) -> List[str]:
    """验证单个认证配置"""
    errors = []
    prefix = f"认证方式 {auth_index}"

    if auth.method == "cookies":
        if not auth.cookies:
            errors.append(f"{prefix}: Cookies 认证缺少 cookies 配置")
        # 注意：api_user 是可选的，可以从认证后的用户信息API自动获取
        # 不再强制要求 session cookie，因为不同平台的cookie名称可能不同

    elif auth.method == "email":
        if not auth.username:
            errors.append(f"{prefix}: 邮箱认证缺少用户名")
        # 注意：不强制验证邮箱格式，因为某些平台可能使用用户名登录

        if not auth.password:
            errors.append(f"{prefix}: 邮箱认证缺少密码")

    else:
        errors.append(f"{prefix}: 未知的认证方式 '{auth.method}'")

    return errors


def validate_environment_variables() -> Dict[str, Any]:
    """
    验证环境变量配置

    Returns:
        Dict: 包含验证结果和详细信息
    """
    import os

    result = {
        "valid": True,
        "warnings": [],
        "errors": [],
        "configured_accounts": 0,
        "configured_providers": []
    }

    # 检查账号配置
    account_env_vars = [
        ("ACCOUNTS", "统一账号配置"),
        ("ANYROUTER_ACCOUNTS", "AnyRouter 账号配置"),
        ("AGENTROUTER_ACCOUNTS", "AgentRouter 账号配置")
    ]

    has_accounts = False
    for env_var, desc in account_env_vars:
        if os.getenv(env_var):
            has_accounts = True
            result["configured_accounts"] += 1

            # 尝试解析 JSON
            try:
                import json
                accounts_data = json.loads(os.getenv(env_var))
                if isinstance(accounts_data, list):
                    result["configured_providers"].append(f"{desc}: {len(accounts_data)} 个账号")
                else:
                    result["warnings"].append(f"{env_var} 不是有效的 JSON 数组")
            except Exception as e:
                result["errors"].append(f"{env_var} JSON 解析失败: {e}")
                result["valid"] = False

    if not has_accounts:
        result["errors"].append("未配置任何账号信息")
        result["valid"] = False

    # 检查通知配置（可选）
    notification_env_vars = [
        ("SERVERPUSHKEY", "Server酱通知"),
        ("EMAIL_USER", "邮件通知"),
        ("DINGDING_WEBHOOK", "钉钉通知"),
        ("FEISHU_WEBHOOK", "飞书通知"),
        ("WEIXIN_WEBHOOK", "企业微信通知"),
        ("PUSHPLUS_TOKEN", "PushPlus 通知")
    ]

    notifications_configured = []
    for env_var, desc in notification_env_vars:
        if os.getenv(env_var):
            notifications_configured.append(desc)

    if notifications_configured:
        result["notifications"] = notifications_configured
    else:
        result["warnings"].append("未配置任何通知方式")

    return result


def print_validation_summary(result: Dict[str, Any]):
    """打印验证结果摘要"""
    print("\n" + "="*60)
    print("📋 配置验证结果")
    print("="*60)

    if result["valid"]:
        print("✅ 配置验证通过")
    else:
        print("❌ 配置验证失败")

    print(f"\n📊 账号配置: {result['configured_accounts']} 种")
    for provider_info in result.get("configured_providers", []):
        print(f"   - {provider_info}")

    if result.get("notifications"):
        print(f"\n🔔 通知配置: {len(result['notifications'])} 种")
        for notification in result["notifications"]:
            print(f"   - {notification}")

    if result["warnings"]:
        print(f"\n⚠️ 警告 ({len(result['warnings'])} 个):")
        for warning in result["warnings"]:
            print(f"   - {warning}")

    if result["errors"]:
        print(f"\n❌ 错误 ({len(result['errors'])} 个):")
        for error in result["errors"]:
            print(f"   - {error}")

    print("="*60)