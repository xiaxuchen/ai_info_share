/**
 * 灵犀工作空间创建脚本
 *
 * 使用方法：
 * 1. 打开灵犀 Dashboard 页面: https://code.x-peng.com/workbench/dashboard
 * 2. 按 F12 打开浏览器控制台
 * 3. 粘贴此脚本并回车执行
 *
 * ======================== 配置说明 ========================
 *
 * CONFIG.newWorkspaceName  [必填] 新工作空间的名称，例如 '充电feature-123'
 *
 * CONFIG.newWorkspacePrompt [选填] 工作空间总提示词，不填则留空
 *
 * CONFIG.defaultBranch  [选填] 默认分支，适用于所有未单独指定 branch 的仓库
 *                        - 设为 'develop' 则所有仓库默认使用 develop 分支
 *                        - 设为 '' 则不填写分支，使用系统默认
 *
 * CONFIG.repos  [必填] 仓库列表，每项格式:
 *   {
 *     name: '仓库名',          // 工作空间中显示的项目名称
 *     gitUrl: '完整git地址',    // 支持 ssh 和 https 格式
 *     branch: '分支名'          // [选填] 该仓库的专属分支，不填则用 defaultBranch
 *   }
 *
 * 分支优先级: repo.branch > CONFIG.defaultBranch > 不填写(系统默认)
 *
 * ======================== 示例 ========================
 *
 * // 所有仓库默认用 develop 分支
 * CONFIG.defaultBranch = 'develop';
 * CONFIG.repos = [
 *   { name: 'xp-charge', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge.git' },
 *   { name: 'xp-common', gitUrl: 'https://gitlab.x-peng.com/charging/xp-common' },
 *   // xp-thor 单独用 feature-123 分支
 *   { name: 'xp-thor', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor.git', branch: 'feature-123' },
 * ];
 *
 * // 不指定任何分支，全部使用系统默认
 * CONFIG.defaultBranch = '';
 * CONFIG.repos = [
 *   { name: 'xp-charge', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge.git' },
 * ];
 */

