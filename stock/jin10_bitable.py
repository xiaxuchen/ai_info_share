"""金十快讯 - bitable 数据读写模块
从飞书多维表格读取全量股票数据，写入快讯记录。
"""
import json, ssl, socket, os
from datetime import datetime

TOKEN_FILE = os.path.expanduser("~/.feishu-cli/token.json")
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE = 'tbl2A9imBZgM7vLl'
FLASH_TABLE = 'tblBxYPy2neYvFtq'  # 金十快讯存储表


def get_token():
    with open(TOKEN_FILE, encoding='utf-8') as f:
        return json.load(f)['access_token']


def https_req(method, host, path, body=None):
    token = get_token()
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
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


def load_stocks():
    """从 bitable 读取全量股票数据，返回股票列表和板块集合"""
    data = https_req('GET', 'open.feishu.cn',
                     '/open-apis/base/v3/bases/{}/tables/{}/records?page_size=50'.format(
                         BASE_TOKEN, STOCK_TABLE))
    d = data.get('data', {})
    field_names = d.get('fields', [])
    records = d.get('data', [])
    record_ids = d.get('record_id_list', [])

    # 定位关键字段
    pos = {}
    for key in ['股票名称', '股票代码', '所属板块', '标签', '所属概念', '板块龙头']:
        try:
            pos[key] = field_names.index(key)
        except ValueError:
            pos[key] = -1

    stocks = []
    sectors_set = set()
    concepts_set = set()

    for i, (rid, row) in enumerate(zip(record_ids, records)):
        name = str(row[pos['股票名称']]) if pos['股票名称'] >= 0 and pos['股票名称'] < len(row) and row[pos['股票名称']] else ''
        code = str(row[pos['股票代码']]) if pos['股票代码'] >= 0 and pos['股票代码'] < len(row) and row[pos['股票代码']] else ''
        sector = str(row[pos['所属板块']]) if pos['所属板块'] >= 0 and pos['所属板块'] < len(row) and row[pos['所属板块']] else ''
        tags = str(row[pos['标签']]) if pos['标签'] >= 0 and pos['标签'] < len(row) and row[pos['标签']] else ''
        concepts = str(row[pos['所属概念']]) if pos['所属概念'] >= 0 and pos['所属概念'] < len(row) and row[pos['所属概念']] else ''
        leader = str(row[pos['板块龙头']]) if pos['板块龙头'] >= 0 and pos['板块龙头'] < len(row) and row[pos['板块龙头']] else ''

        if not name:
            continue

        stock = {
            'record_id': rid,
            'name': name,
            'code': code,
            'sector': sector,
            'tags': tags,
            'concepts': concepts,
            'leader': leader,
        }
        stocks.append(stock)

        for s in sector.replace('，', ',').split(','):
            s = s.strip()
            if s:
                sectors_set.add(s)
        for c in concepts.replace('，', ',').split(','):
            c = c.strip().split('|')[0].strip()  # 取 | 前面的概念
            if c:
                concepts_set.add(c)

    return stocks, sorted(sectors_set), sorted(concepts_set)


def build_context_text(stocks):
    """构建给 Qwen 的上下文文本，包含所有股票信息"""
    lines = []
    for s in stocks:
        parts = ['{} ({})'.format(s['name'], s['code'])]
        if s['sector']:
            parts.append('板块: {}'.format(s['sector']))
        if s['concepts']:
            concepts_short = s['concepts'].split('|')[0].strip() if '|' in s['concepts'] else s['concepts']
            parts.append('概念: {}'.format(concepts_short))
        lines.append('  ' + ' | '.join(parts))
    return '\n'.join(lines)


def write_flash(flash_data, status, analysis=None):
    """写入一条快讯到金十快讯表

    Args:
        flash_data: 原始快讯 dict
        status: '待处理' 或 '垃圾消息'
        analysis: Qwen 分析结果 dict (分类时可为 None)

    Returns:
        record_id 或 None
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    content = flash_data.get('content', '') or flash_data.get('title', '') or json.dumps(flash_data, ensure_ascii=False)
    flash_id = str(flash_data.get('id', ''))

    fields = {
        '快讯内容': content[:5000],
        '状态': status,
        '接收时间': now,
        '快讯ID': flash_id,
    }

    if analysis:
        fields['分析摘要'] = (analysis.get('summary', '') or '')[:1000]
        fields['相关板块'] = '、'.join(analysis.get('sectors', []))[:500]
        fields['相关股票'] = '、'.join(
            '{} ({})'.format(s.get('name', ''), s.get('code', '')) for s in analysis.get('stocks', [])
        )[:500]
        fields['分类标签'] = '、'.join(analysis.get('tags', []))[:500]
        fields['重要性'] = analysis.get('importance', '低')
        fields['情绪'] = analysis.get('sentiment', '中性')

    body = json.dumps({'fields': fields}, ensure_ascii=False).encode()
    resp = https_req('POST', 'open.feishu.cn',
                     '/open-apis/bitable/v1/apps/{}/tables/{}/records'.format(BASE_TOKEN, FLASH_TABLE),
                     body)
    if resp.get('code') == 0:
        rid = resp.get('data', {}).get('record', {}).get('record_id', '')
        return rid
    return None


def update_flash_analysis(record_id, analysis):
    """更新快讯记录的分析结果"""
    fields = {
        '分析摘要': (analysis.get('summary', '') or '')[:1000],
        '相关板块': '、'.join(analysis.get('sectors', []))[:500],
        '相关股票': '、'.join(
            '{} ({})'.format(s.get('name', ''), s.get('code', '')) for s in analysis.get('stocks', [])
        )[:500],
        '分类标签': '、'.join(analysis.get('tags', []))[:500],
        '重要性': analysis.get('importance', '低'),
        '情绪': analysis.get('sentiment', '中性'),
    }
    body = json.dumps({'fields': fields}, ensure_ascii=False).encode()
    resp = https_req('PUT', 'open.feishu.cn',
                     '/open-apis/bitable/v1/apps/{}/tables/{}/records/{}'.format(
                         BASE_TOKEN, FLASH_TABLE, record_id),
                     body)
    return resp.get('code') == 0


if __name__ == '__main__':
    stocks, sectors, concepts = load_stocks()
    print('=== 板块列表 ===')
    for s in sectors:
        print('  ', s)
    print()
    print('=== 概念列表 (前20) ===')
    for c in concepts[:20]:
        print('  ', c)
    print()
    print('=== 股票列表 ===')
    print(build_context_text(stocks))
