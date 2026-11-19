[简体中文](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.md) | [繁體中文](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.zh_TW.md) | [English](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.en.md) | [日本語](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.ja.md)

# NekoriEmojy 0.2.6

本次更新重点改善了大量表情的搜索、浏览和整理体验，新增无需重启的表情库切换，并进一步完善安装与更新流程。

## 新增功能与优化

- **表情库快速切换**：现在可以直接在设置中切换不同的本地表情库，无需重新启动程序。
- **更快的快速面板**：优化首次搜索与缩略图加载，在大量表情中查找资源更加流畅。
- **更稳定的浏览位置**：改善分类、搜索、最近使用及托盘恢复时的滚动位置记录，切换视图后更容易接着原来的位置浏览。
- **动态表情显示**：代表帧和裁切效果在图库与快速面板之间保持同步。ANIM 角标改为轻巧的半透明样式，鼠标悬停时自动淡化。

## 问题修复

- 修复最近使用列表在其他页面发送表情或修改显示数量后，可能仍显示旧内容的问题。
- 修复失效表情重新绑定新文件后，可能沿用原文件动态标记的问题。
- 改善资源库切换及更新窗口的状态管理。
- 修复部分安装路径出现重复目录的问题。安装和卸载时会检查正在运行的程序，避免文件被不完整地替换或移除。
- 改善内置更新时的程序退出、失败恢复和重试流程，并增强长时间卡顿时的本地诊断记录。

## 下载与升级

提供 Windows x64 安装版和免安装版，OCR 文字识别仍为可选组件。

使用安装版升级前，请保存正在编辑的内容，并从系统托盘完全退出旧版程序，再运行安装程序。通过软件内置更新时，按界面提示操作即可。

原有设置与独立表情库继续沿用。

[**Windows 安装版（推荐）**](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.6/NekoriEmojy-Setup-0.2.6.exe) · [Windows 免安装版](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.6/NekoriEmojy-0.2.6-Windows-Portable.zip)
