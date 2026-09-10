# PyGameTools

Windows 桌面工具，用来从安卓手机提取已安装的 APK（提包），再反编译、替换资源、改应用信息、回编译并签名。

适合自己的渠道包、测试包、Unity 游戏资源替换。只处理你有权修改和备份的安装包。

## 能做什么

| 页签 | 功能 |
| --- | --- |
| **提包** | USB / 无线 ADB 连接手机，列出已装应用，提取 APK（含 AAB 分包合并、OBB、应用数据） |
| **改包** | 反编译 → 合并应用数据 → 替换 `res` / `assets` / `lib/*.so` → 可选改包名、应用名、游戏 id、渠道号 → 回编译签名 → 推送 Yoo 缓存到手机 |

额外能力：

- **壳识别**：拖入 / 提取 / 反编译时扫描 so、清单、资源路径，标出常见加固、乐变、引擎
- 回编译 **DebugApk**（`android:debuggable=true` + 测试签名），方便接调试器
- Unity 包可勾选 **强制关闭 Vulkan**，启动时改走 OpenGL ES（`-force-gles`）
- 合并时可选 **超过 4GB 跳过 YooAsset 缓存**，装机后再 **推送缓存到手机**（避免 ZIP/APK 超过 4GB 签不了名）
- **推送 GLES 配置**：把关闭 Vulkan 的 `boot.config` 盖到手机 `files`，避免第二次启动又走 Vulkan
- **清理登录缓存**：只删私有目录里登录相关 SharedPreferences，不动 `files/yoo` 热更资源
- 首次运行自动下载 apktool、uber-apk-signer、便携 JRE、platform-tools（adb）

## 环境要求

- Windows 10 / 11 64 位
- 官方 Python 3.10+（带 tkinter；不要用精简/嵌入版）
- 提包时：安卓手机 + USB 数据线（或同一 Wi-Fi 无线调试）
- **不需要 Root**

Java 不是必须自己装。本机没有 JDK 时，工具会下载便携 JRE 17。

## 安装与启动

第一次：

1. 双击 `一键安装.bat`（会装缺失的 Python / 依赖 / 工具链）
2. 再双击 `启动.bat`

换电脑：拷贝整个 `PyGameTools` 文件夹，再跑一次 `一键安装.bat`。已下载的文件会跳过。

命令行安装：

```bat
python PyGameTools.py --setup
```

## 目录说明

```text
PyGameTools/
  PyGameTools.py      主程序
  启动.bat
  一键安装.bat
  tools/              apktool、签名器、JRE、adb（自动下载）
  work/               反编译后的工程目录
  output/             回编译产物
    pulled/包名/      从手机提出来的 APK / 分包 / OBB
    pulled/包名/appdata/   应用数据（files / 热更 / Yoo 缓存）
```

---

## 提包：已安装的 APK 怎么拿出来

安装包并没有「消失」，只是在手机内部目录里。Package Manager 知道每条安装记录对应哪些文件。

### 原理

1. 电脑通过 **ADB** 连上已授权的手机。
2. `pm list packages -f` 列出包名和当前安装路径。
3. `pm path <包名>` 返回该应用全部安装文件。用户应用一般在：

   ```text
   /data/app/~~xxxx/com.xxx.game-xxxx/base.apk
   ```

4. `adb pull` 把文件拷到电脑。系统开放了这条查询接口，所以 **不必 Root，也不用去翻 `/data` 目录**。

对应命令：

```bat
adb devices
adb shell pm list packages -f -3
adb shell pm path com.example.game
adb pull /data/app/.../base.apk D:\out\base.apk
```

### 为什么会有好几个 apk

应用商店现在大多下发 **AAB**，手机上拆成多个文件：

| 文件 | 内容 |
| --- | --- |
| `base.apk` | 主程序、清单、大部分资源 |
| `split_config.arm64_v8a.apk` 等 | 对应 CPU 的 `.so` |
| `split_config.xxhdpi.apk` 等 | 对应分辨率的资源 |

