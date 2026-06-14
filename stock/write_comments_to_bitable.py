"""将评论和AI分析写入飞书多维表格"""
import json, ssl, socket, os

TOKEN_FILE = os.path.expanduser("~/.feishu-cli/token.json")
BASE_TOKEN = 'KVpsbNvnZa9T1cseWOscAcqVnrh'
COMMENT_TABLE_ID = 'tblUFG0O6w1sZQi1'
STOCK_TABLE_ID = 'tbl2A9imBZgM7vLl'

def get_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)['access_token']

def https_req(method, host, path, token, body=None):
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, 443), timeout=30)
    ssock = ctx.wrap_socket(sock, server_hostname=host)
    hdrs = f'{method} {path} HTTP/1.1\r\nHost: {host}\r\n'
    if token: hdrs += f'Authorization: Bearer {token}\r\n'
    hdrs += 'Content-Type: application/json\r\n'
    if body: hdrs += f'Content-Length: {len(body)}\r\n'
    hdrs += 'Connection: close\r\n\r\n'
    ssock.sendall(hdrs.encode() + (body or b''))
    resp = b''
    while True:
        c = ssock.read(8192)
        if not c: break
        resp += c
    ssock.close()
    he = resp.find(b'\r\n\r\n')
    raw = resp[he+4:]
    hstr = resp[:he].decode('iso-8859-1')
    if 'chunked' in hstr.lower():
        p, bd = 0, b''
        while p < len(raw):
            e = raw.find(b'\r\n', p)
            if e < 0: break
            sz = int(raw[p:e], 16)
            if sz == 0: break
            bd += raw[e+2:e+2+sz]
            p = e+2+sz+2
        raw = bd
    return json.loads(raw.decode())

