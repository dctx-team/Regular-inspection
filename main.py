#!/usr/bin/env python3
"""
Router平台自动签到脚本主程序
支持 AnyRouter 和 AgentRouter 多账号签到
"""

import asyncio
import sys
from datetime import datetime
import pytz

from checkin import RouterCheckin
from config import load_config
from notify import notify

# 设置北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')


def get_beijing_time():
    """获取北京时间"""
    return datetime.now(BEIJING_TZ)


async def main():
    """主函数"""
    print('='*60)
    print('Router平台自动签到脚本')
    print(f'执行时间: {get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")} (北京时间)')
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
    print()

    # 统计余额信息
    total_quota = 0
    total_used = 0
    platform_stats = {'AnyRouter': {'count': 0, 'quota': 0, 'used': 0},
                      'AgentRouter': {'count': 0, 'quota': 0, 'used': 0}}

    for result in results:
        status = '✓' if result['success'] else '✗'
        print(f'{status} [{result["platform"]}] {result["name"]}: {result["message"]}')

        # 显示余额信息
        if result.get('balance'):
            balance = result['balance']
            print(f'  💰 余额: ${balance["quota"]}, 已用: ${balance["used"]}')

            # 累计统计
            total_quota += balance["quota"]
            total_used += balance["used"]
            platform_stats[result["platform"]]['count'] += 1
            platform_stats[result["platform"]]['quota'] += balance["quota"]
            platform_stats[result["platform"]]['used'] += balance["used"]

    # 显示汇总统计
    print()
    print('-' * 60)
    print('💰 余额汇总统计')
    print('-' * 60)

    for platform, stats in platform_stats.items():
        if stats['count'] > 0:
            print(f'{platform}: {stats["count"]} 个账号')
            print(f'  总余额: ${stats["quota"]:.2f}')
            print(f'  总已用: ${stats["used"]:.2f}')

    if total_quota > 0:
        print()
        print(f'📊 全平台汇总:')
        print(f'  总余额: ${total_quota:.2f}')
        print(f'  总已用: ${total_used:.2f}')

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

    # 统计余额信息和变动
    total_quota = 0
    total_used = 0
    total_recharge = 0
    total_used_change = 0
    total_quota_change = 0

    platform_stats = {
        'AnyRouter': {'count': 0, 'success': 0, 'failed': 0, 'quota': 0, 'used': 0,
                      'recharge': 0, 'used_change': 0, 'quota_change': 0},
        'AgentRouter': {'count': 0, 'success': 0, 'failed': 0, 'quota': 0, 'used': 0,
                        'recharge': 0, 'used_change': 0, 'quota_change': 0}
    }

    for result in results:
        platform = result['platform']
        platform_stats[platform]['count'] += 1

        if result['success']:
            platform_stats[platform]['success'] += 1
        else:
            platform_stats[platform]['failed'] += 1

        # 累计余额
        if result.get('balance'):
            balance = result['balance']
            total_quota += balance["quota"]
            total_used += balance["used"]
            platform_stats[platform]['quota'] += balance["quota"]
            platform_stats[platform]['used'] += balance["used"]

        # 累计变动
        if result.get('balance_change'):
            change = result['balance_change']
            total_recharge += change['recharge']
            total_used_change += change['used_change']
            total_quota_change += change['quota_change']
            platform_stats[platform]['recharge'] += change['recharge']
            platform_stats[platform]['used_change'] += change['used_change']
            platform_stats[platform]['quota_change'] += change['quota_change']

    # 构建通知内容
    title = 'Router平台签到提醒'

    content_lines = [
        f'⏰ 执行时间: {get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")} (北京时间)',
        '',
        f'📊 统计结果: ✓ 成功: {success_count} 个 ✗ 失败: {failed_count} 个',
    ]

    # 添加详细结果
    content_lines.append('')
    content_lines.append('📝 详细结果:')

    for result in results:
        icon = '✅' if result['success'] else '❌'
        status_line = f'{icon} [{result["platform"]}] {result["name"]} {result["message"]}'
        content_lines.append(status_line)

        # 添加余额信息
        if result.get('balance'):
            balance = result['balance']
            balance_line = f'   💰 余额: ${balance["quota"]}, 已用: ${balance["used"]}'

            # 如果签到失败但有余额数据，标注为"未更新"
            if not result['success'] and result.get('balance'):
                balance_line += ' (未更新)'

            content_lines.append(balance_line)

        # 添加变动信息（只有签到成功才显示）
        if result['success'] and result.get('balance_change'):
            change = result['balance_change']
            change_items = []
            if change['recharge'] != 0:
                if change['recharge'] > 0:
                    change_items.append(f'增加+${change["recharge"]:.2f}')
                else:
                    change_items.append(f'增加${change["recharge"]:.2f}')
            if change['used_change'] != 0:
                if change['used_change'] > 0:
                    change_items.append(f'使用+${change["used_change"]:.2f}')
                else:
                    change_items.append(f'使用${change["used_change"]:.2f}')
            if change['quota_change'] != 0:
                if change['quota_change'] > 0:
                    change_items.append(f'可用+${change["quota_change"]:.2f}')
                else:
                    change_items.append(f'可用${change["quota_change"]:.2f}')

            if change_items:
                content_lines.append(f'   📈 变动: {", ".join(change_items)}')

    # 添加平台汇总
    for platform, stats in platform_stats.items():
        if stats['count'] > 0:
            content_lines.append('')
            content_lines.append(f'─── {platform} 平台汇总 ───')
            content_lines.append(f'✓ 成功: {stats["success"]} 个 | ✗ 失败: {stats["failed"]} 个')
            if stats['quota'] > 0 or stats['used'] > 0:
                content_lines.append(f'💰 总余额: ${stats["quota"]:.2f}, 总已用: ${stats["used"]:.2f}')

            # 添加平台变动汇总
            if stats['recharge'] != 0 or stats['used_change'] != 0 or stats['quota_change'] != 0:
                change_parts = []
                if stats['recharge'] != 0:
                    change_parts.append(f'增加{"+" if stats["recharge"] > 0 else ""}${stats["recharge"]:.2f}')
                if stats['used_change'] != 0:
                    change_parts.append(f'使用{"+" if stats["used_change"] > 0 else ""}${stats["used_change"]:.2f}')
                if stats['quota_change'] != 0:
                    change_parts.append(f'可用{"+" if stats["quota_change"] > 0 else ""}${stats["quota_change"]:.2f}')
                content_lines.append(f'📈 本期变动: {", ".join(change_parts)}')

    # 全平台汇总
    if total_quota > 0 or total_used > 0:
        content_lines.append('')
        content_lines.append('━━━ 全平台汇总 ━━━')
        content_lines.append(f'💰 总余额: ${total_quota:.2f}')
        content_lines.append(f'📊 总已用: ${total_used:.2f}')

        # 添加总变动
        if total_recharge != 0 or total_used_change != 0 or total_quota_change != 0:
            change_parts = []
            if total_recharge != 0:
                change_parts.append(f'增加{"+" if total_recharge > 0 else ""}${total_recharge:.2f}')
            if total_used_change != 0:
                change_parts.append(f'使用{"+" if total_used_change > 0 else ""}${total_used_change:.2f}')
            if total_quota_change != 0:
                change_parts.append(f'可用{"+" if total_quota_change > 0 else ""}${total_quota_change:.2f}')
            content_lines.append(f'📈 本期变动: {", ".join(change_parts)}')

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
