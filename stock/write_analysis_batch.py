"""批量写入分析结果到飞书"""
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
code_map = {
    '浙江世宝': 'sz002703',
    '天岳先进': 'sh688234',
    '三安光电': 'sh600703',
    '黄河旋风': 'sh600172',
    '德赛西威': 'sz002920',
}

# 1. Write summaries to stock table 今日评论
with open('J:/zss/stock/analysis_results.json', encoding='utf-8') as f:
    analysis = json.load(f)

data = https_req('GET', 'open.feishu.cn',
    '/open-apis/base/v3/bases/{}/tables/{}/records?page_size=50'.format(BASE_TOKEN, STOCK_TABLE), token)
d = data.get('data', {})
records_data = d.get('data', [])
record_ids = d.get('record_id_list', [])

print('=== Writing 今日评论 ===')
for i, rid in enumerate(record_ids):
    if i >= len(records_data): break
    name = records_data[i][0] if records_data[i][0] else ''
    if name in analysis:
        summary = analysis[name].get('summary', '')
        body = json.dumps({'今日评论': summary}, ensure_ascii=False)
        resp = https_req('PATCH', 'open.feishu.cn',
            '/open-apis/base/v3/bases/{}/tables/{}/records/{}'.format(BASE_TOKEN, STOCK_TABLE, rid), token, body.encode())
        print('  {}: {}'.format(name, 'OK' if resp.get('code')==0 else resp.get('msg','FAIL')))

# 2. Batch write comments
print('\n=== Batch writing comments ===')
with open('J:/zss/stock/full_comments.json', encoding='utf-8') as f:
    comments_data = json.load(f)

all_records = []
for name, posts in comments_data.items():
    for post in posts:
        for c in post.get('cmts', []):
            all_records.append({
                'fields': {
                    '股票名称': name,
                    '股票代码': code_map.get(name, ''),
                    '帖子标题': post.get('title', '')[:500],
                    '评论内容': c.get('c', '')[:5000],
                    '分析备注': '用户: {} 日期: {} 点赞: {}'.format(c.get('u',''), c.get('d',''), c.get('l','0')),
                }
            })

print('Total records to write: {}'.format(len(all_records)))

# Batch write 100 at a time
batch_size = 100
written = 0
for i in range(0, len(all_records), batch_size):
    batch = all_records[i:i+batch_size]
    body = json.dumps({'records': batch}, ensure_ascii=False)
    resp = https_req('POST', 'open.feishu.cn',
        '/open-apis/bitable/v1/apps/{}/tables/{}/records/batch_create'.format(BASE_TOKEN, COMMENT_TABLE),
        token, body.encode())
    if resp.get('code') == 0:
        written += len(batch)
        print('  Batch {}: {} records OK ({}/{})'.format(i//batch_size+1, len(batch), written, len(all_records)))
    else:
        print('  Batch {}: FAILED - {}'.format(i//batch_size+1, resp.get('msg','')))
        break

print('\nDone! Written {} records total'.format(written))
