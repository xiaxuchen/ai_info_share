"""爬剩余10只 - 列表页滑块拦截也要破解"""
import time, json, re, os, random, sys, io, cv2, numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SAVE_FILE = 'J:/zss/stock/full_comments.json'
STEALTH = 'J:/zss/stock/EastMoney_Crawler-main/stealth.min.js'
PROFILE = 'C:/Users/xxc/.chrome_guba_login'

REMAINING = [
    ('002915', '中欣氟材', 'sz'),
    ('002407', '多氟多', 'sz'),
    ('002031', '巨轮智能', 'sz'),
    ('002196', '方正电机', 'sz'),
    ('000811', '冰轮环境', 'sz'),
    ('603538', '美诺华', 'sh'),
    ('000988', '华工科技', 'sz'),
    ('600186', '莲花控股', 'sh'),
    ('000592', '平潭发展', 'sz'),
    ('002131', '利欧股份', 'sz'),
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
        for kw in ['请完成验证','滑动验证','拖动滑块','安全验证','完成拼图','填充拼图','数据核实','上滑或点击','验证码']:
            if kw in t: return True
    except: pass
    return False

def solve_slider(drv):
    print('  [SLIDER]', flush=True, end='')
    for attempt in range(3):
        try:
            ss = drv.get_screenshot_as_png()
            img = cv2.imdecode(np.frombuffer(ss, np.uint8), cv2.IMREAD_COLOR)
            h, w = img.shape[:2]
            roi = img[int(h*0.3):int(h*0.75), int(w*0.1):int(w*0.9)]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            piece = None
            for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:15]:
                x, y, cw, ch = cv2.boundingRect(cnt)
                if 30 < cw < 180 and 25 < ch < 90:
                    piece = (x+int(w*0.1), y+int(h*0.3), cw, ch); break
            if not piece: continue
            px, py, pw, ph = piece
            template = img[py:py+ph, px:px+pw]
            search = img[int(h*0.15):int(h*0.7), :]
            res = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
            _, _, _, max_loc = cv2.minMaxLoc(res)
            distance = max(60, max_loc[0])
            print(f' d={distance}', flush=True, end='')
            btn = None
            for sel in ['.yidun_slider', '[class*="slider-btn"]', '[class*="slide-btn"]', '.yidun_slider__indicator']:
                els = drv.find_elements(By.CSS_SELECTOR, sel)
                if els: btn = els[0]; break
            if not btn: continue
            act = ActionChains(drv)
            act.click_and_hold(btn).perform(); time.sleep(0.1)
            tracks = []; t = 0
            while t < distance:
                if t < distance*0.2: s = random.randint(1,3)
                elif t < distance*0.7: s = random.randint(2,5)
                else: s = random.randint(1,2)
                t += s
                if t > distance: t = distance
                tracks.append(t)
            last = 0
            for t in tracks:
                act.move_by_offset(t-last, random.randint(-1,1)).perform()
                time.sleep(random.uniform(0.002,0.006))
                last = t
            act.release().perform(); time.sleep(2)
            if not has_captcha(drv):
                print(' OK', flush=True); return True
            print(' RETRY', flush=True, end='')
        except Exception as e:
            print(f' ERR:{e}', flush=True, end='')
            time.sleep(1)
    print(' FAIL', flush=True)
    return False

def load_list_page(drv, code):
    """加载列表页，遇滑块就破解后重试"""
    for attempt in range(5):
        drv.get('https://guba.eastmoney.com/list,{},f_1.html'.format(code))
        time.sleep(3)
        if has_captcha(drv):
            print('  List captcha!', flush=True)
            if solve_slider(drv):
                print('  Captcha solved, reloading...', flush=True)
                time.sleep(2)
                continue
            else:
                print('  Captcha solve failed', flush=True)
                time.sleep(5)
                continue
        data = xjson(drv.page_source, 'article_list')
        if data and data.get('re'):
            return data
        print('  No data (attempt {})'.format(attempt+1), flush=True)
        time.sleep(3)
    return None

# Load existing
all_data = {}
if os.path.exists(SAVE_FILE):
    with open(SAVE_FILE, encoding='utf-8') as f:
        all_data = json.load(f)

try:
    for code, name, prefix in REMAINING:
        full_code = prefix + code
        if name in all_data and len(all_data[name]) >= 20:
            print(f'\n{name}: DONE ({len(all_data[name])}), skip'); continue

        print(f'\n{"="*40}')
        print(f'{name} ({full_code})')
        print(f'{"="*40}')

        data = load_list_page(d, code)
        if not data:
            print('  Failed - captcha may still block'); continue

        posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0][:80]
        print(f'{len(posts)} posts with comments')

        stock_posts = []
        for i, p in enumerate(posts):
            pid = p['post_id']
            title = p.get('post_title', '')[:60]
            print(f'[{i+1}/{len(posts)}] {title}', end='', flush=True)
            time.sleep(random.uniform(1.2, 2.5))
            try:
                d.get(f'https://guba.eastmoney.com/news,{code},{pid}.html')
                time.sleep(1.5)
                if has_captcha(d):
                    if not solve_slider(d):
                        print(' CAPTCHA_STOP', flush=True); break
                    time.sleep(2)
                    d.get(f'https://guba.eastmoney.com/news,{code},{pid}.html')
                    time.sleep(1.5)
                article = xjson(d.page_source, 'post_article')
                body = strip_html(article.get('post_content', '')) if article else ''
                items = d.find_elements(By.CSS_SELECTOR, 'div.reply_item')
                cmts = []
                for item in items:
                    try:
                        c = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
                        lk = '0'; dt = ''; u = ''
                        try: lk = item.find_element(By.CSS_SELECTOR, 'span.likemodule').text
                        except: pass
                        try: dt = item.find_element(By.CSS_SELECTOR, 'span.pubtime').text
                        except: pass
                        try: u = item.find_element(By.CSS_SELECTOR, '[class*="user_name"] a').text
                        except:
                            try: u = item.find_element(By.CSS_SELECTOR, '[class*="nick"]').text
                            except: pass
                        cmts.append({'u':u,'d':dt,'l':lk,'c':c})
                    except: pass
                stock_posts.append({'id':pid,'title':p.get('post_title',''),'body':body,'cmts':cmts})
                print(f' -> {len(cmts)}cmt', flush=True)
            except Exception as e:
                print(f' ERR:{e}', flush=True)

        all_data[name] = stock_posts
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        total_c = sum(len(x['cmts']) for x in stock_posts)
        print('  SAVED: {} posts, {} comments'.format(len(stock_posts), total_c))

finally:
    d.quit()

grand = sum(sum(len(c['cmts']) for c in p) for p in all_data.values())
print(f'\n=== {sum(len(p) for p in all_data.values())} posts, {grand} comments ===')
