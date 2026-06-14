"""用用户已登录的 Chrome 抓取股吧评论 - 可见窗口模式"""
import time, json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = Options()
options.add_argument('--user-data-dir=C:/Users/xxc/AppData/Local/Google/Chrome/User Data')
options.add_argument('--no-sandbox')
# 不用 headless，直接显示窗口

driver = webdriver.Chrome(service=Service(), options=options)
try:
    # 加载一个有评论的帖子
    url = 'https://guba.eastmoney.com/news,002703,1712037378.html'
    print(f'Loading: {url}')
    driver.get(url)

    # 等评论加载
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.reply_item'))
        )
        print('Comments loaded!')
    except:
        print('Timeout - checking page state...')

    time.sleep(2)

    # 提取评论
    reply_items = driver.find_elements(By.CSS_SELECTOR, 'div.reply_item')
    print(f'Reply items: {len(reply_items)}')

    comments = []
    for item in reply_items:
        try:
            # 评论内容
            content = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
            # 点赞数
            try:
                likes = item.find_element(By.CSS_SELECTOR, 'span.likemodule').text
            except:
                likes = '0'
            # 时间
            try:
                date_el = item.find_element(By.CSS_SELECTOR, 'span.pubtime')
                date = date_el.text
            except:
                date = ''
            # 用户名
            try:
                user_el = item.find_element(By.CSS_SELECTOR, 'div.reply_user_name a')
                user = user_el.text
            except:
                user = ''

            comments.append({
                'content': content[:200],
                'likes': likes,
                'date': date,
                'user': user
            })
        except Exception as e:
            pass

    for i, c in enumerate(comments[:10]):
        print(f'  [{i}] {c["date"]} @{c["user"]} 赞{c["likes"]}')
        print(f'       {c["content"][:120]}')

    # 保存结果
    result = {
        'post_url': url,
        'comment_count': len(comments),
        'comments': comments
    }
    with open('J:/zss/stock/test_comments.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'\nSaved {len(comments)} comments to test_comments.json')

finally:
    driver.quit()
