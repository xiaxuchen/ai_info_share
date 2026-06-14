"""用 raw socket + cookie 调股吧评论 API，抓取完整评论"""
import json, ssl, socket, time, re, os, sys

TOKEN_FILE = os.path.expanduser("~/.feishu-cli/token.json")
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE = 'tbl2A9imBZgM7vLl'
COMMENT_TABLE = 'tblUFG0O6w1sZQi1'

# Load cookies
with open('J:/zss/stock/guba_auth_cookies.json', encoding='utf-8') as f:
    cookies = json.load(f)
cookie_str = '; '.join(f'{c["name"]}={c["value"]}' for c in cookies)

def guba_req(host, path, post_data=None):
    """请求股吧 API，POST JSON"""
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=15)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    body = json.dumps(post_data).encode() if post_data else None
    method = 'POST' if body else 'GET'
    hdrs = f'{method} {path} HTTP/1.1\r\nHost: {host}\r\n'
    hdrs += 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n'
    hdrs += 'Content-Type: application/json\r\n'
    hdrs += f'Cookie: {cookie_str}\r\n'
    hdrs += 'Referer: https://guba.eastmoney.com/\r\n'
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
    return json.loads(raw.decode('utf-8'))

def guba_page(host, path):
    """请求股吧页面 HTML"""
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=15)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = f'GET {path} HTTP/1.1\r\nHost: {host}\r\n'
    hdrs += 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n'
    hdrs += f'Cookie: {cookie_str}\r\n'
    hdrs += 'Connection: close\r\n\r\n'
    ssock.sendall(hdrs.encode())
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
    return raw

def extract_json_var(raw_bytes, var_name):
    idx = raw_bytes.find(var_name.encode() + b'=')
    if idx < 0: return None
    start = raw_bytes.find(b'{', idx)
    if start < 0: return None
    depth = 0; in_str = False; esc = False; end = start
    for i in range(start, len(raw_bytes)):
        b = raw_bytes[i]
        if esc: esc = False; continue
        if b == 0x5c: esc = True; continue
        if b == 0x22: in_str = not in_str; continue
        if in_str: continue
        if b == 0x7b: depth += 1
        elif b == 0x7d:
            depth -= 1
            if depth == 0: end = i + 1; break
    if end <= start: return None
    try: return json.loads(raw_bytes[start:end].decode('utf-8'))
    except: return None

def strip_html(text):
    if not text: return ''
    return re.sub(r'<[^>]+>', '', text).replace('&nbsp;',' ').replace('&lt;','<').replace('&gt;','>').replace('&amp;','&').strip()

stocks = {
    'sz002703': '浙江世宝',
    'sh688234': '天岳先进',
    'sh600703': '三安光电',
    'sh600172': '黄河旋风',
    'sz002920': '德赛西威',
}

# ========================
print('=== 抓取股吧评论（全文版） ===\n')

all_data = {}

for code, name in stocks.items():
    pure = code[2:]
    print(f'\n{name} ({pure})')

    # 1. 获取帖子列表
    raw = guba_page('guba.eastmoney.com', f'/list,{pure},f_1.html')
    data = extract_json_var(raw, 'article_list')
    if not data:
        print('  获取帖子列表失败')
        continue

    posts_with_comments = [p for p in data.get('re', [])
                           if p.get('post_comment_count', 0) > 0]
    print(f'  有评论的帖子: {len(posts_with_comments)}')

    stock_posts = []

    for pidx, p in enumerate(posts_with_comments):
        post_id = p['post_id']
        post_title = p.get('post_title', '')
        post_comment_count = p.get('post_comment_count', 0)

        print(f'  [{pidx+1}] {post_title[:50]}... ({post_comment_count}评论)')

        # 2. 获取帖子正文（从页面 JSON）
        time.sleep(0.5)
        raw2 = guba_page('guba.eastmoney.com', f'/news,{pure},{post_id}.html')
        post_data = extract_json_var(raw2, 'post_article')
        post_body = strip_html(post_data.get('post_content', '')) if post_data else ''

        # 3. 获取评论（调用 API，一次拿最多条）
        time.sleep(0.3)
        try:
            reply_data = guba_req('gbapi.eastmoney.com',
                '/reply/api/Reply/ArticleNewReplyList',
                {'post_id': int(post_id), 'sort': 1, 'sorttype': 1, 'p': 1, 'ps': 50})

            comments = []
            re_list = reply_data.get('re')
            if re_list:
                for r in re_list:
                    comments.append({
                        'user': r.get('user_name', ''),
                        'date': r.get('reply_publish_time', ''),
                        'likes': r.get('reply_like_count', 0),
                        'content': r.get('reply_content', ''),  # 全文
                    })
                print(f'    Got {len(comments)} comments (body={len(post_body)} chars)')
            else:
                print(f'    No comments returned (rc={reply_data.get("rc")})')
        except Exception as e:
            print(f'    API error: {e}')
            comments = []

        if comments or post_body:
            stock_posts.append({
                'post_id': post_id,
                'post_title': post_title,
                'post_comment_count': post_comment_count,
                'post_body': post_body,
                'comments': comments,
            })

    all_data[name] = stock_posts
    total_c = sum(len(p['comments']) for p in stock_posts)
    print(f'  >> {len(stock_posts)} posts, {total_c} comments')

# Save
with open('J:/zss/stock/full_comments.json', 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

grand_total = sum(sum(len(c['comments']) for c in p) for p in all_data.values())
print(f'\n=== Done! Total: {grand_total} comments ===')
