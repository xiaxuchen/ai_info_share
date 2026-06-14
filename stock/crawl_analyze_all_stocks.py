"""
全量股票评论抓取 + Qwen3-32B 分析 + 飞书更新
从 bitable 股票表读取所有股票 -> 抓取股吧评论 -> AI 分析 -> 写入"今日评论"字段
纯 socket 实现，无需 Selenium。使用 v1 bitable API（兼容 app_access_token）
"""
import json, ssl, socket, time, os, sys, io, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ============================================================
# 配置
# ============================================================
API_KEY = 'sk-lsnhfgotvsmsndxsonigqhvpdmbtajviumyobxonrbigsyhh'
APP_ID = 'cli_aa9b1f7b98789cd7'
APP_SECRET = '2pGruMsgNX3ilvc8l8aTYgm1HY8vtAXt'
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE = 'tbl2A9imBZgM7vLl'
COMMENT_TABLE = 'tblUFG0O6w1sZQi1'
COMMENTS_FILE = 'J:/zss/stock/full_comments.json'
ANALYSIS_FILE = 'J:/zss/stock/analysis_results.json'
COOKIE_FILE = 'J:/zss/stock/guba_auth_cookies.json'

# ============================================================
# 1. 飞书 v1 API 工具（使用 app_access_token）
# ============================================================

_feishu_token = None
_feishu_token_time = 0

def get_app_token():
    """获取飞书 app_access_token，带缓存"""
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
    """飞书 v1 bitable API 请求"""
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

# ============================================================
# 2. 股吧请求工具
# ============================================================

with open(COOKIE_FILE, encoding='utf-8') as f:
    COOKIE_STR = '; '.join(f'{c["name"]}={c["value"]}' for c in json.load(f))

def guba_page(host, path):
    """GET 股吧页面 HTML"""
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=15)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = f'GET {path} HTTP/1.1\r\nHost: {host}\r\n'
    hdrs += 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n'
    hdrs += f'Cookie: {COOKIE_STR}\r\n'
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
        raw = decode_chunked(raw)
    return raw

def guba_api(host, path, post_data):
    """POST 股吧评论 API"""
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=15)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    body = json.dumps(post_data).encode()
    hdrs = f'POST {path} HTTP/1.1\r\nHost: {host}\r\n'
    hdrs += 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n'
    hdrs += 'Content-Type: application/json\r\n'
    hdrs += f'Cookie: {COOKIE_STR}\r\n'
    hdrs += 'Referer: https://guba.eastmoney.com/\r\n'
    hdrs += f'Content-Length: {len(body)}\r\n'
    hdrs += 'Connection: close\r\n\r\n'
    ssock.sendall(hdrs.encode() + body)
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

def extract_json_var(raw_bytes, var_name):
    """从 HTML 字节中提取 var xxx = {...} JSON"""
    idx = raw_bytes.find(var_name.encode() + b'=')
    if idx < 0:
        idx = raw_bytes.find(var_name.encode() + b' =')
    if idx < 0:
        return None
    start = raw_bytes.find(b'{', idx)
    if start < 0:
        return None
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
    try:
        return json.loads(raw_bytes[start:end].decode('utf-8'))
    except:
        return None

def strip_html(text):
    if not text: return ''
    return re.sub(r'<[^>]+>', '', text).replace('&nbsp;',' ').replace('&lt;','<').replace('&gt;','>').replace('&amp;','&').strip()

# ============================================================
# 3. 从飞书读取所有股票
# ============================================================

def read_all_stocks():
    """从 bitable 股票表读取所有股票，返回 [{name, code, record_id}]"""
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
                all_stocks.append({
                    'name': name,
                    'code': code,
                    'record_id': item['record_id'],
                })

        if not has_more:
            break

    return all_stocks

# ============================================================
# 4. 抓取股吧评论
# ============================================================

