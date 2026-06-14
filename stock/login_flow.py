"""打开登录页，自动填手机号获取验证码，用户手动过滑块+输验证码，登录后自动抓评论"""
import time, json, re, os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = Options()
options.add_argument('--no-sandbox')
temp_dir = 'C:/Users/xxc/.chrome_guba_login'
options.add_argument(f'--user-data-dir={temp_dir}')

PHONE = '17779911413'

print('Starting Chrome...')
driver = webdriver.Chrome(service=Service(), options=options)

try:
    # === 检测是否已登录 ===
    driver.get('https://guba.eastmoney.com/')
    time.sleep(2)
    body = driver.find_element(By.TAG_NAME, 'body').text

    if '退出' in body[:500] and '登录' not in body[:200]:
        print('Already logged in!')
    else:
        print('Not logged in, starting login flow...')

        # 去登录页面
        driver.get('https://passport2.eastmoney.com/pub/login?backurl=https://guba.eastmoney.com/')
        time.sleep(3)
        print(f'Login page: {driver.current_url[:80]}')

        # 切换到手机登录 tab
        try:
            tabs = driver.find_elements(By.CSS_SELECTOR, '.login-type-item, [data-type], .tab_item')
            for t in tabs:
                if '手机' in t.text or '短信' in t.text:
                    t.click()
                    time.sleep(1)
                    print('Switched to phone login')
                    break
        except Exception as e:
            print(f'Tab switch: {e}')

        # 输入手机号
        try:
            phone_input = driver.find_element(By.CSS_SELECTOR,
                'input[type="tel"], input[placeholder*="手机"], input[name*="phone"], input[name*="mobile"], input[class*="phone"]')
            phone_input.clear()
            phone_input.send_keys(PHONE)
            print(f'Entered phone: {PHONE}')
        except Exception as e:
            print(f'Phone input failed: {e}')

        # 点击获取验证码
        try:
            send_btn = driver.find_element(By.CSS_SELECTOR,
                'button[class*="sms"], button[class*="code"], [class*="getSms"], [class*="send_sms"], span[class*="code_btn"]')
            send_btn.click()
            print('Sent verification code!')
        except Exception as e:
            print(f'Send code failed: {e}')

        # === 等待用户手动完成滑块+输入验证码 ===
        print('\n>>> 请在浏览器中完成滑块验证并输入验证码 <<<')
        print('>>> 完成后脚本自动检测登录状态...\n')

        for i in range(600):  # 最多等5分钟
            time.sleep(0.5)
            try:
                cur_body = driver.find_element(By.TAG_NAME, 'body').text
                if '退出' in cur_body[:800] and '登录' not in cur_body[:200]:
                    print('Login detected!')
                    break
            except:
                pass
            if i % 60 == 0 and i > 0:
                print(f'  waiting for login... ({i//2}s)')

    time.sleep(1)

    # === 保存 cookie ===
    cookies = driver.get_cookies()
    cookie_file = 'J:/zss/stock/guba_auth_cookies.json'
    with open(cookie_file, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f'Saved {len(cookies)} cookies to {cookie_file}')

    # === 抓取全量评论 ===
    stocks = {
        'sz002703': '浙江世宝',
        'sh688234': '天岳先进',
        'sh600703': '三安光电',
        'sh600172': '黄河旋风',
        'sz002920': '德赛西威',
    }

    all_data = {}

    for code, name in stocks.items():
        pure = code[2:]
        print(f'\n=== {name} ({pure}) ===')

        driver.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
        time.sleep(3)

        m = re.search(r'article_list=(\{.+?\});\s*var\s+', driver.page_source, re.DOTALL)
        if not m:
            print('  Failed to get posts')
            continue

        post_data = json.loads(m.group(1))
        posts = [p for p in post_data.get('re', []) if p.get('post_comment_count', 0) > 0]
        print(f'  {len(posts)} posts with comments')

        stock_posts = []
        for pi, p in enumerate(posts):
            pid = p['post_id']
            ptitle = p.get('post_title', '')[:60]
            pcmt = p.get('post_comment_count', 0)
            print(f'  [{pi+1}/{len(posts)}] {ptitle}... ({pcmt}cmt)')

            try:
                driver.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
                time.sleep(3)

                # 正文
                try:
                    post_body = driver.find_element(By.CSS_SELECTOR, 'div.xeditor_content').text
                except:
                    post_body = ''

                # 评论
                items = driver.find_elements(By.CSS_SELECTOR, 'div.reply_item')
                comments = []
                for item in items:
                    try:
                        content = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
                        try:
                            likes = item.find_element(By.CSS_SELECTOR, 'span.likemodule').text
                        except:
                            likes = '0'
                        try:
                            dt = item.find_element(By.CSS_SELECTOR, 'span.pubtime').text
                        except:
                            dt = ''
                        try:
                            user = item.find_element(By.CSS_SELECTOR, 'div.reply_user_name a').text
                        except:
                            user = ''
                        comments.append({'user': user, 'date': dt, 'likes': likes, 'content': content})
                    except:
                        pass

                stock_posts.append({
                    'post_id': pid,
                    'post_title': p.get('post_title', ''),
                    'post_body': post_body,
                    'comments': comments,
                })
                print(f'    {len(comments)} cmt, {len(post_body)} chars body')

            except Exception as e:
                print(f'    Error: {e}')

        all_data[name] = stock_posts
        total_c = sum(len(x['comments']) for x in stock_posts)
        print(f'  >> {len(stock_posts)} posts, {total_c} comments')

    output_file = 'J:/zss/stock/full_comments.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    grand = sum(sum(len(c['comments']) for c in p) for p in all_data.values())
    print(f'\n=== ALL DONE: {grand} total comments saved to {output_file} ===')

finally:
    driver.quit()
