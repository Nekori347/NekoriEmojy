# 上游检查：efc0103（2026-09-14）

P0 基线继续为 c84e5b2c201fe5103e721fca062283cadf97ca0d。本次仅 fetch upstream refs；未 merge/reset/强推。

检查对象：[efc0103f2639cafbf76952608e85a46d3080a8cc](https://github.com/IxinorTyan/SuzuEmojy/commit/efc0103f2639cafbf76952608e85a46d3080a8cc)，提交时间 2026-09-13T11:52:46Z。通过 GitHub API 获取逐文件补丁；issues #7/#8/#9 已关闭是状态信息，不等于本分支验收证据。

| 内容 | 处理 |
|---|---|
| file_size/mtime_ns/sync_key 持久化与后台补齐 | 吸收设计思路；Nekori 用 schema 3、明确 file/pixel/sync 字段、稳定 ID/内容版本和原库任务上下文实现。已有效索引随库保留 |
| 剪贴板图片后台保存 | 吸收思路并汇入统一 ImportPipeline/QThread，避免多套分类提交逻辑 |
| 发布包不复制用户 data | P1 已实现更严格的独立库与发布排除检查；不引入上游程序旁 bin/data 运行方案 |
| FFmpeg 文件名不硬编码、构建失败返回非零 | 小范围移植到 build_nuitka.py，来源为本提交 |
| cursor 原生句柄签名 | 参考其 64 位句柄处理思路；本分支正确解析 PySide VoidPtr/MSG，读取 lParam，并恢复当前 Qt 控件自己的光标 |
| 无条件后台 cleanup/full dedup、旧 JSON 写入与自愈 | 不吸收；即使放到后台，也不符合普通重连不能重写人工状态、不能重复全库计算的边界 |
| QImage 内存直转 PIL | 暂缓。统一后台流程已消除 UI 同步编码，后续按真实瓶颈评估，须处理 bytesPerLine/stride |
| 其他 UI/批处理/翻译、bat、缓存文件 | 未整体移植；P3/P6 根据最终 UI 与发布方式逐项取用，不将此次 commit 整体认定兼容 |

光标补丁细节：上游用 `message.contents` 及 `msg.wParam & 0xffff` 判断 HTCLIENT。PySide 6 当前消息是 VoidPtr，需要按地址解析 MSG；[WM_SETCURSOR 文档](https://learn.microsoft.com/en-us/windows/win32/menurc/wm-setcursor) 明确 wParam 是 HWND，命中码在 lParam 低位。Nekori 仅处理当前窗口客户区，保留控件 I-beam/链接手形、Qt override cursor、capture 与原生边缘行为；不覆盖任意区域为 ArrowCursor。

本地原生源码探针没有自然复现旧残留，不能据此宣布用户事故已根治。源运行、固定鼠标点的验证也不能替代最终 EXE、多 DPI、真实拖动/缩放/睡眠唤醒回归。第一轮底边样本出现 HTCLIENT，标记为无效边缘样本，不把它算作通过。
