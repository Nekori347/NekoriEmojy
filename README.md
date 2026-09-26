# NekoriEmojy

Windows 本地表情图库。基于 [IxinorTyan/SuzuEmojy](https://github.com/IxinorTyan/SuzuEmojy) 的公开 Fork，重点是让图片和整理结果随独立资源库长期保存。

当前为 **0.1.0-rc1 / 第一可用版候选**，尚未正式发布。开发与反馈请使用 [Nekori347/NekoriEmojy](https://github.com/Nekori347/NekoriEmojy)。

## 这一版做什么

- **独立资源库**：用户指定位置；图片、分类、普通 Tag、排序、最近记录和偏好随库保存，更换程序时保留原库。
- **复制导入**：外部原文件保持原位；软件大分类及小分类关联同一份库内图片。
- **平铺小分类**：在大分类内自建、命名、折叠和整理，不增加多级菜单。
- **从 SuzuEmojy 过渡**：只读迁入旧 data，保留原始快照及报告，转换可靠可对应的图库、分类关系、排序、Tag、最近记录等。
- **沿用日常操作**：浏览、普通 Tag 搜索、筛选、多选、复制/发送、最近记录、去重和资源包导入导出。

OCR、隐性 Tag、模型管理、安装器及自动更新不在本轮范围。完整交接是长期 Roadmap，按 [当前范围](docs/spec/2026-09-20-iteration1.md) 小步交付。

## 开始使用

1. 完整解压候选 ZIP，保留 `bin` 和根目录 `NekoriEmojy.exe`。
2. 双击根目录启动器，在程序目录以外创建资源库，或打开已有 Nekori 库。
3. 老用户在设置的“资源库与诊断”中选择“从旧 SuzuEmojy 只读迁入”，把已关闭的旧版 data 迁入另一个空文件夹。保留原版和原 data。
4. 参阅 [使用说明](说明书.md)。完整备份应复制整个库，资源包不等于整库备份。

关闭窗口会隐藏到托盘；完全退出使用托盘菜单。库位置记忆丢失时，重新选择原库即可。

## 数据通道与边界

| 通道 | 场景 | 保留范围 |
|---|---|---|
| 旧 data 只读迁入 | 首次转用 | 图库、可靠可对应的分类关系、图片/分类排序、普通 Tag、最近记录、图标及可用偏好；差异需选择来源，缺失项写报告 |
| exchange v1 资源包 | 两版交换图片 | 旧格式支持的 PNG/GIF、普通 Tag、大分类及关系；没有小分类、手工排序、最近记录或设置 |
| 完整资源库复制 | Nekori 备份/换位置 | 整库及组织信息；旧 Suzu 不直接打开 Nekori 库 |

v1 会跳过 WebP/WebM/APNG 等不支持类型并记录原因。固定基线 Suzu 能读 Nekori 导出的包，但其导入器会忽略空分类，旧导出器还可能拆分 Tag 文本。首次过渡优先直接只读迁入；原 Suzu 数据保留作为退路，新整理的小分类不承诺回传。

## 验证与运行条件

目标是 Windows x64 便携版，当前验证机器为 Windows 11，构建沿用 x86-64-v3 / AVX2 指令目标。尚未完成无开发环境的干净机器、其他 CPU、跨物理磁盘及真实用户大图库验收，不能承诺所有 Windows 10/11 设备可用。

构建与测试证据见 [开发状态](docs/development/STATUS.md) 和 [Iteration 1](docs/development/ITERATION1.md)。测试采用生成的图库，不能替代实际日常使用验收。

## 开发与来源

运行依赖沿用上游，没有引入 OCR、NumPy、OpenCV 或模型。[Windows Python 3.12 依赖锁](requirements/p0-windows-py312.lock.txt) 记录已验证环境；运行 `python build_nuitka.py` 使用 Nuitka、Zig 和系统 C# 编译器构建。使用成品无需另装 Python。

保留 upstream 关系，固定起点为上游 v1.11.6 / `c84e5b2c201fe5103e721fca062283cadf97ca0d`；更新先检查 diff，再选择性吸收兼容修改。详见 [上游记录](docs/development/UPSTREAM.md)。

感谢 SuzuEmojy 原作者 **IxinorTyan** 与原项目贡献者。保留原许可证及致谢，使用 [GPL-3.0](LICENSE)。原项目资料可从保留的 Git 历史查询。Nekori 的问题请提交本 Fork。
