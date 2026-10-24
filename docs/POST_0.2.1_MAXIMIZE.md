# 窗口最大化与还原：#57

2026-10-24；接管 `636109b`，源码与回归提交 `da33e08`。独立窗口宿主问题；已实现、Windows 11 机器验证，待固定 Demo 人工验收。不是 W-01 或 W-03 的完成证据。

## 复现及版本对照

主窗口、设置和 ToolWindow 冷启动时最大化/还原正常。**关闭窗口→重新打开→最大化**是此前漏掉的有效触发条件。

同机相同隔离数据，分别只读载入 v0.2.1 和接管 HEAD 的 materials/window_shell/main_window，复现背景铺满屏幕但内容留在左上角旧尺寸。不是完整发布安装包对照；业务模块及依赖使用当前开发环境。三模块版本差异仅 W-02 `f6fc10f` 的宿主修改，未应用 W-03 候选。

测得 Qt isMaximized 与 Win32 IsZoomed 均为真，Qt 内部内容几何也已经放大；所以仅检查 geometry 或 QWidget.grab 不足以证明屏幕正确。此轮使用 Windows 桌面截图核对实际呈现。

## 已确认原因与最小修正

1. qframelesswindow 构造过程中已经创建 HWND，随后才设置 WA_TranslucentBackground。第一次 native surface 的 alpha=-1；关闭重开后变为 alpha=8，原生 WS_EX_LAYERED 从无变为有，呈现路径发生切换。原生背景放大、Qt 内容几何放大，但实际屏幕仍保留旧尺寸表面。改为保留首次创建的 surface 方式，删除这个过晚的属性设置；不改变原生 Acrylic、圆角、paintEvent 或窗口移动机制。
2. 重建 HWND 还会丢失上游首次初始化设置的 WS_CAPTION。W-02 已保留 WS_THICKFRAME，却没有完整保留原生边框尺寸合同。复用原 WinIdChange/WM_STYLECHANGING 入口同时保留两者，客户区与 Qt 几何重新一致。补齐 caption 单独不能修复视觉残留。

隔离对照中：仅补边框、提前启用 Alpha、改 Qt 状态切换、仅避开重复 opacity 设置、主动 repaint，均不足以解决实际屏幕残留；未将这些试验加入源码。最终只采用上述两项。没有增加延时、resize 重试、重绘循环或新的窗口状态机。

Qt 对已创建窗口晚设 Alpha 的处理依据：[Qt 6.11.2 QWidget 源码 updateIsTranslucent](https://github.com/qt/qtbase/blob/v6.11.2/src/widgets/kernel/qwidget.cpp)。仅用作初始化顺序解释；并未据此声称已定位 DWM 内部全部机制。

## 验证范围

- 本机 Windows 11、PySide6 6.11.2、qframelesswindow 0.8.2，当前主显示器 100% 缩放、可用区域 3392×1440。
- 真实开发 Demo 主窗口、设置、Telegram ToolWindow：首次和关闭重开后最大化/还原；恢复原位置尺寸，客户区/Qt/标题栏/内容同步。共 21 个定向状态快照，无断言失败，包含托盘隐藏恢复和标题栏双击。
- 每种窗口还原后八方向 WM_NCHITTEST 正确，普通尺寸调整后标题栏同步。是原生命中检查及程序化尺寸调整，不冒称重新做完物理鼠标八方向缩放验收。
- 两项 Windows Qt 回归测试通过：重开后的最大化/还原与内容尺寸；双击、隐藏恢复、八方向命中。测试从暂存区加载正式模块，排除 W-01 未提交实验。
- 桌面实际截图确认修前旧尺寸残留、修后完整内容铺开。正常尺寸下主窗口及派生窗口仍有 Acrylic/透明背景与轻量圆角，未见明显视觉回归；API 接受状态不是唯一视觉证据。
- 未操作系统鼠标，控件测试使用 QTest 并由实际 Win32 状态转换执行；完整物理鼠标/系统快捷键、其它 DPI/显示器、安装包运行形态仍待验收。Windows 10 圆角及材质未知。

专项证据：项目根目录 DevData/maximize-check，release/head 为修前对照，native_surface/final_probe 为最小修正验证；桌面截图可能含用户其它窗口，仅留本地，不上传 Issue。临时试验不是新的主 Demo。

## 保护与交付

用户明确批准仅将与 W-01 实验重合的 WA_TranslucentBackground 删除独立归入 #57。提交前审阅暂存区，仅有该宿主修正及独立回归测试；其余实验不混入。

保留七个原脏文件；其中宿主原实验仅上述获准删除行被正式吸收，其它实验内容保持。T-07 不改，W-03 补丁未应用。没有改 MainWindow 几何恢复逻辑，没有新增或删除其定时器；没有改图库、主题及数据模型。

固定入口仍为 DevData/Demo/Start-Demo.cmd，持续数据 DevData/Demo/data 不清空。#57、#37 保持 Open/待人工验收，不 Push、不发布。
