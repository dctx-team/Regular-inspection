"""
配置管理模块
"""

import json
import os
from typing import Dict, List, Optional


def load_config() -> Optional[Dict]:
    """加载所有配置"""
    config = {}

    # 加载 AnyRouter 账号
    anyrouter_accounts = load_accounts('ANYROUTER_ACCOUNTS')
    if anyrouter_accounts:
        config['anyrouter_accounts'] = anyrouter_accounts

    # 加载 AgentRouter 账号
    agentrouter_accounts = load_accounts('AGENTROUTER_ACCOUNTS')
    if agentrouter_accounts:
        config['agentrouter_accounts'] = agentrouter_accounts

    return config


def load_accounts(env_var_name: str) -> Optional[List[Dict]]:
    """从环境变量加载账号配置"""
    accounts_str = os.getenv(env_var_name)
    if not accounts_str:
        return None

    try:
        accounts_data = json.loads(accounts_str)

        # 检查格式
        if not isinstance(accounts_data, list):
            print(f'[ERROR] {env_var_name} 必须是数组格式 []')
            return None

        # 验证每个账号
        for i, account in enumerate(accounts_data):
            if not isinstance(account, dict):
                print(f'[ERROR] {env_var_name} 账号 {i+1} 格式错误')
                return None

            # 检查登录方式：要么提供 cookies+api_user，要么提供 email+password
            has_cookies = 'cookies' in account and 'api_user' in account
            has_password = 'email' in account and 'password' in account

            if not has_cookies and not has_password:
                print(f'[ERROR] {env_var_name} 账号 {i+1} 必须提供以下之一：')
                print(f'       方式1: cookies + api_user (传统方式)')
                print(f'       方式2: email + password (账号密码登录，推荐用于 AgentRouter)')
                return None

            # name 字段可选，但不能为空
            if 'name' in account and not account['name']:
                print(f'[ERROR] {env_var_name} 账号 {i+1} name 字段不能为空')
                return None

            # 如果没有 name，自动生成
            if 'name' not in account:
                account['name'] = f'Account {i+1}'

        print(f'[INFO] {env_var_name} 加载成功: {len(accounts_data)} 个账号')
        return accounts_data

    except json.JSONDecodeError as e:
        print(f'[ERROR] {env_var_name} JSON 格式错误: {e}')
        return None
    except Exception as e:
        print(f'[ERROR] {env_var_name} 加载失败: {e}')
        return None


def parse_cookies(cookies_data) -> Dict[str, str]:
    """解析 cookies 数据"""
    if isinstance(cookies_data, dict):
        return cookies_data

    if isinstance(cookies_data, str):
        cookies_dict = {}
        for cookie in cookies_data.split(';'):
            if '=' in cookie:
                key, value = cookie.strip().split('=', 1)
                cookies_dict[key] = value
        return cookies_dict

    return {}


def get_account_display_name(account: Dict, index: int) -> str:
    """获取账号显示名称"""
    return account.get('name', f'Account {index + 1}')
