# 方案与依赖决策入口

检查日期 2026-09-13；遵守交接 R-DEPS。候选不等于选型。每次新增第三方组件必须记录精确版本/提交、来源、用途、兼容、维护/真实使用基础、已知问题、依赖树、运行条件、体积/CPU/内存/启动成本、许可证、替换边界和更简单替代；没有实测的量不得填“通过”。

优先级：可靠性与数据安全 > 现有项目兼容 > 长期维护 > 简单程度 > 性能/体积 > 开发速度。隔离验证工具不能替代正式迁移/备份核心。

## P0 实际选择

| 组件 | 理由、证据与边界 |
|---|---|
| 原运行依赖 | 保留原 requirements 的依赖集合，在 Python 3.12 Windows 环境锁定实际解析版本；23 原测试、空数据主界面初始化和 Nuitka 编译通过；原生成品完整交互仍未测。未为产品增加 OCR/数据库框架 |
| Pytest 9.1.1（开发） | 原仓库包含 pytest fixture 风格测试，标准 unittest 不收集那 6 项；采用原测试工具契约，MIT，仅开发依赖。[官方发布记录](https://docs.pytest.org/en/stable/announce/index.html)、[变更记录](https://docs.pytest.org/en/latest/changelog.html)；本项目 23 项通过，不宣称排除所有已知问题 |
| Nuitka 4.2.1（构建） | 复用原构建体系；实际 Windows standalone 与 C# 启动器生成成功。编译器 AGPLv3、runtime 有官方额外许可，已读安装发行物中的 LICENSE 与 LICENSE-RUNTIME；保留相应声明。[官方项目](https://github.com/Nuitka/Nuitka)、[runtime 许可](https://github.com/Nuitka/Nuitka/blob/develop/LICENSE-RUNTIME.txt) |
| Zig 0.16.0（构建） | 原脚本的 CPU 参数为 Zig 拼写；Nuitka 官方支持该编译器。默认 MinGW 下载停滞后，显式选择 Zig 并以四个编译任务成功构建。仅工具链，无后台服务，不打入应用环境；版本来自 Nuitka 的 PyPI 下载流程，实际版本在构建报告中核对。不同 CPU/Windows 兼容仍以实测为准 |
| 标准库隔离与校验 | Git 对象校验、hashlib、zipfile、pathlib、subprocess；只处理任务生成/公开源码的隔离副本，不是用户数据迁移产品实现 |

完整版本见 [P0 环境锁](../../requirements/p0-windows-py312.lock.txt)。真实无 OCR ZIP 口径见 [P0](P0.md)。最终成品应记录“实际打入的依赖及许可”，不能把开发虚拟环境列表直接当发布清单。

## 通用能力调查清单

| 能力 | 首先验证的现有/成熟能力 | 待验证后决定 |
|---|---|---|
| 库位置/身份 | pathlib/系统实际路径解析、UUID、Qt 文件夹选择、库相对引用 | D01/D02，路径包含/别名、离线、只读、重连、换盘 |
| DB/schema | Python sqlite3、SQLite 事务/backup/user_version，复用原表和调用边界 | D03，单 DB/多个 DB 的一致性成本、较新 schema 拒绝、失败回退 |
| 旧源导入/整库复制 | SQLite 一致性快照、受控停写、shutil 复制、hashlib 校验、目标暂存后切换 | D03/D17，不以普通目录复制冒充活跃库的一致备份 |
| 日志与诊断 | logging/RotatingFileHandler/QueueHandler、queue.Queue(maxsize)、zipfile | D16，丢弃/聚合策略、磁盘失败、脱敏和实际开销 |
| 导入/拖放/剪贴板 | 已有 PySide QMimeData/QUrl/QImage、Pillow、requests、现有哈希和 FFmpeg | D07/D10，输入优先级、源不变、线程、格式魔数、身份失效 |
| 缩略图/后台任务 | 现有缓存、Qt 线程池/信号、固定库上下文 | 任务归属、受控失效、不要重扫和无界缓存 |
| 设置/布局 | 现有 ConfigService/Qt 控件、独立预览态、SQLite 持久偏好 | D11/D12，关闭/取消/保存语义、错误配置校验 |
| 无边框行为 | 当前 qframelesswindow 公开实现、Qt/Win32 官方接口 | 先记录 native hit-test/cursor/DPI 证据，再选择修复，不预设替库 |
| OCR | 少量官方资料筛选后的实际 backend/runtime/model 组合 | P4 真实样本、语言混排、GIF、有界资源、真实 Nuitka 增量后才能决定 |
| ZIP/许可 | 现有 Nuitka + 标准 zipfile、允许清单/产物检查、依赖实际报告 | P1 先验证无运行数据，P6 完整发行与许可清单 |

## 未决项

| 编号 | 决定时间/状态 |
|---|---|
| D01 库内部结构/身份 | P1 采用独立根目录 + 格式标识/UUID + 库内相对资源引用，见 [P1](P1.md) |
| D02 最近库定位/引导日志 | P1 采用可丢弃的 LocalAppData 定位信息，业务偏好在库 DB；重连已验证 |
| D03 DB 组织/schema/快照/JSON 冲突 | P1 保留五业务 DB，加库管理 DB；SQLite ATTACH/backup/user_version；冲突显式选择 |
| D04/D05 OCR 后端/runtime/模型 | P4 待评估，未选择 |
| D06 GIF 抽帧/合并/上限 | P4 待实测 |
| D07 内容身份与已有索引 | P1/P2 公共契约，再接 P5 |
| D08 人工/机器/有效文本 | P5，人工空值和并发保护为固定语义 |
| D09 内容替换后的人工版本 | P5，以具体交互验证，不静默转移 |
| D10 浏览器载荷/兼容清单 | P2 Windows 实测 |
| D11/D12 设置模态和关闭/保存 | P3，以统一预览语义验证 |
| D13 完整灾难备份产品 | 不在当前必做范围；不阻塞基础一致复制/恢复 |
| D14 exchange 格式扩展 | 当前不扩展、不大改 |
| D15 简繁 alias | 首版非强制，不改原文 |
| D16 性能/并发/日志参数 | 各阶段测量后记录，未设虚构阈值 |
| D17 长期旧格式兼容范围 | P1 提供一次性只读迁入；正常运行没有 JSON 回退/双写；持续旧格式同步不实现 |
| D18 依赖/方案复用方式 | 随对应阶段更新本记录 |
