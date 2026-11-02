'use strict';

// SuperDog 加密狗认证扩展 —— 页面桥接脚本
//
// 页面 <-> content script：window.postMessage（SNTL_FROM_PAGE / SNTL_FROM_HOST）
// content script <-> background：runtime.connect 长连接（端口名 dogport）
//
// 与原始 MV2 版本的差异：
//   1. 注入时机改为 document_start —— 页面脚本可能在 DOM 就绪前就发起认证，
//      原版 document_idle 会漏掉握手消息；
//   2. 端口失效时自动重连并重发一次（ MV3 后台被回收会打断长连接）；
//   3. 对 event.data 做空值与类型判断。

var port = null;

function ensurePort() {
    if (port) {
        return port;
    }
    try {
        port = chrome.runtime.connect({ name: 'dogport' });
    } catch (e) {
        port = null;
        return null;
    }

    port.onMessage.addListener(function () { /* 应答统一走 runtime.onMessage 回页面 */ });
    port.onDisconnect.addListener(function () {
        port = null;
    });

    return port;
}

// 后台回传（来自本地宿主）的应答 -> 页面
chrome.runtime.onMessage.addListener(function (request) {
    window.postMessage({ type: 'SNTL_FROM_HOST', text: request }, '*');
});

// 页面发起的认证请求 -> 后台 -> 本地宿主
window.addEventListener('message', function (event) {
    if (event.source !== window) {
        return;
    }
    if (!event.data || event.data.type !== 'SNTL_FROM_PAGE') {
        return;
    }

    var payload = event.data.text;
    var p = ensurePort();
    if (!p) {
        return;
    }

    try {
        p.postMessage(payload);
    } catch (e) {
        // 端口已失效（后台 Service Worker 被回收等）：重连一次后重发
        port = null;
        var retried = ensurePort();
        if (retried) {
            try { retried.postMessage(payload); } catch (e2) { /* 宿主不可用，放弃本次 */ }
        }
    }
}, false);
