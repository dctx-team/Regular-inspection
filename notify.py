import os
import smtplib
from email.mime.text import MIMEText
from typing import Literal

import httpx


class NotificationKit:
	def __init__(self):
		self.email_user: str = os.getenv('EMAIL_USER', '')
		self.email_pass: str = os.getenv('EMAIL_PASS', '')
		self.email_to: str = os.getenv('EMAIL_TO', '')
		self.smtp_server: str = os.getenv('CUSTOM_SMTP_SERVER', '')
		self.pushplus_token = os.getenv('PUSHPLUS_TOKEN')
		self.server_push_key = os.getenv('SERVERPUSHKEY')
		self.dingding_webhook = os.getenv('DINGDING_WEBHOOK')
		self.feishu_webhook = os.getenv('FEISHU_WEBHOOK')
		self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')

	def send_email(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
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

			# 自动检测 SMTP 服务器
			if self.smtp_server:
				smtp_host = self.smtp_server
			else:
				domain = self.email_user.split('@')[1]
				smtp_host = f'smtp.{domain}'

			# 尝试 SSL 连接 (端口 465)
			try:
				with smtplib.SMTP_SSL(smtp_host, 465, timeout=30) as server:
					server.login(self.email_user, self.email_pass)
					server.send_message(msg)
			except Exception as ssl_error:
				# 如果 SSL 失败，尝试 STARTTLS (端口 587)
				print(f'[DEBUG] SSL (465) 连接失败，尝试 STARTTLS (587): {ssl_error}')
				with smtplib.SMTP(smtp_host, 587, timeout=30) as server:
					server.starttls()
					server.login(self.email_user, self.email_pass)
					server.send_message(msg)

		except Exception as e:
			# 提供更详细的错误信息
			error_msg = str(e)
			if 'authentication failed' in error_msg.lower() or 'auth' in error_msg.lower():
				raise ValueError(f'邮箱认证失败，请检查邮箱地址和授权码: {error_msg}')
			elif 'timeout' in error_msg.lower():
				raise ValueError(f'SMTP 服务器连接超时，请检查网络: {error_msg}')
			elif 'connection refused' in error_msg.lower():
				raise ValueError(f'SMTP 服务器拒绝连接，请检查服务器地址: {smtp_host}')
			else:
				raise ValueError(f'邮件发送失败: {error_msg}')

	def send_pushplus(self, title: str, content: str):
		if not self.pushplus_token:
			raise ValueError('PushPlus Token not configured')

		data = {'token': self.pushplus_token, 'title': title, 'content': content, 'template': 'html'}
		with httpx.Client(timeout=30.0) as client:
			client.post('http://www.pushplus.plus/send', json=data)

	def send_serverPush(self, title: str, content: str):
		if not self.server_push_key:
			raise ValueError('Server Push key not configured')

		data = {'title': title, 'desp': content}
		with httpx.Client(timeout=30.0) as client:
			client.post(f'https://sctapi.ftqq.com/{self.server_push_key}.send', json=data)

	def send_dingtalk(self, title: str, content: str):
		if not self.dingding_webhook:
			raise ValueError('DingTalk Webhook not configured')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.dingding_webhook, json=data)

	def send_feishu(self, title: str, content: str):
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

	def send_wecom(self, title: str, content: str):
		if not self.weixin_webhook:
			raise ValueError('WeChat Work Webhook not configured')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.weixin_webhook, json=data)

	def push_message(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
		notifications = [
			('Email', lambda: self.send_email(title, content, msg_type)),
			('PushPlus', lambda: self.send_pushplus(title, content)),
			('Server Push', lambda: self.send_serverPush(title, content)),
			('DingTalk', lambda: self.send_dingtalk(title, content)),
			('Feishu', lambda: self.send_feishu(title, content)),
			('WeChat Work', lambda: self.send_wecom(title, content)),
		]

		for name, func in notifications:
			try:
				func()
				print(f'[{name}]: Message push successful!')
			except Exception as e:
				print(f'[{name}]: Message push failed! Reason: {str(e)}')


notify = NotificationKit()