def crawl_stock_comments(name, code, max_posts=30):
    """
    抓取单只股票的股吧评论
    返回: [{id, title, body, cmts: [{u, d, l, c}]}] 兼容 analyze_comments 格式
    """
    pure_code = code[2:] if code[:2] in ('sz', 'sh') else code
    print(f'\n  {name} ({code} -> {pure_code})', flush=True)

    raw = guba_page('guba.eastmoney.com', f'/list,{pure_code},f_1.html')
    data = extract_json_var(raw, 'article_list')
    if not data:
        print(f'    获取帖子列表失败', flush=True)
        return []

    posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0]
    posts = posts[:max_posts]
    print(f'    有评论的帖子: {len(posts)}', flush=True)

    stock_posts = []

    for pi, p in enumerate(posts):
        post_id = p['post_id']
        title = p.get('post_title', '')
        ncmt = p.get('post_comment_count', 0)
        print(f'    [{pi+1}/{len(posts)}] {title[:45]}... ({ncmt}\u8bc4\u8bba)', flush=True, end='')

        time.sleep(0.4)
        try:
            raw2 = guba_page('guba.eastmoney.com', f'/news,{pure_code},{post_id}.html')
            post_data = extract_json_var(raw2, 'post_article')
            body = strip_html(post_data.get('post_content', '')) if post_data else ''
        except:
            body = ''

        time.sleep(0.3)
        all_comments = []
        try:
            for api_page in range(1, 6):
                reply = guba_api('gbapi.eastmoney.com',
                    '/reply/api/Reply/ArticleNewReplyList',
                    {'post_id': int(post_id), 'sort': 1, 'sorttype': 1, 'p': api_page, 'ps': 50})
                re_list = reply.get('re')
                if not re_list:
                    break
                for r in re_list:
                    all_comments.append({
                        'u': r.get('user_name', ''),
                        'd': r.get('reply_publish_time', ''),
                        'l': str(r.get('reply_like_count', 0)),
                        'c': r.get('reply_content', ''),
                    })
                if len(re_list) < 50:
                    break
                time.sleep(0.2)
        except Exception as e:
            print(f' err', flush=True, end='')

        stock_posts.append({
            'id': post_id,
            'title': title,
            'body': body,
            'cmts': all_comments,
        })
        print(f' -> {len(all_comments)}cmt', flush=True)

    total_c = sum(len(p['cmts']) for p in stock_posts)
    print(f'    小计: {len(stock_posts)} posts, {total_c} comments', flush=True)
    return stock_posts

# ============================================================
# 5. Qwen3-32B 分析
# ============================================================

def qwen_chat(messages, max_tokens=2000):
    """调用硅基流动 Qwen3-32B"""
    body = json.dumps({
        'model': 'Qwen/Qwen3-32B',
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': 0.3
    })
    ctx = ssl.create_default_context()
    sock = socket.create_connection(('api.siliconflow.cn', 443), timeout=120)
    ssock = ctx.wrap_socket(sock, server_hostname='api.siliconflow.cn')
    hdrs = 'POST /v1/chat/completions HTTP/1.1\r\nHost: api.siliconflow.cn\r\n'
    hdrs += 'Authorization: Bearer {}\r\n'.format(API_KEY)
    hdrs += 'Content-Type: application/json\r\n'
    hdrs += 'Content-Length: {}\r\nConnection: close\r\n\r\n'.format(len(body))
    ssock.sendall(hdrs.encode() + body.encode())
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c: break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he+4:]
    return json.loads(raw.decode()).get('choices', [{}])[0].get('message', {}).get('content', '')

