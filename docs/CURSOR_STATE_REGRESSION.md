# 按钮边缘光标瞬变定向修复 · 2026-10-27

基线941534a，dev/post-0.2.1。源码d584c52、4ef4037；本轮仅客户区光标消息责任，不改变按钮视觉、通知叠层、Tooltip文字或缩放命中算法。最终记录HEAD见CURRENT/#37。维护者在恢复正常Demo后反馈“测试正常”，仍不将有限体验等同于完整系统/DPI矩阵验收。

## 已确认根因

共用NekoriWindow.nativeEvent原先在所有WM_SETCURSOR且LOWORD(lParam)==HTCLIENT时直接SetCursor(IDC_ARROW)，并继续向下处理。该代码来自此前修复缩放光标残留的路径，范围覆盖整个客户区，并非只作用于边框。ButtonPaint等控件本来明确设置PointingHandCursor；Qt进入事件先应用控件光标，随后宿主又设箭头，造成短暂手形后恢复箭头。没有证据将其归因于#60或通知布局。

真实旧Demo有界记录：Win11当前会话标准箭头句柄65541、手形65569；侧栏排序的Qt属性持续PointingHandCursor，overrideCursor为空，原生宿主调用前65569、请求65541、调用后65541。17个命中手形控件的稳定采样中3次为手形、14次为箭头；同轮普通工具/设置/生成弹窗也记录到Qt手形与原生箭头不一致。句柄数值只代表此次会话，不是跨系统固定身份。采集包含屏幕坐标、命中父链、Qt光标、override、Enter/Leave/HoverMove/CursorChange及几何/可见性，原始记录只留私有DevData，不进入提交或Issue。

## 最小修改

- d584c52删除宿主客户区强制LoadCursor/SetCursor箭头，不改变ButtonPaint、TransparentToolButton、TooltipFilter或各按钮自身光标。
- 4ef4037在同一现有nativeEvent分支对HTCLIENT返回handled/TRUE，保留Qt已解析的客户区光标，避免Windows继续使用原生窗口类光标覆盖；不自行选择手形/箭头，不调用全局override，不在mouseMove中设置光标。
- 非客户区、缩放边缘及其它原生消息仍走既有处理。客户端光标更新、链接、文本输入、拖动及应用override仍由Qt负责。没有增加轮询、Hook、延迟补偿或新输入框架。

依据：[Microsoft WM_SETCURSOR](https://learn.microsoft.com/en-us/windows/win32/menurc/wm-setcursor)明确HTCLIENT、父级处理与TRUE停止后续处理；[Qt 6.11.2 QWindowsCursor](https://github.com/qt/qtbase/blob/v6.11.2/src/plugins/platforms/windows/qwindowscursor.cpp)、[QWindowsWindow::applyCursor](https://github.com/qt/qtbase/blob/v6.11.2/src/plugins/platforms/windows/qwindowswindow.cpp)对应Qt窗口光标及override的应用路径。未升级或修改依赖。

## 验证事实与限制

- 新回归先在旧代码失败，捕获真实nativeEvent调用SetCursor(65541)。最终测试覆盖手形、IBeam及应用Wait override，客户区停止默认处理且不改光标，HTLEFT仍委派原后端。
- 最终37项直接相邻检查通过：tests/test_client_cursor.py、test_shared_interaction_lifecycle.py、test_tooltip_rendering.py、test_notification_interaction.py；保留通知叠层/计时及Hover/Focus规则。前阶段13项窗口/原生子窗口机制检查通过，但不冒充最终完整物理缩放验收，W02仍暂停。
- 实际Demo使用Windows鼠标移动，覆盖侧栏、普通工具、标题按钮、Tag控制、设置及生成弹窗；方向往返、边缘/中心、Tooltip及按压均有采集。移除重置后侧栏记录30个手形命中均保持65569；标题栏普通箭头及相邻顶边SizeNS有实窗记录。
- 其它入口的自动采集出现不一致、原生释放与Qt按压状态未同步，以及实际指针偏离预定路径，相关失败没有记为通过。首次输入不可用、反复激活、以及采集条件变化均只作为私有诊断记录，不能推出产品全局点击或特殊光标已经回归，也不能宣称全入口自动验收通过。
- 自动异常退出时生成的模态弹窗没有被清理，其确认/取消测试按钮未绑定关闭，导致维护者无法测试。这是本轮诊断清理缺陷，不是图库数据损坏或产品新业务要求。已通过固定脚本正常停止并以无测试PYTHONPATH重启；禁用私有sitecustomize入口，不再自动采集或移动鼠标。
- 恢复正常Demo后维护者反馈“测试正常”。记录这一人工反馈；没有据此推断其逐项验过所有按钮、链接、输入、拖动或DPI组合。当前真实桌面修复反馈正常，完整特殊光标矩阵、150%及其它系统仍未完整验收，不继续无限自动采样。

## 工程保护与交接

源码仅fluent_ui/window_shell.py及tests/test_client_cursor.py。window_shell属于受保护文件：只暂存HEAD派生的客户区光标差异；其余实验未混入。对七文件做哈希/重建核对，插回旧光标分支即逐字节匹配原实验文件，其余六文件哈希不变，原换行方式保留。没有reset/stash/覆盖实验。

正常固定Demo运行源码4ef4037，PID77344；后续记录提交仅文档。全部7表逐行与原快照相同：132资源、54分类、433混排、recent15、meta6、features132、checkpoint0。正式版、原Library/Suzu未操作；W01实验保留、W02暂停、W03未启用。无Push/打包/发布，不关闭议题。停止本轮修复，保留人工验收边界。
