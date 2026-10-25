# Post-0.2.1：原生回收站研究与本地候选验收

## G-27最新状态：主图库确认已实现、待人工验收

维护者已明确批准投放后应用删除确认，源码`3699239`已接入主图库。真实Nekori窗口完成单张/批量确认与取消，复用原删除框和存储事务；取消后原件、记录、关系和顺序不变，确认后正确清理。普通文件夹、Esc、受控延迟读取、内部排序和Relative停留切换经定向验证。完整结果及限制见 [回收站确认记录](POST_0.2.1_RECYCLE_CONFIRMATION.md)。

系统仍可能先回收外拖副本，原框以四语言明确解释；不清空回收站。QuickPanel保持旧安全副本路径，确认接入未包含；Win10、真实聊天客户端和维护者体验仍待验证。**下文“确认后置/需批准”只属于上一轮当时研究，不再是产品需求待决。** 上一轮38c2910本地候选包尚未重建，不含此次功能；当前体验用固定Demo。

## 以下为97c1fca时的原生研究与候选构建记录

日期：2026-10-25。应用构建基线 `38c2910`，分支 `dev/post-0.2.1`。本轮不改业务源码、不启用 W-03、不吸收七处 W-01 实验。不 Push、不发布。

## G-27 / #52：结论与证据

**原生目标身份能够取得；现有 Qt/Python 拖放不能直接接收。暂不纳入内部删除确认。**

`f21fa35` 的原件保护保持：`ResourceDragMimeData` 内部 MIME 携带既有身份，外部 URL/文本按需生成独立副本，不使用硬链接；复制失败不回退原件；保留文件供聊天软件异步读取，后续进程首次导出清理七天前的自有缓存。`EmojiCard` 仍由 QDrag 持有 MIME 并执行 Copy/Move 会话。返回效果不是可靠的回收站身份。

本轮未修改 `services/external_drag.py`、EmojiCard、Drop Contract 或删除事务。现有跨生命期、失败不暴露原件、多同名文件及缓存清理检查沿用既有测试。

### 实际 Windows 证据

独立 `tools/probe_recycle_target.cs` 实现最小诊断用 IDataObject / IDropSource，仅公布生成文件的 CF_HDROP。它不是产品组件，没有导入应用、访问真实 Library 或挂钩其它进程。SetData 只记录通知，不调用 Nekori 删除。测试目录必须为空，不能输入用户资料目录。

| 场景 | 原生反馈 | 文件结果 |
| --- | --- | --- |
| 直接绑定真实回收站 IDropTarget，DragEnter → Drop | TargetCLSID=`645ff040-5081-101b-9f08-00aa002f954e`；Performed=0、Logical=2、返回 effect=0 | 导出副本被回收，生成原件保留 |
| 真实 OLE 鼠标拖入回收站窗口 | button-released 后收到相同 TargetCLSID，DoDragDrop 返回 `DRAGDROP_S_DROP`、effect=0 | 副本被回收，原件保留 |
| 普通资源管理器文件夹，直接与真实鼠标投放 | TargetCLSID=`f3364ba0-65b9-11ce-a9ba-00aa004ae837`，不同于回收站 | 仅独立副本移动，原件保留 |
| 回收站 DragEnter → DragLeave | 没有 TargetCLSID | 副本与原件保留 |
| 真实 OLE 按 Esc | `DRAGDROP_S_CANCEL`，没有 TargetCLSID | 副本与原件保留 |

真实回收站鼠标记录：松手 2714ms → TargetCLSID 2775ms → 完成 3173ms（样例启动为时钟起点）。所以 **不是投放前识别**；也不能仅看到 CLSID 就认定文件操作最终成功。初次桌面尝试因目标尚未稳定命中而在输入前中止；修正验证程序 DPI 与落点等待后才完成上述原生组，未把首轮中止计为通过。

本次只验证 Win11 当前系统、CF_HDROP、同步样例。没有把 Win10、全部 Shell 扩展、FileDescriptor/Contents、虚拟文件、异步数据对象及真实聊天软件兼容性算作通过。生成副本可能留在回收站；没有清空或遍历删除其它回收站文件。

