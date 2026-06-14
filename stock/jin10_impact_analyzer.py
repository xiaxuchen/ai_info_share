#!/usr/bin/env python3
"""
金十快讯 → 板块 → 标签 → 个股 影响分析
=============================================
流程:
1. 从金十快讯表获取待处理快讯（状态=待处理）
2. 从板块表获取全量板块及其逻辑/预期
3. Qwen 分析影响哪些板块 → 获取对应板块的标签信息
4. Qwen 分析涉及哪些标签 → 通过标签获取相关个股
5. Qwen 分析消息面对个股的影响（投资逻辑+公告+K线走势）
6. 写入股票表"消息面影响"字段
7. 重要性≥中的快讯通过飞书通知
"""
import json, ssl, socket, os, sys, io
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOKEN_FILE = os.path.expanduser("~/.feishu-cli/token.json")
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE = 'tbl2A9imBZgM7vLl'
SECTOR_TABLE = 'tblYQ1mU8FfuqIt2'
TAG_TABLE = 'tblyaMaXvJXLODzs'
FLASH_TABLE = 'tblBxYPy2neYvFtq'
WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/7fc8880c-af27-4242-a098-99df6cc26159'
API_KEY = 'sk-lsnhfgotvsmsndxsonigqhvpdmbtajviumyobxonrbigsyhh'
API_HOST = 'api.siliconflow.cn'

# ======================== 工具函数 ========================

def get_token():
    with open(TOKEN_FILE, encoding='utf-8') as f:
        return json.load(f)['access_token']


def https_req(method, host, path, body=None):
    """纯 socket HTTP 请求"""
    token = get_token()
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=60)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = '{} {} HTTP/1.1\r\nHost: {}\r\n'.format(method, path, host)
    if token:
        hdrs += 'Authorization: Bearer {}\r\n'.format(token)
    hdrs += 'Content-Type: application/json\r\n'
    if body:
        hdrs += 'Content-Length: {}\r\n'.format(len(body))
    hdrs += 'Connection: close\r\n\r\n'
    ssock.sendall(hdrs.encode() + (body or b''))
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c:
            break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he + 4:]
    hstr = resp[:he].decode('iso-8859-1').lower()
    if 'chunked' in hstr:
        p, bd = 0, b''
        while p < len(raw):
            e = raw.find(b'\r\n', p)
            if e < 0:
                break
            sz = int(raw[p:e], 16)
            if sz == 0:
                break
            bd += raw[e + 2:e + 2 + sz]
            p = e + 2 + sz + 2
        raw = bd
    return json.loads(raw.decode())


def qwen_chat(messages, max_tokens=2000, temperature=0.3):
    """调用 SiliconFlow Qwen3-32B"""
    body = json.dumps({
        'model': 'Qwen/Qwen3-32B',
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
    })
    ctx = ssl.create_default_context()
    sock = socket.create_connection((API_HOST, 443), timeout=120)
    ssock = ctx.wrap_socket(sock, server_hostname=API_HOST)
    hdrs = 'POST /v1/chat/completions HTTP/1.1\r\nHost: {}\r\n'.format(API_HOST)
    hdrs += 'Authorization: Bearer {}\r\nContent-Type: application/json\r\n'.format(API_KEY)
    hdrs += 'Content-Length: {}\r\nConnection: close\r\n\r\n'.format(len(body))
    ssock.sendall(hdrs.encode() + body.encode())
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c:
            break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he + 4:]
    return json.loads(raw.decode()).get('choices', [{}])[0].get('message', {}).get('content', '')


def parse_json(text):
    """解析 Qwen 返回的 JSON（处理 markdown code block）"""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        if text.startswith('json'):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return None


def post_webhook(card):
    """发送飞书机器人消息"""
    host = 'open.feishu.cn'
    body = json.dumps(card, ensure_ascii=False).encode()
    path = WEBHOOK.split(host, 1)[1]
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = 'POST {} HTTP/1.1\r\nHost: {}\r\n'.format(path, host)
    hdrs += 'Content-Type: application/json\r\n'
    hdrs += 'Content-Length: {}\r\nConnection: close\r\n\r\n'.format(len(body))
    ssock.sendall(hdrs.encode() + body)
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c:
            break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he + 4:]
    return json.loads(raw.decode())


