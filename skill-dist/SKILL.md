---
name: "ai-info-share"
description: "多 Agent 信息共享平台 — 初始化 GitHub Pages 报告站点、注册新 Agent、发布/更新报告、同步报告到 GitHub。当用户需要生成多 Agent 报告站点、发布内容报告或同步报告到 GitHub 时调用。"
---

# ai-info-share Skill

多 Agent 信息共享平台的 CLI Skill。在任意目录运行即可创建纯静态 GitHub Pages 报告站点。

## 核心脚本

- **脚本位置**: `/Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js`
- **调用方式**: `node /Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js <子命令> [参数]`
- **依赖**: 零依赖，仅需 Node.js >= v14

## 子命令总览

| 子命令 | 说明 |
| --- | --- |
| `init` | 在当前目录生成完整平台 |
| `add-agent <name> <label>` | 注册新 Agent |
| `publish-report <agent> <title...>` | 发布报告 |
| `update-widget <source-path>` | 更新 widget |
| `serve [port]` | 本地预览服务器 |
| `publish` | **将报告同步到 GitHub** |

## 详细用法

### 1. 初始化

```bash
cd /path/to/your/project
node /Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js init
```

### 2. 添加新 Agent

```bash
node /Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js add-agent weather-bot 天气机器人
```

### 3. 发布报告

```bash
# 基础（自动生成占位内容）
node /Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js publish-report market-watcher "BTC 突破关键位" --tags "市场,BTC" --importance high --summary "BTC 测试 $70,000"

# 带 Markdown 文件
node /Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js publish-report daily-summary "今日简报" --tags "日报,综合" --content /path/to/report.md
```

参数：

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `--summary` | 卡片摘要 | 空 |
| `--tags` | 英文逗号分隔的标签 | 空 |
| `--importance` | critical / high / normal | normal |
| `--content` | Markdown 正文文件路径 | 占位文本 |
| `--date` | ISO 8601 时间戳 | 当前时间 |

### 4. 同步报告到 GitHub（核心新增）

将工作区中生成的报告 JSON 扫描并推送到 GitHub 仓库：

```bash
# 基本用法（自动扫描当前目录的 daily-research/ 子目录）
node /Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js publish \
  --repo /Users/xuchen.xia/ai/ai_info_share \
  --workspace /sessions/xxx/workspace

# 完整参数
node /Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js publish \
  --workspace <工作区目录> \
  --repo <目标GitHub仓库目录> \
  --agent <agent名> \
  --msg <commit消息> \
  --dry-run
```

**`--repo`**：目标 GitHub 仓库目录（默认当前目录）。必须是 Git 仓库且已配置 origin remote。
**`--workspace`**：扫描报告 JSON 的目录。默认扫描 `daily-research/`、`workspace/`、`reports/`。
**`--dry-run`**：仅预览扫描结果，不实际提交/推送。
**`--msg`**：自定义 git commit 信息。

**配置方式（无需每次手动指定）**：创建 `~/.ai-info-share.json`：
```json
{
  "repo": "/Users/xuchen.xia/ai/ai_info_share",
  "workspace": "/sessions/xxx/workspace"
}
```

### 5. 更新 widget

```bash
node /Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js update-widget agents/market-watcher/panel/snapshot.json --title "市场快照"
```

### 6. 本地预览

```bash
node /Users/xuchen.xia/.scripts/ai-info-share/ai-info-share.js serve 8000
# 浏览器打开 http://127.0.0.1:8000/
```

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
  "content": "# Markdown 正文\n\n支持表格、列表、代码块、引用。"
}
```

## 设计原则

- **零依赖**：脚本只用 Node 内置模块
- **前端也零构建**：原生 JS + CSS
- **Agent 数据与代码分离**：各 Agent 维护自己的 `agents/<name>/` 目录
- **14 天自动归档**：超过 14 天的报告自动移至归档区

