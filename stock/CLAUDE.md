# 股票多维分析系统

## 项目概述

基于飞书多维表格的股票分析系统，核心功能：
1. **股吧评论监控** — 从东方财富股吧抓取帖子+评论，AI 分析情绪，写入飞书
2. **公告采集分析** — 从东方财富/巨潮资讯网抓取公司公告，Qwen3-32B 提取关键信息 + Claude 深度解读
3. **K 线图表** — 从腾讯证券获取行情数据，生成 K 线图写入飞书
4. **知识图谱** — 中欣氟材产业链 RDF 知识图谱 (Turtle 格式)

## 关键文件

### 公告分析系统（新）
| 文件 | 用途 |
|------|------|
| `announcement_analyze.py` | 主控脚本：串联采集→Qwen提取→Claude分析→飞书写入 |
| `announcement_fetch.py` | 公告采集：东财API（主）+ 巨潮（辅），PDF转文本，去重 |
| `announcement_extract.py` | Qwen3-32B：硅基流动API，长文本分段提取结构化摘要 |
| `announcement_to_bitable.py` | 飞书写入：字段管理（最新公告/公告分析），记录更新 |
| `announcement_state.json` | 运行时状态：已处理公告ID记录 |
| `announcement_analysis_output.json` | 中间文件：Qwen提取结果 + Claude分析的JSON |

### 股吧评论系统
| 文件 | 用途 |
|------|------|
| `guba_to_bitable.py` | 股吧帖子抓取 + 写入飞书 |
| `crawl_new.py` | Selenium 爬虫：新12只股票评论采集 |
| `analyze_comments.py` | Qwen3-32B 评论分类 + 情绪总结 |
| `write_comments_to_bitable.py` | 评论分析结果写入飞书 |
| `full_comments.json` | 评论原始数据 |
| `analysis_results.json` | AI 分析结果 |

### 其他
| 文件 | 用途 |
|------|------|
| `knowledge-graph.ttl` | 中欣氟材产业链知识图谱 (RDF/Turtle) |
| `kg-editor.html` | 知识图谱可视化编辑器 |
| `requirements.txt` | Python 依赖 (pdfplumber, bitable-sdk, pandas) |

## 技术栈

- **语言**: Python 3
- **HTTP**: 纯 socket/ssl（不用 requests 库）
- **AI**: 硅基流动 Qwen3-32B（API Key 硬编码在 `analyze_comments.py` 和 `announcement_extract.py`）
- **飞书**: Bitable API v3（Token 存储在 `~/.feishu-cli/token.json`）
- **爬虫**: Selenium + Chrome（股吧评论）
- **PDF**: pdfplumber

## 代码约定

- 所有 HTTP 调用使用纯 socket/ssl，不引入 requests
- 飞书 Token 从 `~/.feishu-cli/token.json` 读取
- BASE_TOKEN: `KVpsbNvnZa9T1cseWOscAcqVnrh`
- 股票表格 ID: `tbl2A9imBZgM7vLl`
- 评论表格 ID: `tblUFG0O6w1sZQi1`
- `sys.stdout` 编码包装需检查 `encoding != 'utf-8'` 再替换，避免多模块导入冲突
- 飞书机器人 Webhook: `https://open.feishu.cn/open-apis/bot/v2/hook/7fc8880c-af27-4242-a098-99df6cc26159`（用于发送任务完成/异常通知，纯 socket POST JSON `{"msg_type":"text","content":{"text":"消息内容"}}`）

## 公告分析使用

```bash
# 第一步：采集公告 + Qwen3-32B 提取（生成 announcement_analysis_output.json）
python announcement_analyze.py

# 第二步：Claude 读取 announcement_analysis_output.json
#         对每只股票深度分析，填充 claude_analysis 字段

# 第三步：写入飞书多维表格（新增/更新"最新公告""公告分析"字段）
python announcement_analyze.py --write
```

### 数据源

- **东财 API** (主): `np-anotice-stock.eastmoney.com/api/security/ann`
  - `stock_list`: 6位纯数字代码
  - `ann_type`: `SZA`(深市) / `SHA`(沪市) —— 必须加此参数才能过滤公司公告
- **巨潮 API** (辅助): `www.cninfo.com.cn/new/hisAnnouncement/query`
  - 需 User-Agent + Referer 头
  - stock 参数不生效，需客户端按 secCode 过滤

### 去重

- 状态文件: `announcement_state.json`
- 键格式: `{6位纯数字code}_{announcementId}`
- 仅在成功提取内容后标记已处理

## 飞书多维表格 — 完整表结构

BASE_TOKEN: `KVpsbNvnZa9T1cseWOscAcqVnrh`，共 5 张表，全部字段如下。