### 可复用来源与接入障碍

- [Microsoft Shell transfer scenarios](https://learn.microsoft.com/en-us/windows/win32/shell/datascenarios)：目标可通过数据对象回传回收站 CLSID；源端处理自身数据。
- [Shell clipboard formats](https://learn.microsoft.com/en-us/windows/win32/shell/clipboard)：TargetCLSID、Performed/Logical DropEffect 是不同通知，不能互相替代。
- [ExplorerListView](https://github.com/TimoKunze/ExplorerListView/blob/master/samples/WTL10/General/Drag%27n%27Drop/MainDlg.cpp)，blob `fade12416e57e063d38f3c2b8d195b9d6f852ba2`，994–1021：**OLECompleteDrag** 后读取 TargetCLSID，再更新自身条目，不是释放前拦截。不能照搬其直接删除列表项为 Nekori 的删除事务。
- [7-Zip PanelDrag.cpp](https://github.com/ip7z/7zip/blob/main/CPP/7zip/UI/FileManager/PanelDrag.cpp)：IDataObject::SetData/SetData2 接收并存储反馈；TargetCLSID 分支说明发生在 QueryContinueDrag 松手之后。避免在 OLE 会话内弹模态确认。可借鉴格式、所有权及完成后调度原则，未复制其整套原生拖放实现。
- [ReactOS](https://github.com/reactos/reactos/blob/master/dll/win32/shell32/droptargets/CRecyclerDropTarget.cpp)，blob `46bde7d4c3fe2ef1e2c0cc2be979886ffacfd9f7`：对应 TargetCLSID 通知仍为 TODO，不能代替 Windows 实测。
- [实际 Qt 6.11.2 qwindowsole.cpp](https://github.com/qt/qtbase/blob/v6.11.2/src/plugins/platforms/windows/qwindowsole.cpp)，blob `8e14b8f2fd55145d13b19c4c99d6449431838748`，114–133：SetData 仅接收 Performed DropEffect，其余 E_NOTIMPL。不是只依据 6.11 分支快照。

本地 PySide6 / Qt 均为 6.11.2；QDrag 公开 target 是 Qt 对象而非 Shell CLSID，未公开原生 IDataObject 指针或 SetData 观察入口；QWindowsMimeConverter 也未绑定到当前 PySide6。现有 QMimeData.retrieveData 是交付路径，不是目标 SetData 通知入口。改 MIME 名称或监听 MoveAction 无法补上它。

因此不能仅加一个 Python 回调完成可靠接入。需要额外原生桥接/自有 IDataObject 与 IDropSource，并兼容内部 MIME、混合选择、投影切换、拖动投影、取消和异步读取；或修改 Qt 平台层再维护对应分发。独立样例成功不证明这些集成已完成。本轮不替换 QDrag、不升级 Qt、不加 Hook。

若维护者未来接受“系统先处理临时副本 → OLE 完成并验证结果 → 应用确认是否删除原件”，还需批准该语义，并决定取消后回收站副本的解释方式；不能自动清空回收站。应携带稳定资源 ID，完成后回到 GUI，复用原有全局删除确认/事务并重新核实资源状态。它仍不是阻止系统先回收副本。当前建议后置此功能，#52 保持部分完成/Open。

### 样例复现

用系统 .NET Framework csc，引用 System.Windows.Forms.dll / System.Drawing.dll 编译该工具，输出到独立测试目录。传入全新目录：第二参数 `shell` 直接调用真实回收站 Drop、`shell-folder` 调用自有文件夹、`shell-leave` 仅进入退出；不传第二参数时显示原生 OLE 拖动窗口。真实鼠标自动化只在获得当次空闲确认后执行。私有时间线位于 `DevData/release-candidate-20261025`，不打包进应用。

## 当前更新范围与后置项

沿用 [52 项进度摘要](POST_0.2.1_PROGRESS.md)，未重新开发或扩大计数。44 项已实现/机器验证待人工；W-02 #9 当前 Win11 已验收待发布；三项部分完成 #8/#52/#54；W-03 #7 候选未启用；T-10 #50 有限未复现等证据；#53 继续观察；E-01 #36 仅契约待审阅、没有适配器。

候选包含已提交的窗口唤醒/更新/快捷导入、图库与管理/混排选择/拖放、分类图标/Sticky、标签及动画、性能、导入去重/任务恢复/导出、诊断、QQ 告知及 Telegram 可靠性。主要最近提交见进度摘要及 WP-B/QQ 收尾文档。

后置范围明确：W-01 未稳定归因的新环境边缘问题；W-03 未启用候选等待 Win10；T-10 等实际失效证据；#53 首次操作观察；#54 残余长尾正常体验；G-27 应用回收站确认；E-01 实际插件/传输适配。它们不写成已修复，也不强行启用实验来清零待办。

## 连续人工验收流程

日常仍只用 `DevData/Demo/Start-Demo.cmd`。以下是一次连续使用流程，**当前实际结果均为待维护者体验**，不是要求用户采样、计时或重复机器测试。

| 流程 | 预期行为 / 需确认内容 | 关联 |
| --- | --- | --- |
| A 打开图库 → 设置 → 工具，关闭重开，再最大化/还原、拖动缩放、托盘恢复 | 内容跟随窗口；原位置合理；圆角/阴影无异常；Win11 结果不代替 Win10 | #8/#9/#10/#57；#7 后置 |
| A 设置切换毛玻璃并重启，再独立切换动效 | 材质与 UI 动效互不混淆；标签原地向上呼出，无动效时静态线存在 | #24、窗口开关 |
| B 左树导航 → Relative 标签 → 展开嵌套 → 滚动长分类 → 管理选择 | 左树不被投影强制展开；虚线映射正确；Sticky 归属/折叠/交接正确；选择与发送按模式 | #28/#39/#41/#45/#55/#56 |
| B 资源/节点拖向标签，快速经过/停留/松手；节点间隙排序，再取消一次菜单/拖放 | 停留700ms只切投影；资源弹原菜单、节点直接移动；自身/后代拒绝；无漂移；重开顺序保持 | #16/#17/#18/#42/#43/#56 |
| B 将生成资源拖给外部受控文件夹 | 原件和多分类关系不变；回收站目前只处理副本，**不会出现应用删除确认**；实际聊天兼容仍待体验 | #52 |
| C 导入一组正常与重复资源 → 个别/全部决策 → 排序 → 导出/取消 | 任务身份稳定、进度真实；重复对照集中；成功清选择、取消不提交；渐进出现、关系/混排保持 | #26/#27/#38/#40/#46/#54、T-02/03/05/09 |
| C 在临时样本中做 Suzu迁移、资源包往返、旧包安全部分恢复及任务中断恢复 | 不动来源；正常兼容内容保留，拒绝部分有说明；恢复不是无条件重放 | #34/#47/#48/#58 |
| D QQ扫描/预览/导入/关闭 → 宿主菜单 → Telegram → OCR → 更新/导出诊断 | QQ告知可见；宿主持续失效仍收实际证据；恢复阶段可见且可取消；无凭据泄露；更新不自动安装 | #11/#35/#50/#51/#59 |

只在隔离数据中做取消/中断、删除及破坏性验收，不要求用户在真实 Library 上测试。每组可在对应 Issue 反馈正常体验与异常步骤，尚未反馈不能打勾人工验收。

## 本地候选构建与兼容检查

构建输入：`git worktree add --detach` 取得精确 `38c2910`，构建前工作树干净。沿用 `build_nuitka.py`、`scripts/build_distribution.py`、现有 Inno Setup 和 OCR 打包机制，不重写构建系统。产品版本号仍为0.2.1，**仅本地候选，不是重发同版本**；尚未批准下一版本号，不得上传这些文件到正式下载地址。

构建成功：Nuitka/MSVC standalone，应用目标 x64/SSE2（依赖与非AVX2硬件仍非本次认证），随后按既有清单生成 Portable、Installer、对应源码和可选 OCR 包。所有包位于项目 `DevData/release-candidate-20261025` 下，日常固定 Demo 不迁移到此处。

程序发布正向清单不包含 config、Library、DevData、编辑器文件、tests/tools/docs 候选补丁。对应源码归档保留提交中的研究文档与未启用补丁，**不代表运行启用**，也不把私人证据打包。七处工作区实验不在该提交中。

安装运行必须隔离目录、配置、Library、单实例身份。正式安装程序 AppId 与现有安装相同，不能为测试覆盖正在使用的安装记录；实际安装使用同一生成清单、仅替换测试 AppId/名称/位置的本地验证安装器，并禁止图标、自动启动和关闭其它应用。生产身份安装覆盖与安装向导人工体验仍待维护者。

### 实际结果与边界

| 验证 | 结果 |
| --- | --- |
| 原构建脚本与原发布布局 | 成功；输入38c2910，保护实验不混入；发布清单校验通过 |
| Portable ZIP解压后实际EXE | 正常显示启动、托盘方式启动、smoke自动退出均通过；不是源码运行替身 |
| Installer | 原身份安装包成功生成但未执行覆盖；隔离身份安装器真实安装成功，包内清单校验、实际EXE托盘启动与退出通过 |
| 旧版库与配置 | 从v0.2.1 tag `b1788f8` 源码生成4资源/4节点/13条混排及成员关系的隔离库；新EXE读取后这些表逐行相同，既有配置值保留，库路径不变 |
| 新设置默认 | 旧配置未含动效、毛玻璃及全局剪贴板导入开关时，当前ConfigService合并默认均为true；未冒称已覆盖所有设置组合 |
| 可选OCR | 沿用已存在的隔离运行时、从干净提交复制worker/帧与排版模块，重新打包；本地安装及真实离线推理、关闭worker通过。生成文字被识别为`NEKORI T TEST 2026`，非本轮精度验收；未下载组件、未在真实资源上推理 |
| 更新/失败回滚 | 既有更新测试覆盖中途失败回滚、下次启动恢复、数据不变；新编译Updater通过Windows原生测试，实际安装隔离标记应用并重启。未向真实安装更新，未改变正式更新源 |
| 相邻机制 | 外部副本/发布布局/更新/OCR数据与帧：29项及12子检查通过；Telegram反馈9项通过（模拟网络）；编译Updater原生1项通过 |

Telegram兼容边界：当前高级配置的Token/代理是工具会话输入（`TGStickerInterface._get_configured_downloader`），没有现成的跨重启持久化合同。本轮没有新增凭据存储或自动覆盖输入；已有自定义Token身份/恢复反馈测试通过。**不能把保留普通配置字段写成已实现跨重启恢复Telegram输入。** 如要新增保存能力，须另行决定，不在候选整理中悄悄实现。

程序清单不含私人配置、库、测试脚本或候选补丁。源码归档中的 `config/config.json` 经核对只是原有无路径的QFluentWidgets字体/主题示例，不是`data/config.json`；与#58已明确的开发连续性规则一致，保留示例，没有因名字中有config便无差别删掉。

本地文件（不上传）：`packages/NekoriEmojy-0.2.1-Windows-Portable.zip` 116,100,436字节；原身份安装包85,973,865字节；可选OCR包121,041,098字节。名称中的0.2.1来自现有元数据，只表示本地构建输入，不能覆盖正式Release。已有打包器照常生成manifest/校验文件，没有额外哈希审计。

构建专项入口：`DevData/release-candidate-20261025/Start-Portable-Check.cmd`，只供此次包验证，显式指向生成的compatibility配置/Library。**不要直接双击未设置隔离环境的包内EXE进行用户库实验。** 默认日常验收仍是固定 `DevData/Demo/Start-Demo.cmd`，持续库与排序不重置。

私有证据：同目录 `native-results.json`、`shell-*/events.txt`、`package-results.json`、`compatibility/compiled-result.json`、`install.log`、构建/OCR日志与生成样本。均留在DevData，不进入发布清单。诊断样例提交`9e63db3`；本轮没有新的产品修复提交。

升级边界：候选仍标0.2.1，没有把正式0.2.1到同版本当成一次真实在线升级。原更新协议的隔离正常/故障回滚与编译辅助程序重启已验证；未来确定版本号后的真实旧安装覆盖、正式AppId向导及整套端到端升级仍待验收。
