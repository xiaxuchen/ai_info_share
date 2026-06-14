# 公告采集与 AI 分析 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为股票多维表格新增公告采集、Qwen3-32B 提取、Claude 深度分析、飞书写入的完整流程

**Architecture:** 4 个 Python 模块 + 1 个主控脚本，纯 socket HTTP，复用现有 API key 和 bitable 模式。巨潮(主) + 东财(辅)获取公告 PDF → pdfplumber 转文本 → Qwen3-32B 提取结构化摘要 → Claude 生成投资者分析 → 写入飞书多维表格

**Tech Stack:** Python 3, socket/ssl (纯原生 HTTP), pdfplumber, 硅基流动 Qwen3-32B API, 飞书 Bitable API

---

## 文件结构

```
J:\zss\stock\
  announcement_fetch.py          # 新建 - 模块1: 公告采集+PDF转文本
  announcement_extract.py        # 新建 - 模块2: Qwen3-32B 信息提取
  announcement_to_bitable.py     # 新建 - 模块4: 写入飞书多维表格
  announcement_analyze.py        # 新建 - 主控: 串联全流程
  announcement_state.json        # 新建 - 运行时状态: 已处理公告ID
  requirements.txt               # 新建 - 项目依赖(含pdfplumber)
```

**修改的现有文件:** 无（全部新建，不修改已有文件）

**复用参考:**
- `guba_to_bitable.py` — bitable API 模式 (get_user_token, ensure_fields, update_text_field, fetch_records)
- `analyze_comments.py` — 硅基流动 Qwen3-32B API 调用模式
- `write_comments_to_bitable.py` — BASE_TOKEN / TABLE_ID 硬编码模式

---

### Task 1: 项目基础设施 — requirements.txt

**Files:**
- Create: `J:\zss\stock\requirements.txt`

- [ ] **Step 1: 创建 requirements.txt**

```python
# requirements.txt - 项目依赖
bitable-sdk
pdfplumber
pandas
```

- [ ] **Step 2: 安装 pdfplumber**

```bash
pip install pdfplumber
```

- [ ] **Step 3: 验证安装**

```bash
python -c "import pdfplumber; print('pdfplumber OK')"
```

期望输出: `pdfplumber OK`

---

### Task 2: 模块 1 — announcement_fetch.py（公告采集 + PDF 转文本）

**Files:**
- Create: `J:\zss\stock\announcement_fetch.py`

- [ ] **Step 1: 写文件骨架和配置**

```python
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
```

- [ ] **Step 2: 实现纯 socket HTTPS POST 请求函数**

参考 `guba_to_bitable.py` 的 `https_request` 模式，新增 POST method 支持：

```python
def https_post(host, path, token=None, body=None):
    """纯 socket HTTPS POST 请求"""
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    b = body.encode() if isinstance(body, str) else (body or b'')
    hdrs = f'POST {path} HTTP/1.1\r\nHost: {host}\r\n'
    if token:
        hdrs += f'Authorization: Bearer {token}\r\n'
    hdrs += 'Content-Type: application/json\r\n'
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
```

- [ ] **Step 3: 实现巨潮公告列表查询**

```python
def fetch_cninfo_announcements(code, exchange, days=ANNOUNCEMENT_LOOKBACK_DAYS):
    """从巨潮获取公告列表
    code: 6位纯数字, 如 '002703'
    exchange: 'sz' 或 'sh'
    返回: [{announcementId, announcementTitle, announcementTime, adjunctUrl}, ...]
    """
    # CNINFO stock参数格式: "sz002703,sse" 或 "sh688234,sse"
    stock_param = f'{exchange}{code},sse'
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    body = json.dumps({
        'stock': stock_param,
        'pageNum': 1,
        'pageSize': CNINFO_PAGE_SIZE,
        'seDate': f'{start_date}~{end_date}'
    })
    try:
        data = https_post('www.cninfo.com.cn', '/new/hisAnnouncement/query', body=body)
        return data.get('announcements', []) if isinstance(data, dict) else []
    except Exception as e:
        print(f'  巨潮查询失败: {e}')
        return []
```