只拉 `base.apk`，回编译后容易缺 so 或缺图。提包页默认把全部分包拉下来，再按 zip 合并成一个完整 APK（后写入的分包补齐 base 里没有的文件）。

部分老游戏还有扩展包，在：

```text
/sdcard/Android/obb/<包名>/
```

工具可一并拉到 `output/pulled/<包名>/obb/`。

### 手机怎么开调试

1. **设置 → 关于手机**，连续点击「版本号」，打开开发者选项
2. 打开 **USB 调试**，用数据线连电脑，手机弹出授权时点允许
3. 小米 / OPPO / vivo / 华为再打开 **USB 调试（安全设置）**
4. 无线：开发者选项 → 无线调试，在工具里填 `IP:端口` 点连接

### 提包页怎么用

1. 打开 **提包** 页签，点 **刷新设备**
2. 点 **刷新应用列表**（默认只看第三方应用）
3. 搜索包名，或先在手机里打开目标 App，再点 **定位前台应用 / 提取前台应用**
4. 双击列表，或点 **提取选中应用**

默认选项：

- 合并分包为单个 APK
- 同时提取 OBB
- 提取后自动选入「改包」页，可直接反编译

可选：**同时提取应用数据（files / 热更缓存）**。勾选后会再拉：

```text
/sdcard/Android/data/<包名>/files
/sdcard/Android/data/<包名>/cache
```

以及目录名带 lebian / update / patch 等的热更文件夹。应用若是 DebugApk（debuggable），还会尝试用 `run-as` 拉 `/data/data/<包名>/` 下的 files、cache。商店原包的私有目录拉不下来。

目录可能很大，默认不勾。Android 11+ 有的机型会拦截 `Android/data`，日志里会提示。

产物：`output/pulled/<包名>/<包名>.apk`，同目录保留原始分包；应用数据在 `appdata/`。

### 应用数据和 APK 怎么合并

热更一般**不会改安装包**，完整资源在 `appdata/files/`。乐变的对应关系是：

```text
手机  Android/data/<包名>/files/xxx
  →   反编译工程  assets/xxx
```

在改包页：

1. 先反编译（或点合并时选「先反编译再合并」）
2. 点 **合并应用数据**
3. 工具会自动找 `提包目录/包名/appdata`；找不到再让你选 `appdata` 或 `files`
4. 把 `files` 填进 `work/<apk名>/assets/`（占位小文件不会盖掉已有大文件；`lib/<abi>/*.so` 会写到工程的 lib）
5. 再点回编译

`cache`、临时文件、apk/dex 不会打进包。差分补丁（xdelta）不是散文件，这条路径合不进去。

### 超过 4GB 时怎么取舍（YooAsset）

普通 ZIP/APK 上限 **4GB**。把整份热更缓存打进包会超过这个上限，签名器报 `Malformed ZIP Central Directory` / `offset 4294967295`，装不了。

YooAsset 的 `CacheBundleFiles` / `CacheRawFiles` 本来就在手机 `files/yoo/`，游戏也从那里读，**不必、也不该打进 APK**。包内只需内置的 `assets/yoo/<分包>/*.bundle`。

改包页默认勾选 **「合并超过 4GB 时跳过 YooAsset 缓存」**：

1. 合并前预估：工程现有 + 待合并 + 缓存
2. **将超过 4GB** 才跳过上述缓存目录；没超则全部合并
3. 取消勾选 = 强制全量合并；超过 4GB 时无法签名
4. 回编译时若仍勾着、且工程已经大于 4GB，会再移出这些缓存目录

跳过后：先装 APK（至少启动一次，让系统建好目录），再点 **「推送缓存到手机」**。

### 推送缓存到手机

按钮在 **改包** 页，和「合并应用数据」同一行。

**手机在「提包」页选，改包页没有设备下拉框。**

