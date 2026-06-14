"""金十快讯 - 深度影响分析
从待处理快讯出发，逐级分析：板块 → 标签 → 个股 → 消息面影响
"""

import json, ssl, socket, os, sys, io, time, logging
from datetime import datetime

# === stdout 编码 ===
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# === 配置 ===
TOKEN_FILE = os.path.expanduser("~/.feishu-cli/token.json")
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
STOCK_TABLE = 'tbl2A9imBZgM7vLl'
SECTOR_TABLE = 'tblYQ1mU8FfuqIt2'
LABEL_TABLE = 'tblyaMaXvJXLODzs'
FLASH_TABLE = 'tblBxYPy2neYvFtq'

API_KEY = 'sk-lsnhfgotvsmsndxsonigqhvpdmbtajviumyobxonrbigsyhh'
API_HOST = 'api.siliconflow.cn'
FEISHU_WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/7fc8880c-af27-4242-a098-99df6cc26159'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'jin10_config.json')

# === 日志配置 ===
LOG_DIR = os.path.join(SCRIPT_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
log_handler = logging.FileHandler(
    os.path.join(LOG_DIR, 'impact_analysis_{}.log'.format(datetime.now().strftime('%Y%m%d'))),
    encoding='utf-8')
log_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
logger = logging.getLogger('impact_analysis')
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

def log(msg):
    """输出到控制台和日志文件"""
    logger.info(msg)
    try:
        print('[{}] {}'.format(datetime.now().strftime('%H:%M:%S'), msg), flush=True)
    except Exception:
        pass


# ============================================================
#  通用工具函数
# ============================================================

def get_token():
    with open(TOKEN_FILE, encoding='utf-8') as f:
        return json.load(f)['access_token']


def https_req(method, host, path, body=None, timeout=60):
    """纯 socket/ssl HTTP 请求"""
    token = get_token()
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=timeout)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = '{} {} HTTP/1.1\r\nHost: {}\r\n'.format(method, path, host)
    if token:
        hdrs += 'Authorization: Bearer {}\r\n'.format(token)
    hdrs += 'Content-Type: application/json\r\n'
    if body:
        hdrs += 'Content-Length: {}\r\n'.format(len(body))
    hdrs += 'Connection: close\r\n\r\n'
    ssock.sendall(hdrs.encode() + (body or b''))
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c:
            break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he + 4:]
    hstr = resp[:he].decode('iso-8859-1').lower()
    if 'chunked' in hstr:
        p, bd = 0, b''
        while p < len(raw):
            e = raw.find(b'\r\n', p)
            if e < 0:
                break
            sz = int(raw[p:e], 16)
            if sz == 0:
                break
            bd += raw[e + 2:e + 2 + sz]
            p = e + 2 + sz + 2
        raw = bd
    return json.loads(raw.decode())


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


def parse_json(text):
    """从 Qwen 返回中提取 JSON"""
    text = text.strip()
    if text.startswith('```'):
        parts = text.split('\n', 1)
        if len(parts) > 1:
            text = parts[1]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        if text.startswith('json'):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def send_feishu_card(title, content_md, sentiment='中性'):
    """发送飞书卡片通知"""
    emotion_color = {'利好': 'blue', '利空': 'red', '中性': 'grey'}
    card = {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': '金十快讯 · 深度分析'},
                'template': emotion_color.get(sentiment, 'grey'),
            },
            'elements': [
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': content_md}},
            ],
        },
    }
    try:
        host = 'open.feishu.cn'
        body = json.dumps(card, ensure_ascii=False).encode()
        path = FEISHU_WEBHOOK.split(host, 1)[1]
        ctx = ssl.create_default_context()
        sock = socket.create_connection((host, 443), timeout=30)
        ssock = ctx.wrap_socket(sock, server_hostname=host)
        hdrs = 'POST {} HTTP/1.1\r\nHost: {}\r\n'.format(path, host)
        hdrs += 'Content-Type: application/json\r\n'
        hdrs += 'Content-Length: {}\r\nConnection: close\r\n\r\n'.format(len(body))
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
        return result.get('code') == 0
    except Exception as e:
        log('  飞书通知发送失败: {}'.format(e))
        return False


# ============================================================
#  v3 API 数据读取
# ============================================================

