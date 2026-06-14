import re
with open('J:/zss/stock/login_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

print(f'Page length: {len(html)}')

# Find ALL input elements
print('\n=== inputs ===')
for m in re.finditer(r'<input[^>]+>', html, re.IGNORECASE):
    tag = m.group()
    tp_m = re.search(r'type=("[^"]+"|\'[^\']+\')', tag)
    ph_m = re.search(r'placeholder=("[^"]*"|\'[^\']*\')', tag)
    cl_m = re.search(r'class=("[^"]+"|\'[^\']+\')', tag)
    tp = tp_m.group(1).strip('"\'') if tp_m else 'text'
    ph = ph_m.group(1).strip('"\'') if ph_m else ''
    cl = cl_m.group(1).strip('"\'') if cl_m else ''
    print(f'  input type={tp} placeholder="{ph[:60]}" class="{cl[:50]}"')

# Find all iframes
print('\n=== iframes ===')
for m in re.finditer(r'<iframe[^>]+src=("[^"]+"|\'[^\']+\')[^>]*>', html, re.IGNORECASE):
    src = m.group(1).strip('"\'')
    print(f'  {src[:150]}')

# Find login-related elements
print('\n=== login-related ===')
for kw in ['password', 'phone', 'mobile', 'sms', '验证码', '号码']:
    idxs = [m.start() for m in re.finditer(kw, html, re.IGNORECASE)]
    for idx in idxs[:2]:
        ctx = html[max(0,idx-100):idx+150]
        print(f'  [{kw}] {ctx[:200]}')

# Search for any form or div that has login-related ID/class
print('\n=== divs with id/class ===')
for m in re.finditer(r'<(div|form|section)[^>]*(?:login|passport|auth)[^>]*>', html, re.IGNORECASE):
    print(f'  {m.group()[:200]}')
