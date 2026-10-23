# WP-H 启动体验与 G-16 分类树选中映射

2026-10-23；基点9041053，dev/post-0.2.1。本轮不重复47项历史审计。W-04/#10、W-05/#11、G-16/#28已实现、机器验证后待人工验收，Issue保持Open。

## W-04 / 06e1087

原main.py的QSharedMemory锁检测到已有进程便直接退出，未发送唤醒请求。保留共享内存锁，在同一入口增加当前用户的QLocalServer/QLocalSocket通知，复用show_main_panel及系统正常恢复/激活；不重新初始化Library，不设永久置顶或焦点重试。锁持有者先监听，窗口未就绪时仅保留一个待唤醒请求；第二进程可向Windows授权已有PID一次前台激活尝试。

显式NEKORI_APP_DATA按规范化配置路径隔离锁与通知端点，默认正式启动仍沿用原锁名。固定Demo复用同一入口；仍保留原Demo的停止控制通道。只能唤醒具有新IPC入口的实例，未升级的v0.2.1进程不因此获得新能力。

真实Windows主程序进程验证：正常显示、最小化、隐藏各再运行main.py，同一PID54556/HWND1709216恢复显示，MainWindow只初始化1次；正常退出后再次冷启动成功。非对真实用户进程注入。安装/Portable共用分发的同一主程序，轻量launcher.py转发参数至main.py；仅核对启动路径，本轮未重新构建安装包或ZIP运行成品。系统前台规则可能限制抢焦点，不承诺每次强制焦点成功。

## W-05 / ab8d2de

设置→关于新增“启动时自动检查更新”，默认开启，遵循原保存/放弃规则。首次窗口show之后以Qt事件排队启动，复用UpdateService及UpdateWorker；不在GUI线程执行HTTP，不自动下载/安装。有更新沿用已有更新中心徽标/按钮，无更新不弹窗，失败仅保留error状态，不当作确认最新版。原HTTP客户端、版本规则、渠道及摘要校验不变。

配置保存auto_update_last_attempt和auto_update_status，自动尝试（含失败）间隔24小时；手动检查不受限。状态区分checking/current/available/error/unpublished；没有发布渠道不请求。第二进程在配置/Library初始化前退出，不额外触发自动检查。退出沿用协作取消并等待正在执行的请求结束；仍受已有HTTP超时边界限制，不声称立即取消阻塞中的网络调用。

可控HTTP响应验证有更新、无更新、网络失败及未发布；检查关闭、保存/放弃/持久化、过期重查、24小时内重启、手动检查及不下载。网络替身等待期间GUI仍能显示窗口。Windows主程序第一次仅检查1次，三次唤醒不增加，冷重启24小时内0次。没有实际下载安装更新。

## G-16 / 1631934：隐藏子分类的虚线位置映射

根因：Qt对折叠隐藏的子项返回空visualRect，代理仍将空矩形转换为(16,11,2,2)的有效指示器，进而在顶部绘制悬空选中背景。现有NavigationItem拒绝空几何，折叠/展开时停止旧位置动画并同步几何；仅沿真实选中项祖先链找到可见折叠祖先，在原选中轮廓位置绘制低权重主题色虚线，无额外背景、角标、覆盖控件或业务选择模型。

以用户最新规格为准：A展开/B选中时保留B的原正常选中态；A折叠时仅A虚线。A→B→C中B折叠映射B，A再折叠映射A，展开A回到B，再展开B恢复C。点击父分类正常导航，旧虚线消失；多选继续原规则，不伪造共同父级选择。当前分类、Gallery资源投影及滚动不因折叠改变。

真实控件验证单层chevron点击、多级映射、滚动后折叠、父级直接选中、切换真实分类清理虚线；Windows主窗口截图核对展开、内层虚线、外层虚线和逐级恢复。截图DevData/startup-check/G16-tree.png、G16-nested.png、G16-collapse.png、G16-collapse_outer.png、G16-expand_outer.png、G16-expand.png。此前“只隐藏所有高亮”的候选仅保留为G16-pending历史调查，已由当前明确产品规格替代，不是交付方案。

## 验证与停止边界

- 最终30项及12个子断言通过；定向范围：tests/test_single_instance.py、test_startup_updates.py、test_tree_collapsed_selection.py、test_update_dialog.py、test_updates.py；结果见DevData/startup-check/final-tests.log。
- Windows实际Qt主窗口、独立进程：DevData/startup-check/windows-result.json、windows-owner.log；无系统鼠标占用。测试入口只在DevData，未新增产品诊断平台。W-01三份宿主模块同固定Demo读取当前Git HEAD，未使用未提交实验。
- Windows当前环境验证；打包成品、Win10、其它DPI及系统前台限制仍待相应验收，不扩大为W-01/W-03完成证据。
- 固定DevData/Demo/Start-Demo.cmd及持续data继续使用；不清空数据或排序，不Push/发布、不改正式v0.2.1，不开展其它Issue。七处原W-01实验按前后SHA256核对。
