"""
认证模块单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from utils.auth_method import AuthMethod
from utils.config import AuthConfig, ProviderConfig


class TestCookiesAuthenticator:
    """Cookies 认证器测试"""

    @pytest.mark.auth
    @pytest.mark.asyncio
    async def test_authenticate_success(self, mock_page, mock_context, sample_provider_config):
        """测试 Cookies 认证成功场景"""
        from utils.auth import CookiesAuthenticator

        auth_config = AuthConfig(
            method=AuthMethod.COOKIES,
            cookies={"session": "test_session_value"},
            api_user="12345"
        )

        authenticator = CookiesAuthenticator(
            account_name="Test Account",
            auth_config=auth_config,
            provider_config=sample_provider_config
        )

        # Mock cookies 验证成功
        mock_context.cookies.return_value = [
            {"name": "session", "value": "test_session_value"}
        ]

        # Mock API 响应
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "data": {
                    "id": "12345",
                    "username": "test_user"
                }
            }
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            result = await authenticator.authenticate(mock_page, mock_context)

            assert result["success"] is True
            assert result["user_id"] == "12345"
            assert result["username"] == "test_user"

    @pytest.mark.auth
    @pytest.mark.asyncio
    async def test_authenticate_expired_cookies(self, mock_page, mock_context, sample_provider_config):
        """测试 Cookies 过期场景"""
        from utils.auth import CookiesAuthenticator

        auth_config = AuthConfig(
            method=AuthMethod.COOKIES,
            cookies={"session": "expired_session"},
            api_user="12345"
        )

        authenticator = CookiesAuthenticator(
            account_name="Test Account",
            auth_config=auth_config,
            provider_config=sample_provider_config
        )

        # Mock cookies 验证失败
        mock_page.url = "https://test.com/login"
        mock_context.cookies.return_value = [
            {"name": "session", "value": "expired_session"}
        ]

        # Mock API 返回 401
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            mock_page.goto = AsyncMock()

            result = await authenticator.authenticate(mock_page, mock_context)

            assert result["success"] is False
            assert "expired" in result["error"].lower() or "invalid" in result["error"].lower()


class TestEmailAuthenticator:
    """邮箱认证器测试"""

    @pytest.mark.auth
    @pytest.mark.asyncio
    async def test_authenticate_no_email_input(self, mock_page, mock_context, sample_provider_config):
        """测试找不到邮箱输入框场景"""
        from utils.auth import EmailAuthenticator

        auth_config = AuthConfig(
            method=AuthMethod.EMAIL,
            username="test@example.com",
            password="password123"
        )

        authenticator = EmailAuthenticator(
            account_name="Test Account",
            auth_config=auth_config,
            provider_config=sample_provider_config
        )

        # Mock 找不到邮箱输入框
        mock_page.query_selector.return_value = None

        result = await authenticator.authenticate(mock_page, mock_context)

        assert result["success"] is False
        assert "not found" in result["error"].lower()


# 添加更多测试用例...
# TODO: 添加 GitHub 和 Linux.do 认证器测试
