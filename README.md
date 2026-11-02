# SuperDog 加密狗认证扩展 —— Manifest V3 兼容修复

把老版 **CRX2 / Manifest V2** 的 SuperDog（深思数盾 / Virbox）加密狗浏览器扩展，移植为 **Manifest V3**，使其能继续在 **Edge 139+ / Chrome 139+** 上加载运行。

面向的场景：一批政务 / 房地产 / 招投标老系统依赖这个扩展通过 `nativeMessaging` 与本机加密狗通讯。2025 年起 Chromium 内核停用 MV2、拒收 CRX2，原厂安装包直接装不上了。本仓库提供一份最小改动的兼容移植。

> 非官方项目。与原厂（Gemalto / 深思数盾）无任何关联，未获其授权或背书。

---

## 一、为什么原扩展装不上

把 `.crx` 拖进浏览器时报 `CRX_HEADER_INVALID`，只是第一层。实际有两道门都过不了：

| 层级 | 问题 | 判断依据 |
|------|------|----------|
| 1 | 文件是 **CRX2** 格式，Chromium 只接受 CRX3 | 文件头 `Cr24` 后版本号 `02000000`（CRX3 为 `03000000`） |
| 2 | 扩展是 **Manifest V2**，已被停用 | `"manifest_version": 2` + `background.scripts` 持久后台页 |

所以只重打包成 CRX3 没有用，会继续被"清单版本过旧"拦下。必须改造成 MV3，并以**加载解压缩扩展**的方式安装。

## 二、最关键的坑：扩展 ID 不能变

本地消息宿主（`dogauthentication-win.json`）用 `allowed_origins` 白名单锁死了扩展 ID：

```json
"allowed_origins": [
  "chrome-extension://pkoaafcbkhngggbdlpjojgadneppiajj/",
  "chrome-extension://hffoinfgcckjcnbnkklmllehiclagnam/"
]
```

而**加载解压缩的扩展，ID 由目录路径哈希生成**——换个目录就换个 ID，宿主立刻拒绝连接：

```
Access to the specified native messaging host is forbidden.
```

扩展看起来装好了，实际是死的。这是本项目唯一的技术难点。

### 解法

CRX 内嵌着原始 RSA-2048 公钥。把它以 base64 写进 `manifest.json` 的 `key` 字段，扩展 ID 就被钉死回原值：

```json
"key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsqiTPw9z..."
```

验算（`ID = sha256(公钥 DER)[:16]`，十六进制映射到 `a`–`p`）：

```
sha256(pubkey)[0:32] -> 9f9a0a2...  (32 hex)
derived id           -> pkoaafcbkhngggbdlpjojgadneppiajj   ← 与白名单第一条一致
```

> 无法重签一个"ID 不变"的 CRX3：CRX3 签名需要原作者私钥，我们拿不到。**保留 ID 的唯一可行路径就是解压加载 + `key` 字段。**

## 三、安装

详见 [INSTALL.md](INSTALL.md)。最简版：

1. 打开 `edge://extensions/`（Chrome 为 `chrome://extensions/`）
2. 打开**开发人员模式**
3. **加载解压缩的扩展** → 选本仓库根目录
4. 扩展管理页里应当显示 ID 为 `pkoaafcbkhngggbdlpjojgadneppiajj`

**Edge 用户注意**：Edge 只从自己的注册表命名空间读取本地消息宿主，原厂安装程序通常只写了 Chrome 的键。需要补一条（当前用户即可，无需管理员）：

```
HKCU\SOFTWARE\Microsoft\Edge\NativeMessagingHosts\dogauthentication
  (默认值) = C:\Program Files (x86)\Common Files\Gemalto Dog\SuperDog Auth\dogauthentication-win.json
```

撤销：

```powershell
Remove-Item "HKCU:\SOFTWARE\Microsoft\Edge\NativeMessagingHosts" -Recurse -Force
```

## 四、改了什么

| 文件 | 改动 |
|------|------|
| `manifest.json` | `manifest_version` 2 → 3；`background.scripts` → `background.service_worker`；删除 `update_url`（本地扩展无需，保留会被引导去商店校验）；新增 `host_permissions`；**新增 `key` 字段以保持扩展 ID** |
| `background.js` | 重写为 Service Worker 语义：宿主连接按需建立、断开自动重连、`postMessage` 加异常兜底 |
| `content.js` | 注入时机 `document_idle` → `document_start`（页面可能在 DOM 就绪前就发起握手）；端口失效时重连重发一次；`event.data` 加空值判断 |

协议层（`SNTL_FROM_PAGE` / `SNTL_FROM_HOST` 消息格式、`dogport` 端口名、`dogauthentication` 宿主名）**完全未改动**，因此与原厂 `doghost.exe` 保持兼容。

## 五、本仓库不包含什么

| 不包含 | 原因 |
|--------|------|
| `doghost.exe` 及驱动 | 原厂专有二进制，需从其官方安装包装 |
| 原厂 128px 图标 | 原厂美术资源，不再分发。仓库内附带的 `icon-128.png` 是本项目自绘的替代图标（`make-icon.py` 生成，可自行替换） |
| 原始 `.crx` | 同上。用 `extract-crx.py` 可从你自己的安装包里解出对照 |

## 六、目录

```
manifest.json         ← 扩展清单（本仓库根目录即扩展本体，加载解压缩时选这个目录）
background.js            MV3 Service Worker，负责与本地宿主通讯
content.js               页面桥接脚本
icon-128.png             扩展图标（本项目自绘，可用 make-icon.py 重新生成）
extract-crx.py           解析 CRX2/CRX3，导出原始文件并验算扩展 ID
make-icon.py             生成自绘 128px 图标（可选，纯 Python 无依赖）
INSTALL.md               详细安装与排错
NOTICE.md                来源、权利与免责声明
```

> 根目录的 `README.md`、`LICENSE` 等文件与扩展无关，Chromium 加载时会忽略，不影响运行。

## 七、验证记录

在 Edge `139.0.3405.119`（Windows，Chromium 内核）上以临时用户配置加载，通过 DevTools 协议确认：

```
service_worker | chrome-extension://pkoaafcbkhngggbdlpjojgadneppiajj/background.js
```

即：MV3 清单被接受、Service Worker 正常注册、扩展 ID 与原版一致。

## 八、许可

本仓库**我们改写的部分**（MV3 移植代码、工具脚本、文档）采用 [MIT](LICENSE)。
上游扩展本身为第三方专有软件，本项目不对其主张任何权利，详见 [NOTICE.md](NOTICE.md)。

按现状提供，不附带任何担保。用于承载合同、备案等正式业务的系统前，请自行完成充分验证。
