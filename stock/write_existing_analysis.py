"""将已有分析结果写入飞书股票表的"今日评论"字段"""
import json, ssl, socket, time, os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

APP_ID = 'cli_aa9b1f7b98789cd7'
APP_SECRET = '2pGruMsgNX3ilvc8l8aTYgm1HY8vtAXt'
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE = 'tbl2A9imBZgM7vLl'
ANALYSIS_FILE = 'J:/zss/stock/analysis_results.json'

_feishu_token = None
_feishu_token_time = 0

def get_app_token():
    global _feishu_token, _feishu_token_time
    if _feishu_token and time.time() - _feishu_token_time < 3600:
        return _feishu_token
    body = json.dumps({'app_id': APP_ID, 'app_secret': APP_SECRET})
    ctx = ssl.create_default_context()
    sock = socket.create_connection(('open.feishu.cn', 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname='open.feishu.cn')
    hdrs = 'POST /open-apis/auth/v3/app_access_token/internal HTTP/1.1\r\nHost: open.feishu.cn\r\n'
    hdrs += 'Content-Type: application/json\r\n'
    hdrs += f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n'
    ssock.sendall(hdrs.encode() + body.encode())
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c: break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he+4:]
    _feishu_token = json.loads(raw.decode('utf-8')).get('app_access_token', '')
    _feishu_token_time = time.time()
    return _feishu_token

def decode_chunked(raw):
    p, bd = 0, b''
    while p < len(raw):
        e = raw.find(b'\r\n', p)
        if e < 0: break
        sz = int(raw[p:e], 16)
        if sz == 0: break
        bd += raw[e+2:e+2+sz]
        p = e+2+sz+2
    return bd

def bitable_req(method, path, body_bytes=None):
    token = get_app_token()
    ctx = ssl.create_default_context()
    sock = socket.create_connection(('open.feishu.cn', 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname='open.feishu.cn')
    hdrs = f'{method} {path} HTTP/1.1\r\nHost: open.feishu.cn\r\n'
    hdrs += f'Authorization: Bearer {token}\r\n'
    hdrs += 'Content-Type: application/json\r\n'
    if body_bytes:
        hdrs += f'Content-Length: {len(body_bytes)}\r\n'
    hdrs += 'Connection: close\r\n\r\n'
    ssock.sendall(hdrs.encode() + (body_bytes or b''))
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c: break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he+4:]
    hstr = resp[:he].decode('iso-8859-1')
    if 'chunked' in hstr.lower():
        raw = decode_chunked(raw)
    return json.loads(raw.decode('utf-8'))

def read_all_stocks():
    """从 bitable 读取所有股票"""
    all_stocks = []
    page_token = None
    while True:
        path = f'/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{STOCK_TABLE}/records?page_size=200'
        if page_token:
            path += '&page_token=' + page_token
        data = bitable_req('GET', path)
        d = data.get('data', {})
        items = d.get('items', [])
        has_more = d.get('has_more', False)
        page_token = d.get('page_token', '')
        for item in items:
            fields = item.get('fields', {})
            name = fields.get('股票名称', '')
            code = fields.get('股票代码', '')
            if name and code:
                all_stocks.append({'name': name, 'code': code, 'record_id': item['record_id']})
        if not has_more:
            break
    return all_stocks

def update_record(record_id, fields_dict):
    body = json.dumps({'fields': fields_dict}, ensure_ascii=False)
    result = bitable_req('PUT',
        f'/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{STOCK_TABLE}/records/{record_id}',
        body.encode())
    return result.get('code') == 0

# ====== MAIN ======
print('读取分析结果...')
with open(ANALYSIS_FILE, 'r', encoding='utf-8') as f:
    analyses = json.load(f)
print(f'  已加载 {len(analyses)} 只股票的分析结果')

print('\n读取股票表...')
stocks = read_all_stocks()
print(f'  读取到 {len(stocks)} 只股票')

print('\n更新"今日评论"字段...')
updated = 0
not_found = []

for s in stocks:
    name = s['name']
    if name in analyses and analyses[name].get('summary'):
        summary = analyses[name]['summary']
        if update_record(s['record_id'], {'今日评论': summary}):
            print(f'  {name}: 已更新 ({len(summary)} chars)', flush=True)
            updated += 1
        else:
            print(f'  {name}: 更新失败', flush=True)
            not_found.append(name)
    else:
        print(f'  {name}: 无分析数据，跳过', flush=True)
        not_found.append(name)
    time.sleep(0.3)

print(f'\n完成! 更新了 {updated} 只股票')
if not_found:
    print(f'无分析数据的股票: {", ".join(not_found)}')
