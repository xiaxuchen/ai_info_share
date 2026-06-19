#!/usr/bin/env node
'use strict';

/**
 * AI 信息共享平台 — CLI 工具
 * 用法：node ~/.scripts/ai-info-share/ai-info-share.js <subcommand> [options]
 *
 * 子命令：
 *   init                                在当前目录初始化平台
 *   add-agent <name> <label>            注册新 Agent
 *   publish-report <agent> <title...>   发布报告
 *       --summary <text>
 *       --tags "tag1,tag2"
 *       --importance critical|high|normal
 *       --content <markdown-file>
 *       --date ISO8601
 *   update-widget <source-path>         更新 widget
 *       --type json|html|markdown
 *       --title <text>
 *   serve [port]                        启动本地预览服务器
 */

const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();

function readJSON(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function writeJSON(file, data) { fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n', 'utf8'); }
function ensureDir(dir) { if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true }); }
function slugify(str) {
  return String(str).toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-')
    .replace(/^-|-$/g, '').replace(/-+/g, '-') || 'item';
}
function nowISO() {
  const d = new Date(); const pad = n => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
    'T' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()) + 'Z';
}
function datePrefix(iso) { return iso.slice(0, 10); }

function printHelp() {
  console.log(`
AI 信息共享平台 CLI

用法: node ~/.scripts/ai-info-share/ai-info-share.js <subcommand> [options]

子命令:
  init                                在当前目录初始化
  add-agent <name> <label>            注册新 Agent
  publish-report <agent> <title...>   发布报告
      --summary <text>
      --tags "tag1,tag2"
      --importance critical|high|normal
      --content <markdown-file>
      --date ISO8601
  update-widget <source-path>         更新 widget
      --type json|html|markdown
      --title <text>
  serve [port]                        启动本地预览服务器
`);
}

function parseArgs(argv) {
  const args = { _: [], flags: {} };
  let cur = null;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '-h' || a === '--help') { args.flags.help = true; continue; }
    if (a.startsWith('--')) { cur = a.slice(2); args.flags[cur] = true; }
    else if (cur) { args.flags[cur] = a; cur = null; }
    else { args._.push(a); }
  }
  return args;
}

function inferType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.json') return 'json';
  if (ext === '.html' || ext === '.htm') return 'html';
  if (ext === '.md' || ext === '.markdown') return 'markdown';
  return 'json';
}

// ==================== 子命令 ====================

function cmdInit() {
  console.log('正在初始化 AI 信息共享平台于: ' + ROOT);

  const dirs = [
    'assets/css', 'assets/js', 'system',
    'agents/market-watcher/reports', 'agents/market-watcher/panel',
    'agents/tech-insights/reports', 'agents/tech-insights/panel',
    'agents/daily-summary/reports', 'agents/daily-summary/panel',
  ];
  dirs.forEach(d => ensureDir(path.join(ROOT, d)));

  fs.writeFileSync(path.join(ROOT, 'index.html'), generateIndexHTML(), 'utf8');
  fs.writeFileSync(path.join(ROOT, 'assets/css/style.css'), generateStyleCSS(), 'utf8');
  fs.writeFileSync(path.join(ROOT, 'assets/js/app.js'), generateAppJS(), 'utf8');

  writeJSON(path.join(ROOT, 'system/agents.json'), {
    agents: [
      { name: 'market-watcher', label: '市场观察员' },
      { name: 'tech-insights', label: '技术情报员' },
      { name: 'daily-summary', label: '每日摘要员' },
    ],
  });

  writeJSON(path.join(ROOT, 'system/panel.json'), {
    widgets: [
      { order: 1, type: 'json', title: '市场快照', source: 'agents/market-watcher/panel/snapshot.json', updatedAt: nowISO() },
      { order: 2, type: 'html', title: '关键技术动态', source: 'agents/tech-insights/panel/highlights.html', updatedAt: nowISO() },
      { order: 3, type: 'markdown', title: '今日摘要', source: 'agents/daily-summary/panel/daily.md', updatedAt: nowISO() },
    ],
  });

  writeJSON(path.join(ROOT, 'agents/market-watcher/reports/index.json'), { files: [] });
  writeJSON(path.join(ROOT, 'agents/tech-insights/reports/index.json'), { files: [] });
  writeJSON(path.join(ROOT, 'agents/daily-summary/reports/index.json'), { files: [] });

  writeJSON(path.join(ROOT, 'agents/market-watcher/panel/snapshot.json'), {
    updatedAt: nowISO(),
    kpi: [
      { label: '纳斯达克 100', value: '—', trend: 'neutral' },
      { label: 'BTC / USD', value: '—', trend: 'neutral' },
    ],
  });
  fs.writeFileSync(path.join(ROOT, 'agents/tech-insights/panel/highlights.html'),
    '<ul><li><strong>暂无数据</strong>：请技术情报员 Agent 更新此文件</li></ul>', 'utf8');
  fs.writeFileSync(path.join(ROOT, 'agents/daily-summary/panel/daily.md'),
    '- 请每日摘要员 Agent 更新此文件。\n', 'utf8');

  fs.writeFileSync(path.join(ROOT, '.gitignore'), '.DS_Store\nnode_modules/\n.idea/\n.vscode/\n*.log\n', 'utf8');
  fs.writeFileSync(path.join(ROOT, 'README.md'),
    '# AI 信息共享平台\n\n由 `ai-info-share` skill 自动生成的纯静态多 Agent 报告聚合平台。\n\n' +
    '## 本地预览\n\n```bash\nnode ~/.scripts/ai-info-share/ai-info-share.js serve 8000\n```\n\n' +
    '## 添加 Agent\n\n```bash\nnode ~/.scripts/ai-info-share/ai-info-share.js add-agent my-bot 我的机器人\n```\n\n' +
    '## 发布报告\n\n```bash\nnode ~/.scripts/ai-info-share/ai-info-share.js publish-report my-bot "报告标题" --tags "标签1,标签2" --importance high --content ./content.md\n```\n\n部署: 推送到 GitHub 后在 Settings → Pages 启用 main / root。\n', 'utf8');

  console.log('✅ 初始化完成');
  console.log('  预览: node ~/.scripts/ai-info-share/ai-info-share.js serve 8000');
}

