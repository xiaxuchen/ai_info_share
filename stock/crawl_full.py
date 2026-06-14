"""全量爬虫 - 5只股票 × 80帖 = 增量保存到 full_comments.json"""
import time, json, re, os, random, sys, io
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SAVE_FILE = 'J:/zss/stock/full_comments.json'
STEALTH = 'J:/zss/stock/EastMoney_Crawler-main/stealth.min.js'
PROFILE = 'C:/Users/xxc/.chrome_guba'
MAX_POSTS = 80

STOCKS = [
    ('002703', '浙江世宝'),
    ('688234', '天岳先进'),
    ('600703', '三安光电'),
    ('600172', '黄河旋风'),
    ('002920', '德赛西威'),
]

opts = Options()
opts.add_argument('--no-sandbox')
opts.add_argument(f'--user-data-dir={PROFILE}')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option('excludeSwitches', ['enable-automation'])

d = webdriver.Chrome(service=Service(), options=opts)
if os.path.exists(STEALTH):
    with open(STEALTH) as f:
        d.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': f.read()})

def xjson(html, varname):
    idx = html.find(varname + '=')
    if idx < 0: return None
    start = html.find('{', idx)
    if start < 0: return None
    depth = 0; in_str = False; esc = False
    for i in range(start, len(html)):
        ch = html[i]
        if esc: esc = False; continue
        if ch == '\\': esc = True; continue
        if ch == '"': in_str = not in_str; continue
        if in_str: continue
        if ch == '{': depth += 1
        elif ch == '}': depth -= 1
        if depth == 0 and ch == '}': return json.loads(html[start:i+1])
    return None

def strip_html(t):
    if not t: return ''
    return re.sub(r'<[^>]+>', '', t).replace('&nbsp;',' ').replace('&lt;','<').replace('&gt;','>').strip()

def has_captcha(drv):
    try:
        t = drv.find_element(By.TAG_NAME, 'body').text[:3000]
        for kw in ['请完成验证', '滑动验证', '拖动滑块', '安全验证']:
            if kw in t: return True
    except: pass
    return False

# Load existing
all_data = {}
if os.path.exists(SAVE_FILE):
    with open(SAVE_FILE, encoding='utf-8') as f:
        all_data = json.load(f)

try:
    # Check login
    d.get('https://guba.eastmoney.com/')
    time.sleep(3)
    body = d.find_element(By.TAG_NAME, 'body').text[:1000]
    if '退出' not in body:
        print('NOT LOGGED IN! Need manual login first')
    else:
        print('Logged in OK')

    for code, name in STOCKS:
        if name in all_data and len(all_data[name]) >= 50:
            print(f'\n{name}: DONE ({len(all_data[name])}), skip')
            continue

        print(f'\n{"="*40}')
        print(f'{name} ({code})')
        print(f'{"="*40}')

        d.get(f'https://guba.eastmoney.com/list,{code},f_1.html')
        time.sleep(3)

        if has_captcha(d):
            print('CAPTCHA! Pausing 30s...')
            time.sleep(30)
            d.get(f'https://guba.eastmoney.com/list,{code},f_1.html')
            time.sleep(3)

        data = xjson(d.page_source, 'article_list')
        if not data:
            print('Failed to get posts')
            continue

        posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0][:MAX_POSTS]
        print(f'{len(posts)} posts with comments')

        stock_posts = []
        for i, p in enumerate(posts):
            pid = p['post_id']
            title = p.get('post_title', '')[:60]
            ncmt = p.get('post_comment_count', 0)
            print(f'[{i+1}/{len(posts)}] {title}', end='', flush=True)

            time.sleep(random.uniform(1.5, 3.5))
            try:
                d.get(f'https://guba.eastmoney.com/news,{code},{pid}.html')
                time.sleep(2)

                if has_captcha(d):
                    print(' CAPTCHA! wait 20s', end='')
                    time.sleep(20)
                    d.get(f'https://guba.eastmoney.com/news,{code},{pid}.html')
                    time.sleep(2)

                article = xjson(d.page_source, 'post_article')
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
                        try: u = item.find_element(By.CSS_SELECTOR, '[class*="user_name"] a').text
                        except:
                            try: u = item.find_element(By.CSS_SELECTOR, '[class*="nick"]').text
                            except: pass
                        cmts.append({'u':u, 'd':dt, 'l':lk, 'c':c})
                    except: pass

                stock_posts.append({'id':pid, 'title':p.get('post_title',''), 'body':body, 'cmts':cmts})
                print(f' -> {len(cmts)}cmt', flush=True)

            except Exception as e:
                print(f' ERR:{e}', flush=True)

        all_data[name] = stock_posts
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        print(f'  SAVED {name}: {len(stock_posts)} posts, {sum(len(x["cmts"]) for x in stock_posts)} comments')

finally:
    d.quit()

grand = sum(sum(len(c['cmts']) for c in p) for p in all_data.values())
print(f'\n=== COMPLETE: {sum(len(p) for p in all_data.values())} posts, {grand} comments ===')
