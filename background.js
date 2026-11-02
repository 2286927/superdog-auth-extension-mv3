'use strict';

// SuperDog 加密狗认证扩展 —— MV3 Service Worker
//
// 职责：把页面侧（content script）的认证请求转发给本地宿主 doghost.exe，
//       再把宿主的应答回传给当前标签页。
//
// 与原始 MV2 版本的差异：
//   1. 后台从持久化后台页改为 Service Worker，会被随时回收，因此宿主连接必须按需重建；
//   2. 端口断开后一律置空，下一次请求自动重连，不保留失效句柄；
//   3. postMessage 包异常，避免宿主进程消失时抛未捕获错误。

var HOST_NAME = 'dogauthentication';
var nativePort = null;

function dropNativePort() {
    if (nativePort) {
        try { nativePort.disconnect(); } catch (e) { /* 已断开，忽略 */ }
        nativePort = null;
    }
}

// 按需建立到本地宿主的连接；Service Worker 被回收后靠这里自动重连。
function getNativePort() {
    if (nativePort) {
        return nativePort;
    }
    try {
        nativePort = chrome.runtime.connectNative(HOST_NAME);
    } catch (e) {
        nativePort = null;
        return null;
    }

    nativePort.onMessage.addListener(function (reply) {
        chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
            if (tabs && tabs[0] && tabs[0].id !== undefined) {
                try {
                    chrome.tabs.sendMessage(tabs[0].id, reply);
                } catch (e) { /* 目标页面已关闭，忽略 */ }
            }
        });
    });

    nativePort.onDisconnect.addListener(function () {
        // 宿主进程退出或通道断开：置空，下次请求时重新拉起
        nativePort = null;
    });

    return nativePort;
}

chrome.runtime.onConnect.addListener(function (pagePort) {
    if (pagePort.name !== 'dogport') {
        return;
    }

    pagePort.onMessage.addListener(function (msg) {
        var port = getNativePort();

        if (!port) {
            // 宿主不可用：断开页面端口，让页面侧下次请求时重连
            try { pagePort.disconnect(); } catch (e) { /* 忽略 */ }
            return;
        }

        try {
            port.postMessage(msg);
        } catch (e) {
            dropNativePort();
            try { pagePort.disconnect(); } catch (e2) { /* 忽略 */ }
        }
    });
});
