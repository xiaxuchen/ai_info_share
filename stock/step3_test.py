"""Step 3: 测试爬取3条帖子"""
import time, json, re, os, random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument('--no-sandbox')
opts.add_argument('--user-data-dir=C:/Users/xxc/.chrome_guba_login')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option('excludeSwitches', ['enable-automation'])

stealth = 'J:/zss/stock/EastMoney_Crawler-main/stealth.min.js'
d = webdriver.Chrome(service=Service(), options=opts)
if os.path.exists(stealth):
    with open(stealth) as f:
        d.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': f.read()})

def extract_json(html, varname):
    idx = html.find(varname + '=')
    if idx < 0: return None
    start = html.find('{', idx)
    if start < 0: return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(html)):
        ch = html[i]
        if esc:
            esc = False
            continue
        if ch == '\\':
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return json.loads(html[start:i+1])
    return None

def strip_html(t):
    if not t: return ''
    return re.sub(r'<[^>]+>', '', t).replace('&nbsp;',' ').replace('&lt;','<').replace('&gt;','>').strip()

# Test: 浙江世宝
code = '002703'
name = '浙江世宝'
print(f'=== {name} ({code}) ===')

d.get(f'https://guba.eastmoney.com/list,{code},f_1.html')
time.sleep(3)

data = extract_json(d.page_source, 'article_list')
posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0]
print(f'Posts with comments: {len(posts)}')

results = []
for i, p in enumerate(posts[:3]):
    pid = p['post_id']
    title = p.get('post_title', '')[:60]
    ncmt = p.get('post_comment_count', 0)
    print(f'[{i+1}] {title}... ({ncmt}cmt)', flush=True, end='')

    time.sleep(random.uniform(2, 4))
    d.get(f'https://guba.eastmoney.com/news,{code},{pid}.html')
    time.sleep(2)

    article = extract_json(d.page_source, 'post_article')
    body = strip_html(article.get('post_content', '')) if article else ''

    items = d.find_elements(By.CSS_SELECTOR, 'div.reply_item')
    cmts = []
    for item in items:
        try:
            c = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
            lk = '0'
            dt = ''
            u = ''
            try: lk = item.find_element(By.CSS_SELECTOR, 'span.likemodule').text
            except: pass
            try: dt = item.find_element(By.CSS_SELECTOR, 'span.pubtime').text
            except: pass
            try: u = item.find_element(By.CSS_SELECTOR, 'div.reply_user_name a').text
            except: pass
            cmts.append({'u': u, 'd': dt, 'l': lk, 'c': c})
        except:
            pass

    results.append({'id': pid, 'title': p.get('post_title', ''), 'body': body, 'cmts': cmts})
    print(f' -> {len(cmts)}cmt body={len(body)}c', flush=True)

d.quit()

print(f'\n=== Results ===')
for r in results:
    print(f'\n[{r["id"]}] {r["title"][:80]}')
    print(f'  Body({len(r["body"])}c): {r["body"][:200]}')
    for c in r['cmts'][:3]:
        print(f'  [{c["u"]}] {c["c"][:120]}')
    if len(r['cmts']) > 3:
        print(f'  ... +{len(r["cmts"])-3} more')

with open('J:/zss/stock/test_crawl.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'\nSaved to test_crawl.json')
