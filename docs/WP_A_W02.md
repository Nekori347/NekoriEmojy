# WP-A 小任务：W-02 / Issue #9

2026-10-21，开发分支 dev/post-0.2.1；接管 HEAD 8efb819，发布基线仍 v0.2.1 / b1788f8。本轮只交付 W-02，全部 Issue 保持开放。本次调度以 [新版计划](POST_0.2.1_HANDOFF.md) 为准，原 POST_0.2.1_PLAN.md 保留为历史需求来源。

## 已有工作与边界

| 需求 | 接管事实与结果 | 当前状态 |
|---|---|---|
| W-01 / #8 | 已调查且已有未提交源码候选。Acrylic 和 Blur 在无 DWM 圆角路径均出现矩形残边；用户明确否决早期原型。纯色背景对照中，圆角外像素由 #ff00ff 变为 #e101e1；不透明后备保持 #ff00ff。当前工作树包含不透明降级和轮廓收敛候选。 | 不纳入 W-02 提交；未人工验收，未在 Win10 实机验证，不能记为修复完成。 |
| W-02 / #9 | 已修改共享宿主；正式安装实例真实拖动 A/B 与隔离原生回归均有证据。 | 本次独立提交，待人工体验。 |
| W-03 / #7 | 读过社区报告，Win10 LTSC 21H2，录屏上传失败。当前 Win11 的 HWND 标题栏拖动采样不能替代该环境。 | 未形成独立修复，待复现。 |

接管时 main_window.py / materials.py / window_shell.py / test_ui_tail.py / test_window_resize.py 及新增原生测试有未提交工作。只将 window_shell.py 的 W-02 原生句柄和命中部分及相关原生测试提交；其它改动原样留在工作树。未 reset、stash、clean 或切换旧版本。

## 已确认根因

用户安装实例 C:/[1]Ruanjian/NekoriEmojy/bin/NekoriEmojy.exe（运行 PID 32168）四边四角实际命中均正确，但样式为 0x960b0000，缺少 WS_THICKFRAME。原样右边拖动 4 次位置采样，宽度始终 1000；仅临时加回该标志后，宽度连续变为 1010/1020/1030/1040。随后恢复原样式和矩形 [1238,325,2238,1211]，不修改安装文件或库。

进一步最小复现：QWidget.close() 销毁 HWND；show() 新建句柄，而 qframelesswindow 的样式初始化仅在构造时执行。旧代码从 0x96cf0008 变为 0x960b0000。Demo 初次显示或仅 hide/show 不触发这一生命周期，不能用于否定正式实例故障。

## 修复

- NekoriWindow 在 WinIdChange 时为新句柄维护原生缩放标志；只在缺失时变更样式及刷新非客户区。不在 show 后加计时补丁。
- WM_STYLECHANGING 保持同一缩放合同，覆盖 Qt 在不换 HWND 时重新写样式的路径；保留禁用缩放和全屏边界。
- 四边与四角统一用 WM_NCHITTEST 自带屏幕坐标、DPI 缩放后的热区；不再由上游读取已经移动到另一处的鼠标当前位置判定边缘。标题栏普通区域仍 HTCLIENT，沿用原生拖动链。
- 不改材质、数据格式、窗口业务、发布版本号或用户配置合同。

## 验证与人工验收

证据目录：../../DevData/post-021-wpa。

- live-installed.json / live-resize-ab.json：真实安装实例命中及临时标志对照，样式/几何已恢复。
- close-reopen-baseline.log：旧源码 close/reopen 实际销毁并重建 HWND，缩放样式丢失。
- native-baseline.log：原生回归旧实现失败；w02-only-tests.log：仅装载本次 W-02 代码、保留原材质的 3 项原生检查通过（标志重写、关闭重开、八向消息坐标）。
- w02-close-main-corners.json / w02-close-main-edges.json：独立 W-02 完整主窗关闭重开后真实四角/四边鼠标缩放。
- corners-w02-dpi150*.json：Qt 进程 150% 的实际鼠标检查；不等于 Windows 全局 150% 或混合 DPI 切屏验收。
- 已有 test_window_resize 的旧图库夹具 3 项失败，原基线夹具复跑同样失败（legacy-baseline.log）；其 _current_columns/布局模型与现有图库不符。本次不扩大修理图库测试。W-01 的旧测试修改留在工作区。

人工请重点：关闭主窗/设置窗后重新打开，四边四角缩放，最小尺寸限制，标题栏拖动与最小化/最大化/恢复，内容点击不被抢。真实 Win10、Windows 全局 150%/混合 DPI 未验证；W-01 和 W-03 不据本次缩放通过自动完成。

DevData/post-021-wpa/Start-W02.cmd 提供隔离数据的验收入口。它从固定 W-02 Git 提交加载三个窗口相关模块，使用同一 Source 与 .venv，排除仍留在工作树的 W-01 候选；不是第二个正式工程、不覆盖安装版。独立托盘提供显示主窗/设置/退出；未注册全局快捷键，不影响运行中的正式实例。
