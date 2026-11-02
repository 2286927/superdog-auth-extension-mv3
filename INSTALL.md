# 安装与排错

面向 Edge / Chrome 139 及以上版本（Chromium 内核，已停用 Manifest V2）。

---

## 一、准备

1. 先安装原厂客户端（提供 `doghost.exe` 本地消息宿主与加密狗驱动）。
   Windows 默认位置：

   ```
   C:\Program Files (x86)\Common Files\Gemalto Dog\SuperDog Auth\
   ├─ doghost.exe
   ├─ dogauthentication-win.json     ← 本地消息宿主清单
   └─ ...
   ```

2. 插好加密狗。

> 本仓库不含原厂二进制。没有原厂客户端，扩展装上也无法认证。

## 二、安装扩展

1. 浏览器地址栏打开
   - Edge：`edge://extensions/`
   - Chrome：`chrome://extensions/`
2. 打开 **开发人员模式 / Developer mode**
3. 点 **加载解压缩的扩展 / Load unpacked**
4. 选择本仓库根目录（含 `manifest.json` 的那一层）
5. 确认列表中出现 `SuperDog Authentication Extension`

### 必须核对：扩展 ID

在扩展条目上应能看到：

```
ID: pkoaafcbkhngggbdlpjojgadneppiajj
```

**这个 ID 必须与上面完全一致。** 如果 ID 不同，说明 `manifest.json` 的 `key` 字段被改动过或文件被重新打包过——此时宿主会拒绝连接，扩展是死的。

自己验算：

```bash
python extract-crx.py --id-only path/to/DogAuthExtension.crx
```

## 三、Edge 需要额外一条注册表（Chrome 通常不用）

Chromium 系浏览器只从**自己的**注册表命名空间读取本地消息宿主。原厂安装程序一般只注册了 Chrome 的键，所以 Edge 里 `connectNative` 会报"未找到指定的本地消息宿主"。

### 写入（当前用户，无需管理员）

PowerShell：

```powershell
$path = "C:\Program Files (x86)\Common Files\Gemalto Dog\SuperDog Auth\dogauthentication-win.json"
New-Item -Path "HKCU:\SOFTWARE\Microsoft\Edge\NativeMessagingHosts\dogauthentication" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Edge\NativeMessagingHosts\dogauthentication" -Name "(default)" -Value $path
```

核对：

```powershell
(Get-ItemProperty "HKCU:\SOFTWARE\Microsoft\Edge\NativeMessagingHosts\dogauthentication").'(default)'
```

### 撤销

```powershell
Remove-Item "HKCU:\SOFTWARE\Microsoft\Edge\NativeMessagingHosts" -Recurse -Force
```

> 若原厂清单里的 `path` 写的是相对路径（如 `"path": "doghost.exe"`），Chromium 会相对清单文件所在目录解析，无需改。

## 四、验证是否真的通了

1. 打开目标业务系统页面（如网签 / 备案系统登录页，需插好加密狗）
2. 触发需要加密狗认证的操作
3. 正常表现：读到狗信息、完成认证

排查用：打开扩展管理页 → 该扩展的 **Service Worker / 检查视图**，看 Console 是否有：

| 报错 | 含义 | 处理 |
|------|------|------|
| `Specified native messaging host not found` | 浏览器找不到宿主注册项 | 做第三节的注册表；确认路径文件存在 |
| `Access to the specified native messaging host is forbidden` | 扩展 ID 不在 `allowed_origins` 白名单 | 核对扩展 ID 是否 `pkoaafc...`；核对宿主 json 的 `allowed_origins` |
| `Native host has exited` | `doghost.exe` 启动即退出 | 检查加密狗是否插好、驱动是否安装、是否被安全软件拦截 |
| 无任何报错但页面无响应 | 页面与扩展握手未发生 | 确认页面确实在 `http(s)://` 下（`file://` 与 `chrome://` 不注入内容脚本） |

## 五、常见疑问

**工具栏没有图标？**
正常。原扩展本就没有 `browser_action`，不在工具栏显示，只在扩展管理页有条目。功能由内容脚本自动挂载到所有网页。

**每次启动提示"请停用开发人员模式的扩展程序"？**
解压加载的扩展属于开发者模式，Edge 会在启动时提示，点关闭即可，不影响功能。若需彻底消除，可改用企业策略 `ExtensionInstallForcelist` 下发（需要能托管 update.xml 的内网地址）。

**Edge 大版本更新后扩展被停用？**
去 `edge://extensions/` 重新启用开关；若条目消失，重新"加载解压缩的扩展"选回仓库根目录。因为 `key` 字段在，ID 不变，宿主白名单无需重配。

**能不能打包成 .crx 双击安装？**
不能保住 ID。CRX 签名需要原作者私钥，重新签名必然换 ID，宿主白名单随即失效。解压加载是唯一能维持 ID 的路径。

**要不要把仓库目录挪走？**
ID 由 `key` 字段决定，与路径无关，可以随意移动或复制到其他机器。但**不要删除或修改 `key` 字段**。
