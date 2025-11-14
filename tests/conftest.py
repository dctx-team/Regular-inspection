"""
Pytest 配置和共享 fixtures
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from playwright.async_api import async_playwright


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于整个测试会话"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_page():
    """模拟 Playwright Page 对象"""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.query_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.wait_for_selector = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.title = AsyncMock(return_value="Test Page")
    page.url = "https://test.com"
    page.content = AsyncMock(return_value="<html><body>Test</body></html>")
    page.is_closed = Mock(return_value=False)
    page.close = AsyncMock()
    page.evaluate = AsyncMock()
    page.add_init_script = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_url = AsyncMock()
    page.mouse = Mock()
    page.mouse.move = AsyncMock()
    page.mouse.wheel = AsyncMock()
    page.keyboard = Mock()
    page.keyboard.press = AsyncMock()
    return page


@pytest.fixture
async def mock_context():
    """模拟 Playwright BrowserContext 对象"""
    context = AsyncMock()
    context.cookies = AsyncMock(return_value=[])
    context.add_cookies = AsyncMock()
    context.new_page = AsyncMock()
    context.close = AsyncMock()
    return context


@pytest.fixture
def sample_cookies():
    """示例 cookies 数据"""
    return {
        "session": "test_session_cookie_value_123456",
        "csrf_token": "test_csrf_token_789",
    }


@pytest.fixture
def sample_account_config():
    """示例账号配置"""
    from utils.config import AccountConfig, AuthConfig
    from utils.auth_method import AuthMethod

    return AccountConfig(
        name="Test Account",
        provider="anyrouter",
        auth_configs=[
            AuthConfig(
                method=AuthMethod.COOKIES,
                cookies={"session": "test_session"},
                api_user="12345"
            )
        ]
    )


@pytest.fixture
def sample_provider_config():
    """示例 Provider 配置"""
    from utils.config import ProviderConfig

    return ProviderConfig(
        name="TestProvider",
        base_url="https://test.example.com",
        login_url="https://test.example.com/login",
        checkin_url="https://test.example.com/api/user/sign_in",
        user_info_url="https://test.example.com/api/user/self",
    )
