"""金十数据 WebSocket 订阅服务
订阅 flash（快讯）频道 → Qwen AI 分析 → 飞书通知 + bitable 写入
支持后台服务模式（文件日志）
"""
import json
import time
import signal
import sys
import os
import io
import threading
import queue
import logging
from datetime import datetime
from websocket import WebSocketApp, WebSocketConnectionClosedException

# === 日志配置 ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 文件日志（完整）
file_handler = logging.FileHandler(
    os.path.join(LOG_DIR, 'jin10_{}.log'.format(datetime.now().strftime('%Y%m%d'))),
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))

logger = logging.getLogger('jin10')
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

# 控制台日志（仅在前台运行时）
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 导入项目内的模块
from jin10_bitable import load_stocks, build_context_text, write_flash, update_flash_analysis
from jin10_analyzer import analyze_flash, classify_flash
from jin10_notify import send_flash_card

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jin10_config.json')

def load_config():
    with open(CONFIG_FILE, encoding='utf-8') as f:
        return json.load(f)

cfg = load_config()
USER_ID = cfg['user_id']
TOKEN = cfg['token']
WS_URL = cfg['ws_url'].format(user_id=USER_ID, token=TOKEN)
CHANNELS = cfg['channels']
RECONNECT_CFG = cfg['reconnect']
ANALYSIS_CFG = cfg.get('analysis', {})
ANALYSIS_ENABLED = ANALYSIS_CFG.get('enabled', True)
MIN_IMPORTANCE = ANALYSIS_CFG.get('min_importance', '中')
FEISHU_WEBHOOK = cfg.get('feishu_webhook', '')

# 全局控制
running = True
reconnect_count = 0
ws_app = None
msg_queue = queue.Queue()  # 消息队列，异步处理
stocks_context = ''  # 股票上下文，启动时加载

def log(msg):
    """同时输出到控制台和日志文件"""
    logger.info(msg)
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
    except Exception:
        pass  # 无控制台时静默忽略

def on_open(ws):
    global reconnect_count
    reconnect_count = 0
    log("连接成功")

    sub_msg = {
        "type": "subscribe",
        "channels": CHANNELS
    }
    ws.send(json.dumps(sub_msg))
    log(f"已发送订阅: {CHANNELS}")

def on_message(ws, message):
    """接收消息，过滤系统消息后放入队列异步处理"""
    try:
        data = json.loads(message)

        # 过滤系统消息（连接确认、心跳等）
        if isinstance(data, dict):
            msg_type = data.get('type', '')
            if msg_type in ('connected', 'pong', 'error', 'subscribed'):
                log(f"系统消息: {msg_type} - {str(data.get('message', ''))[:100]}")
                return

        # 检查是否为有效的快讯消息（有 content 或 title）
        if isinstance(data, dict) and not data.get('content') and not data.get('title'):
            # 可能是未知类型的消息，打印但不分析
            log(f"未知消息类型: {json.dumps(data, ensure_ascii=False)[:200]}")
            return

        ts = datetime.now().strftime('%H:%M:%S')
        log(f"收到快讯:")
        logger.info("快讯详情: %s", json.dumps(data, ensure_ascii=False)[:1000])
        if isinstance(data, dict):
            for key in ['title', 'content', 'id']:
                if key in data:
                    val = data[key]
                    if isinstance(val, str) and len(val) > 150:
                        val = val[:150] + '...'
                    print(f"  {key}: {val}")
            extra = {k: v for k, v in data.items() if k not in ('title', 'content', 'id')}
            if extra:
                print(f"  extra: {json.dumps(extra, ensure_ascii=False)[:200]}")
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2)[:500])

        if ANALYSIS_ENABLED:
            msg_queue.put(data)
    except json.JSONDecodeError:
        log(f"收到非JSON消息: {str(message)[:200]}")

def on_error(ws, error):
    log(f"WebSocket 错误: {error}")

def on_close(ws, close_status_code, close_msg):
    log(f"连接关闭: code={close_status_code}, msg={close_msg}")
    if running:
        delay = min(RECONNECT_CFG['min_delay'] * (RECONNECT_CFG['backoff'] ** reconnect_count), RECONNECT_CFG['max_delay'])
        log(f"将在 {delay}s 后重连...")
        time.sleep(delay)
        connect()

