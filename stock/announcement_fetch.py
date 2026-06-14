#!/usr/bin/env python3
"""公告采集模块 - 从巨潮/东财获取公告，PDF转文本，去重"""
import json, ssl, socket, os, time, re
from datetime import datetime, timedelta

# 配置
ANNOUNCEMENT_LOOKBACK_DAYS = 3
CNINFO_PAGE_SIZE = 30
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'announcement_state.json')
TOKEN_FILE = os.path.expanduser("~/.feishu-cli/token.json")

def get_user_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)['access_token']


def https_post(host, path, token=None, body=None, extra_headers=''):
    """纯 socket HTTPS POST 请求"""
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    b = body.encode() if isinstance(body, str) else (body or b'')
    hdrs = f'POST {path} HTTP/1.1\r\nHost: {host}\r\n'
    if token:
        hdrs += f'Authorization: Bearer {token}\r\n'
    hdrs += 'Content-Type: application/json\r\n'
    if extra_headers:
        hdrs += extra_headers + '\r\n'
    hdrs += f'Content-Length: {len(b)}\r\nConnection: close\r\n\r\n'
    ssock.sendall(hdrs.encode() + b)
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
    return json.loads(raw.decode())


def https_get(host, path):
    """纯 socket HTTPS GET 请求（东财公告接口用，返回gbk解码的JSON）"""
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = f'GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\nAccept: application/json\r\nConnection: close\r\n\r\n'
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
    # 东财API返回UTF-8 JSON
    try:
        return json.loads(raw.decode('utf-8'))
    except:
        return json.loads(raw.decode('utf-8', errors='replace'))


def fetch_cninfo_announcements(code, exchange, days=ANNOUNCEMENT_LOOKBACK_DAYS):
    """从巨潮获取公告列表（不过滤股票，返回近期全部公告）
    code: 6位纯数字, 如 '002703'
    exchange: 'sz' 或 'sh'
    返回: [{announcementId, announcementTitle, announcementTime, adjunctUrl, secCode}, ...]
    """
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    body = json.dumps({
        'pageNum': 1,
        'pageSize': CNINFO_PAGE_SIZE,
        'seDate': f'{start_date}~{end_date}'
    })
    try:
        data = https_post('www.cninfo.com.cn', '/new/hisAnnouncement/query', body=body,
                          extra_headers=f'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\nReferer: http://www.cninfo.com.cn/\r\n')
        return data.get('announcements', []) if isinstance(data, dict) else []
    except Exception as e:
        print(f'  巨潮查询失败: {e}')
        return []


def fetch_eastmoney_announcements(code, days=ANNOUNCEMENT_LOOKBACK_DAYS):
    """从东方财富获取公告列表
    code: 带交易所前缀，如 'sz002703'
    """
    pure_code = code[2:] if len(code) > 2 else code
    exchange = code[:2]  # sz or sh
    ann_type = 'SZA' if exchange == 'sz' else 'SHA'
    path = f'/api/security/ann?stock_list={pure_code}&page_size=30&page_index=1&sr=-1&ann_type={ann_type}'
    try:
        data = https_get('np-anotice-stock.eastmoney.com', path)
        announcements = []
        for item in data.get('data', {}).get('list', []):
            art_code = str(item.get('art_code', ''))
            title = item.get('title_ch', '') or item.get('title', '')
            notice_date = item.get('notice_date', '')[:10]
            # 构造公告详情页URL
            url = f'https://data.eastmoney.com/notices/detail/{pure_code}/{art_code}.html'
            announcements.append({
                'announcementId': art_code,
                'announcementTitle': title,
                'announcementTime': notice_date,
                'adjunctUrl': url
            })
        return announcements
    except Exception as e:
        print(f'  东财查询失败: {e}')
        return []


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def is_new_announcement(pure_code, announce_id):
    """检查是否为新公告"""
    state = load_state()
    key = f'{pure_code}_{announce_id}'
    return key not in state

