#!/usr/bin/env python3
"""
股吧全自动：登录 + OpenCV滑块破解 + 评论爬取 + 写入飞书
"""
import time, json, re, os, sys, io, random, base64
import cv2, numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ====================== CONFIG ======================
PHONE = '17779911413'
STOCKS = {
    'sz002703': '浙江世宝',
    'sh688234': '天岳先进',
    'sh600703': '三安光电',
    'sh600172': '黄河旋风',
    'sz002920': '德赛西威',
}
SAVE_FILE = 'J:/zss/stock/full_comments.json'
STEALTH_JS = os.path.join(os.path.dirname(__file__), 'EastMoney_Crawler-main', 'stealth.min.js')
PROFILE_DIR = 'C:/Users/xxc/.chrome_guba'
MAX_POSTS = 80
VALID_THRESHOLD = 50

# ====================== DRIVER ======================
def make_options():
    opts = Options()
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_argument(f'--user-data-dir={PROFILE_DIR}')
    # opts.add_argument('--headless=new')
    return opts

def make_driver():
    d = webdriver.Chrome(service=Service(), options=make_options())
    if os.path.exists(STEALTH_JS):
        with open(STEALTH_JS) as f:
            d.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': f.read()})
    # 隐藏webdriver特征
    d.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return d

# ====================== SLIDER CAPTCHA SOLVER ======================
def find_slider_button(drv):
    """找到滑块按钮元素"""
    selectors = [
        '.yidun_slider', '.yidun_slide_indicator', '.yidun_slider__indicator',
        '[class*="slider-btn"]', '[class*="slide-btn"]', '.slider-btn',
        '.captcha-slider-btn', '.yidun_slider-btn'
    ]
    for sel in selectors:
        els = drv.find_elements(By.CSS_SELECTOR, sel)
        if els: return els[0]
    return None

def find_captcha_images(drv):
    """找滑块验证码的背景图和拼图"""
    imgs = drv.find_elements(By.CSS_SELECTOR, 'img.yidun_bg-img, img.yidun_jigsaw, canvas, .yidun_bg-img img, .yidun_jigsaw img')
    bg_src = None
    jigsaw_src = None
    for img in drv.find_elements(By.TAG_NAME, 'img'):
        src = img.get_attribute('src') or ''
        cl = img.get_attribute('class') or ''
        if ('bg' in cl or 'back' in cl or 'background' in cl) and not bg_src:
            bg_src = src
        if ('jigsaw' in cl or 'piece' in cl or 'slider' in cl or 'block' in cl) and not jigsaw_src:
            jigsaw_src = src
    return bg_src, jigsaw_src