def on_ping(ws, message):
    pass  # 自动回复 pong

def on_pong(ws, message):
    pass

def connect():
    global ws_app, reconnect_count
    reconnect_count += 1
    log(f"正在连接... (第 {reconnect_count} 次)")
    ws_app = WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_ping=on_ping,
        on_pong=on_pong,
    )
    ws_app.run_forever(ping_interval=30, ping_timeout=10)

def analysis_worker():
    """后台分析线程：分类 → 写入bitable → 深度分析 → 更新bitable → 飞书通知"""
    global stocks_context

    # 定期刷新股票数据（每30分钟）
    last_refresh = 0

    while running:
        try:
            # 刷新股票数据
            now = time.time()
            if now - last_refresh > 1800:
                try:
                    stocks, _, _ = load_stocks()
                    stocks_context = build_context_text(stocks)
                    last_refresh = now
                    log(f"已刷新股票数据 ({len(stocks)} 只)")
                except Exception as e:
                    log(f"刷新股票数据失败: {e}")

            # 取消息（1秒超时）
            try:
                flash_data = msg_queue.get(timeout=1)
            except queue.Empty:
                continue

            flash_text = json.dumps(flash_data, ensure_ascii=False)

            # Step 1: 快速分类（spam / valuable）
            log("Qwen 快速分类...")
            verdict = classify_flash(flash_text)
            log(f"分类结果: {verdict}")

            if verdict == 'spam':
                # 垃圾消息 → 写入 bitable 并跳过
                rid = write_flash(flash_data, '垃圾消息')
                log(f"已写入垃圾消息 (record_id={rid})")
                continue

            # Step 2: 有价值 → 先写入（状态=待处理）
            rid = write_flash(flash_data, '待处理')
            log(f"已写入待处理 (record_id={rid})")

            # Step 3: 深度分析（板块/股票/标签）
            log("开始深度分析...")
            result = analyze_flash(flash_text, stocks_context)

            logger.info("分析结果: %s", json.dumps(result, ensure_ascii=False))
            try:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            except Exception:
                pass

            # Step 4: 更新 bitable 记录（补充分析结果）
            if rid:
                update_flash_analysis(rid, result)
                log("已更新分析结果")

            # Step 5: 重要快讯发送飞书通知
            if not result.get('related'):
                log("快讯与股票池无关，跳过通知")
                continue

            importance = result.get('importance', '低')
            imp_order = {'高': 3, '中': 2, '低': 1}
            if imp_order.get(importance, 0) < imp_order.get(MIN_IMPORTANCE, 0):
                log(f"重要性 {importance} 低于阈值 {MIN_IMPORTANCE}，跳过通知")
                continue

            log("发送飞书通知...")
            ok, resp = send_flash_card(flash_data, result, FEISHU_WEBHOOK)
            if ok:
                log("飞书通知发送成功")
            else:
                log(f"飞书通知发送失败: {resp}")

        except Exception as e:
            log(f"分析处理错误: {e}")
            # 出错时也尝试写入，避免丢失消息
            try:
                write_flash(flash_data, '待处理')
            except Exception:
                pass
            import traceback
            logger.error(traceback.format_exc())

def signal_handler(sig, frame):
    global running
    log("收到退出信号，正在关闭...")
    running = False
    if ws_app:
        ws_app.keep_running = False
    time.sleep(0.5)
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log("金十数据订阅服务启动")
    log(f"频道: {CHANNELS}")
    log(f"用户: {USER_ID}")
    log(f"AI分析: {'开' if ANALYSIS_ENABLED else '关'}, 最低重要性: {MIN_IMPORTANCE}")

    # 启动时加载股票数据
    try:
        stocks, sectors, _ = load_stocks()
        stocks_context = build_context_text(stocks)
        log(f"已加载股票数据: {len(stocks)} 只, {len(sectors)} 个板块")
    except Exception as e:
        log(f"加载股票数据失败: {e}")
        stocks_context = ''

    # 启动分析线程
    analysis_thread = threading.Thread(target=analysis_worker, daemon=True)
    analysis_thread.start()

    # 主线程运行 WebSocket
    connect()
