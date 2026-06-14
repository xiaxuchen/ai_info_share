#!/usr/bin/env python3
"""
公告分析主控脚本
流程: 采集公告 → Qwen3-32B 提取 → Claude 深度分析 → 写入飞书

使用: python announcement_analyze.py [base_token] [table_id]
"""
import json, os, sys, io

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 导入其他模块
from announcement_fetch import fetch_stocks_from_bitable, fetch_announcements
from announcement_extract import extract_all
from announcement_to_bitable import write_analysis

# 硬编码的 BASE_TOKEN 和 TABLE_ID（和 write_comments_to_bitable.py 一致）
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE_ID = 'tbl2A9imBZgM7vLl'

# Claude 分析结果输出文件
ANALYSIS_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'announcement_analysis_output.json')


def save_extracted_for_claude(extracted_results):
    """保存 Qwen3-32B 提取结果，供 Claude 分析使用"""
    with open(ANALYSIS_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(extracted_results, f, ensure_ascii=False, indent=2)
    print(f'\nQwen提取结果已保存到: {ANALYSIS_OUTPUT}')
    print('请主 agent 读取此文件进行 Claude 深度分析。')


def load_claude_analysis():
    """加载 Claude 分析结果"""
    if os.path.exists(ANALYSIS_OUTPUT):
        with open(ANALYSIS_OUTPUT, encoding='utf-8') as f:
            data = json.load(f)
        return data
    return None


def generate_announcement_list(extracted_results):
    """生成公告列表摘要文本"""
    lines = []
    for stock_name, anns in extracted_results.items():
        lines.append(f'【{stock_name}】')
        for ann in anns:
            lines.append(f'  - {ann["date"]} {ann["title"][:60]}')
        lines.append('')
    return '\n'.join(lines)


def main():
    # 解析参数
    base_token = sys.argv[1] if len(sys.argv) > 1 else BASE_TOKEN
    table_id = sys.argv[2] if len(sys.argv) > 2 else STOCK_TABLE_ID

    print('=== 公告分析系统 ===')
    print(f'BASE_TOKEN: {base_token}')
    print(f'TABLE_ID: {table_id}')

    # Step 1: 从飞书读取股票列表
    print('\n--- Step 1: 读取股票列表 ---')
    stocks = fetch_stocks_from_bitable(base_token, table_id)
    print(f'读取到 {len(stocks)} 只股票')

    if not stocks:
        print('无股票数据，退出')
        return

    # Step 2: 采集新公告
    print('\n--- Step 2: 采集公告 ---')
    new_announcements = fetch_announcements(stocks)

    if not new_announcements:
        print('无新公告，退出')
        return

    total_anns = sum(len(v) for v in new_announcements.values())
    print(f'\n共发现 {total_anns} 条新公告')

    # Step 3: Qwen3-32B 提取
    print('\n--- Step 3: Qwen3-32B 信息提取 ---')
    extracted = extract_all(new_announcements)

    # Step 4: 保存提取结果，等待 Claude 分析
    print('\n--- Step 4: 保存提取结果 ---')

    # 构建 Claude 分析输入
    claude_input = {}
    for stock_name, anns in extracted.items():
        summaries = []
        for ann in anns:
            summaries.append({
                'title': ann['title'],
                'date': ann['date'],
                'summary': ann['summary_text']
            })
        claude_input[stock_name] = {
            'announcements': summaries,
            'claude_analysis': ''  # 待 Claude 填充
        }

    save_extracted_for_claude(claude_input)

    # Step 5: 提示 Claude 分析
    print('\n--- Step 5: Claude 深度分析 ---')
    print(f'请 Claude agent 读取 {ANALYSIS_OUTPUT}')
    print('对每只股票的公告进行深度分析，填充 claude_analysis 字段')
    print('完成后重新运行本脚本加 --write 参数')

    # 打印摘要供 Claude 直接使用
    print('\n' + '='*60)
    for stock_name, data in claude_input.items():
        print(f'\n### {stock_name}')
        for ann in data['announcements']:
            print(f"\n--- {ann['date']} {ann['title'][:60]}")
            print(ann['summary'])
    print('\n' + '='*60)


def write_mode():
    """--write 模式：加载 Claude 分析结果，写入飞书"""
    data = load_claude_analysis()
    if not data:
        print('未找到分析文件，请先运行主流程')
        return

    # 构建写入数据
    stock_analyses = {}
    missing_analysis = []
    for stock_name, info in data.items():
        announcement_list = '\n'.join([
            f"{ann['date']} {ann['title'][:80]}"
            for ann in info.get('announcements', [])
        ])
        analysis = info.get('claude_analysis', '').strip()
        if not analysis:
            missing_analysis.append(stock_name)
            print(f'  WARNING: {stock_name} 缺少 claude_analysis，仅写入公告列表')
            analysis = ''

        stock_analyses[stock_name] = {
            'announcement_list': announcement_list,
            'analysis': analysis
        }

    if missing_analysis:
        print(f'\n  {len(missing_analysis)} 只股票缺少Claude分析: {missing_analysis}')
        print('  已跳过分析字段写入，仅写入公告列表')

    print(f'\n准备写入 {len(stock_analyses)} 只股票的分析结果')
    write_analysis(stock_analyses)
    print('写入完成')


if __name__ == '__main__':
    if '--write' in sys.argv:
        write_mode()
    else:
        main()
