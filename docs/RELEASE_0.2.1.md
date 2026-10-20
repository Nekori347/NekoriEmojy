[简体中文](RELEASE_0.2.1.md) | [English](RELEASE_0.2.1.en.md) | [日本語](RELEASE_0.2.1.ja.md)

# NekoriEmojy 0.2.1

NekoriEmojy 是一个用于 Windows 的本地表情管理工具，提供分类与节点整理、搜索、快速面板和直接发送等功能。

本次提供安装版与免安装版，并附有需要时使用的文字识别组件。

## 下载 v0.2.1

| Windows 下载 | 适用方式 |
| --- | --- |
| **[Windows 安装版（推荐）](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.1/NekoriEmojy-Setup-0.2.1.exe)** | 适合普通用户，下载安装程序后正常使用。 |
| [Windows 免安装版](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.1/NekoriEmojy-0.2.1-Windows-Portable.zip) | 下载 ZIP，解压后使用；用户数据不一定保存在软件目录。 |

- **OCR 为可选组件**，可从软件设置中按需安装。普通用户无需先手动下载 OCR ZIP 或 JSON，普通表情管理不依赖 OCR。
- `BUILD_INFO.json`、`RELEASE_INFO.json` 和 `NekoriOCR-win-x64-1.metadata.json` 是构建、发行和 OCR 组件元数据，供诊断或组件安装流程使用，不是主程序安装包。
- `SHA256SUMS.txt` 用于核对下载文件的 SHA-256 校验值。
- `NekoriEmojy-0.2.1-Source.zip` 及 GitHub 自动提供的 Source code ZIP / tar.gz 面向阅读源码或自行构建的用户，日常使用无需下载。

[查看完整 Release 与全部附件](https://github.com/Nekori347/NekoriEmojy/releases/tag/v0.2.1)

## 主要功能

- **分类与节点**：多级分类、子分类、顶部分类标签页，以及可以与普通表情混合排列的可折叠节点。
- **自由整理**：单张或多张表情拖动排序、分类调整与标签管理。
- **查找表情**：名称与标签搜索、最近使用、动态预览、自定义 GIF 缩略图停留帧；可按需安装文字识别（OCR）组件。
- **快速使用**：快速面板、一键粘贴导入、点击发送与拖动发送。并可选择将静态表情作为单帧 GIF 发送。
- **界面与个性化：** 支持深浅主题、实时预览主题强调色、自定义软件图标、可调整的界面布局和多语言界面。
- **导入与数据管理：** 支持独立表情库存储、Nekori 原生资源包导入导出、Suzu 兼容分享包、设置文件备份，以及从 SuzuEmojy 现有数据或分享包迁移收藏。

更多截图与操作演示请参阅仓库首页的 README。

## 更新与个人数据

升级前建议备份表情库和个人配置，特别是从旧版本或其它表情管理器迁移时。表情库目录与配置目录不一定相同；请勿通过直接删除用户数据目录的方式更新程序。

## 已知限制

- 目前主要面向 Windows x64。
- 主程序已经采用面向通用 x64 的构建目标，但尚未在不支持 AVX2 的实际硬件上完成验证。
- 文字识别为可选组件，首次使用需要获取相应文件；公开下载路径以本次 Release 实际上传的资源为准。
- 表情发送与拖动效果可能因目标程序的接收行为而异。

## 反馈与开发方式

这是一个个人维护的 **Vibe Coding 项目**，代码主要通过 AI 辅助编写与迭代。若遇到问题，请尽量附上软件版本、复现步骤与相关错误信息，通过仓库 Issues 反馈。

项目基于 [SuzuEmojy](https://github.com/IxinorTyan/SuzuEmojy) 等开源项目继续开发。更多来源与许可信息见仓库 README 与 LICENSE。
