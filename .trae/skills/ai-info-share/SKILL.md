---
name: "ai-info-share"
description: "将投研报告、分析结果等结构化信息同步到指定渠道（飞书/钉钉/企微/自定义API/Git仓库）。Invoke when user asks to share research reports, daily analysis results, or any structured output to external platforms."
---

# AI 信息同步 Skill

## 功能
将生成的投研报告、分析结果等结构化内容同步到外部协作平台、Git 仓库或自定义端点。

## 支持的同步渠道

### 1. 飞书/Lark
- 通过飞书机器人 Webhook 发送到指定群聊
- 支持消息卡片（interactive 消息类型）

### 2. 钉钉
- 通过钉钉机器人 Webhook 发送到指定群聊
- 支持 Markdown 格式消息

### 3. 企业微信
- 通过企微机器人 Webhook 发送群消息
- 支持图文消息卡片

### 4. 自定义 HTTP API
- 调用用户指定的 API 端点发送报告内容
- 支持 POST JSON 格式数据

### 5. Git 仓库同步（Gitee/GitHub）
- 将投研内容提交到 Git 仓库并推送到远程
- 支持直接传入内容或复制文件
- 自动生成提交信息

## 配置

### Webhook 渠道配置
通过环境变量或配置文件读取：

```bash
# 飞书
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 钉钉
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx

# 企微
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx

# 自定义 API
CUSTOM_API_URL=https://your-api.com/report
CUSTOM_API_KEY=xxx
```

配置也可写入 `~/.ai-info-share.json`：
```json
{
  "feishu": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
  "dingtalk": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
  "wechat": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
  "custom": {
    "url": "https://your-api.com/report",
    "key": "xxx"
  }
}
```

### Git 仓库配置
Git 同步自动使用工作区的 Git 配置（remote origin），无需额外环境变量。

## 脚本用法

### 1. Webhook 同步（share.js）

```bash
# 同步指定报告到所有已配置渠道
node /Users/xuchen.xia/.scripts/ai-info-share/share.js --report=/path/to/report.html

# 同步到指定渠道
node /Users/xuchen.xia/.scripts/ai-info-share/share.js --report=/path/to/report.html --channel=feishu

# 测试渠道连通性
node /Users/xuchen.xia/.scripts/ai-info-share/share.js --test
```

### 2. Git 仓库同步（git-sync.js）

```bash
# 查看 Git 仓库状态
node /Users/xuchen.xia/.scripts/ai-info-share/git-sync.js --list

# 将内容写入并提交到 Git 仓库
node /Users/xuchen.xia/.scripts/ai-info-share/git-sync.js \
  --content="markdown内容" \
  --target="daily-research/2026-06-14/plan.md" \
  --message="盛龙股份建仓计划"

# 复制文件到工作区并提交
node /Users/xuchen.xia/.scripts/ai-info-share/git-sync.js \
  --file=/path/to/report.html \
  --target="daily-research/2026-06-14/report.html" \
  --message="每日投研报告 2026-06-14"

# 设置工作区路径（默认使用当前工作区）
WORKSPACE_PATH=/path/to/repo node /Users/xuchen.xia/.scripts/ai-info-share/git-sync.js \
  --content="内容" --target="path/file.md" --message="提交说明"
```