- [ ] **Step 4: 实现东方财富公告查询（fallback）**

```python
def fetch_eastmoney_announcements(code, days=ANNOUNCEMENT_LOOKBACK_DAYS):
    """从东方财富获取公告列表（巨潮 fallback）"""
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    # 东财使用带前缀的代码格式
    path = f'/api/security/ann?stock_list={code}&page_size=30&page_index=1'
    try:
        data = https_get('np-anotice-stock.eastmoney.com', path)
        # 东财返回格式不同，需映射
        announcements = []
        for item in data.get('data', {}).get('list', []):
            announcements.append({
                'announcementId': str(item.get('art_code', '')),
                'announcementTitle': item.get('title', ''),
                'announcementTime': item.get('notice_date', ''),
                'adjunctUrl': item.get('url', '')
            })
        return announcements
    except Exception as e:
        print(f'  东财查询失败: {e}')
        return []
```

- [ ] **Step 5: 实现去重和状态管理**

```python
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
```

- [ ] **Step 6: 实现 PDF 下载和文本提取**

```python
def download_pdf(url, save_path):
    """用纯 socket 下载 PDF"""
    host = 'www.cninfo.com.cn'
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = f'GET {url} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n'
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
```

- [ ] **Step 7: 实现东财 https_get（供 fallback 用）**

```python
def https_get(host, path):
    """纯 socket HTTPS GET 请求（东财公告接口用）"""
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
    return json.loads(raw.decode())
```

- [ ] **Step 8: 实现 fetch_stocks_from_bitable（从飞书读取股票列表）**

```python
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
```

- [ ] **Step 9: 实现主函数 fetch_announcements**

```python
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

        # 1. 巨潮查询
        cninfo_anns = fetch_cninfo_announcements(pure_code, exchange)
        print(f'  巨潮返回 {len(cninfo_anns)} 条公告')

        # 2. 如果巨潮为空，回退到东财
        if not cninfo_anns:
            print(f'  回退到东财...')
            em_anns = fetch_eastmoney_announcements(code)
            print(f'  东财返回 {len(em_anns)} 条公告')
            cninfo_anns = em_anns

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
            if pdf_url:
                pdf_path = os.path.join(temp_dir, f'{pure_code}_{ann_id}.pdf')
                try:
                    downloaded = download_pdf(pdf_url, pdf_path)
                    if downloaded:
                        text = pdf_to_text(pdf_path)
                        os.remove(pdf_path)  # 清理临时文件
                        print(f'    [{ann_time}] {title[:40]} -> {len(text)}字')
                        # 只在成功提取文本后才标记已处理
                        mark_processed(pure_code, ann_id)
                    else:
                        print(f'    [{ann_time}] {title[:40]} -> PDF下载失败（未标记，下次重试）')
                except Exception as e:
                    print(f'    [{ann_time}] {title[:40]} -> PDF解析失败（未标记，下次重试）: {e}')
            else:
                print(f'    [{ann_time}] {title[:40]} -> 无PDF链接')
                # 无PDF的公告只记标题，也标记已处理避免重复
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
```

- [ ] **Step 10: 验证模块 1 导入无语法错误**

```bash
python -c "import ast; ast.parse(open('J:/zss/stock/announcement_fetch.py').read()); print('Syntax OK')"
```

---

### Task 3: 模块 2 — announcement_extract.py（Qwen3-32B 信息提取）

**Files:**
- Create: `J:\zss\stock\announcement_extract.py`

- [ ] **Step 1: 写文件骨架和 Qwen API 调用**

