"""股吧登录+爬虫 - 验证码通过文件交互"""
import time, json, re, os, sys, io, random, cv2, numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PHONE = '17779911413'
SAVE_FILE = 'J:/zss/stock/full_comments.json'
CODE_FILE = 'J:/zss/stock/verify_code.txt'
SIGNAL_FILE = 'J:/zss/stock/waiting_for_code.txt'
STEALTH = os.path.join(os.path.dirname(__file__), 'EastMoney_Crawler-main', 'stealth.min.js')
PROFILE = 'C:/Users/xxc/.chrome_guba'

STOCKS = [
    ('sz002703', '浙江世宝'),
    ('sh688234', '天岳先进'),
    ('sh600703', '三安光电'),
    ('sh600172', '黄河旋风'),
    ('sz002920', '德赛西威'),
]

def mkdriver():
    opts = Options()
    opts.add_argument('--no-sandbox')
    opts.add_argument(f'--user-data-dir={PROFILE}')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    d = webdriver.Chrome(service=Service(), options=opts)
    d.maximize_window()  # 强制弹出到前台
    if os.path.exists(STEALTH):
        with open(STEALTH) as f:
            d.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': f.read()})
    return d

def is_logged_in(drv):
    try:
        t = drv.find_element(By.TAG_NAME, 'body').text[:1000]
        return '退出' in t and '登录' not in t[:300]
    except: return False

def has_captcha(drv):
    try:
        t = drv.find_element(By.TAG_NAME, 'body').text[:2000]
        for kw in ['请完成验证', '滑动验证', '拖动滑块', '安全验证']:
            if kw in t: return True
    except: pass
    return False

def extract_json(html, varname):
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

