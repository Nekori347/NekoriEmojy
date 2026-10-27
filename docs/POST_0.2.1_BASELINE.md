# Post-0.2.1 开发基线

2026-10-21：阶段一至三完成后进入 WP-A，开发阶段为 Unreleased，不修改 version.json。

- 唯一工程 F:\[2]Ai\NekoriEmojy；Git 在 Source；初始分支 main，HEAD/本地 origin/main/实时远端 main 均 b6b07b5b20cb7c1fd4c2a60e3e046bf17f272cbf。工作区、暂存区均干净，无待混入改动。
- 正式 v0.2.1 提交 b1788f85f9a125596645a8a2c7caae4b8a048ef1，为 main 祖先；二进制构建来源 6657e89。Release 418398591 已公开，2026-10-20 22:07:59 北京时间，非预发布。未重验发布流程、未重建/下载发行物。
- main 比 Tag 多 PR #6 下载指引，只影响三语言 README / Release Notes 共六文件；基点选 main，避免丢失有效文档改动。nekori/framework 停在 6657e89。
- 本地与实时远端分支没有适用的 post-0.2.1 分支；新建 dev/post-0.2.1。Git ls-remote 网络重置后，用已连接 GitHub API 只读确认远端 main/分支/Release；未 Push。
- [需求原文](POST_0.2.1_PLAN.md) 字节保留，包括 W/G/T/E 编号和 WP-A 至 I 关系。原文的未授权声明是历史属性；本轮授权仅准备和 WP-A。
- 本地项目状态见 ../../ProjectDocs/CURRENT.md，重要决定见 ../../ProjectDocs/DECISIONS.md，验证证据及独立数据在 ../../DevData/post-021-wpa。

## 文档回退

Source/docs 的规划、基线、Unreleased 和本地文档差异一起提交。ProjectDocs 位于 Git 外，不创建第二仓库、不复制一套活动文档。POST_0.2.1_LOCAL_DOCS.patch 保存本轮本地文档增量；从工程根执行 `git apply --reverse --check Source/docs/POST_0.2.1_LOCAL_DOCS.patch`，确认后去掉 --check 可回退（后续有冲突时人工处理，不强制覆盖）。Source 内文档用普通 git revert 回退文档准备提交。

## 停止边界

本轮仅 WP-A W-01/02/03（P0）；WP-B 至 I 未实施。E-01 仅未来最小契约。保留 main/Tag/发行资产/真实用户与 Suzu 数据；以隔离数据体验开发源码版本，不更改发布版本号。不 Push、不新 Release。