```python
#!/usr/bin/env python3
"""Qwen3-32B 公告信息提取模块 - 调用硅基流动 API，提取结构化摘要"""
import json, ssl, socket, time, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API_KEY = 'sk-lsnhfgotvsmsndxsonigqhvpdmbtajviumyobxonrbigsyhh'

def qwen_chat(messages, max_tokens=1500):
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
    hdrs += f'Authorization: Bearer {API_KEY}\r\n'
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
    return json.loads(raw.decode()).get('choices', [{}])[0].get('message', {}).get('content', '')
```

- [ ] **Step 2: 实现长文本分段**

```python
MAX_CHUNK_SIZE = 4000

def split_text(text, max_chars=MAX_CHUNK_SIZE):
    """将长文本按字符数分段"""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    for i in range(0, len(text), max_chars):
        chunks.append(text[i:i+max_chars])
    return chunks
```

- [ ] **Step 3: 实现单段提取 prompt**

```python
def extract_chunk(chunk_text, stock_name, title):
    """提取单段关键信息"""
    prompt = f"""你是一个股票公告分析师。请从以下公告文本中提取关键信息，输出严格JSON格式：

公告标题：{title}
公司：{stock_name}

公告文本（节选）：
{chunk_text}

请提取以下字段（若无则为空字符串）：
- 核心要点：1-2句话概括
- 财务数据：营收、利润、同比变化等数字
- 重大事项：合同、重组、增减持等
- 风险因素
- 对股价影响：利好/利空/中性
- 影响程度：高/中/低

严格输出JSON，不要输出其他内容：
{{"核心要点":"...","财务数据":"...","重大事项":"...","风险因素":"...","对股价影响":"...","影响程度":"..."}}"""
    
    result = qwen_chat([{'role': 'user', 'content': prompt}], 600)
    return result
```

- [ ] **Step 4: 实现多段汇总**

```python
def merge_chunks(chunk_results, stock_name, title):
    """汇总多段提取结果"""
    summaries = '\n'.join([f'[段{i+1}] {r}' for i, r in enumerate(chunk_results)])
    prompt = f"""汇总以下多段公告分析结果，输出一个合并后的JSON：

公告标题：{title}
公司：{stock_name}

各段提取结果：
{summaries}

合并所有信息，输出一个JSON（不要输出其他内容）：
{{"核心要点":"...","财务数据":"...","重大事项":"...","风险因素":"...","对股价影响":"...","影响程度":"..."}}"""
    
    result = qwen_chat([{'role': 'user', 'content': prompt}], 800)
    return result
```

- [ ] **Step 5: 实现主提取函数**

