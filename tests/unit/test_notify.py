"""
通知模块单元测试（mocked）
"""
import pytest
from unittest.mock import patch, MagicMock
from utils.notify import NotificationKit


@pytest.fixture
def notification_kit():
    """创建通知工具实例"""
    with patch.dict("os.environ", {
        "EMAIL_USER": "test@qq.com",
        "EMAIL_PASS": "test_auth_code",
        "EMAIL_TO": "recipient@example.com",
        "PUSHPLUS_TOKEN": "test_pushplus_token",
        "SERVERPUSHKEY": "test_server_key",
        "DINGDING_WEBHOOK": "https://oapi.dingtalk.com/robot/send?access_token=test",
        "FEISHU_WEBHOOK": "https://open.feishu.cn/open-apis/bot/v2/hook/test",
        "WEIXIN_WEBHOOK": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
    }):
        yield NotificationKit()


class TestChannelDetection:
    """通知渠道检测测试"""

    def test_all_channels_configured(self, notification_kit):
        """测试所有渠道已配置"""
        assert notification_kit.email_user == "test@qq.com"
        assert notification_kit.pushplus_token == "test_pushplus_token"
        assert notification_kit.server_push_key == "test_server_key"
        assert notification_kit.dingding_webhook is not None
        assert notification_kit.feishu_webhook is not None
        assert notification_kit.weixin_webhook is not None

    def test_no_channels_configured(self):
        """测试无渠道配置"""
        with patch.dict("os.environ", {}, clear=True):
            kit = NotificationKit()
            assert kit.email_user == ""
            assert kit.pushplus_token is None
            assert kit.server_push_key is None

    def test_partial_channels(self):
        """测试部分渠道配置"""
        with patch.dict("os.environ", {
            "EMAIL_USER": "test@example.com",
            "EMAIL_PASS": "pass",
            "EMAIL_TO": "to@example.com",
        }, clear=True):
            kit = NotificationKit()
            assert kit.email_user == "test@example.com"
            assert kit.pushplus_token is None


class TestSMTPAutoDetection:
    """SMTP 服务商自动识别测试"""

    @patch("smtplib.SMTP_SSL")
    def test_qq_smtp_detection(self, mock_smtp):
        """测试 QQ 邮箱 SMTP 自动识别"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {
            "EMAIL_USER": "test@qq.com",
            "EMAIL_PASS": "auth_code",
            "EMAIL_TO": "to@example.com",
        }, clear=True):
            kit = NotificationKit()
            kit.send_email("Test", "Content")
            mock_smtp.assert_called_once_with("smtp.qq.com", 465, timeout=30)

    @patch("smtplib.SMTP_SSL")
    def test_163_smtp_detection(self, mock_smtp):
        """测试 163 邮箱 SMTP 自动识别"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {
            "EMAIL_USER": "test@163.com",
            "EMAIL_PASS": "auth_code",
            "EMAIL_TO": "to@example.com",
        }, clear=True):
            kit = NotificationKit()
            kit.send_email("Test", "Content")
            mock_smtp.assert_called_once_with("smtp.163.com", 465, timeout=30)

    @patch("smtplib.SMTP")
    def test_gmail_smtp_detection(self, mock_smtp):
        """测试 Gmail SMTP 自动识别（STARTTLS）"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {
            "EMAIL_USER": "test@gmail.com",
            "EMAIL_PASS": "app_password",
            "EMAIL_TO": "to@example.com",
        }, clear=True):
            kit = NotificationKit()
            kit.send_email("Test", "Content")
            mock_smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=30)

    def test_missing_email_config_raises(self):
        """测试缺少邮件配置抛出异常"""
        with patch.dict("os.environ", {}, clear=True):
            kit = NotificationKit()
            with pytest.raises(ValueError, match="Email configuration not set"):
                kit.send_email("Test", "Content")


class TestPushMessage:
    """push_message 统一发送测试"""

    def test_no_configured_channels_logs_warning(self):
        """测试无配置渠道时的警告"""
        with patch.dict("os.environ", {}, clear=True):
            kit = NotificationKit()
            # 不应抛出异常
            kit.push_message("Test", "Content")

    @patch("smtplib.SMTP_SSL")
    def test_sends_to_configured_channels(self, mock_smtp):
        """测试发送到已配置的渠道"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {
            "EMAIL_USER": "test@qq.com",
            "EMAIL_PASS": "pass",
            "EMAIL_TO": "to@example.com",
        }, clear=True):
            kit = NotificationKit()
            kit.push_message("Title", "Content")
            mock_smtp.assert_called_once()
