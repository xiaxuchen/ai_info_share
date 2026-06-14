"""聪明版：只访问帖子列表页，用fetch()调评论API，避免频繁翻页触发滑块"""
import time, json, re, os, sys, io
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SAVE_FILE = 'J:/zss/stock/full_comments.json'
STEALTH_JS = os.path.join(os.path.dirname(__file__), 'EastMoney_Crawler-main', 'stealth.min.js')
POSTS_PER_STOCK = 50
MAX_POSTS = 80

opts = Options()
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option('excludeSwitches', ['enable-automation'])
opts.add_argument('--user-data-dir=C:/Users/xxc/.chrome_guba_login')

driver = webdriver.Chrome(service=Service(), options=opts)
if os.path.exists(STEALTH_JS):
    with open(STEALTH_JS) as f:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': f.read()})
    print('Stealth.js injected')

def extract_json(html, var_name):
    idx = html.find(var_name + '=')
    if idx < 0: return None
    start = html.find('{', idx)
    if start < 0: return None
    depth = 0; in_str = False; esc = False; end = start
    for i in range(start, len(html)):
        ch = html[i]
        if esc: esc = False; continue
        if ch == '\\': esc = True; continue
        if ch == '"': in_str = not in_str; continue
        if in_str: continue
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: end = i + 1; break
    if end <= start: return None
    try: return json.loads(html[start:end])
    except: return None

def strip_html(text):
    if not text: return ''
    return re.sub(r'<[^>]+>', '', text).replace('&nbsp;',' ').replace('&lt;','<').replace('&gt;','>').replace('&amp;','&').strip()

def fetch_comments_via_js(post_id, page=1, ps=30):
    """在浏览器中用fetch调评论API，自动带cookie"""
    js = f"""
    return fetch('https://gbapi.eastmoney.com/reply/api/Reply/ArticleNewReplyList', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{post_id: {post_id}, sort: 1, sorttype: 1, p: {page}, ps: {ps}}})
    }}).then(r => r.json()).then(d => JSON.stringify(d)).catch(e => JSON.stringify({{error: e.message}}))
    """
    try:
        result = driver.execute_script(js)
        return json.loads(result)
    except Exception as e:
        return {'error': str(e)}

def check_captcha():
    try:
        body_text = driver.find_element('tag name', 'body').text
        for kw in ['请完成验证', '滑动验证', '请按住滑块', '验证码', '拖动滑块']:
            if kw in body_text:
                return True
    except: pass
    return False

stocks = {
    'sz002703': '浙江世宝',
    'sh688234': '天岳先进',
    'sh600703': '三安光电',
    'sh600172': '黄河旋风',
    'sz002920': '德赛西威',
}

all_data = {}
if os.path.exists(SAVE_FILE):
    with open(SAVE_FILE, 'r', encoding='utf-8') as f:
        all_data = json.load(f)
    print(f'Loaded: {list(all_data.keys())}')

try:
    for code, name in stocks.items():
        if name in all_data and len(all_data[name]) >= POSTS_PER_STOCK:
            print(f'\n{name}: already {len(all_data[name])} posts, skip')
            continue

        pure = code[2:]
        print(f'\n=== {name} ({pure}) ===')

        # 只加载帖子列表页（1次HTTP请求！）
        driver.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
        time.sleep(3)

        if check_captcha():
            print('  CAPTCHA! 请在浏览器中手动完成滑块验证...')
            for _ in range(180):
                time.sleep(1)
                if not check_captcha():
                    print('  Captcha solved!')
                    driver.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
                    time.sleep(3)
                    break

        data = extract_json(driver.page_source, 'article_list')
        if not data:
            print('  No data')
            continue

        posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0][:MAX_POSTS]
        print(f'  {len(posts)} posts with comments')

        stock_posts = []
        for pi, p in enumerate(posts):
            pid = p['post_id']
            ptitle = p.get('post_title', '')[:50]
            pcmt = p.get('post_comment_count', 0)
            print(f'  [{pi+1}/{len(posts)}] {ptitle}... ({pcmt}cmt)', flush=True, end='')

            time.sleep(0.8)  # API调用间隔0.8秒即可

            # 用JS fetch调评论API（浏览器内，自动带cookie）
            reply_data = fetch_comments_via_js(pid)
            re_list = reply_data.get('re')
            comments = []
            if re_list:
                for r in re_list:
                    comments.append({
                        'user': r.get('user_name', ''),
                        'date': r.get('reply_publish_time', ''),
                        'likes': r.get('reply_like_count', 0),
                        'content': r.get('reply_content', ''),
                    })

            # 帖子正文用API不返回，需要单独访问页面（但可以skip非关键帖子）
            post_body = ''
            if pi < 10:  # 仅前10条获取正文
                time.sleep(1)
                driver.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
                time.sleep(2)
                article = extract_json(driver.page_source, 'post_article')
                post_body = strip_html(article.get('post_content', '')) if article else ''

            stock_posts.append({
                'post_id': pid,
                'post_title': p.get('post_title', ''),
                'post_body': post_body,
                'comments': comments,
            })
            print(f' {len(comments)}cmt', flush=True)

        all_data[name] = stock_posts
        total_c = sum(len(x['comments']) for x in stock_posts)
        print(f'  >> {len(stock_posts)} posts, {total_c} comments')

        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

finally:
    try: driver.quit()
    except: pass

grand = sum(sum(len(c['comments']) for c in p) for p in all_data.values())
total_posts = sum(len(p) for p in all_data.values())
print(f'\n=== DONE: {total_posts} posts, {grand} comments ===')
