"""
敏感信息脱敏模块单元测试
"""

import pytest
from utils.sanitizer import (
    sanitize_dict,
    sanitize_string,
    sanitize_exception,
    safe_repr,
)


class TestSanitizeDict:
    """sanitize_dict 测试"""

    def test_mask_sensitive_fields(self):
        """测试敏感字段掩码"""
        data = {
            "username": "admin",
            "password": "secret123",
            "token": "abc-xyz-123",
            "api_key": "sk-12345",
        }
        result = sanitize_dict(data)
        assert result["username"] == "admin"
        assert result["password"] == "***"
        assert result["token"] == "***"
        assert result["api_key"] == "***"

    def test_nested_dict(self):
        """测试嵌套字典处理"""
        data = {
            "user": {
                "name": "test",
                "password": "secret",
                "profile": {"api_key": "key123"},
            }
        }
        result = sanitize_dict(data)
        assert result["user"]["name"] == "test"
        assert result["user"]["password"] == "***"
        assert result["user"]["profile"]["api_key"] == "***"

    def test_list_handling(self):
        """测试列表处理"""
        data = {
            "accounts": [
                {"name": "user1", "password": "pass1"},
                {"name": "user2", "password": "pass2"},
            ]
        }
        result = sanitize_dict(data)
        assert result["accounts"][0]["name"] == "user1"
        assert result["accounts"][0]["password"] == "***"
        assert result["accounts"][1]["password"] == "***"

    def test_non_dict_input(self):
        """测试非字典输入"""
        assert sanitize_dict("string") == "string"
        assert sanitize_dict(123) == 123

    def test_custom_mask(self):
        """测试自定义掩码"""
        data = {"password": "secret"}
        result = sanitize_dict(data, mask="[REDACTED]")
        assert result["password"] == "[REDACTED]"

    def test_empty_dict(self):
        """测试空字典"""
        assert sanitize_dict({}) == {}

    def test_case_insensitive_keys(self):
        """测试键名大小写不敏感"""
        data = {"Password": "secret", "TOKEN": "abc123"}
        result = sanitize_dict(data)
        assert result["Password"] == "***"
        assert result["TOKEN"] == "***"


class TestSanitizeString:
    """sanitize_string 测试"""

    def test_password_sanitization(self):
        """测试密码脱敏"""
        text = "login with password=secret123 ok"
        result = sanitize_string(text)
        assert "secret123" not in result
        assert "password=***" in result

    def test_token_sanitization(self):
        """测试 token 脱敏"""
        text = "using token=abc-xyz-123 for auth"
        result = sanitize_string(text)
        assert "abc-xyz-123" not in result
        assert "token=***" in result

    def test_cookie_sanitization(self):
        """测试 cookie 脱敏"""
        text = "cookies={session: abc, token: xyz}"
        result = sanitize_string(text)
        # sanitize_string 会处理 cookies={...} 模式或 token=xxx 模式
        assert "token=***" in result or "sanitized" in result

    def test_non_string_input(self):
        """测试非字符串输入"""
        result = sanitize_string(12345)
        assert result == "12345"

    def test_no_sensitive_data(self):
        """测试无敏感数据"""
        text = "this is a normal log message"
        result = sanitize_string(text)
        assert result == text

    def test_authorization_header(self):
        """测试 Authorization 脱敏"""
        text = "Authorization:Bearer_eyJhbGciOiJIUzI1NiJ9"
        result = sanitize_string(text)
        assert "Authorization=***" in result or "eyJhbGciOiJIUzI1NiJ9" not in result


class TestSanitizeException:
    """sanitize_exception 测试"""

    def test_exception_with_password(self):
        """测试包含密码的异常消息脱敏"""
        exc = ValueError("login failed with password=mysecret")
        result = sanitize_exception(exc)
        assert "ValueError" in result
        assert "mysecret" not in result

    def test_exception_type_preserved(self):
        """测试异常类型保留"""
        exc = ConnectionError("timeout connecting to server")
        result = sanitize_exception(exc)
        assert "ConnectionError" in result
        assert "timeout" in result

    def test_clean_exception(self):
        """测试无敏感信息的异常"""
        exc = RuntimeError("something went wrong")
        result = sanitize_exception(exc)
        assert "RuntimeError" in result
        assert "something went wrong" in result


class TestSafeRepr:
    """safe_repr 测试"""

    def test_dict_sanitization(self):
        """测试字典安全表示"""
        obj = {"username": "admin", "password": "secret"}
        result = safe_repr(obj)
        assert "secret" not in result
        assert "***" in result

    def test_length_truncation(self):
        """测试长度截断"""
        obj = "a" * 200
        result = safe_repr(obj, max_length=50)
        assert len(result) <= 53  # 50 + "..."
        assert result.endswith("...")

    def test_short_string(self):
        """测试短字符串不截断"""
        result = safe_repr("hello", max_length=100)
        assert "hello" in result
        assert "..." not in result

    def test_error_handling(self):
        """测试错误处理"""

        # 应该返回安全的错误表示而不是崩溃
        class BadRepr:
            def __repr__(self):
                raise RuntimeError("repr failed")

        result = safe_repr(BadRepr())
        assert "Unable to represent" in result
