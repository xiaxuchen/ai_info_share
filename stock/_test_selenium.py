import json, time, re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option('excludeSwitches', ['enable-automation'])
opts.add_argument('--user-data-dir=C:/Users/xxc/.chrome_guba_login')

driver = webdriver.Chrome(service=Service(), options=opts)

driver.get('https://guba.eastmoney.com/list,002703,f_1.html')
time.sleep(3)

def extract_json(html, var_name):
    idx = html.find(var_name + '=')
    if idx < 0: return None
    start = html.find('{', idx)
    if start < 0: return None
    depth = 0; in_str = False; esc = False; end = start
    for i in range(start, len(html)):
        ch = html[i]
        if esc: esc = False; continue
        if ch == chr(92): esc = True; continue
        if ch == '"': in_str = not in_str; continue
        if in_str: continue
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: end = i + 1; break
    if end <= start: return None
    try: return json.loads(html[start:end])
    except: return None

data = extract_json(driver.page_source, 'article_list')
posts = [p for p in data.get('re', []) if p.get('post_comment_count', 0) > 0][:3]

for p in posts:
    pid = p['post_id']
    ncmt = p.get('post_comment_count', 0)
    title = p.get('post_title', '')[:40]
    print(f'Post {pid}: {ncmt}cmt - {title}')
    
    js = (
        "return fetch('https://gbapi.eastmoney.com/reply/api/Reply/ArticleNewReplyList', {"
        "method: 'POST',"
        "headers: {'Content-Type': 'application/json'},"
        f"body: JSON.stringify({{post_id: {pid}, sort: 1, sorttype: 1, p: 1, ps: 50}})"
        "}).then(r => r.json()).then(d => JSON.stringify(d))"
        ".catch(e => JSON.stringify({error: e.message}))"
    )
    result = driver.execute_script(js)
    reply = json.loads(result)
    re_list = reply.get('re')
    print(f'  API fetch: re_count={len(re_list) if re_list else 0}')
    
    # Navigate to post page and scrape HTML
    driver.get(f'https://guba.eastmoney.com/news,002703,{pid}.html')
    time.sleep(2)
    items = driver.find_elements(By.CSS_SELECTOR, 'div.reply_item')
    print(f'  HTML scraping: {len(items)} reply_item divs')
    if items:
        for item in items[:2]:
            try:
                c = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
                print(f'    {c[:80]}')
            except:
                pass

driver.quit()
print('Done')
