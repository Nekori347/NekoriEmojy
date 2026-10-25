# W-02 连续缩放回归与长期门槛（2026-10-26）

接管 `ef5428b`；安全规范独立提交 **`d98cdce`**。本轮**未找到可安全提交的缩放修复，未修改业务源码**。#9 保持 Open：左/上及相关顶角连续缩放抖动仍未闭环，不进入最终发布验收。下文的 `5d784f3` 及旧人工验收保留其原有范围，不能代表连续过程视觉稳定。

## 事实与定位边界

维护者确认固定 Demo 右/下稳定、左/上及顶角内部剧烈抖动。本轮在 Win11、DPR1.0 的生成图库中，以系统鼠标连续外拉、反向和返回，采集自身 HWND 矩形、NCCALCSIZE / SIZING / WINDOWPOS 消息、Qt Move/Resize/Paint 及桌面图像；只在隔离进程内短时观察，无正式程序注入或永久诊断。

- 有效顶部和左侧实拖的下/右锚点最大误差为 **0px**，内容容器记录的局部位置保持 `(0,0)`；未捕获正常尺寸恢复逻辑在普通缩放期间反复 `setGeometry()` 的证据。不能由此证明画面稳定，也不能证明所有布局没有问题。
- 桌面画面相对当时 `GetWindowRect` 的裁剪原点出现位移，但**普通 Qt 原生边框窗口对照也有同类位移**。进一步以同帧标题标记校准，120资源、未强制原生化子控件的顶部19个有效帧，标题与侧栏文本相对位移均为0；左侧32帧只差0–1px。原始截图偏移混入了窗口呈现与采样原点不同步，不能把它直接报告成“内部UI抖动已稳定复现/根因是DWM”。
- 因此，A（外框/几何竞争）在已测样本没有证据；B（内部几何反复变化）未取得确证；C（呈现/重绘）仍需进一步证据，**尚未在B/C之间完成归因**。维护者的实际异常保留，不能用采样局限否定人工反馈。

| 隔离对照 | 有效证据及结论 |
|---|---|
| 当前宿主 Acrylic 顶部/右侧 | 顶部20个有效图像帧、右侧30帧；锚点0px。顶部原始偏移−16至+10px、右侧0，但原始偏移不能当作内部抖动幅度。首次左侧未进入缩放，作废。 |
| 当前宿主 Opaque 顶部/左侧 | 21/37帧、锚点0px；原始偏移仍出现。关闭材质未形成可接受的修复证据，不作为产品方案。 |
| 恢复 WVR_REDRAW 的试验 | 顶部28帧、左侧39帧；未取得消除画面异常的可信证据，不提交。 |
| 附加 SWP_NOCOPYBITS 的试验 | 顶部26帧；未取得改善证据。Qt 6.11.2 的 handleGeometryChangingMessage 已在实际尺寸变化时设置此位，应用再加没有充分依据。 |
| 120资源/普通Qt窗口控制 | 用于识别采样混淆和卡片异步加载干扰，不替代真实宿主验收；原生Qt对照顶部28帧也出现相对裁剪原点偏移。 |
| DwmFlush/CAPTUREBLT/系统SC_SIZE补充 | 最后会话没有进入真实缩放，明确作废；未用其宣称同步捕获成功或测得实际显示FPS。卡片模板匹配失败组也作废。 |

上述候选只在 `DevData/resize-stability/probe.py` 的一次性隔离运行中替换方法，**没有应用到 Source 或固定 Demo**。本轮停止继续堆叠宿主补丁，未升级Qt/窗口库、未改圆角/Mask/Alpha、未添加补偿定位/刷新或节流。该探针有未同步屏幕帧及手势建立的限制，仅保留本地用于追溯，不纳入回归通过门槛。

## 已核对的责任层与相邻保护