# ======================== Bitable 操作 (v1 API) ========================

def bitable_list(table_id, page_size=100):
    """列出记录"""
    data = https_req('GET', 'open.feishu.cn',
        '/open-apis/bitable/v1/apps/{}/tables/{}/records?page_size={}'.format(
            BASE_TOKEN, table_id, page_size))
    return data.get('data', {}).get('items', [])


def bitable_update(table_id, record_id, fields):
    """更新记录"""
    body = json.dumps({'fields': fields}, ensure_ascii=False).encode()
    data = https_req('PUT', 'open.feishu.cn',
        '/open-apis/bitable/v1/apps/{}/tables/{}/records/{}'.format(
            BASE_TOKEN, table_id, record_id), body)
    return data.get('code') == 0


# ======================== 字段管理 (v3 API) ========================

def v3_req(method, path, body=None):
    """飞书 v3 API 请求"""
    token = get_token()
    ctx = ssl.create_default_context()
    sock = socket.create_connection(('open.feishu.cn', 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname='open.feishu.cn')
    hdrs = '{} {} HTTP/1.1\r\nHost: open.feishu.cn\r\n'.format(method, path)
    hdrs += 'Authorization: Bearer {}\r\n'.format(token)
    hdrs += 'Content-Type: application/json\r\n'
    if body:
        hdrs += 'Content-Length: {}\r\n'.format(len(body))
    hdrs += 'Connection: close\r\n\r\n'
    ssock.sendall(hdrs.encode() + (body or b''))
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c:
            break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he + 4:]
    hstr = resp[:he].decode('iso-8859-1').lower()
    if 'chunked' in hstr:
        p, bd = 0, b''
        while p < len(raw):
            e = raw.find(b'\r\n', p)
            if e < 0:
                break
            sz = int(raw[p:e], 16)
            if sz == 0:
                break
            bd += raw[e + 2:e + 2 + sz]
            p = e + 2 + sz + 2
        raw = bd
    return json.loads(raw.decode())


def get_existing_fields():
    """获取股票表已有字段"""
    data = v3_req('GET', '/open-apis/base/v3/bases/{}/tables/{}/fields'.format(BASE_TOKEN, STOCK_TABLE))
    fields = {}
    for f in data.get('data', {}).get('fields', []):
        fields[f['name']] = f['id']
    return fields


def ensure_field(field_name):
    """确保字段存在，不存在则创建"""
    existing = get_existing_fields()
    if field_name in existing:
        return existing[field_name]

    body = json.dumps({'field_name': field_name, 'type': 'text'}).encode()
    data = v3_req('POST', '/open-apis/base/v3/bases/{}/tables/{}/fields'.format(BASE_TOKEN, STOCK_TABLE), body)
    if data.get('code') == 0:
        fid = data['data']['id']
        print('  [OK] 创建字段 "{}" -> {}'.format(field_name, fid))
        return fid
    print('  [ERROR] 创建字段 "{}" 失败: {}'.format(field_name, data.get('msg', data)))
    return None


# ======================== 数据加载 ========================

def get_pending_flashes():
    """获取状态=待处理的快讯"""
    items = bitable_list(FLASH_TABLE)
    pending = []
    for item in items:
        fields = item.get('fields', {})
        if fields.get('状态') == '待处理':
            pending.append({
                'record_id': item.get('record_id', ''),
                'content': fields.get('快讯内容', ''),
                'summary': fields.get('分析摘要', ''),
                'importance': fields.get('重要性', '低'),
                'sentiment': fields.get('情绪', '中性'),
                'flash_id': fields.get('快讯ID', ''),
                'sectors_text': fields.get('相关板块', ''),
                'tags_text': fields.get('分类标签', ''),
            })
    return pending