def read_bitable_records(table_id, page_size=200):
    """使用 v3 API 读取表格全部记录，返回 [{field_name: value, _record_id: ...}, ...]"""
    all_records = []
    page_token = None

    while True:
        path = '/open-apis/base/v3/bases/{}/tables/{}/records?page_size={}'.format(
            BASE_TOKEN, table_id, page_size)
        if page_token:
            path += '&page_token=' + page_token

        data = https_req('GET', 'open.feishu.cn', path)
        d = data.get('data', {})
        field_names = d.get('fields', [])
        records_data = d.get('data', [])
        record_ids = d.get('record_id_list', [])
        has_more = d.get('has_more', False)
        page_token = d.get('page_token', '')

        for i, rid in enumerate(record_ids):
            if i >= len(records_data):
                break
            row = records_data[i]
            record = {field_names[j]: row[j] if j < len(row) and row[j] else ''
                      for j in range(min(len(field_names), len(row)))}
            record['_record_id'] = rid
            all_records.append(record)

        if not has_more:
            break

    return all_records


# ============================================================
#  数据加载
# ============================================================

def load_pending_flashes():
    """加载待处理的快讯"""
    log('[1/4] 加载闪讯表中待处理快讯...')
    all_records = read_bitable_records(FLASH_TABLE)
    pending = [r for r in all_records if r.get('状态', '') == '待处理']
    log('  共 {} 条记录, {} 条待处理'.format(len(all_records), len(pending)))
    return pending


def load_sectors():
    """加载全量板块数据"""
    log('[2/4] 加载板块表...')
    records = read_bitable_records(SECTOR_TABLE)
    sectors = []
    for r in records:
        name = r.get('板块名字', '')
        if not name:
            continue
        sectors.append({
            'name': name,
            'parent': r.get('父板块', ''),
            'problem': r.get('问题', ''),
            'logic': r.get('板块逻辑', ''),
            'tags': r.get('标签', ''),
            'expectation': r.get('后续预期', ''),
            'core_expectation': r.get('核心预期', ''),
            'burst_period': r.get('爆发期', ''),
            '_record_id': r.get('_record_id', ''),
        })
    log('  加载 {} 个板块'.format(len(sectors)))
    return sectors


def load_labels():
    """加载全量标签数据"""
    log('[3/4] 加载标签表...')
    records = read_bitable_records(LABEL_TABLE)
    labels = []
    for r in records:
        name = r.get('标签', '')
        if not name:
            continue
        labels.append({
            'name': name,
            'description': r.get('描述', ''),
            'sector': r.get('所属板块', ''),
            'stocks': r.get('股票', ''),
            '_record_id': r.get('_record_id', ''),
        })
    log('  加载 {} 个标签'.format(len(labels)))
    return labels


def load_stocks_detailed():
    """加载全量股票数据（含投资逻辑、公告、K线等详细字段）"""
    log('[4/4] 加载股票表...')
    records = read_bitable_records(STOCK_TABLE)
    stocks = []
    for r in records:
        name = r.get('股票名称', '')
        code = r.get('股票代码', '')
        if not name or not code:
            continue
        stocks.append({
            'name': name,
            'code': code,
            'sector': r.get('所属板块', ''),
            'tags': r.get('标签', ''),
            'concepts': r.get('所属概念', ''),
            'leader': r.get('板块龙头', ''),
            'invest_logic': r.get('投资逻辑', ''),
            'biz_model': r.get('业务模式', ''),
            'finance': r.get('财务现状', ''),
            'barrier': r.get('竞争壁垒', ''),
            'risk': r.get('风险点', ''),
            'market_cap': r.get('市值', ''),
            'pe': r.get('市盈率', ''),
            'price': r.get('现价', ''),
            'shares': r.get('流通股', ''),
            'kline_desc': r.get('当前k线', ''),
            'kline_analysis': r.get('K线分析', ''),
            'week_kline_analysis': r.get('周K分析', ''),
            'ai_strategy': r.get('AI策略', ''),
            'latest_announcement': r.get('最新公告', ''),
            'announcement_analysis': r.get('公告分析', ''),
            'good_factors': r.get('可能的利好', ''),
            'bad_factors': r.get('可能的利空', ''),
            'guba_hot': r.get('股吧热帖', ''),
            'today_comments': r.get('今日评论', ''),
            '_record_id': r.get('_record_id', ''),
        })
    log('  加载 {} 只股票'.format(len(stocks)))
    return stocks


# ============================================================
#  Qwen 分析步骤
# ============================================================

