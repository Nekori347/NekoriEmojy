# 上游与长期仓库

用户指定的长期开发仓库是 [Nekori347/NekoriEmojy](https://github.com/Nekori347/NekoriEmojy)，是 [IxinorTyan/SuzuEmojy](https://github.com/IxinorTyan/SuzuEmojy) 的公开 Fork。2026-09-13 通过 GitHub API 核验 `fork=true`、`parent` 和 `source` 均为上述上游，默认分支 `main`，许可证 `GPL-3.0`。

P0 固定基线：`v1.11.6`，`c84e5b2c201fe5103e721fca062283cadf97ca0d`。此次核验时 Fork main、upstream main、上游标签均指向它，双方 diff 为空。

## 开发工具的远端配置

```powershell
git remote add upstream https://github.com/IxinorTyan/SuzuEmojy.git
git remote set-url --push upstream DISABLED
git config remote.pushDefault origin
```

`origin` 指向用户的 Fork。以上配置仅作用于开发工具管理的检出副本；Git 的 remote 配置不随提交传播，新的环境应重新建立。用户无需执行或维护这些命令。

## 吸收上游修改

1. 只获取远端 refs，记录检查时间、上游旧/新 SHA；上游标签放在 `upstream/` 命名空间，避免与 Nekori 版本冲突。
2. 先看 `git log`、`git diff --stat` 及逐文件 diff，识别实际功能、依赖、数据写入与发布路径变化。
3. 特别检查是否重新引入程序旁运行数据、自动删 JSON、自愈重写排序、同步全库扫描、错误的库上下文或 OCR 人工覆盖。
4. 在独立分支选择性吸收有价值且兼容的修改；适合时用 `cherry-pick -x` 保留来源，否则手工移植并记录原提交和取舍。
5. 运行相关契约和原功能回归，再提交到用户 Fork。拒绝或延后某项也记录理由。

不启用无条件 Fork 同步，不以 `reset --hard upstream/main`、强推、覆盖整个目录等方式更新长期开发分支。不要向 upstream 推送。保留原 `LICENSE`、作者版权、来源说明及修改记录。