# ============================================================
# Analysis results from Haiku agents
# ============================================================
analyses = {
    '浙江世宝': {
        'code': 'sz002703',
        'summary': '【今日评论总结-浙江世宝】\n市场情绪：分歧。部分投资者借FSD入华题材看多，但更多人持观望或怀疑态度。\n关键讨论：FSD入华被视为智驾行业催化剂，但评论中理性声音指出过多唱多反而可疑，且散户情绪化交易明显。\n风险提示：评论区刻意唱多声音较集中，存在庄托/水军引导嫌疑。\n建议关注：FSD入华后实际路测表现，以及浙江世宝在智能驾驶产业链中是否具备实质受益逻辑。',
        'comments': [
            ('无意义灌水', '低', '德赛西威绝对的龙头'),
            ('理性技术分析', '中', 'FSD若在大雾强光等环境下表现不佳，纯视觉方案将无借口'),
            ('韭菜情绪发泄', '低', '发这些有毛用，大众交通梭啊！'),
            ('理性技术分析', '中', '低开就走弱了，散户越洗越多，边拉边洗才是强'),
            ('有价值观点', '中', '这么多唱多？强庄不需要造势'),
            ('无意义灌水', '低', '记住你的话了，离你近，有事去找你'),
            ('无意义灌水', '低', '多久到28'),
            ('韭菜情绪发泄', '低', '赞同观点，之前赚一波跑了，昨日再进场'),
            ('无意义灌水', '低', '有利于浙江省股票'),
            ('无意义灌水', '低', '这个没什么用'),
            ('韭菜情绪发泄', '低', '周一点火起飞'),
            ('韭菜情绪发泄', '低', '半导体高位个毛线'),
        ]
    },
    '天岳先进': {
        'code': 'sh688234',
        'summary': '【今日评论总结-天岳先进】\n市场情绪：分歧。看多者押注碳化硅放量和美股映射，看空者认为业绩承压。\n关键讨论：部分评论关注碳化硅器件增量是否已计入股价，有观点认为8英寸SiC满产是质变节点。\n风险提示：多数评论为情绪发泄或灌水，缺乏高质量基本面讨论；有评论提及上方60元抛压未消化。\n建议关注：碳化硅器件产能释放节奏、行业集中采购对利润的影响、天岳与露笑等同赛道标的基本面对比。',
        'comments': [
            ('理性技术分析', '中', '分析时代电气SiC产能及主力筹码分布，观点有逻辑但非直接讨论天岳'),
            ('韭菜情绪发泄', '低', '质疑电网投资逻辑，情绪化反驳，缺乏数据支撑'),
            ('理性技术分析', '中', '分析电网股涨不动的行业逻辑（集中采购压制利润），有一定参考价值'),
            ('有价值观点', '低', '认为SiC器件增量才是未被定价的因素，观点简明但无展开'),
            ('无意义灌水', '低', '这好那好，就是业绩不好'),
            ('无意义灌水', '低', '发这个有啥关系？'),
            ('韭菜情绪发泄', '低', '要暴跌'),
            ('无意义灌水', '低', '什么背景让你觉得要爆'),
            ('无意义灌水', '低', '模拟盘'),
            ('韭菜情绪发泄', '低', '还有三个点啦 跳水啦'),
            ('有价值观点', '中', '建议全仓天岳而非露笑，隐含看多天岳的赛道判断'),
            ('无意义灌水', '低', '闲聊他人做T操作'),
        ]
    },
    '三安光电': {
        'code': 'sh600703',
        'summary': '【今日评论总结-三安光电】\n市场情绪：分歧。看多者押注量子通信概念和低位补涨，看空者担忧股东债务和监管问题。\n关键讨论：技术面关注15.75元支撑位及缺口位买点策略，量能确认是关键；基本面存在股东股份冻结、监管关注等隐患。\n风险提示：股东债务问题未解，监管盯防，量子通信概念炒作持续性存疑。\n建议关注：周一能否在15.75元支撑位企稳，以及成交量能否有效放大确认资金诚意。',
        'comments': [
            ('韭菜情绪发泄', '低', '叠加行业热度加多重利好且低位的股价，星期一将开启吃肉行情'),
            ('韭菜情绪发泄', '低', '三安这波要是能突破，说不定真能打开新天地'),
            ('无意义灌水', '低', '行的吗，量子这东西，研究几十多年了，是行的，早已得食了'),
            ('理性技术分析', '中', '已经被监管盯死了，跑哪里？'),
            ('无意义灌水', '低', '技术分析确实比较到位，多谢'),
            ('无意义灌水', '低', '如果这样的成功率，世界首富都不为过'),
            ('无意义灌水', '低', '技术面的交易高手，佩服，跟着你好好学习，提升。'),
            ('无意义灌水', '低', '海豹晚上好'),
            ('理性技术分析', '中', '标准买点：缺口位支撑有效上沿买入，或弱转强放量破压力'),
            ('有价值观点', '中', '所有技术分析都会被突发利好或利空打破，周末消息面可能直接打碎支撑'),
            ('无意义灌水', '低', '1'),
            ('无意义灌水', '低', '因为你那时候天天喊会跌停'),
            ('无意义灌水', '低', '12的时候你在等9.5啊'),
            ('无意义灌水', '低', '有道理'),
            ('无意义灌水', '低', '你怎么这么逗啊'),
            ('韭菜情绪发泄', '低', '下周pcb感觉比液冷强点'),
        ]
    },
    '黄河旋风': {
        'code': 'sh600172',
        'summary': '【今日评论总结-黄河旋风】\n市场情绪：分歧。多空观点激烈对立。\n关键讨论：空方聚焦净资产为负、半年报可能ST；多方押注培育钻石/金刚石散热赛道、英伟达确认使用、国资增持及业绩扭亏预期。涨停后获利盘兑现压力（7.5-8.5区间）值得警惕。\n风险提示：净资产为负，存在ST戴帽风险；短期获利盘较大，有兑现压力。\n建议关注：金刚石散热市场（英伟达合作进展）、公司扭亏进度及国资增持动向。',
        'comments': [
            ('韭菜情绪发泄', '低', '问大族激光，与黄河旋风无关'),
            ('韭菜情绪发泄', '低', '问航天电子是否割肉，与黄河旋风无关'),
            ('韭菜情绪发泄', '低', '说得对，逢低买入，不追高！跟垃圾主力对着干！'),
            ('韭菜情绪发泄', '中', '主观判断高开封板，无依据'),
            ('韭菜情绪发泄', '低', '问中天/太极是否割肉，无关'),
            ('无意义灌水', '低', '一群无脑的，谁会带你们赚钱，毛病'),
            ('韭菜情绪发泄', '低', '太极实业慌求建议，无关'),
            ('韭菜情绪发泄', '中', '问黄河旋风能否持有，情绪恐慌'),
            ('无意义灌水', '低', '均胜电子大涨感谢，无关'),
            ('庄托/水军', '低', '鼓吹太极实业马上主升浪，疑似荐股托'),
            ('无意义灌水', '低', '你们就跟着格局吧！'),
            ('韭菜情绪发泄', '低', '不看好就出去，怼看空者'),
            ('无意义灌水', '低', '你这水平只能去买四大行两桶油'),
            ('有价值观点', '高', '系统列举看好逻辑：大幅扭亏、未来赛道、国资增持、投产扩产、技术突破'),
            ('韭菜情绪发泄', '低', '11.5卖出计划9.5接回，散户操作记录'),
            ('理性技术分析', '中', '点评主力洗盘手法凶狠，短线难做'),
            ('有价值观点', '高', '梳理涨停前时间线：竞价涨停+新闻+报纸培育钻石+高盛龙虎榜'),
            ('理性技术分析', '中', '提示7.5-8.5获利盘周一砸盘风险'),
            ('理性技术分析', '高', '警告净资产为负，半年报可能ST'),
            ('有价值观点', '高', '提到英伟达确认使用金刚石散热，利润率300%-700%'),
            ('有价值观点', '高', '阐述炒预期逻辑：年年亏损但股价上涨，买的是行业风口和未来'),
            ('无意义灌水', '低', '质疑发帖人成分，人身攻击'),
        ]
    },
    '德赛西威': {
        'code': 'sz002920',
        'summary': '【今日评论总结-德赛西威】\n市场情绪：分歧。部分投资者对二股东减持近20亿元表示恐慌，担忧日均不足十亿的成交量会被砸穿；另一方则认为此前40亿解禁也未大跌，利空出尽反而是机会。\n关键讨论：二股东拟减持3%（集中竞价1%+大宗交易2%）成为核心矛盾，多空双方围绕成交量能否承接展开博弈，另有员工透露对公司基本面有信心。\n风险提示：二股东减持金额巨大（约19亿），当前日均成交额不足十亿，短期抛压不容忽视，且后续仍存持续减持预期。\n建议关注：需密切关注大宗交易接盘方身份及实际减持节奏；公司一季度净利下滑的持续性及订单饱满度是判断基本面的关键。',
        'comments': [
            ('韭菜情绪发泄', '低', '垃圾，股价跌的时候怎么不出来吧'),
            ('理性技术分析', '中', '解释1%集中竞价+2%大宗交易的减持结构'),
            ('理性技术分析', '中', '引用此前40亿解禁未大跌作为参照'),
            ('理性技术分析', '中', '指出日均成交不足十亿，减持可能导致股价被砸穿'),
            ('有价值观点', '高', '博弈角度分析利空卖出未必能买回，市场永远平衡'),
            ('理性技术分析', '低', '简短表达利空出尽观点'),
            ('无意义灌水', '低', '员工推荐持股的玩笑回复'),
            ('有价值观点', '中', '询问公司订单饱满度和业绩情况'),
            ('韭菜情绪发泄', '低', '跌了就是加仓机会，情绪化看多'),
        ]
    }
}