def build_sector_context(sectors):
    """构建板块上下文文本"""
    lines = []
    for s in sectors:
        parts = ['**{}**'.format(s['name'])]
        if s['logic']:
            parts.append('逻辑: {}'.format(s['logic'][:100]))
        if s['tags']:
            parts.append('关联标签: {}'.format(s['tags'][:100]))
        if s['core_expectation']:
            parts.append('核心预期: {}'.format(s['core_expectation'][:100]))
        lines.append('- ' + ' | '.join(parts))
    return '\n'.join(lines)


def analyze_sectors_and_labels(flash_content, sectors_context):
    """Step A: Qwen 分析快讯影响哪些板块和标签"""
    prompt = """你是一个中国A股分析助手。根据快讯内容，判断它影响以下哪些板块和标签。

## 已知板块池
{}

## 快讯内容
{}

## 要求
返回 JSON（不要其他内容）：
```json
{{
  "related": true,
  "summary": "一句话总结这条快讯的核心信息（50字内）",
  "affected_sectors": ["板块名1", "板块名2"],
  "sector_reasons": {{"板块名1": "为什么影响这个板块"}},
  "affected_labels": ["标签1", "标签2"],
  "label_reasons": {{"标签1": "为什么涉及这个标签"}},
  "sentiment": "利好/利空/中性",
  "importance": "高/中/低"
}}
```

规则：
- 板块名和标签名必须与上面的板块池完全一致，不要编造
- 如果快讯与所有板块都无关，设置 related=false 并留空 arrays
- 标签从板块的"关联标签"字段中选取最匹配的""".format(sectors_context, flash_content)

    result = qwen_chat([{'role': 'user', 'content': prompt}], max_tokens=1500)
    parsed = parse_json(result)
    if not parsed:
        log('  [WARN] Qwen 板块分析 JSON 解析失败，原文: {}'.format(result[:200]))
        return {
            'related': False, 'summary': result[:200],
            'affected_sectors': [], 'sector_reasons': {},
            'affected_labels': [], 'label_reasons': {},
            'sentiment': '中性', 'importance': '低'
        }
    return parsed


def find_stocks_by_labels(affected_labels, labels, stocks):
    """Step B: 根据标签找关联股票"""
    # 构建 标签名 → 股票列表 映射
    label_stocks_map = {}
    for label in labels:
        if label['name'] not in affected_labels:
            continue
        stock_names = [s.strip() for s in label['stocks'].replace('，', ',').split(',') if s.strip()]
        label_stocks_map[label['name']] = stock_names

    # 构建 股票名 → 股票详情 映射
    stock_map = {s['name']: s for s in stocks}

    # 找到所有受影响的股票
    found = {}  # name → stock dict
    for label_name, stock_names in label_stocks_map.items():
        for sn in stock_names:
            if sn in stock_map and sn not in found:
                found[sn] = stock_map[sn]

    # 如果标签匹配的股票太少，也从股票表中按板块和标签名模糊匹配
    if len(found) == 0:
        for s in stocks:
            s_tags = s['tags']
            s_sector = s['sector']
            for lbl in affected_labels:
                if lbl in s_tags or lbl in s_sector:
                    if s['name'] not in found:
                        found[s['name']] = s

    return list(found.values())


def build_stock_context(stocks):
    """构建股票详情上下文（用于 Qwen 个股影响分析）"""
    lines = []
    for i, s in enumerate(stocks, 1):
        parts = []
        parts.append('### {}. {}({})'.format(i, s['name'], s['code']))
        if s['invest_logic']:
            parts.append('- 投资逻辑: {}'.format(s['invest_logic'][:200]))
        if s['latest_announcement']:
            ann = s['latest_announcement'][:300]
            parts.append('- 最新公告: {}'.format(ann))
        if s['announcement_analysis']:
            aa = s['announcement_analysis'][:300]
            parts.append('- 公告分析: {}'.format(aa))
        if s['kline_analysis']:
            parts.append('- K线分析: {}'.format(s['kline_analysis'][:200]))
        if s['week_kline_analysis']:
            parts.append('- 周K分析: {}'.format(s['week_kline_analysis'][:200]))
        if s['kline_desc']:
            parts.append('- K线形态: {}'.format(s['kline_desc'][:100]))
        if s['ai_strategy']:
            parts.append('- AI策略: {}'.format(s['ai_strategy'][:200]))
        if s['market_cap']:
            parts.append('- 市值: {}'.format(s['market_cap']))
        if s['pe']:
            parts.append('- 市盈率: {}'.format(s['pe']))
        if s['price']:
            parts.append('- 现价: {}'.format(s['price']))
        if s['sector']:
            parts.append('- 所属板块: {}'.format(s['sector'][:100]))
        if s['risk']:
            parts.append('- 风险点: {}'.format(s['risk'][:150]))
        if s['barrier']:
            parts.append('- 竞争壁垒: {}'.format(s['barrier'][:150]))
        lines.append('\n'.join(parts))
    return '\n\n'.join(lines)