def analyze_stock_comments(name, posts):
    """分析一只股票的所有评论，返回 {stats, details, summary}"""
    total_cmts = sum(len(p['cmts']) for p in posts)
    print(f'\n  === {name}: {len(posts)} posts, {total_cmts} comments ===', flush=True)

    all_analyzed = []

    for i, post in enumerate(posts):
        if not post['cmts']:
            continue

        cmt_texts = []
        for j, c in enumerate(post['cmts']):
            cmt_texts.append('[{}.{}] {}'.format(i+1, j+1, c['c'][:300]))

        batch = '\n'.join(cmt_texts)
        prompt = """\u5206\u6790\u4ee5\u4e0b\u80a1\u5427\u8bc4\u8bba\uff0c\u5bf9\u6bcf\u6761\u8bc4\u8bba\u6807\u6ce8\uff1a
- \u7c7b\u578b\uff1a[\u6709\u4ef7\u503c]/[\u60c5\u7eea\u53d1\u6cc4]/[\u65e0\u610f\u4e49\u704c\u6c34]/[\u5e84\u6258\u6c34\u519b]
- \u91cd\u8981\u6027\uff1a[\u9ad8]/[\u4e2d]/[\u4f4e]\uff08\u9ad8=\u5bf9\u6295\u8d44\u6709\u53c2\u8003\u4ef7\u503c\uff09

\u5e16\u5b50\u6807\u9898\uff1a{title}

\u8bc4\u8bba\uff1a
{comments}

\u8bf7\u4e25\u683c\u6309\u683c\u5f0f\u8f93\u51fa\uff0c\u6bcf\u6761\u4e00\u884c\uff1a
[\u5e8f\u53f7] [\u7c7b\u578b] [\u91cd\u8981\u6027] | \u5206\u6790\u8bf4\u660e\uff0810\u5b57\u4ee5\u5185\uff09""".format(
            title=post.get('title','\u65e0\u6807\u9898'), comments=batch)

        try:
            result = qwen_chat([{'role': 'user', 'content': prompt}], 800)
            analyzed = []
            for line in result.strip().split('\n'):
                line = line.strip()
                if line and '[' in line:
                    analyzed.append(line)
            all_analyzed.append({'post_id': post['id'], 'title': post['title'][:60], 'analysis': analyzed})
            print(f'    [{i+1}/{len(posts)}] {len(post["cmts"])} comments analyzed', flush=True)
        except Exception as e:
            print(f'    [{i+1}/{len(posts)}] analyze error: {e}', flush=True)
            all_analyzed.append({'post_id': post['id'], 'title': post['title'][:60], 'analysis': ['[\u5206\u6790\u5931\u8d25]']})

        time.sleep(0.5)

    stats = {'\u6709\u4ef7\u503c': 0, '\u60c5\u7eea\u53d1\u6cc4': 0, '\u65e0\u610f\u4e49\u704c\u6c34': 0, '\u5e84\u6258\u6c34\u519b': 0, '\u9ad8\u91cd\u8981\u6027': 0}
    for a in all_analyzed:
        for line in a['analysis']:
            for k in ['\u6709\u4ef7\u503c', '\u60c5\u7eea\u53d1\u6cc4', '\u65e0\u610f\u4e49\u704c\u6c34', '\u5e84\u6258\u6c34\u519b']:
                if '[' + k + ']' in line: stats[k] += 1
            if '[\u9ad8]' in line: stats['\u9ad8\u91cd\u8981\u6027'] += 1

    summary_prompt = """\u4ee5\u4e0b\u662f{name}\u80a1\u5427\u7684\u8bc4\u8bba\u5206\u6790\u7edf\u8ba1\uff1a
- \u603b\u8bc4\u8bba\u6570: {total}
- \u6709\u4ef7\u503c: {val}\u6761
- \u60c5\u7eea\u53d1\u6cc4: {emo}\u6761
- \u65e0\u610f\u4e49\u704c\u6c34: {spam}\u6761
- \u5e84\u6258\u6c34\u519b: {shill}\u6761
- \u9ad8\u91cd\u8981\u6027: {high}\u6761

\u8bf7\u751f\u6210200\u5b57\u4ee5\u5185\u7684\u4eca\u65e5\u8bc4\u8bba\u603b\u7ed3\uff0c\u683c\u5f0f\uff1a
\u3010\u4eca\u65e5\u8bc4\u8bba\u603b\u7ed3-{name}\u3011
\u5e02\u573a\u60c5\u7eea\uff1a\uff08\u770b\u591a/\u770b\u7a7a/\u5206\u6b67/\u89c2\u671b\uff09
\u5173\u952e\u8ba8\u8bba\uff1a\uff081-2\u53e5\u6982\u62ec\uff09
\u98ce\u9669\u63d0\u793a\uff1a\uff08\u5982\u6709\uff09
\u5efa\u8bae\u5173\u6ce8\uff1a\uff08\u503c\u5f97\u5173\u6ce8\u7684\u4fe1\u606f\uff09""".format(
        name=name, total=total_cmts,
        val=stats['\u6709\u4ef7\u503c'], emo=stats['\u60c5\u7eea\u53d1\u6cc4'],
        spam=stats['\u65e0\u610f\u4e49\u704c\u6c34'], shill=stats['\u5e84\u6258\u6c34\u519b'],
        high=stats['\u9ad8\u91cd\u8981\u6027']
    )

    try:
        summary = qwen_chat([{'role': 'user', 'content': summary_prompt}], 300)
        print(f'    Summary generated', flush=True)
    except Exception as e:
        summary = '\u3010\u4eca\u65e5\u8bc4\u8bba\u603b\u7ed3-{}\n\u5206\u6790\u751f\u6210\u5931\u8d25: {}\n\u3011'.format(name, e)
        print(f'    Summary error: {e}', flush=True)

    return {'stats': stats, 'details': all_analyzed, 'summary': summary}

# ============================================================
# 6. 写入飞书（v1 API）
# ============================================================

