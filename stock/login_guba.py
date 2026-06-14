"""自动检测股吧登录，成功后就抓评论写到飞书"""
import time, json, os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

options = Options()
options.add_argument('--no-sandbox')

temp_dir = 'C:/Users/xxc/.chrome_guba_login'
options.add_argument(f'--user-data-dir={temp_dir}')

print('正在启动 Chrome...')
driver = webdriver.Chrome(service=Service(), options=options)

try:
    # 打开股吧登录页
    driver.get('https://guba.eastmoney.com/')
    print('\n>>> 请在浏览器窗口扫码登录股吧 <<<\n')

    # 自动等待登录完成（最多等 120 秒）
    logged_in = False
    for i in range(240):
        time.sleep(0.5)
        try:
            # 检查是否出现"退出"链接（登录成功标志）
            body_text = driver.find_element(By.TAG_NAME, 'body').text
            if '退出' in body_text[:800] and '登录' not in body_text[:200]:
                logged_in = True
                print('登录成功！')
                break
            # 也检查是否有用户昵称显示
            try:
                nick_el = driver.find_element(By.CSS_SELECTOR, '.username, .nickname, [class*="nick"]')
                if nick_el.text.strip():
                    logged_in = True
                    print(f'登录成功！欢迎 {nick_el.text.strip()}')
                    break
            except:
                pass
        except:
            pass

        if i % 20 == 0 and i > 0:
            print(f'  等待登录中... ({i//2}秒)')

    if not logged_in:
        print('超时未检测到登录，但你也可以继续...')

    time.sleep(1)

    # 保存 cookie
    all_cookies = driver.get_cookies()
    with open('J:/zss/stock/guba_auth_cookies.json', 'w', encoding='utf-8') as f:
        json.dump(all_cookies, f, ensure_ascii=False, indent=2)
    print(f'已保存 {len(all_cookies)} 个 cookie')

    # ========================
    # 抓取评论
    # ========================
    stocks = {
        'sz002703': '浙江世宝',
        'sh688234': '天岳先进',
        'sh600703': '三安光电',
        'sh600172': '黄河旋风',
        'sz002920': '德赛西威',
    }

    pure_codes = {k: k[2:] for k in stocks}

    all_comments = {}

    for code, name in stocks.items():
        pure = pure_codes[code]
        print(f'\n=== {name} ({pure}) ===')

        # 先获取帖子列表（从页面JSON）
        driver.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
        time.sleep(3)

        # 提取 article_list JSON
        html = driver.page_source
        import re
        m = re.search(r'article_list=(\{.+?\});\s*var\s+', html, re.DOTALL)
        if not m:
            print('  获取帖子列表失败')
            continue

        post_data = json.loads(m.group(1))
        posts = post_data.get('re', [])
        posts_with_comments = [p for p in posts if p.get('post_comment_count', 0) > 0][:10]
        print(f'  找到 {len(posts)} 条帖子，{len(posts_with_comments)} 条有评论')

        stock_comments = []
        for p in posts_with_comments[:5]:  # 最多处理5个帖子
            post_id = p['post_id']
            post_title = p.get('post_title', '')[:50]

            try:
                # 调用评论 API
                driver.get(f'https://guba.eastmoney.com/news,{pure},{post_id}.html')
                time.sleep(3)

                # 提取评论
                reply_items = driver.find_elements(By.CSS_SELECTOR, 'div.reply_item')
                if reply_items:
                    for item in reply_items:
                        try:
                            content = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
                            stock_comments.append({
                                'post_title': post_title,
                                'content': content[:200],
                            })
                        except:
                            pass
            except Exception as e:
                pass

        print(f'  抓到 {len(stock_comments)} 条评论')
        all_comments[name] = stock_comments

    # 保存评论
    with open('J:/zss/stock/guba_comments.json', 'w', encoding='utf-8') as f:
        json.dump(all_comments, f, ensure_ascii=False, indent=2)
    print(f'\n评论已保存到 guba_comments.json')

finally:
    driver.quit()