def analyze_stock_impact(flash_content, sector_analysis, affected_stocks):
    """Step C: Qwen 分析快讯对每个个股的消息面影响"""
    if not affected_stocks:
        return []

    stock_context = build_stock_context(affected_stocks)

    prompt = """你是一个中国A股分析助手。根据快讯内容，分析它对以下每只股票的消息面影响。

## 快讯内容
{}

## 快讯分析摘要
- 总结: {}
- 情绪: {}
- 重要性: {}
- 影响板块: {}
- 涉及标签: {}

## 受影响股票详情
{}

## 要求
返回 JSON（不要其他内容）：
```json
{{
  "stock_impacts": [
    {{
      "name": "股票名称",
      "code": "股票代码",
      "impact": "结合该股的投资逻辑、最新公告、K线走势等信息，分析这条快讯对该股的短期和中期影响（100-200字）",
      "impact_level": "高/中/低",
      "direction": "利好/利空/中性"
    }}
  ]
}}
```

分析要点：
1. 快讯是否验证/挑战该股的投资逻辑
2. 是否与该股最新公告有联动关系
3. K线走势是否支持当前消息面判断
4. 短期（1-3天）和中期（1-4周）影响分别如何""".format(
        flash_content,
        sector_analysis.get('summary', ''),
        sector_analysis.get('sentiment', '中性'),
        sector_analysis.get('importance', '低'),
        '、'.join(sector_analysis.get('affected_sectors', [])),
        '、'.join(sector_analysis.get('affected_labels', [])),
        stock_context,
    )

    result = qwen_chat([{'role': 'user', 'content': prompt}], max_tokens=3000)
    parsed = parse_json(result)
    if not parsed:
        log('  [WARN] Qwen 个股影响 JSON 解析失败，原文: {}'.format(result[:200]))
        return [{
            'name': s['name'], 'code': s['code'],
            'impact': '分析失败: {}'.format(result[:200]),
            'impact_level': '低', 'direction': '中性',
        } for s in affected_stocks]

    impacts = parsed.get('stock_impacts', [])
    # 确保所有受影响股票都有分析
    analyzed_names = {imp['name'] for imp in impacts}
    for s in affected_stocks:
        if s['name'] not in analyzed_names:
            impacts.append({
                'name': s['name'], 'code': s['code'],
                'impact': '未单独分析',
                'impact_level': '低', 'direction': '中性',
            })
    return impacts


# ============================================================
#  写入飞书
# ============================================================

def ensure_fields(table_id, required_fields):
    """确保表中存在所需字段，不存在的自动创建。返回 {field_name: field_id}"""
    # 获取现有字段
    path = '/open-apis/base/v3/bases/{}/tables/{}/fields'.format(BASE_TOKEN, table_id)
    data = https_req('GET', 'open.feishu.cn', path)
    existing = {}
    if isinstance(data, dict):
        for f in data.get('data', {}).get('fields', []):
            existing[f['name']] = f['id']

    result = {}
    for field_name in required_fields:
        if field_name in existing:
            result[field_name] = existing[field_name]
        else:
            # 创建字段
            body = json.dumps({'field_name': field_name, 'type': 'text'}).encode()
            resp = https_req('POST', 'open.feishu.cn',
                             '/open-apis/base/v3/bases/{}/tables/{}/fields'.format(BASE_TOKEN, table_id),
                             body)
            if resp.get('code') == 0 and 'data' in resp:
                fid = resp['data'].get('id', '')
                result[field_name] = fid
                log('  已创建字段 "{}" (id={})'.format(field_name, fid))
            else:
                log('  [ERROR] 创建字段 "{}" 失败: {}'.format(field_name, resp.get("msg", resp)))

    return result


def update_flash_record(record_id, fields_dict):
    """使用 v3 API PATCH 更新闪讯记录"""
    body = json.dumps(fields_dict, ensure_ascii=False).encode()
    path = '/open-apis/base/v3/bases/{}/tables/{}/records/{}'.format(
        BASE_TOKEN, FLASH_TABLE, record_id)
    resp = https_req('PATCH', 'open.feishu.cn', path, body)
    ok = resp.get('code') == 0
    if not ok:
        log('  [ERROR] 更新记录失败: {}'.format(resp.get("msg", resp)))
    return ok