function cmdAddAgent(name, label) {
  if (!name || !label) { printHelp(); process.exit(1); }

  const agentsFile = path.join(ROOT, 'system/agents.json');
  if (!fs.existsSync(agentsFile)) {
    console.log('⚠️  未找到 system/agents.json，先在项目目录执行 init');
    process.exit(1);
  }

  const data = readJSON(agentsFile);
  if (data.agents.some(a => a.name === name)) {
    console.log('⚠️  Agent "' + name + '" 已存在');
    return;
  }
  data.agents.push({ name, label });
  writeJSON(agentsFile, data);

  ensureDir(path.join(ROOT, 'agents', name, 'reports'));
  ensureDir(path.join(ROOT, 'agents', name, 'panel'));
  writeJSON(path.join(ROOT, 'agents', name, 'reports', 'index.json'), { files: [] });

  // 自动添加到 panel
  const panelFile = path.join(ROOT, 'system/panel.json');
  if (fs.existsSync(panelFile)) {
    const panel = readJSON(panelFile);
    const maxOrder = panel.widgets.reduce((m, w) => Math.max(m, w.order || 0), 0);
    writeJSON(path.join(ROOT, 'agents', name, 'panel', 'kpi.json'), {
      updatedAt: nowISO(),
      kpi: [{ label: label + ' 数据', value: '—', trend: 'neutral' }],
    });
    panel.widgets.push({
      order: maxOrder + 1, type: 'json', title: label,
      source: 'agents/' + name + '/panel/kpi.json', updatedAt: nowISO(),
    });
    writeJSON(panelFile, panel);
    console.log('   已在首页面板添加 widget: agents/' + name + '/panel/kpi.json');
  }

  console.log('✅ Agent "' + name + '" (' + label + ') 已注册');
}

function cmdPublishReport(agent, title, flags) {
  if (!agent || !title) { printHelp(); process.exit(1); }
  const reportsDir = path.join(ROOT, 'agents', agent, 'reports');
  const indexFile = path.join(reportsDir, 'index.json');
  if (!fs.existsSync(indexFile)) {
    console.log('⚠️  未找到该 Agent 的 reports/index.json，先执行 add-agent');
    process.exit(1);
  }
  const agentsData = readJSON(path.join(ROOT, 'system/agents.json'));
  const agentInfo = agentsData.agents.find(a => a.name === agent);
  const agentLabel = agentInfo ? agentInfo.label : agent;

  const updatedAt = flags.date || nowISO();
  const summary = flags.summary || '';
  const tags = flags.tags ? String(flags.tags).split(',').map(t => t.trim()).filter(Boolean) : [];
  const importance = flags.importance || 'normal';

  let content = '（请在此处撰写报告正文，支持 Markdown。）\n';
  if (flags.content && flags.content !== true) {
    const contentFile = path.resolve(flags.content);
    if (fs.existsSync(contentFile)) {
      content = fs.readFileSync(contentFile, 'utf8');
      console.log('   正文来自文件: ' + path.relative(ROOT, contentFile));
    } else {
      console.log('   ⚠️  未找到 --content 文件: ' + contentFile);
    }
  }

  const reportId = datePrefix(updatedAt) + '-' + slugify(title);
  const fileName = reportId + '.json';
  const filePath = path.join(reportsDir, fileName);

  writeJSON(filePath, {
    id: reportId, title, agent, agentLabel, updatedAt, summary, tags, importance, content,
  });

  const idx = readJSON(indexFile);
  if (!idx.files.includes(fileName)) idx.files.unshift(fileName);
  idx.files = idx.files.slice().sort((a, b) => a > b ? -1 : 1);
  writeJSON(indexFile, idx);

  console.log('✅ 报告已发布: agents/' + agent + '/reports/' + fileName);
  console.log('   importance: ' + importance + ' | tags: ' + (tags.join(',') || '-'));
}

