#!/usr/bin/env python3
"""公告分析写入飞书多维表格"""
import json, ssl, socket, os, sys

TOKEN_FILE = os.path.expanduser("~/.feishu-cli/token.json")
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE_ID = 'tbl2A9imBZgM7vLl'

def get_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)['access_token']

def https_request(method, host, path, token, body=None):
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = f'{method} {path} HTTP/1.1\r\nHost: {host}\r\n'
    if token: hdrs += f'Authorization: Bearer {token}\r\n'
    hdrs += 'Content-Type: application/json\r\n'
    if body: hdrs += f'Content-Length: {len(body)}\r\n'
    hdrs += 'Connection: close\r\n\r\n'
    ssock.sendall(hdrs.encode() + (body or b''))
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c: break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he+4:]
    hstr = resp[:he].decode('iso-8859-1')
    status_line = resp[:he].decode('iso-8859-1').split('\r\n')[0]
    if 'chunked' in hstr.lower():
        p, bd = 0, b''
        while p < len(raw):
            e = raw.find(b'\r\n', p)
            if e < 0: break
            sz = int(raw[p:e], 16)
            if sz == 0: break
            bd += raw[e+2:e+2+sz]
            p = e+2+sz+2
        raw = bd
    return status_line, json.loads(raw.decode())


def get_existing_fields():
    token = get_token()
    _, data = https_request('GET', 'open.feishu.cn',
        f'/open-apis/base/v3/bases/{BASE_TOKEN}/tables/{STOCK_TABLE_ID}/fields',
        token=token)
    fields = {}
    if isinstance(data, dict):
        for f in data.get('data', {}).get('fields', []):
            fields[f['name']] = f['id']
    return fields


def create_field(field_name, field_type='text'):
    token = get_token()
    body = json.dumps({'field_name': field_name, 'type': field_type})
    _, data = https_request('POST', 'open.feishu.cn',
        f'/open-apis/base/v3/bases/{BASE_TOKEN}/tables/{STOCK_TABLE_ID}/fields',
        token=token, body=body.encode())
    if data.get('code') == 0:
        fid = data['data']['id']
        print(f'  创建字段 "{field_name}" -> {fid}')
        return fid
    existing = get_existing_fields()
    if field_name in existing:
        return existing[field_name]
    return None


def ensure_fields():
    required = {'最新公告': 'text', '公告分析': 'text'}
    existing = get_existing_fields()
    result = {}
    for name, type_id in required.items():
        if name in existing:
            result[name] = existing[name]
            print(f'  字段 "{name}" 已存在: {existing[name]}')
        else:
            fid = create_field(name, type_id)
            if fid:
                result[name] = fid
            else:
                print(f'  ERROR: 字段 "{name}" 创建失败，飞书写入将跳过此字段')
    if len(result) < len(required):
        missing = [n for n in required if n not in result]
        print(f'  WARNING: 以下字段缺失: {missing}，相关数据将不会被写入')
    return result


def get_stock_records():
    """获取股票表格中的所有记录，返回 {股票名称: {record_id, code}}"""
    token = get_token()
    _, data = https_request('GET', 'open.feishu.cn',
        f'/open-apis/base/v3/bases/{BASE_TOKEN}/tables/{STOCK_TABLE_ID}/records?page_size=50',
        token=token)
    d = data.get('data', {})
    field_names = d.get('fields', [])
    records_data = d.get('data', [])
    record_ids = d.get('record_id_list', [])

    try:
        name_pos = field_names.index('股票名称')
        code_pos = field_names.index('股票代码')
    except ValueError:
        print('找不到股票名称/股票代码字段')
        return {}

    result = {}
    for i, rid in enumerate(record_ids):
        if i >= len(records_data): break
        row = records_data[i]
        name = row[name_pos] if name_pos < len(row) and row[name_pos] else ''
        code = row[code_pos] if code_pos < len(row) and row[code_pos] else ''
        if name and code:
            result[name] = {'record_id': rid, 'code': code}
    return result


def update_fields(record_id, fields_dict):
    """更新一条记录的多维表格字段"""
    token = get_token()
    body = json.dumps(fields_dict, ensure_ascii=False)
    _, result = https_request('PATCH', 'open.feishu.cn',
        f'/open-apis/base/v3/bases/{BASE_TOKEN}/tables/{STOCK_TABLE_ID}/records/{record_id}',
        token=token, body=body.encode())
    return result.get('code') == 0


def write_analysis(stock_analyses):
    """将所有股票的分析结果写入飞书
    stock_analyses: {stock_name: {announcement_list: str, analysis: str}}
    """
    fields = ensure_fields()
    if '最新公告' not in fields or '公告分析' not in fields:
        print('所有必要字段创建/查找失败，无法写入')
        return

    stock_records = get_stock_records()

    for stock_name, data in stock_analyses.items():
        if stock_name not in stock_records:
            print(f'  未找到股票: {stock_name}')
            continue

        rid = stock_records[stock_name]['record_id']
        announcement_list = data.get('announcement_list', '')
        analysis = data.get('analysis', '')

        update_data = {}
        if '最新公告' in fields:
            update_data['最新公告'] = announcement_list[:8000]
        if '公告分析' in fields:
            update_data['公告分析'] = analysis[:8000]

        if not update_data:
            print(f'  {stock_name}: 无可用字段，跳过写入')
            continue

        if update_fields(rid, update_data):
            print(f'  {stock_name}: 写入成功')
        else:
            print(f'  {stock_name}: 写入失败')


if __name__ == '__main__':
    # 测试字段创建
    ensure_fields()
    # 测试写入
    test_data = {
        '浙江世宝': {
            'announcement_list': '2026-05-20 2025年度报告\n2026-05-19 关于签订重大合同的公告',
            'analysis': '【测试分析】近期公告显示公司经营状况良好...'
        }
    }
    write_analysis(test_data)
