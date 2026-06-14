# 公告采集与 AI 分析 - 设计文档

## 概述

为现有的股票分析系统新增公告采集和 AI 分析能力。从巨潮资讯网（主）和东方财富（辅）抓取持仓股票的公告（定期报告 + 临时公告），通过 Qwen3-32B 提取关键信息，再由 Claude 深度解读，最终写入飞书多维表格。

## 架构

```
飞书多维表格(股票列表)
        │
        ▼
┌─────────────────────────┐
│  1. 公告采集             │  ← 巨潮(主) + 东财(辅)
│  announcement_fetch.py   │
└────────┬────────────────┘
         │ 公告文本
         ▼
┌─────────────────────────┐
│  2. Qwen3-32B 信息提取   │  ← 硅基流动 API
│  announcement_extract.py │
└────────┬────────────────┘
         │ 结构化摘要
         ▼
┌─────────────────────────┐
│  3. Claude 深度分析      │  ← 主 agent 在流程中调用
│  (main agent 内联)       │
└────────┬────────────────┘
         │ 最终分析文本
         ▼
┌─────────────────────────┐
│  4. 写入飞书多维表格     │  ← 复用现有 bitable 模式
│  announcement_to_bitable │
└─────────────────────────┘
```

## 模块设计

### 模块 1: announcement_fetch.py — 公告采集

**职责**: 从飞书多维表格读取股票列表，从巨潮/东财获取公告列表，下载 PDF 并转文本，去重。

**数据流**:
1. 读取飞书多维表格中的股票代码列表（复用 guba_to_bitable.py 的 fetch_records 逻辑，代码格式如 `sz002703`）
2. 对每只股票，查询巨潮资讯网公告列表 API：
   - 接口: `http://www.cninfo.com.cn/new/hisAnnouncement/query`
   - POST body: `{"stock": "sz002703,sse", "pageNum": 1, "pageSize": 30, "seDate": "2026-05-21~2026-05-24"}`
   - stock 参数格式: `{orgId}` 或 `"{code},{exchange}"` (如 `"sz002703,sse"` 或 `"sh688234,sse"`)
   - 飞书表格中的代码格式为 `sz002703` / `sh688234`，需提取 code 和 exchange 构造请求
   - 返回: `announcements[]` 含 `announcementId`, `announcementTitle`, `announcementTime`, `adjunctUrl` (PDF)
3. 东方财富公告接口做补充 — 仅当巨潮返回空或超时时启用：
   - 接口: `https://np-anotice-stock.eastmoney.com/api/security/ann`
   - 参数: `stock_list={code}`, 如 `stock_list=sz002703`（兼容现有飞书表格格式）
   - 返回: 公告列表含标题、日期、URL
4. 去重：本地维护 `announcement_state.json`，以 `{6位纯数字code}_{announcementId}` 为唯一键（6位码如 `002703`，兼容两个数据源）
5. 下载 PDF，用 pdfplumber 提取文本
6. 输出: `{stock_name: [{title, date, url, text, announce_id}, ...]}`

**技术要点**:
- HTTPS 请求复用项目现有的纯 socket 方式（不引入 requests）
- PDF 解析用 pdfplumber（参考 Annualreport_tools 的 pdf_batch_converter.py）
- 状态文件防重复处理
- 盘中实时运行，每次检查最近 N 天的公告

**配置**:
- `ANNOUNCEMENT_LOOKBACK_DAYS`: 回溯天数，默认 3
- `CNINFO_PAGE_SIZE`: 每页公告数，默认 30

### 模块 2: announcement_extract.py — Qwen3-32B 信息提取

**职责**: 将公告原文交给 Qwen3-32B，提取结构化关键信息。

**输入**: 公告全文（超长文本分段处理）
**输出**: 结构化 JSON 摘要

