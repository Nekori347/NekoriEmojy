# NekoriEmojy

Windows 本地表情 / 图片资源管理器，基于 SuzuEmojy v1.13.0（`0152f075a5595f12cf71512321b84fa76755820e`）。保留原作者署名与 [GPL-3.0 许可](LICENSE)。

本目录是正式工作树。AI 接手：[AI_START](../ProjectDocs/AI_START.md) → [CURRENT](../ProjectDocs/CURRENT.md)；当前模块关系见 [ARCHITECTURE](../ProjectDocs/ARCHITECTURE.md)。进度统一在 CURRENT，不以本目录继承的 Suzu 说明书 / 专项文档判断当前产品状态。

唯一正常启动入口为项目根 [Start-Nekori.bat](../Start-Nekori.bat)，当前加载项目内可丢弃的 Demo 数据。AI 的根 Restart-Nekori.ps1 只重启同一入口；隔离自动检查显式设置数据路径，不能替代正式 Demo。修改后须退出旧进程并从根入口重启。

环境安装：`python -m venv .venv`，然后 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest`。验证按修改风险选已有测试，不默认全库回归。当前开发版为 `0.1.2`，版本单一来源为 `version.json`；[版本变更与本地 Git 基线](docs/CHANGELOG.md)。

Library 在程序外，默认 Pictures；配置 / 缓存在 LocalAppData。Settings 选库保存后重启生效。真实测试使用 DevData；Suzu 源只读复制。上游 build / 发布说明尚未适配正式 Nekori 发布，不能用旧 artifact 代替当前开发启动。

ProjectDocs 等在本 Git 仓库外，交接必须保留完整 NekoriEmojy 根目录。
