"""最终版：Selenium访问帖子页，长间隔+滑块暂停+增量保存"""
import time, json, re, os, sys, io, random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SAVE_FILE = 'J:/zss/stock/full_comments.json'
STEALTH_JS = os.path.join(os.path.dirname(__file__),
    'EastMoney_Crawler-main', 'stealth.min.js')
POSTS_PER_STOCK = 50
MAX_POSTS = 80
STOCKS = {
    'sz002703': '浙江世宝',
    'sh688234': '天岳先进',
    'sh600703': '三安光电',
    'sh600172': '黄河旋风',
    'sz002920': '德赛西威',
}

def make_driver():
    opts = Options()
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_argument('--user-data-dir=C:/Users/xxc/.chrome_guba_login')
    d = webdriver.Chrome(service=Service(), options=opts)
    if os.path.exists(STEALTH_JS):
        with open(STEALTH_JS) as f:
            d.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': f.read()})
    return d

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

def has_captcha(drv):
    try:
        t = drv.find_element(By.TAG_NAME, 'body').text[:1000]
        for kw in ['请完成验证', '滑动验证', '请按住滑块', '验证码', '拖动滑块', '安全验证']:
            if kw in t: return True
    except: pass
    return False

def wait_captcha(drv):
    print('\n    *** 滑块验证！请在浏览器中手动完成，不要关闭窗口 ***', flush=True)
    for i in range(300):  # 最多等150秒
        time.sleep(0.5)
        if not has_captcha(drv):
            print('    滑块已解决！', flush=True)
            return True
        if i % 60 == 0 and i > 0:
            print(f'    等待中... ({i//2}秒)', flush=True)
    return False

# ====== 加载存量 ======
all_data = {}
if os.path.exists(SAVE_FILE):
    with open(SAVE_FILE, 'r', encoding='utf-8') as f:
        all_data = json.load(f)
    print(f'Loaded: {list(all_data.keys())}')

driver = make_driver()

try:
    for code, name in STOCKS.items():
        if name in all_data and len(all_data[name]) >= POSTS_PER_STOCK:
            print(f'\n{name}: done ({len(all_data[name])} posts), skip')
            continue

        pure = code[2:]
        print(f'\n{"="*50}')
        print(f'{name} ({pure})')
        print(f'{"="*50}')

        # 1. 加载帖子列表
        driver.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
        time.sleep(4)
        if has_captcha(driver):
            wait_captcha(driver)
            driver.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
            time.sleep(4)

        data = extract_json(driver.page_source, 'article_list')
        if not data:
            print('  No article_list')
            continue

        posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0][:MAX_POSTS]
        print(f'  {len(posts)} posts with comments')

        stock_posts = []
        for pi, p in enumerate(posts):
            pid = p['post_id']
            ptitle = p.get('post_title', '')[:50]
            pcmt = p.get('post_comment_count', 0)
            print(f'  [{pi+1}/{len(posts)}] {ptitle}', flush=True, end='')

            # 长随机延迟: 3-8秒，减少触发滑块
            delay = random.uniform(3.0, 8.0)
            time.sleep(delay)

            try:
                driver.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
                time.sleep(2)

                # 检查滑块
                if has_captcha(driver):
                    print(' SLIDER!', end='', flush=True)
                    if wait_captcha(driver):
                        driver.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
                        time.sleep(3)
                    else:
                        print(' TIMEOUT', flush=True)
                        continue

                # 提取正文
                article = extract_json(driver.page_source, 'post_article')
                post_body = strip_html(article.get('post_content', '')) if article else ''

                # 提取评论
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'div.reply_item')))
                except:
                    pass

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
                    except: pass

                stock_posts.append({
                    'post_id': pid,
                    'post_title': p.get('post_title', ''),
                    'post_body': post_body,
                    'comments': comments,
                })
                print(f' -> {len(comments)}cmt {len(post_body)}c', flush=True)

            except Exception as e:
                print(f' ERR:{e}', flush=True)

        all_data[name] = stock_posts
        total_c = sum(len(x['comments']) for x in stock_posts)
        print(f'  >> SAVED: {len(stock_posts)} posts, {total_c} comments', flush=True)

        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

except KeyboardInterrupt:
    print('\n\nInterrupted! Saving partial data...')
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

finally:
    try: driver.quit()
    except: pass

grand = sum(sum(len(c['comments']) for c in p) for p in all_data.values())
print(f'\nDone: {grand} total comments')