```python
def extract_announcement(announcement, stock_name):
    """对一条公告进行完整提取
    announcement: {title, date, text, announce_id, code}
    stock_name: 股票名称（从外层传入，避免从标题拆分）
    返回: {title, date, announce_id, extracted_json, summary_text}
    """
    title = announcement.get('title', '')
    text = announcement.get('text', '')
    
    if not text or len(text) < 50:
        # 文本太短，直接跳过（降级到只用标题）
        return {
            'title': title,
            'date': announcement.get('date', ''),
            'announce_id': announcement.get('announce_id', ''),
            'extracted_json': {'核心要点': f'公告：{title}', '财务数据': '', '重大事项': '', '风险因素': '', '对股价影响': '中性', '影响程度': '低'},
            'summary_text': f'公告：{title}（文本内容为空或过短）'
        }
    
    chunks = split_text(text)
    print(f'    分段: {len(chunks)} 段, 总{len(text)}字', end='', flush=True)
    
    if len(chunks) == 1:
        raw = extract_chunk(chunks[0], stock_name, title)
    else:
        chunk_results = []
        for i, chunk in enumerate(chunks):
            print(f' 段{i+1}', end='', flush=True)
            try:
                r = extract_chunk(chunk, stock_name, title)
                chunk_results.append(r)
                time.sleep(0.3)
            except Exception as e:
                chunk_results.append(f'{{"错误":"{e}"}}')
        raw = merge_chunks(chunk_results, stock_name, title)
    
    # 解析 JSON
    try:
        extracted = json.loads(raw)
    except:
        # 尝试从响应中提取JSON
        import re
        m = re.search(r'\{[^{}]*\}', raw.replace('\n', ' '))
        if m:
            try:
                extracted = json.loads(m.group())
            except:
                extracted = {'核心要点': raw[:200], '财务数据': '', '重大事项': '', '风险因素': '', '对股价影响': '中性', '影响程度': '低'}
        else:
            extracted = {'核心要点': raw[:200], '财务数据': '', '重大事项': '', '风险因素': '', '对股价影响': '中性', '影响程度': '低'}
    
    # 生成500字以内摘要文本（供 Claude 消费）
    summary_text = f"""【{title}】{extracted.get('核心要点', '')}
财务：{extracted.get('财务数据', '无')}
事项：{extracted.get('重大事项', '无')}
风险：{extracted.get('风险因素', '无')}
判断：{extracted.get('对股价影响', '中性')} | {extracted.get('影响程度', '低')}"""
    summary_text = summary_text[:500]
    
    return {
        'title': title,
        'date': announcement.get('date', ''),
        'announce_id': announcement.get('announce_id', ''),
        'extracted_json': extracted,
        'summary_text': summary_text
    }


def extract_all(new_announcements):
    """对所有新公告进行提取
    new_announcements: {stock_name: [{title, date, text, announce_id, code}, ...]}
    返回: {stock_name: [{title, date, announce_id, extracted_json, summary_text}, ...]}
    """
    all_results = {}
    total = sum(len(v) for v in new_announcements.values())
    done = 0
    for stock_name, anns in new_announcements.items():
        print(f'\n=== Qwen提取: {stock_name} ({len(anns)}条) ===')
        results = []
        for ann in anns:
            done += 1
            print(f'  [{done}/{total}] {ann["title"][:50]}', end='', flush=True)
            for attempt in range(3):
                try:
                    result = extract_announcement(ann, stock_name)
                    results.append(result)
                    print(f' OK', flush=True)
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f' 重试{attempt+1}', end='', flush=True)
                        time.sleep(2)
                    else:
                        print(f' FAIL:{e}', flush=True)
                        results.append({
                            'title': ann['title'],
                            'date': ann['date'],
                            'announce_id': ann['announce_id'],
                            'extracted_json': {},
                            'summary_text': f'提取失败: {e}'
                        })
            time.sleep(0.5)
        all_results[stock_name] = results
    return all_results


if __name__ == '__main__':
    # 测试
    test_anns = {
        '测试股': [{
            'title': '2025年度报告摘要',
            'date': '2026-05-20',
            'text': '公司2025年实现营业收入50亿元，同比增长15%；净利润5亿元，同比增长20%。',
            'announce_id': 'test001',
            'code': 'sz002703'
        }]
    }
    results = extract_all(test_anns)
    print(json.dumps(results, ensure_ascii=False, indent=2))
```

- [ ] **Step 6: 验证模块 2 语法**

```bash
python -c "import ast; ast.parse(open('J:/zss/stock/announcement_extract.py').read()); print('Syntax OK')"
```

---

### Task 4: 模块 4 — announcement_to_bitable.py（写入飞书多维表格）

**Files:**
- Create: `J:\zss\stock\announcement_to_bitable.py`

- [ ] **Step 1: 写完整文件**

```python
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
        print('字段创建/查找失败')
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
```

- [ ] **Step 2: 验证模块 4 语法**

```bash
python -c "import ast; ast.parse(open('J:/zss/stock/announcement_to_bitable.py').read()); print('Syntax OK')"
```

---

### Task 5: 主控脚本 — announcement_analyze.py

**Files:**
- Create: `J:\zss\stock\announcement_analyze.py`

- [ ] **Step 1: 写主控脚本**