1. 打开 **提包**，点 **刷新设备**，在左上角 **设备** 里选目标机
2. 回到 **改包**，确认「包名」栏（改过包名就填新包名）
3. 点 **推送缓存到手机**

推送目标：

```text
/sdcard/Android/data/<包名>/files/yoo
```

本地来源是提包得到的 `output/pulled/<包名>/appdata/files/yoo`（或你手动选的 appdata）。只推 `CacheBundleFiles` / `CacheRawFiles`。

若提包页没选过设备，会用 `adb devices` 里第一台已授权的手机；一台都没有会提示先去提包页刷新。多机务必先选对设备再推。Android 11+ 有的机型会拦 `Android/data` 写入，需先启动过游戏，或用系统文件管理授权。

手机上已经有这份缓存、只是覆盖安装同签名 Debug 包时，**一般不用再推**。

### 推送 GLES 配置（覆盖二次 Vulkan）

按钮在 **改包** 页，和「推送缓存到手机」同一行。设备同样在 **提包** 页「设备」里选。

第一次能挂 RenderDoc、第二次卡切换界面，常见原因是乐变用本地 `files/bin/Data/boot.config` 盖住包内配置，第二次又选了 Vulkan。此功能会：

1. 给工程里的 `assets/bin/Data/boot.config` 补上 `android-disable-vulkan=1`、`force-gles=1`（没有则只生成这两行推上去）
2. 推到 `/sdcard/Android/data/<包名>/files/bin/Data/boot.config`
3. Debug 包会尝试 `run-as` 清掉名称里带 vulkan/graphics 的 SharedPreferences
4. `am force-stop` 应用

之后请从 **RenderDoc 重新启动**，不要只点桌面图标。包名用改包页「包名」（改过就填新包名）。

这不能代替回编译时勾选「强制关闭 Vulkan」；包内没有 `-force-gles` 时，有的版本仍会在初始化选 Vulkan。

### 清理登录缓存

按钮在 **改包** 页。设备在 **提包** 页选。需要已装 **DebugApk**（`run-as`）。

桌面第二次能进、RenderDoc 第二次卡在登录切换时，多半是途游自动登录 + RenderDoc 从启动注入撞车。此功能只删登录相关文件，**不会删热更资源**：

| 会删 | 不会删 |
| --- | --- |
| `/data/data/<包名>/shared_prefs/` 里名称带 login / token / tuyoo / account / session 等 | `files/yoo`（私有和 `Android/data` 两处） |
| `files/` **根目录**下同名规则的散文件 | `files/bin`、`files/lebian`、整个 `Android/data` |

不会执行 `rm -rf files`，也不会用系统「清除数据」。清完日志会确认 `yoo` 还在。然后用 RenderDoc Launch，走回第一次那种手动登录。

---

## 改包：反编译、换资源、回编译

### 原理

APK 本质是带固定结构的 zip：

```text
AndroidManifest.xml    二进制清单（包名、权限、组件）
classes*.dex           Java/Kotlin 字节码
lib/<abi>/*.so         原生库（Unity 的 libunity / il2cpp 等）
assets/                流式资源（Unity 常见 assets/bin/Data）
res/                   编译后的 Android 资源
resources.arsc
META-INF/              签名
```

