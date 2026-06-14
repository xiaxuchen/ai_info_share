"""打开浏览器让你登录股吧，登录后自动抓全量评论并写入飞书"""
import time, json, re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

options = Options()
options.add_argument('--no-sandbox')
temp_dir = 'C:/Users/xxc/.chrome_guba_login'
options.add_argument(f'--user-data-dir={temp_dir}')

print('Starting Chrome...')
driver = webdriver.Chrome(service=Service(), options=options)

try:
    driver.get('https://guba.eastmoney.com/')
    print('\n>>> 请在浏览器窗口登录股吧（手机号+验证码+滑块） <<<')
    print('>>> 完成后自动检测登录状态...\n')

    # 等登录
    for i in range(300):
        time.sleep(0.5)
        try:
            body = driver.find_element(By.TAG_NAME, 'body').text
            if '退出' in body[:800] and '登录' not in body[:200]:
                print('Login detected!')
                break
        except: pass
        if i % 40 == 0 and i > 0:
            print(f'  waiting... ({i//2}s)')

    time.sleep(1)

    # 保存 cookie
    cookies = driver.get_cookies()
    with open('J:/zss/stock/guba_auth_cookies.json', 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f'Saved {len(cookies)} cookies')

    # ========== 抓取全量评论 ==========
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
            print('  Failed')
            continue

        post_data = json.loads(m.group(1))
        posts = [p for p in post_data.get('re', []) if p.get('post_comment_count', 0) > 0]
        print(f'  {len(posts)} posts with comments')

        stock_posts = []
        for pi, p in enumerate(posts):
            pid = p['post_id']
            print(f'  [{pi+1}/{len(posts)}] {p.get("post_title","")[:50]}... ({p.get("post_comment_count")}cmt)')
            try:
                driver.get(f'https://guba.eastmoney.com/news,{pure},{pid}.html')
                time.sleep(3)

                # 正文全文
                try:
                    body_el = driver.find_element(By.CSS_SELECTOR, 'div.xeditor_content')
                    post_body = body_el.text
                except:
                    post_body = ''

                # 评论全文
                items = driver.find_elements(By.CSS_SELECTOR, 'div.reply_item')
                comments = []
                for item in items:
                    try:
                        c = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text  # 全文不截断
                        try:
                            likes = item.find_element(By.CSS_SELECTOR, 'span.likemodule').text
                        except:
                            likes = '0'
                        try:
                            d = item.find_element(By.CSS_SELECTOR, 'span.pubtime').text
                        except:
                            d = ''
                        try:
                            u = item.find_element(By.CSS_SELECTOR, 'div.reply_user_name a').text
                        except:
                            u = ''
                        comments.append({'user': u, 'date': d, 'likes': likes, 'content': c})
                    except:
                        pass

                stock_posts.append({
                    'post_id': pid,
                    'post_title': p.get('post_title', ''),
                    'post_body': post_body,
                    'comments': comments,
                })
                print(f'    {len(comments)} comments, body={len(post_body)} chars')

            except Exception as e:
                print(f'    Error: {e}')

        all_data[name] = stock_posts
        total_c = sum(len(x['comments']) for x in stock_posts)
        print(f'  >> {len(stock_posts)} posts, {total_c} comments')

    with open('J:/zss/stock/full_comments.json', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    grand = sum(sum(len(c['comments']) for c in p) for p in all_data.values())
    print(f'\n=== ALL DONE: {grand} comments ===')

finally:
    driver.quit()