def solve_slider(drv):
    print('    *** 滑块验证码 ***', flush=True)
    try:
        ss = drv.get_screenshot_as_png()
        img = cv2.imdecode(np.frombuffer(ss, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        roi = img[int(h*0.35):int(h*0.75), :]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        piece = None
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if 40 < cw < 150 and 40 < ch < 100:
                piece = (x, y+int(h*0.35), cw, ch); break
        if not piece:
            print('    找不到滑块，等待手动...', flush=True)
            return _wait_manual(drv)
        px, py, pw, ph = piece
        template = img[py:py+ph, px:px+pw]
        search_area = img[int(h*0.2):int(h*0.7), :]
        result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(result)
        distance = max(100, max_loc[0] + pw - px)
        print(f'    拖动距离: {distance}px', flush=True)
        btn = None
        for sel in ['.yidun_slider', '[class*="slider-btn"]', '[class*="slide-btn"]', '.yidun_slider__indicator']:
            els = drv.find_elements(By.CSS_SELECTOR, sel)
            if els: btn = els[0]; break
        if not btn:
            print('    找不到滑块按钮', flush=True)
            return _wait_manual(drv)
        action = ActionChains(drv)
        action.click_and_hold(btn).perform(); time.sleep(0.1)
        tracks = []; t = 0
        while t < distance:
            if t < distance*0.2: s = random.randint(1,4)
            elif t < distance*0.7: s = random.randint(3,8)
            else: s = random.randint(1,3)
            t += s
            if t > distance: t = distance
            tracks.append(t)
        last = 0
        for t in tracks:
            action.move_by_offset(t-last, random.randint(-1,1)).perform()
            time.sleep(random.uniform(0.003,0.01))
            last = t
        action.release().perform(); time.sleep(2)
        if not has_captcha(drv):
            print('    *** 破解成功! ***', flush=True); return True
        print('    验证失败', flush=True)
        return _wait_manual(drv)
    except Exception as e:
        print(f'    异常: {e}', flush=True)
        return _wait_manual(drv)

def _wait_manual(drv):
    print('    请在浏览器中手动完成滑块...', flush=True)
    for _ in range(180):
        time.sleep(0.5)
        if not has_captcha(drv):
            print('    已解决!', flush=True); return True
    return False

# ================ LOGIN ================
def do_login(drv):
    print('\n=== 登录 ===')
    drv.get('https://passport2.eastmoney.com/pub/login?backurl=https://guba.eastmoney.com/')
    time.sleep(4)

    if is_logged_in(drv):
        print('已登录'); return True

    iframe = None
    for f in drv.find_elements(By.TAG_NAME, 'iframe'):
        if 'exaccount' in (f.get_attribute('src') or ''):
            iframe = f; break
    if not iframe: return is_logged_in(drv)

    drv.switch_to.frame(iframe); time.sleep(2)
    print('进入iframe')

    for s in drv.find_elements(By.TAG_NAME, 'span'):
        if '短信' in s.text: s.click(); time.sleep(1); print('短信登录'); break

    for sel in ['div.checkbox', 'div.agreement-row']:
        els = drv.find_elements(By.CSS_SELECTOR, sel)
        if els: drv.execute_script('arguments[0].click()', els[0]); time.sleep(0.3); print('已勾选协议'); break

    phone = drv.find_element(By.ID, 'txt_mobile')
    phone.click(); time.sleep(0.3)
    for ch in PHONE: phone.send_keys(ch); time.sleep(0.05)
    print(f'手机号: {PHONE}')
    time.sleep(1)

    btn = drv.find_element(By.ID, 'btn_getvcode')
    btn.click()
    print('点击发送验证码')
    time.sleep(2)

    drv.switch_to.default_content()

    # 处理滑块
    if has_captcha(drv):
        print('需要滑块验证')
        if not solve_slider(drv):
            for _ in range(120):
                time.sleep(0.5)
                if not has_captcha(drv): break
        drv.switch_to.frame(iframe)
        time.sleep(1)
        try:
            btn2 = drv.find_element(By.ID, 'btn_getvcode')
            btn2.click()
            time.sleep(2)
        except: pass
        drv.switch_to.default_content()

    # --- 等验证码 ---
    print(f'\n>>> 验证码已发送到 {PHONE} <<<')
    print('请在浏览器中输入验证码并登录')

    # 写信号文件
    with open(SIGNAL_FILE, 'w') as f: f.write(str(int(time.time())))
    print(f'信号文件: {SIGNAL_FILE}')

    # 等用户输入验证码+登录
    for i in range(1200):
        time.sleep(0.5)
        if is_logged_in(drv):
            print('登录成功!')
            return True
        if i % 120 == 0 and i > 0:
            print(f'  等待中... ({i//2}s)')

    return False

# ================ CRAWL ================
def crawl_stock(drv, name, code):
    pure = code[2:]
    print(f'\n=== {name} ({pure}) ===')
    drv.get(f'https://guba.eastmoney.com/list,{pure},f_1.html'); time.sleep(3)
    if has_captcha(drv):
        if not solve_slider(drv): return []
        drv.get(f'https://guba.eastmoney.com/list,{pure},f_1.html'); time.sleep(3)

    data = extract_json(drv.page_source, 'article_list')
    if not data: return []
    posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0][:80]
    print(f'  {len(posts)} 帖子有评论')

    result = []
    for i, p in enumerate(posts):
        pid = p['post_id']
        title = p.get('post_title', '')[:60]
        ncmt = p.get('post_comment_count', 0)
        print(f'  [{i+1}/{len(posts)}] {title}', end='', flush=True)
        time.sleep(random.uniform(2.0, 5.0))
        try:
            drv.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html'); time.sleep(2)
            if has_captcha(drv):
                print(' SLIDER!', end='', flush=True)
                if not solve_slider(drv): print(' TIMEOUT', flush=True); continue
                drv.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html'); time.sleep(3)
            article = extract_json(drv.page_source, 'post_article')
            body = strip_html(article.get('post_content', '')) if article else ''
            items = drv.find_elements(By.CSS_SELECTOR, 'div.reply_item')
            cmts = []
            for item in items:
                try:
                    c = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
                    try: lk = item.find_element(By.CSS_SELECTOR, 'span.likemodule').text
                    except: lk = '0'
                    try: dt = item.find_element(By.CSS_SELECTOR, 'span.pubtime').text
                    except: dt = ''
                    try: u = item.find_element(By.CSS_SELECTOR, 'div.reply_user_name a').text
                    except: u = ''
                    cmts.append({'u':u,'d':dt,'l':lk,'c':c})
                except: pass
            result.append({'id':pid,'title':p.get('post_title',''),'body':body,'cmts':cmts})
            print(f' -> {len(cmts)}cmt', flush=True)
        except Exception as e:
            print(f' ERR:{e}', flush=True)

    print(f'  DONE: {len(result)} posts, {sum(len(x["cmts"]) for x in result)} comments')
    return result

# ================ MAIN ================
if __name__ == '__main__':
    d = mkdriver()
    all_data = {}
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
        print(f'已加载: {list(all_data.keys())}')

    try:
        logged = False
        for code, name in STOCKS:
            if name in all_data and len(all_data[name]) >= 50:
                print(f'{name}: 已完成 ({len(all_data[name])}), 跳过'); continue
            if not logged:
                logged = do_login(d)
                if not logged: print('登录失败!'); break
            posts = crawl_stock(d, name, code)
            if posts:
                all_data[name] = posts
                with open(SAVE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2)
                print(f'  已保存 {name}')
    except KeyboardInterrupt:
        print('\n中断!')
    finally:
        try: d.quit()
        except: pass

    total = sum(sum(len(x.get('cmts',x.get('comments',[]))) for x in p) for p in all_data.values())
    print(f'\n=== 总计 {sum(len(p) for p in all_data.values())} posts, {total} comments ===')
