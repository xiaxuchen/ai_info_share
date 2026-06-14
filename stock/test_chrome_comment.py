"""用已登录的 Chrome 加载股吧评论"""
import time, json, os, shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 复制 Chrome 用户数据到临时目录（避免被正在运行的 Chrome 锁定）
user_data = r'C:\Users\xxc\AppData\Local\Google\Chrome\User Data'
temp_profile = r'C:\Users\xxc\.chrome_temp_profile'

# 只复制关键文件夹
os.makedirs(temp_profile, exist_ok=True)
for folder in ['Default', 'Local State']:
    src = os.path.join(user_data, folder)
    dst = os.path.join(temp_profile, folder)
    if os.path.exists(src):
        if os.path.exists(dst):
            if os.path.isdir(dst):
                shutil.rmtree(dst, ignore_errors=True)
            else:
                os.remove(dst)
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=True, ignore_dangling_symlinks=True)
            else:
                shutil.copy2(src, dst)
        except Exception as e:
            print(f'  Copy {folder} error: {e}')

options = Options()
options.add_argument(f'--user-data-dir={temp_profile}')
options.add_argument('--profile-directory=Default')
options.add_argument('--no-sandbox')
# options.add_argument('--headless=new')  # 先不用 headless 看效果

service = Service()
driver = webdriver.Chrome(service=service, options=options)
try:
    url = 'https://guba.eastmoney.com/news,002703,1712037378.html'
    print(f'Loading: {url}')
    driver.get(url)

    # 等待评论加载
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.reply_item'))
        )
        print('Found reply items!')
    except:
        print('Timeout waiting for reply items')

    time.sleep(2)

    # 检查评论元素
    reply_items = driver.find_elements(By.CSS_SELECTOR, 'div.reply_item')
    print(f'\nReply items found: {len(reply_items)}')

    for i, item in enumerate(reply_items[:5]):
        try:
            content = item.find_element(By.CSS_SELECTOR, 'div.reply_title span').text
            print(f'  [{i}] {content[:100]}')
        except:
            try:
                content = item.text
                print(f'  [{i}] (fallback) {content[:100]}')
            except:
                print(f'  [{i}] failed to extract')

    # 检查登录状态
    page_text = driver.find_element(By.TAG_NAME, 'body').text
    if '登录' in page_text and '注册' in page_text:
        # 检查是否在页面顶部显示登录链接（未登录状态）
        top_200 = page_text[:200]
        if '登录/注册' in top_200:
            print('\n*** NOT LOGGED IN - need to log in on Chrome first ***')
        else:
            print('\nLogin state unclear')
    else:
        print('\nLikely logged in (no login prompt visible)')

    # 保存页面
    with open('J:/zss/stock/chrome_page.html', 'w', encoding='utf-8') as f:
        f.write(driver.page_source)
    print('Page saved')

finally:
    driver.quit()
    # 清理临时文件
    shutil.rmtree(temp_profile, ignore_errors=True)
