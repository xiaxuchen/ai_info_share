"""先用 Edge 测试 guba 评论页面加载"""
import time, json
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

options = Options()
# 不用 headless，先看看能不能加载评论

driver = webdriver.Edge(options=options)
try:
    # 加载一个有评论的帖子
    url = 'https://guba.eastmoney.com/news,002703,1712037378.html'
    print(f'Loading: {url}')
    driver.get(url)
    time.sleep(5)  # 等JS加载评论

    # 检查页面元素
    html = driver.page_source

    # 搜索评论相关的元素
    for cls in ['reply_item', 'replylist_content', 'allReplyList', 'recont_right', 'reply_title']:
        elements = driver.find_elements(By.CLASS_NAME, cls)
        print(f'  .{cls}: {len(elements)} elements')

    # 搜索包含"reply"的文本
    for elem in driver.find_elements(By.CSS_SELECTOR, '[class*="reply"]'):
        text = elem.text.strip()[:80]
        if text:
            print(f'  Reply element: {text}')
            if len([t for t in [e.text.strip() for e in driver.find_elements(By.CSS_SELECTOR, '[class*="reply"]')] if t]) > 3:
                break

    print('\nPage title:', driver.title)

    # 检查页面中是否有评论内容
    page_text = driver.find_element(By.TAG_NAME, 'body').text
    print(f'Body text length: {len(page_text)}')
    # 打印前500个字符
    print(f'Body preview: {page_text[:500]}')

    # Save page HTML for inspection
    with open('J:/zss/stock/guba_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print('Page saved to guba_page.html')

finally:
    driver.quit()
