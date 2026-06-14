(function () {
  'use strict';

  const CONFIG = {
    staleDays: 14,
    agentsIndex: 'system/agents.json',
    panelConfig: 'system/panel.json',
  };

  const STORAGE_KEY = 'ai_info_share_view';

  /* ---------- 工具函数 ---------- */
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${day} ${hh}:${mm}`;
  }

  function daysAgo(iso) {
    if (!iso) return Infinity;
    const d = new Date(iso);
    if (isNaN(d)) return Infinity;
    return (Date.now() - d.getTime()) / (1000 * 60 * 60 * 24);
  }

  function fetchJSON(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ': ' + url);
      return r.json();
    });
  }

  function fetchText(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ': ' + url);
      return r.text();
    });
  }

  /* ---------- 极简 Markdown 渲染 ---------- */
  function renderMarkdown(md) {
    if (!md) return '';
    let html = String(md);
    html = html.replace(/\r\n/g, '\n');

    // 代码块 ```lang\n...```
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, function (_, lang, code) {
      return '\n<pre><code>' + escapeHtml(code) + '</code></pre>\n';
    });

    // 行内代码
    html = html.replace(/`([^`]+)`/g, function (_, code) {
      return '<code>' + escapeHtml(code) + '</code>';
    });

    // 段落和块级结构 — 按空行分段
    const blocks = html.split(/\n{2,}/);
    const out = [];
    for (let i = 0; i < blocks.length; i++) {
      let block = blocks[i].trim();
      if (!block) continue;

      // 表格
      if (/^\|.*\|\s*\|[-:\s|]+\|/.test(block)) {
        out.push(renderTable(block));
        continue;
      }

      // 引用块
      if (/^>\s?/m.test(block)) {
        const lines = block.split('\n').map(function (l) {
          return l.replace(/^>\s?/, '');
        });
        out.push('<blockquote>' + renderInline(lines.join('\n')) + '</blockquote>');
        continue;
      }

      // 列表（有序/无序，简单处理整个块）
      if (/^(\s*)[-*+]\s+/m.test(block) || /^(\s*)\d+\.\s+/m.test(block)) {
        out.push(renderList(block));
        continue;
      }

      // 标题
      const headingMatch = block.match(/^(#{1,6})\s+(.+)$/);
      if (headingMatch && !/^\s*\|/.test(block)) {
        const level = headingMatch[1].length;
        out.push('<h' + level + '>' + renderInline(headingMatch[2]) + '</h' + level + '>');
        continue;
      }

      // 水平线
      if (/^(-{3,}|\*{3,}|_{3,})$/.test(block)) {
        out.push('<hr />');
        continue;
      }

      // 默认段落 — 只处理不在其他块中的单行
      const paragraphs = block.split('\n').filter(Boolean);
      for (let j = 0; j < paragraphs.length; j++) {
        out.push('<p>' + renderInline(paragraphs[j]) + '</p>');
      }
    }
    return out.join('\n');
  }

  function renderInline(text) {
    let t = escapeHtml(text);
    // 链接 [text](url)
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, url) {
      return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">' + label + '</a>';
    });
    // 粗体 **text**
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // 斜体 *text*
    t = t.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
    return t;
  }

  function renderList(block) {
    const lines = block.split('\n');
    const ordered = /^\s*\d+\.\s+/.test(lines[0]);
    const tag = ordered ? 'ol' : 'ul';
    let html = '<' + tag + '>';
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].replace(/^\s*([-*+]|\d+\.)\s+/, '');
      if (!line.trim()) continue;
      html += '<li>' + renderInline(line) + '</li>';
    }
    html += '</' + tag + '>';
    return html;
  }

  function renderTable(block) {
    const lines = block.split('\n').filter(Boolean);
    if (lines.length < 2) return '<p>' + renderInline(block) + '</p>';
    const splitRow = function (row) {
      return row.replace(/^\||\|$/g, '').split('|').map(function (c) {
        return c.trim();
      });
    };
    const header = splitRow(lines[0]);
    let html = '<table><thead><tr>';
    for (let i = 0; i < header.length; i++) {
      html += '<th>' + renderInline(header[i]) + '</th>';
    }
    html += '</tr></thead><tbody>';
    for (let i = 2; i < lines.length; i++) {
      const cells = splitRow(lines[i]);
      html += '<tr>';
      for (let j = 0; j < cells.length; j++) {
        html += '<td>' + renderInline(cells[j]) + '</td>';
      }
      html += '</tr>';
    }
    html += '</tbody></table>';
    return html;
  }

  /* ---------- 主程序 ---------- */
  const state = {
    reports: [],
    searchKey: '',
    isListView: false,
  };

  function init() {
    state.isListView = localStorage.getItem(STORAGE_KEY) === 'list';
    const toggleBtn = $('#viewToggle');
    if (toggleBtn) {
      toggleBtn.textContent = state.isListView ? '卡片视图' : '列表视图';
      toggleBtn.addEventListener('click', function () {
        state.isListView = !state.isListView;
        localStorage.setItem(STORAGE_KEY, state.isListView ? 'list' : 'card');
        toggleBtn.textContent = state.isListView ? '卡片视图' : '列表视图';
        renderReports();
      });
    }

    const searchBox = $('#searchBox');
    if (searchBox) {
      searchBox.addEventListener('input', function (e) {
        state.searchKey = (e.target.value || '').trim().toLowerCase();
        renderReports();
      });
    }

    initModal();

    // 面板
    loadPanel().catch(function (err) {
      console.error(err);
      $('#panelMeta').textContent = '面板加载失败';
      $('#panelContainer').innerHTML = '<div class="empty">无法加载面板配置：' + escapeHtml(err.message) + '</div>';
    });

    // 报告
    loadReports().then(function (reports) {
      state.reports = reports.sort(function (a, b) {
        return new Date(b.updatedAt) - new Date(a.updatedAt);
      });
      renderReports();
    }).catch(function (err) {
      console.error(err);
      $('#reportMeta').textContent = '报告加载失败';
      $('#reportContainer').innerHTML = '<div class="empty">无法加载报告：' + escapeHtml(err.message) + '</div>';
    });
  }

  /* ---------- 面板 ---------- */
  async function loadPanel() {
    const cfg = await fetchJSON(CONFIG.panelConfig);
    const widgets = (cfg.widgets || []).slice().sort(function (a, b) {
      return (a.order || 99) - (b.order || 99);
    });
    $('#panelMeta').textContent = '共 ' + widgets.length + ' 个 widget · 最后检查：' + fmtDate(new Date().toISOString()).slice(0, 10);

    // 先渲染占位，再逐个填充
    const container = $('#panelContainer');
    container.innerHTML = '';
    const slots = [];
    for (let i = 0; i < widgets.length; i++) {
      const w = widgets[i];
      const el = document.createElement('article');
      el.className = 'widget';
      el.innerHTML =
        '<header class="widget-title"><h3>' + escapeHtml(w.title || '（未命名）') + '</h3>' +
        '<span class="widget-updated">加载中…</span></header>' +
        '<div class="widget-body"><div class="loading" style="padding:10px 0;border:none;background:transparent;">…</div></div>';
      container.appendChild(el);
      slots.push({ el: el, w: w });
    }

    await Promise.all(slots.map(function (slot) {
      return renderWidget(slot.el, slot.w).catch(function (err) {
        console.warn('widget 渲染失败', slot.w, err);
        slot.el.querySelector('.widget-body').innerHTML = '<div class="empty" style="padding:10px 0;">加载失败：' + escapeHtml(err.message) + '</div>';
        slot.el.querySelector('.widget-updated').textContent = '—';
      });
    }));
  }

  async function renderWidget(el, w) {
    const body = el.querySelector('.widget-body');
    const updated = el.querySelector('.widget-updated');
    if (w.type === 'html') {
      const html = await fetchText(w.source);
      body.innerHTML = html;
      updated.textContent = w.updatedAt ? fmtDate(w.updatedAt) : (w.updated ? fmtDate(w.updated) : '');
    } else if (w.type === 'json') {
      const data = await fetchJSON(w.source);
      body.innerHTML = renderJSONWidget(data);
      updated.textContent = data.updatedAt ? fmtDate(data.updatedAt) : (w.updatedAt ? fmtDate(w.updatedAt) : '');
    } else if (w.type === 'text') {
      body.innerHTML = '<p>' + renderInline(w.content || '') + '</p>';
      updated.textContent = w.updatedAt ? fmtDate(w.updatedAt) : '';
    } else if (w.type === 'markdown' || w.type === 'md') {
      const md = w.source ? await fetchText(w.source) : (w.content || '');
      body.innerHTML = renderMarkdown(md);
      updated.textContent = w.updatedAt ? fmtDate(w.updatedAt) : '';
    } else {
      body.innerHTML = '<p>未知 widget 类型: ' + escapeHtml(w.type || '（未声明）') + '</p>';
    }
  }

  function renderJSONWidget(data) {
    // JSON widget 可以是多种结构：{kpi:[..]}、{table:{head:[],rows:[]}}、{html:'...'}、{text:'...'}、{list:[..]}
    if (data.html) return data.html;
    if (data.kpi && Array.isArray(data.kpi)) {
      return '<div class="kpi-list">' + data.kpi.map(function (k) {
        const upDown = k.trend === 'up' ? ' up' : (k.trend === 'down' ? ' down' : '');
        return '<div class="kpi-row"><span class="kpi-label">' + escapeHtml(k.label || '') + '</span>' +
               '<span class="kpi-value' + upDown + '">' + escapeHtml(k.value == null ? '' : k.value) + '</span></div>';
      }).join('') + '</div>';
    }
    if (data.table) {
      const t = data.table;
      const head = (t.head || []).map(function (h) { return '<th>' + escapeHtml(h) + '</th>'; }).join('');
      const rows = (t.rows || []).map(function (row) {
        return '<tr>' + row.map(function (c) { return '<td>' + escapeHtml(c == null ? '' : c) + '</td>'; }).join('') + '</tr>';
      }).join('');
      return '<table><thead><tr>' + head + '</tr></thead><tbody>' + rows + '</tbody></table>';
    }
    if (data.list && Array.isArray(data.list)) {
      return '<ul>' + data.list.map(function (it) { return '<li>' + renderInline(it) + '</li>'; }).join('') + '</ul>';
    }
    if (data.text) return '<p>' + renderInline(data.text) + '</p>';
    // 退化为 key-value 网格
    const keys = Object.keys(data).filter(function (k) { return k !== 'updatedAt'; });
    if (keys.length === 0) return '<p>（空数据）</p>';
    return '<div class="kv-grid">' + keys.map(function (k) {
      return '<div class="kpi-label">' + escapeHtml(k) + '</div><div class="kpi-value">' + escapeHtml(data[k] == null ? '' : data[k]) + '</div>';
    }).join('') + '</div>';
  }

  /* ---------- 报告 ---------- */
  async function loadReports() {
    const agents = await fetchJSON(CONFIG.agentsIndex);
    if (!agents || !Array.isArray(agents.agents)) {
      throw new Error('agents.json 格式不正确');
    }
    const all = [];
    // 并发加载每个 agent 的报告索引
    await Promise.all(agents.agents.map(function (agent) {
      const name = typeof agent === 'string' ? agent : agent.name;
      const label = typeof agent === 'string' ? agent : (agent.label || agent.name);
      const idxPath = 'agents/' + name + '/reports/index.json';
      return fetchJSON(idxPath).then(function (idx) {
        const files = idx.files || [];
        return Promise.all(files.map(function (f) {
          const path = 'agents/' + name + '/reports/' + f;
          return fetchJSON(path).then(function (rep) {
            rep._agent = name;
            rep._agentLabel = rep.agentLabel || label || name;
            rep._path = path;
            all.push(rep);
          }).catch(function (err) {
            console.warn('报告加载失败', path, err);
          });
        }));
      }).catch(function (err) {
        console.warn('agent 索引加载失败', idxPath, err);
      });
    }));
    return all;
  }

  function renderReports() {
    const container = $('#reportContainer');
    const archiveContainer = $('#archiveContainer');
    const archiveSection = $('#archive');

    if (!state.reports || state.reports.length === 0) {
      $('#reportMeta').textContent = '暂无报告';
      container.innerHTML = '<div class="empty">还没有任何报告。请各 Agent 上传报告后刷新。</div>';
      return;
    }

    const key = state.searchKey;
    const active = state.reports.filter(function (r) {
      return daysAgo(r.updatedAt) <= CONFIG.staleDays;
    });
    const archived = state.reports.filter(function (r) {
      return daysAgo(r.updatedAt) > CONFIG.staleDays;
    });

    const filter = function (r) {
      if (!key) return true;
      const hay = [r.title, r.summary, r.agent || r._agent, r._agentLabel, (r.tags || []).join(' ')].join(' ').toLowerCase();
      return hay.indexOf(key) !== -1;
    };

    const activeList = active.filter(filter);
    $('#reportMeta').textContent = '显示 ' + activeList.length + ' / ' + active.length + ' 条（' + archived.length + ' 条归档）';
    container.className = 'report-container' + (state.isListView ? ' list-view' : '');
    if (activeList.length === 0) {
      container.innerHTML = '<div class="empty">没有匹配的报告</div>';
    } else {
      container.innerHTML = activeList.map(renderReportCard).join('');
      bindCardClicks(container, activeList);
    }

    // 归档
    if (archived.length > 0) {
      archiveSection.style.display = '';
      $('#archiveMeta').textContent = '共 ' + archived.length + ' 条归档报告（超过 ' + CONFIG.staleDays + ' 天）';
      archiveContainer.className = 'report-container' + (state.isListView ? ' list-view' : '');
      archiveContainer.innerHTML = archived.filter(filter).map(renderReportCard).join('');
      bindCardClicks(archiveContainer, archived);
    } else {
      archiveSection.style.display = 'none';
    }
  }

  function renderReportCard(r) {
    const importance = r.importance || 'normal';
    const tags = (r.tags || []).slice(0, 6).map(function (t) {
      return '<span class="tag">' + escapeHtml(t) + '</span>';
    }).join('');
    return (
      '<article class="report-card ' + escapeHtml(importance) + '" data-idx="' + (r._idx || 0) + '">' +
        '<header class="report-head">' +
          '<h3 class="report-title">' + escapeHtml(r.title || '（未命名）') + '</h3>' +
        '</header>' +
        '<div class="report-meta">' +
          '<span class="badge badge-agent"><span class="report-agent-dot"></span>' + escapeHtml(r._agentLabel || r._agent || '') + '</span>' +
          '<span class="badge ' + escapeHtml(importance) + '">' + escapeHtml(importanceLabel(importance)) + '</span>' +
          '<span>' + fmtDate(r.updatedAt) + '</span>' +
        '</div>' +
        '<p class="report-summary">' + escapeHtml(r.summary || '') + '</p>' +
        (tags ? '<div class="report-tags">' + tags + '</div>' : '') +
      '</article>'
    );
  }

  function importanceLabel(level) {
    return { critical: '关键', high: '重要', normal: '常规' }[level] || level;
  }

  function bindCardClicks(container, list) {
    // 给列表补充索引
    $$('.report-card', container).forEach(function (el, i) {
      el.dataset.hash = list[i]._path || (list[i].agent + '/' + list[i].id);
      el.addEventListener('click', function () {
        const idx = Array.prototype.indexOf.call(container.children, el);
        const rep = list[idx];
        openReport(rep);
      });
    });
  }

  /* ---------- 弹窗 ---------- */
  function initModal() {
    const modal = $('#reportModal');
    $$('[data-close]', modal).forEach(function (el) {
      el.addEventListener('click', function () {
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
      });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('open')) {
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
      }
    });
  }

  function openReport(r) {
    const modal = $('#reportModal');
    const content = $('#modalContent');
    const importance = r.importance || 'normal';
    const tags = (r.tags || []).map(function (t) {
      return '<span class="tag">' + escapeHtml(t) + '</span>';
    }).join(' ');

    const body = r.html ? r.html : renderMarkdown(r.content || '');

    content.innerHTML =
      '<h2>' + escapeHtml(r.title || '（未命名）') + '</h2>' +
      '<div class="report-meta">' +
        '<span class="badge badge-agent"><span class="report-agent-dot"></span>' + escapeHtml(r._agentLabel || r._agent || '') + '</span>' +
        '<span class="badge ' + escapeHtml(importance) + '">' + escapeHtml(importanceLabel(importance)) + '</span>' +
        '<span>' + fmtDate(r.updatedAt) + '</span>' +
      '</div>' +
      (tags ? '<div class="report-tags" style="margin-bottom:18px;">' + tags + '</div>' : '') +
      (r.summary ? '<blockquote style="margin:0 0 20px 0;"><strong>摘要：</strong>' + escapeHtml(r.summary) + '</blockquote>' : '') +
      '<div class="content">' + body + '</div>';

    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  /* ---------- 启动 ---------- */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
