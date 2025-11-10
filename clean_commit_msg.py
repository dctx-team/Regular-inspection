#!/usr/bin/env python3
"""清理提交信息中的 Claude 引用"""
import sys

# 读取提交信息
msg = sys.stdin.read()

# 移除 Claude 相关行
lines = msg.split('\n')
cleaned_lines = []
skip_next_empty = False

for line in lines:
    # 跳过 Claude 标识行
    if '🤖 Generated with' in line or 'Claude Code' in line:
        skip_next_empty = True
        continue
    # 跳过 Co-Authored-By: Claude 行
    if 'Co-Authored-By: Claude' in line:
        continue
    # 跳过 Claude 标识后的第一个空行
    if skip_next_empty and line.strip() == '':
        skip_next_empty = False
        continue

    cleaned_lines.append(line)

# 移除末尾多余的空行
while cleaned_lines and cleaned_lines[-1].strip() == '':
    cleaned_lines.pop()

# 输出清理后的信息
print('\n'.join(cleaned_lines))
