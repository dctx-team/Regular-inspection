"""
配置验证模块单元测试
"""
import os
import pytest
from unittest.mock import patch

from utils.validator import (
    validate_account_config,
    validate_environment_variables,
)
from utils.config import AccountConfig, AuthConfig
from utils.auth_method import AuthMethod


class TestValidateAccountConfig:
    """账号配置验证测试"""

    def test_valid_cookies_config(self):
        """测试有效的 Cookies 配置"""
        account = AccountConfig(
            name="Test",
            provider="anyrouter",
            auth_configs=[
                AuthConfig(
                    method=AuthMethod.COOKIES,
                    cookies={"session": "test_value"},
                    api_user="12345"
                )
            ]
        )
        errors = validate_account_config(account)
        assert len(errors) == 0

    def test_valid_email_config(self):
        """测试有效的 Email 配置"""
        account = AccountConfig(
            name="Test",
            provider="anyrouter",
            auth_configs=[
                AuthConfig(
                    method=AuthMethod.EMAIL,
                    username="test@example.com",
                    password="StrongP@ss1"
                )
            ]
        )
        errors = validate_account_config(account)
        assert len(errors) == 0

    def test_empty_name(self):
        """测试空名称"""
        account = AccountConfig(
            name="",
            provider="anyrouter",
            auth_configs=[
                AuthConfig(
                    method=AuthMethod.COOKIES,
                    cookies={"session": "test"},
                )
            ]
        )
        errors = validate_account_config(account)
        assert any("名称" in e for e in errors)

    def test_empty_provider(self):
        """测试空 Provider"""
        account = AccountConfig(
            name="Test",
            provider="",
            auth_configs=[
                AuthConfig(
                    method=AuthMethod.COOKIES,
                    cookies={"session": "test"},
                )
            ]
        )
        errors = validate_account_config(account)
        assert any("Provider" in e for e in errors)

    def test_no_auth_configs(self):
        """测试无认证配置"""
        account = AccountConfig(
            name="Test",
            provider="anyrouter",
            auth_configs=[]
        )
        errors = validate_account_config(account)
        assert any("认证方式" in e for e in errors)

    def test_cookies_auth_missing_cookies(self):
        """测试 Cookies 认证缺少 cookies"""
        account = AccountConfig(
            name="Test",
            provider="anyrouter",
            auth_configs=[
                AuthConfig(method=AuthMethod.COOKIES, cookies=None)
            ]
        )
        errors = validate_account_config(account)
        assert len(errors) > 0

    def test_email_auth_missing_username(self):
        """测试 Email 认证缺少用户名"""
        account = AccountConfig(
            name="Test",
            provider="anyrouter",
            auth_configs=[
                AuthConfig(
                    method=AuthMethod.EMAIL,
                    username=None,
                    password="password123"
                )
            ]
        )
        errors = validate_account_config(account)
        assert any("用户名" in e for e in errors)

    def test_email_auth_missing_password(self):
        """测试 Email 认证缺少密码"""
        account = AccountConfig(
            name="Test",
            provider="anyrouter",
            auth_configs=[
                AuthConfig(
                    method=AuthMethod.EMAIL,
                    username="test@example.com",
                    password=None
                )
            ]
        )
        errors = validate_account_config(account)
        assert any("密码" in e for e in errors)


class TestValidateEnvironmentVariables:
    """环境变量验证测试"""

    def test_no_accounts_configured(self):
        """测试无账号配置"""
        with patch.dict("os.environ", {}, clear=True):
            result = validate_environment_variables()
            assert result["valid"] is False
            assert any("未配置" in e for e in result["errors"])

    def test_valid_accounts_env(self):
        """测试有效的账号环境变量"""
        import json
        accounts = [{"name": "test", "cookies": {"session": "v"}}]
        with patch.dict("os.environ", {
            "ACCOUNTS": json.dumps(accounts),
        }, clear=True):
            result = validate_environment_variables()
            assert result["valid"] is True
            assert result["configured_accounts"] >= 1

    def test_invalid_json_accounts(self):
        """测试无效 JSON 格式的账号配置"""
        with patch.dict("os.environ", {
            "ACCOUNTS": "invalid json{{{",
        }, clear=True):
            result = validate_environment_variables()
            assert result["valid"] is False
            assert any("JSON" in e for e in result["errors"])

    def test_notification_detection(self):
        """测试通知配置检测"""
        import json
        accounts = [{"name": "test", "cookies": {"session": "v"}}]
        with patch.dict("os.environ", {
            "ACCOUNTS": json.dumps(accounts),
            "SERVERPUSHKEY": "test_key",
            "PUSHPLUS_TOKEN": "test_token",
        }, clear=True):
            result = validate_environment_variables()
            assert "notifications" in result
            assert len(result["notifications"]) == 2

    def test_no_notification_warning(self):
        """测试无通知配置的警告"""
        import json
        accounts = [{"name": "test", "cookies": {"session": "v"}}]
        with patch.dict("os.environ", {
            "ACCOUNTS": json.dumps(accounts),
        }, clear=True):
            result = validate_environment_variables()
            assert any("通知" in w for w in result["warnings"])
