"""稳健版股吧爬虫 - stealth.js反滑块 + 随机延迟 + 增量保存"""
import time, json, re, os, sys, io, random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

POSTS_PER_STOCK = 50
MAX_POSTS = 80
SAVE_FILE = 'J:/zss/stock/full_comments.json'
STEALTH_JS = os.path.join(os.path.dirname(__file__), 'EastMoney_Crawler-main', 'stealth.min.js')

def make_options():
    opts = Options()
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument('--user-data-dir=C:/Users/xxc/.chrome_guba_login')
    return opts

def make_driver():
    d = webdriver.Chrome(service=Service(), options=make_options())
    if os.path.exists(STEALTH_JS):
        with open(STEALTH_JS) as f:
            d.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': f.read()})
    return d

def check_captcha(drv):
    try:
        body_text = drv.find_element(By.TAG_NAME, 'body').text
        for kw in ['请完成验证', '滑动验证', '请按住滑块', '验证码', '拖动滑块', '安全验证']:
            if kw in body_text:
                return True
    except: pass
    return False

def wait_for_captcha(drv, timeout=90):
    print('    *** 检测到滑块验证码！请在浏览器中手动完成 ***', flush=True)
    for _ in range(timeout * 2):
        time.sleep(0.5)
        if not check_captcha(drv):
            print('    滑块已解除，继续...', flush=True)
            time.sleep(2)
            return True
    return False

def load_page(drv, url, wait=3):
    try:
        drv.get(url)
    except:
        try: drv.quit()
        except: pass
        time.sleep(5)
        drv = make_driver()
        drv.get(url)
    time.sleep(wait)
    if check_captcha(drv):
        if not wait_for_captcha(drv):
            return drv, False
        try: drv.get(url); time.sleep(wait)
        except: return drv, False
    return drv, True

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

# ====== MAIN ======
if not os.path.exists(STEALTH_JS):
    print('WARNING: stealth.js not found')

stocks = {
    'sz002703': '浙江世宝',
    'sh688234': '天岳先进',
    'sh600703': '三安光电',
    'sh600172': '黄河旋风',
    'sz002920': '德赛西威',
}

all_data = {}
if os.path.exists(SAVE_FILE):
    try:
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
        print(f'Loaded: {list(all_data.keys())}')
    except: pass

driver = make_driver()

try:
    for code, name in stocks.items():
        if name in all_data and len(all_data[name]) >= POSTS_PER_STOCK:
            print(f'\n{name}: already {len(all_data[name])} posts, skip')
            continue

        pure = code[2:]
        print(f'\n=== {name} ({pure}) ===')

        driver, ok = load_page(driver, f'https://guba.eastmoney.com/list,{pure},f_1.html')
        if not ok:
            print('  Post list captcha timeout')
            continue

        data = extract_json(driver.page_source, 'article_list')
        if not data:
            print('  No article_list')
            continue

        posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0]
        posts = posts[:MAX_POSTS]
        print(f'  {len(posts)} posts with comments')

        stock_posts = []
        for pi, p in enumerate(posts):
            pid = p['post_id']
            ptitle = p.get('post_title', '')[:50]
            pcmt = p.get('post_comment_count', 0)
            print(f'  [{pi+1}/{len(posts)}] {ptitle}... ({pcmt}cmt)', flush=True, end='')

            time.sleep(random.uniform(1.5, 4.0))

            driver, ok = load_page(driver, f'https://guba.eastmoney.com/news,{pure},{pid}.html', wait=2)
            if not ok:
                print(' CAPTCHA_TIMEOUT', flush=True)
                time.sleep(10)
                continue

            try:
                article = extract_json(driver.page_source, 'post_article')
                post_body = strip_html(article.get('post_content', '')) if article else ''

                items = driver.find_elements(By.CSS_SELECTOR, 'div.reply_item')
                comments = []
                for item in items:
                    try:
                        c = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
                        try: lk = item.find_element(By.CSS_SELECTOR, 'span.likemodule').text
                        except: lk = '0'
                        try: dt = item.find_element(By.CSS_SELECTOR, 'span.pubtime').text
                        except: dt = ''
                        try: u = item.find_element(By.CSS_SELECTOR, 'div.reply_user_name a').text
                        except: u = ''
                        comments.append({'user': u, 'date': dt, 'likes': lk, 'content': c})
                    except: pass

                stock_posts.append({
                    'post_id': pid,
                    'post_title': p.get('post_title', ''),
                    'post_body': post_body,
                    'comments': comments,
                })
                print(f' {len(comments)}cmt {len(post_body)}c', flush=True)

            except Exception as e:
                print(f' ERR:{e}', flush=True)

        all_data[name] = stock_posts
        total_c = sum(len(x['comments']) for x in stock_posts)
        print(f'  >> {len(stock_posts)} posts, {total_c} comments', flush=True)

        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

finally:
    try: driver.quit()
    except: pass

grand = sum(sum(len(c['comments']) for c in p) for p in all_data.values())
total_posts = sum(len(p) for p in all_data.values())
print(f'\n=== DONE: {total_posts} posts, {grand} comments ===')
