"""Debug: test single record update with v1 API"""
import json, ssl, socket, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

app_id = 'cli_aa9b1f7b98789cd7'
app_secret = '2pGruMsgNX3ilvc8l8aTYgm1HY8vtAXt'
body = json.dumps({'app_id': app_id, 'app_secret': app_secret})
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
token = json.loads(raw.decode('utf-8'))['app_access_token']
print(f'Token: {token[:20]}...')

def req(method, path, body_bytes=None):
    ctx2 = ssl.create_default_context()
    sock2 = socket.create_connection(('open.feishu.cn', 443), timeout=30)
    ssock2 = ctx2.wrap_socket(sock2, server_hostname='open.feishu.cn')
    hdrs2 = f'{method} {path} HTTP/1.1\r\nHost: open.feishu.cn\r\n'
    hdrs2 += f'Authorization: Bearer {token}\r\n'
    hdrs2 += 'Content-Type: application/json\r\n'
    if body_bytes:
        hdrs2 += f'Content-Length: {len(body_bytes)}\r\n'
    hdrs2 += 'Connection: close\r\n\r\n'
    ssock2.sendall(hdrs2.encode() + (body_bytes or b''))
    resp2 = b''
    while True:
        c = ssock2.read(8192)
        if not c: break
        resp2 += c
    ssock2.close()
    he2 = resp2.find(b'\r\n\r\n')
    raw2 = resp2[he2+4:]
    hstr = resp2[:he2].decode('iso-8859-1')
    if 'chunked' in hstr.lower():
        p, bd = 0, b''
        while p < len(raw2):
            e = raw2.find(b'\r\n', p)
            if e < 0: break
            sz = int(raw2[p:e], 16)
            if sz == 0: break
            bd += raw2[e+2:e+2+sz]
            p = e+2+sz+2
        raw2 = bd
    return json.loads(raw2.decode('utf-8'))

BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE = 'tbl2A9imBZgM7vLl'
record_id = 'recvksfbiUmCIL'  # zhejiang shibao

# Test 1: PUT with field name
update_body = json.dumps({'fields': {'今日评论': 'test content v1'}}, ensure_ascii=False)
path = f'/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{STOCK_TABLE}/records/{record_id}'
result = req('PUT', path, update_body.encode())
print(f'Test 1 (PUT v1): code={result.get("code")}, msg={result.get("msg","")}')

# Test 2: Try PATCH instead
result2 = req('PATCH', path, update_body.encode())
print(f'Test 2 (PATCH v1): code={result2.get("code")}, msg={result2.get("msg","")}')

# Test 3: Try v3 API with app token (might work for some endpoints)
path3 = f'/open-apis/base/v3/bases/{BASE_TOKEN}/tables/{STOCK_TABLE}/records/{record_id}'
result3 = req('PATCH', path3, update_body.encode())
print(f'Test 3 (PATCH v3): code={result3.get("code")}, msg={result3.get("msg","")}')

# Test 4: Try different field reference - use field_id directly
update_body4 = json.dumps({'fields': {'fldS7PySIN': 'test content by field id'}}, ensure_ascii=False)
result4 = req('PUT', path, update_body4.encode())
print(f'Test 4 (PUT v1 by field_id): code={result4.get("code")}, msg={result4.get("msg","")}')

# Test 5: Check table fields to verify field names
path5 = f'/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{STOCK_TABLE}/fields'
result5 = req('GET', path5)
if result5.get('code') == 0:
    items = result5.get('data', {}).get('items', [])
    for f in items[:5]:
        print(f'  Field: {f.get("field_name")} -> {f.get("field_id")} (type={f.get("type")})')
    # Find 今日评论
    for f in items:
        if '评论' in f.get('field_name', ''):
            print(f'  TARGET: {f.get("field_name")} -> {f.get("field_id")} (type={f.get("type")})')
