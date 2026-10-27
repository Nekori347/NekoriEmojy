[简体中文](RELEASE_0.2.2.md) | [English](RELEASE_0.2.2.en.md) | [日本語](RELEASE_0.2.2.ja.md)

# NekoriEmojy 0.2.2

本次更新主要改善表情整理、拖放操作、批量导入及日常使用体验，并修复 0.2.1 发布后发现的多项问题。

## 新增与改进

### 更方便地整理表情

- **统一选择操作**：表情和分类节点使用统一的多选逻辑，改善 Ctrl、Shift 选择及管理模式下的批量操作。
- **分类标题吸附**：滚动图库时，当前分类标题可以停留在视口顶部，方便辨认所在位置。
- **完善拖放整理**：支持将表情和分类节点拖放至顶部分类标签，并增加明确的取消拖放区域。
- **回收站保护**：主图库向 Windows 回收站拖放时，使用独立副本保护原件，并通过确认操作决定是否从表情库中删除。

### 导入、导出与任务管理

- **全局快捷导入**：复制图片后，可使用 `Ctrl + Alt + V` 导入表情。快捷键支持自定义或关闭。
- **集中处理重复文件**：批量导入时可以统一查看和决定如何处理重复表情。
- **中断任务恢复**：受支持的本地导入和 OCR 任务意外中断后，可在下次启动时选择继续、暂留或放弃，不必无条件重新处理整批内容。
- 改善批量导入的进度反馈、图库刷新及导出任务的停止处理。

### 界面与日常使用

- **更清晰的任务通知**：进度与临时结果保持原有叠层显示；完善通知展开、清理、悬停暂停和倒计时提示。
- **更易读的操作提示**：调整排序、设置、导入导出及工具反馈文案，完善简体中文、繁体中文、英语和日语支持。
- **独立视觉开关**：界面动效与窗口毛玻璃可以分别设置。
- **自动检查更新**：支持启动后后台检查新版，可在设置中关闭；不会未经确认自动安装。
- **重复启动唤醒**：再次启动程序时，尝试恢复已经运行的主窗口。
- **反馈与建议**：在应用菜单和关于页面中可以直接打开 GitHub 反馈入口，并主动复制基本环境信息。

### 性能、安全与可靠性

- 优化部分图库查询、分类索引、菜单构建及批量分类操作，减少重复计算与不必要的全量刷新。
- 增强资源包引用路径、压缩包内容和图片下载大小的检查，避免不安全的外部文件引用。
- 改善 Telegram 默认连接配置失效时的恢复流程，并加强自定义凭据和代理传输的边界保护。
- 完善诊断日志留存与主动导出能力；不会自动上传用户的表情库或诊断文件。

## 问题修复

本次还包含多项图库、窗口和交互修复，详细过程保留在对应 Issue：

- [图库滚动、分类与批量操作：#26](https://github.com/Nekori347/NekoriEmojy/issues/26)、[#40](https://github.com/Nekori347/NekoriEmojy/issues/40)
- [分类节点与拖放：#16](https://github.com/Nekori347/NekoriEmojy/issues/16)、[#17](https://github.com/Nekori347/NekoriEmojy/issues/17)、[#18](https://github.com/Nekori347/NekoriEmojy/issues/18)
- [标签栏交互与显示：#24](https://github.com/Nekori347/NekoriEmojy/issues/24)、[#25](https://github.com/Nekori347/NekoriEmojy/issues/25)
- [窗口最大化及恢复：#57](https://github.com/Nekori347/NekoriEmojy/issues/57)
- [按钮悬停与焦点反馈：#60](https://github.com/Nekori347/NekoriEmojy/issues/60)
- [Tooltip 显示及文案：#62](https://github.com/Nekori347/NekoriEmojy/issues/62)
- [完整的 0.2.1 发布后更新记录：#37](https://github.com/Nekori347/NekoriEmojy/issues/37)

## 已知问题

窗口边缘连续缩放、部分 Windows 环境下的拖动响应，以及大图库滚动的性能长尾仍在持续跟踪。这些问题没有被标记为全部修复。

详见 [#9 窗口缩放](https://github.com/Nekori347/NekoriEmojy/issues/9)、[#7 窗口拖动](https://github.com/Nekori347/NekoriEmojy/issues/7)、[#26 图库性能](https://github.com/Nekori347/NekoriEmojy/issues/26)。

## 下载与升级

提供 Windows x64 安装版和免安装版。文字识别 OCR 仍为可选组件，普通表情管理不需要预先安装。

从旧版升级前，建议备份表情库及个人配置。软件数据可能保存在独立目录中，不要通过删除用户数据目录来更新程序。

如遇到问题或有功能建议，可使用软件内「反馈与建议」或前往 [GitHub Issues](https://github.com/Nekori347/NekoriEmojy/issues)。
