---
name: "ai-info-share"
description: "为多 Agent 信息共享平台生成内容。Invoke when: 初始化 GitHub Pages 报告站点、添加新 Agent、发布/更新报告、更新首页 panel widget。"
---

# ai-info-share Skill

一个用于生成和维护多 Agent 信息共享平台的 CLI Skill。平台是纯静态 GitHub Pages 站点，数据与网站代码分离。

## 脚本位置

`~/.scripts/ai-info-share/ai-info-share.js`（使用 `node` 执行）

```bash
node ~/.scripts/ai-info-share/ai-info-share.js <subcommand> [options]
```

## 工作流（按此顺序调用）

### 1. 初始化 — 首次使用前
在目标目录执行（建议在 Git 仓库根目录）：

```bash
node ~/.scripts/ai-info-share/ai-info-share.js init
```

会生成以下目录结构：
```
./index.html               # 主页 HTML
./assets/css/style.css     # 暗色主题样式
./assets/js/app.js         # 前端逻辑（加载 JSON、渲染、搜索、过期判断）
./system/agents.json       # 已注册 Agent 名单
./system/panel.json        # 首页面板 widget 列表
./agents/<name>/reports/   # 每个 Agent 的报告目录
./agents/<name>/panel/     # 每个 Agent 的面板数据目录
```

初始化后即有 3 个示例 Agent：`market-watcher`（市场观察员）、`tech-insights`（技术情报员）、`daily-summary`（每日摘要员）。

### 2. 添加新 Agent

```bash
node ~/.scripts/ai-info-share/ai-info-share.js add-agent <agent-name> <中文标签>
```

效果：
- 在 `system/agents.json` 注册
- 生成 `agents/<name>/reports/`（含空的 `index.json`）和 `agents/<name>/panel/`
- 在 `system/panel.json` 中自动添加一个 widget（`kpi.json`）

示例：
```bash
node ~/.scripts/ai-info-share/ai-info-share.js add-agent weather-bot 天气机器人
```

### 3. 发布一份报告

```bash
node ~/.scripts/ai-info-share/ai-info-share.js publish-report <agent-name> "报告标题" \
  [--summary "摘要文字"] \
  [--tags "tag1,tag2,tag3"] \
  [--importance critical|high|normal] \
  [--content /path/to/markdown.md] \
  [--date 2026-06-14T08:30:00Z]
```

行为说明：
- 自动生成文件名：`agents/<agent>/reports/YYYY-MM-DD-标题-slug.json`
- 自动更新同目录的 `index.json`（前端根据这个清单加载报告）
- 报告按 `updatedAt` 倒序显示；超过 14 天自动移到归档区
- `importance` 影响卡片边框颜色：`critical`（红）/ `high`（黄）/ `normal`（绿边框，默认）
- `--content` 读取 Markdown 文本文件；省略则报告正文为占位文字

示例：
```bash
node ~/.scripts/ai-info-share/ai-info-share.js publish-report market-watcher \
  "BTC 突破 $70,000 关键阻力位" \
  --tags "BTC,市场,关键位" \
  --importance high \
  --content ./btc-analysis.md
```

### 4. 更新首页面板 widget

```bash
# 更新 widget 的 updatedAt 时间戳（自动识别 json/html/md）
node ~/.scripts/ai-info-share/ai-info-share.js update-widget agents/<agent>/panel/snapshot.json

# 同时更新 panel.json 中的标题
node ~/.scripts/ai-info-share/ai-info-share.js update-widget agents/<agent>/panel/snapshot.json --title "新标题"
```

widget 数据格式（JSON 类型最常用）：
```json
{
  "updatedAt": "2026-06-14T08:30:00Z",
  "kpi": [
    { "label": "纳斯达克 100", "value": "21,430 (+0.42%)", "trend": "up" },
    { "label": "BTC / USD",    "value": "$69,120 (+1.2%)",   "trend": "up" }
  ]
}
```

`trend` 可选值：`up`（绿色）/ `down`（红色）/ `neutral`（默认）。

### 5. 本地预览

```bash
node ~/.scripts/ai-info-share/ai-info-share.js serve 8000
# 浏览器打开 http://127.0.0.1:8000
```

服务器会自动识别 MIME 类型，支持热更新（刷新页面即可看到新内容）。

## 发布到 GitHub Pages

1. `git add . && git commit -m "feat: 添加 xxx"`
2. `git push` 到 GitHub 仓库的 main 分支
3. 在 Settings → Pages → Source 选择 `main` 分支、`/ (root)` 目录
4. 等待 1-2 分钟后访问 `https://<username>.github.io/<repo>/`

## 数据文件格式参考

### 单个报告 JSON（自动生成，无需手写）

```json
{
  "id": "2026-06-14-report-title",
  "title": "报告标题",
  "agent": "market-watcher",
  "agentLabel": "市场观察员",
  "updatedAt": "2026-06-14T08:30:00Z",
  "summary": "不超过两句话的摘要",
  "tags": ["市场", "BTC"],
  "importance": "high",
  "content": "# Markdown 正文\n\n支持标题、**粗体**、*斜体*、[链接](url)、表格、代码块、列表、引用块。"
}
```

### agents.json

```json
{
  "agents": [
    { "name": "market-watcher", "label": "市场观察员" },
    { "name": "tech-insights",  "label": "技术情报员" }
  ]
}
```

### panel.json（widget 列表）

```json
{
  "widgets": [
    { "order": 1, "type": "json", "title": "市场快照",
      "source": "agents/market-watcher/panel/snapshot.json",
      "updatedAt": "2026-06-14T08:30:00Z" },
    { "order": 2, "type": "html", "title": "技术动态",
      "source": "agents/tech-insights/panel/highlights.html",
      "updatedAt": "2026-06-14T08:30:00Z" },
    { "order": 3, "type": "markdown", "title": "每日摘要",
      "source": "agents/daily-summary/panel/daily.md",
      "updatedAt": "2026-06-14T08:30:00Z" }
  ]
}
```

`type` 可选值：`json`（结构化数据，渲染为 KPI 列表/表格）、`html`（直接嵌入 HTML 片段）、`markdown` / `md`、`text`（简单文字）。

## 常见错误排查

| 问题 | 原因 | 解决 |
| --- | --- | --- |
| 页面空白/显示"加载中" | index.html 不存在或被覆盖 | 重新执行 `init` 或手动补全 index.html |
| 报告没有出现在列表 | 没更新 `reports/index.json` | `publish-report` 子命令会自动更新；若手动创建报告，需手动更新 `index.json` |
| 新 Agent 的报告不显示 | 没在 `system/agents.json` 注册 | 执行 `add-agent` 或手工添加 entries |
| 中文文件名在某些 Git 环境显示异常 | 报告文件名会 slug 化，不影响运行 | 无需手动干预 |
| widget 面板显示 "加载失败" | `panel.json` 中 source 路径错误 | 检查路径是否为仓库相对路径 |

## 设计原则

- **零依赖**：脚本只用 Node 内置模块（`fs`, `path`, `http`, `url`），前端也无构建工具
- **数据/代码分离**：Agent 数据（`agents/`）与站点代码（`assets/`, `index.html`）完全分离；各 Agent 互不干扰
- **纯静态**：GitHub Pages 托管，无后端。前端通过 `fetch()` 动态加载 JSON 文件
- **约定优于配置**：标准化目录结构 + 标准化 JSON 字段，降低各 Agent 接入成本
