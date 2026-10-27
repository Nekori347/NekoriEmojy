# W-01 / Issue #8：轮廓与合成面最小复现

2026-10-21，接管 `dev/post-0.2.1` / `762efdd`。**尚未修复，不交付“已修复”Demo。** 本轮保存可重复的诊断；原有五个未提交源码/测试文件保持接管状态，不将不透明后备候选提交成产品修复。W-02 已提交修复不变，W-03 未展开。

## 本轮新增证据

运行环境是 Windows 11 build 26340，屏幕 100%。显式关闭 DWM 原生圆角，用 Region 路径定位合成层；这不是 Win10 实测，也不把系统版本伪装成 Win10。

1. `DevData/post-021-wpa/w01_layers.py`：现有宿主，纯色背景对照。Region 路径下，实色背景圆角外像素为 `(255,0,255)`；开启 Acrylic 后为 `(232,143,231)`，与窗口内 `(233,149,232)` 接近。关闭非客户区渲染后相同。不是仅把正常阴影误当漏底。
2. 同一对照启用 Qt 透明属性并关闭重开，确认原生扩展样式由 `0x108` 变为 `0x80108`，真实进入 layered 路径；漏底仍存在。只在 Python 对象上设置属性不能当作原生分层已经生效。
3. 移除全部 Qt / Nekori / qframelesswindow 调用，直接创建 Win32 HWND、设置圆角 Region 和 Acrylic，仍复现矩形合成面。`GetWindowRgn` 确认 `(1,1)` 在 Region 外，`WindowFromPoint` 确认鼠标落到后面的背景窗口，但截图仍显示 Acrylic 混色。
4. 在 Acrylic 之后再调用 `SetWindowRgn` 无效。这条路径无需隐藏、恢复、主题变化或 HWND 重建即可复现，不能按 W-02 的句柄问题直接归因。

纯 Win32 对照结果：

| 条件 | Region 外像素 | 后方背景像素 | 在 Region 内 | 命中后方窗口 |
|---|---|---|---|---|
| 禁用 Acrylic | 255,255,255 | 255,255,255 | 否 | 是 |
| 启用 Acrylic | 241,242,240 | 255,255,255 | 否 | 是 |
| 启用后重新设置 Region | 241,242,240 | 255,255,255 | 否 | 是 |

输出在 `DevData/post-021-wpa/w01-native-repro/`，包括 JSON、三张真实桌面截图。纯 Win32 背景实际截图为白色；结论以实测背景像素为参照，不假定请求的背景色一定显示出来。

## 已厘清的职责与尚未解决的边界

- Qt 圆角绘制只控制 Qt 内容表面，无法据此保证 Acrylic 合成面也被裁掉。
- Region 在本机确实控制窗口形状/输入命中，但上述 Acrylic 路径仍在 Region 外绘制；不能把 Region 的正确性等同于整个合成结果正确。
- DWM 原生圆角可在适用的 Windows 11 窗口上统一裁剪最终外观，但 API 是提示，不保证实际圆角。微软明确列出 per-pixel alpha 和 Window Region 不适用原生圆角；该 API 最低系统为 build 22000。[官方说明](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners)、[支持范围](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwm_window_corner_preference)。
- 当前候选按系统版本标记 `nativeContour`，并把 Win10/透明窗口退为实色，不能满足用户此次“保留透明材质”的条件。它不是最终责任分配，也不应进入正式修复提交。

**本轮确认的是一个独立机制缺陷：Region/Qt 轮廓不能约束当前 Accent Acrylic 合成面。** 因而补 show/resize 调用或重设相同 Region 不会修好这条路径。尚不能断言所有用户反馈、所有 Windows 版本与所有生命周期回归只有这一个原因。

## 最小复现入口

在 Source 目录执行（会短暂显示三个测试窗口；不读取应用配置/资源库，不操作现有软件）：

```powershell
& .\.venv\Scripts\python.exe scripts/w01_region_repro.py
# 每个对照停留五秒，便于人工观察
& .\.venv\Scripts\python.exe scripts/w01_region_repro.py --hold 5
```

依赖工程已有 pywin32/Pillow。JSON 的 `leak_detected` 是实际像素差、Region 外点及后方窗口命中共同判断；不是 API 返回成功。其他窗口遮挡或系统不启用透明时需要人工检查截图，不能单凭未检出判定修复。

## 阻碍与停止点

现有直接 HWND Accent Acrylic + Region 组合已经能在无业务代码的窗口复现，尚无经过验证且同时保留 Acrylic、缩放、拖动和最大化的小范围替代。不能据此宣布所有 Windows 的组合都绝对不可能，也不应未经验证引入第二套合成框架或继续尝试未知标志。

下一步需要在实际反馈的 Win10 环境执行同一最小复现，确认 compositor 行为一致后，再决定是否需要一个可在合成层裁剪材质的实现。若只有 Win11 原生轮廓方案通过，也只能按该环境记录，不能关闭 W-01。已向用户询问 Win10 验证环境。

本轮没有新的产品源码修改，因此没有合并或移除旧圆角处理；接管时已有的移除/不透明候选原样保留。W-02 原提交及其八方向实际拖动证据仍有效，本轮没有重新声称八方向实测。显示/隐藏/恢复/尺寸/主题/DPI 的最终 W-01 修复验收尚未进行；Win10、系统 150% 和混合 DPI 未测试。CHANGELOG 不增加完成项，不 Push、不发布。