def mark_processed(pure_code, announce_id):
    state = load_state()
    key = f'{pure_code}_{announce_id}'
    state[key] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_state(state)


def fetch_eastmoney_content(art_code):
    """从东方财富公告详情页抓取公告正文"""
    host = 'data.eastmoney.com'
    path = f'/notices/detail/{art_code}.html'
    try:
        ctx = ssl.create_default_context()
        sock = socket.create_connection((host, 443), timeout=15)
        ssock = ctx.wrap_socket(sock, server_hostname=host)
        hdrs = f'GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\nAccept: text/html\r\nConnection: close\r\n\r\n'
        ssock.sendall(hdrs.encode())
        resp = b''
        while True:
            c = ssock.read(8192)
            if not c: break
            resp += c
        ssock.close()
        he = resp.find(b'\r\n\r\n')
        body = resp[he+4:]
        hstr = resp[:he].decode('iso-8859-1')
        if 'chunked' in hstr.lower():
            p, bd = 0, b''
            while p < len(body):
                e = body.find(b'\r\n', p)
                if e < 0: break
                sz = int(body[p:e], 16)
                if sz == 0: break
                bd += body[e+2:e+2+sz]
                p = e+2+sz+2
            body = bd
        # 尝试GBK解码HTML
        for enc in ['gbk', 'gb2312', 'utf-8']:
            try:
                html = body.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            html = body.decode('utf-8', errors='replace')
        # 提取公告正文：查找包含公告内容的div
        import re
        # 常见模式：detail-body, noticeContent, content-body
        patterns = [
            r'<div[^>]*class="[^"]*detail-body[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="noticeContent"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*content-body[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
            if m:
                text = re.sub(r'<[^>]+>', '', m.group(1))
                text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                return text[:30000]
        return ''
    except Exception as e:
        print(f'    内容抓取失败: {e}')
        return ''


def download_pdf(url, save_path):
    """用纯 socket 下载 PDF，支持相对URL和绝对URL"""
    if url.startswith('http'):
        # 绝对URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.netloc
        url_path = parsed.path + ('?' + parsed.query if parsed.query else '')
    else:
        # CNINFO相对URL
        host = 'www.cninfo.com.cn'
        url_path = '/' + url if not url.startswith('/') else url
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = f'GET {url_path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\nReferer: http://{host}/\r\nConnection: close\r\n\r\n'
    ssock.sendall(hdrs.encode())
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c: break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    body = resp[he+4:]
    # 处理 chunked
    hstr = resp[:he].decode('iso-8859-1')
    if 'chunked' in hstr.lower():
        p, bd = 0, b''
        while p < len(body):
            e = body.find(b'\r\n', p)
            if e < 0: break
            sz = int(body[p:e], 16)
            if sz == 0: break
            bd += body[e+2:e+2+sz]
            p = e+2+sz+2
        body = bd
    # 验证 PDF header
    if body[:4] != b'%PDF':
        return None
    with open(save_path, 'wb') as f:
        f.write(body)
    return save_path

def pdf_to_text(pdf_path):
    """用 pdfplumber 提取文本"""
    import pdfplumber
    text = ''
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + '\n'
    return text[:30000]  # 最多3万字，超长截断


def fetch_stocks_from_bitable(base_token, table_id):
    """从飞书多维表格读取股票列表
    返回: [{name, code, record_id}, ...]
    code 格式: 'sz002703' / 'sh688234'
    """
    from announcement_to_bitable import https_request
    token = get_user_token()
    _, data = https_request('GET', 'open.feishu.cn',
        f'/open-apis/base/v3/bases/{base_token}/tables/{table_id}/records?page_size=50',
        token=token)
    d = data.get('data', {})
    record_ids = d.get('record_id_list', [])
    field_names = d.get('fields', [])
    records_data = d.get('data', [])
    try:
        name_pos = field_names.index('股票名称')
        code_pos = field_names.index('股票代码')
    except ValueError:
        print('找不到股票名称/股票代码字段')
        return []
    result = []
    for i, rid in enumerate(record_ids):
        if i >= len(records_data): break
        row = records_data[i]
        name = row[name_pos] if name_pos < len(row) and row[name_pos] else ''
        code = row[code_pos] if code_pos < len(row) and row[code_pos] else ''
        if name and code:
            result.append({'record_id': rid, 'name': name, 'code': code})
    return result


def fetch_announcements(stocks):
    """对所有股票采集新公告
    stocks: [{name, code, record_id}, ...]
    返回: {stock_name: [{title, date, text, announce_id, code}, ...]}
    """
    all_new = {}
    for stock in stocks:
        name = stock['name']
        code = stock['code']  # sz002703
        pure_code = code[2:]  # 002703
        exchange = code[:2]  # sz
        rid = stock['record_id']

        print(f'\n处理: {name} ({code})')

        # 1. 东财查询（主数据源）
        em_anns = fetch_eastmoney_announcements(code)
        print(f'  东财返回 {len(em_anns)} 条公告')
        cninfo_anns = em_anns

        # 2. 如果东财为空，回退到巨潮
        if not cninfo_anns:
            all_cninfo = fetch_cninfo_announcements(pure_code, exchange)
            cninfo_anns = [a for a in all_cninfo if a.get('secCode', '') == pure_code]
            print(f'  巨潮返回 {len(all_cninfo)} 条，过滤后 {len(cninfo_anns)} 条({pure_code})')

        # 3. 过滤已处理的公告
        new_anns = []
        for ann in cninfo_anns:
            ann_id = ann.get('announcementId', '')
            if not ann_id:
                continue
            if is_new_announcement(pure_code, ann_id):
                new_anns.append(ann)

        if not new_anns:
            print(f'  无新公告')
            continue

        # 4. 限制每轮最多5条
        new_anns = new_anns[:5]
        print(f'  处理 {len(new_anns)} 条新公告')

        # 5. 下载PDF并提取文本
        results = []
        temp_dir = os.path.join(os.path.dirname(__file__), 'data', 'announcements')
        os.makedirs(temp_dir, exist_ok=True)

        for ann in new_anns:
            ann_id = ann.get('announcementId', '')
            title = ann.get('announcementTitle', '')
            ann_time = ann.get('announcementTime', '')[:10]
            pdf_url = ann.get('adjunctUrl', '')

            text = ''
            # 优先尝试下载PDF
            if pdf_url and pdf_url.endswith('.PDF'):
                pdf_path = os.path.join(temp_dir, f'{pure_code}_{ann_id}.pdf')
                try:
                    downloaded = download_pdf(pdf_url, pdf_path)
                    if downloaded:
                        text = pdf_to_text(pdf_path)
                        os.remove(pdf_path)  # 清理临时文件
                        print(f'    [{ann_time}] {title[:40]} -> {len(text)}字（PDF）')
                        mark_processed(pure_code, ann_id)
                    else:
                        print(f'    [{ann_time}] {title[:40]} -> PDF下载失败（未标记，下次重试）')
                except Exception as e:
                    print(f'    [{ann_time}] {title[:40]} -> PDF解析失败（未标记，下次重试）: {e}')

            if not text:
                # 用标题作为基础文本，供AI分析
                text = f'公告标题：{title}\n日期：{ann_time}\n（正文暂未获取，基于标题分析）'
                print(f'    [{ann_time}] {title[:40]} -> 标题模式')
                mark_processed(pure_code, ann_id)

            results.append({
                'title': title,
                'date': ann_time,
                'text': text,
                'announce_id': ann_id,
                'code': code,
            })

        if results:
            all_new[name] = results

    return all_new

if __name__ == '__main__':
    # 测试用
    stocks = [{'name': '浙江世宝', 'code': 'sz002703', 'record_id': 'test'}]
    results = fetch_announcements(stocks)
    print(f'\n总结果: {json.dumps({k: len(v) for k, v in results.items()}, ensure_ascii=False)}')