def solve_slider_captcha(drv, max_attempts=3):
    """用OpenCV破解滑块验证码"""
    print('    *** 检测到滑块验证码，尝试自动破解...', flush=True)

    for attempt in range(max_attempts):
        try:
            # 方式1：找滑动条容器
            sliders = drv.find_elements(By.CSS_SELECTOR, '.yidun_slider, [class*="slider-wrap"], [class*="slide-verify"]')
            if not sliders:
                sliders = drv.find_elements(By.CSS_SELECTOR, 'div[class*="yidun"]')

            if not sliders:
                # 尝试通过截图找滑块
                driver_screenshot = drv.get_screenshot_as_png()
                nparr = np.frombuffer(driver_screenshot, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                h, w = img.shape[:2]

                # 在底部区域找滑块（通常在40%-70%高度位置）
                bottom_half = img[int(h*0.35):int(h*0.75), :]

                # 转灰度找边缘
                gray = cv2.cvtColor(bottom_half, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150)

                # 找轮廓
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                # 找到可能的滑块（左右对称的矩形）
                slider_rect = None
                for cnt in contours:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    if 50 < cw < 200 and 40 < ch < 80:
                        slider_rect = (x, y + int(h*0.35), cw, ch)
                        break

                if not slider_rect:
                    print(f'    无法找到滑块元素 (attempt {attempt+1})', flush=True)
                    time.sleep(2)
                    continue

                print(f'    找到滑块区域: {slider_rect}', flush=True)

                # 用模板匹配找缺口
                slider_crop = img[slider_rect[1]:slider_rect[1]+slider_rect[3],
                                 slider_rect[0]:slider_rect[0]+slider_rect[2]]
                # 在背景中找匹配
                result = cv2.matchTemplate(img[int(h*0.2):int(h*0.7), :],
                                          slider_crop, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                distance = max_loc[0] - slider_rect[0]
                print(f'    计算滑动距离: {distance}px', flush=True)

                # 找可拖动的滑块元素
                slider_btn = find_slider_button(drv)
                if not slider_btn:
                    print('    找不到滑块拖动按钮', flush=True)
                    continue

                # 用ActionChains模拟人类拖动
                action = ActionChains(drv)
                action.click_and_hold(slider_btn).perform()
                time.sleep(0.1)

                # 模拟人类轨迹：加速-匀速-减速
                tracks = []
                current = 0
                while current < distance:
                    if current < distance * 0.3:
                        # 加速阶段
                        step = random.randint(3, 8)
                    elif current < distance * 0.8:
                        # 匀速阶段
                        step = random.randint(5, 10)
                    else:
                        # 减速阶段
                        step = random.randint(1, 3)
                    current += step
                    if current > distance:
                        current = distance
                    tracks.append(current)

                last_x = 0
                for t in tracks:
                    offset = t - last_x
                    action.move_by_offset(offset, random.randint(-1, 1)).perform()
                    time.sleep(random.uniform(0.005, 0.015))
                    last_x = t

                # 稍微超过一点再回拉（模仿人类）
                action.move_by_offset(random.randint(-3, 3), 0).perform()
                time.sleep(0.3)
                action.release().perform()

                time.sleep(2)

                # 检查是否成功
                if not has_captcha(drv):
                    print('    *** 滑块破解成功! ***', flush=True)
                    return True
                else:
                    print(f'    滑块验证失败，重试... ({attempt+1})', flush=True)
                    time.sleep(1)

            else:
                # 方式2：有明确的滑块容器
                container = sliders[0]
                # 获取滑块背景图
                bg_img = container.find_elements(By.CSS_SELECTOR, 'img[class*="bg"], canvas[class*="bg"]')
                jigsaw_img = container.find_elements(By.CSS_SELECTOR, 'img[class*="jigsaw"], canvas[class*="jigsaw"]')

                if bg_img and jigsaw_img:
                    bg_b64 = bg_img[0].get_attribute('src')
                    jigsaw_b64 = jigsaw_img[0].get_attribute('src')

                    if bg_b64 and jigsaw_b64 and 'base64' in bg_b64:
                        # Decode base64 images
                        bg_data = base64.b64decode(bg_b64.split(',')[1])
                        jigsaw_data = base64.b64decode(jigsaw_b64.split(',')[1])

                        bg_arr = np.frombuffer(bg_data, np.uint8)
                        jigsaw_arr = np.frombuffer(jigsaw_data, np.uint8)
                        bg = cv2.imdecode(bg_arr, cv2.IMREAD_GRAYSCALE)
                        jigsaw = cv2.imdecode(jigsaw_arr, cv2.IMREAD_GRAYSCALE)

                        res = cv2.matchTemplate(bg, jigsaw, cv2.TM_CCOEFF_NORMED)
                        _, _, _, max_loc = cv2.minMaxLoc(res)
                        distance = max_loc[0]
                        print(f'    模板匹配距离: {distance}px', flush=True)

                        # 获取实际的拖动距离（需要按网页缩放比例转换）
                        # 通常bg_img的width等于container的width
                        container_w = container.size['width']
                        bg_w = bg_img[0].size['width']
                        scale = container_w / bg_w if bg_w else 1
                        distance = int(distance * scale)
                        print(f'    缩放后距离: {distance}px', flush=True)

                        slider_btn = find_slider_button(drv)
                        if slider_btn:
                            action = ActionChains(drv)
                            action.click_and_hold(slider_btn).perform()
                            time.sleep(0.1)

                            # 模拟人类拖动轨迹
                            tracks = []
                            t = 0
                            while t < distance:
                                if t < distance * 0.2:
                                    s = random.randint(2, 5)
                                elif t < distance * 0.7:
                                    s = random.randint(4, 8)
                                else:
                                    s = random.randint(1, 3)
                                t += s
                                if t > distance: t = distance
                                tracks.append(t)

                            last = 0
                            for t in tracks:
                                action.move_by_offset(t - last, random.randint(-1, 1)).perform()
                                time.sleep(random.uniform(0.005, 0.012))
                                last = t

                            action.move_by_offset(random.randint(-2, 2), 0).perform()
                            time.sleep(0.3)
                            action.release().perform()

                            time.sleep(2)
                            if not has_captcha(drv):
                                print('    *** 滑块破解成功! ***', flush=True)
                                return True

        except Exception as e:
            print(f'    滑块破解异常: {e}', flush=True)
            time.sleep(2)

    print('    *** 滑块自动破解失败，需手动解决 ***', flush=True)
    return False


# ====================== UTILS ======================
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
        t = drv.find_element(By.TAG_NAME, 'body').text[:2000]
        for kw in ['请完成验证', '滑动验证', '请按住滑块', '验证码', '拖动滑块', '安全验证']:
            if kw in t: return True
    except: pass
    return False

def has_captcha_or_login(drv):
    """检测是否有滑块或登录按钮（未登录）"""
    try:
        t = drv.find_element(By.TAG_NAME, 'body').text[:1000]
        if '退出' in t and '登录' not in t[:200]:
            return 'logged_in'
        for kw in ['请完成验证', '滑动验证', '请按住滑块', '验证码', '拖动滑块']:
            if kw in t: return 'captcha'
        return 'ok'
    except: return 'error'

# ====================== LOGIN ======================
def do_login(drv):
    """自动登录股吧"""
    print('\n=== 开始登录流程 ===')

    # 直接去东方财富统一登录页
    drv.get('https://passport2.eastmoney.com/pub/login?backurl=https://guba.eastmoney.com/')
    time.sleep(4)

    print(f'Login page: {drv.current_url[:80]}')

    # 切换到短信登录 iframe
    iframe = None
    for frame in drv.find_elements(By.TAG_NAME, 'iframe'):
        src = frame.get_attribute('src') or ''
        if 'exaccount' in src or 'login' in src:
            iframe = frame
            break
    if not iframe:
        # 如果没找到login iframe，可能已经登录
        body = drv.find_element(By.TAG_NAME, 'body').text
        if '退出' in body[:800] and '登录' not in body[:200]:
            print('已登录！')
            return True
        print('找不到登录iframe！')
        with open('J:/zss/stock/login_page.html', 'w', encoding='utf-8') as f:
            f.write(drv.page_source)
        print('页面已保存，请手动登录')
        return False

    drv.switch_to.frame(iframe)
    time.sleep(2)
    print('切换到登录iframe')

    # 点"手机登录"tab
    for el in drv.find_elements(By.CSS_SELECTOR, 'span, div, a'):
        t = el.text.strip()
        if t in ['手机登录', '短信登录', '手机', '短信']:
            try:
                el.click()
                time.sleep(1)
                print('切换到手机登录')
                break
            except: pass

    # 找手机号输入框（iframe内）
    phone_input = None
    for el in drv.find_elements(By.CSS_SELECTOR, 'input'):
        tp = el.get_attribute('type') or 'text'
        ph = el.get_attribute('placeholder') or ''
        nm = el.get_attribute('name') or ''
        if tp == 'tel' or '手机' in ph or '号码' in ph or 'phone' in ph.lower() or 'mobile' in nm.lower():
            phone_input = el
            break

    if phone_input:
        # 用JS设置值，避免元素不可交互的问题
        try:
            drv.execute_script('arguments[0].value = arguments[1]', phone_input, PHONE)
            # 触发input事件
            drv.execute_script('arguments[0].dispatchEvent(new Event("input", {bubbles: true})); arguments[0].dispatchEvent(new Event("change", {bubbles: true}))', phone_input)
        except:
            phone_input.send_keys(PHONE)
        print(f'输入手机号: {PHONE}')
    else:
        print('找不到手机号输入框！请手动输入')
        with open('J:/zss/stock/login_frame.html', 'w', encoding='utf-8') as f:
            f.write(drv.page_source)
        drv.switch_to.default_content()
        return False

    # 点获取验证码 - 按ID查找最可靠
    time.sleep(1)
    send_btn = None
    for sel in ['#btn_getvcode', 'input[value*="获取"]', 'input[value*="验证码"]',
                '.login_vcode', '[class*="vcode"]']:
        els = drv.find_elements(By.CSS_SELECTOR, sel)
        if els:
            send_btn = els[0]
            break
    if not send_btn:
        for el in drv.find_elements(By.CSS_SELECTOR, 'input[type="button"], button, span, a'):
            t = el.text.strip() or el.get_attribute('value') or ''
            if t in ['获取验证码', '发送验证码', '获取']:
                send_btn = el
                break

    if send_btn:
        try:
            send_btn.click()
            print('点击发送验证码')
        except:
            # 用JS点
            drv.execute_script('arguments[0].click()', send_btn)
            print('JS点击发送验证码')
        time.sleep(3)
    else:
        print('找不到发送按钮！保存页面用于调试')
        with open('J:/zss/stock/login_frame.html', 'w', encoding='utf-8') as f:
            f.write(drv.page_source)
        drv.switch_to.default_content()
        return False

    drv.switch_to.default_content()

    # 检查并处理滑块验证
    if has_captcha(drv):
        print('发送验证码前需要滑块验证')
        if not solve_slider_captcha(drv):
            print('滑块自动破解失败，请在浏览器中手动完成...')
            for _ in range(180):
                time.sleep(1)
                if not has_captcha(drv):
                    print('滑块已手动解决！')
                    # 重新点发送
                    if send_btn:
                        try: send_btn.click()
                        except: pass
                        time.sleep(2)
                    break
            else:
                print('滑块超时未解决')
                return False

    # 用户在浏览器中手动输入验证码、过滑块、完成登录
    print(f'\n{"="*50}')
    print(f'验证码已发送到 {PHONE}')
    print(f'请在浏览器中：输入验证码 + 过滑块 + 点击登录')
    print(f'{"="*50}')
    print('等待登录完成...')
    for _ in range(180):
        time.sleep(1)
        try:
            body = drv.find_element(By.TAG_NAME, 'body').text
            if '退出' in body[:800] and '登录' not in body[:200]:
                print('检测到登录成功！')
                return True
        except: pass

    return False

# ====================== CRAWL ======================
def crawl_stock(drv, name, code, pure):
    print(f'\n=== {name} ({pure}) ===')

    # 先清理可能的滑块
    if has_captcha(drv):
        solve_slider_captcha(drv)

    drv.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
    time.sleep(3)

    if has_captcha(drv):
        if not solve_slider_captcha(drv):
            print('  滑块超时，跳过该股票')
            return []
        drv.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
        time.sleep(3)

    data = extract_json(drv.page_source, 'article_list')
    if not data:
        print('  无法获取帖子列表')
        return []

    posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0][:MAX_POSTS]
    print(f'  {len(posts)} posts with comments')

    stock_posts = []
    for pi, p in enumerate(posts):
        pid = p['post_id']
        ptitle = p.get('post_title', '')[:60]
        pcmt = p.get('post_comment_count', 0)
        print(f'  [{pi+1}/{len(posts)}] {ptitle}', flush=True, end='')

        delay = random.uniform(2.0, 5.0)
        time.sleep(delay)

        try:
            drv.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
            time.sleep(2)

            if has_captcha(drv):
                print(' CAPTCHA!', end='', flush=True)
                if not solve_slider_captcha(drv):
                    print(' TIMEOUT', flush=True)
                    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
                        json.dump({'temp': stock_posts}, f, ensure_ascii=False)
                    continue
                drv.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
                time.sleep(3)

            article = extract_json(drv.page_source, 'post_article')
            post_body = strip_html(article.get('post_content', '')) if article else ''

            try:
                WebDriverWait(drv, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.reply_item')))
            except: pass

            items = drv.find_elements(By.CSS_SELECTOR, 'div.reply_item')
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
            print(f' -> {len(comments)}cmt', flush=True)

        except Exception as e:
            print(f' ERR:{e}', flush=True)

    print(f'  DONE: {len(stock_posts)} posts, {sum(len(x["comments"]) for x in stock_posts)} comments')
    return stock_posts



# ====================== MAIN ======================
if __name__ == '__main__':
    driver = make_driver()

    all_data = {}
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
            if 'temp' in all_data: del all_data['temp']
            print(f'Loaded: {list(all_data.keys())}')
        except: pass

    try:
        # ===== LOGIN =====
        logged_in = False
        for name, code in STOCKS.items():
            pure = code[2:]
            if name in all_data and len(all_data[name]) >= VALID_THRESHOLD:
                print(f'{name}: already done ({len(all_data[name])} posts), skip')
                continue

            if not logged_in:
                # Try to login if not already done
                driver.get('https://guba.eastmoney.com/')
                time.sleep(3)
                status = has_captcha_or_login(driver)
                if status != 'logged_in':
                    logged_in = do_login(driver)
                    if not logged_in:
                        print('登录失败，退出')
                        break
                    # 先处理滑块
                    if has_captcha(driver):
                        solve_slider_captcha(driver)
                else:
                    logged_in = True
                    print('检测到已登录状态')

            posts = crawl_stock(driver, name, code, pure)
            if posts:
                all_data[name] = posts
                with open(SAVE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2)

    except KeyboardInterrupt:
        print('\nInterrupted, saving...')
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

    finally:
        try: driver.quit()
        except: pass

    grand = sum(sum(len(c['comments']) for c in p) for p in all_data.values())
    print(f'\nDONE: {sum(len(p) for p in all_data.values())} posts, {grand} comments')