```python
#!/usr/bin/env python3
"""
公告分析主控脚本
流程: 采集公告 → Qwen3-32B 提取 → Claude 深度分析 → 写入飞书

使用: python announcement_analyze.py [base_token] [table_id]
"""
import json, os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 导入其他模块
from announcement_fetch import fetch_stocks_from_bitable, fetch_announcements
from announcement_extract import extract_all
from announcement_to_bitable import write_analysis

# 硬编码的 BASE_TOKEN 和 TABLE_ID（和 write_comments_to_bitable.py 一致）
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE_ID = 'tbl2A9imBZgM7vLl'

# Claude 分析结果输出文件
ANALYSIS_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'announcement_analysis_output.json')


def save_extracted_for_claude(extracted_results):
    """保存 Qwen3-32B 提取结果，供 Claude 分析使用"""
    with open(ANALYSIS_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(extracted_results, f, ensure_ascii=False, indent=2)
    print(f'\nQwen提取结果已保存到: {ANALYSIS_OUTPUT}')
    print('请主 agent 读取此文件进行 Claude 深度分析。')


def load_claude_analysis():
    """加载 Claude 分析结果"""
    if os.path.exists(ANALYSIS_OUTPUT):
        with open(ANALYSIS_OUTPUT, encoding='utf-8') as f:
            data = json.load(f)
        # 检查是否已有 claude_analysis 字段
        return data
    return None


def generate_announcement_list(extracted_results):
    """生成公告列表摘要文本"""
    lines = []
    for stock_name, anns in extracted_results.items():
        lines.append(f'【{stock_name}】')
        for ann in anns:
            lines.append(f'  - {ann["date"]} {ann["title"][:60]}')
        lines.append('')
    return '\n'.join(lines)


def main():
    # 解析参数
    base_token = sys.argv[1] if len(sys.argv) > 1 else BASE_TOKEN
    table_id = sys.argv[2] if len(sys.argv) > 2 else STOCK_TABLE_ID
    
    print('=== 公告分析系统 ===')
    print(f'BASE_TOKEN: {base_token}')
    print(f'TABLE_ID: {table_id}')
    
    # Step 1: 从飞书读取股票列表
    print('\n--- Step 1: 读取股票列表 ---')
    stocks = fetch_stocks_from_bitable(base_token, table_id)
    print(f'读取到 {len(stocks)} 只股票')
    
    if not stocks:
        print('无股票数据，退出')
        return
    
    # Step 2: 采集新公告
    print('\n--- Step 2: 采集公告 ---')
    new_announcements = fetch_announcements(stocks)
    
    if not new_announcements:
        print('无新公告，退出')
        return
    
    total_anns = sum(len(v) for v in new_announcements.values())
    print(f'\n共发现 {total_anns} 条新公告')
    
    # Step 3: Qwen3-32B 提取
    print('\n--- Step 3: Qwen3-32B 信息提取 ---')
    extracted = extract_all(new_announcements)
    
    # Step 4: 保存提取结果，等待 Claude 分析
    print('\n--- Step 4: 保存提取结果 ---')
    
    # 构建 Claude 分析输入
    claude_input = {}
    for stock_name, anns in extracted.items():
        summaries = []
        for ann in anns:
            summaries.append({
                'title': ann['title'],
                'date': ann['date'],
                'summary': ann['summary_text']
            })
        claude_input[stock_name] = {
            'announcements': summaries,
            'claude_analysis': ''  # 待 Claude 填充
        }
    
    save_extracted_for_claude(claude_input)
    
    # Step 5: 提示 Claude 分析
    print('\n--- Step 5: Claude 深度分析 ---')
    print(f'请 Claude agent 读取 {ANALYSIS_OUTPUT}')
    print('对每只股票的公告进行深度分析，填充 claude_analysis 字段')
    print('完成后重新运行本脚本加 --write 参数')
    
    # 打印摘要供 Claude 直接使用
    print('\n' + '='*60)
    for stock_name, data in claude_input.items():
        print(f'\n### {stock_name}')
        for ann in data['announcements']:
            print(f"\n--- {ann['date']} {ann['title'][:60]}")
            print(ann['summary'])
    print('\n' + '='*60)


def write_mode():
    """--write 模式：加载 Claude 分析结果，写入飞书"""
    data = load_claude_analysis()
    if not data:
        print('未找到分析文件，请先运行主流程')
        return
    
    # 构建写入数据
    stock_analyses = {}
    missing_analysis = []
    for stock_name, info in data.items():
        announcement_list = '\n'.join([
            f"{ann['date']} {ann['title'][:80]}"
            for ann in info.get('announcements', [])
        ])
        analysis = info.get('claude_analysis', '').strip()
        if not analysis:
            missing_analysis.append(stock_name)
            print(f'  WARNING: {stock_name} 缺少 claude_analysis，仅写入公告列表')
            analysis = ''  # 留空而非填充占位符
        
        stock_analyses[stock_name] = {
            'announcement_list': announcement_list,
            'analysis': analysis
        }
    
    if missing_analysis:
        print(f'\n  {len(missing_analysis)} 只股票缺少Claude分析: {missing_analysis}')
        print('  已跳过分析字段写入，仅写入公告列表')
    
    print(f'\n准备写入 {len(stock_analyses)} 只股票的分析结果')
    write_analysis(stock_analyses)
    print('写入完成')


if __name__ == '__main__':
    if '--write' in sys.argv:
        write_mode()
    else:
        main()
```

