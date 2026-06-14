#!/usr/bin/env python3
"""股吧登录+评论爬取 - 最终精简版"""
import time, json, re, os, sys, io, random
import cv2, numpy as np
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
STEALTH = os.path.join(os.path.dirname(__file__), 'EastMoney_Crawler-main', 'stealth.min.js')
PROFILE = 'C:/Users/xxc/.chrome_guba'

STOCKS = [
    ('sz002703', '浙江世宝'),
    ('sh688234', '天岳先进'),
    ('sh600703', '三安光电'),
    ('sh600172', '黄河旋风'),
    ('sz002920', '德赛西威'),
]

# ================ DRIVER ================
def mkdriver():
    opts = Options()
    opts.add_argument('--no-sandbox')
    opts.add_argument(f'--user-data-dir={PROFILE}')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    d = webdriver.Chrome(service=Service(), options=opts)
    if os.path.exists(STEALTH):
        with open(STEALTH) as f:
            d.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': f.read()})
    return d

# ================ UTILS ================
def is_logged_in(drv):
    try:
        t = drv.find_element(By.TAG_NAME, 'body').text[:1000]
        return '退出' in t and '登录' not in t[:300]
    except: return False

def has_captcha(drv):
    try:
        t = drv.find_element(By.TAG_NAME, 'body').text[:2000]
        for kw in ['请完成验证', '滑动验证', '拖动滑块', '验证码', '安全验证']:
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