def get_all_sectors():
    """获取全量板块及核心逻辑"""
    items = bitable_list(SECTOR_TABLE)
    sectors = []
    for item in items:
        f = item.get('fields', {})
        name = f.get('板块名字', '')
        if not name:
            continue
        sectors.append({
            'record_id': item.get('record_id', ''),
            'name': str(name).strip(),
            'logic': str(f.get('板块逻辑', '') or '').strip(),
            'expectation': str(f.get('后续预期', '') or '').strip(),
            'core_expectation': str(f.get('核心预期', '') or '').strip(),
            'tags': str(f.get('标签', '') or '').strip(),
            'issues': str(f.get('问题', '') or '').strip(),
            'burst_period': str(f.get('爆发期', '') or '').strip(),
            'parent': str(f.get('父板块', '') or '').strip(),
        })
    return sectors


def get_all_tags():
    """获取全量标签"""
    items = bitable_list(TAG_TABLE)
    tags = []
    for item in items:
        f = item.get('fields', {})
        tn = f.get('标签', '')
        if not tn:
            continue
        tags.append({
            'record_id': item.get('record_id', ''),
            'name': str(tn).strip(),
            'description': str(f.get('描述', '') or '').strip(),
            'sector': str(f.get('所属板块', '') or '').strip(),
            'stocks': str(f.get('股票', '') or '').strip(),
        })
    return tags


def get_all_stocks():
    """获取全量股票及完整分析字段"""
    items = bitable_list(STOCK_TABLE)
    stocks = []
    for item in items:
        f = item.get('fields', {})
        name = f.get('股票名称', '')
        if not name:
            continue
        stocks.append({
            'record_id': item.get('record_id', ''),
            'name': str(name).strip(),
            'code': str(f.get('股票代码', '') or '').strip(),
            'sector': str(f.get('所属板块', '') or '').strip(),
            'tags': str(f.get('标签', '') or '').strip(),
            'concepts': str(f.get('所属概念', '') or '').strip(),
            'leader': str(f.get('板块龙头', '') or '').strip(),
            'investment_logic': str(f.get('投资逻辑', '') or '').strip(),
            'business_model': str(f.get('业务模式', '') or '').strip(),
            'financial_status': str(f.get('财务现状', '') or '').strip(),
            'barrier': str(f.get('竞争壁垒', '') or '').strip(),
            'risk': str(f.get('风险点', '') or '').strip(),
            'good_factors': str(f.get('可能的利好', '') or '').strip(),
            'bad_factors': str(f.get('可能的利空', '') or '').strip(),
            'latest_announcements': str(f.get('最新公告', '') or '').strip(),
            'announcement_analysis': str(f.get('公告分析', '') or '').strip(),
            'kline_analysis': str(f.get('K线分析', '') or '').strip(),
            'weekly_analysis': str(f.get('周K分析', '') or '').strip(),
            'kline_pattern': str(f.get('当前k线', '') or '').strip(),
            'ai_strategy': str(f.get('AI策略', '') or '').strip(),
            'current_price': str(f.get('现价', '') or '').strip(),
            'existing_impact': str(f.get('消息面影响', '') or '').strip(),
        })
    return stocks


# ======================== Qwen 分析 ========================