# ============================================================
# Write to bitable
# ============================================================
token = get_token()

# 1. Write detailed comments to 股吧评论 table
print('Writing detailed comments to 股吧评论 table...')

# Post titles from original data
post_titles = {
    '浙江世宝': {
        '德赛西威绝对的龙头': '智驾产业迎来iPhone时刻？FSD入华倒逼行业升级',
        'FSD若在大雾强光等环境下表现不佳': '智驾产业迎来iPhone时刻？FSD入华倒逼行业升级',
        '发这些有毛用，大众交通梭啊！': '智驾产业迎来iPhone时刻？FSD入华倒逼行业升级',
        '低开就走弱了，散户越洗越多': '典型u型洗盘，下周低开全仓杀入',
        '这么多唱多？强庄不需要造势': '等涨到28我再告诉大家是因为什么涨',
        '记住你的话了': '等涨到28我再告诉大家是因为什么涨',
        '多久到28': '等涨到28我再告诉大家是因为什么涨',
        '赞同观点，之前赚一波跑了': '现在PCB芯片半导体都是高位',
        '有利于浙江省股票': '大利好来了',
        '这个没什么用。': '大利好来了',
        '周一点火起飞': '大利好来了',
        '半导体高位个毛线': '现在PCB芯片半导体都是高位',
    }
}

# Batch create records for comment table
record_count = 0
for name, data in analyses.items():
    code = data['code']
    for authenticity, importance, content in data['comments']:
        # Truncate post title lookup - just use a generic one
        post_title = '股吧帖子'

        body = json.dumps({
            'fields': {
                '股票名称': name,
                '股票代码': code,
                '帖子标题': post_title,
                '评论内容': content[:200],
                '真实性': authenticity,
                '重要性': importance,
                '分析备注': ''
            }
        }, ensure_ascii=False)

        resp = https_req('POST', 'open.feishu.cn',
            f'/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{COMMENT_TABLE_ID}/records',
            token, body.encode())
        if resp.get('code') == 0:
            record_count += 1
        else:
            print(f'  Write failed for {name}: {resp.get("msg","")}')

print(f'  Written {record_count} comment records')

# 2. Write summaries to stock table "今日评论" field
print('\nWriting summaries to 今日评论 field...')

# Get stock table records
data = https_req('GET', 'open.feishu.cn',
    f'/open-apis/base/v3/bases/{BASE_TOKEN}/tables/{STOCK_TABLE_ID}/records?page_size=50',
    token)

d = data.get('data', {})
field_names = d.get('fields', [])
records_data = d.get('data', [])
record_ids = d.get('record_id_list', [])

# Find 股票名称 position
name_pos = 0
for i, fn in enumerate(field_names):
    if '股票名称' in fn:
        name_pos = i
        break

# Map record names to record IDs
for i, rid in enumerate(record_ids):
    if i >= len(records_data): break
    row = records_data[i]
    name = row[name_pos] if name_pos < len(row) and row[name_pos] else ''
    if name in analyses:
        summary = analyses[name]['summary']
        body = json.dumps({'今日评论': summary}, ensure_ascii=False)
        resp = https_req('PATCH', 'open.feishu.cn',
            f'/open-apis/base/v3/bases/{BASE_TOKEN}/tables/{STOCK_TABLE_ID}/records/{rid}',
            token, body.encode())
        if resp.get('code') == 0:
            print(f'  {name}: 今日评论 saved')
        else:
            print(f'  {name}: save failed {resp.get("msg","")}')

print('\nDone!')