- `fluent_ui/window_shell.py::NekoriWindow.nativeEvent`：继续沿 `5d784f3` 的自有子窗口边缘让路及标题栏捕获处理；旧正常态 NCCALCSIZE 的 WVR_REDRAW→0 路径没有因本轮猜测而改写。
- `fluent_ui/main_window.py::_remember_normal_geometry / _apply_normal_geometry / changeEvent / moveEvent / resizeEvent`：普通调整记录正常几何，恢复路径另行负责状态切换。未确认多个定位处理器竞争，因此未删除恢复机制。
- Qt 6.11.2 `qwindowswindow.cpp / qwindowscontext.cpp / qwindowsbackingstore.cpp` 与 Microsoft NCCALCSIZE 文档只用于解释消息及复制行为；不照搬补丁。对应只读文件留在私有 references 目录。
- 本轮无业务源码变化；复用前轮16项Windows机制/生命周期、Acrylic三宿主24次边界实拖、Opaque三次右下角、六组42状态快照等已有证据。**这些不是本轮八方向连续视觉验收**。顶角/最小尺寸/三宿主全过程稳定性尚未完成，不能报告完整交叉回归通过。#60及#57保持原结论，不无证据重开或称解决。
- Win10、混合DPI及安装形态未验收。W-01七处原工作区差异保留、不暂存；W-03候选未启用，T-06/T-07及原Library/发布端未动。

私有证据位于 `DevData/resize-stability/`（生成样本、trace、GIF和对照图）；不提交原始桌面素材或私人运行资料。固定Demo使用其当下持续数据，重启前后以完整表行/混排顺序对照，最终结果见CURRENT。

## 长期安全门槛

