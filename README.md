# NekoriEmojy

Windows 本地表情 / 图片资源管理器，基于 SuzuEmojy v1.13.0（`0152f075a5595f12cf71512321b84fa76755820e`）。保留原作者署名与 [GPL-3.0 许可](LICENSE)。

本目录是正式工作树。AI 接手：[AI_START](../ProjectDocs/AI_START.md) → [CURRENT](../ProjectDocs/CURRENT.md)；当前模块关系见 [ARCHITECTURE](../ProjectDocs/ARCHITECTURE.md)。进度统一在 CURRENT，不以本目录继承的 Suzu 说明书 / 专项文档判断当前产品状态。

唯一正常启动入口为项目根 [Start-Nekori.bat](../Start-Nekori.bat)，当前加载项目内可丢弃的 Demo 数据。AI 的根 Restart-Nekori.ps1 只重启同一入口；隔离自动检查显式设置数据路径，不能替代正式 Demo。修改后须退出旧进程并从根入口重启。

环境安装：`python -m venv .venv`，然后 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest`。验证按修改风险选已有测试，不默认全库回归。版本单一来源为 `version.json`；[版本变更与本地 Git 基线](docs/CHANGELOG.md)。

表情库默认位于 `%USERPROFILE%\Pictures\NekoriEmojy Library`；配置位于 `%LOCALAPPDATA%\NekoriEmojy\config.json`，已有 `library_path` 指定的自定义表情库继续保留。设置选库保存后重启生效。真实测试使用 DevData；Suzu 源只读复制。

## 候选包启动与更新

正式独立文件集和本地候选安装版/ZIP已验证，使用 `NekoriEmojy.exe` 启动，更新器为 `NekoriEmojyUpdater.exe`；不得覆盖独立 Suzu 安装目录。完整独立版无需外部 Python，开发轻量入口仍可按需准备环境。项目根开发启动器不随发布包分发。

更新只替换发布清单拥有的程序文件，配置、表情库与可选文字识别组件具有独立位置。重装或移动程序后继续使用原配置中的表情库路径；路径变化时在设置中重新连接。手动删除程序目录前，确认没有把自定义表情库放在其中，并先备份配置与整个表情库。源码回退不代表数据库可以直接降级。

正式工程位于 `F:\[2]Ai\NekoriEmojy`，本目录仍是唯一活动 Git 工作树。`build.bat` 默认仅构建独立的 `../Build/lightweight-时间/application/` 验证目录，不会生成分发ZIP；`--archive` 为下一阶段明确制作ZIP时使用。`build_nuitka.bat`/`build_nuitka.py`保留独立版编译入口，最终也进入工程外层Build独立暂存区。正向白名单与生成物规则见 [DISTRIBUTION](docs/DISTRIBUTION.md)。不从工程根、DevData、旧包或Archive递归打包。分发文件与SHA-256保留在工程根Distribution/0.2.1；Inno构建入口为scripts/build_distribution.py。当前仅做本地验证，不自动公开发布。

文字识别为可选本地组件，不混入基础依赖。当前公开组件下载地址尚未发布，本轮验证的是本地组件安装与运行，不声称联网部署已经完成。源码中的`说明书.md`为Suzu历史参考，不随新基础包分发。

ProjectDocs 等在本 Git 仓库外，交接必须保留完整 NekoriEmojy 根目录。
