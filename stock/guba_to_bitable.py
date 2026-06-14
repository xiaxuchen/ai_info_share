#!/usr/bin/env python3
"""
股吧热帖抓取 - 集成到飞书多维表格
从东方财富股吧抓取股票的最新帖子，写入飞书多维表格

功能:
  1. 获取股吧帖子列表（标题、阅读量、评论数、日期、作者）
  2. 获取帖子正文内容
  3. 写入飞书多维表格的"股吧热帖"字段

使用:
  python guba_to_bitable.py <base_token> <table_id>
"""

import json, ssl, socket, os, sys, time, re
from datetime import datetime
from pathlib import Path

# ============================================================
# 工具函数
# ============================================================

TOKEN_FILE = os.path.expanduser("~/.feishu-cli/token.json")

def get_user_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)['access_token']

def decode_chunked(data):
    body = b''
    pos = 0
    while pos < len(data):
        end = data.find(b'\r\n', pos)
        if end < 0: break
        size = int(data[pos:end], 16)
        if size == 0: break
        chunk_start = end + 2
        body += data[chunk_start:chunk_start + size]
        pos = chunk_start + size + 2
    return body

def https_request(method, host, path, token=None, body=None, content_type="application/json", extra_headers=None):
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    headers = f"{method} {path} HTTP/1.1\r\nHost: {host}\r\n"
    if token:
        headers += f"Authorization: Bearer {token}\r\n"
    headers += f"Content-Type: {content_type}\r\n"
    if extra_headers:
        headers += extra_headers
    if body:
        headers += f"Content-Length: {len(body)}\r\n"
    headers += "Connection: close\r\n\r\n"
    ssock.sendall(headers.encode() + (body or b''))
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c: break
        resp += c
    ssock.close()
    header_end = resp.find(b'\r\n\r\n')
    raw_body = resp[header_end + 4:]
    if 'chunked' in resp[:header_end].decode('iso-8859-1').lower():
        raw_body = decode_chunked(raw_body)
    status_line = resp[:header_end].decode('iso-8859-1').split('\r\n')[0]
    return status_line, json.loads(raw_body.decode())

def guba_request(host, path):
    """请求股吧页面，返回原始字节"""
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=15)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = f'GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\nAccept: text/html,application/json\r\nConnection: close\r\n\r\n'
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


def extract_json(raw_bytes, var_name):
    """从HTML中提取 var xxx = {...} 这样的JSON"""
    idx = raw_bytes.find(var_name.encode() + b'=')
    if idx < 0:
        idx = raw_bytes.find(var_name.encode() + b' =')
    if idx < 0:
        return None
    start = raw_bytes.find(b'{', idx)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    end = start
    for i in range(start, len(raw_bytes)):
        b = raw_bytes[i]
        if escaped:
            escaped = False
            continue
        if b == 0x5c:
            escaped = True
            continue
        if b == 0x22:
            in_string = not in_string
            continue
        if in_string:
            continue
        if b == 0x7b:
            depth += 1
        elif b == 0x7d:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end <= start:
        return None
    try:
        return json.loads(raw_bytes[start:end].decode('utf-8'))
    except:
        return None


def strip_html(text):
    """去除HTML标签"""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    return text.strip()


# ============================================================
# 1. 股吧数据抓取
# ============================================================

def fetch_guba_posts(code, pages=3):
    """
    获取股吧帖子列表
    code: 纯数字代码，如 '002703'
    pages: 抓取页数
    返回帖子列表
    """
    all_posts = []
    for page in range(1, pages + 1):
        time.sleep(0.5)
        raw = guba_request('guba.eastmoney.com', f'/list,{code},f_{page}.html')
        data = extract_json(raw, 'article_list')
        if not data:
            print(f'  第{page}页解析失败')
            continue
        posts = data.get('re', [])
        for p in posts:
            all_posts.append({
                'post_id': p.get('post_id'),
                'post_title': p.get('post_title', ''),
                'post_click_count': p.get('post_click_count', 0),
                'post_comment_count': p.get('post_comment_count', 0),
                'post_publish_time': p.get('post_publish_time', ''),
                'post_user': p.get('post_user', {}).get('user_nickname', ''),
            })
        print(f'  第{page}页获取{len(posts)}条帖子')
    return all_posts


def fetch_post_content(code, post_id):
    """获取单个帖子的正文内容"""
    time.sleep(0.3)
    raw = guba_request('guba.eastmoney.com', f'/news,{code},{post_id}.html')
    data = extract_json(raw, 'post_article')
    if not data:
        return ''
    content_html = data.get('post_content', '')
    return strip_html(content_html)


# ============================================================
# 2. 飞书操作
# ============================================================

def get_existing_fields(base_token, table_id):
    token = get_user_token()
    _, data = https_request('GET', 'open.feishu.cn',
        f'/open-apis/base/v3/bases/{base_token}/tables/{table_id}/fields',
        token=token)
    fields = {}
    if isinstance(data, dict):
        for f in data.get('data', {}).get('fields', []):
            fields[f['name']] = f['id']
    return fields