def write_results(flash_record, sector_analysis, stock_impacts, field_ids):
    """将分析结果写入闪讯记录"""
    fields = {}

    # 基础分析
    if '分析摘要' in field_ids:
        fields['分析摘要'] = (sector_analysis.get('summary', '') or '')[:5000]
    if '相关板块' in field_ids:
        sectors = sector_analysis.get('affected_sectors', [])
        # 附上原因
        reasons = sector_analysis.get('sector_reasons', {})
        sector_text = '、'.join('{}({})'.format(s, reasons.get(s, '')) for s in sectors)
        fields['相关板块'] = sector_text[:2000]
    if '分类标签' in field_ids:
        labels = sector_analysis.get('affected_labels', [])
        lreasons = sector_analysis.get('label_reasons', {})
        label_text = '、'.join('{}({})'.format(l, lreasons.get(l, '')) for l in labels)
        fields['分类标签'] = label_text[:2000]
    if '相关股票' in field_ids:
        stock_texts = []
        for imp in stock_impacts:
            stock_texts.append('{}({}): {}'.format(imp['name'], imp['code'], imp.get('impact', '')[:200]))
        fields['相关股票'] = '\n'.join(stock_texts)[:5000]
    if '重要性' in field_ids:
        fields['重要性'] = sector_analysis.get('importance', '低')
    if '情绪' in field_ids:
        fields['情绪'] = sector_analysis.get('sentiment', '中性')

    # 消息面影响（新字段，汇总所有个股分析）
    if '消息面影响' in field_ids:
        impact_lines = []
        impact_lines.append('【快讯摘要】{}'.format(sector_analysis.get('summary', '')))
        impact_lines.append('【整体情绪】{} | 重要性: {}'.format(
            sector_analysis.get('sentiment', '中性'),
            sector_analysis.get('importance', '低')))
        impact_lines.append('【影响板块】{}'.format('、'.join(sector_analysis.get('affected_sectors', []))))
        impact_lines.append('【涉及标签】{}'.format('、'.join(sector_analysis.get('affected_labels', []))))
        impact_lines.append('')
        impact_lines.append('━━━ 个股影响分析 ━━━')
        for imp in stock_impacts:
            direction_emoji = {'利好': '🟢', '利空': '🔴', '中性': '🟡'}.get(imp.get('direction', '中性'), '')
            impact_lines.append('')
            impact_lines.append('▶ {}({}) {} | 影响: {}'.format(
                imp['name'], imp['code'],
                direction_emoji + imp.get('direction', '中性'),
                imp.get('impact_level', '低')))
            impact_lines.append('  {}'.format(imp.get('impact', '')))
        fields['消息面影响'] = '\n'.join(impact_lines)[:15000]

    # 更新状态为已分析
    if '状态' in field_ids:
        fields['状态'] = '已分析'

    return update_flash_record(flash_record['_record_id'], fields)


def send_impact_notification(flash_content, sector_analysis, stock_impacts):
    """发送重要快讯的飞书通知"""
    importance = sector_analysis.get('importance', '低')
    if importance not in ('高', '中'):
        return False

    title = flash_content.get('快讯内容', '') or '(无内容)'
    if len(title) > 80:
        title = title[:80] + '...'

    sentiment = sector_analysis.get('sentiment', '中性')

    md_lines = []
    md_lines.append('**快讯**\n{}'.format(title))
    md_lines.append('')
    md_lines.append('**摘要**: {}'.format(sector_analysis.get('summary', '')))
    md_lines.append('')

    sectors = sector_analysis.get('affected_sectors', [])
    labels = sector_analysis.get('affected_labels', [])
    if sectors:
        md_lines.append('**影响板块**: {}'.format('、'.join(sectors)))
    if labels:
        md_lines.append('**涉及标签**: {}'.format('、'.join(labels)))
    md_lines.append('')

    if stock_impacts:
        md_lines.append('**个股影响**:')
        for imp in stock_impacts[:8]:  # 最多显示8只
            d = imp.get('direction', '')
            lvl = imp.get('impact_level', '')
            emoji = {'利好': '🟢', '利空': '🔴', '中性': '🟡'}.get(d, '')
            md_lines.append('- {} {} {}({}) {}: {}'.format(
                emoji, lvl, imp['name'], imp['code'],
                d, imp.get('impact', '')[:60]))

    imp_emoji = {'高': '🔥', '中': '📌', '低': '📎'}
    sent_emoji = {'利好': '🟢', '利空': '🔴', '中性': '🟡'}
    md_lines.append('')
    md_lines.append('{} **{}** | {} **{}**'.format(
        sent_emoji.get(sentiment, ''), sentiment,
        imp_emoji.get(importance, ''), importance))

    content_md = '\n'.join(md_lines)
    return send_feishu_card(title, content_md, sentiment)


