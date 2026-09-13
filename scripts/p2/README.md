# P2 隔离验证

使用 P0 锁定依赖/开发虚拟环境。设置 P2_WORK_DIR 为本次新建的绝对目录，必须位于程序目录外；每个脚本的测试库不存在时才执行，重复使用会拒绝覆盖。以仓库根运行 `python scripts/p2/startup.py` / `performance.py` / `native_cursor.py` / `native_injection.py`。

- startup：actual main + offscreen 两个合成库，禁用热键和头像网络。
- performance：2000×256×256 PNG，git show 固定 P1 Storage 源与当前服务比较，Qt 后台心跳。消耗仅测试库和内存，不清空系统磁盘缓存。
- native_cursor：Windows 临时 MainWindow、鼠标边缘/客户区记录。需要桌面空闲，会移动光标并短暂显示窗口，完成恢复原鼠标位置和前台窗口。只记录范围，不把未自然复现当作事故修复证据。
- native_injection：同样的隔离原生窗口，注入横向残留后测试文本、链接、标题区域的恢复，并检查边缘委托；明确区分注入场景与真实事故。

原生探针不终止任何既有应用，不读真实图库。执行前通知正在使用桌面的用户，避免与其鼠标操作冲突。最终 EXE、多 DPI、实际拖动和唤醒仍需另测。