def create_field(base_token, table_id, field_name, field_type='text'):
    token = get_user_token()
    body = json.dumps({'field_name': field_name, 'type': field_type})
    _, data = https_request('POST', 'open.feishu.cn',
        f'/open-apis/base/v3/bases/{base_token}/tables/{table_id}/fields',
        token=token, body=body.encode())
    if data.get('code') == 0:
        fid = data['data']['id']
        print(f'  创建字段 "{field_name}" -> {fid}')
        return fid
    # 可能已存在，重新获取匹配
    print(f'  字段 "{field_name}" 已存在或创建失败，尝试匹配')
    existing = get_existing_fields(base_token, table_id)
    if field_name in existing:
        return existing[field_name]
    return None


def ensure_fields(base_token, table_id, field_names):
    existing = get_existing_fields(base_token, table_id)
    result = {}
    for name, type_id in field_names.items():
        if name in existing:
            result[name] = existing[name]
        else:
            fid = create_field(base_token, table_id, name, type_id)
            if fid:
                result[name] = fid
    return result


def fetch_records(base_token, table_id):
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


def update_text_field(base_token, table_id, record_id, field_name, value):
    token = get_user_token()
    body = json.dumps({field_name: value}, ensure_ascii=False)
    _, result = https_request('PATCH', 'open.feishu.cn',
        f'/open-apis/base/v3/bases/{base_token}/tables/{table_id}/records/{record_id}',
        token=token, body=body.encode())
    return result.get('code') == 0


# ============================================================
# 3. 格式化输出
# ============================================================

def format_posts_summary(posts, stock_name, code, top_n=10):
    """将帖子列表格式化为文本摘要"""
    pure_code = code[2:]  # sz002703 -> 002703
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [f'【{stock_name}({code}) 股吧热帖】更新于 {now}', '']

    # 取前top_n个帖子，优先显示有回复的
    with_comments = [p for p in posts if p['post_comment_count'] > 0]
    without_comments = [p for p in posts if p['post_comment_count'] == 0]
    sorted_posts = with_comments + without_comments

    for i, p in enumerate(sorted_posts[:top_n]):
        title = p['post_title'][:60]
        click = p['post_click_count']
        comments = p['post_comment_count']
        ptime = p['post_publish_time'][:10] if p['post_publish_time'] else ''
        user = p['post_user'][:10] if p['post_user'] else '匿名'

        lines.append(f'{i+1}. [{ptime}] {title}')
        lines.append(f'   阅读{click} 评论{comments} @{user}')

        # 获取帖子正文（前200字）
        post_id = p['post_id']
        if post_id and (i < 5 or comments > 0):  # 前5个或有评论的才取正文
            try:
                content = fetch_post_content(pure_code, post_id)
                if content:
                    lines.append(f'   {content[:200]}')
            except:
                pass
        lines.append('')

    # 统计概要
    total_posts = len(posts)
    total_comments = sum(p['post_comment_count'] for p in posts)
    avg_click = sum(p['post_click_count'] for p in posts) / max(total_posts, 1)
    lines.append(f'> 近{total_posts}条帖子 共{total_comments}条评论 均阅{avg_click:.0f}')

    return '\n'.join(lines)


# ============================================================
# 主流程
# ============================================================

def main(base_token, table_id, pages=2):
    user_token = get_user_token()
    print(f'Token获取成功 ({len(user_token)} chars)')

    # 确保字段存在
    required_fields = {
        '股吧热帖': 'text',
    }
    fields = ensure_fields(base_token, table_id, required_fields)
    if '股吧热帖' not in fields:
        print('股吧热帖字段创建失败，退出')
        return

    # 读取股票记录
    records = fetch_records(base_token, table_id)
    if not records:
        print('未找到有股票代码的记录')
        return
    print(f'读取到 {len(records)} 条记录\n')

    for rec in records:
        name = rec['name']
        code = rec['code']
        rid = rec['record_id']

        # 转换代码格式: sh688234 -> 688234
        pure_code = code[2:] if len(code) > 2 else code
        print(f'处理: {name} ({code}) -> guba code {pure_code}')

        try:
            # 抓取帖子
            posts = fetch_guba_posts(pure_code, pages)
            if not posts:
                print(f'  未获取到帖子')
                continue

            # 格式化
            summary = format_posts_summary(posts, name, code)
            print(f'  共{len(posts)}条帖子，生成摘要{len(summary)}字')

            # 写入飞书
            if update_text_field(base_token, table_id, rid, '股吧热帖', summary):
                print(f'  写入成功')
            else:
                print(f'  写入失败')

        except Exception as e:
            print(f'  错误: {e}')

    print(f'\n完成!')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    base_token = sys.argv[1]
    table_id = sys.argv[2]
    pages = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    main(base_token, table_id, pages)
