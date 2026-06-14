# PDF 研报 → 知识图谱 实施方案

## 总体流程

```
PDF (已转) → 重命名 → 提取元数据 → 更新 Frontmatter + Wikilinks → 生成索引页 → Obsidian 图谱可视化
```

---

## Phase 1: 文件重命名（去除数字前缀）

### 命名模式分析

781 个文件存在多种模式：

| 模式 | 示例 | 数量（约） |
|------|------|-----------|
| `YYYYMMDD-代码-名称` | `20251209-688012-中微公司.md` | ~400+ |
| `YYYYMMDD_代码_名称` | `20260514_002916_深南电路.md` | ~200+ |
| `YYYY-名称` | `2025-三花智控，拓普集团，绿的谐波对比分析.md` | ~100+ |

### 去重策略

同一公司可能有多份报告（如宁德时代有2份），重名冲突处理：
- **保留最新日期的为主文件名**（如 `宁德时代.md`）
- **旧报告加日期后缀**（如 `宁德时代-20251209.md`）

### 实现

用 Python 脚本批量重命名，同时更新对应的 PDF 文件名保持一致。

---

## Phase 2: 元数据提取（SiliconFlow + Qwen3-8B）

### 工具

使用 `~/.kiro/skills/siliconflow-batch/scripts/siliconflow-batch.js`

### 提取目标

对每份研报提取结构化 JSON：

```json
{
  "file": "宁德时代.md",
  "primary_company": "宁德时代",
  "stock_code": "300750",
  "industry_tags": ["锂电池", "新能源汽车", "储能"],
  "related_companies": ["比亚迪", "亿纬锂能", "天赐材料"],
  "report_date": "2025-12-09",
  "report_type": "公司深度",
  "tech_fields": ["动力电池", "钠离子电池"],
  "key_metrics": {
    "revenue": "...",
    "market_cap": "..."
  }
}
```

### Prompt 设计

```
你是一个中文金融研报分析助手。请从以下研报内容中提取结构化信息。

提取规则：
1. primary_company: 研报分析的主要公司名称
2. stock_code: 6位股票代码（如果出现）
3. industry_tags: 所属行业/产业链标签（2-5个，如 锂电池、新能源汽车、储能）
4. related_companies: 文中提到的其他公司（只提取名称，不包含代码）
5. report_date: 研报日期
6. tech_fields: 涉及的关键技术领域
7. key_metrics: 关键财务指标（如果有）

返回纯 JSON，不要额外解释。
```

### 处理方式

1. 将 781 个 .md 文件路径和内容组装为 JSONL
2. 用 `siliconflow-batch.js` 批量调用 Qwen3-8B（免费）
3. 输出 `metadata.jsonl`
4. 并发数设为 5，失败自动重试 3 次

---

## Phase 3: 更新 Markdown 文件

读取 `metadata.jsonl`，对每个文件：

1. **更新 YAML Frontmatter**：
   ```yaml
   ---
   title: "宁德时代"
   company: "宁德时代"
   stock_code: "300750"
   tags: [锂电池, 新能源汽车, 储能]
   report_date: 2025-12-09
   report_type: 公司深度
   related: [比亚迪, 亿纬锂能, 天赐材料]
   ---
   ```

2. **在文档末尾添加关联链接**：
   ```markdown
   ## 相关公司
   - [[比亚迪]]
   - [[亿纬锂能]]
   - [[天赐材料]]
   
   #锂电池 #新能源汽车 #储能
   ```

这样 Obsidian 的 Graph View 会自动展示节点间的关系连线。

---

## Phase 4: 生成索引/总览页面

### 4.1 行业分类索引页

按 `industry_tags` 分组，生成 MOC (Map of Content) 页面：

```markdown
# 新能源汽车 产业链

## 核心公司
- [[宁德时代]] — 动力电池龙头
- [[比亚迪]] — 整车+电池
- [[亿纬锂能]] — 消费+动力电池
...
```

### 4.2 知识图谱 Mermaid 图

在主索引页生成 Mermaid 格式的关系图，展示核心公司的关联。

### 4.3 Dataview 查询

利用更新后的 YAML frontmatter，可以快速查询：
- `LIST WHERE contains(tags, "锂电池")`
- `TABLE stock_code, report_date FROM "0-公司深度"`

---

## 执行步骤

1. Phase 1 — 文件重命名脚本（~50行 Python）
2. Phase 2 — 构建 JSONL + 调用 siliconflow-batch（核心步骤，~5-10分钟）
3. Phase 3 — 更新 markdown frontmatter + 添加 wikilinks（脚本）
4. Phase 4 — 生成索引页和 Mermaid 图谱

### 成本估计

Qwen3-8B 免费，781 份研报每份约 2000 tokens 输入 + 200 tokens 输出 ≈ 172万 tokens，完全在免费额度内。

### 时间估计

- 重命名: ~1秒
- API 批量调用 (并发5，每条约2秒): 约 5-10 分钟
- 更新文件: ~1秒
- 生成索引: ~1秒