### 股票 (`tbl2A9imBZgM7vLl`)
| 字段名 | 类型 | field_id | 说明 |
|--------|------|----------|------|
| 股票名称 | 1(文本) | fldlaz2TRi | 如"浙江世宝" |
| 股票代码 | 1(文本) | fldTOEhUHx | 如"sz002703" |
| 当前k线 | 1(文本) | fldrHBtXCE | 当前K线形态描述 |
| 所属板块 | 1(文本) | fld9rC0NJV | 逗号分隔多板块 |
| 标签 | 1(文本) | fldI0mf57r | 逗号分隔多标签 |
| 板块龙头 | 4(多选) | fldi4FeGVa | 是否板块龙头 |
| 投资逻辑 | 1(文本) | fldSR0N8iQ | 核心投资逻辑 |
| 业务模式 | 1(文本) | fld1aZZNG1 | 业务模式描述 |
| 财务现状 | 1(文本) | fldx1vNu9U | 财务现状分析 |
| 竞争壁垒 | 1(文本) | fldSYbUKar | 护城河/壁垒 |
| 风险点 | 1(文本) | fldCedxyaT | 潜在风险 |
| 市值 | 1(文本) | fldr2LWP8T | 公司市值 |
| 市盈率 | 1(文本) | fldatE4Kel | PE 值 |
| 可能的利好 | 1(文本) | fldkgRVMtz | 潜在利好因素 |
| 可能的利空 | 1(文本) | fldQE8OVzS | 潜在利空因素 |
| K线图 | 17(附件) | fldDH8GEUE | 日K线图附件 |
| 周K线图 | 17(附件) | fldkxhy0Vp | 周K线图附件 |
| 现价 | 1(文本) | fldmz2U2Bp | 当前价格 |
| 流通股 | 1(文本) | fldSEOah2o | 流通股本 |
| K线分析 | 1(文本) | fldpOYbQ8A | K线走势分析 |
| 周K分析 | 1(文本) | fldXkbStjz | 周K走势分析 |
| AI策略 | 1(文本) | fldcu6YcBI | AI 投资策略 |
| 30日日K | 1(文本) | fldhtiwPTs | 近30天K线数据 |
| 周K线 | 1(文本) | fldfAyEmd1 | 周K线数据 |
| 所属概念 | 1(文本) | fldo5Whxli | 所属概念（`|`分隔） |
| 股吧热帖 | 1(文本) | flde6cWr8u | 热帖摘要 |
| 今日评论 | 1(文本) | fldS7PySIN | 评论分析总结 |
| 公告分析 | 1(文本) | fldKrNGnHB | Claude 公告深度分析 |
| 最新公告 | 1(文本) | fldvKDkeVf | 最近公告标题列表 |

### 板块 (`tblYQ1mU8FfuqIt2`)
| 字段名 | 类型 | field_id | 说明 |
|--------|------|----------|------|
| 板块名字 | 3(单选) | fldAalCaql | 板块名称 |
| 父板块 | 3(单选) | flddOku1Wr | 上级板块 |
| 问题 | 1(文本) | fldgLYlDIN | 板块面临的问题 |
| 板块逻辑 | 1(文本) | fldjgH0ePC | 板块核心逻辑 |
| 标签 | 1(文本) | fldQeceqYV | 关联的标签 |
| 后续预期 | 1(文本) | fldZYW3d2v | 后续走势预期 |
| 核心预期 | 1(文本) | fldhUlBilp | 核心预期要点 |
| 爆发期 | 1(文本) | fldn6nt2Jg | 板块爆发时间节点 |

### 标签 (`tblyaMaXvJXLODzs`)
| 字段名 | 类型 | field_id | 说明 |
|--------|------|----------|------|
| 标签 | 3(单选) | fldEPPlpp4 | 标签名称 |
| 描述 | 1(文本) | fldZDXuGCx | 标签描述 |
| 所属板块 | 1(文本) | fldG9jmoTn | 标签归属的板块 |
| 股票 | 1(文本) | fldQKW9qVH | 相关股票列表 |

### 股吧评论 (`tblUFG0O6w1sZQi1`)
| 字段名 | 类型 | field_id | 说明 |
|--------|------|----------|------|
| ID | 1005(自动编号) | fld9jQuOM4 | 自动生成 |
| 股票名称 | 1(文本) | fld0RGYlX9 | 关联股票名称 |
| 股票代码 | 1(文本) | fldqRd4XOB | 关联股票代码 |
| 帖子标题 | 1(文本) | fldFhjyi1l | 帖子标题 |
| 评论内容 | 1(文本) | fldlQxMHnc | 评论内容 |
| 真实性 | 1(文本) | fldxtCGPyu | 真实性判断 |
| 重要性 | 1(文本) | fldO23EBzd | 重要性评级 |
| 分析备注 | 1(文本) | fldH4VHE5G | 分析备注 |