# ================ SLIDER SOLVER ================
def solve_slider(drv):
    """用OpenCV破解滑块，失败则等待用户手动"""
    print('    *** 滑块验证码 ***', flush=True)
    try:
        # 截图整个页面
        ss_bytes = drv.get_screenshot_as_png()
        img = cv2.imdecode(np.frombuffer(ss_bytes, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]

        # 在页面中部找滑块区域 (40-70% height)
        roi = img[int(h*0.35):int(h*0.75), :]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 找滑块拼图（小矩形区域）
        piece = None
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if 40 < cw < 150 and 40 < ch < 100:
                piece = (x, y+int(h*0.35), cw, ch)
                break

        if not piece:
            print('    无法找到滑块拼图，等待手动...', flush=True)
            return _wait_manual(drv)

        # 用模板匹配找缺口位置
        px, py, pw, ph = piece
        template = img[py:py+ph, px:px+pw]
        search_area = img[int(h*0.2):int(h*0.7), :]
        result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(result)

        # 缺口位置（缺口在拼图右边一定距离）
        # 实际上模板匹配会找到最佳匹配位置，它在背景中
        distance = max_loc[0] + pw - px  # 调整计算
        distance = max(distance, 50)
        print(f'    计算拖动距离: {distance}px', flush=True)

        # 找滑块按钮
        btn = None
        for sel in ['.yidun_slider', '[class*="slider-btn"]', '[class*="slide-btn"]',
                    '.yidun_slider__indicator', '[class*="yidun_control"]']:
            els = drv.find_elements(By.CSS_SELECTOR, sel)
            if els: btn = els[0]; break
        if not btn:
            print('    找不到滑块按钮，等待手动...', flush=True)
            return _wait_manual(drv)

        # 执行拖动（人类轨迹）
        action = ActionChains(drv)
        action.click_and_hold(btn).perform()
        time.sleep(0.1)

        # 分段拖动
        tracks = []
        t = 0
        while t < distance:
            if t < distance * 0.2: s = random.randint(1, 4)
            elif t < distance * 0.7: s = random.randint(3, 8)
            else: s = random.randint(1, 3)
            t += s
            if t > distance: t = distance
            tracks.append(t)

        last = 0
        for t in tracks:
            action.move_by_offset(t-last, random.randint(-1, 1)).perform()
            time.sleep(random.uniform(0.003, 0.01))
            last = t

        action.release().perform()
        time.sleep(2)

        if not has_captcha(drv):
            print('    *** 滑块破解成功! ***', flush=True)
            return True
        else:
            print('    滑块验证失败', flush=True)
            return _wait_manual(drv)

    except Exception as e:
        print(f'    滑块破解异常: {e}，等待手动...', flush=True)
        return _wait_manual(drv)

def _wait_manual(drv):
    print('    请在浏览器中手动完成滑块验证...', flush=True)
    for _ in range(180):
        time.sleep(0.5)
        if not has_captcha(drv):
            print('    滑块已解决', flush=True)
            return True
    return False

# ================ LOGIN ================
def do_login(drv):
    print('\n=== 登录 ===')
    drv.get('https://passport2.eastmoney.com/pub/login?backurl=https://guba.eastmoney.com/')
    time.sleep(4)

    if is_logged_in(drv):
        print('已登录')
        return True

    # 找登录iframe
    iframe = None
    for f in drv.find_elements(By.TAG_NAME, 'iframe'):
        src = f.get_attribute('src') or ''
        if 'exaccount' in src:
            iframe = f
            break
    if not iframe:
        print('无登录iframe，可能已登录')
        return is_logged_in(drv)

    drv.switch_to.frame(iframe)
    time.sleep(2)
    print('进入登录iframe')

    # 点短信登录tab
    for s in drv.find_elements(By.TAG_NAME, 'span'):
        if '短信' in s.text:
            s.click()
            time.sleep(1)
            print('切换到短信登录')
            break

    # 勾选协议
    for sel in ['div.checkbox', 'div.agreement-row', '[class*="agree"]']:
        els = drv.find_elements(By.CSS_SELECTOR, sel)
        if els:
            try: els[0].click(); time.sleep(0.3); print('已勾选协议'); break
            except: pass

    # 逐字符输入手机号
    phone = drv.find_element(By.ID, 'txt_mobile')
    phone.click(); time.sleep(0.3)
    for ch in PHONE:
        phone.send_keys(ch); time.sleep(0.05)
    print(f'手机号: {PHONE}')
    time.sleep(1)

    # 点击"获取验证码"按钮——可能是"点击开始验证"（需要先过滑块）或"获取验证码"（直接发送）
    btn = drv.find_element(By.ID, 'btn_getvcode')
    btn_val = btn.get_attribute('value') or btn.text or ''
    print(f'按钮状态: "{btn_val}"')

    if '验证' not in btn_val and '获取' not in btn_val:
        # 按钮没激活，等一等
        for _ in range(20):
            time.sleep(0.5)
            btn_val = btn.get_attribute('value') or btn.text or ''
            if '验证' in btn_val or '获取' in btn_val:
                break

    btn.click()
    print(f'已点击: "{btn_val}"')
    time.sleep(2)

    drv.switch_to.default_content()
    time.sleep(2)

    # 处理滑块验证（可能在点击"点击开始验证"后弹出）
    if has_captcha(drv):
        print('检测到滑块验证，尝试破解...')
        if not solve_slider(drv):
            print('滑块破解失败，请手动完成')
            for _ in range(120):
                time.sleep(0.5)
                if not has_captcha(drv): break

        # 滑块通过后可能需要再次点击发送按钮
        time.sleep(1)
        drv.switch_to.frame(iframe)
        try:
            btn2 = drv.find_element(By.ID, 'btn_getvcode')
            btn2_val = btn2.get_attribute('value') or ''
            if '获取' in btn2_val or '验证码' in btn2_val:
                btn2.click()
                print('滑块通过后重新点击获取验证码')
        except: pass
        drv.switch_to.default_content()
        time.sleep(2)

    print(f'\n>>> 验证码已发送到 {PHONE}，请在浏览器中完成登录 <<<')
    print('（输入验证码 + 通过滑块 + 点击登录）')

    # 等待登录完成
    for i in range(1200):  # 最多等 10 分钟
        time.sleep(0.5)
        if is_logged_in(drv):
            print('登录成功！')
            return True
        if i % 60 == 0 and i > 0:
            print(f'  等待中... ({i//2}s)')

    return False

# ================ CRAWL ================
def crawl_stock(drv, name, code):
    pure = code[2:]
    print(f'\n=== {name} ({pure}) ===')

    drv.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
    time.sleep(3)

    if has_captcha(drv):
        solve_slider(drv)
        drv.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
        time.sleep(3)

    data = extract_json(drv.page_source, 'article_list')
    if not data:
        print('  无法获取帖子列表')
        return []

    posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0][:80]
    print(f'  {len(posts)} 个帖子有评论')

    result = []
    for i, p in enumerate(posts):
        pid = p['post_id']
        title = p.get('post_title', '')[:60]
        ncmt = p.get('post_comment_count', 0)
        print(f'  [{i+1}/{len(posts)}] {title}', end='', flush=True)

        time.sleep(random.uniform(2.0, 5.0))

        try:
            drv.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
            time.sleep(2)

            if has_captcha(drv):
                print(' SLIDER!', end='', flush=True)
                if not solve_slider(drv):
                    print(' TIMEOUT', flush=True); continue
                drv.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
                time.sleep(3)

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
                    cmts.append({'u': u, 'd': dt, 'l': lk, 'c': c})
                except: pass

            result.append({'id': pid, 'title': p.get('post_title', ''), 'body': body, 'cmts': cmts})
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
        logged_in = False
        for code, name in STOCKS:
            if name in all_data and len(all_data[name]) >= 50:
                print(f'{name}: 已完成 ({len(all_data[name])}条), 跳过')
                continue

            if not logged_in:
                logged_in = do_login(d)
                if not logged_in:
                    print('登录失败!')
                    break

            posts = crawl_stock(d, name, code)
            if posts:
                all_data[name] = posts
                with open(SAVE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2)

    except KeyboardInterrupt:
        print('\n中断!')
    finally:
        try: d.quit()
        except: pass

    total = sum(sum(len(x.get('cmts', x.get('comments', []))) for x in p) for p in all_data.values())
    print(f'\n=== 总计 {sum(len(p) for p in all_data.values())} posts, {total} comments ===')
