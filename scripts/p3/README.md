# P3 隔离探针

使用 P0 锁定的 Windows / Python 环境。将 `P3_WORK_DIR` 设为程序目录之外的空测试目录；脚本只操作自己创建的 `ui/` 或 `performance/` 合成资源库。不会覆盖已有同名测试库；重新执行创建步骤时换一个测试目录。

1. `python scripts/p3/ui_probe.py`：64 PNG，29 个界面检查与八种布局，输出 `ui/report.json` 和截图。禁止头像联网及全局热键，默认 offscreen；从系统读取现有字体用于截图，不复制字体。
2. `python scripts/p3/group_performance.py`：独立创建 2000 PNG、四个小分类，输出 `performance/report.json`。测量首屏卡片数量、切换耗时和心跳。
3. `python scripts/p3/scroll_probe.py`：复用第二步测试库，检查末尾/折叠/窄窗口，输出 `p3-scroll.json`。
4. `python scripts/p3/native_probe.py`：复用第一步测试库，**会短暂显示 Windows 测试窗口**；检查深浅设置窗口及 `WM_GETICON`。不启用全局快捷键，不写真实启动项，不修改真实用户图库。

原生探针使用测试用 AppUserModelID，不代表已通过最终成品的登录启动或任务栏验收。不要在用户唯一真实库设置此测试目录。源码运行结果不能替代最终 ZIP。
