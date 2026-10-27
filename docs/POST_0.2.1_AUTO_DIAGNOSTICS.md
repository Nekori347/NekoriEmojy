# T-07 自动上下文与日志生命周期

2026-10-24，dev/post-0.2.1，接管22cb2b3，源码2289e01。T-07/#35已机器验证待人工；W-03/#7仅自动诊断准备，未修复或复现Win10视觉延迟。W-01/#8及七处未提交实验未编辑。

## 复用与新增

保留44d7208/168289e的sys.excepthook、threading.excepthook、Qt线程可到达Python异常、faulthandler独立匿名管道写入进程、脱敏ZIP及设置中原查看/导出入口。任务失败仍记录脱敏身份/阶段/计数，不记录错误消息里的资源内容。没有新增按钮、调试开关、上传、全局鼠标Hook或高频监控。

新增固定64条进程内deque，事件只含单调时间、内部事件码、角色/状态及数值。记录启动/正常退出、主要窗口显示隐藏及恢复、设置/快速面板/QQ工具生命周期、任务状态变化、可捕获异常和受限拖动摘要。排除图片预览、菜单及逐次输入。不记录窗口标题、资源文件名、完整路径、剪贴板、聊天或配置原文。

异常/任务错误把有限上下文加入原Python轮转日志；启动和关键窗口环境变化保存小型环境快照；普通事件留内存。原导出ZIP的environment.json追加runtime_context，直接读取环形缓冲，不先生成另一份日志。导出仍有原脱敏、取消和原子写入，不收集Library。

## 存储和回收

- 正常路径：%LOCALAPPDATA%/NekoriEmojy/diagnostics；NEKORI_APP_DATA覆盖时为其diagnostics子目录。固定Demo实际为F:/[2]Ai/NekoriEmojy/DevData/Demo/data/app/diagnostics。
- Python：exceptions.log、exceptions.log.1、exceptions.log.2；各≤512KiB，单条≤16KiB。原生：最多两个fatal-YYYYMMDD-HHMMSS-PID.log，各≤512KiB，超额管道仍排空。共五份受管理日志≤2.5MiB，上下文和环境没有额外预算。
- 最长14天按文件段mtime判断；启动、原日志轮转、运行期间每24小时维护一次。活跃Python段先关闭并轮转再回收过期段；当前原生写入段不删除。活跃段和未落盘内容不承诺14天全量留存；容量可以提前淘汰。
- 仅处理三个确定Python文件名及严格原生文件名模式；未知文件、符号链接、其它目录内容、用户导出的ZIP不清理。清理PermissionError等不会阻断启动；不可删除或磁盘故障时无法保证成功回收，正常情况下硬预算有效。没有每分钟扫描或日志数据库。

## 窗口证据及限制

应用入口使用DiagnosticApplication和被动过滤器，主窗口业务/移动/缩放/材质算法不变。基本环境包括版本、可取得的源码构建SHA、Windows版本/Build、Python/PySide6/qframelesswindow实际版本、窗口角色/类型/状态、nativeMaterial、DPI及缩放；无显示器序号或用户身份。打包成品无额外构建标识时仅标packaged，不伪造SHA。

使用[WM_ENTERSIZEMOVE](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-entersizemove) / [WM_EXITSIZEMOVE](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-exitsizemove)界定尺寸/移动循环。当前Qt过滤入口未稳定暴露WM_MOVING，因此用循环内顶层Qt Move且无Resize分类为移动；其它循环只计未分类数，不猜测为拖动。

会话内只用单调计时/标量计数；不读坐标、不写盘、不构造JSON、不遍历控件。Qt notify仅测顶层Move/Resize/Paint同步分发最大耗时。相关原生命中过滤、非客户计算、位置消息为**观测次数**，可能含Qt分发重复，不冒充材质/Mask API调用次数；当前不测这些函数体成本。

结束后异步整理小摘要：duration_ms、max_dispatch_ms、qt_dispatches、native_events、hit_tests、nc_calculations、position_changes。每进程只保存最早3条正常摘要；其余仅保留sessions/unclassified_loops/max_dispatch_ms聚合。顶层分发≥100ms视为应用侧慢事件，异常摘要最多每小时一条，仍使用原日志预算。

这些信息不等于Win32全部处理成本、DWM合成延迟、系统输入延迟或鼠标与窗口视觉距离。无原生循环边界或Qt Move的路径无法得到拖动摘要；混合恢复/缩放循环不强行分类。没有ETW/WPR/WPA，也不能以正常应用耗时否认Win10用户反馈。

## 验证

- tests/test_diagnostic_lifecycle.py、test_crash_evidence.py、test_diagnostic_export.py、test_wpf_import.py共19项通过；最后回收/分类调整后生命周期4项重验通过，不重复计数。
- 覆盖环形上限、故障上下文/隐私、14天封闭段、活跃段先轮转、容量优先、活跃原生文件与旧文件淘汰、删除失败、ZIP不误删、已有超大Unicode日志/原生管道上限、异常退出后真实堆栈、用户导出与取消及任务反馈。
- Win11独立Qt窗口实际接收受控Win32生命周期消息、窗口移动/最小化/恢复/隐藏及ZIP输出。不是物理鼠标拖动，也不是Win10复现。证据DevData/t07-lifecycle/result.json、report.zip。10000次普通Qt事件分发三组中位对照约43.76→68.75ms，即新增约2.50µs/事件；受控会话顶层最大约0.053ms。微基准不构成实际拖动视觉验收。
- 进程突然终止时内存上下文可能丢失；原生管道/faulthandler继续独立保存可取得的线程栈，不保证强杀/断电/故障处理器未运行/写入端故障的证据，不生成minidump或恢复进程。未构建验证冻结包，未测试Win10 Enterprise LTSC 21H2。

固定Demo继续原入口与持续数据，重启核对120资源/54分类/413混排及完整顺序。#35/#7/#37同步待人工；#7只自动诊断准备，Issue不关闭、不勾选。不Push/发布，不继续W-01/W-03功能修复或其它工作包。