[Apktool](https://apktool.org/) 把清单和资源解码成可编辑的 XML / 目录；`assets`、`lib` 按原样展开。改完后再编码回 APK。

新包必须重新签名，系统才允许安装。本工具用 [uber-apk-signer](https://github.com/patrickfav/uber-apk-signer) 打 **测试签名**（debug keystore）。测试签名的包可以装到自己的测试机，不能覆盖商店原包（签名不一致）。

### 改包页怎么用

1. 把 APK 拖进下方日志区，或从提包页自动带入
2. 点 **反编译 apk**，工程在 `work/<apk文件名>/`
3. 有热更数据时点 **合并应用数据**（可勾选超过 4GB 跳过 Yoo 缓存），或手动打开目录替换 `res` / `assets` / `lib/*.so`
4. 需要时填写游戏 id、渠道号、包名、应用名
5. 点 **回编译 apk** 或 **回编译 DebugApk**
6. 若合并时跳过了缓存：装机并启动一次后，到提包页选好手机，再点 **推送缓存到手机**
7. 第二次启动又走 Vulkan：同一台手机上点 **推送 GLES 配置**
8. RenderDoc 第二次卡在登录切换（桌面能进）：点 **清理登录缓存**，再从 RenderDoc 启动

产物在 `output/`。

### 回编译时会改什么

| 填写项 | 行为 |
| --- | --- |
| 包名 | 改 `AndroidManifest.xml` 的 `package`，并写进 `apktool.yml` 的 `renameManifestPackage` |
| 应用名 | 改 `res/values*/strings.xml` 的 `app_name`，以及清单里的硬编码 label |
| 游戏 id / 渠道号 | 尝试改常见 `meta-data`，并写入 `assets/game_info.json` |
| DebugApk | 清单加 `android:debuggable="true"`，用 debug 证书签名 |
| 强制关闭 Vulkan | 仅 Unity：smali 注入 `-force-gles`，改 `boot.config`，并把 Vulkan `uses-feature` 标成非必需 |
| 关闭乐变热更（可选） | 改 `assets/lebian/globalSettings.xml`：关掉 `use_regeng`、启动查新、边玩边下。**不关** `use_lebian`，SDK 仍在 |
| 超过 4GB 跳过 Yoo 缓存（默认开） | 合并前预估体积；将超 4GB 时不把 `CacheBundleFiles` / `CacheRawFiles` 打进 APK |

没有填的项不会强行改。勾选关闭乐变热更前，应先合并应用数据，否则包内可能缺热更资源。

乐变把 `Android/data/<包名>/files/xxx` 当成 `assets/xxx` 来读。关热更只表示不再去拉新包，**已经落在 files 里的同路径文件仍会盖住 APK**。要减乐变干扰又保留玩法资源：留下 `files/yoo`，清掉会撞 `assets` 的本地文件（常见是 `files/lebian`、以及乐变下过的 `bin` 等）。不要整目录清空 `Android/data`，否则 Yoo 缓存也没了。

部分乐变版本要求 `use_regeng` 和 `use_streaming` 不能同时为 false，否则 SDK 可能报错。当前选项两个都会关；若启动直接报开关错误，需要再权衡。

---

## 推荐工作流

```text
手机打开目标游戏并完成热更
    → 提包页：刷新设备并选好手机（合并分包 + OBB，勾选应用数据）
    → 改包页反编译 → 合并应用数据（默认：将超 4GB 则跳过 Yoo 缓存）
    → 需要冻结热更时勾选「关闭乐变热更」
    → 替换其它 assets / so
    → 回编译（测试包用 DebugApk）
    → 安装（见下）
    → 若跳过了缓存：提包页确认设备 → 改包页「推送缓存到手机」
```

### 安装和旧数据

覆盖安装要求：**包名相同且签名相同**。商店原包是正式签名，本工具是测试签名，**不能直接覆盖商店包**，要先卸载或改新包名并列安装。

| 情况 | 结果 |
| --- | --- |
| 商店原包上直接装 Debug | 装不上（签名冲突） |
| 本工具上一版 Debug 上再装（同一把测试证书） | 能覆盖；**`Android/data` 不会清**，旧 files / Yoo 缓存都在 |
| 先卸载再装（没改包名） | 能装；`files` 是否还在看系统，很多机子会删掉 |
| 改了新包名 | 旧缓存不会跟过来，要推到 `Android/data/<新包名>/files/yoo` |

同签名覆盖安装时：Yoo 缓存一般还在，**不必再推**。但乐变落在 `files` 里的旧配置/分包也会留下，可能盖住新 APK 里刚关的热更开关。这时不要全清 data，只去掉会撞 `assets` 的本地文件，留下 `files/yoo`。

## 常见问题

**刷新设备是空的**  
没授权 USB 调试，或驱动没装好。手机通知栏点允许，换数据线或口再试。

**列表里没有目标应用**  
取消「仅第三方应用」后再刷新。系统预装应用也在这里。

**提取后缺 so、闪退**  
确认勾选了「合并分包」。`split_config.arm64_v8a.apk` 里才有 64 位库。

**勾了应用数据却是空的 / 无权限**  
先在手机里把游戏打开并热更完。Android 11+ 常拦截 `Android/data`：用系统文件管理打开该目录拷到电脑，或先装 DebugApk 再提（可用 `run-as` 拉私有 files/cache）。

**回编译失败**  
看日志区 apktool 报错。常见原因是手动改坏了 XML，或资源名冲突。

**签名报 Malformed ZIP / offset 4294967295**  
未签名 APK 超过了 4GB。勾选「合并超过 4GB 时跳过 YooAsset 缓存」再合并，把 `CacheBundleFiles` / `CacheRawFiles` 留在手机 `files/yoo`，用「推送缓存到手机」补回去。

**签名报 could not align / could not execute zipalign**  
回编译已经成功，卡在 Windows 自带的 `zipalign`：它对超过 **2GB** 的 APK 会因 `ftell` 用 32 位 long 而失败（你的包大约 3.3GB 就会中招）。工具会自动跳过对齐再签名。侧载、调试、RenderDoc 都能装；只有上架商店才必须对齐。再点一次回编译即可。

**推送缓存推错手机 / 找不到设备**  
改包页没有选设备。到 **提包** 页点「刷新设备」，在 **设备** 下拉框里选目标机，再回改包页推送。

**推送失败 / Android/data 无权限**  
先装好 APK 并启动一次。Android 11+ 常拦截该目录；可用系统文件管理授权，或把 `appdata/files/yoo` 手动拷到手机对应路径。

**覆盖安装后乐变仍在查新版本 / 边玩边下**  
关热更只改了 APK 内配置。本地 `files` 里若还有旧的 `lebian` 配置或同路径资源，会盖住包内设置。留下 `files/yoo`，清掉其余会撞 `assets` 的文件。

**安装提示签名冲突**  
测试签名无法覆盖正式包，先卸载原应用，或改包名。

**Unity 仍走 Vulkan / 黑屏 / 第一次能抓帧第二次卡切换**  
勾选「强制关闭 Vulkan」后再回编译。装机后若第二次又走 Vulkan，到提包页选好手机，点「推送 GLES 配置」。若 RenderDoc 显示已是 OpenGLES 但仍卡登录切换、且桌面第二次能进，点「清理登录缓存」再从 RenderDoc 启动。不是 Unity 的包 GLES 选项无效。

**清理登录缓存会不会把资源也清掉**  
不会。只删 `shared_prefs`（以及 `files` 根目录）里带登录关键字的文件，日志里会写 `yoo` 是否还在。不要用手机「清除存储」。

**壳识别说没壳，但改不动逻辑**  
识别靠 so / 清单 / 资源路径，能覆盖国内渠道包里大部分商业加固（360、乐固、梆梆、爱加密、阿里、百度、娜迦等）。改过 so 名的私有壳、全新壳、只做混淆的包认不出来。识别不是脱壳。

## 依赖（自动获取）

| 组件 | 用途 |
| --- | --- |
| Apktool 2.9.3 | 反编译 / 回编译 |
| uber-apk-signer 1.3.0 | 签名 |
| Eclipse Temurin JRE 17 | 跑上面两个 jar |
| Android platform-tools | adb 提包 |
| tkinterdnd2 | 拖放 APK（没有也能右键选择） |

## 使用边界

只提取、修改你有权处理的安装包（自己的包、自己的测试设备）。不要用本工具传播他人的付费应用或破解授权。
