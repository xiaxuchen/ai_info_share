---
name: "serenity-daily-research"
description: "每日 Serenity 式投研分析 Skill。每天早上8点自动调研当天最新火热题材，从工作区研报库中获取相关信息，按照 Serenity 紫苏叶理论逆向投研框架筛选高胜率股票，并给出建仓/加仓/止损/减仓策略。每日复盘前一日预测结果。Invoke when user asks for daily stock research, Serenity-style investment analysis, or when the scheduled daily research task runs."
---

# Serenity 每日投研分析 Skill

## 一、执行流程

### Step 1: 调研当天最新消息面
1. 搜索当天 A 股市场最火热的题材、概念、板块
2. 搜索当天涨停个股、连板梯队、主力资金流向
3. 搜索当天重大政策/事件/公告催化
4. 搜索当天机构研报重点推荐方向

### Step 2: 从研报库匹配信息
1. 在工作区 `0-公司深度/`、`1-细分行业&产业链分析/`、`2-公司PK/` 中搜索与当天热点相关的研报
2. 提取相关公司的核心投资逻辑、财务数据、估值区间
3. 提取产业链上下游关系、竞争格局、瓶颈环节

### Step 3: Serenity 式筛选
按照紫苏叶三要素评估每个候选标的：
- **刚需性**：该环节是否是下游爆发式增长的物理前提，有无替代方案
- **稀缺性**：全球合格供应商是否 ≤2-3 家，扩产周期是否 18-24 个月+
- **冷门性**：市值是否 <100 亿，机构覆盖是否极少，是否无资金抱团

### Step 4: 技术面验证
结合股票走势筛选：
- 沿 5 日线持续上行
- 均线多头排列
- 成交量配合放大
- 突破关键压力位

### Step 5: 生成策略报告
对每只入选标的给出：
- **建仓策略**：目标价格区间、首次建仓仓位（10-15%）、触发条件
- **加仓策略**：回踩支撑位不破时加仓、突破确认时加仓、加仓比例
- **止损策略**：技术止损位（跌破 10 日线/前低）、逻辑止损位（核心假设被证伪）
- **减仓策略**：达到目标价分批减仓、乖离率过大时减仓、逻辑兑现后减仓

### Step 6: 每日复盘
1. 回顾前一日推荐标的的实际走势
2. 对比预测与实际，分析偏差原因
3. 统计按策略操作的模拟收益
4. 总结教训，优化模型

## 二、输出格式

生成一份自包含 HTML 报告，保存到 `workspace/daily-research/YYYY-MM-DD/` 目录下：
- `report.html`：主报告
- `assets/`：图表、数据文件

报告包含章节：
1. 今日市场热点概览
2. 相关研报匹配结果
3. Serenity 筛选结果（含三要素评分）
4. 技术面分析
5. 操作策略（建仓/加仓/止损/减仓）
6. 前日复盘（如有）

## 三、关键约束

- 所有分析必须基于公开信息和研报数据，禁止编造
- 必须明确标注信息来源
- 必须包含风险提示
- 报告开头必须包含免责声明
- 中文输出

## 四、脚本用法

本 Skill 配套的可执行脚本位于 `/Users/xuchen.xia/.scripts/serenity-daily-research/`：

```bash
# 手动执行每日投研分析
node /Users/xuchen.xia/.scripts/serenity-daily-research/run.js --date=2026-06-14

# 查看历史报告
node /Users/xuchen.xia/.scripts/serenity-daily-research/run.js --list

# 复盘指定日期
node /Users/xuchen.xia/.scripts/serenity-daily-research/run.js --review=2026-06-13
```
