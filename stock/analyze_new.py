"""分析新爬的5只股票评论 - SiliconFlow Qwen3-32B"""
import json, ssl, socket, time, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API_KEY = 'sk-lsnhfgotvsmsndxsonigqhvpdmbtajviumyobxonrbigsyhh'
COMMENTS_FILE = 'J:/zss/stock/full_comments.json'
ANALYSIS_FILE = 'J:/zss/stock/analysis_results.json'

# Stocks to analyze (new ones only)
NEW_STOCKS = ['引力传媒', '博纳影业', '多氟多', '巨轮智能', '方正电机']

def qwen_chat(messages, max_tokens=2000):
    body = json.dumps({'model': 'Qwen/Qwen3-32B', 'messages': messages, 'max_tokens': max_tokens, 'temperature': 0.3})
    ctx = ssl.create_default_context()
    sock = socket.create_connection(('api.siliconflow.cn', 443), timeout=60)
    ssock = ctx.wrap_socket(sock, server_hostname='api.siliconflow.cn')
    hdrs = 'POST /v1/chat/completions HTTP/1.1\r\nHost: api.siliconflow.cn\r\n'
    hdrs += 'Authorization: Bearer {}\r\nContent-Type: application/json\r\n'.format(API_KEY)
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

def analyze_stock(name, posts):
    print('\n=== {}: {} posts, {} comments ==='.format(name, len(posts), sum(len(p['cmts']) for p in posts)))

    all_analyzed = []
    for i, post in enumerate(posts):
        if not post['cmts']: continue
        cmt_texts = []
        for j, c in enumerate(post['cmts']):
            cmt_texts.append('[{}.{}] {}'.format(i+1, j+1, c['c'][:300]))
        batch = '\n'.join(cmt_texts)
        prompt = """分析股吧评论，标注类型和重要性。
类型：[有价值]/[情绪发泄]/[无意义灌水]/[庄托水军]
重要性：[高]/[中]/[低]

帖子：{}

评论：
{}

格式：每条一行：[序号] [类型] [重要性] | 简要说明""".format(post.get('title','无标题')[:80], batch)
        try:
            result = qwen_chat([{'role': 'user', 'content': prompt}], 800)
            analyzed = [l.strip() for l in result.split('\n') if l.strip() and '[' in l]
            all_analyzed.append({'post_id': post['id'], 'title': post['title'][:60], 'analysis': analyzed})
            if (i+1) % 5 == 0: print('  {}/{} done'.format(i+1, len(posts)), flush=True)
        except Exception as e:
            all_analyzed.append({'post_id': post['id'], 'title': post['title'][:60], 'analysis': ['[分析失败]']})
            print('  ERROR at {}: {}'.format(i+1, e), flush=True)
        time.sleep(0.3)

    # Stats
    stats = {'有价值': 0, '情绪发泄': 0, '无意义灌水': 0, '庄托水军': 0, '高重要性': 0}
    for a in all_analyzed:
        for line in a['analysis']:
            for k in ['有价值', '情绪发泄', '无意义灌水', '庄托水军']:
                if '[' + k + ']' in line: stats[k] += 1
            if '[高]' in line: stats['高重要性'] += 1

    # Summary
    summary_prompt = """{}股吧分析统计：总{}条, 有价值{}, 情绪{}, 灌水{}, 庄托{}.
生成200字总结：格式：【今日评论总结-{}】市场情绪：/关键讨论：/风险提示：/建议关注：""".format(
        name, sum(stats.values()), stats['有价值'], stats['情绪发泄'], stats['无意义灌水'], stats['庄托水军'], name)
    try:
        summary = qwen_chat([{'role': 'user', 'content': summary_prompt}], 300)
    except:
        summary = '【今日评论总结-{}】\n分析生成失败'.format(name)

    return {'stats': stats, 'details': all_analyzed, 'summary': summary}

# Load data
with open(COMMENTS_FILE, encoding='utf-8') as f:
    all_data = json.load(f)

# Load existing analysis
results = {}
if os.path.exists(ANALYSIS_FILE):
    with open(ANALYSIS_FILE, encoding='utf-8') as f:
        results = json.load(f)

# Analyze new stocks
for name in NEW_STOCKS:
    if name not in all_data or not all_data[name]: continue
    if name in results:
        print('{}: already analyzed, skip'.format(name))
        continue
    results[name] = analyze_stock(name, all_data[name])
    # Save incrementally
    with open(ANALYSIS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    time.sleep(1)

print('\n=== Analysis complete ===')
for name, r in results.items():
    s = r.get('stats', {})
    total = sum(s.values()) or 1
    print('{}: {}cmt valid={}({}%)'.format(name, sum(s.values()), s.get('有价值',0), s.get('有价值',0)*100//total))
