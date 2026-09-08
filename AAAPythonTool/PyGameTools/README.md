# PyGameTools

Windows 桌面工具，用来从安卓手机提取已安装的 APK（提包），再反编译、替换资源、改应用信息、回编译并签名。

适合自己的渠道包、测试包、Unity 游戏资源替换。只处理你有权修改和备份的安装包。

## 能做什么

| 页签 | 功能 |
| --- | --- |
| **提包** | USB / 无线 ADB 连接手机，列出已装应用，提取 APK（含 AAB 分包合并、OBB） |
| **改包** | 反编译 → 替换 `res` / `assets` / `lib/*.so` → 可选改包名、应用名、游戏 id、渠道号 → 回编译签名 |

额外能力：

- 回编译 **DebugApk**（`android:debuggable=true` + 测试签名），方便接调试器
- Unity 包可勾选 **强制关闭 Vulkan**，启动时改走 OpenGL ES（`-force-gles`）
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

产物：`output/pulled/<包名>/<包名>.apk`，同目录保留原始分包。

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
3. 点 **打开目录，替换游戏资源**，替换 `res`、`assets`、`lib/*.so` 等
4. 需要时填写游戏 id、渠道号、包名、应用名
5. 点 **回编译 apk** 或 **回编译 DebugApk**

产物在 `output/`。

### 回编译时会改什么

| 填写项 | 行为 |
| --- | --- |
| 包名 | 改 `AndroidManifest.xml` 的 `package`，并写进 `apktool.yml` 的 `renameManifestPackage` |
| 应用名 | 改 `res/values*/strings.xml` 的 `app_name`，以及清单里的硬编码 label |
| 游戏 id / 渠道号 | 尝试改常见 `meta-data`，并写入 `assets/game_info.json` |
| DebugApk | 清单加 `android:debuggable="true"`，用 debug 证书签名 |
| 强制关闭 Vulkan | 仅 Unity：smali 注入 `-force-gles`，改 `boot.config`，并把 Vulkan `uses-feature` 标成非必需 |

没有填的项不会强行改。

---

## 推荐工作流

```text
手机打开目标游戏
    → 提包（合并分包 + OBB）
    → 改包页反编译
    → 替换 assets / so
    → 回编译（测试包用 DebugApk）
    → adb install -r output\xxx.apk
```

覆盖安装要求：**包名相同且签名相同**。商店原包是正式签名，本工具产出是测试签名，一般要先卸载原包，或改一个新包名并列安装。

## 常见问题

**刷新设备是空的**  
没授权 USB 调试，或驱动没装好。手机通知栏点允许，换数据线或口再试。

**列表里没有目标应用**  
取消「仅第三方应用」后再刷新。系统预装应用也在这里。

**提取后缺 so、闪退**  
确认勾选了「合并分包」。`split_config.arm64_v8a.apk` 里才有 64 位库。

**回编译失败**  
看日志区 apktool 报错。常见原因是手动改坏了 XML，或资源名冲突。

**安装提示签名冲突**  
测试签名无法覆盖正式包，先卸载原应用，或改包名。

**Unity 仍走 Vulkan / 黑屏**  
勾选「强制关闭 Vulkan」后再回编译。不是 Unity 的包这个选项无效。

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
