/**
 * 灵犀工作空间批量创建脚本
 * 用法：在 AI编程(灵犀) 的 Dashboard 页面打开浏览器控制台(F12)，粘贴此代码并回车执行
 *
 * 示例：
 * await batchCreateWorkspace('充电feature-xxx', [
 *   { name: 'xp-charge', gitUrl: 'https://gitlab.xiaopeng.com/FRD-充电研发组/xp-charge.git', branch: 'develop' },
 *   { name: 'xp-charge-parent', gitUrl: 'https://gitlab.xiaopeng.com/FRD-充电研发组/xp-charge-parent.git', branch: 'develop' },
 * ]);
 */

(function() {
  'use strict';

  // ============ 工具函数 ============

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

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

  const waitForText = (text, timeout = 10000) => {
    return new Promise((resolve, reject) => {
      const check = () => {
        if (document.body.innerText.includes(text)) return resolve(true);
        requestAnimationFrame(check);
      };
      check();
      setTimeout(() => reject(new Error(`等待文本超时: ${text}`)), timeout);
    });
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

  const fillInput = async (selector, value) => {
    const input = await waitForElement(selector);
    input.focus();

    // 使用原生属性setter绕过React受控组件的状态管理
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value'
    ).set;
    nativeSetter.call(input, value);

    // 触发React需要的事件
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await sleep(800);
  };

  const clickButton = async (textOrSelector, isSelector = false) => {
    let btn;
    if (isSelector) {
      btn = await waitForElement(textOrSelector);
    } else {
      // 通过按钮文本查找
      const buttons = Array.from(document.querySelectorAll('button'));
      btn = buttons.find(b => b.innerText.trim().includes(textOrSelector));
    }
    if (!btn) throw new Error(`未找到按钮: ${textOrSelector}`);
    btn.click();
    await sleep(300);
  };

  // ============ 核心功能 ============

  /**
   * 创建工作空间
   * @param {string} name - 工作空间名称
   * @param {string} prompt - 工作空间提示词（可选）
   * @returns {Promise<string>} 新工作空间的ID
   */
  async function createWorkspace(name, prompt = '') {
    // 确保在 Dashboard 页面
    if (!window.location.href.includes('/workbench/dashboard')) {
      throw new Error('请先导航到 Dashboard 页面: https://code.x-peng.com/workbench/dashboard');
    }

    console.log(`[步骤1/2] 正在创建工作空间: ${name} ...`);

    // 点击"新建工作空间"按钮
    await clickButton('新建工作空间');
    await sleep(500);

    // 填写工作空间名称
    await fillInput('input[placeholder*="智能驾驶研发空间"], input[placeholder*="例如"]\\:nth-child(1)', name);

    // 填写工作空间提示词（如果有）
    if (prompt) {
      await fillInput('input[placeholder*="工作空间总提示词"], textarea[placeholder*="提示词"]', prompt);
    }

    // 点击"创建"按钮
    await clickButton('创建');
    await sleep(1000);

    // 等待弹窗关闭
    await sleep(1500);

    // 获取新创建的工作空间ID（通过API或DOM刷新）
    // 由于创建后页面不会自动跳转，我们需要刷新或搜索
    console.log(`[步骤1/2] 工作空间 "${name}" 创建请求已发送`);

    // 等待一下让后台处理
    await sleep(2000);

    // 尝试通过API获取最新工作空间ID
    try {
      const orgId = await getCurrentOrgId();
      const resp = await fetch(`/api/workspaces?org_id=${orgId}&keyword=${encodeURIComponent(name)}`);
      const data = await resp.json();
      if (data.data && data.data.length > 0) {
        const workspace = data.data.find(w => w.name === name);
        if (workspace) {
          console.log(`[步骤1/2] 工作空间创建成功，ID: ${workspace.id}`);
          return workspace.id;
        }
      }
    } catch (e) {
      console.warn('无法通过API获取工作空间ID:', e.message);
    }

    return null;
  }

  /**
   * 在工作空间中创建/添加项目（仓库）
   * @param {string} workspaceId - 工作空间ID
   * @param {Object} repo - 仓库配置 { name, gitUrl, branch }
   */
  async function addProjectToWorkspace(workspaceId, repo) {
    const { name, gitUrl, branch = 'master' } = repo;

    console.log(`  → 正在添加仓库: ${name} (${branch})`);

    // 点击工作空间卡片上的"新建项目"按钮
    // 需要先找到对应工作空间卡片的按钮
    const card = findWorkspaceCard(workspaceId);
    if (!card) {
      console.warn(`  ⚠ 未找到工作空间卡片，尝试通过全局"新建项目"添加`);
      // 如果没有找到特定工作空间的卡片，使用全局新建项目
      await clickButton('新建项目');
    } else {
      const newProjectBtn = card.querySelector('button');
      if (newProjectBtn) {
        newProjectBtn.click();
      } else {
        await clickButton('新建项目');
      }
    }

    await sleep(500);

    // 填写Git仓库地址
    const gitInput = await waitForElement('input[placeholder*="gitlab"]');
    await fillInput('input[placeholder*="gitlab"]', gitUrl);

    // 填写项目名称
    await fillInput('input[placeholder*="my-project"]', name);

    // 填写分支
    if (branch) {
      await fillInput('input[placeholder*="默认分支"]', branch);
    }

    await sleep(300);

    // 点击"克隆仓库"按钮
    await clickButton('克隆仓库');

    // 等待"克隆中..."消失（最长60秒）
    try {
      await waitForTextGone('克隆中', 60000);
      console.log(`  ✓ 仓库 "${name}" 克隆完成`);
    } catch (e) {
      console.warn(`  ⚠ 仓库 "${name}" 等待克隆完成超时`);
    }

    // 再等等弹窗关闭
    await sleep(1000);
  }

  /**
   * 查找工作空间卡片
   */
  function findWorkspaceCard(workspaceId) {
    // 尝试通过链接或数据属性查找
    const links = document.querySelectorAll('a[href*="workspace"]');
    for (const link of links) {
      if (link.href.includes(workspaceId)) {
        return link.closest('[class*="card"], [class*="item"]') || link.parentElement;
      }
    }
    return null;
  }

  /**
   * 获取当前组织ID
   */
  async function getCurrentOrgId() {
    try {
      // 从页面全局变量或API获取
      if (window.__APP_STATE__ && window.__APP_STATE__.organization) {
        return window.__APP_STATE__.organization.id;
      }
      // 尝试从URL或其他地方获取
      const resp = await fetch('/api/user/preferences');
      const data = await resp.json();
      return data.data?.org_id || '303181695700852736';
    } catch (e) {
      return '303181695700852736'; // 默认值，从网络请求中观察到的
    }
  }

  // ============ 批量操作 ============

  /**
   * 批量创建工作空间并添加多个仓库
   * @param {string} workspaceName - 新工作空间名称
   * @param {Array} repos - 仓库配置数组 [{ name, gitUrl, branch }]
   * @param {Object} options - 配置选项
   */
  async function batchCreateWorkspace(workspaceName, repos, options = {}) {
    const {
      workspacePrompt = '',
      gitBaseUrl = 'https://gitlab.xiaopeng.com/FRD-充电研发组',
      delay = 3000
    } = options;

    console.log('============================================');
    console.log('🚀 灵犀工作空间批量创建工具');
    console.log('============================================');
    console.log(`工作空间名称: ${workspaceName}`);
    console.log(`仓库数量: ${repos.length}`);
    console.log('');

    // 步骤1: 创建工作空间
    const workspaceId = await createWorkspace(workspaceName, workspacePrompt);

    if (!workspaceId) {
      console.error('❌ 无法获取工作空间ID，请手动刷新页面后重试');
      return;
    }

    // 步骤2: 批量添加仓库
    console.log(`[步骤2/2] 开始添加 ${repos.length} 个仓库...`);

    for (let i = 0; i < repos.length; i++) {
      const repo = repos[i];
      // 自动补全git地址
      if (!repo.gitUrl && repo.name) {
        repo.gitUrl = `${gitBaseUrl}/${repo.name}.git`;
      }

      try {
        await addProjectToWorkspace(workspaceId, repo);
        console.log(`  进度: ${i + 1}/${repos.length}`);
      } catch (err) {
        console.error(`  ❌ 添加仓库 "${repo.name}" 失败:`, err.message);
      }

      // 等待一段时间避免请求过快
      if (i < repos.length - 1) {
        await sleep(delay);
      }
    }

    console.log('');
    console.log('============================================');
    console.log('✅ 批量创建完成！');
    console.log('============================================');
    console.log(`请刷新页面查看工作空间 "${workspaceName}" 和已添加的仓库。`);
  }

  /**
   * 基于现有工作空间快速创建（指定仓库和分支）
   * 这是主要入口函数
   */
  async function createWorkspaceWithRepos(workspaceName, repoConfigs, options = {}) {
    // repoConfigs 格式:
    // [
    //   { name: 'xp-charge', branch: 'develop' },
    //   { name: 'xp-charge-parent', branch: 'feature-xxx' },
    // ]

    const repos = repoConfigs.map(cfg => ({
      name: cfg.name,
      gitUrl: cfg.gitUrl || `${options.gitBaseUrl || 'https://gitlab.xiaopeng.com/FRD-充电研发组'}/${cfg.name}.git`,
      branch: cfg.branch || 'master'
    }));

    return batchCreateWorkspace(workspaceName, repos, options);
  }

  // ============ 暴露全局函数 ============

  window.LingxiWorkspaceCreator = {
    createWorkspace,
    addProjectToWorkspace,
    batchCreateWorkspace,
    createWorkspaceWithRepos,
    sleep,
    utils: { waitForElement, fillInput, clickButton }
  };

  console.log('============================================');
  console.log('✅ 灵犀工作空间创建脚本已加载！');
  console.log('============================================');
  console.log('');
  console.log('可用函数:');
  console.log('  LingxiWorkspaceCreator.createWorkspace(name, prompt)');
  console.log('  LingxiWorkspaceCreator.createWorkspaceWithRepos(name, repoConfigs, options)');
  console.log('  LingxiWorkspaceCreator.batchCreateWorkspace(name, repos, options)');
  console.log('');
  console.log('快速示例:');
  console.log(`  await LingxiWorkspaceCreator.createWorkspaceWithRepos('充电feature-test', [
    { name: 'xp-charge', branch: 'develop' },
    { name: 'xp-charge-parent', branch: 'develop' }
  ]);`);
  console.log('');

})();
