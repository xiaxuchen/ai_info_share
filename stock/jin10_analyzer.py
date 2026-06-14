"""金十快讯 - Qwen AI 分析模块
调用 SiliconFlow Qwen3-32B 分析快讯，识别相关板块、股票、标签。
"""
import json, ssl, socket

API_KEY = 'sk-lsnhfgotvsmsndxsonigqhvpdmbtajviumyobxonrbigsyhh'
API_HOST = 'api.siliconflow.cn'


def qwen_chat(messages, max_tokens=2000, temperature=0.3):
    """调用 SiliconFlow Qwen3-32B"""
    body = json.dumps({
        'model': 'Qwen/Qwen3-32B',
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
    })
    ctx = ssl.create_default_context()
    sock = socket.create_connection((API_HOST, 443), timeout=120)
    ssock = ctx.wrap_socket(sock, server_hostname=API_HOST)
    hdrs = 'POST /v1/chat/completions HTTP/1.1\r\nHost: {}\r\n'.format(API_HOST)
    hdrs += 'Authorization: Bearer {}\r\nContent-Type: application/json\r\n'.format(API_KEY)
    hdrs += 'Content-Length: {}\r\nConnection: close\r\n\r\n'.format(len(body))
    ssock.sendall(hdrs.encode() + body.encode())
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c:
            break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he + 4:]
    return json.loads(raw.decode()).get('choices', [{}])[0].get('message', {}).get('content', '')


def classify_flash(flash_content):
    """快速分类：判断快讯是否有价值

    Returns:
        'valuable' 或 'spam'
    """
    prompt = """你是一个财经快讯过滤器。判断以下快讯是否是垃圾消息。

## 垃圾消息特征
- 纯广告、推广
- 与财经/股市/投资完全无关
- 空白或无意义内容
- 重复的纯符号或纯数字

## 有价值的快讯特征
- 涉及股市、经济、政策、行业
- 涉及具体公司、板块、商品
- 数据发布、事件预告
- 市场行情、交易数据

## 快讯内容
{}

## 要求
只返回一个词: valuable 或 spam""".format(flash_content)

    result = qwen_chat([{'role': 'user', 'content': prompt}], max_tokens=10, temperature=0)
    result = result.strip().lower()
    if 'spam' in result:
        return 'spam'
    return 'valuable'


def analyze_flash(flash_content, stocks_context):
    """分析快讯，返回结构化结果"""
    prompt = """你是一个中国A股分析助手。请根据快讯内容，判断它与以下哪些股票、板块相关。

## 已知股票池
{}

## 快讯内容
{}

## 要求
返回 JSON，不要其他内容：
```json
{{
  "related": true,
  "summary": "一句话总结这条快讯的核心信息",
  "sectors": ["相关板块1", "相关板块2"],
  "stocks": [
    {{"name": "股票名称", "code": "股票代码", "reason": "相关原因"}}
  ],
  "tags": ["标签1", "标签2"],
  "sentiment": "利好/利空/中性",
  "importance": "高/中/低"
}}
```

如果快讯与股票池中所有股票都无关，设置 related=false 并留空 arrays。
板块和标签都从股票池中找到最匹配的，不要编造新的。""".format(stocks_context, flash_content)

    result = qwen_chat([{'role': 'user', 'content': prompt}], max_tokens=1500)

    # 解析 JSON
    try:
        # 处理 markdown code block
        text = result.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
            if text.startswith('json'):
                text = text[4:].strip()
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return {
            'related': False,
            'summary': result[:200],
            'sectors': [],
            'stocks': [],
            'tags': [],
            'sentiment': '中性',
            'importance': '低',
            'parse_error': True,
            'raw': result[:500],
        }


if __name__ == '__main__':
    from jin10_bitable import load_stocks, build_context_text

    stocks, sectors, concepts = load_stocks()
    ctx = build_context_text(stocks)
    print('股票池:')
    print(ctx)
    print()

    # 测试分析
    test = "【央行：下调存款准备金率0.5个百分点 释放长期资金约1万亿元】"
    print('测试快讯:', test)
    print()
    result = analyze_flash(test, ctx)
    print('分析结果:')
    print(json.dumps(result, ensure_ascii=False, indent=2))
