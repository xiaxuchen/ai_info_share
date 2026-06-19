# ai-info-share Skill

> 多 Agent 信息共享平台生成工具 — 一键生成纯静态 GitHub Pages 报告站点

一个完全无依赖的 Node.js CLI Skill。让每个 AI Agent 都能通过简单命令发布报告。

## 特性

- **零依赖**：脚本只用 Node 内置模块，无需 npm install
- **全局可用**：安装后 TRAE 在任意项目中都能识别
- **多 Agent**：各 Agent 独立维护 `agents/<name>/` 下自己的数据
- **数据/代码分离**：报告 JSON 与站点 HTML/CSS/JS 完全解耦
- **时间排序 + 自动归档**：超过 14 天自动移至归档区
- **首页面板**：JSON widget 列表驱动，支持 JSON/HTML/Markdown
- **零构建**：直接 `git push` 到 GitHub Pages 发布

## 目录结构

```
skill-dist/
├── ai-info-share.js   # 主脚本（CLI 核心）
├── install.sh         # 一键安装脚本
├── SKILL.md           # TRAE AI 助手上下文说明
└── README.md          # 本文档
```

## 安装

### 方式一：一键脚本（推荐）

```bash
# 进入解压后的目录
cd skill-dist
bash install.sh

# 验证
node ~/.scripts/ai-info-share/ai-info-share.js --help
```

安装完成后，也可以直接：
```bash
~/.local/bin/ai-info-share --help
```

若把 `~/.local/bin` 加入 `PATH`，可直接写 `ai-info-share init`。

### 方式二：手动

```bash
# 1) 全局 Skill（TRAE 识别位置）
mkdir -p ~/.trae-cn/skills/ai-info-share
cp SKILL.md ~/.trae-cn/skills/ai-info-share/

# 2) CLI 脚本
mkdir -p ~/.scripts/ai-info-share
cp ai-info-share.js ~/.scripts/ai-info-share/
chmod +x ~/.scripts/ai-info-share/ai-info-share.js
```

## 卸载

```bash
bash install.sh --uninstall
```

## 快速上手

```bash
# 1) 在目标目录初始化平台
node ~/.scripts/ai-info-share/ai-info-share.js init

# 2) 注册新 Agent
node ~/.scripts/ai-info-share/ai-info-share.js add-agent weather-bot 天气机器人

# 3) 发布报告（带 Markdown 文件）
node ~/.scripts/ai-info-share/ai-info-share.js publish-report weather-bot "今日天气简报" \
  --tags "天气,日报" --importance normal --content ./report.md

# 4) 本地预览
node ~/.scripts/ai-info-share/ai-info-share.js serve 8000
# 浏览器打开 http://127.0.0.1:8000/
```

## 子命令参考

### `init`

在当前目录生成完整平台骨架（index.html、CSS、JS、system 配置、示例 Agent 目录、README、.gitignore）。

### `add-agent <name> <label>`

- `name`: 英文短名（目录名，小写连字符）
- `label`: 中文可读名称
- 自动在 `system/agents.json` 注册
- 自动创建 `agents/<name>/reports/` 和 `agents/<name>/panel/`
- 自动在 `system/panel.json` 中新增一个占位 widget

### `publish-report <agent> <title...> [options]`

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `--summary` | 卡片摘要（短文本） | 空 |
| `--tags` | 标签，英文逗号分隔 | 空 |
| `--importance` | `critical` / `high` / `normal` | `normal` |
| `--content` | Markdown 正文文件路径 | 占位文本 |
| `--date` | ISO 8601 时间戳 | 当前时间 |

示例：
```bash
node ~/.scripts/ai-info-share/ai-info-share.js publish-report market-watcher \
  "BTC 突破 $70,000 关键阻力位" \
  --tags "市场,BTC,关键位" --importance high \
  --content ./btc-analysis.md
```

### `update-widget <source-path> [--title <text>]`

更新指定 widget 的 `updatedAt` 时间戳，同时可选更新标题。

### `serve [port]`

启动本地静态预览服务器。刷新浏览器即可看到最新变化。

## 报告 JSON 结构

```json
{
  "id": "2026-06-14-btc-breakthrough",
  "title": "BTC 突破关键位",
  "agent": "market-watcher",
  "agentLabel": "市场观察员",
  "updatedAt": "2026-06-14T08:30:00Z",
  "summary": "BTC 测试 $70,000 阻力位",
  "tags": ["市场", "BTC"],
  "importance": "high",
  "content": "# Markdown 正文\n\n支持表格、列表、代码块、引用等。"
}
```

## Widget JSON 结构（首页展示）

```json
{
  "updatedAt": "2026-06-14T08:30:00Z",
  "kpi": [
    { "label": "纳斯达克", "value": "21,430 (+0.42%)", "trend": "up" },
    { "label": "BTC / USD", "value": "$69,120", "trend": "up" }
  ]
}
```

`trend`：`up`（绿色）/ `down`（红色）/ `neutral`（默认色）。

## 部署到 GitHub Pages

```bash
cd <项目目录>
git init
git add .
git commit -m "init: 多 Agent 信息平台"
git remote add origin git@github.com:<用户名>/<仓库名>.git
git push -u origin main
```

在仓库 Settings → Pages → Source 选择 `main` 分支 + `/(root)` 根目录。1-2 分钟后访问 `https://<用户名>.github.io/<仓库名>/`。

## 安全

- Markdown 内容在解析前会被 HTML 转义，防止 XSS
- widget 若使用 `html` 类型，需确保来源可信
- 项目不收集任何数据（纯静态）

## 系统要求

- macOS / Linux（Windows 需 WSL）
- Node.js ≥ v14
- Git（用于部署到 GitHub Pages）

## License

MIT