# ============================================================
#  主流程
# ============================================================

def main():
    log('=' * 50)
    log('金十快讯 · 深度影响分析')
    log('=' * 50)

    # Step 0: 确保字段存在
    log('[0/5] 检查必要字段...')
    required = ['分析摘要', '相关板块', '相关股票', '分类标签', '重要性', '情绪', '状态', '消息面影响']
    field_ids = ensure_fields(FLASH_TABLE, required)
    log('  可用字段: {}'.format(list(field_ids.keys())))

    # Step 1-4: 加载数据
    pending_flashes = load_pending_flashes()
    if not pending_flashes:
        log('没有待处理快讯，退出。')
        return

    sectors = load_sectors()
    labels = load_labels()
    stocks = load_stocks_detailed()

    log('=' * 50)
    log('开始逐条分析 (共 {} 条)'.format(len(pending_flashes)))
    log('=' * 50)

    sectors_context = build_sector_context(sectors)

    success_count = 0
    fail_count = 0

    for idx, flash in enumerate(pending_flashes, 1):
        log('--- [{}/{}] ---'.format(idx, len(pending_flashes)))

        flash_content = flash.get('快讯内容', '') or ''
        if not flash_content:
            log('  快讯内容为空，跳过')
            continue

        # 截断过长的内容
        flash_text = flash_content[:2000]
        log('  快讯: {}...'.format(flash_text[:100]))

        try:
            # Step A: 板块+标签分析
            log('  [A] Qwen 分析板块和标签...')
            sector_analysis = analyze_sectors_and_labels(flash_text, sectors_context)

            if not sector_analysis.get('related'):
                log('  快讯与所有板块无关，标记已处理')
                update_flash_record(flash['_record_id'], {'状态': '已分析'})
                success_count += 1
                continue

            log('  板块: {}'.format('、'.join(sector_analysis.get('affected_sectors', []))))
            log('  标签: {}'.format('、'.join(sector_analysis.get('affected_labels', []))))
            log('  情绪: {} | 重要性: {}'.format(
                sector_analysis.get('sentiment', '?'),
                sector_analysis.get('importance', '?')))

            # Step B: 标签→股票匹配
            affected_labels = sector_analysis.get('affected_labels', [])
            affected_stocks = find_stocks_by_labels(affected_labels, labels, stocks)
            log('  [B] 匹配到 {} 只关联股票: {}'.format(
                len(affected_stocks),
                '、'.join(s['name'] for s in affected_stocks)))

            # Step C: 个股影响分析
            stock_impacts = []
            if affected_stocks:
                log('  [C] Qwen 分析个股影响...')
                stock_impacts = analyze_stock_impact(flash_text, sector_analysis, affected_stocks)
                for imp in stock_impacts:
                    log('    {} {}: {} ({})'.format(
                        {'利好': '🟢', '利空': '🔴', '中性': '🟡'}.get(imp.get('direction', ''), ''),
                        imp['name'], imp.get('impact', '')[:80], imp.get('impact_level', '?')))

            # Step D: 写入飞书
            log('  [D] 写入飞书...')
            if write_results(flash, sector_analysis, stock_impacts, field_ids):
                log('  写入成功')
                success_count += 1
            else:
                log('  写入失败')
                fail_count += 1

            # Step E: 飞书通知
            importance = sector_analysis.get('importance', '低')
            if importance in ('高', '中') and affected_stocks:
                log('  [E] 发送飞书通知...')
                ok = send_impact_notification(flash, sector_analysis, stock_impacts)
                if ok:
                    log('  通知发送成功')
                else:
                    log('  通知发送失败')

            # 冷却 1 秒避免 API 限流
            time.sleep(1)

        except Exception as e:
            log('  [ERROR] 分析失败: {}'.format(e))
            import traceback
            logger.error(traceback.format_exc())
            fail_count += 1
            try:
                update_flash_record(flash['_record_id'], {'状态': '分析失败'})
            except Exception:
                pass

    log('=' * 50)
    log('分析完成! 成功: {}, 失败: {}'.format(success_count, fail_count))
    log('=' * 50)


if __name__ == '__main__':
    main()