唯一权威规则仍是 [README：维护回归门槛](../README.md#维护回归门槛)，`d98cdce` 将信息/隐私/数据边界、实际暂存检查、实际发行输入输出检查及用户化Tooltip表达并入现有回归流程；安全报告仅引用，不维护第二清单。

本轮复用隔离 `main.py --smoke-test`，输出 **NEKORI_STARTUP_OK**；使用HEAD宿主模块，不加载七处窗口实验。

本轮只读检查 `.gitignore`、现有正向打包清单/构建脚本；`tests/test_release_layout.py` **2项通过**。未生成新Portable/Installer/源码/OCR附件，不将清单测试等同实际发行产物已检查。规范提交前实际index仅README和安全报告引用，未含配置实例/凭据/资源/日志/实验；没有删除本地配置、改写历史、上传资料或取消合法兼容功能。

---

## 以下为前轮阶段记录（不代表连续缩放回归已解决）

# 窗口与共享状态回归收敛（2026-10-26）

接管 `69e0aa0` / dev/post-0.2.1。#9 已按真实回归重新 Open；保留旧人工验收历史。本轮源码：**W-02 `5d784f3`；共享状态 `aa0da3a` / `bee0e5f`；HSV调查 `36454ea`**。机器验证后仍待维护者体验，不Push/发布。

## W-02：真正接收消息的窗口与顶层不是同一个

- 初次、未原生化的隔离 Main/Settings/Tool 三个窗口24次实拖全部成功；不能代表长期运行实例。
- 运行中 Demo 的顶层 HWND 有 WS_THICKFRAME，四边返回10/11/12/15；但 WindowFromPoint 指向内容/标题栏子 HWND。它们覆盖宿主边缘，子窗口返回 HTCLIENT=1，所以只测试顶层会假绿。正式版用户反馈保留，采样时其主窗口隐藏，未注入代码或操作真实数据。
- 隔离窗口调用现有 Qt winId 原生化后稳定重现。Qt 明确说明 winId 可使 alien widget 取得 native handle；不能凭此推断某个具体业务入口创建了运行中子窗口，本轮未将创建来源猜为 G-27、Tooltip 或T-07。
- `native_resize.resize_hit` 直接提取原有八方向/DPI几何，不改变尺寸或判定规格。一个局部 Qt native filter 仅让 **自有子 HWND、宿主边缘、正常可缩放状态**返回 HTTRANSPARENT；Windows继续同线程下层命中，最终宿主负责系统缩放。内容、菜单、最大化/全屏不拦截。无全局鼠标Hook/定时器/重建HWND/新窗口模型。
- 相邻回归发现标题栏原生子 HWND 的隐式鼠标捕获令双击中先发送的SC_MAXIMIZE不生效。捕获释放前/后A/B及独立失败测试确认；共享标题栏仅在有效双击时释放本宿主所属子捕获，再执行原库行为。没有重写拖动或最大化算法。
- 官方依据：[Qt QWidget::winId](https://doc.qt.io/qt-6/qwidget.html#winId)、[Microsoft WM_NCHITTEST / HTTRANSPARENT](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-nchittest)。T-07原观察链不改；新filter是输入路由而非第二条诊断链。

## 已完成验证与明确边界

| 范围 | 实际证据 |
|---|---|
| Windows机制/生命周期 | `test_native_child_resize` + `test_window_host_native` + `test_window_maximize_lifecycle`：16项通过；覆盖真正子接收者、内容不拦截、双击捕获、flags/关闭重开及#57。新用例先出现1 != -1及双击不最大化的失败，修后转绿。 |
| Acrylic | Main、Settings、ToolWindow各8方向实拖，**24/24**改变正确边界尺寸；不是仅查询HT。 |
| Opaque | 三个宿主各右下角实拖通过，另核对全部HT结果；不称为48次全方向实拖。 |
| 六组共享行为 | 首次/关闭重开的最大化还原、标题拖动/双击、最小化与隐藏恢复；共42个尺寸快照通过Qt/Win32客户区、标题宽度、Alpha及layered检查。主窗口隐藏恢复沿实际窗口组/托盘恢复入口。 |
| 内部交互 | 原生补验管理按钮切换、导入菜单显示并取消、收起标签条点击展开通过。早期脚本错读manage_mode而中止，修正为mode后只补内部组；原失败记录保留，不隐藏成整组绿灯。 |
| 视觉 | 查看生成样本的真实桌面截图，未发现新的圆角、Acrylic/Opaque、背景/客户区错位。未修改任何圆角/材质规格或资源外框。 |
| 邻接数据/拖放 | 管理、Windows OLE、顶部标签拖放组合37项通过（含共享用例），未将模拟网络/Qt事件冒充真实聊天发送。 |
| 基础冒烟 | 复用 main.py --smoke-test，独立空Library/配置、无自动网络/全局快捷键，输出NEKORI_STARTUP_OK。 |

环境：Win11、DPR1.0、主屏可用3392×1440。**Win10、150%/混合DPI、正式安装版运行形态未验收**。发布端及原始Library未修改；不能宣称已修复用户当前运行中的旧exe。

私有证据：`DevData/host-regression/{acrylic,opaque}/native.json`、`controls.json`、`running-readonly.json`、`demo-restored-readonly.json`。鼠标验证一次超出预估，未将该问题掩盖为数据结论；后续不重复通过组。持续Demo以重启前的真实表行与排序快照为准，不从历史120项数量回填资源。

## 共享 Hover / Focus：复用现有状态入口

#60：`ButtonPaint`在Show、几何、重设父级、EnabledChange、UngrabMouse等既有生命周期节点，使用原单次合并计时器校准实际命中，隐藏清理瞬态；不轮询。`pointer_hits`排除覆盖、隐藏、禁用和非活动窗口。

标签收起条原先独立用几何判断Hover、hasFocus画框；现接入既有ButtonPaint/输入来源跟踪，鼠标焦点不再冒充持续键盘提示。分隔柄也复用**同一个**输入来源；即使鼠标操作不移走Qt焦点，也结束旧键盘提示。Checked/Expanded业务状态不被清理。

横线与Chevron统一读取text_secondary/Accent，既有线段及折线几何不变。七个针对性绘制/控件用例通过；四停靠/颜色取消保存相邻用例通过。Tooltip过滤器未发现吞Enter/Leave或修改业务选择的证据，本轮不归因或重写Tooltip。

实时预览开关的Checked底色与Hover是两件事；开关/更多均32px但位于不同行。弱线框及同一基准作为后续UI-A事实依据，本轮不擅自重做设置栏或实装待确认图标。HSV #61仅调查，见 [详细测量](HSV_INTERACTION_INVESTIGATION.md)。

## 为什么原回归漏检，今后如何收敛

原窗口测试偏重冷启动、顶层HT和右下角，未覆盖内容原生化后真正接收消息的子 HWND，也未覆盖该状态下的捕获/双击。控件各自判断geometry/focus/hover，缺少共享生命周期与输入来源；这不证明所有旧症状都只有同一个原因。

统一规则已写入README“维护回归门槛”：基础冒烟 + 依赖范围相邻回归 + 阶段候选集成，显式区分offscreen/windows、工作树/已审阅宿主、机器/人工。新native child测试复用既有#57 fixture装载审阅index模块，避免W-01实验假绿。没有新测试框架或重复台账。

一次19项旧组合出现2失败/2错误：窗口类offscreen测试使用Win32句柄导致1400；另有既有工具栏3px对齐断言。加载修改前controls/panel_host后，选取的两个失败仍复现，属于基线/平台问题，未删除断言或更改无关布局。真正窗口门槛改用windows运行并通过16项；不能把旧组合说成全部通过。

七处原实验在扣除#9的必要新增后逐字节内容一致，暂存区检查未夹带实验；W-03原补丁对新提交git apply --check通过，仍未启用、未改写。#57、T-06/T-07及其它源码保护不变。只更新#9/#60/#61/#37及必要引用，均不关闭。

---

## 以下为2026-10-25历史快照（不作为当前验收状态）

# WP-A 责任层与项目状态收尾

2026-10-25；接管 `dev/post-0.2.1` / `3f6bdb1`。本轮仅记录、状态同步和有限窗口回归，**没有新增业务源码修复，也没有吸收七处实验**。已发布版本仍为 v0.2.1。

## 当前结论

| 事项 | 当前状态 | 证据与剩余范围 |
| --- | --- | --- |
| W-01 #8 | 部分调查／跨系统材质轮廓仍受阻 | Win11 当前原生轮廓路径未复现历史 Region 外 Acrylic 合成问题；不能将本轮通过当作旧机制问题已解决。保留 `79ea7ae` 及 WP_A_W01.md 证据；停止本轮主动试验，待实际反馈环境或合成层新证据，不承诺进入下一版。 |
| W-02 #9 | 当前环境已人工验收／待发布 | `f6fc10f`；既有用户验收加本轮 Win11 回归，按验收范围闭环；Win10、其它／混合 DPI 未验收，不据此否认这些环境的独立风险。 |
| W-03 #7 | 隔离候选／未启用，等待外部 Win10 验证 | `b465927`；当前基线补丁可应用，不等于效果获验收；未列入默认运行或正式发布计划。 |
| #57 | 已实现／机器验证／待人工 | `da33e08` 消除过晚 Alpha surface 切换并保留原生样式，`5f74b91` 还原图标轮廓；本轮回归通过，不重写 HWND／几何管理。 |

## 实际责任层

- 主窗口继承 `NekoriWindow`；设置窗口及 `ToolWindow` 经 `NekoriOwnedWindow` 复用同一宿主和标题栏。Owner 的 present/fit/center 负责显示和可用区域约束，不负责资源导航或材质策略。
- `materials.native_material()` 是原生材质责任层，缓存键含 HWND／明暗主题／实际启用状态／overlay。17763 以上且系统与用户策略允许时使用 Acrylic；否则使用 opaque。`window_acrylic_enabled` 经启动环境策略控制，保存后重启；它与 `ui_animations_enabled` 是不同开关。
- `shell_color()`／宿主 paintEvent 负责 Qt 表面与轻量轮廓；Qt 绘制圆角不等于原生 Acrylic 已裁剪。`sync_native_clip()` 负责 Qt Region：Win11 原生轮廓及最大化／全屏清除 Mask，后备路径使用圆角 Region，不能保证 Accent 合成面按 Region 裁剪。
- #57 已删除宿主构造后期的 WA_TranslucentBackground 设置；在 HWND 重建及样式更新边界保留 WS_CAPTION／WS_THICKFRAME。八方向命中使用原消息坐标及 DPI；不是依靠不断重设尺寸。
- MainWindow 保留 `_normal_window_geometry`／`_geometry_transition` 等恢复逻辑，本轮没有新证据要求删除。T-07 仍被动观察原消息，未新建并行过滤器。派生宿主与主窗口没有另外复制修复。
- 当前 opaque show 路径仍有短暂 windowOpacity reveal；这与已删除的过晚 WA_TranslucentBackground 不是同一个机制。本轮静稳采样未见其残留 layered 状态，不以此推断所有窗口动画都已移除。

固定 Demo 明确从 **当前 Git HEAD** 装入 materials／window_shell／main_window，避免把未提交 W-01 实验当作已提交功能；其它模块使用工作树。直接启动任意源码入口不具备这一隔离保证。

## 七处受保护改动逐项判断

“可吸收”仅指有价值的后续审阅方向，不是合并授权或本轮决定；七个文件均保留工作树原状态。

| 文件 | 实验内容 | 本轮判断 |
| --- | --- | --- |
| docs/POST_0.2.1_HANDOFF.md | 修正 G-01／G-12 历史需求描述 | 有价值的事实修正，可后续独立吸收；不是窗口修复，本轮不暂存。 |
| docs/POST_0.2.1_PLAN.md | 同步上述用户需求边界 | 同上，保留，不因“窗口实验”称呼而误删技术记录。 |
| fluent_ui/main_window.py | 删除重复 apply_rounded_corners 包装及部分 DWM 变更调用 | 与共同宿主责任收敛方向相符，但原生调用有缓存，不能凭调用次数认定实际成本或根因。没有新复现支持整体替换，保留待证。 |
| fluent_ui/materials.py | 原生轮廓／Alpha 判断、DWM 边距与缓存；同时强制 Win10 常态 opaque | 其中 contour 意图部分与 #57 消除 Alpha 冲突重合；但 Win10 全时 opaque 违背保留静止 Acrylic 的要求，**不采用整块实验作为发布修复**。其它改动无新的独立效果证据，保留。 |
| fluent_ui/window_shell.py | 删除 opaque reveal、状态变化同步 clip、统一材质系统消息 | #57 已吸收用户明确授权的单行 late-Alpha 删除，其余不等价于 #57。共用事件收敛有潜在价值，但状态 clip／reveal 删除未证明必要，不合并。 |
| tests/test_ui_tail.py | 对应删除包装入口，改测 hide/show clip | 依赖尚未采用的源码实验，保留，不以测试改名证明修复。 |
| tests/test_window_resize.py | 删除旧包装测试与导入 | 仅在旧入口真正删除时才可考虑，不单独删除回归保护。 |

本轮无 reset／stash／清理，七处没有被暂存或修改。保留 #57 授权吸收的既有行，不逆向恢复已确认故障。

## W-03 候选的当前兼容性与交付条件

在 DevData/wp-a-closeout/candidate-head-check 中从 HEAD 提取两个已提交模块，对原 `W03_WIN10_MOVE_CANDIDATE.patch` 执行 git apply --check，**通过**。检查目录不等于新的长期工程或运行实例，未向工作树套补丁。

- 候选复用 `native_material()` 的 enabled 缓存；Win10 明确 SC_MOVE→ENTER 才临时 opaque，SC_SIZE 不切换，EXIT／CANCEL／隐藏／状态／HWND 丢失清理。现有 `_transparency_allowed()` 包含用户毛玻璃关闭策略，因此关闭时不启动降级，也不会在退出后强开材质。
- 补丁没有重新加入 WA_TranslucentBackground，也没有改变 #57 的样式保留、Mask、圆角或 paint 路径；同一 nativeEvent 中转发，不接管 T-07 统计。
- 现有五项替身／消息检查来自原候选记录，本轮没有反复运行不能回答 Win10 视觉问题的 Win11 合成实验。
- 具备在**独立、干净、同基线的 Win10 测试副本**应用候选的机械条件；应先做 git apply --check，再应用补丁。不要在当前七处脏文件上套用，也不要覆盖正式安装目录。使用隔离配置／Library，保持默认 Demo 不启用。
- 尚未制作或运行 Win10 安装包，也没有外部视觉结果。应用补丁后的性能、闪烁和材质交接仍未知；恢复 API 失败时可能暂留 opaque，不能把成功返回等同于视觉恢复。

外部只需一次少量检查：正常拖动的起步／跟手／停止；松手及 Esc 后 Acrylic 是否恢复、有无闪烁漏底；圆角／阴影；一次最大化还原、边缘缩放和标题按钮。无需重跑此前高频移动实验。材料切换不可接受则撤回候选，而不是增加定时器补救。

## 本轮 Win11 验证

当前屏幕 DPR 1.0，可用区域 3392×1440；主窗口、真实 SettingsWindow、带可见内容的共同 ToolWindow；Acrylic／opaque 分别使用独立进程和配置。测试数据为生成的小样本，原始用户 Library 与持续 Demo 数据均未用于写入实验。

先完成一次不操作系统鼠标的 Qt／原生状态预检查，再经用户允许完成一轮原生鼠标回归。记录位于私有 `DevData/wp-a-closeout/{acrylic,opaque}`，截图为实际桌面窗口区域，不公开用户资源。

- 六组真实标题拖动均产生位置变化 **(51,26) px**；右下角原生缩放均为 **(+32,+24) px**。多段移动超过系统拖动阈值，先校验前台 HWND 与实际落点，避免把工具调用成功当作拖动成功。
- 六组各核对八方向 WM_NCHITTEST；这是 48 个命中结果，**不是本轮重新做了八方向全部实拖**。W-02 的完整实拖人工验收沿用已有证据。
- 标题栏按钮执行首次及关闭重开后的最大化／还原，恢复到各周期正常几何；原生系统标题双击执行最大化／还原；最小化恢复、隐藏重显及主窗口托盘恢复通过。
- 原生运行共有 **42 个状态快照**：Qt 与 IsZoomed 一致、Qt 几何与 Win32 客户区匹配，标题栏同步宽度，静稳 Alpha=-1、非 layered。关闭重开允许 HWND 正常变化，不错误断言整个进程必须同句柄。
- 实际窗口截图检查未出现 #57 的“背景铺满、内容旧尺寸”现象，未识别到需要新增补丁的稳定 W-01 故障。原生轮廓属性／API 接受本身不构成像素级圆角或阴影验收；截图裁到窗口边界，完整外阴影未做定量评估。派生窗口 Acrylic 可透出 Owner，不将其直接当成圆角失效。
- 未进行多显示器、不同 DPI、Win10 或安装／ZIP 打包形态验收。不能据此关闭 W-01、W-03 或代替 #57 人工体验。

本轮没有持续日志／采样／重绘开销，没有新业务代码、窗口库升级、材质切换默认行为或计时器补丁。

## 项目管理与停止点

#58/#59 正文已纳入 d6fcc9a、0552c45、46e13b2 和 3f6bdb1；保留旧评论，不重复发送同一结果。两项待人工验收。
#37 以 52 个子事项为当前总数，旧的 47 等统计明确保留为历史快照。T-06 已实现，E-01 仅契约预留；不把 Open 当作未开发。
W-02 按既有当前环境人工验收闭环／待发布；其它窗口项按表保持 Open。没有新建窗口 Issue。
CURRENT 使用精简入口，旧 CURRENT 时间线转存现有 ProjectDocs/CHANGELOG.md，技术上下文没有删除。固定 Demo 入口和持续数据不改变，停止于人工验收；不 Push、不发布。