function cmdUpdateWidget(sourcePath, flags) {
  if (!sourcePath) { printHelp(); process.exit(1); }
  const fullPath = path.isAbsolute(sourcePath) ? sourcePath : path.join(ROOT, sourcePath);
  const type = flags.type || inferType(fullPath);

  if (type === 'json') {
    if (!fs.existsSync(fullPath)) {
      writeJSON(fullPath, { updatedAt: nowISO(), kpi: [] });
      console.log('✅ 已创建新 widget: ' + sourcePath);
    } else {
      const data = readJSON(fullPath);
      data.updatedAt = nowISO();
      writeJSON(fullPath, data);
      console.log('✅ widget updatedAt 已更新: ' + sourcePath);
    }
  } else {
    if (!fs.existsSync(fullPath)) {
      fs.writeFileSync(fullPath, type === 'html' ? '<p>（请更新此内容）</p>\n' : '（请更新此内容）\n', 'utf8');
      console.log('✅ 已创建空 widget: ' + sourcePath);
    } else {
      console.log('ℹ️ widget 已存在，直接编辑源文件即可: ' + sourcePath);
    }
  }

  if (flags.title && flags.title !== true) {
    const panelFile = path.join(ROOT, 'system/panel.json');
    if (fs.existsSync(panelFile)) {
      const panel = readJSON(panelFile);
      let hit = false;
      for (const w of panel.widgets) {
        if (w.source === sourcePath) { w.title = flags.title; w.updatedAt = nowISO(); hit = true; }
      }
      if (hit) { writeJSON(panelFile, panel); console.log('   panel.json 中的 title 已更新'); }
    }
  }
}

function cmdServe(port) {
  const p = Number(port) || 8000;
  const http = require('http');
  const url = require('url');
  const mime = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.md': 'text/markdown; charset=utf-8',
    '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
    '.ico': 'image/x-icon', '.txt': 'text/plain; charset=utf-8',
  };
  const server = http.createServer((req, res) => {
    try {
      let pathname = decodeURIComponent(url.parse(req.url).pathname);
      if (pathname.endsWith('/')) pathname += 'index.html';
      const filePath = path.normalize(path.join(ROOT, pathname));
      if (!filePath.startsWith(ROOT)) { res.writeHead(403); res.end('Forbidden'); return; }
      if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('404 Not Found: ' + pathname); return;
      }
      const ext = path.extname(filePath).toLowerCase();
      res.writeHead(200, { 'Content-Type': mime[ext] || 'application/octet-stream' });
      fs.createReadStream(filePath).pipe(res);
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('500: ' + err.message);
    }
  });
  server.listen(p, () => {
    console.log('🌐 本地预览: http://127.0.0.1:' + p + '/   (Ctrl+C 停止)');
  });
}

// ==================== 静态内容生成 ====================

function generateIndexHTML() {
  return '<!DOCTYPE html>\n<html lang="zh-CN"><head>\n' +
    '<meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />\n' +
    '<title>AI 信息共享平台</title><meta name="description" content="多 Agent 报告信息聚合展示平台" />\n' +
    '<link rel="stylesheet" href="assets/css/style.css" /></head><body>\n' +
    '<header class="site-header"><div class="container header-inner">' +
    '<h1 class="site-title"><span class="logo-dot"></span>AI 信息共享</h1>' +
    '<nav class="site-nav"><a href="#dashboard">面板</a><a href="#reports">最新报告</a>' +
    '<a href="#archive">归档</a><button id="viewToggle" class="toggle-btn">卡片视图</button></nav>' +
    '</div></header>\n' +
    '<main class="container main">' +
    '<section id="dashboard"><div class="section-header"><h2>首页面板</h2><span class="section-sub" id="panelMeta">加载中…</span></div>' +
    '<div id="panelContainer" class="panel-container"><div class="loading">正在加载面板内容…</div></div></section>' +
    '<section id="reports"><div class="section-header"><h2>最新报告</h2>' +
    '<div class="section-controls"><span class="section-sub" id="reportMeta">加载中…</span>' +
    '<input type="text" id="searchBox" placeholder="搜索标题 / 标签 / agent…" /></div></div>' +
    '<div id="reportContainer" class="report-container"><div class="loading">正在加载报告…</div></div></section>' +
    '<section id="archive" style="display:none;"><div class="section-header"><h2>归档报告（超过 14 天）</h2>' +
    '<span class="section-sub" id="archiveMeta"></span></div><div id="archiveContainer" class="report-container"></div></section>' +
    '</main>\n' +
    '<footer class="site-footer"><div class="container"><p>多 Agent 信息聚合 · 静态站点 · 由各 AI Agent 独立维护</p></div></footer>\n' +
    '<div id="reportModal" class="modal" aria-hidden="true"><div class="modal-backdrop" data-close></div>' +
    '<div class="modal-dialog"><button class="modal-close" data-close aria-label="关闭">×</button>' +
    '<div id="modalContent" class="modal-content"></div></div></div>\n' +
    '<script src="assets/js/app.js"></script>\n</body></html>\n';
}

