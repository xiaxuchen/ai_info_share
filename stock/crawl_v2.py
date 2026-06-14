"""爬股吧评论 v2 - 已登录，直接抓"""
import time, json, re, os, sys, io
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Fix GBK encoding crashes
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

options = Options()
options.add_argument('--no-sandbox')
options.add_argument(f'--user-data-dir=C:/Users/xxc/.chrome_guba_login')

print('Starting Chrome...')
driver = webdriver.Chrome(service=Service(), options=options)

stocks = {
    'sz002703': '浙江世宝',
    'sh688234': '天岳先进',
    'sh600703': '三安光电',
    'sh600172': '黄河旋风',
    'sz002920': '德赛西威',
}

all_data = {}

def extract_json_var(html, var_name):
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

try:
    for code, name in stocks.items():
        pure = code[2:]
        print(f'\n=== {name} ({pure}) ===')

        driver.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
        time.sleep(3)

        html = driver.page_source
        post_data = extract_json_var(html, 'article_list')
        if not post_data:
            print('  No article_list')
            continue

        posts = [p for p in post_data.get('re', []) if p.get('post_comment_count', 0) > 0]
        print(f'  Posts with comments: {len(posts)}')

        stock_posts = []
        for pi, p in enumerate(posts):
            pid = p['post_id']
            ptitle = p.get('post_title', '')[:50]
            pcmt = p.get('post_comment_count', 0)
            print(f'  [{pi+1}/{len(posts)}] {ptitle}... ({pcmt}cmt)', flush=True)

            try:
                driver.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
                time.sleep(2.5)

                html2 = driver.page_source
                article_data = extract_json_var(html2, 'post_article')
                post_body = strip_html(article_data.get('post_content', '')) if article_data else ''

                items = driver.find_elements(By.CSS_SELECTOR, 'div.reply_item')
                comments = []
                for item in items:
                    try:
                        content = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
                        try: likes = item.find_element(By.CSS_SELECTOR, 'span.likemodule').text
                        except: likes = '0'
                        try: dt = item.find_element(By.CSS_SELECTOR, 'span.pubtime').text
                        except: dt = ''
                        try: user = item.find_element(By.CSS_SELECTOR, 'div.reply_user_name a').text
                        except: user = ''
                        comments.append({'user': user, 'date': dt, 'likes': likes, 'content': content})
                    except:
                        pass

                stock_posts.append({
                    'post_id': pid,
                    'post_title': p.get('post_title', ''),
                    'post_body': post_body,
                    'comments': comments,
                })
                print(f'    {len(comments)} cmt, body={len(post_body)} chars', flush=True)

            except Exception as e:
                print(f'    Error: {e}', flush=True)

        all_data[name] = stock_posts

    output_file = 'J:/zss/stock/full_comments.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    total_comments = sum(sum(len(c['comments']) for c in p) for p in all_data.values())
    total_posts = sum(len(p) for p in all_data.values())
    print(f'\n=== DONE: {total_posts} posts, {total_comments} comments ===')

finally:
    driver.quit()