def analyze_sectors_and_tags(flash_content, sectors, tags):
    """Qwen 分析快讯影响哪些板块和标签

    一次性完成板块+标签分析，减少 API 调用次数。
    """
    sectors_text = '\n'.join([
        '- {} | 逻辑: {} | 核心预期: {}'.format(
            s['name'],
            s['logic'][:80] if s['logic'] else '无',
            s['core_expectation'][:80] if s['core_expectation'] else '无'
        )
        for s in sectors
    ])

    tags_text = '\n'.join([
        '- {} | 描述: {} | 所属板块: {}'.format(
            t['name'],
            t['description'][:60] if t['description'] else '无',
            t['sector']
        )
        for t in tags
    ])

    prompt = """你是一个A股投资分析助手。根据以下快讯内容，分析它可能影响哪些板块和标签。

## 快讯内容
{}

## 已知板块列表（名称 | 逻辑 | 核心预期）
{}

## 已知标签列表（名称 | 描述 | 所属板块）
{}

## 要求
返回纯JSON（不要markdown代码块）：
{{
  "related": true,
  "summary": "一句话总结快讯核心信息（50字以内）",
  "affected_sectors": [
    {{"name": "板块名（必须严格从已知板块中选择）", "reason": "影响原因（30字以内）"}}
  ],
  "relevant_tags": [
    {{"name": "标签名（必须严格从已知标签中选择）", "reason": "相关原因（30字以内）"}}
  ],
  "sentiment": "利好/利空/中性",
  "importance": "高/中/低"
}}

注意：
- 板块和标签名称必须严格从已知列表中匹配，一字不差，不要编造
- 如果快讯与A股/已知板块无关，设置 related=false，留空数组
- importance: 影响大盘/重要政策→高，影响行业→中，仅信息类→低""".format(
        flash_content[:3000], sectors_text[:4000], tags_text[:4000]
    )

    result = qwen_chat([{'role': 'user', 'content': prompt}], max_tokens=1500, temperature=0.3)
    parsed = parse_json(result)

    if not parsed:
        print('    [WARN] 板块/标签JSON解析失败，原文: {}'.format(result[:200]))
        return {
            'related': False, 'summary': result[:200],
            'affected_sectors': [], 'relevant_tags': [],
            'sentiment': '中性', 'importance': '低'
        }
    return parsed


def analyze_stock_impact(flash_content, flash_summary, flash_sentiment, stock):
    """Qwen 分析快讯对个股的具体影响"""
    info_items = []
    def add(label, val):
        if val:
            info_items.append('{}: {}'.format(label, val))

    add('股票名称', stock['name'])
    add('股票代码', stock['code'])
    add('所属板块', stock['sector'])
    add('标签', stock['tags'])
    add('概念', stock['concepts'])
    add('板块地位', stock['leader'])
    add('投资逻辑', stock['investment_logic'])
    add('业务模式', stock['business_model'])
    add('财务现状', stock['financial_status'])
    add('竞争壁垒', stock['barrier'])
    add('风险点', stock['risk'])
    add('可能的利好', stock['good_factors'])
    add('可能的利空', stock['bad_factors'])
    add('最新公告', stock['latest_announcements'][:300])
    add('K线分析', stock['kline_analysis'])
    add('K线形态', stock['kline_pattern'])
    add('AI策略', stock['ai_strategy'])
    add('现价', stock['current_price'])

    prompt = """你是A股投资分析助手。分析快讯消息面对以下个股的具体影响。

## 快讯
{}

## 快讯摘要: {}
## 快讯情绪: {}

## 个股详情
{}

## 要求
基于该股的投资逻辑、业务模式、近期公告、K线走势和风险点，
分析消息对它的短期（1-5交易日）影响。返回纯JSON：
{{
  "impact": "利好/利空/中性",
  "analysis": "详细分析（150-300字）：结合该股具体情况说明消息面如何影响它",
  "confidence": "高/中/低",
  "key_reason": "一句话核心影响逻辑（30字以内）"
}}

注意：
- 如个股与消息关联度低，confidence标"低"，analysis说明关联有限
- analysis要具体到这只股票，不要泛泛而谈
- 考虑近期公告和K线走势反映的市场状态""".format(
        flash_content[:1500], flash_summary, flash_sentiment,
        '\n'.join(info_items)[:4000]
    )

    result = qwen_chat([{'role': 'user', 'content': prompt}], max_tokens=1000, temperature=0.3)
    parsed = parse_json(result)

    if not parsed:
        print('      [WARN] 个股影响JSON解析失败')
        return {
            'impact': '中性', 'analysis': result[:300],
            'confidence': '低', 'key_reason': '分析异常'
        }
    return parsed


# ======================== 飞书通知 ========================