(async function() {
  'use strict';

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  // ==================== 配置区域：修改这里 ====================

  const CONFIG = {
    // 新工作空间名称
    newWorkspaceName: '充电feature-xxx',

    // 新工作空间提示词（可选）
    newWorkspacePrompt: '',

    // 仓库配置列表：从充电develop提取的47个仓库
    // 格式: { name: '仓库名', gitUrl: '完整git地址' }
    // 需要指定分支时可添加 branch 属性: { name: 'xxx', gitUrl: '...', branch: 'develop' }
    repos: [
      { name: 'xp-charge', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge.git' },
      { name: 'xp-charge-parent', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-parent.git' },
      { name: 'xp-charge-activity', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-activity.git' },
      { name: 'xp-charge-asset', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-asset.git' },
      { name: 'xp-charge-charging', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-charging.git' },
      { name: 'xp-charge-collection', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-collection.git' },
      { name: 'xp-charge-common', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-common.git' },
      { name: 'xp-charge-customer-group', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-customer-group.git' },
      { name: 'xp-charge-data-collector', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-data-collector.git' },
      { name: 'xp-charge-open', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-open.git' },
      { name: 'xp-charge-par-marketing', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/par/backend/xp-charge-par-marketing.git' },
      { name: 'xp-thor-finance', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-finance.git' },
      { name: 'xp-thor-common', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-common.git' },
      { name: 'xp-thor-operate', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-operate.git' },
      { name: 'xp-charge-parking', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-parking.git' },
      { name: 'xp-charge-pile-state', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-pile-state.git' },
      { name: 'xp-charge-pile-time', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-pile-time.git' },
      { name: 'xp-charge-private-collection', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-private-collection.git' },
      { name: 'xp-charge-private-pile', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-private-pile.git' },
      { name: 'xp-charge-starter', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-starter.git' },
      { name: 'xp-charge-station-monitor', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-station-monitor.git' },
      { name: 'xp-charge-third-sync', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-third-sync.git' },
      { name: 'xp-charge-vehicle-gw', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-charge-vehicle-gw.git' },
      { name: 'xp-thor-saas', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/fe/xp-thor-saas.git' },
      { name: 'xp-thor-saas-asset', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/thor-saas/xp-thor-saas-asset.git' },
      { name: 'xp-thor-saas-common', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/thor-saas/xp-thor-saas-common.git' },
      { name: 'xp-thor-saas-data', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/thor-saas/xp-thor-saas-data.git' },
      { name: 'xp-thor-saas-gw', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/thor-saas/xp-thor-saas-gw.git' },
      { name: 'xp-thor-saas-notify', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/thor-saas/xp-thor-saas-notify.git' },
      { name: 'xp-thor-saas-operation', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/thor-saas/xp-thor-saas-operation.git' },
      { name: 'xp-thor-saas-system', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/thor-saas/xp-thor-saas-system.git' },
      { name: 'xp-search-2', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-search-2.git' },
      { name: 'xp-lark-coupon', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-lark-coupon.git' },
      { name: 'xp-charge-skills', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/ai-infra/xp-charge-skills.git' },
      { name: 'xp-thor-ops', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-ops.git' },
      { name: 'xp-thor-project', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-project.git' },
      { name: 'xp-thor-data', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-data.git' },
      { name: 'xp-thor-asset', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-asset.git' },
      { name: 'xp-thor-auth', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-auth.git' },
      { name: 'xp-thor-xxljob', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-xxljob.git' },
      { name: 'xp-thor-workflow', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-workflow.git' },
      { name: 'xp-thor-settle', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-settle.git' },
      { name: 'xp-thor-par-construction', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/par/backend/xp-thor-par-construction.git' },
      { name: 'xp-thor-notify', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor-notify.git' },
      { name: 'xp-thor-mgnt', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/fe/xp-thor-mgnt.git' },
      { name: 'xp-thor', gitUrl: 'ssh://git@gitlab.xiaopeng.local:10022/charging/xp-thor.git' },
      { name: 'xp-common', gitUrl: 'https://gitlab.x-peng.com/charging/xp-common' },
    ],

    // 每次添加仓库后的等待时间（毫秒）
    delayBetweenRepos: 3000,
  };

  // ==================== 工具函数 ====================

  const waitForElement = (selector, timeout = 10000) => {
    return new Promise((resolve, reject) => {
      const el = document.querySelector(selector);
      if (el) return resolve(el);

      const observer = new MutationObserver(() => {
        const el = document.querySelector(selector);
        if (el) {
          observer.disconnect();
          resolve(el);
        }
      });

      observer.observe(document.body, { childList: true, subtree: true });

      setTimeout(() => {
        observer.disconnect();
        reject(new Error(`等待元素超时: ${selector}`));
      }, timeout);
    });
  };

    const fillInput = async (selector, value) => {
    const input = await waitForElement(selector);
    input.focus();

    // 使用原生属性setter绕过React受控组件的状态管理
    const prototype = Object.getPrototypeOf(input);
    const nativeSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
    if (nativeSetter) {
      nativeSetter.call(input, value);
    } else {
      // fallback：直接赋值
      input.value = value;
    }

    // 触发React需要的事件
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await sleep(800);
  };

  const clickButtonByText = async (text) => {
    const buttons = Array.from(document.querySelectorAll('button'));
    // 去除空格后匹配，支持"创 建"这类按钮
    const btn = buttons.find(b => {
      const btnText = b.innerText.trim().replace(/\s+/g, '');
      return btnText.includes(text.replace(/\s+/g, ''));
    });
    if (!btn) throw new Error(`未找到按钮: ${text}`);
    btn.click();
    await sleep(500);
  };

  // 等待指定文本从页面上消失
  const waitForTextGone = (text, timeout = 60000) => {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const check = () => {
        const gone = !document.body.innerText.includes(text);
        if (gone) {
          resolve(true);
          return;
        }
        if (Date.now() - startTime > timeout) {
          reject(new Error(`等待"${text}"消失超时`));
          return;
        }
        setTimeout(check, 500);
      };
      check();
    });
  };

  // 关闭当前弹窗（点击弹窗右上角的关闭按钮或取消按钮）
  const closeDialog = async () => {
    // 尝试查找关闭按钮：通常是弹窗右上角的 X 或"取消"按钮
    const closeBtns = document.querySelectorAll(
      '[class*="close"], [class*="Close"], svg[class*="close"], button[aria-label="Close"]'
    );
    if (closeBtns.length > 0) {
      // 取最后一个（通常是最上层弹窗的关闭按钮）
      const btn = closeBtns[closeBtns.length - 1];
      btn.click();
      await sleep(500);
      return;
    }
    // 尝试点击"取消"按钮
    const buttons = Array.from(document.querySelectorAll('button'));
    const cancelBtn = buttons.find(b => b.innerText.trim().replace(/\s+/g, '') === '取消');
    if (cancelBtn) {
      cancelBtn.click();
      await sleep(500);
      return;
    }
    // 最后手段：按 Escape 关闭弹窗
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await sleep(500);
  };

  // ==================== 核心逻辑 ====================

  async function main() {
    // 检查页面
    if (!window.location.href.includes('/workbench/dashboard')) {
      alert('请先导航到 Dashboard 页面: https://code.x-peng.com/workbench/dashboard');
      return;
    }

    console.clear();
    console.log('============================================');
    console.log('🚀 灵犀工作空间一键复制工具');
    console.log('============================================');
    console.log(`目标工作空间: ${CONFIG.newWorkspaceName}`);
    console.log(`仓库数量: ${CONFIG.repos.length}`);
    console.log('');

    // 步骤1: 创建工作空间
    console.log('[步骤1/2] 创建工作空间...');
    await clickButtonByText('新建工作空间');
    await sleep(1000); // 等待弹窗渲染

    await fillInput('input[placeholder*="智能驾驶研发空间"]', CONFIG.newWorkspaceName);
    if (CONFIG.newWorkspacePrompt) {
      await fillInput('input[placeholder*="工作空间总提示词"], textarea[placeholder*="提示词"]', CONFIG.newWorkspacePrompt);
    }

    await sleep(500); // 等待按钮可用
    await clickButtonByText('创建');
    await sleep(3000);
    console.log('✅ 工作空间创建请求已发送');

    // 获取工作空间ID
    let workspaceId = null;
    try {
      const resp = await fetch('/api/workspaces?org_id=303181695700852736&keyword=' + encodeURIComponent(CONFIG.newWorkspaceName));
      const data = await resp.json();
      if (data.data?.length > 0) {
        const ws = data.data.find(w => w.name === CONFIG.newWorkspaceName);
        if (ws) workspaceId = ws.id;
      }
    } catch (e) {
      console.warn('获取工作空间ID失败:', e.message);
    }

    if (!workspaceId) {
      console.warn('无法获取工作空间ID，尝试手动搜索...');
      // 刷新页面以获取最新列表
      // 不自动刷新，让用户手动操作
    }

    // 步骤2: 批量添加仓库
    console.log('');
    console.log(`[步骤2/2] 开始添加 ${CONFIG.repos.length} 个仓库...`);
    console.log('（注意：如果未找到工作空间卡片，请手动刷新页面后再次运行脚本）');
    console.log('');

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < CONFIG.repos.length; i++) {
      const repo = CONFIG.repos[i];
      const gitUrl = repo.gitUrl;
      // 分支优先级：repo.branch > CONFIG.defaultBranch > 不填写
      const branch = repo.branch || CONFIG.defaultBranch || '';

      console.log(`[${i + 1}/${CONFIG.repos.length}] ${repo.name}${branch ? ` (${branch})` : ''}`);

      try {
        // 点击"新建项目"
        await clickButtonByText('新建项目');
        await sleep(500);

        // 填写Git地址
        await fillInput('input[placeholder*="gitlab"]', gitUrl);

        // 填写项目名称
        await fillInput('input[placeholder*="my-project"]', repo.name);

        // 有分支时才填写
        if (branch) {
          await fillInput('input[placeholder*="默认分支"]', branch);
        }

        await sleep(200);

        // 点击克隆
        await clickButtonByText('克隆仓库');

        // 等待"克隆中..."消失（最长60秒）
        try {
          await waitForTextGone('克隆中', 180000);
          console.log(`  ✅ ${repo.name} 克隆完成`);
        } catch (e) {
          console.warn(`  ⚠ ${repo.name} 等待克隆完成超时，尝试关闭弹窗继续...`);
          await closeDialog();
        }

        // 再等等弹窗关闭
        await sleep(1000);
        successCount++;
      } catch (err) {
        console.error(`  ❌ ${repo.name} 添加失败:`, err.message);
        // 确保弹窗被关闭，避免影响下一个仓库
        await closeDialog();
        await sleep(1000);
        failCount++;
      }

      // 等待
      if (i < CONFIG.repos.length - 1) {
        await sleep(CONFIG.delayBetweenRepos);
      }
    }

    // 完成
    console.log('');
    console.log('============================================');
    console.log('✅ 批量创建完成！');
    console.log(`成功: ${successCount} / 失败: ${failCount}`);
    console.log('============================================');
    console.log(`请刷新页面查看工作空间 "${CONFIG.newWorkspaceName}"`);
  }

  // 运行
  await main();

})();
