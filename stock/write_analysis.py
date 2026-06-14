"""将分析结果写入飞书：详细评论到股吧评论表，总结到股票主表今日评论"""
import json, ssl, socket, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOKEN_FILE = os.path.expanduser('~/.feishu-cli/token.json')
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE = 'tbl2A9imBZgM7vLl'
COMMENT_TABLE = 'tblUFG0O6w1sZQi1'

def get_token():
    with open(TOKEN_FILE, encoding='utf-8') as f:
        return json.load(f)['access_token']

def https_req(method, host, path, token, body=None):
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = '{} {} HTTP/1.1\r\nHost: {}\r\n'.format(method, path, host)
    if token: hdrs += 'Authorization: Bearer {}\r\n'.format(token)
    hdrs += 'Content-Type: application/json\r\n'
    if body: hdrs += 'Content-Length: {}\r\n'.format(len(body))
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
    hstr = resp[:he].decode('iso-8859-1').lower()
    if 'chunked' in hstr:
        p, bd = 0, b''
        while p < len(raw):
            e = raw.find(b'\r\n', p)
            if e < 0: break
            sz = int(raw[p:e], 16)
            if sz == 0: break
            bd += raw[e+2:e+2+sz]
            p = e+2+sz+2
        raw = bd
    return json.loads(raw.decode())

token = get_token()

# 1. Write summaries to stock table 今日评论 field
with open('J:/zss/stock/analysis_results.json', encoding='utf-8') as f:
    analysis = json.load(f)

# Get stock table records to find record IDs
data = https_req('GET', 'open.feishu.cn',
    '/open-apis/base/v3/bases/{}/tables/{}/records?page_size=50'.format(BASE_TOKEN, STOCK_TABLE), token)
d = data.get('data', {})
field_names = d.get('fields', [])
records_data = d.get('data', [])
record_ids = d.get('record_id_list', [])

# Find name position
name_pos = 0
for i, fn in enumerate(field_names):
    if '股票名称' in fn or '名称' in fn:
        name_pos = i
        break

code_map = {
    '浙江世宝': 'sz002703',
    '天岳先进': 'sh688234',
    '三安光电': 'sh600703',
    '黄河旋风': 'sh600172',
    '德赛西威': 'sz002920',
}

print('=== Writing 今日评论 summaries ===')
for i, rid in enumerate(record_ids):
    if i >= len(records_data): break
    name = records_data[i][name_pos] if name_pos < len(records_data[i]) and records_data[i][name_pos] else ''
    if name in analysis:
        summary = analysis[name].get('summary', '')
        body = json.dumps({'今日评论': summary}, ensure_ascii=False)
        resp = https_req('PATCH', 'open.feishu.cn',
            '/open-apis/base/v3/bases/{}/tables/{}/records/{}'.format(BASE_TOKEN, STOCK_TABLE, rid),
            token, body.encode())
        if resp.get('code') == 0:
            print('  {} OK'.format(name))
        else:
            print('  {} FAIL: {}'.format(name, resp.get('msg', '')))

# 2. Write detailed comments to 股吧评论 table
print('\n=== Writing detailed comments ===')
with open('J:/zss/stock/full_comments.json', encoding='utf-8') as f:
    comments_data = json.load(f)

written = 0
for name, posts in comments_data.items():
    for post in posts:
        for c in post.get('cmts', []):
            body = json.dumps({
                'fields': {
                    '股票名称': name,
                    '股票代码': code_map.get(name, ''),
                    '帖子标题': post.get('title', '')[:500],
                    '评论内容': c.get('c', '')[:5000],
                    '真实性': '',
                    '重要性': '',
                    '分析备注': '用户: {} 日期: {} 点赞: {}'.format(c.get('u',''), c.get('d',''), c.get('l','0')),
                }
            }, ensure_ascii=False)
            resp = https_req('POST', 'open.feishu.cn',
                '/open-apis/bitable/v1/apps/{}/tables/{}/records'.format(BASE_TOKEN, COMMENT_TABLE),
                token, body.encode())
            if resp.get('code') == 0:
                written += 1
            else:
                if written == 0:
                    print('  First write failed: {}'.format(resp.get('msg', '')))

print('  Written {} comment records'.format(written))
print('\nDone!')
