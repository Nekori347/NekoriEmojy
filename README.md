# NekoriEmojy

Windows 本地表情 / 图片资源管理器，基于 SuzuEmojy v1.13.0（`0152f075a5595f12cf71512321b84fa76755820e`）。保留原作者署名与 [GPL-3.0 许可](LICENSE)。

本目录是正式工作树。AI 接手：[AI_START](../ProjectDocs/AI_START.md) → [CURRENT](../ProjectDocs/CURRENT.md)；当前模块关系见 [ARCHITECTURE](../ProjectDocs/ARCHITECTURE.md)。进度统一在 CURRENT，不以本目录继承的 Suzu 说明书 / 专项文档判断当前产品状态。

唯一正常启动入口为项目根 [Start-Nekori.bat](../Start-Nekori.bat)，当前加载项目内可丢弃的 Demo 数据。AI 的根 Restart-Nekori.ps1 只重启同一入口；隔离自动检查显式设置数据路径，不能替代正式 Demo。修改后须退出旧进程并从根入口重启。

环境安装：`python -m venv .venv`，然后 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest`。验证按修改风险选已有测试，不默认全库回归。版本单一来源为 `version.json`；[版本变更与本地 Git 基线](docs/CHANGELOG.md)。

表情库默认位于 `%USERPROFILE%\Pictures\NekoriEmojy Library`；配置位于 `%LOCALAPPDATA%\NekoriEmojy\config.json`，已有 `library_path` 指定的自定义表情库继续保留。设置选库保存后重启生效。真实测试使用 DevData；Suzu 源只读复制。

## 候选包启动与更新

本轮构建的是轻量候选包。解压到独立程序目录，使用包内 `SuzuEmojy.exe` 启动；该文件名及更新器名为现有更新协议保留，软件仍为 NekoriEmojy，不应覆盖 Suzu 原安装目录。轻量入口首次运行可能联网准备 Python/图形依赖。项目根开发启动器不随发布包分发。

更新只替换发布清单拥有的程序文件，配置、表情库与可选文字识别组件具有独立位置。重装或移动程序后继续使用原配置中的表情库路径；路径变化时在设置中重新连接。手动删除程序目录前，确认没有把自定义表情库放在其中，并先备份配置与整个表情库。源码回退不代表数据库可以直接降级。

`build.bat`构建轻量包，`build_nuitka.bat`/`build_nuitka.py`为独立版入口；当前候选包的实际构建/验收范围以发布记录为准。ZIP名称读取`version.json`的`update_asset`，内部更新清单协议仍保留兼容名称。不存在Windows安装器或卸载器，不声称验证了尚不存在的安装形式。

文字识别为可选本地组件，不混入基础依赖。当前公开组件下载地址尚未发布，本轮验证的是本地组件安装与运行，不声称联网部署已经完成。随附`说明书.md`明确标记为Suzu历史参考，不作为当前Nekori操作指南。

ProjectDocs 等在本 Git 仓库外，交接必须保留完整 NekoriEmojy 根目录。