### 金十快讯 (`tblBxYPy2neYvFtq`, 原"数据表")
| 字段名 | 类型 | field_id | 说明 |
|--------|------|----------|------|
| 文本 | 1(文本) | fldeQKEb1h | (旧字段) |
| 讨论群 | 23(群聊) | fldKLABXfM | (旧字段) |
| 人员 | 11(人员) | fldWsjP7It | (旧字段) |
| 单选 | 3(单选) | fldrMrQdia | (旧字段) |
| 多选 | 4(多选) | fldlDJvyLT | (旧字段) |
| 日期 | 5(日期) | fldb6FFmqE | (旧字段) |
| 附件 | 17(附件) | fld41vpawD | (旧字段) |
| 快讯内容 | 1(文本) | fldF1g3Ovg | 快讯原文 |
| 状态 | 3(单选) | fldNohjXt3 | 待处理/垃圾消息 |
| 分析摘要 | 1(文本) | fld4b38rYv | AI 分析摘要 |
| 相关板块 | 1(文本) | flde4BP8Hw | 受影响的板块 |
| 相关股票 | 1(文本) | fldsOMbH2S | 受影响的股票 |
| 分类标签 | 1(文本) | fld0yQ6Gqy | 分类标签 |
| 重要性 | 3(单选) | fldcj2TLOA | 高/中/低 |
| 情绪 | 3(单选) | fld4tEjvOj | 利好/利空/中性 |
| 接收时间 | 1(文本) | fldaDi7FUr | 快讯接收时间 |
| 快讯ID | 1(文本) | fldqaBrRYC | 金十快讯唯一 ID |

## AI 操作规范

- **定时任务/批处理任务禁止额外探索项目结构**，直接基于本文档中的表结构、文件列表进行开发，不要再运行 `ls`、`Glob`、`Agent Explore` 等探索性操作来了解项目。
- 处理金十相关任务前必须先运行 `python jin10_keepalive.py` 确保后台服务在线。

## 金十快讯订阅系统

实时订阅金十数据 WebSocket 快讯（flash），Qwen3-32B 快速分类（有价值/垃圾），
有价值快讯深度分析（板块/股票/标签/情绪），写入飞书多维表格并通过飞书机器人通知。

### 数据流

```
金十 WebSocket (wss://jin10.coinstar.top/ws/<user_id>?token=)
    → 过滤系统消息
    → Qwen3-32B 快速分类 (spam / valuable)
    → 写入 bitable 金十快讯表 (状态: 待处理 / 垃圾消息)
    → 若有价值: Qwen3-32B 深度分析 (板块/股票/标签/情绪/重要性)
    → 更新 bitable 分析字段
    → 重要性 ≥ 中 → 飞书卡片通知
```

### 快讯存储表

- 表格 ID: `tblBxYPy2neYvFtq`（原"数据表"）
- 字段: 快讯内容、状态（待处理/垃圾消息）、分析摘要、相关板块、相关股票、分类标签、重要性、情绪、接收时间、快讯ID

### 关键文件

| 文件 | 用途 |
|------|------|
| `jin10_subscriber.py` | 主服务：WebSocket连接/重连、消息过滤、分类→写入→分析→通知 |
| `jin10_bitable.py` | 读写飞书：加载股票数据 + 写入/更新快讯记录 |
| `jin10_analyzer.py` | Qwen3-32B：classify_flash() 快速分类 + analyze_flash() 深度分析 |
| `jin10_notify.py` | 飞书机器人 webhook 卡片消息发送 |
| `jin10_config.json` | 配置文件（WS认证、webhook URL、分析开关、重要性阈值） |

### 后台服务

| 文件 | 用途 |
|------|------|
| `jin10_keepalive.py` | **保活脚本**：检测服务是否运行，未运行则自动启动。AI 每次处理金十相关任务前应先调用 `python jin10_keepalive.py` |
| `jin10_service.bat` | 双击启动后台（pythonw.exe 无窗口） |
| `jin10_service.vbs` | VBS 启动器（完全隐藏，适合计划任务调用） |
| `jin10_stop.bat` | 停止服务 |
| `register_service.ps1` | 注册 Windows 计划任务（开机自启，需管理员运行） |

### AI 操作约定

**每次处理金十快讯相关任务前，必须先运行：**
```bash
python jin10_keepalive.py
```
输出 `已在运行` 则继续，输出 `未运行...已启动` 则等待 3 秒后继续。

### 启动方式

```bash
# 保活检测（推荐，AI 优先使用）
python jin10_keepalive.py

# 前台运行（调试）
python jin10_subscriber.py

# 后台运行
双击 jin10_service.bat
# 或
wscript jin10_service.vbs

# 开机自启（需管理员）
powershell -ExecutionPolicy Bypass -File register_service.ps1
```

### 配置

`jin10_config.json`:
- `user_id` / `token` — 金十 WebSocket 认证
- `channels` — 订阅频道（默认 `["flash"]`）
- `reconnect` — 重连策略（指数退避，最大60秒）
- `feishu_webhook` — 飞书机器人 webhook URL
- `analysis.enabled` — AI 分析开关
- `analysis.min_importance` — 通知最低阈值（高/中/低）

### 日志

- 每日日志文件：`logs/jin10_YYYYMMDD.log`
- 同时输出到控制台（前台）和日志文件