function generateStyleCSS() {
  return ':root{--bg:#0f1220;--bg-elev:#171a2e;--bg-soft:#1d2140;--border:rgba(255,255,255,0.08);' +
    '--border-strong:rgba(255,255,255,0.16);--text:#e8ecff;--text-dim:#9aa3c7;--text-faint:#6b7496;' +
    '--primary:#6c8cff;--primary-soft:rgba(108,140,255,0.16);--success:#3ddc97;--warning:#ffb74d;' +
    '--danger:#ff6b81;--radius:14px;--radius-sm:8px}\n' +
    '*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 10% -10%,rgba(108,140,255,0.18),transparent 60%),var(--bg);' +
    'color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Segoe UI",Roboto,sans-serif;font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}\n' +
    '.container{max-width:1180px;margin:0 auto;padding:0 20px}' +
    '.site-header{position:sticky;top:0;z-index:50;backdrop-filter:saturate(180%) blur(14px);background:rgba(15,18,32,0.72);border-bottom:1px solid var(--border)}\n' +
    '.header-inner{display:flex;align-items:center;justify-content:space-between;padding:14px 20px}' +
    '.site-title{display:flex;align-items:center;gap:10px;margin:0;font-size:17px;font-weight:600}' +
    '.logo-dot{width:12px;height:12px;border-radius:50%;background:linear-gradient(135deg,var(--primary),var(--success));box-shadow:0 0 18px rgba(108,140,255,0.6)}\n' +
    '.site-nav{display:flex;align-items:center;gap:18px}' +
    '.site-nav a{color:var(--text-dim);text-decoration:none;font-size:14px}.site-nav a:hover{color:var(--text)}\n' +
    '.toggle-btn{background:var(--bg-soft);color:var(--text);border:1px solid var(--border);border-radius:999px;padding:6px 12px;font-size:13px;cursor:pointer}\n' +
    '.main{padding:32px 20px 80px}.section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:10px}' +
    '.section-header h2{margin:0;font-size:20px;font-weight:600}.section-controls{display:flex;align-items:center;gap:14px}' +
    '.section-sub{color:var(--text-faint);font-size:13px}#searchBox{background:var(--bg-soft);border:1px solid var(--border);color:var(--text);' +
    'border-radius:999px;padding:8px 14px;font-size:13px;outline:none;min-width:220px}#searchBox:focus{border-color:var(--primary);box-shadow:0 0 0 3px var(--primary-soft)}\n' +
    '.dashboard-section,.reports-section,.archive-section{margin-bottom:40px}' +
    '.panel-container,.report-container{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}' +
    '.report-container.list-view{grid-template-columns:1fr}' +
    '.widget,.report-card{background:linear-gradient(180deg,var(--bg-elev),var(--bg-soft));border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px}' +
    '.report-card{cursor:pointer;transition:transform .15s ease,border-color .15s ease}.report-card:hover{transform:translateY(-2px);border-color:var(--border-strong)}\n' +
    '.report-card.critical{border-color:rgba(255,107,129,.5)}.report-card.high{border-color:rgba(255,183,77,.4)}\n' +
    '.widget-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}' +
    '.widget-title h3{margin:0;font-size:14px;font-weight:600;color:var(--text-dim);letter-spacing:.3px;text-transform:uppercase}' +
    '.widget-updated{font-size:11px;color:var(--text-faint)}\n' +
    '.report-head{display:flex;justify-content:space-between;gap:12px;margin-bottom:10px}' +
    '.report-title{margin:0;font-size:16px;font-weight:600;line-height:1.4}\n' +
    '.report-meta{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px;font-size:12px;color:var(--text-faint)}\n' +
    '.badge{display:inline-flex;align-items:center;gap:6px;padding:3px 9px;border-radius:999px;font-size:11.5px;background:var(--primary-soft);color:var(--primary);border:1px solid rgba(108,140,255,.3)}\n' +
    '.badge.critical{background:rgba(255,107,129,.15);color:var(--danger);border-color:rgba(255,107,129,.35)}\n' +
    '.badge.high{background:rgba(255,183,77,.15);color:var(--warning);border-color:rgba(255,183,77,.35)}\n' +
    '.badge.normal{background:rgba(61,220,151,.12);color:var(--success);border-color:rgba(61,220,151,.3)}\n' +
    '.badge-agent{background:rgba(255,255,255,.06);color:var(--text-dim);border-color:var(--border)}\n' +
    '.report-summary{color:var(--text-dim);font-size:14px;line-height:1.6;margin:0 0 12px}' +
    '.report-tags{display:flex;flex-wrap:wrap;gap:6px}.tag{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--text-faint);background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:4px;padding:2px 7px}\n' +
    '.report-agent-dot{width:6px;height:6px;border-radius:50%;background:var(--primary);display:inline-block}\n' +
    '.kpi-list{display:grid;gap:10px}.kpi-row{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;border-bottom:1px dashed var(--border)}\n' +
    '.kpi-row:last-child{border-bottom:none}.kpi-label{color:var(--text-dim);font-size:13px}.kpi-value{font-weight:600;font-size:15px}.kpi-value.up{color:var(--success)}.kpi-value.down{color:var(--danger)}\n' +
    '.kv-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 14px}\n' +
    '.loading,.empty{padding:40px 20px;text-align:center;color:var(--text-faint);grid-column:1/-1;border:1px dashed var(--border);border-radius:var(--radius);background:var(--bg-elev)}\n' +
    '.modal{position:fixed;inset:0;display:none;z-index:100}.modal.open{display:block}.modal-backdrop{position:absolute;inset:0;background:rgba(8,10,20,.7);backdrop-filter:blur(4px)}\n' +
    '.modal-dialog{position:relative;max-width:780px;margin:5vh auto;background:var(--bg-elev);border:1px solid var(--border-strong);border-radius:var(--radius);max-height:90vh;overflow:auto}\n' +
    '.modal-close{position:absolute;top:12px;right:14px;width:34px;height:34px;border-radius:50%;background:var(--bg-soft);border:1px solid var(--border);color:var(--text);font-size:20px;cursor:pointer}\n' +
    '.modal-content{padding:28px 32px 32px}.modal-content h2{margin:0 0 8px;font-size:22px}' +
    '.modal-content .content{font-size:15px;line-height:1.75}' +
    '.modal-content .content h1,.modal-content .content h2,.modal-content .content h3{margin:1.4em 0 .6em;line-height:1.3}' +
    '.modal-content .content pre{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px 14px;overflow-x:auto;font-size:13px}' +
    '.modal-content .content code{font-family:ui-monospace,Menlo,monospace;background:rgba(255,255,255,.06);padding:1px 6px;border-radius:4px;font-size:13px}' +
    '.modal-content .content blockquote{border-left:3px solid var(--primary);padding:4px 0 4px 14px;margin:1em 0;color:var(--text-dim);background:var(--primary-soft);border-radius:0 var(--radius-sm) var(--radius-sm) 0}' +
    '.modal-content .content table{width:100%;border-collapse:collapse;margin:1em 0;font-size:13.5px}' +
    '.modal-content .content th,.modal-content .content td{padding:8px 10px;border:1px solid var(--border);text-align:left}' +
    '.modal-content .content th{background:var(--bg);color:var(--text-dim)}\n' +
    '.site-footer{border-top:1px solid var(--border);padding:24px 0;color:var(--text-faint);font-size:13px;text-align:center}\n' +
    '@media (max-width:640px){.header-inner{flex-direction:column;align-items:flex-start;gap:10px}#searchBox{min-width:0;width:100%}}\n';
}

