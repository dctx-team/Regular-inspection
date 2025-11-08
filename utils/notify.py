import os
import smtplib
import logging
from email.mime.text import MIMEText
from typing import Literal

import httpx


logger = logging.getLogger(__name__)


class NotificationKit:
    def __init__(self) -> None:
        self.email_user: str = os.getenv('EMAIL_USER', '')
        self.email_pass: str = os.getenv('EMAIL_PASS', '')
        self.email_to: str = os.getenv('EMAIL_TO', '')
        self.smtp_server: str = os.getenv('CUSTOM_SMTP_SERVER', '')
        self.pushplus_token = os.getenv('PUSHPLUS_TOKEN')
        self.server_push_key = os.getenv('SERVERPUSHKEY')
        self.dingding_webhook = os.getenv('DINGDING_WEBHOOK')
        self.feishu_webhook = os.getenv('FEISHU_WEBHOOK')
        self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')

    def send_email(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text') -> None:
        if not self.email_user or not self.email_pass or not self.email_to:
            raise ValueError('Email configuration not set')

        try:
            # 使用简单的 MIMEText 而不是 MIMEMultipart，避免被识别为二进制
            if msg_type == 'html':
                msg = MIMEText(content, 'html', 'utf-8')
            else:
                msg = MIMEText(content, 'plain', 'utf-8')

            msg['From'] = f'Router签到助手 <{self.email_user}>'
            msg['To'] = self.email_to
            msg['Subject'] = title

            # 智能检测 SMTP 服务器
            smtp_host = None
            smtp_port = 465
            use_ssl = True

            if self.smtp_server and self.smtp_server.strip():
                # 用户指定了自定义服务器
                smtp_host = self.smtp_server.strip()
            else:
                # 自动检测邮箱服务商
                domain = self.email_user.split('@')[1].lower()

                # 常见邮箱服务商配置
                email_providers = {
                    'qq.com': ('smtp.qq.com', 465, True),
                    'vip.qq.com': ('smtp.qq.com', 465, True),
                    'foxmail.com': ('smtp.qq.com', 465, True),
                    '163.com': ('smtp.163.com', 465, True),
                    '126.com': ('smtp.126.com', 465, True),
                    'yeah.net': ('smtp.yeah.net', 465, True),
                    'gmail.com': ('smtp.gmail.com', 587, False),
                    'outlook.com': ('smtp.office365.com', 587, False),
                    'hotmail.com': ('smtp.office365.com', 587, False),
                    'live.com': ('smtp.office365.com', 587, False),
                    'sina.com': ('smtp.sina.com', 465, True),
                    'sina.cn': ('smtp.sina.cn', 465, True),
                    'sohu.com': ('smtp.sohu.com', 465, True),
                    '139.com': ('smtp.139.com', 465, True),
                    '189.cn': ('smtp.189.cn', 465, True),
                }

                if domain in email_providers:
                    smtp_host, smtp_port, use_ssl = email_providers[domain]
                    logger.debug(f'检测到邮箱服务商: {domain} -> {smtp_host}:{smtp_port}')
                else:
                    # 默认使用标准格式
                    smtp_host = f'smtp.{domain}'
                    logger.debug(f'使用默认 SMTP 服务器: {smtp_host}')

            # 尝试连接并发送
            if use_ssl:
                # 尝试 SSL (465)
                try:
                    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                        server.login(self.email_user, self.email_pass)
                        server.send_message(msg)
                        logger.debug(f'邮件发送成功 via SSL:{smtp_port}')
                except Exception as ssl_error:
                    # SSL 失败，尝试 STARTTLS (587)
                    logger.debug(f'SSL ({smtp_port}) 连接失败，尝试 STARTTLS (587): {ssl_error}')
                    with smtplib.SMTP(smtp_host, 587, timeout=30) as server:
                        server.starttls()
                        server.login(self.email_user, self.email_pass)
                        server.send_message(msg)
                        logger.debug(f'邮件发送成功 via STARTTLS:587')
            else:
                # 使用 STARTTLS
                with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                    server.starttls()
                    server.login(self.email_user, self.email_pass)
                    server.send_message(msg)
                    logger.debug(f'邮件发送成功 via STARTTLS:{smtp_port}')

        except Exception as e:
            # 提供更详细的错误信息
            error_msg = str(e)
            if 'authentication failed' in error_msg.lower() or 'auth' in error_msg.lower():
                raise ValueError(f'邮箱认证失败，请检查邮箱地址和授权码')
            elif 'timeout' in error_msg.lower():
                raise ValueError(f'SMTP 服务器连接超时，请检查网络或尝试其他端口')
            elif 'name or service not known' in error_msg.lower():
                raise ValueError(f'SMTP 服务器地址无法解析: {smtp_host}，请检查 CUSTOM_SMTP_SERVER 配置或邮箱地址')
            elif 'connection refused' in error_msg.lower():
                raise ValueError(f'SMTP 服务器拒绝连接: {smtp_host}:{smtp_port}')
            else:
                raise ValueError(f'邮件发送失败: {error_msg}')

    def send_pushplus(self, title: str, content: str) -> None:
        if not self.pushplus_token:
            raise ValueError('PushPlus Token not configured')

        data = {'token': self.pushplus_token, 'title': title, 'content': content, 'template': 'html'}
        with httpx.Client(timeout=30.0) as client:
            client.post('http://www.pushplus.plus/send', json=data)

    def send_serverPush(self, title: str, content: str) -> None:
        if not self.server_push_key:
            raise ValueError('Server Push key not configured')

        data = {'title': title, 'desp': content}
        with httpx.Client(timeout=30.0) as client:
            client.post(f'https://sctapi.ftqq.com/{self.server_push_key}.send', json=data)

    def send_dingtalk(self, title: str, content: str) -> None:
        if not self.dingding_webhook:
            raise ValueError('DingTalk Webhook not configured')

        data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
        with httpx.Client(timeout=30.0) as client:
            client.post(self.dingding_webhook, json=data)

    def send_feishu(self, title: str, content: str) -> None:
        if not self.feishu_webhook:
            raise ValueError('Feishu Webhook not configured')

        data = {
            'msg_type': 'interactive',
            'card': {
                'elements': [{'tag': 'markdown', 'content': content, 'text_align': 'left'}],
                'header': {'template': 'blue', 'title': {'content': title, 'tag': 'plain_text'}},
            },
        }
        with httpx.Client(timeout=30.0) as client:
            client.post(self.feishu_webhook, json=data)

    def send_wecom(self, title: str, content: str) -> None:
        if not self.weixin_webhook:
            raise ValueError('WeChat Work Webhook not configured')

        data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
        with httpx.Client(timeout=30.0) as client:
            client.post(self.weixin_webhook, json=data)

    def push_message(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text') -> None:
        notifications = [
            ('Email', lambda: self.send_email(title, content, msg_type)),
            ('PushPlus', lambda: self.send_pushplus(title, content)),
            ('Server Push', lambda: self.send_serverPush(title, content)),
            ('DingTalk', lambda: self.send_dingtalk(title, content)),
            ('Feishu', lambda: self.send_feishu(title, content)),
            ('WeChat Work', lambda: self.send_wecom(title, content)),
        ]

        success_count = 0
        failed_count = 0

        for name, func in notifications:
            try:
                func()
                logger.info(f'[{name}]: Message push successful!')
                logger.info(f'[{name}]: 通知发送成功')
                success_count += 1
            except Exception as e:
                error_msg = f'[{name}]: Message push failed! Reason: {str(e)}'
                logger.error(error_msg)
                logger.error(error_msg)
                failed_count += 1

        # 记录总体通知结果
        if success_count == 0 and failed_count > 0:
            logger.error(f'所有通知方式都失败 ({failed_count} 个)')
        elif failed_count > 0:
            logger.warning(f'部分通知失败: 成功 {success_count}, 失败 {failed_count}')
        else:
            logger.info(f'所有通知发送成功 ({success_count} 个)')


notify = NotificationKit()