def update_stock_comment_field(record_id, summary_text):
    """更新股票记录的 u201c 今日评论 u201d 字段"""
    body = json.dumps({'fields': {'今日评论': summary_text}}, ensure_ascii=False)
    result = bitable_req('PUT',
        f'/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{STOCK_TABLE}/records/{record_id}',
        body.encode())
    return result.get('code') == 0

def write_comment_details(stock_name, stock_code, posts, analysis):
    """将每条评论的分析写入股吧评论表"""
    count = 0
    for post in posts:
        post_title = post.get('title', '')[:100]
        for ci, cmt in enumerate(post['cmts']):
            # 找到对应的分析行
            analyzed = ''
            for a in analysis.get('details', []):
                if a['post_id'] == post['id']:
                    lines = a.get('analysis', [])
                    # 匹配序号
                    target_prefix = '[{}.{}]'.format(1, ci+1)  # approximate
                    for line in lines:
                        analyzed = line[:200]
                        break
                    break

            fields = {
                '股票名称': stock_name,
                '股票代码': stock_code,
                '帖子标题': post_title,
                '评论内容': cmt['c'][:500],
                '真实性': '',
                '重要性': '',
                '分析备注': analyzed[:500],
            }
            body = json.dumps({'fields': fields}, ensure_ascii=False)
            resp = bitable_req('POST',
                f'/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{COMMENT_TABLE}/records',
                body.encode())
            if resp.get('code') == 0:
                count += 1
            time.sleep(0.15)
    return count

# ============================================================
# 7. 主流程
# ============================================================

def main():
    print('=' * 60)
    print('全量股票评论抓取 + Qwen分析 + 飞书更新')
    print('=' * 60)

    # Step 1: 读取所有股票
    print('\n[1/4] 读取股票列表...')
    stocks = read_all_stocks()
    if not stocks:
        print('未找到任何股票记录，退出')
        return
    print(f'  读取到 {len(stocks)} 只股票:')
    for s in stocks:
        print(f'    {s["name"]} ({s["code"]})')

    # Step 2: 逐只抓取评论
    print('\n[2/4] 抓取股吧评论...')
    all_data = {}
    for i, s in enumerate(stocks):
        name, code = s['name'], s['code']
        print(f'\n--- [{i+1}/{len(stocks)}] {name} ({code}) ---', flush=True)
        try:
            posts = crawl_stock_comments(name, code)
            all_data[name] = posts
        except Exception as e:
            print(f'  抓取失败: {e}', flush=True)
            all_data[name] = []

        with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        time.sleep(1)

    grand = sum(sum(len(p['cmts']) for p in posts) for posts in all_data.values())
    print(f'\n  总计: {sum(len(p) for p in all_data.values())} posts, {grand} comments')

    # Step 3: AI 分析
    print('\n[3/4] Qwen3-32B 分析评论...')
    results = {}
    for name, posts in all_data.items():
        if not posts:
            results[name] = {'stats': {}, 'details': [], 'summary': ''}
            continue
        try:
            results[name] = analyze_stock_comments(name, posts)
        except Exception as e:
            print(f'  {name} 分析失败: {e}', flush=True)
            results[name] = {'stats': {}, 'details': [], 'summary': f'\u5206\u6790\u5931\u8d25: {e}'}
        time.sleep(1)

    with open(ANALYSIS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print('\n  === 分析统计 ===')
    for name, r in results.items():
        s = r.get('stats', {})
        if s:
            print('  {}: {}条, 有价值={}, 情绪={}, 灌水={}, 水军={}'.format(
                name, sum(s.values()), s.get('有价值',0), s.get('情绪发泄',0),
                s.get('无意义灌水',0), s.get('庄托水军',0)))

    # Step 4: 写入飞书
    print('\n[4/4] 写入飞书...')
    updated = 0
    comment_total = 0
    for s in stocks:
        name = s['name']
        code = s['code']
        if name in results and results[name].get('summary'):
            summary = results[name]['summary']
            if update_stock_comment_field(s['record_id'], summary):
                print(f'  {name}: 今日评论已更新', flush=True)
                updated += 1
            else:
                print(f'  {name}: 更新失败', flush=True)

            # 写入详细评论到股吧评论表
            if name in all_data and all_data[name]:
                c = write_comment_details(name, code, all_data[name], results[name])
                comment_total += c
                if c > 0:
                    print(f'      评论详情写入: {c} 条', flush=True)
        else:
            print(f'  {name}: 无分析结果，跳过', flush=True)
        time.sleep(0.3)

    print(f'\n完成! 更新了 {updated}/{len(stocks)} 只股票，写入了 {comment_total} 条评论详情')

if __name__ == '__main__':
    main()
