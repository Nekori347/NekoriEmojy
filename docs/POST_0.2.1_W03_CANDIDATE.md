# W-03 外部Win10证据与未启用的材质候选

2026-10-24；dev/post-0.2.1，接管ae74066。候选提交b465927。**只有隔离补丁及验证被提交，没有修改当前运行源码，也没有加入正式发布计划。W-03未最终验收。**

## 外部报告核查

完整阅读D:/[4]Downl0ad/X1aZai/NekoriEmojy-Win10-拖动延迟-调查报告.md。外部为Win10 IoT Enterprise LTSC 21H2 / 19044.7807、正式安装版v0.2.1，BUILD_INFO指向6657e895526af233ae7d102070b73daf74aa7b49；本地为Win11。当前依赖PySide6 6.11.2 / qframelesswindow 0.8.2与报告相符。

同机、同窗口、同程序化负载切换Acrylic后的巨大差异，加上可恢复的材质截图对照，足以将Win10 Acrylic合成路径列为首要性能触发因素。接受为外部提供的实测证据；本轮没有原始脚本/数据文件，未独立复算数值，不要求对方重做高频移动实验。

必须收窄报告中的几个结论：

- [DwmFlush官方说明](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/nf-dwmapi-dwmflush)：它等待相关排队DirectX更新，不刷新整个会话渲染批次。因此报告的12.9/4.1/144等数字应标为该探针的往返完成节奏，不能称单窗口真实FPS，也不能直接当整台桌面的逐帧合成计数。
- 程序化SetWindowPos、几何误差0和WM_NULL响应快是支持材料路径的旁证，不等于真实鼠标拖动逐帧跟随误差已测得，亦不全面排除全部Qt/Win32交互路径。
- 最大化测试同时改变面积与遮罩，不能据此量化Mask贡献；同机不透明窗口正常不能全面排除驱动与Acrylic的交互。采样不到进程GPU实例也不足以证明从不使用GPU。
- 报告对DWM内部重采样/非矩形慢路径、125%缩放贡献仍属假设。不能把IoT单机结果外推为所有Win10分支或显卡均已验证。

## 本地真正相关的路径

6657e89与v0.2.1 Tag的materials/window_shell两文件无差异；6657e89→ae74066的materials.py仍无差异，window_shell仅有后续W-02 HWND恢复、样式及八方向命中等修改（38行差异）。没有重新审计发布历史。

- 已提交materials.native_material：17763以上且系统允许时设置Accent state=4；_material_key为(HWND, dark, enabled, overlay)。nativeMaterial决定shell_color的Alpha，Acrylic为12、opaque为正常主题底色。sync_native_clip独立处理Region，Win10普通状态仍用圆角Region。
- 当前本机已安装上游WindowsMoveResize.startSystemMove仍为ReleaseCapture→SendMessage(WM_SYSCOMMAND,SC_MOVE|HTCAPTION)，位置交给原生移动循环。
- NekoriWindow.nativeEvent是既有宿主入口；T-07的RuntimeDiagnostics只是被动观察/统计，不修改材质或消息返回值。候选复用宿主入口，不新增原生过滤器、消息Hook或第二移动循环，不改T-07。
- 工作树materials.py/window_shell.py属于W-01七处保护实验：例如实验材料代码限制Win10为opaque，与已提交运行基线不同。固定Demo会从HEAD载入这些保护模块。不能把工作树实验当当前已发布/已提交行为，也不能混入提交或直接应用候选。

## 隔离候选及责任

[W03_WIN10_MOVE_CANDIDATE.patch](W03_WIN10_MOVE_CANDIDATE.patch)针对ae74066已提交两模块生成。git apply --check --cached验证可应用于该提交索引；**未应用于脏工作树**。它不是另一套正式工程、不是运行时Wrapper，不自动被main或固定Demo加载。后续必须在能明确处理W-01保护边界的干净审阅基线上集成，不能用reset/stash/覆盖实验来套补丁。

候选行为：

1. 仅17763≤Build<22000且当前nativeMaterial为acrylic的窗口，在WM_SYSCOMMAND的SC_MOVE上记录本HWND的armed会话。命令按[官方规则](https://learn.microsoft.com/en-us/windows/win32/menurc/wm-syscommand)掩去低4位。SC_SIZE、未明确来源的进入尺寸/移动循环不降级。
2. WM_ENTERSIZEMOVE把armed转active，仍由native_material调用原生接口：临时令enabled=False，Qt正常paint使用opaque主题色。_material_key包含有效enabled，因此现有材质重应用也不能在移动中误开Acrylic。
3. WM_EXITSIZEMOVE/WM_CANCELMODE、隐藏/关闭、状态变化结束临时态。恢复沿当前主题及系统透明策略，保留overlay语义，不永久改用户配置。重复消息幂等。
4. HWND丢失/替换则只丢弃旧会话，不调用winId创建窗口、不向旧句柄恢复；下一次原有show/material生命周期为新HWND正常设置材质。Win10原生设置失败时保留此前已知材质，不把失败伪报为切换成功，不计时重试；若恢复失败可暂留opaque，后续正常材质应用才再次尝试。
5. Win11不进入该策略；原有paintEvent、sync_native_clip、Mask、圆角、阴影规则和标题栏移动/缩放路径均未修改。没有用户材质开关、注册表写入、窗口库升级或定时器。

## 已做验证及未解决风险

tests/test_w03_material_candidate.py五项通过。测试把ae74066的两个模块装入临时目录后应用补丁，再隔离载入，未改七处实验；原生材质API用可控替身，不能据此声称Win10真实合成改善。

覆盖SC_MOVE→进入→退出的[4,0,4]材质序列、重复进入/退出、SC_SIZE不切换、overlay/tint及缓存保持、系统策略变化、API拒绝、取消/隐藏/HWND失效、Win11和原本opaque不降级。真实Win11 Qt隔离宿主中模拟nativeEvent分发：八方向命中结果保持，切换中HWND与Mask不变，隐藏/恢复清理正确；不是Win10实体鼠标拖动或八方向实际缩放验收。

尚未验证：Win10真实拖动改善幅度；第一次切换时Qt旧Alpha backing store与原生brush交接是否闪烁/黑闪/背景突变；移动期间opaque外观可接受程度；松手、Esc、吸附/最大化恢复、隐藏恢复后的Acrylic/圆角/阴影一致性。API成功仅证明接口接受，不等于视觉已恢复。这些风险必须由Win10实际使用判断，当前不能升级为正式修复。

外部下一次只需少量正常使用检查（在开发者准备好隔离候选构建后）：

- 原有复现机器正常拖动数次，比较起步、跟随和停止后的追赶感；不重复150–200Hz实验。
- 松手及Esc取消后，检查Acrylic恢复、边角/背景无明显闪烁漏底；再做一次隐藏恢复和最大化/还原。
- 确认边缘/四角缩放及最小化/最大化/关闭按钮仍正常，普通尺寸调整不发生该临时降级。

固定Demo仅更新仓库记录标识，不启用候选，持续data与排序保留；T-07、G-16及其它成果不改。#7/#37记录“隔离候选，未启用，待Win10实测”，不关闭/勾选，不Push/发布。
