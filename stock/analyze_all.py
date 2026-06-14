"""分析所有未分析的股票评论 - 带超时重试"""
import json, ssl, socket, time, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API_KEY = 'sk-lsnhfgotvsmsndxsonigqhvpdmbtajviumyobxonrbigsyhh'
COMMENTS_FILE = 'J:/zss/stock/full_comments.json'
ANALYSIS_FILE = 'J:/zss/stock/analysis_results.json'
MIN_COMMENTS = 20  # At least 20 comments analyzed for a stock to be considered done

def qwen(messages, max_tokens=2000, retries=3):
    for attempt in range(retries):
        try:
            body = json.dumps({'model':'Qwen/Qwen3-32B','messages':messages,'max_tokens':max_tokens,'temperature':0.3})
            ctx = ssl.create_default_context()
            sock = socket.create_connection(('api.siliconflow.cn', 443), timeout=90)
            ssock = ctx.wrap_socket(sock, server_hostname='api.siliconflow.cn')
            hdrs = 'POST /v1/chat/completions HTTP/1.1\r\nHost: api.siliconflow.cn\r\n'
            hdrs += 'Authorization: Bearer {}\r\n'.format(API_KEY)
            hdrs += 'Content-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n'.format(len(body))
            ssock.sendall(hdrs.encode() + body.encode())
            resp = b''
            while True:
                c = ssock.read(8192)
                if not c: break
                resp += c
            ssock.close()
            he = resp.find(b'\r\n\r\n')
            return json.loads(resp[he+4:].decode()).get('choices',[{}])[0].get('message',{}).get('content','')
        except Exception as e:
            print('  retry {}: {}'.format(attempt+1, e), flush=True)
            time.sleep(2)
    return ''

def analyze_stock(name, posts):
    total_cmt = sum(len(p['cmts']) for p in posts)
    print('\n=== {}: {} posts, {} comments ==='.format(name, len(posts), total_cmt))

    all_analyzed = []
    cmt_count = 0

    for i, post in enumerate(posts):
        if not post['cmts']: continue

        # Batch up to 10 comments per API call
        cmts = post['cmts']
        for batch_start in range(0, len(cmts), 10):
            batch = cmts[batch_start:batch_start+10]
            cmt_texts = []
            for j, c in enumerate(batch):
                cmt_texts.append('[{}.{}] {}'.format(i+1, batch_start+j+1, c['c'][:300]))

            prompt = """分析股吧评论：
帖子：{}

评论：
{}

标注每条：[类型] [重要性] | 说明
类型：有价值/情绪发泄/无意义灌水/庄托水军
重要性：高/中/低""".format(post.get('title','无标题')[:60], '\n'.join(cmt_texts))

            result = qwen([{'role':'user','content':prompt}], 600)
            if result:
                for line in result.split('\n'):
                    if line.strip() and '[' in line:
                        all_analyzed.append(line.strip())
                        cmt_count += 1
            time.sleep(0.2)

        if (i+1) % 10 == 0:
            print('  {}/{} posts, {} comments analyzed'.format(i+1, len(posts), cmt_count), flush=True)

    # Stats
    stats = {'有价值':0,'情绪发泄':0,'无意义灌水':0,'庄托水军':0,'高重要性':0}
    for line in all_analyzed:
        for k in ['有价值','情绪发泄','无意义灌水','庄托水军']:
            if '[{}]'.format(k) in line: stats[k] += 1
        if '[高]' in line: stats['高重要性'] += 1

    # Summary
    sp = """{}股吧：{}条评论, 有价值{}, 情绪{}, 灌水{}, 庄托{}.
生成200字总结：【今日评论总结-{}】市场情绪：/关键讨论：/风险提示：/建议关注：""".format(
        name, sum(stats.values()), stats['有价值'], stats['情绪发泄'], stats['无意义灌水'], stats['庄托水军'], name)
    summary = qwen([{'role':'user','content':sp}], 400) or '分析失败'

    return {'stats':stats, 'details':all_analyzed, 'summary':summary}

# Load
with open(COMMENTS_FILE, encoding='utf-8') as f:
    all_data = json.load(f)

results = {}
if os.path.exists(ANALYSIS_FILE):
    with open(ANALYSIS_FILE, encoding='utf-8') as f:
        results = json.load(f)
print('Loaded: {} stocks analyzed'.format(len(results)))

# Find stocks that need analysis
for name, posts in all_data.items():
    if not posts: continue
    if name in results:
        stats = results[name].get('stats', {})
        total = sum(stats.values())
        if total >= MIN_COMMENTS:
            print('{}: OK ({} comments analyzed)'.format(name, total))
            continue
    results[name] = analyze_stock(name, posts)
    with open(ANALYSIS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    time.sleep(1)

print('\n=== Complete ===')
for name, r in results.items():
    s = r.get('stats', {})
    total = sum(s.values()) or 1
    print('{}: {}cmt V={}({}%) E={} S={}'.format(name, total, s.get('有价值',0), s.get('有价值',0)*100//total, s.get('情绪发泄',0), s.get('无意义灌水',0)))
