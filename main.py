#!/usr/bin/env python3
"""
Router平台自动签到脚本 - 重构版
支持 AnyRouter、AgentRouter 等多平台
支持 Cookies、GitHub、Linux.do 等多种认证方式
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional

from dotenv import load_dotenv

from checkin import CheckIn
from utils.config import AppConfig, load_accounts, validate_account
from utils.notify import notify

load_dotenv(override=True)

BALANCE_HASH_FILE = "balance_hash.txt"


def setup_logging():
    """配置日志系统"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"checkin_{datetime.now().strftime('%Y%m%d')}.log")

    # 配置logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)


def load_balance_hash() -> Optional[str]:
    """加载余额hash"""
    try:
        if os.path.exists(BALANCE_HASH_FILE):
            with open(BALANCE_HASH_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def save_balance_hash(balance_hash: str) -> None:
    """保存余额hash"""
    logger = logging.getLogger(__name__)
    try:
        with open(BALANCE_HASH_FILE, "w", encoding="utf-8") as f:
            f.write(balance_hash)
        logger.debug(f"余额hash已保存: {balance_hash}")
    except (IOError, OSError) as e:
        error_msg = f"Failed to save balance hash: {e}"
        print(f"⚠️ {error_msg}")
        logger.error(error_msg, exc_info=True)


def generate_balance_hash(balances: dict) -> str:
    """生成余额数据的hash"""
    simple_balances = {}
    if balances:
        for account_key, account_balances in balances.items():
            quota_list = []
            for _, balance_info in account_balances.items():
                quota_list.append(balance_info["quota"])
            simple_balances[account_key] = quota_list

    balance_json = json.dumps(simple_balances, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(balance_json.encode("utf-8")).hexdigest()[:16]


async def main():
    """主函数"""
    logger = setup_logging()

    print("=" * 80)
    print("🚀 Router平台多账号自动签到脚本 (重构版)")
    print(f"🕒 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    logger.info("="* 80)
    logger.info("程序启动")
    logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 加载应用配置
    app_config = AppConfig.load_from_env()
    print(f"\n⚙️ 已加载 {len(app_config.providers)} 个 Provider 配置")
    for name, provider in app_config.providers.items():
        print(f"   - {provider.name} ({name})")

    # 加载账号配置
    accounts = load_accounts()
    if not accounts:
        print("\n❌ 未找到任何账号配置，程序退出")
        print("💡 提示: 请配置 ANYROUTER_ACCOUNTS、AGENTROUTER_ACCOUNTS 或 ACCOUNTS 环境变量")
        return 1

    print(f"\n⚙️ 找到 {len(accounts)} 个账号配置")

    # 验证账号配置
    valid_accounts = []
    for i, account in enumerate(accounts):
        if validate_account(account, i):
            valid_accounts.append(account)
            auth_methods = ", ".join([auth.method for auth in account.auth_configs])
            print(f"   ✅ {account.name} ({account.provider}) - 认证方式: {auth_methods}")
        else:
            print(f"   ❌ {account.name} - 配置无效，跳过")

    if not valid_accounts:
        print("\n❌ 没有有效的账号配置，程序退出")
        return 1

    print(f"\n✅ 共 {len(valid_accounts)} 个账号通过验证\n")

    # 加载余额hash
    last_balance_hash = load_balance_hash()

    # 执行签到
    success_count = 0
    total_count = 0
    notification_content = []
    current_balances = {}
    need_notify = False

    for i, account in enumerate(valid_accounts):
        account_key = f"account_{i + 1}"

        if notification_content:
            notification_content.append("\n" + "-" * 60)

        try:
            # 获取 Provider 配置
            provider_config = app_config.get_provider(account.provider)
            if not provider_config:
                print(f"❌ {account.name}: Provider '{account.provider}' 配置未找到")
                need_notify = True
                notification_content.append(
                    f"[FAIL] {account.name}: Provider '{account.provider}' 配置未找到"
                )
                continue

            print(f"\n🌀 正在处理 {account.name} (使用 Provider '{account.provider}')")

            # 执行签到
            checkin = CheckIn(account, provider_config)
            results = await checkin.execute()

            total_count += len(results)

            # 处理多个认证方式的结果
            account_success = False
            successful_methods = []
            failed_methods = []
            this_account_balances = {}

            # 构建详细的结果报告
            account_result = f"📣 {account.name} 汇总:\n"

            for auth_method, success, user_info in results:
                status = "✅ SUCCESS" if success else "❌ FAILED"
                account_result += f"  {status} 使用 {auth_method} 认证\n"

                if success:
                    # 计入成功方法与账号成功标记
                    account_success = True
                    success_count += 1
                    successful_methods.append(auth_method)

                    # 展示用户信息（若可用）与余额信息
                    if user_info and user_info.get("success"):
                        account_result += f"    💰 {user_info['display']}\n"

                        # 记录余额信息
                        current_quota = user_info.get("quota")
                        current_used = user_info.get("used")
                        if current_quota is not None and current_used is not None:
                            this_account_balances[auth_method] = {
                                "quota": current_quota,
                                "used": current_used,
                            }

                        # 显示余额变化
                        if user_info.get("balance_change"):
                            change = user_info["balance_change"]
                            if change["recharge"] != 0 or change["used_change"] != 0:
                                change_parts = []
                                if change["recharge"] != 0:
                                    change_parts.append(f"充值{'+' if change['recharge'] > 0 else ''}${change['recharge']:.2f}")
                                if change["used_change"] != 0:
                                    change_parts.append(f"使用{'+' if change['used_change'] > 0 else ''}${change['used_change']:.2f}")
                                account_result += f"    📈 变动: {', '.join(change_parts)}\n"
                    elif user_info and user_info.get("message"):
                        # 签到成功但无法获取详细信息时给出简要信息
                        account_result += f"    ℹ️ {user_info['message']}\n"
                else:
                    # 仅在认证/签到失败时计入失败方法
                    failed_methods.append(auth_method)
                    error_msg = user_info.get("error", "Unknown error") if user_info else "Unknown error"
                    account_result += f"    🔺 错误: {str(error_msg)[:80]}\n"

            if account_success:
                current_balances[account_key] = this_account_balances

            # 如果所有认证方式都失败，需要通知
            if not account_success and results:
                need_notify = True
                print(f"🔔 {account.name} 所有认证方式都失败，将发送通知")

            # 如果有部分失败，也通知
            if failed_methods and successful_methods:
                need_notify = True
                print(f"🔔 {account.name} 有部分认证方式失败，将发送通知")

            # 添加统计信息
            success_count_methods = len(successful_methods)
            failed_count_methods = len(failed_methods)

            account_result += f"\n📊 统计: {success_count_methods}/{len(results)} 个认证方式成功"
            if failed_count_methods > 0:
                account_result += f" ({failed_count_methods} 个失败)"

            notification_content.append(account_result)

        except (ConnectionError, TimeoutError) as e:
            error_msg = f"{account.name} 网络连接异常: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)
            need_notify = True
            notification_content.append(f"❌ {account.name} 网络异常: {str(e)[:80]}")
        except ValueError as e:
            error_msg = f"{account.name} 配置或数据异常: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)
            need_notify = True
            notification_content.append(f"❌ {account.name} 配置异常: {str(e)[:80]}")
        except Exception as e:
            error_msg = f"{account.name} 处理异常: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)
            need_notify = True
            notification_content.append(f"❌ {account.name} 异常: {str(e)[:80]}")

    # 检查余额变化
    current_balance_hash = generate_balance_hash(current_balances) if current_balances else None
    print(f"\n\nℹ️ 当前余额 hash: {current_balance_hash}, 上次余额 hash: {last_balance_hash}")

    if current_balance_hash:
        if last_balance_hash is None:
            # 首次运行
            need_notify = True
            print("🔔 首次运行检测到，将发送通知")
        elif current_balance_hash != last_balance_hash:
            # 余额有变化
            need_notify = True
            print("🔔 余额变化检测到，将发送通知")
        else:
            print("ℹ️ 余额无变化")

    # 保存当前余额hash
    if current_balance_hash:
        save_balance_hash(current_balance_hash)

    # 发送通知
    if need_notify and notification_content:
        # 构建通知内容
        summary = [
            "-" * 60,
            "📢 签到结果统计:",
            f"🔵 成功: {success_count}/{total_count}",
            f"🔴 失败: {total_count - success_count}/{total_count}",
        ]

        if success_count == total_count:
            summary.append("✅ 所有账号签到成功!")
        elif success_count > 0:
            summary.append("⚠️ 部分账号签到成功")
        else:
            summary.append("❌ 所有账号签到失败")

        time_info = f"🕓 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        notify_content = "\n\n".join([time_info, "\n".join(notification_content), "\n".join(summary)])

        print("\n" + notify_content)
        notify.push_message("Router签到提醒", notify_content, msg_type="text")
        print("\n🔔 通知已发送")
    else:
        # 区分无余额数据和余额无变化两种情况
        if current_balance_hash:
            print("\nℹ️ 所有账号成功且余额无变化，跳过通知")
        else:
            print("\nℹ️ 所有账号成功（未获取到余额数据），跳过通知")

    print("\n" + "=" * 80)
    print(f"✅ 程序执行完成 - 成功: {success_count}/{total_count}")
    print("=" * 80)

    logger.info("=" * 80)
    logger.info(f"程序执行完成 - 成功: {success_count}/{total_count}")
    logger.info("=" * 80)

    # 设置退出码
    sys.exit(0 if success_count > 0 else 1)


def run_main():
    """运行主函数的包装函数"""
    logger = logging.getLogger(__name__)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        msg = "程序被用户中断"
        logger.warning(msg)
        sys.exit(1)
    except Exception as e:
        msg = f"程序执行出错: {e}"
        logger.error(msg, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_main()