def send_impact_notification(flash, sector_result, stock_impacts):
    """重要快讯发送飞书卡片通知"""
    sentiment = sector_result.get('sentiment', '中性')
    importance = sector_result.get('importance', '低')
    summary = sector_result.get('summary', flash['content'][:100])

    emotion_map = {'利好': '🟢', '利空': '🔴', '中性': '🟡'}
    importance_map = {'高': '🔥', '中': '📌', '低': '📎'}

    md_lines = ['**快讯原文**\n{}\n'.format(flash['content'][:200])]
    if summary:
        md_lines.append('**摘要**: {}\n'.format(summary))

    sectors = sector_result.get('affected_sectors', [])
    if sectors:
        md_lines.append('**影响板块**:')
        for s in sectors:
            md_lines.append('- {}: {}'.format(s['name'], s.get('reason', '')))
        md_lines.append('')

    tags = sector_result.get('relevant_tags', [])
    if tags:
        md_lines.append('**涉及标签**: {}'.format('、'.join(t['name'] for t in tags)))
        md_lines.append('')

    if stock_impacts:
        md_lines.append('**个股影响**:')
        for si in stock_impacts:
            em = emotion_map.get(si.get('impact', '中性'), '🟡')
            md_lines.append('- {} **{}**({}): {}'.format(
                em, si['name'], si.get('impact', '中性'),
                si.get('key_reason', si.get('analysis', '')[:60])
            ))
        md_lines.append('')

    md_lines.append('{} **{}** | {} **{}**'.format(
        emotion_map.get(sentiment, ''), sentiment,
        importance_map.get(importance, ''), importance
    ))

    card = {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': '金十消息面影响分析'},
                'template': 'red' if sentiment == '利空' else ('blue' if sentiment == '利好' else 'grey'),
            },
            'elements': [
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': '\n'.join(md_lines)}},
            ],
        },
    }

    try:
        result = post_webhook(card)
        return result.get('code') == 0
    except Exception as e:
        print('    飞书通知异常: {}'.format(e))
        return False


# ======================== 核心逻辑 ========================

def find_stocks_by_tags_and_sectors(all_stocks, tag_names, sector_names):
    """根据标签名和板块名匹配个股"""
    matched = []
    seen = set()
    for stock in all_stocks:
        if stock['name'] in seen:
            continue
        stock_tags = [t.strip() for t in stock['tags'].replace('，', ',').split(',') if t.strip()]
        stock_sectors = [s.strip() for s in stock['sector'].replace('，', ',').split(',') if s.strip()]

        reasons = []
        for tn in tag_names:
            if tn in stock_tags:
                reasons.append('标签:{}'.format(tn))
        for sn in sector_names:
            if sn in stock_sectors:
                reasons.append('板块:{}'.format(sn))

        if reasons:
            sc = stock.copy()
            sc['match_reason'] = '、'.join(reasons)
            matched.append(sc)
            seen.add(stock['name'])
    return matched


