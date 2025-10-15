#!/usr/bin/env python3
"""
Router平台自动签到脚本主程序
支持 AnyRouter 和 AgentRouter 多账号签到
"""

import asyncio
import sys
from datetime import datetime

from checkin import RouterCheckin
from config import load_config
from notify import notify


async def main():
    """主函数"""
    print('='*60)
    print('Router平台自动签到脚本')
    print(f'执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*60)

    # 加载配置
    config = load_config()
    if not config:
        print('[ERROR] 配置加载失败，程序退出')
        sys.exit(1)

    # 统计信息
    anyrouter_accounts = config.get('anyrouter_accounts', [])
    agentrouter_accounts = config.get('agentrouter_accounts', [])
    total_accounts = len(anyrouter_accounts) + len(agentrouter_accounts)

    if total_accounts == 0:
        print('[WARN] 未配置任何账号，程序退出')
        sys.exit(0)

    print(f'\n[INFO] 找到 {len(anyrouter_accounts)} 个 AnyRouter 账号')
    print(f'[INFO] 找到 {len(agentrouter_accounts)} 个 AgentRouter 账号')
    print(f'[INFO] 总计 {total_accounts} 个账号需要处理\n')

    # 创建签到实例
    checkin = RouterCheckin()

    # 执行签到
    results = await checkin.run_all(anyrouter_accounts, agentrouter_accounts)

    # 统计结果
    success_count = sum(1 for r in results if r['success'])
    failed_count = len(results) - success_count

    print('\n' + '='*60)
    print('签到结果汇总')
    print('='*60)
    print(f'总计: {len(results)} 个账号')
    print(f'成功: {success_count} 个')
    print(f'失败: {failed_count} 个')

    for result in results:
        status = '✓' if result['success'] else '✗'
        print(f'{status} [{result["platform"]}] {result["name"]}: {result["message"]}')

    print('='*60)

    # 发送通知
    if failed_count > 0 or (success_count > 0 and checkin.has_balance_changed()):
        await notify_results(results, success_count, failed_count)
    else:
        print('\n[INFO] 全部成功且余额无变化，跳过通知')

    # 设置退出码
    sys.exit(0 if success_count > 0 else 1)


async def notify_results(results, success_count, failed_count):
    """发送通知"""
    print('\n[INFO] 准备发送通知...')

    # 构建通知内容
    title = 'Router平台签到提醒'

    content_lines = [
        f'⏰ 执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '',
        f'📊 统计结果:',
        f'✓ 成功: {success_count} 个',
        f'✗ 失败: {failed_count} 个',
        '',
        '📝 详细结果:'
    ]

    for result in results:
        icon = '✅' if result['success'] else '❌'
        content_lines.append(f'{icon} [{result["platform"]}] {result["name"]}')
        content_lines.append(f'   {result["message"]}')

        # 添加余额信息
        if result.get('balance'):
            balance = result['balance']
            content_lines.append(f'   💰 余额: ${balance["quota"]}, 已用: ${balance["used"]}')

    content = '\n'.join(content_lines)

    # 发送通知
    notify.push_message(title, content, msg_type='text')
    print('[INFO] 通知发送完成')


def run_main():
    """运行主函数的包装"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n[WARN] 程序被用户中断')
        sys.exit(1)
    except Exception as e:
        print(f'\n[ERROR] 程序执行出错: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    run_main()
