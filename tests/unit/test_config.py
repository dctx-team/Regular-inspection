"""
配置模块单元测试
"""
import pytest
import os
from utils.config import (
    validate_password_strength,
    AccountConfig,
    ProviderConfig,
    AuthConfig
)
from utils.auth_method import AuthMethod


class TestPasswordValidation:
    """密码强度验证测试"""

    def test_valid_password_strong(self):
        """测试强密码"""
        is_valid, error = validate_password_strength("MyP@ssw0rd123!", "test", 0)
        assert is_valid is True
        assert error is None

    def test_valid_password_medium(self):
        """测试中等强度密码"""
        is_valid, error = validate_password_strength("password123", "test", 0)
        assert is_valid is True
        assert error is None

    def test_invalid_password_too_short(self):
        """测试过短密码"""
        is_valid, error = validate_password_strength("12345", "test", 0)
        assert is_valid is False
        assert "长度不足" in error

    def test_invalid_password_common_weak(self):
        """测试常见弱密码"""
        is_valid, error = validate_password_strength("123456", "test", 0)
        assert is_valid is False
        assert "常见弱密码" in error

    def test_invalid_password_repeated_chars(self):
        """测试重复字符密码"""
        is_valid, error = validate_password_strength("111111", "test", 0)
        assert is_valid is False
        assert "重复字符" in error

    def test_invalid_password_consecutive_chars(self):
        """测试连续字符密码"""
        is_valid, error = validate_password_strength("123456", "test", 0)
        assert is_valid is False
        assert "连续字符" in error

    def test_skip_validation_env(self, monkeypatch):
        """测试跳过密码验证环境变量"""
        monkeypatch.setenv("SKIP_PASSWORD_VALIDATION", "true")
        is_valid, error = validate_password_strength("123456", "test", 0)
        assert is_valid is True
        assert error is None


class TestAccountConfig:
    """账号配置测试"""

    def test_from_dict_cookies_auth(self):
        """测试从字典创建 Cookies 认证配置"""
        data = {
            "name": "Test Account",
            "provider": "anyrouter",
            "cookies": {"session": "test_value"},
            "api_user": "12345"
        }
        config = AccountConfig.from_dict(data, 0)

        assert config.name == "Test Account"
        assert config.provider == "anyrouter"
        assert len(config.auth_configs) == 1
        assert config.auth_configs[0].method == AuthMethod.COOKIES
        assert config.auth_configs[0].cookies == {"session": "test_value"}
        assert config.auth_configs[0].api_user == "12345"

    def test_from_dict_email_auth(self):
        """测试从字典创建邮箱认证配置"""
        data = {
            "name": "Email Account",
            "provider": "anyrouter",
            "email": {
                "username": "test@example.com",
                "password": "password123"
            }
        }
        config = AccountConfig.from_dict(data, 0)

        assert len(config.auth_configs) == 1
        assert config.auth_configs[0].method == AuthMethod.EMAIL
        assert config.auth_configs[0].username == "test@example.com"
        assert config.auth_configs[0].password == "password123"

    def test_from_dict_multiple_auth(self):
        """测试从字典创建多种认证方式配置"""
        data = {
            "name": "Multi Auth",
            "provider": "anyrouter",
            "cookies": {"session": "test"},
            "api_user": "12345",
            "email": {
                "username": "test@example.com",
                "password": "password123"
            }
        }
        config = AccountConfig.from_dict(data, 0)

        assert len(config.auth_configs) == 2
        methods = [auth.method for auth in config.auth_configs]
        assert AuthMethod.COOKIES in methods
        assert AuthMethod.EMAIL in methods


class TestProviderConfig:
    """Provider 配置测试"""

    def test_provider_urls(self):
        """测试 Provider URL 生成"""
        provider = ProviderConfig(
            name="TestProvider",
            base_url="https://test.com",
            login_url="https://test.com/login",
            checkin_url="https://test.com/api/sign_in",
            user_info_url="https://test.com/api/user"
        )

        assert provider.get_login_url() == "https://test.com/login"
        assert provider.get_checkin_url() == "https://test.com/api/sign_in"
        assert provider.get_user_info_url() == "https://test.com/api/user"

    def test_provider_status_url_default(self):
        """测试 Provider 状态 URL 默认生成"""
        provider = ProviderConfig(
            name="TestProvider",
            base_url="https://test.com",
            login_url="https://test.com/login",
            checkin_url="https://test.com/api/sign_in",
            user_info_url="https://test.com/api/user"
        )

        assert provider.get_status_url() == "https://test.com/api/user/status"
        assert provider.get_auth_state_url() == "https://test.com/api/user/auth_state"
