# 第一可用版验证与打包

本目录是开发工具，不进入便携程序运行依赖。测试只使用新建隔离目录/合成图片；不要把用户正在使用的库传给原生交互探针。

- `transition_probe.py --work <不存在的目录>`：从固定 Git 基线提取原 Suzu 服务源码，借助 `legacy_side.py` 子进程验证源只读迁入与 exchange 双向过渡。需在 P0 锁定环境运行。
- `tests/test_release_launcher.py`：真实编译 C# 启动器与接收器，核对包含中文、空格、引号和反斜杠的 argv。
- `uia_probe.cs`：用系统 .NET Framework C# 编译器编译，引用 WPF 中 UIAutomationClient / UIAutomationTypes / WindowsBase；仅访问指定 PID 的控件。使用 id/name 定位，动态窗口会改变数字索引。
- `native_driver.py`：launch / dump / action / click 辅助实际 EXE 验证，需与目标程序在同一 Windows 桌面。launch 提供独立 bootstrap 并禁用测试网络；dump 用 PrintWindow 捕获指定窗口，不截图其他应用。后台窗口弹出菜单及前台激活可能受 Windows 限制；不能据此宣称真实点击已通过。
- `package_candidate.py --output <输出目录>`：在同一构建环境，源码工作树干净且 runtime 已验证后，将 `dist/NekoriEmojy_Release`、声明、精确源码和校验报告输出；不发布、不上传。

原生退出验证向测试进程的 `QTrayIconMessageWindow` 发送 WM_CLOSE，Qt 正常终止、退出码 0、clean shutdown 日志及数据库一致性均核验；没有强杀进程。机制参考 [Qt 6.11 官方源码](https://raw.githubusercontent.com/qt/qtbase/6.11/src/plugins/platforms/windows/qwindowssystemtrayicon.cpp)。不能把这项称为物理托盘菜单点击验证。

全套回归使用临时 basetemp、Qt offscreen，并禁用头像网络。实际数字和未通过/未执行边界见 `docs/development/ITERATION1.md`，不是在此重复承诺。
