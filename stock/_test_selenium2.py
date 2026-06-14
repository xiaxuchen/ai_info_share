"""Test 2: Longer wait, scroll, check network for comment loading"""
import json, time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option('excludeSwitches', ['enable-automation'])
opts.add_argument('--user-data-dir=C:/Users/xxc/.chrome_guba_login')

# Enable performance logging to capture network requests
opts.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

driver = webdriver.Chrome(service=Service(), options=opts)

# Visit list page first
driver.get('https://guba.eastmoney.com/list,002703,f_1.html')
time.sleep(3)
print('List page loaded')

# Now visit a post page with known comments
driver.get('https://guba.eastmoney.com/news,002703,1719194845.html')
print('Post page loading...')
time.sleep(5)  # Longer wait

# Scroll down to trigger lazy loading
driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
time.sleep(3)
driver.execute_script('window.scrollTo(0, 0);')
time.sleep(1)
driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
time.sleep(3)

# Check for various comment selectors
for selector in [
    'div.reply_item',
    'div.reply_text',
    'div.reply_content',
    '[class*="reply"]',
    '[class*="comment"]',
    'div.article_reply',
    'div.reply_list',
    'div#reply_list',
]:
    items = driver.find_elements(By.CSS_SELECTOR, selector)
    if items:
        print(f'  {selector}: {len(items)} items')
        for item in items[:2]:
            try:
                print(f'    text: {item.text[:100]}')
            except:
                pass

# Check page source for comment-related JSON
source = driver.page_source
import re
json_vars = re.findall(r'var\s+(\w+)\s*=', source)
print(f'\nJS vars: {sorted(set(json_vars))}')

# Look for any comment count in page
cmt_refs = re.findall(r'comment[^=]*=\s*\d+', source)
print(f'Comment refs: {cmt_refs[:5]}')

# Check network logs for API calls
logs = driver.get_log('performance')
api_urls = set()
for entry in logs:
    try:
        msg = json.loads(entry['message'])
        url = msg.get('message', {}).get('params', {}).get('request', {}).get('url', '')
        if 'reply' in url or 'comment' in url or 'ArticleNewReply' in url:
            api_urls.add(url)
    except:
        pass
print(f'\nComment API URLs in network: {api_urls}')

driver.quit()
print('Done')