def main():
    print('=' * 60)
    print('  金十快讯 → 板块 → 标签 → 个股 影响分析')
    print('  {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    print('=' * 60)

    # 0. 确保字段存在
    print('\n[0] 检查字段...')
    impact_fid = ensure_field('消息面影响')
    if not impact_fid:
        print('  [FATAL] 无法创建"消息面影响"字段，退出')
        return

    # 1. 获取待处理快讯
    print('\n[1/5] 获取待处理快讯...')
    pending = get_pending_flashes()
    print('  待处理: {} 条'.format(len(pending)))
    if not pending:
        print('  无待处理快讯，退出')
        return
    for i, f in enumerate(pending):
        print('  {}. [{}] {}'.format(i + 1, f.get('importance', '?'), f['content'][:80]))

    # 2. 加载板块和标签（一次性）
    print('\n[2/5] 加载板块和标签...')
    sectors = get_all_sectors()
    tags = get_all_tags()
    stocks = get_all_stocks()
    print('  板块: {} | 标签: {} | 股票: {}'.format(len(sectors), len(tags), len(stocks)))

    # 3. 逐条分析
    print('\n[3/5] 逐条分析...')
    print('-' * 60)

    flash_updates = []
    stock_writes = []

    for idx, flash in enumerate(pending):
        print('\n>>> 快讯 {}/{}: {}'.format(idx + 1, len(pending), flash['content'][:100]))

        # 3a. 分析板块+标签
        print('  [Qwen] 分析板块+标签...')
        result = analyze_sectors_and_tags(flash['content'], sectors, tags)

        if not result.get('related', False):
            print('  => 与A股无关，标记为垃圾消息')
            flash_updates.append((flash['record_id'], '垃圾消息'))
            continue

        affected_sectors = result.get('affected_sectors', [])
        relevant_tags = result.get('relevant_tags', [])
        sentiment = result.get('sentiment', '中性')
        importance = result.get('importance', '低')
        summary = result.get('summary', '')

        print('  摘要: {}'.format(summary))
        print('  情绪: {} | 重要性: {}'.format(sentiment, importance))
        print('  板块: {}'.format([s['name'] for s in affected_sectors]))
        print('  标签: {}'.format([t['name'] for t in relevant_tags]))

        # 3b. 匹配个股
        sector_names = [s['name'] for s in affected_sectors]
        tag_names = [t['name'] for t in relevant_tags]
        affected = find_stocks_by_tags_and_sectors(stocks, tag_names, sector_names)
        print('  匹配个股({}): {}'.format(len(affected), [s['name'] for s in affected]))

        if not affected:
            flash_updates.append((flash['record_id'], '已分析'))
            continue

        # 3c. 逐股分析影响
        impact_results = []
        for stock in affected:
            print('  [Qwen] 分析 {}...'.format(stock['name']))
            imp = analyze_stock_impact(
                flash['content'], summary, sentiment, stock
            )
            imp['name'] = stock['name']
            imp['code'] = stock['code']
            imp['record_id'] = stock['record_id']
            imp['match_reason'] = stock.get('match_reason', '')
            impact_results.append(imp)
            print('    -> {} {} | 置信度: {} | {}'.format(
                imp.get('impact', '?'), stock['name'],
                imp.get('confidence', '?'), imp.get('key_reason', '')[:60]
            ))

        # 记录快讯状态
        flash_updates.append((flash['record_id'], '已分析'))

        # 3d. 准备写入数据
        now_str = datetime.now().strftime('%m-%d %H:%M')
        semoji = {'利好': '▲', '利空': '▼', '中性': '◆'}

        for imp in impact_results:
            if imp.get('impact') == '中性' and imp.get('confidence') == '低':
                continue

            line = '[{}] {} {} | 消息:{} | {}'.format(
                now_str,
                semoji.get(imp.get('impact', '中性'), '◆'),
                imp.get('impact', '中性'),
                flash['content'][:80],
                imp.get('analysis', '')
            )
            # 找股票记录获取现有影响
            stock = next((s for s in stocks if s['name'] == imp['name']), None)
            existing = stock['existing_impact'] if stock else ''
            combined = line + '\n\n' + existing if existing else line

            stock_writes.append({
                'record_id': imp['record_id'],
                'name': imp['name'],
                'text': combined[:8000],
                'impact': imp.get('impact', '?'),
                'key_reason': imp.get('key_reason', ''),
            })

        # 3e. 重要快讯发飞书通知
        if importance in ('高', '中'):
            print('  => 发送飞书通知...')
            ok = send_impact_notification(flash, result, impact_results)
            print('    通知: {}'.format('OK' if ok else 'FAIL'))

    # 4. 更新快讯状态
    print('\n[4/5] 更新快讯状态...')
    for rid, status in flash_updates:
        ok = bitable_update(FLASH_TABLE, rid, {'状态': status})
        print('  {} -> {} {}'.format(rid[:10], status, 'OK' if ok else 'FAIL'))

    # 5. 写入个股消息面影响
    print('\n[5/5] 写入个股"消息面影响"...')
    for sw in stock_writes:
        ok = bitable_update(STOCK_TABLE, sw['record_id'], {'消息面影响': sw['text']})
        print('  {} {} {} | {}'.format(
            sw['impact'], sw['name'],
            'OK' if ok else 'FAIL', sw['key_reason'][:50]
        ))

    # 汇总
    print('\n' + '=' * 60)
    print('  完成!')
    print('  快讯处理: {} 条'.format(len(pending)))
    print('  个股分析: {} 条'.format(len(stock_writes)))
    print('  {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    print('=' * 60)


if __name__ == '__main__':
    main()
