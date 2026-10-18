# 0.2.0 审计前冻结说明

2026-10-18；本次提交用于保存此前累计的可运行修改，随后建立本地 `pre-release-audit-20261018` Tag。它不是正式Release，不推送。

版本唯一来源为根 `version.json`（0.2.0/development）。源码运行使用项目外壳的 `Start-Nekori.bat → Start-Nekori.ps1 → Source/.venv/Scripts/python.exe Source/main.py`；该开发入口显式使用 `DevData/demo-runtime`。正常发布程序没有开发入口的路径覆盖：配置由 `services.app_paths.app_data_dir`定位，表情库由环境覆盖、已有`library_path`或默认图片目录定位。OCR是配置目录下的可选components/ocr，不属于基础包依赖。

Git工作树只覆盖Source。现有构建入口是`build.bat`（轻量）和`build_nuitka.bat/build_nuitka.py`（独立版）；实际可发布性、历史Suzu名称及更新合同将在冻结后审计，不能把脚本存在当作构建成功。

项目根ProjectDocs、启动脚本、必要参考手册、用户原文与实际依赖版本随独立工程快照保存；不将真实配置、表情库、模型、虚拟环境或安装包纳入Git。完整SHA、Tag、快照与备份位置、恢复步骤记在项目根`DevData/release-audit-20261018`及快照元数据。Source可用Tag/Git bundle或source.zip还原；数据库须从独立备份恢复，源码回退不等于数据库降级。

冻结后先验证源码、配置和数据库能够在隔离路径读取，再进行任何清理、升级试验。正式发布和远端推送仍需用户决定。