function generateAppJS() {
  return '(function(){\'use strict\';const CONFIG={staleDays:14,agentsIndex:\'system/agents.json\',panelConfig:\'system/panel.json\'};const SK=\'ai_info_share_view\';' +
    'const $=(s,r)=>(r||document).querySelector(s);function eH(s){return String(s==null?\'\':s).replace(/&/g,\'&amp;\').replace(/</g,\'&lt;\').replace(/>/g,\'&gt;\').replace(/"/g,\'&quot;\').replace(/\\\'/g,\'&#39;\')}' +
    'function fD(i){const d=new Date(i);if(isNaN(d))return i;const p=n=>String(n).padStart(2,\'0\');return d.getFullYear()+\'-\'+p(d.getMonth()+1)+\'-\'+p(d.getDate())+\' \'+p(d.getHours())+\':\'+p(d.getMinutes())}' +
    'function dA(i){const d=new Date(i);if(isNaN(d))return Infinity;return(Date.now()-d.getTime())/86400000}' +
    'function gJ(u){return fetch(u,{cache:\'no-cache\'}).then(r=>r.ok?r.json():Promise.reject(\'HTTP \'+r.status+\': \'+u))}' +
    'function gT(u){return fetch(u,{cache:\'no-cache\'}).then(r=>r.ok?r.text():Promise.reject(\'HTTP \'+r.status+\': \'+u))}' +
    'function rM(md){if(!md)return \'\';let h=String(md).replace(/\\r\\n/g,\'\\n\');h=h.replace(/```(\\w+)?\\n([\\s\\S]*?)```/g,(_,l,c)=>\'\\n<pre><code>\'+eH(c)+\'</code></pre>\\n\');' +
    'h=h.replace(/`([^`]+)`/g,(_,c)=>\'<code>\'+eH(c)+\'</code>\');const bs=h.split(/\\n{2,}/);const out=[];for(const b of bs){const bl=b.trim();if(!bl)continue;' +
    'if(/^\\|.*\\|\\s*\\|[-:\\s|]+\\|/.test(bl)){out.push(rT(bl));continue;}if(/^>\\s?/m.test(bl)){out.push(\'<blockquote>\'+rI(bl.split(\'\\n\').map(l=>l.replace(/^>\\s?/,\'\')).join(\'\\n\'))+\'</blockquote>\');continue;}' +
    'if(/^\\s*[-*+]\\s+/.test(bl)||/^\\s*\\d+\\.\\s+/.test(bl)){out.push(rL(bl));continue;}const hd=bl.match(/^(#{1,6})\\s+(.+)$/);if(hd){out.push(\'<h\'+hd[1].length+\'>\'+rI(hd[2])+\'</h\'+hd[1].length+\'>\');continue;}' +
    'if(/^(-{3,}|\\*{3,}|_{3,})$/.test(bl)){out.push(\'<hr/>\');continue;}for(const ln of bl.split(\'\\n\'))out.push(\'<p>\'+rI(ln)+\'</p>\')}return out.join(\'\\n\')}' +
    'function rI(t){let x=eH(t);x=x.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g,(_,l,u)=>\'<a href="\'+eH(u)+\'" target="_blank" rel="noopener">\'+l+\'</a>\');' +
    'x=x.replace(/\\*\\*([^*]+)\\*\\*/g,\'<strong>$1</strong>\');x=x.replace(/(^|[^*])\\*([^*]+)\\*/g,\'$1<em>$2</em>\');return x}' +
    'function rL(bl){const ls=bl.split(\'\\n\').filter(Boolean);const tag=/^\\s*\\d+\\.\\s+/.test(ls[0])?\'ol\':\'ul\';return \'<\'+tag+\'>\'+ls.map(l=>\'<li>\'+rI(l.replace(/^\\s*([-*+]|\\d+\\.)\\s+/,\'\'))+\'</li>\').join(\'\')+\'</\'+tag+\'>\'}' +
    'function rT(bl){const ls=bl.split(\'\\n\').filter(Boolean);const sp=r=>r.replace(/^\\||\\|$/g,\'\').split(\'|\').map(c=>c.trim());const hd=sp(ls[0]);' +
    'let h=\'<table><thead><tr>\'+hd.map(x=>\'<th>\'+rI(x)+\'</th>\').join(\'\')+\'</tr></thead><tbody>\';' +
    'for(let i=2;i<ls.length;i++)h+=\'<tr>\'+sp(ls[i]).map(x=>\'<td>\'+rI(x)+\'</td>\').join(\'\')+\'</tr>\';return h+\'</tbody></table>\'}' +
    'const st={reports:[],searchKey:\'\',isListView:false};' +
    'function init(){st.isListView=localStorage.getItem(SK)===\'list\';const tg=$(\'#viewToggle\');if(tg){tg.textContent=st.isListView?\'卡片视图\':\'列表视图\';' +
    'tg.addEventListener(\'click\',()=>{st.isListView=!st.isListView;localStorage.setItem(SK,st.isListView?\'list\':\'card\');tg.textContent=st.isListView?\'卡片视图\':\'列表视图\';renderReports();});}' +
    'const sb=$(\'#searchBox\');if(sb)sb.addEventListener(\'input\',e=>{st.searchKey=(e.target.value||\'\').trim().toLowerCase();renderReports();});' +
    'initModal();loadPanel().catch(err=>{console.error(err);const m=$(\'#panelMeta\');if(m)m.textContent=\'面板加载失败\';const c=$(\'#panelContainer\');if(c)c.innerHTML=\'<div class="empty">无法加载面板配置</div>\'});' +
    'loadReports().then(rs=>{st.reports=rs.sort((a,b)=>new Date(b.updatedAt)-new Date(a.updatedAt));renderReports();}).catch(err=>{console.error(err);const m=$(\'#reportMeta\');if(m)m.textContent=\'报告加载失败\'});}' +
    'async function loadPanel(){const cfg=await gJ(CONFIG.panelConfig);const ws=(cfg.widgets||[]).slice().sort((a,b)=>(a.order||99)-(b.order||99));const m=$(\'#panelMeta\');if(m)m.textContent=\'共 \'+ws.length+\' 个 widget\';' +
    'const c=$(\'#panelContainer\');if(!c)return;c.innerHTML=\'\';for(const w of ws){const el=document.createElement(\'article\');el.className=\'widget\';' +
    'el.innerHTML=\'<header class="widget-title"><h3>\'+eH(w.title||\'\')+\'</h3><span class="widget-updated">加载中…</span></header><div class="widget-body"><div class="loading" style="padding:10px 0;border:none;background:transparent;">…</div></div>\';' +
    'c.appendChild(el);renderWidget(el,w).catch(err=>{console.warn(err);el.querySelector(\'.widget-body\').innerHTML=\'<div class="empty" style="padding:10px 0;">加载失败</div>\'})}}' +
    'async function renderWidget(el,w){const body=el.querySelector(\'.widget-body\');const up=el.querySelector(\'.widget-updated\');' +
    'if(w.type===\'json\'){const data=await gJ(w.source);body.innerHTML=rJW(data);up.textContent=data.updatedAt?fD(data.updatedAt):(w.updatedAt?fD(w.updatedAt):\'\');}' +
    'else if(w.type===\'html\'){body.innerHTML=await gT(w.source);up.textContent=w.updatedAt?fD(w.updatedAt):\'\';}' +
    'else if(w.type===\'markdown\'||w.type===\'md\'){body.innerHTML=rM(w.source?await gT(w.source):(w.content||\'\'));up.textContent=w.updatedAt?fD(w.updatedAt):\'\';}' +
    'else if(w.type===\'text\'){body.innerHTML=\'<p>\'+rI(w.content||\'\')+\'</p>\';up.textContent=w.updatedAt?fD(w.updatedAt):\'\';}}' +
    'function rJW(d){if(d.html)return d.html;if(d.kpi&&Array.isArray(d.kpi))return \'<div class="kpi-list">\'+d.kpi.map(k=>{const c=k.trend===\'up\'?\' up\':(k.trend===\'down\'?\' down\':\'\');' +
    'return \'<div class="kpi-row"><span class="kpi-label">\'+eH(k.label||\'\')+\'</span><span class="kpi-value\'+c+\'">\'+eH(k.value==null?\'\':k.value)+\'</span></div>\';}).join(\'\')+\'</div>\';' +
    'if(d.table){const t=d.table;return \'<table><thead><tr>\'+(t.head||[]).map(h=>\'<th>\'+eH(h)+\'</th>\').join(\'\')+\'</tr></thead><tbody>\'+(t.rows||[]).map(r=>\'<tr>\'+r.map(c=>\'<td>\'+eH(c==null?\'\':c)+\'</td>\').join(\'\')+\'</tr>\').join(\'\')+\'</tbody></table>\';}' +
    'if(d.list&&Array.isArray(d.list))return \'<ul>\'+d.list.map(l=>\'<li>\'+rI(l)+\'</li>\').join(\'\')+\'</ul>\';' +
    'const ks=Object.keys(d).filter(k=>k!==\'updatedAt\');if(!ks.length)return \'<p>（空数据）</p>\';' +
    'return \'<div class="kv-grid">\'+ks.map(k=>\'<div class="kpi-label">\'+eH(k)+\'</div><div class="kpi-value">\'+eH(d[k]==null?\'\':d[k])+\'</div>\').join(\'\')+\'</div>\';}' +
    'async function loadReports(){const a=await gJ(CONFIG.agentsIndex);if(!a||!Array.isArray(a.agents))throw new Error(\'agents.json bad\');const all=[];' +
    'for(const ag of a.agents){const nm=typeof ag===\'string\'?ag:ag.name;const lb=typeof ag===\'string\'?ag:(ag.label||ag.name);' +
    'try{const idx=await gJ(\'agents/\'+nm+\'/reports/index.json\');for(const f of(idx.files||[])){try{const rep=await gJ(\'agents/\'+nm+\'/reports/\'+f);rep._agent=nm;rep._agentLabel=rep.agentLabel||lb;all.push(rep);}catch(e){console.warn(\'report fail\',f,e);}}catch(e){console.warn(\'agent idx fail\',nm,e);}}return all;}' +
    'function renderReports(){const active=st.reports.filter(r=>dA(r.updatedAt)<=CONFIG.staleDays);const archived=st.reports.filter(r=>dA(r.updatedAt)>CONFIG.staleDays);' +
    'const key=st.searchKey;const filter=r=>!key||[r.title,r.summary,r._agent,r._agentLabel,(r.tags||[]).join(\' \')].join(\' \').toLowerCase().indexOf(key)!==-1;' +
    'const list=active.filter(filter);const rm=$(\'#reportMeta\');if(rm)rm.textContent=\'显示 \'+list.length+\' / \'+active.length+\' 条（\'+archived.length+\' 条归档）\';' +
    'const c=$(\'#reportContainer\');if(c){c.className=\'report-container\'+(st.isListView?\' list-view\':\'\');c.innerHTML=list.length?list.map(renderCard).join(\'\'):\'<div class="empty">没有匹配的报告</div>\';bindClick(c,list);}' +
    'const as=$(\'#archive\');if(as){if(archived.length>0){as.style.display=\'\';const am=$(\'#archiveMeta\');if(am)am.textContent=\'共 \'+archived.length+\' 条归档报告\';' +
    'const ac=$(\'#archiveContainer\');if(ac){ac.className=\'report-container\'+(st.isListView?\' list-view\':\'\');ac.innerHTML=archived.filter(filter).map(renderCard).join(\'\');bindClick(ac,archived);}}else{as.style.display=\'none\'}}}' +
    'function renderCard(r){const imp=r.importance||\'normal\';const tags=(r.tags||[]).slice(0,6).map(t=>\'<span class="tag">\'+eH(t)+\'</span>\').join(\'\');' +
    'return \'<article class="report-card \'+eH(imp)+\'"><header class="report-head"><h3 class="report-title">\'+eH(r.title||\'\')+\'</h3></header>\'+\'<div class="report-meta"><span class="badge badge-agent"><span class="report-agent-dot"></span>\'+eH(r._agentLabel||r._agent||\'\')+\'</span><span class="badge \'+eH(imp)+\'">\'+eH(impLabel(imp))+\'</span><span>\'+fD(r.updatedAt)+\'</span></div>\'+\'<p class="report-summary">\'+eH(r.summary||\'\')+\'</p>\'+(tags?\'<div class="report-tags">\'+tags+\'</div>\':\'\')+\'</article>\';}' +
    'function impLabel(l){return{critical:\'关键\',high:\'重要\',normal:\'常规\'}[l]||l}' +
    'function bindClick(container,list){Array.from(container.children).forEach((el,i)=>el.addEventListener(\'click\',()=>openReport(list[i])))}' +
    'function initModal(){const m=$(\'#reportModal\');document.addEventListener(\'click\',e=>{const t=e.target.closest(\'[data-close]\');if(t&&m&&m.contains(t)){m.classList.remove(\'open\');document.body.style.overflow=\'\'}});' +
    'document.addEventListener(\'keydown\',e=>{if(e.key===\'Escape\'&&m&&m.classList.contains(\'open\')){m.classList.remove(\'open\');document.body.style.overflow=\'\'}});}' +
    'function openReport(r){const m=$(\'#reportModal\');const c=$(\'#modalContent\');if(!m||!c)return;const imp=r.importance||\'normal\';' +
    'const tags=(r.tags||[]).map(t=>\'<span class="tag">\'+eH(t)+\'</span>\').join(\' \');const body=r.html?r.html:rM(r.content||\'\');' +
    'c.innerHTML=\'<h2>\'+eH(r.title||\'\')+\'</h2><div class="report-meta"><span class="badge badge-agent"><span class="report-agent-dot"></span>\'+eH(r._agentLabel||r._agent||\'\')+\'</span><span class="badge \'+eH(imp)+\'">\'+eH(impLabel(imp))+\'</span><span>\'+fD(r.updatedAt)+\'</span></div>\'+(tags?\'<div class="report-tags" style="margin-bottom:18px;">\'+tags+\'</div>\':\'\')+(r.summary?\'<blockquote style="margin:0 0 20px 0;"><strong>摘要：</strong>\'+eH(r.summary)+\'</blockquote>\':\'\')+\'<div class="content">\'+body+\'</div>\';' +
    'm.classList.add(\'open\');document.body.style.overflow=\'hidden\';}' +
    'if(document.readyState===\'loading\')document.addEventListener(\'DOMContentLoaded\',init);else init();})();';
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.flags.help || args._.length === 0) { printHelp(); return; }
  const [sub, ...rest] = args._;
  switch (sub) {
    case 'init': return cmdInit();
    case 'add-agent': return cmdAddAgent(rest[0], rest[1]);
    case 'publish-report': return cmdPublishReport(rest[0], rest.slice(1).join(' '), args.flags);
    case 'update-widget': return cmdUpdateWidget(rest[0], args.flags);
    case 'serve': return cmdServe(rest[0]);
    default: console.log('未知子命令: ' + sub); printHelp(); process.exit(1);
  }
}

main();
