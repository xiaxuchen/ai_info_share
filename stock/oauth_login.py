"""
飞书 OAuth 2.0 授权流程 — 获取 user_access_token
启动本地 HTTP 服务器，等待浏览器回调获取 authorization_code，交换 token
"""
import json, ssl, socket, time, os, sys, io, re, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

APP_ID = 'cli_aa9b1f7b98789cd7'
APP_SECRET = '2pGruMsgNX3ilvc8l8aTYgm1HY8vtAXt'
TOKEN_FILE = os.path.expanduser('~/.feishu-cli/token.json')

# Step 1: 打开浏览器，用户授权
REDIRECT_URI = 'http://127.0.0.1:18080/callback'
AUTH_URL = (
    'https://open.feishu.cn/open-apis/authen/v1/authorize'
    f'?app_id={APP_ID}'
    f'&redirect_uri={REDIRECT_URI}'
    '&scope=base:record:read,base:record:write,base:table:read,base:table:write'
)

received_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global received_code
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if 'code' in query:
            received_code = query['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write('<h1>授权成功!</h1><p>可以关闭此页面。</p>'.encode('utf-8'))
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(f'<h1>授权失败</h1><pre>{self.path}</pre>'.encode('utf-8'))

    def log_message(self, format, *args):
        pass  # suppress logs

# Step 2: 打开浏览器
print('正在打开浏览器进行飞书 OAuth 授权...')
print(f'授权 URL: {AUTH_URL[:80]}...')
webbrowser.open(AUTH_URL)

# Step 3: 等待回调
print('等待浏览器回调 (http://127.0.0.1:18080/callback)...')
server = HTTPServer(('127.0.0.1', 18080), OAuthHandler)
server.timeout = 120
try:
    while received_code is None:
        server.handle_request()
except KeyboardInterrupt:
    pass
server.server_close()

if not received_code:
    print('未收到授权码，退出')
    sys.exit(1)

print(f'收到授权码: {received_code[:20]}...')

# Step 4: 交换 access token
ctx = ssl.create_default_context()
sock = socket.create_connection(('open.feishu.cn', 443), timeout=30)
ssock = ctx.wrap_socket(sock, server_hostname='open.feishu.cn')
body = json.dumps({
    'grant_type': 'authorization_code',
    'code': received_code,
    'app_id': APP_ID,
    'app_secret': APP_SECRET,
})
hdrs = 'POST /open-apis/authen/v1/oidc/access_token HTTP/1.1\r\nHost: open.feishu.cn\r\n'
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
hstr = resp[:he].decode('iso-8859-1')
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

result = json.loads(raw.decode('utf-8'))
print(f'Response code: {result.get("code")}')
if result.get('code') == 0:
    token_data = result.get('data', {})
    # Save token
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'access_token': token_data.get('access_token', ''),
            'refresh_token': token_data.get('refresh_token', ''),
            'token_type': token_data.get('token_type', 'Bearer'),
            'expires_at': int(time.time()) + token_data.get('expires_in', 7200),
            'refresh_expires_at': int(time.time()) + token_data.get('refresh_expires_in', 0),
            'scope': token_data.get('scope', ''),
        }, f, ensure_ascii=False, indent=2)
    print(f'Token 已保存到 {TOKEN_FILE}')
    print(f'  access_token: {token_data.get("access_token","")[:30]}...')
    print(f'  scope: {token_data.get("scope","")}')
    print(f'  expires_in: {token_data.get("expires_in")}')
else:
    print(f'Token 交换失败: {result.get("msg")}')
    print(json.dumps(result, ensure_ascii=False, indent=2))