**提取字段**:
- `核心要点`: 1-2 句话概括
- `财务关键数据`: 营收、利润、同比变化等（如有）
- `重大事项`: 合同、重组、增减持等
- `风险因素`: 公告中提及的风险
- `对股价影响判断`: 利好/利空/中性
- `影响程度`: 高/中/低

**API 调用**: 复用 analyze_comments.py 的纯 socket + 硅基流动 API 方式

**分段策略**: 年报等长文本按 4000 字分段，逐段提取后汇总（汇总也交给 Qwen3-32B）

### 模块 3: Claude 深度分析

**职责**: 基于 Qwen3-32B 提取的结构化摘要，由主 agent (Claude) 进行深度解读。

**输入**: Qwen3-32B 提取的 `[{title, date, structured_summary}]`
**输出**: Markdown 格式的投资者分析

**分析维度**:
- 公告核心内容解读（用通俗语言解释）
- 对基本面的实际影响
- 结合行业背景的深度分析
- 风险提示
- 投资者建议关注的点

**实现方式**: Claude 在运行 announcement_analyze.py 主控脚本时，将 Qwen3-32B 的提取结果作为上下文，直接生成分析文本，写入文件后由模块 4 上传到飞书。

**上下文控制策略**（防止多公告超出 Claude 上下文限制）:
- 每只股票每轮最多处理 5 条新公告（超出部分延至下一轮）
- Qwen3-32B 提取的每条公告摘要控制在 500 字以内
- 分析按股票维度生成：一只股票的所有新公告合并为一份分析文本
- 极端情况（5 条公告 × 500 字 = 2500 字摘要输入）仍在上下文安全范围内

### 模块 4: announcement_to_bitable.py — 写入飞书

**职责**: 将分析结果写入飞书多维表格。

**新增字段**（在股票多维表格中）:
- `最新公告`: 文本类型 — 最近公告的标题和日期列表
- `公告分析`: 文本类型 — Claude 生成的完整分析

**实现**: 复用 guba_to_bitable.py 的 ensure_fields / update_text_field 逻辑

## 主控脚本: announcement_analyze.py

串联全流程：

```python
# 伪代码
1. stocks = fetch_records_from_bitable()
2. new_announcements = fetch_announcements(stocks)
3. if not new_announcements: exit("无新公告")
4. for stock, announcements in new_announcements.items():
5.    for ann in announcements:
6.        ann.extracted = qwen_extract(ann.text)       # 模块 2
7.    stock.analysis = claude_analyze(announcements)   # 模块 3 (主 agent)
8.    write_to_bitable(stock, stock.analysis)           # 模块 4
```

## 文件清单

| 文件 | 用途 |
|------|------|
| `announcement_fetch.py` | 模块 1: 公告采集 + PDF 转文本 |
| `announcement_extract.py` | 模块 2: Qwen3-32B 信息提取 |
| `announcement_to_bitable.py` | 模块 4: 写入飞书多维表格 |
| `announcement_analyze.py` | 主控: 串联全流程，含 Claude 分析 |
| `announcement_state.json` | 状态文件: 已处理公告 ID 记录 |
| `requirements.txt` | 新增 pdfplumber 依赖 |

## 去重策略

- 以 `{6位纯数字code}_{announcementId}` 为唯一键，存入 `announcement_state.json`
  - 6位纯数字 code: 从飞书表格的 `sz002703` / `sh688234` 格式中提取后 6 位，如 `002703`
- announce_id 取自巨潮的 `announcementId` 字段（东财的公告也映射到此格式）
- 每次运行只处理状态文件中不存在的公告

## 错误处理

- 巨潮接口超时/返回空 → 回退到东方财富接口
- PDF 下载失败 → 跳过该公告，记录日志
- Qwen3-32B API 调用失败 → 重试 2 次，仍失败则跳过
- 飞书写入失败 → 打印错误，不中断其他股票处理

## 依赖

- pdfplumber（新增，用于 PDF 转文本）
- 现有项目的纯 socket HTTP 调用方式
- 硅基流动 API（复用现有 key）
