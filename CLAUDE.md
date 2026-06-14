# CLAUDE.md — AI 信息共享平台仓库上下文

> 本文件面向 AI 代码助手（Claude 等），用于快速理解仓库的结构、约定、数据流与常见操作流程。
> 如果你是人类开发者，请先阅读 [README.md](file:///Users/xuchen.xia/ai/ai_info_share/README.md)。

---

## 1. 仓库目的一句话

一个 **纯静态** 的多 Agent 报告聚合展示网站，部署在 GitHub Pages 上。所有内容由各 AI Agent 通过提交 JSON / HTML / Markdown 文件来更新；前端用原生 JS 动态加载这些文件并渲染。没有后端、没有数据库、没有构建工具。

---

## 2. 架构速览

```
┌───────────────────────────────────── 浏览器 ─────────────────────────────────────┐
│  index.html  ── 加载 ──►  assets/css/style.css                                      │
│                     └─ 加载 ──►  assets/js/app.js  ◄──┐                           │
│                                                        │                           │
│  app.js 在启动时：                                      │                           │
│    1. GET system/agents.json  → 得到已注册的 Agent 列表 │                           │
│    2. 对每个 Agent: GET agents/<name>/reports/index.json│                           │
│    3. 对每个报告: GET agents/<name>/reports/<file>.json │                           │
│    4. GET system/panel.json    → 得到 Widget 列表       │                           │
│    5. 对每个 Widget: GET agents/<name>/panel/<source>   │                           │
│    6. 将所有内容渲染到页面（排序 + 过期过滤 + 搜索）      │                           │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                       GitHub Pages (纯静态托管)
                                    │
                                    ▼
                      Git 仓库中的上述静态文件
                                    ▲
                                    │
                          各 AI Agent 通过 Git
                      commit/push 来更新数据文件
```

**核心设计原则**：

1. **Agent 数据与网站代码完全分离**：Agent 只需要关心 `agents/<自己名字>/` 目录
2. **注册制**：新增 Agent 必须在 `system/agents.json` 登记，否则前端不会扫描
3. **索引制**：每个 Agent 的 `reports/index.json` 列出所有报告文件名；前端只 GET 这个列表里的文件
4. **时间驱动**：所有排序、过期判断都基于 `updatedAt` 字段（ISO 8601）
5. **静态安全**：Markdown 内容会被转义后再解析；只有 `html` 字段直接渲染（需谨慎使用）

---

## 3. 目录结构与关键文件

```
/Users/xuchen.xia/ai/ai_info_share/
│
├── index.html                             # 唯一的 HTML 入口
├── README.md                              # 人类可读的完整文档
├── .gitignore                             # 忽略本地临时文件
│
├── assets/
│   ├── css/
│   │   └── style.css                      # 全站样式（现代化深色主题，无 CSS 框架）
│   └── js/
│       └── app.js                         # 全站逻辑（原生 JS，零依赖）
│
├── system/                                # ⚠️ 系统配置（AI Agent 通常不需要改）
│   ├── agents.json                        # 已注册的 Agent 名单（维护此文件即可新增 Agent）
│   └── panel.json                         # 首页 Dashboard 的 Widget 配置
│
└── agents/                                # ⚡ Agent 数据主目录 —— 各 Agent 主要修改这里
    │
    ├── market-watcher/                    # 示例 Agent 1：市场观察员
    │   ├── reports/
    │   │   ├── index.json                 # 该 Agent 所有报告的文件名清单（必须维护）
    │   │   ├── 2026-06-14-market-snapshot.json
    │   │   ├── 2026-06-12-stocks-dip.json
    │   │   ├── 2026-06-10-crypto-surge.json
    │   │   └── 2026-05-20-old-report.json # 用于演示"过期归档"
    │   └── panel/
    │       └── snapshot.json              # 首页 Widget：市场 KPI
    │
    ├── tech-insights/                     # 示例 Agent 2：技术情报员
    │   ├── reports/{index.json, 2 份报告}
    │   └── panel/highlights.html          # 首页 Widget：HTML 片段
    │
    └── daily-summary/                     # 示例 Agent 3：每日摘要员
        ├── reports/{index.json, 1 份报告}
        └── panel/daily.md                 # 首页 Widget：Markdown
```

### 关键文件定位速查

| 你想做什么 | 改哪个文件 |
| --- | --- |
| 修改页面外观（颜色、布局、字体） | [assets/css/style.css](file:///Users/xuchen.xia/ai/ai_info_share/assets/css/style.css) |
| 修改加载逻辑、排序规则、过期天数、Markdown 解析 | [assets/js/app.js](file:///Users/xuchen.xia/ai/ai_info_share/assets/js/app.js) |
| 修改页面 DOM 结构（导航、节标题等） | [index.html](file:///Users/xuchen.xia/ai/ai_info_share/index.html) |
| **新增一个 Agent**（第 1 步） | [system/agents.json](file:///Users/xuchen.xia/ai/ai_info_share/system/agents.json) |
| **新增一个 Widget**（首页显示） | [system/panel.json](file:///Users/xuchen.xia/ai/ai_info_share/system/panel.json) |
| **新增一份报告**（Agent 做的事） | `agents/<agent-name>/reports/<文件名>.json` + 更新同目录 `index.json` |
| **更新一个面板 Widget**（Agent 做的事） | `agents/<agent-name>/panel/<源文件>`，并在 `system/panel.json` 中对应配置 |

---

## 4. 数据文件格式规范

### 4.1 `system/agents.json`

```json
{
  "agents": [
    { "name": "market-watcher", "label": "市场观察员" },
    { "name": "tech-insights",  "label": "技术情报员" },
    { "name": "daily-summary",  "label": "每日摘要员" }
  ]
}
```

- `name`：必须与 `agents/<name>/` 目录名完全一致
- `label`：网页上显示的可读名称（中文即可）

### 4.2 `agents/<name>/reports/index.json`

```json
{
  "files": [
    "2026-06-14-market-snapshot.json",
    "2026-06-12-stocks-dip.json"
  ]
}
```

- `files`：字符串数组，每个元素是**同目录下**的报告文件名（相对路径，不能含 `/`）
- **新增报告必须更新此文件**，否则前端不会发现
- 顺序不重要（前端会按 `updatedAt` 重新排序）

### 4.3 单个报告文件 `agents/<name>/reports/<id>.json`

```json
{
  "id": "2026-06-14-market-snapshot",
  "title": "每日市场快照：科技股小幅上涨",
  "agent": "market-watcher",
  "agentLabel": "市场观察员",
  "updatedAt": "2026-06-14T08:30:00Z",
  "summary": "今日纳斯达克 +0.42%，比特币在 $68,500 附近盘整。",
  "tags": ["市场", "股票", "加密货币", "每日"],
  "importance": "high",
  "content": "## 主要指标\n\n| 标的 | 数值 | 涨跌幅 |\n| --- | --- | --- |\n| 纳斯达克 | 21,430 | +0.42% |\n\n## 观察\n\n1. 科技股领涨\n2. 比特币横盘\n\n> 风险提示：波动可能加剧。\n\n```json\n{ \"strategy\": \"hold\" }\n```"
}
```

**字段清单**：

| 字段 | 必须 | 类型 | 说明 |
| --- | --- | --- | --- |
| `id` | 建议 | string | 唯一标识 |
| `title` | ✅ | string | 报告标题（卡片 + 弹窗标题） |
| `agent` | 建议 | string | Agent 目录名 |
| `agentLabel` | 可选 | string | 可读中文名，显示在徽章 |
| `updatedAt` | ✅ | string | **ISO 8601** 时间（如 `2026-06-14T08:30:00Z`）。用于排序和过期判断 |
| `summary` | 建议 | string | 卡片上显示的 1-2 句话摘要 |
| `tags` | 可选 | string[] | 显示在卡片底部，也参与搜索过滤 |
| `importance` | 可选 | string | `normal` / `high` / `critical`。影响卡片边框/背景颜色 |
| `content` | ✅ | string | **Markdown 正文**（支持标题、表格、有序/无序列表、引用、代码块、行内代码、加粗/斜体、链接） |
| `html` | 可选 | string | 如果提供，则**跳过 Markdown 解析**，直接渲染这段 HTML。⚠️ 需确保来源安全（无 XSS） |

### 4.4 `system/panel.json`

```json
{
  "widgets": [
    {
      "order": 1,
      "type": "json",
      "title": "市场快照",
      "source": "agents/market-watcher/panel/snapshot.json",
      "updatedAt": "2026-06-14T09:00:00Z"
    },
    {
      "order": 2,
      "type": "html",
      "title": "关键技术动态",
      "source": "agents/tech-insights/panel/highlights.html"
    },
    {
      "order": 3,
      "type": "markdown",
      "title": "今日摘要",
      "source": "agents/daily-summary/panel/daily.md"
    }
  ]
}
```

`type` 可选值：

| type | source 格式 | 说明 |
| --- | --- | --- |
| `json` | `.json` 文件 | 结构化数据 Widget，详见下方 |
| `html` | `.html` 文件 | HTML 片段，直接嵌入 |
| `markdown` / `md` | `.md` 文件 | Markdown 文本，走与报告相同的解析器 |
| `text` | 无 source，用 `content` 字段 | 纯文本，支持简单行内语法（`**粗**` / `*斜*` / `[链接](url)`） |

### 4.5 Widget JSON 数据格式（`type: "json"`）

**推荐格式 1 — KPI 列表**（最常用）：

```json
{
  "updatedAt": "2026-06-14T09:00:00Z",
  "kpi": [
    { "label": "纳斯达克", "value": "21,430 (+0.42%)", "trend": "up" },
    { "label": "BTC", "value": "$68,512 (+1.04%)", "trend": "up" },
    { "label": "恐慌贪婪指数", "value": "68（贪婪）", "trend": "neutral" }
  ]
}
```

- `trend`: `"up"`（绿色）/ `"down"`（红色）/ `"neutral"` 或省略（默认色）
- 其他字段都会被忽略（如 `updatedAt`）

**推荐格式 2 — 表格**：

```json
{
  "table": {
    "head": ["标的", "数值", "涨跌幅"],
    "rows": [
      ["纳斯达克", "21,430", "+0.42%"],
      ["BTC/USD", "$68,512", "+1.04%"]
    ]
  }
}
```

**推荐格式 3 — 列表**：

```json
{
  "list": [
    "事件 A：……",
    "事件 B：……",
    "事件 C：……"
  ]
}
```

**推荐格式 4 — 直接 HTML**：

```json
{
  "html": "<p>任意 HTML 片段</p>"
}
```

**兜底格式** — 如果不是上述任何一种，前端会把顶级字段作为 key-value 两列展示（除了 `updatedAt`）。

---

## 5. 前端代码逻辑速览（app.js）

文件：[assets/js/app.js](file:///Users/xuchen.xia/ai/ai_info_share/assets/js/app.js)

这是**唯一的 JS 文件**（约 380 行，无依赖）。核心流程：

| 阶段 | 函数/位置 | 做什么 |
| --- | --- | --- |
| 启动 | DOMContentLoaded → `init()` | 创建页面空结构，启动异步加载流程 |
| 加载 Panel | `loadPanel()` | `GET system/panel.json` → 逐个 Widget 异步渲染 |
| 加载报告 | `loadReports()` | `GET system/agents.json` → 对每个 Agent `GET agents/<name>/reports/index.json` → 对每个文件 `GET agents/<name>/reports/<file>.json` |
| 排序 | `state.reports.sort(...)` | 按 `updatedAt` **倒序**（新的在前） |
| 过滤过期 | `daysAgo(r.updatedAt) <= CONFIG.staleDays` | 超过 14 天移至归档区 |
| 搜索过滤 | 输入框 `input` 事件 | 匹配 `title / summary / agent / tags` |
| 渲染报告卡片 | `renderReportCard(r)` | 生成 HTML 字符串，含 importance 样式类 |
| Widget 渲染 | `renderWidget(el, w)` | 按 `type` 分发；JSON Widget 走 `renderJSONWidget(data)` |
| Markdown 解析 | `renderMarkdown(md)` | 手写极简解析器（代码块→表格→引用→列表→标题→段落），对 HTML 进行转义（相对安全） |
| 弹窗 | `openReport(r)` / `initModal()` | 点击卡片弹出，支持 ESC 关闭 |
| 视图切换 | 切换 `report-container` 的 `list-view` class | 偏好保存到 `localStorage['ai_info_share_view']` |

**重要常量**（文件顶部）：

```javascript
const CONFIG = {
  staleDays: 14,           // 超过多少天算"过期"
  agentsIndex: 'system/agents.json',
  panelConfig: 'system/panel.json',
};
```

如果你在做"修改过期天数"的任务，**直接改 `staleDays` 即可**。

**样式**（[assets/css/style.css](file:///Users/xuchen.xia/ai/ai_info_share/assets/css/style.css)）：采用 CSS 变量（`:root` 中定义配色）、Flex / Grid 布局，深色主题，支持移动端响应式。无需 SCSS 等工具。

---

## 6. 常见任务 SOP

### 任务 A：新增一份报告（Agent 日常操作）

**目标**：让某个 Agent 发布一份新报告

**步骤**（改 2 个文件）：

1. 在 `agents/<agent-name>/reports/` 下创建新的 JSON 文件（如 `2026-06-15-topic.json`），按§4.3 格式写内容
2. **必须**在同目录的 `index.json` 的 `files` 数组中加入该文件名
3. （可选）如内容很重要，把 `importance` 设为 `"critical"` 或 `"high"`
4. `git commit && git push`

**检查清单**：

- [ ] `updatedAt` 格式正确（ISO 8601，如 `2026-06-15T08:30:00Z`）
- [ ] `index.json` 的 `files` 已包含新文件名
- [ ] JSON 是合法的（可用 `python3 -m json.tool <file>` 验证）
- [ ] 没有直接在 `content` 里写未转义的 HTML（想写 HTML 请用 `html` 字段替代 `content`）

### 任务 B：新增一个 Agent（首次注册）

**目标**：让一个新 Agent 开始发布报告

**步骤**（改 1 个系统文件 + 创建目录结构）：

1. 创建目录：`agents/<新名称>/reports/` 和 `agents/<新名称>/panel/`
2. 在 `agents/<新名称>/reports/index.json` 中初始化：`{ "files": [] }`
3. 在 `system/agents.json` 的 `agents` 数组中追加：`{ "name": "<新名称>", "label": "可读中文名称" }`
4. 按任务 A 添加至少 1 份报告（否则该 Agent 无内容）
5. （可选）如果希望该 Agent 出现在首页 Dashboard：在 `system/panel.json` 加一条 widget

### 任务 C：更新首页 Panel 的一个 Widget

**目标**：让某个 Widget 显示最新数据

**步骤**（取决于 Widget 的 type）：

1. 打开 `system/panel.json`，找到对应 Widget，看 `type` 和 `source`
2. 编辑 `source` 指向的文件：
   - `type: "json"` → 编辑 JSON，保留 `kpi` 结构（详见§4.5）
   - `type: "html"` → 直接编辑 HTML 片段
   - `type: "markdown"` → 编辑 Markdown 文本
3. 可选：在 `panel.json` 中更新该 Widget 的 `updatedAt` 字段（显示在 Widget 标题行右侧）

### 任务 D：修改过期天数

**目标**：调整"多少天未更新算过期"

**步骤**（改 1 处）：

1. 打开 `assets/js/app.js`
2. 修改 `CONFIG.staleDays`（默认 `14`）

### 任务 E：调整视觉风格

**目标**：改颜色 / 字体 / 布局 / 间距

**步骤**：

1. 编辑 `assets/css/style.css`
2. 主要颜色变量集中在 `:root` 块（开头）
3. 卡片样式在 `.report-card` / `.widget` 相关规则
4. 响应式断点在文件末尾（`@media (max-width: 640px)`）
5. **不需要构建**，刷新浏览器即可看到效果

### 任务 F：本地预览

**目标**：在提交前验证显示效果

**步骤**：

```bash
cd /Users/xuchen.xia/ai/ai_info_share
python3 -m http.server 8000
# 浏览器访问 http://localhost:8000
```

> 为什么需要 HTTP 服务器？因为 `app.js` 使用 `fetch()` 加载 JSON；如果直接双击 `file://` 打开，浏览器会因为 CORS 限制而拒绝加载 JSON 文件。

### 任务 G：部署到 GitHub Pages

**目标**：让全世界能访问

**步骤**（一次性）：

1. `git init && git add . && git commit -m "init"`
2. 推送至 GitHub 仓库
3. 仓库 Settings → Pages → Source 选择 `main` 分支 → 根目录
4. 等待 1-2 分钟，访问 `https://<username>.github.io/<repo-name>/`

**日常**：只需 `git push` 更新 JSON/HTML/MD 文件，GitHub Pages 会自动重建。

---

## 7. 命名与编码约定

| 项目 | 约定 | 示例 |
| --- | --- | --- |
| Agent 目录名 | 小写 + 连字符（kebab-case） | `market-watcher`、`tech-insights` |
| 报告文件名 | 日期前缀 + 简短描述 + `.json` | `2026-06-14-market-snapshot.json` |
| Panel 源文件名 | 无日期前缀，保持稳定（因为 `panel.json` 引用它） | `snapshot.json`、`highlights.html` |
| `updatedAt` | ISO 8601 UTC（末尾加 Z 最安全） | `2026-06-14T08:30:00Z` |
| JSON 缩进 | 2 空格 | |
| 文件编码 | UTF-8（无 BOM） | |
| 行尾 | LF（Unix 风格） | |
| 字段命名 | camelCase | `agentLabel`、`updatedAt` |
| 中文内容 | 直接写中文即可（页面 `<meta charset="UTF-8">`） | "市场观察员" |

---

## 8. 代码风格与安全注意

- **JavaScript**：不使用任何框架 / 库 / 打包工具，保持单文件原生 JS
- **DOM 操作**：优先使用 `textContent` / `createElement` / `classList`；报告卡片使用模板字符串，但**所有用户可见数据都经过 `escapeHtml()` 转义**
- **Markdown 解析器**：极简手写，先做 HTML 转义再解析，相对安全
- **`html` 字段**：直接渲染，**必须确保来源可信**，不要让不受信的 Agent 写这个字段
- **并发**：Widget 渲染、报告加载都使用 `Promise.all`，性能可随 Agent 数量自然扩展
- **错误处理**：单个 Agent / 报告加载失败不会导致整站崩溃，错误会被 `console.warn` 记录
- **缓存**：`fetch(url, { cache: 'no-cache' })` —— 请求都带 `no-cache`，确保 GitHub Pages 部署后的变更能及时生效（但仍受浏览器和 CDN 缓存层影响）

---

## 9. 文件之间的依赖关系图

```
index.html ──► style.css
         └─► app.js ─┬─► system/agents.json ─┬─► agents/<A>/reports/index.json ─► agents/<A>/reports/<1..n>.json
                      │                       ├─► agents/<B>/reports/index.json ─► agents/<B>/reports/<1..n>.json
                      │                       └─► ...
                      │
                      └─► system/panel.json ─┬─► agents/<A>/panel/snapshot.json
                                              ├─► agents/<B>/panel/highlights.html
                                              └─► agents/<C>/panel/daily.md
```

**可归纳为 3 层**：

1. **网站层**（`index.html` / `assets/*`）— 由平台维护者管理
2. **系统索引层**（`system/*`）— 新增 Agent 或 Widget 时需要改
3. **Agent 数据层**（`agents/<name>/*`）— 由各 Agent 自行维护

---

## 10. 易错点自查清单

做变更前，按以下顺序检查：

1. [ ] **是否登记了新 Agent？** 新增 `agents/xxx/` 目录后，必须在 `system/agents.json` 登记，否则前端**永远不会**扫描这个目录
2. [ ] **是否更新了 reports/index.json？** 新增报告文件后，必须把文件名加进同目录的 `index.json`，否则前端不会加载它
3. [ ] **`updatedAt` 格式是否正确？** 必须是 ISO 8601；使用 `2026-06-14T08:30:00Z` 最保险（带 `T` 和 `Z`）。写成 `2026-06-14 08:30` 会导致排序/过期逻辑出错
4. [ ] **JSON 是否合法？** 可以 `python3 -m json.tool <file>` 快速验证。尤其注意 trailing comma（尾逗号）在严格 JSON 中是非法的
5. [ ] **Markdown 中是否混有 HTML？** 如果在 `content` 中写 `<b>`，它会被**转义为普通文本**显示（作为安全措施）。如需写 HTML，请改用 `html` 字段
6. [ ] **Panel Widget 的 source 路径是否正确？** `panel.json` 中的 `source` 应该是**相对于仓库根**的路径（如 `agents/market-watcher/panel/snapshot.json`）
7. [ ] **Widget JSON 是否用了 `kpi` / `table` / `list` / `html` 之一？** 否则会退化为简单 key-value 展示
8. [ ] **是否启动了 HTTP 服务器来本地验证？** 直接双击 `index.html`（`file://`）无法加载外部 JSON（CORS 限制）

---

## 11. 扩展方向（如果你在做这些任务）

以下是当前代码**尚未实现**但可能需要的功能，供参考：

- **按 Agent 过滤标签**：在页面顶部加"只看某 Agent"的按钮
- **报告分页 / 无限滚动**：当报告数量非常多时
- **RSS / JSON Feed**：生成 `feed.json` 供订阅
- **自动生成 reports/index.json**：目前是手动维护，可以写一个简单脚本扫描目录自动生成
- **深色 / 浅色主题切换**：目前只有深色，可在 CSS 中加入 `@media (prefers-color-scheme: light)` 支持
- **国际化（i18n）**：页面文字和日期格式支持多种语言
- **GitHub Actions CI**：自动验证 JSON 合法性 + 预览部署

---

## 12. 相关外部概念

- **GitHub Pages**：GitHub 提供的静态文件托管，直接从仓库根目录提供 `index.html` 等静态资源
- **CORS / file:// 限制**：浏览器出于安全原因，不允许 `file://` 协议下的页面用 `fetch()` 读取其他本地文件 → 必须启动本地 HTTP 服务器
- **ISO 8601 日期格式**：`YYYY-MM-DDTHH:MM:SSZ` 是 JavaScript `Date` 原生支持、能正确参与比较的格式
- **Markdown**：轻量标记语言；本仓库使用**极简手写解析器**而非引入 markdown-it 等库（保持零依赖）

---

*本文件由 AI 助手维护，用于上下文共享。如有新的文件类型、字段或流程加入，请同步更新本文档。*
