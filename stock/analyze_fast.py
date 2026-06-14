"""高效版：每只股票一次API调用，生成分析总结"""
import json, ssl, socket, time, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API_KEY = 'sk-lsnhfgotvsmsndxsonigqhvpdmbtajviumyobxonrbigsyhh'
COMMENTS_FILE = 'J:/zss/stock/full_comments.json'
ANALYSIS_FILE = 'J:/zss/stock/analysis_results.json'

def qwen(content, max_tokens=2000):
    body = json.dumps({'model':'Qwen/Qwen3-32B','messages':[{'role':'user','content':content}],'max_tokens':max_tokens,'temperature':0.3})
    ctx = ssl.create_default_context()
    sock = socket.create_connection(('api.siliconflow.cn', 443), timeout=120)
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

# Load data
with open(COMMENTS_FILE, encoding='utf-8') as f:
    all_data = json.load(f)

results = {}
if os.path.exists(ANALYSIS_FILE):
    with open(ANALYSIS_FILE, encoding='utf-8') as f:
        results = json.load(f)

for name, posts in all_data.items():
    if not posts: continue

    # Check if already analyzed with good coverage
    if name in results:
        s = results[name].get('stats', {})
        total = sum(s.values())
        if total >= 20:
            print('{}: SKIP ({} analyzed)'.format(name, total))
            continue

    total_cmt = sum(len(p['cmts']) for p in posts)
    print('\n=== {}: {} posts, {} comments ==='.format(name, len(posts), total_cmt))

    # Build a compact comment list (first 80 chars each, max 100 comments)
    comment_list = []
    for p in posts[:30]:  # Limit to 30 posts
        for c in p['cmts'][:5]:  # Limit to 5 comments per post
            txt = c['c'][:100].replace('\n',' ')
            if txt.strip():
                comment_list.append(txt)

    # If too many, sample evenly
    if len(comment_list) > 150:
        step = len(comment_list) // 150
        comment_list = comment_list[::step][:150]

    comments_text = '\n'.join('  - {}'.format(c) for c in comment_list)

    prompt = """分析以下{}股吧的{}条评论（采样），输出两个部分：

【数据统计】
- 有价值评论：大致数量
- 情绪发泄：大致数量
- 灌水：大致数量

【今日评论总结-{}】
市场情绪：（看多/看空/分歧/观望）
关键讨论：（1-2句概括）
风险提示：（如有明显风险）
建议关注：（值得关注的信息）

评论内容：
{}""".format(name, len(comment_list), name, comments_text)

    try:
        result = qwen(prompt, 600)
        print('  Result: {} chars'.format(len(result)), flush=True)

        # Parse stats from result
        stats = {'有价值':0, '情绪发泄':0, '无意义灌水':0, '庄托水军':0}
        for line in result.split('\n'):
            for k in stats:
                if k in line and '评论' in line:
                    # Try to extract number
                    import re
                    nums = re.findall(r'(\d+)', line)
                    if nums: stats[k] = int(nums[-1])

        # Extract summary
        summary = result
        if '【今日评论总结' in result:
            idx = result.index('【今日评论总结')
            summary = result[idx:]

        results[name] = {'stats': stats, 'summary': summary}
        with open(ANALYSIS_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print('  Saved', flush=True)

    except Exception as e:
        print('  ERROR: {}'.format(e), flush=True)
        results[name] = {'stats': {'有价值':0,'情绪发泄':0,'无意义灌水':0}, 'summary': '【今日评论总结-{}】\n分析失败: {}'.format(name, e)}
        with open(ANALYSIS_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    time.sleep(0.5)

print('\n=== ALL DONE ===')
for name, r in results.items():
    s = r.get('stats', {})
    print('{}: {}cmt | {}'.format(name, sum(s.values()), r.get('summary','')[:100]))
