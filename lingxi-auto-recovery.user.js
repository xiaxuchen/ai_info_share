// ==UserScript==
// @name         灵犀自动恢复
// @namespace    https://docs.scriptcat.org/
// @version      0.5.0
// @description  自动取消任务、新建会话、输入发送；控制台 stop() 停止
// @author       You
// @match        https://code.x-peng.com/workbench/workspace/*
// @grant        none
// @noframes
// ==/UserScript==

(function() {
    'use strict';

    // ==================== 配置 ====================

    const CONFIG = {
        intervalMs: 15000,           // 正常轮询间隔（ms）
        coolDownMs: 5 * 60 * 1000,   // 超限冷却时间
        limitCount: 3,               // 统计窗口内上限次数
        timeWindow: 60 * 1000,       // 统计窗口大小
        inputDelay: 1500,            // 输入后等多久再点发送
        sendMessage: '拉取最新的xp-charge-skills,继续启动多活循环机制，加载长期记忆',
    };

    // ==================== 状态 ====================

    let timer = null;
    let coolDownTimer = null;
    let isRunning = false;
    const runTimeList = [];

    // ==================== 工具 ====================

    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
    const $ = (s) => document.querySelector(s);
    const $$ = (s) => Array.from(document.querySelectorAll(s));

    /**
     * 查找包含指定文本的可点击元素（button 或带 role 的元素）
     * 去除空格后匹配，支持"取 消"这类按钮
     */
    const findClickableByText = (text) => {
        const normalized = text.replace(/\s+/g, '');
        const candidates = $$('button, [role="button"], a[class*="btn"], a[class*="iconBtn"]');
        return candidates.find(el => {
            const t = (el.innerText || '').trim().replace(/\s+/g, '');
            return t === normalized || t.includes(normalized);
        });
    };

    // ==================== 页面操作 ====================

    /**
     * 0. 取消正在运行的任务
     * 如果页面有"取消"按钮则点击，然后处理弹出的"确定"确认框
     * @returns {Promise<boolean>} 是否执行了取消
     */
    async function tryCancelRunning() {
        const cancelBtn = findClickableByText('取消');
        if (!cancelBtn) return false;

        console.log('[灵犀] 检测到取消按钮，点击取消');
        cancelBtn.click();
        await sleep(1000);

        // 取消后会弹出确认框，按钮文本是"确 认"（带空格）
        // findClickableByText 已做去空格处理，用"确认"匹配
        const confirmBtn = findClickableByText('确认');
        if (confirmBtn) {
            console.log('[灵犀] 检测到确认弹窗，点击确认');
            confirmBtn.click();
            await sleep(2000);
        } else {
            // 弹窗可能延迟出现，再等一会重试
            await sleep(1000);
            const retryConfirm = findClickableByText('确认');
            if (retryConfirm) {
                console.log('[灵犀] 延迟检测到确认弹窗，点击确认');
                retryConfirm.click();
                await sleep(2000);
            }
        }

        return true;
    }

    /**
     * 1. 新建会话：点击"会话"区域旁的新建图标
     * @returns {Promise<boolean>} 是否成功创建
     */
    async function tryCreateNewSession() {
        const svgs = document.querySelectorAll('svg.lucide-message-square-plus');
        let addIcon = null;
        for (const svg of svgs) {
            const wrap = svg.closest('div');
            if (wrap && wrap.innerText.includes('会话')) {
                addIcon = svg;
                break;
            }
        }

        if (!addIcon) {
            console.log('[灵犀] 未找到新建会话图标');
            return false;
        }

        console.log('[灵犀] 点击新建会话图标');
        addIcon.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        await sleep(3000);
        return true;
    }

    /**
     * 2. 输入文字并点击发送
     * @returns {Promise<boolean>} 是否发送成功
     */
    async function tryInputAndSend() {
        const inputBox =
            $('div[data-chat-input="1"][contenteditable="true"]') ||
            $('div[contenteditable="true"][role="textbox"]');

        const sendBtn = $('button[title="⌘↵"]');

        if (!inputBox) {
            console.warn('[灵犀] 未找到输入框');
            return false;
        }
        if (!sendBtn) {
            console.warn('[灵犀] 未找到发送按钮');
            return false;
        }

        // 填入内容（Tiptap/ProseMirror 编辑器用 <p> 包裹）
        inputBox.focus();
        inputBox.innerHTML = `<p>${CONFIG.sendMessage}</p>`;
        inputBox.dispatchEvent(new Event('input', { bubbles: true }));
        await sleep(100);
        inputBox.dispatchEvent(new Event('change', { bubbles: true }));

        console.log('[灵犀] 已填入内容:', CONFIG.sendMessage);

        // 等待框架识别内容
        await sleep(CONFIG.inputDelay);

        // 确认内容还在（防止被框架清空）
        if (!inputBox.textContent.trim()) {
            console.warn('[灵犀] 输入框内容被清空，跳过发送');
            return false;
        }

        // 点击发送
        console.log('[灵犀] 点击发送');
        sendBtn.click();
        await sleep(1000);
        return true;
    }

    // ==================== 核心循环 ====================

    async function runTask() {
        if (isRunning) {
            console.log('[灵犀] 上一轮仍在执行，跳过');
            return;
        }
        isRunning = true;

        try {
            const now = Date.now();

            // 清理过期记录
            while (runTimeList.length && now - runTimeList[0] > CONFIG.timeWindow) {
                runTimeList.shift();
            }

            // 频率限制
            if (runTimeList.length >= CONFIG.limitCount) {
                console.log(`[灵犀] ${CONFIG.timeWindow / 1000}秒内已执行${runTimeList.length}次，冷却${CONFIG.coolDownMs / 1000}秒`);
                clearInterval(timer);
                timer = null;
                coolDownTimer = setTimeout(() => {
                    console.log('[灵犀] 冷却结束，恢复');
                    startLoop();
                    coolDownTimer = null;
                }, CONFIG.coolDownMs);
                return;
            }

            runTimeList.push(now);
            console.log(`[灵犀] 第 ${runTimeList.length}/${CONFIG.limitCount} 轮任务开始`);

            // 步骤0: 取消正在运行的任务（如有）
            if (await tryCancelRunning()) {
                console.log('[灵犀] 任务已取消');
            }

            // 步骤1: 新建会话
            if (await tryCreateNewSession()) {
                console.log('[灵犀] 新会话已创建');
            }

            // 步骤2: 输入并发送
            await sleep(1000);
            if (await tryInputAndSend()) {
                console.log('[灵犀] 消息已发送');
            }

        } catch (err) {
            console.error('[灵犀] 任务出错:', err.message);
        } finally {
            isRunning = false;
        }
    }

    // ==================== 控制 ====================

    function startLoop() {
        if (timer) return;
        console.log('[灵犀] 自动任务已启动');
        timer = setInterval(runTask, CONFIG.intervalMs);
    }

    function stopLoop() {
        clearInterval(timer);
        clearTimeout(coolDownTimer);
        timer = null;
        coolDownTimer = null;
        isRunning = false;
        console.log('[灵犀] 已停止，刷新页面可重新启动');
    }

    // ==================== 启动 ====================

    startLoop();

    window.stop = stopLoop;
    window.start = startLoop;
    window.lingxiConfig = CONFIG;

    console.log('%c[灵犀自动恢复] 脚本已加载 v0.5.0', 'color: #4CAF50; font-weight: bold');
    console.log('  stop()        - 停止');
    console.log('  start()       - 启动');
    console.log('  lingxiConfig  - 查看/修改配置');
})();
