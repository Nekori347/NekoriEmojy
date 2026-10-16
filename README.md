# NekoriEmojy

Windows 本地表情 / 图片资源管理器，基于 SuzuEmojy v1.13.0（`0152f075a5595f12cf71512321b84fa76755820e`）。保留原作者署名与 [GPL-3.0 许可](LICENSE)。

本目录是正式工作树。AI 接手：[AI_START](../ProjectDocs/AI_START.md) → [CURRENT](../ProjectDocs/CURRENT.md)；当前模块关系见 [ARCHITECTURE](../ProjectDocs/ARCHITECTURE.md)。进度统一在 CURRENT，不以本目录继承的 Suzu 说明书 / 专项文档判断当前产品状态。

启动用项目根 [Start-Nekori.bat](../Start-Nekori.bat)，或本目录 `.\.venv\Scripts\python.exe main.py`。隔离体验用 [DevData/Start-v2-Demo.bat](../DevData/Start-v2-Demo.bat)：直接加载本工作树，仅隔离数据。修改后先退出旧进程再重启。

环境安装：`python -m venv .venv`，然后 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest`。启动来源检查可运行隔离 Demo BAT 并传入 `--smoke-test`，输出解释器 / 模块实际路径；其他验证按修改风险选已有测试，不默认全库回归。

Library 在程序外，默认 Pictures；配置 / 缓存在 LocalAppData。Settings 选库保存后重启生效。真实测试使用 DevData；Suzu 源只读复制。上游 build / 发布说明尚未适配正式 Nekori 发布，不能用旧 artifact 代替当前开发启动。

ProjectDocs 等在本 Git 仓库外，交接必须保留完整 NekoriEmojy 根目录。
