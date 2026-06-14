#!/usr/bin/env node
/**
 * Serenity 每日投研分析脚本
 * 用法: node run.js --date=YYYY-MM-DD [--workspace=/path/to/workspace]
 *       node run.js --list
 *       node run.js --review=YYYY-MM-DD
 */

const fs = require('fs');
const path = require('path');

const WORKSPACE = process.env.SERENITY_WORKSPACE || '/sessions/6a2d3e4112bda658430b314b/workspace';
const DAILY_DIR = path.join(WORKSPACE, 'daily-research');

function getToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function listReports() {
  if (!fs.existsSync(DAILY_DIR)) {
    console.log('暂无历史报告');
    return;
  }
  const dirs = fs.readdirSync(DAILY_DIR).filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d)).sort().reverse();
  console.log('历史报告列表:');
  dirs.forEach(d => {
    const reportPath = path.join(DAILY_DIR, d, 'report.html');
    const exists = fs.existsSync(reportPath);
    console.log(`  ${d} ${exists ? '✓' : '✗'}`);
  });
}

function reviewReport(date) {
  const reportPath = path.join(DAILY_DIR, date, 'report.html');
  if (!fs.existsSync(reportPath)) {
    console.log(`未找到 ${date} 的报告`);
    return;
  }
  console.log(`打开 ${date} 的报告: ${reportPath}`);
}

function generateReportMeta(date) {
  const metaPath = path.join(DAILY_DIR, date, 'meta.json');
  const meta = {
    date,
    createdAt: new Date().toISOString(),
    workspace: WORKSPACE,
    researchDirs: [
      '0-公司深度/',
      '1-细分行业&产业链分析/',
      '2-公司PK/'
    ],
    status: 'pending'
  };
  ensureDir(path.join(DAILY_DIR, date));
  fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2));
  console.log(`已创建 ${date} 的报告元数据: ${metaPath}`);
  return meta;
}

function main() {
  const args = process.argv.slice(2);
  const dateArg = args.find(a => a.startsWith('--date='));
  const listFlag = args.includes('--list');
  const reviewArg = args.find(a => a.startsWith('--review='));
  const wsArg = args.find(a => a.startsWith('--workspace='));

  if (wsArg) {
    process.env.SERENITY_WORKSPACE = wsArg.split('=')[1];
  }

  if (listFlag) {
    listReports();
    return;
  }

  if (reviewArg) {
    const date = reviewArg.split('=')[1];
    reviewReport(date);
    return;
  }

  const date = (dateArg ? dateArg.split('=')[1] : null) || getToday();
  ensureDir(DAILY_DIR);
  const meta = generateReportMeta(date);

  console.log('\n========================================');
  console.log('Serenity 每日投研分析');
  console.log(`日期: ${date}`);
  console.log(`工作区: ${WORKSPACE}`);
  console.log('========================================\n');
  console.log('报告目录:', path.join(DAILY_DIR, date));
  console.log('\n下一步: 请使用 serenity-daily-research Skill 执行投研分析');
  console.log('该 Skill 将自动完成以下步骤:');
  console.log('  1. 调研当天最新市场热点');
  console.log('  2. 从研报库匹配相关信息');
  console.log('  3. 按 Serenity 紫苏叶理论筛选标的');
  console.log('  4. 技术面验证');
  console.log('  5. 生成策略报告');
  console.log('  6. 前日复盘（如有）');
}

main();
