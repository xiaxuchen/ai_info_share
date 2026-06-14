"""用硅基流动Qwen3-32B分析评论，不消费Claude上下文"""
import json, ssl, socket, time, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API_KEY = 'sk-lsnhfgotvsmsndxsonigqhvpdmbtajviumyobxonrbigsyhh'
COMMENTS_FILE = 'J:/zss/stock/full_comments.json'
ANALYSIS_FILE = 'J:/zss/stock/analysis_results.json'

def qwen_chat(messages, max_tokens=2000):
    """调用硅基流动 Qwen3-32B"""
    body = json.dumps({
        'model': 'Qwen/Qwen3-32B',
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': 0.3
    })
    ctx = ssl.create_default_context()
    sock = socket.create_connection(('api.siliconflow.cn', 443), timeout=60)
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
    """分析一只股票的所有评论"""
    print(f'\n=== {name}: {len(posts)} posts, {sum(len(p["cmts"]) for p in posts)} comments ===')

    all_analyzed = []
    summaries = []

    # Step 1: 批量分类评论
    for i, post in enumerate(posts):
        if not post['cmts']:
            continue

        # 构建评论列表
        cmt_texts = []
        for j, c in enumerate(post['cmts']):
            cmt_texts.append('[{}.{}] {}'.format(i+1, j+1, c['c'][:300]))

        batch = '\n'.join(cmt_texts)
        prompt = """分析以下股吧评论，对每条评论标注：
- 类型：[有价值]/[情绪发泄]/[无意义灌水]/[庄托水军]
- 重要性：[高]/[中]/[低]（高=对投资有参考价值）

帖子标题：{title}

评论：
{comments}

请严格按格式输出，每条一行：
[序号] [类型] [重要性] | 分析说明（10字以内）""".format(title=post.get('title','无标题'), comments=batch)

        try:
            result = qwen_chat([{'role': 'user', 'content': prompt}], 800)
            analyzed = []
            for line in result.strip().split('\n'):
                line = line.strip()
                if line and '[' in line:
                    analyzed.append(line)
            all_analyzed.append({'post_id': post['id'], 'title': post['title'][:60], 'analysis': analyzed})
            print('  [{}/{}] {} comments analyzed'.format(i+1, len(posts), len(post['cmts'])), flush=True)
        except Exception as e:
            print('  [{}/{}] analyze error: {}'.format(i+1, len(posts), e), flush=True)
            all_analyzed.append({'post_id': post['id'], 'title': post['title'][:60], 'analysis': ['[分析失败]']})

        time.sleep(0.5)  # API rate limit

    # Step 2: 生成总结
    stats = {'有价值': 0, '情绪发泄': 0, '无意义灌水': 0, '庄托水军': 0, '高重要性': 0}
    for a in all_analyzed:
        for line in a['analysis']:
            for k in ['有价值', '情绪发泄', '无意义灌水', '庄托水军']:
                if '[' + k + ']' in line: stats[k] += 1
            if '[高]' in line: stats['高重要性'] += 1

    summary_prompt = """以下是{name}股吧的评论分析统计：
- 总评论数: {total}
- 有价值: {val}条
- 情绪发泄: {emo}条
- 无意义灌水: {spam}条
- 庄托水军: {shill}条
- 高重要性: {high}条

请生成200字以内的今日评论总结，格式：
【今日评论总结-{name}】
市场情绪：（看多/看空/分歧/观望）
关键讨论：（1-2句概括）
风险提示：（如有）
建议关注：（值得关注的信息）""".format(
        name=name, total=sum(len(p['cmts']) for p in posts),
        val=stats['有价值'], emo=stats['情绪发泄'], spam=stats['无意义灌水'],
        shill=stats['庄托水军'], high=stats['高重要性']
    )

    try:
        summary = qwen_chat([{'role': 'user', 'content': summary_prompt}], 300)
        print('  Summary generated', flush=True)
    except Exception as e:
        summary = '【今日评论总结-{}\n分析生成失败: {}\n】'.format(name, e)
        print('  Summary error:', e, flush=True)

    return {'stats': stats, 'details': all_analyzed, 'summary': summary}

# ====== MAIN ======
if not os.path.exists(COMMENTS_FILE):
    print('No comments file yet! Run crawl first.')
    exit()

with open(COMMENTS_FILE, encoding='utf-8') as f:
    all_data = json.load(f)

results = {}
for name, posts in all_data.items():
    if not posts: continue
    results[name] = analyze_stock_comments(name, posts)
    time.sleep(1)

with open(ANALYSIS_FILE, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print('\n=== All analysis complete ===')
for name, r in results.items():
    s = r['stats']
    print('{}: {}cmt, valid={}, emotion={}, spam={}, shill={}'.format(
        name, sum(s.values()), s.get('有价值',0), s.get('情绪发泄',0),
        s.get('无意义灌水',0), s.get('庄托水军',0)))
