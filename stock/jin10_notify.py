"""金十快讯 - 飞书通知模块
通过飞书机器人 Webhook 发送卡片消息。
"""
import json, ssl, socket


def send_flash_card(flash_data, analysis, webhook_url):
    """发送快讯分析卡片到飞书

    Args:
        flash_data: 原始快讯 dict
        analysis: Qwen 分析结果 dict
        webhook_url: 飞书机器人 webhook 地址
    """
    title = flash_data.get('title', '') or flash_data.get('content', '') or '(无标题)'
    if len(title) > 100:
        title = title[:100] + '...'

    sentiment = analysis.get('sentiment', '中性')
    importance = analysis.get('importance', '中')
    summary = analysis.get('summary', '')
    sectors = analysis.get('sectors', [])
    stocks = analysis.get('stocks', [])
    tags = analysis.get('tags', [])

    # 构建 markdown 内容
    md_lines = []
    if summary:
        md_lines.append('**摘要**\n{}\n'.format(summary))

    if sectors:
        md_lines.append('**相关板块**: {}\n'.format('、'.join(sectors)))
    if tags:
        md_lines.append('**标签**: {}\n'.format('、'.join(tags)))
    if stocks:
        md_lines.append('**相关股票**:')
        for s in stocks:
            md_lines.append('- {} ({}) {}'.format(s['name'], s['code'], s.get('reason', '')))

    emotion_map = {'利好': '🟢', '利空': '🔴', '中性': '🟡'}
    importance_map = {'高': '🔥', '中': '📌', '低': '📎'}
    md_lines.append('\n{} **{}** | {} **{}**'.format(
        emotion_map.get(sentiment, ''), sentiment,
        importance_map.get(importance, ''), importance
    ))

    content_md = '\n'.join(md_lines)

    # 飞书卡片消息
    card = {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': '金十快讯'},
                'template': 'red' if sentiment == '利空' else ('blue' if sentiment == '利好' else 'grey'),
            },
            'elements': [
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': '**快讯原文**\n{}'.format(title)}},
                {'tag': 'hr'},
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': content_md}},
            ],
        },
    }

    try:
        host = 'open.feishu.cn'
        body = json.dumps(card, ensure_ascii=False).encode()
        path = webhook_url.split(host, 1)[1]

        ctx = ssl.create_default_context()
        sock = socket.create_connection((host, 443), timeout=30)
        ssock = ctx.wrap_socket(sock, server_hostname=host)

        hdrs = 'POST {} HTTP/1.1\r\nHost: {}\r\n'.format(path, host)
        hdrs += 'Content-Type: application/json\r\n'
        hdrs += 'Content-Length: {}\r\n'.format(len(body))
        hdrs += 'Connection: close\r\n\r\n'

        ssock.sendall(hdrs.encode() + body)
        resp = b''
        while True:
            c = ssock.read(8192)
            if not c:
                break
            resp += c
        ssock.close()

        he = resp.find(b'\r\n\r\n')
        raw = resp[he + 4:]
        result = json.loads(raw.decode())
        return result.get('code') == 0, result
    except Exception as e:
        return False, str(e)


if __name__ == '__main__':
    WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/7fc8880c-af27-4242-a098-99df6cc26159'
    test_flash = {'title': '【央行：下调存款准备金率0.5个百分点 释放长期资金约1万亿元】'}
    test_analysis = {
        'related': True,
        'summary': '央行降准释放万亿流动性，对A股整体偏利好',
        'sectors': ['无人驾驶/智驾', '新能源汽车'],
        'stocks': [
            {'name': '浙江世宝', 'code': 'sz002703', 'reason': '智驾龙头，受益于流动性改善'},
            {'name': '德赛西威', 'code': 'sz002920', 'reason': '汽车电子龙头，与新能源车板块联动'},
        ],
        'tags': ['降准', '流动性', '政策利好'],
        'sentiment': '利好',
        'importance': '高',
    }
    ok, resp = send_flash_card(test_flash, test_analysis, WEBHOOK)
    print('发送结果:', ok)
    print(json.dumps(resp, ensure_ascii=False, indent=2))
