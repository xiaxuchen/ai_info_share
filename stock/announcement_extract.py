#!/usr/bin/env python3
"""Qwen3-32B 公告信息提取模块 - 调用硅基流动 API，提取结构化摘要"""
import json, ssl, socket, time, sys, io

if sys.stdout.encoding != 'utf-8':
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


MAX_CHUNK_SIZE = 4000

def split_text(text, max_chars=MAX_CHUNK_SIZE):
    """将长文本按字符数分段"""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    for i in range(0, len(text), max_chars):
        chunks.append(text[i:i+max_chars])
    return chunks


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