- [ ] **Step 2: 验证主控脚本语法**

```bash
python -c "import ast; ast.parse(open('J:/zss/stock/announcement_analyze.py').read()); print('Syntax OK')"
```

---

### Task 6: 集成验证

- [ ] **Step 1: 检查所有文件语法**

```bash
cd J:/zss/stock && python -c "
import ast
for f in ['announcement_fetch.py', 'announcement_extract.py', 'announcement_to_bitable.py', 'announcement_analyze.py']:
    with open(f) as fh:
        ast.parse(fh.read())
    print(f'{f}: OK')
"
```

期望输出: 4 个文件的 `OK`

- [ ] **Step 2: 测试模块独立导入**

```bash
cd J:/zss/stock && python -c "
from announcement_fetch import load_state, save_state, is_new_announcement, mark_processed
print('Module 1: import OK')
from announcement_extract import split_text, extract_all
print('Module 2: import OK')
"
```

- [ ] **Step 3: 测试去重逻辑**

```bash
cd J:/zss/stock && python -c "
from announcement_fetch import is_new_announcement, mark_processed
# 清理测试
import os
sf = 'announcement_state.json'
if os.path.exists(sf): os.remove(sf)

assert is_new_announcement('002703', 'test001') == True
mark_processed('002703', 'test001')
assert is_new_announcement('002703', 'test001') == False
assert is_new_announcement('002703', 'test002') == True
print('去重逻辑: PASS')
"
```

- [ ] **Step 4: 测试分段逻辑**

```bash
cd J:/zss/stock && python -c "
from announcement_extract import split_text
assert len(split_text('abc')) == 1
assert len(split_text('a' * 5000)) == 2
print('分段逻辑: PASS')
"
```

---

## 执行流程

### 日常运行流程

```
1. python announcement_analyze.py          # 采集 + Qwen提取
2. Claude 读取 announcement_analysis_output.json，深度分析每只股票
3. Claude 编辑 announcement_analysis_output.json，填充 claude_analysis 字段
4. python announcement_analyze.py --write  # 写入飞书
```

### 模块依赖图

```
announcement_analyze.py (主控)
  ├── announcement_fetch.py      (导入: fetch_stocks_from_bitable, fetch_announcements)
  ├── announcement_extract.py    (导入: extract_all)
  └── announcement_to_bitable.py (导入: write_analysis)
```
