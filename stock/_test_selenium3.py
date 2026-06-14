"""Test 3: Try without Chrome profile, check if guba loads properly"""
import json, time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option('excludeSwitches', ['enable-automation'])
# NO user-data-dir - fresh profile

driver = webdriver.Chrome(service=Service(), options=opts)

# Visit list page
driver.get('https://guba.eastmoney.com/list,002703,f_1.html')
time.sleep(5)
print(f'List page length: {len(driver.page_source)}')
print(f'Page title: {driver.title}')

# Check for article_list
source = driver.page_source
if 'article_list' in source:
    print('article_list FOUND')
    import re
    # Try to find and extract
    idx = source.find('article_list')
    print(f'article_list at: {idx}')
    print(source[idx:idx+200])

# Check for captcha
body_text = driver.find_element(By.TAG_NAME, 'body').text
for kw in ['验证', '滑块', 'captcha', '安全检测']:
    if kw in body_text:
        print(f'Captcha detected: {kw}')
        print(body_text[:500])
        break
else:
    print('No captcha detected')

# Check what's rendered
items = driver.find_elements(By.CSS_SELECTOR, '.article_list li, .list_item, [class*="article"]')
print(f'\nArticle-like elements: {len(items)}')
if items:
    for item in items[:3]:
        print(f'  text: {item.text[:100]}')
        print(f'  class: {item.get_attribute("class")}')

# Visit a post page
driver.get('https://guba.eastmoney.com/news,002703,1719194845.html')
time.sleep(5)
print(f'\nPost page length: {len(driver.page_source)}')
print(f'Post page title: {driver.title}')

if 'post_article' in driver.page_source:
    print('post_article FOUND')
elif 'reply_item' in driver.page_source:
    print('reply_item FOUND')

body_text = driver.find_element(By.TAG_NAME, 'body').text[:500]
print(f'Body text (first 500): {body_text}')

driver.quit()
print('Done')
