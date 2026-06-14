"""抓取完整的股吧评论（全文），存JSON"""
import time, json, re, os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = Options()
options.add_argument('--no-sandbox')
options.add_argument('--disable-blink-features=AutomationControlled')
temp_dir = 'C:/Users/xxc/.chrome_guba_login'
options.add_argument(f'--user-data-dir={temp_dir}')

stocks = {
    'sz002703': '浙江世宝',
    'sh688234': '天岳先进',
    'sh600703': '三安光电',
    'sh600172': '黄河旋风',
    'sz002920': '德赛西威',
}
pure_codes = {k: k[2:] for k in stocks}

driver = webdriver.Chrome(service=Service(), options=options)
all_data = {}

try:
    # 先去首页确认登录状态
    driver.get('https://guba.eastmoney.com/')
    time.sleep(2)
    logged = '退出' in driver.find_element(By.TAG_NAME, 'body').text[:500]
    print(f'Login status: {"LOGGED IN" if logged else "NOT LOGGED IN"}')

    for code, name in stocks.items():
        pure = pure_codes[code]
        print(f'\n{"="*40}')
        print(f'{name} ({pure})')
        print(f'{"="*40}')

        # 获取帖子列表
        driver.get(f'https://guba.eastmoney.com/list,{pure},f_1.html')
        time.sleep(3)

        html = driver.page_source
        m = re.search(r'article_list=(\{.+?\});\s*var\s+', html, re.DOTALL)
        if not m:
            print('  Failed to get post list')
            continue

        post_data = json.loads(m.group(1))
        # 只要第一页有评论的帖子
        posts_with_comments = [p for p in post_data.get('re', [])
                               if p.get('post_comment_count', 0) > 0]
        print(f'  Posts on page: {len(post_data.get("re",[]))}, with comments: {len(posts_with_comments)}')

        stock_posts = []
        for pidx, p in enumerate(posts_with_comments):
            post_id = p['post_id']
            post_title = p.get('post_title', '')
            post_author = p.get('post_user', {}).get('user_nickname', '')
            post_time = p.get('post_publish_time', '')
            post_clicks = p.get('post_click_count', 0)
            post_comment_count = p.get('post_comment_count', 0)

            print(f'  [{pidx+1}/{len(posts_with_comments)}] {post_title[:50]}... ({post_comment_count} comments)')

            try:
                driver.get(f'https://guba.eastmoney.com/news,{pure},{post_id}.html')
                time.sleep(3)

                # 等待评论加载
                try:
                    WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'div.reply_item'))
                    )
                except:
                    pass
                time.sleep(1)

                # 获取正文（全文，不截断）
                try:
                    post_body = driver.find_element(By.CSS_SELECTOR, 'div.xeditor_content').text
                except:
                    try:
                        post_body = driver.find_element(By.CSS_SELECTOR, '[class*="content"]').text
                    except:
                        post_body = ''

                # 获取所有评论（全文，不截断）
                reply_items = driver.find_elements(By.CSS_SELECTOR, 'div.reply_item')
                post_comments = []
                for item in reply_items:
                    try:
                        content = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
                        try:
                            likes = item.find_element(By.CSS_SELECTOR, 'span.likemodule').text
                        except:
                            likes = '0'
                        try:
                            date_el = item.find_element(By.CSS_SELECTOR, 'span.pubtime')
                            date = date_el.text
                        except:
                            date = ''
                        try:
                            user_el = item.find_element(By.CSS_SELECTOR, 'div.reply_user_name a')
                            user = user_el.text
                        except:
                            user = ''

                        post_comments.append({
                            'user': user,
                            'date': date,
                            'likes': likes,
                            'content': content,  # 全文
                        })
                    except:
                        pass

                stock_posts.append({
                    'post_id': post_id,
                    'post_title': post_title,
                    'post_author': post_author,
                    'post_time': post_time,
                    'post_clicks': post_clicks,
                    'post_comment_count': post_comment_count,
                    'post_body': post_body,  # 全文
                    'comments': post_comments,
                })
                print(f'    Got {len(post_comments)} comments, body={len(post_body)} chars')

            except Exception as e:
                print(f'    Error: {e}')

        all_data[name] = stock_posts
        print(f'  Total: {len(stock_posts)} posts, {sum(len(p["comments"]) for p in stock_posts)} comments')

    # 保存
    with open('J:/zss/stock/full_comments.json', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    total_c = sum(sum(len(c['comments']) for c in p) for p in all_data.values())
    print(f'\nDone! Total comments: {total_c}')

finally:
    driver.quit()
