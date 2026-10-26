# Tooltip 渲染与提示文案入口（2026-10-26）

TP-A基线 **84e3d00 / dev/post-0.2.1**，源码 **436a097**，仍待人工验收；不把已复现原因外推为所有历史黑块唯一原因。追踪 [#62](https://github.com/Nekori347/NekoriEmojy/issues/62)，关联 #37/#60/#24。TP-B最新实施状态见下节，旧入口/候选与事实表保留为当时记录。

## TP-B 第一批锁定映射实施（2026-10-26）

基线 **28be368**，源码 **11b8451**。只按负责人提供的第一批四语言映射实施，不自主创作文案或译文。**部分完成/机器验证/待人工；TPB-222输入接入暂缓，其它未审定文字不扩展。**

| TPB编号 | 实际状态 |
|---|---|
| 036 | 筛选浮层与同一状态筛选Chip同步使用“找不到文件的表情”，不改missing判断；检查完成等其它文案不动 |
| 039、041、054、058、059、061、081 | 中文源键不变，补齐指定四语言；数量/name占位符原样 |
| 062、063、064 | 正常资源态显示正式说明；节点/混选禁用原因优先；说明由_sync_command_bar这一入口绑定，不再被button.text覆盖 |
| 065 | 调整位置Tooltip换成正式映射，不改手动顺序可用条件或排序持久化 |
| 074、082 | 只替换指定全局删除后果与ROOT来源拖放说明；回收站文件/副本、取消等其它警告保留 |
| 141 | 名称和副描述为两个独立源键，四语言同步；配置键gallery_node_icon_size不变 |
| 220 | 当前按钮与每次构造的导出菜单共用“保存到表情库并导出…”；旧输入对话框标题未列入映射，保持 |
| 225、226、229 | 进度、部分保存失败、失败标题按正式映射；原具体错误详情与处理路径保留 |
| 044、073 | 仅更正zh_TW，中文及现有en/ja不变 |
| 222 | 两段四语言映射已录入，但未接入产品弹窗；保留旧输入提示，原因如下 |
| 029～031 / F1 | 保留三种排序片段及含义；直接逐片翻译后setToolTip，由已有refresh_texts在语言切换时刷新，不再将译文组合交bind_text二次查译 |
| F2 | 与062～064同一绑定修正；节点单独移动仍使用原“移动到分类”提示，不把资源专用说明套到节点 |
| 090、092、094 / F7 | ActionPolicy.delete_label源键不变，工具栏与右键菜单均翻译同一键；刷新不再用原中文覆盖 |
| 235 | 只将旧测试子串改成现有“拖动表情至聊天窗口”；Enter键帽/换行断言保留，产品说明及发送语义未变 |
| 221、230～234、其它未审定条目 | 未补译、未显示旧隐藏控件、未修改 |

### TPB-222 的实际布局限制

按批准全文试接既有prompt_text：第一行放原正文QLabel，第二段放原hint信息区，没有新增确认窗口。Win11实际Qt四语言弹窗：512px宽，信息区480px；风险说明所需高度zh/zh_TW/en为30px、ja为45px，实际均足够。但日文第一行非换行QLabel文字约504px，内容只有480px，桌面截图证实末端裁剪。offscreen另有提示区高度偏小（28/30、33/45）的表现，不能与Windows信息区已正常的结果混写。

遵照“无法完整呈现先报告，不删短或重设计”边界，已撤回这次弹窗接入；只保留指定的两段四语言资源和测试映射，等待对现有正文换行/布局责任的后续明确处理。**不把有已知裁剪的新提示提交为可用功能，也不擅改通用Dialog或KeycapLabel。** 临时截图和探针仅本地生成样本，未提交；222未称通过。

### 映射、检查与边界

- 锁定映射的测试样本：`tests/fixtures/tpb_batch1_copy.json`，从附件逐语言/段提取；仅为核对样本，运行时仍只有原translations体系。20个完整映射组（141/222各拆两个源键）、2个繁中勘误：每种语言22个键，繁中另2个，合计90个指定单元；旧键保留供其它上下文/隐藏旧控件使用，不做全局清理。
- 新增8项精确映射/占位符/绑定/状态/安全替身测试，加旧键帽1项、TP-A绘制5项、#60生命周期8项，共22个不同用例最终通过（分组运行）。三种排序×四语言、正常/节点/混选、单资源存在/缺失/批量删除标签、TG真实菜单创建/语言切换及进度/失败替身均覆盖，不触发删除或真实网络。只更新了235对应旧断言，没有删其它断言让检查通过。
- Win11真实Qt控件：四语言排序/正常工具栏提示、141设置名称/完整副描述及截图检查通过；en/ja新提示正常换行，141副描述高度足够。独立main启动退出冒烟通过。TP-A主题切换字形及#60状态测试通过，未改其实现；未重复窗口缩放/性能/网络套件。
- 额外核对实际JSON差异，只有指定键和值改变，无删除旧键；044/073的en/ja未改。暂存仅本批11个源码/语言/测试文件，无W01实验、私人数据/凭据、Demo数据或新增网络端点。已有帮助中的Token形状示例为HEAD原内容，未新增/更改。
- QTest控件/截图不等于维护者验收；Win10/混合DPI未测。TG未知错误原有t(message)路径可能包裹MISSING，具体原因仍保留，本轮未扩展错误翻译机制。真实发送、网络下载、入库或删除未测试。其余TP-B正式映射待审，#62保持Open；W02暂停、W03未启用、七处实验/T06/T07及固定Demo数据保护保持。

## TP-A：事实、责任与修正

| 提示来源 | 当前路径与责任 | 本轮结论 |
|---|---|---|
| 普通 QWidget / 分类树 item 提示 | `main.py` 安装 `components/tooltip.py::GlobalToolTipFilter`；统一 `TooltipSurface` + `KeycapLabel`，item 的 ToolTipRole 也转入同一弹窗 | 本次确认的故障层 |
| 原生 QToolTip | 未安装过滤器的入口或显式调用；QSS 见 `visual.window_style()`，应用 Palette 见 `window_shell.apply_shell_theme()` | 隔离真实宿主深浅主题均可读，Inactive Text/Base 正确；未复现独立的原生合成黑块，不修改宿主 Palette |
| Fluent 提示 | 依赖库有 `ToolTipFilter` / `ToolTip`；应用源码无直接注册这种过滤器，代表宿主未发现该类实例 | 不凭依赖存在就宣称发生双提示，不重写第三方体系 |
| 任务状态提示 | `StateToolTipManager` 实为 `feedback_for()` / 标题反馈通道的兼容门面，不是鼠标悬停窗 | 不改任务生命周期与通知 |
| 图片 Hover 预览 | `HoverPreviewPopup` 为独立 Qt.Tool 图片/元数据窗口，其标签另有普通 Tooltip | 不混为 Tooltip 渲染故障，不改动图解码或窗口层 |
| 菜单 / 托盘 | SafeRoundMenu 的菜单项绘制与原生 Shell 托盘提示独立；item 若发 ToolTip 事件再走全局路径 | 不改菜单外观、交互或系统托盘提示 |

### 已复现的黑块

隔离的真实 MainWindow 中显示排序按钮提示，再由浅色切换到深色并执行现有主题刷新：提示保持可见，背景已变为 `#292d27`，文字仍为 `#222720`，预期文字是 `#eeeee8`。真实桌面抓取能看到几乎不可读的暗块，属于**文字与背景对比度异常**，不是已经证明的 HWND/Alpha 故障。

原因：`TooltipSurface.paintEvent()` 每次读取当前主题背景，但 `GlobalToolTipFilter._show_text()` 仅在显示时把文字颜色固化进局部 QSS；可见弹窗没有主题同步入口。KeycapLabel 的 QTextDocument 使用 Palette.Text，这条局部颜色还会覆盖父窗口新 Palette。因此只改全局 Inactive 色或最近的 Tag Surface 都不能修正此明确路径。

修正仍在原 TooltipSurface：用已有 `visual.theme.changed` 同步字体及 Text / WindowText / ToolTipText、Base / ToolTipBase 的所有颜色组；透明 QLabel QSS 不再固化主题文字色。背景仍沿原圆角自绘，不新增底板、阴影、窗口材质或第二弹窗。显示/复用时也应用同一入口。

另确认两项边界：

- 固定 Demo 原先**遗漏**正式 `main.py` 已有的 `install_global_tooltips()`，因而此前不能用 Demo 原生提示证明正式版自绘提示已修复。本轮仅补同一安装入口及原 tooltip_delay 配置；并未复现“遗漏过滤器必然黑块”。
- 原过滤器只处理目标自身 Hide，宿主隐藏或失活时未取消待显示任务。现宿主 Hide / Close / WindowDeactivate 取消原单次延时并隐藏同一提示；不吞正常输入、不修改 ButtonPaint 的 Hover / Pressed / Focus。自动用例包含延时尚未触发时的宿主退出。

### 与历史修复的关系

- `14a67ab` 从 Fluent ToolTip 改为单一自绘、透明背景的 TooltipSurface，并消费原生提示事件；这套实现仍在，未回退到旧 Fluent 窗口。
- `d67e721` 只将 QLabel 换为 KeycapLabel 以绘制快捷键键帽；本轮不移除键帽或重写共享标签。
- 后续窗口收尾记录只排除了过滤器吞 Enter/Leave 的证据，没有证明所有 Tooltip 黑块已经消失；UI-A/B 记录也明确将它留作独立反馈。
- 本次复现不需要 Tag Panel 覆盖层，简单宿主也能触发；未找到证据将它归因于最近 Tag/公共外框修改。不触碰 W-01/W-02/W-03 或 #57。

### 针对性验证

- 新增 `tests/test_tooltip_rendering.py` 5 项：真实 QTextDocument 字形像素、可见弹窗双向主题切换、Active/Inactive/Disabled 文字角色、宿主关闭/隐藏/失活及待显示取消、屏幕边界定位、Leave/复用/单弹窗。
- 加上既有 #60 生命周期 8 项、原 Tooltip 复用和卡片/树 Hover 2 项，**15 项通过**。
- 额外运行的旧 `test_ui_polish::test_keycaps_are_painted_objects_and_wrap_without_losing_text` 在本轮及加载 HEAD 原 Tooltip 的基线中均失败：断言要求“拖到聊天窗口”，现有说明是“拖动表情至聊天窗口”。保留该已存在的文字断言失配，不修改无关文案/测试或称全部测试通过；新用例已核对实际字形与键帽内容绘制。
- Win11 / Qt Windows 平台的真实 MainWindow、SettingsWindow：Acrylic 与 Opaque 各深浅主题 × 分类树、顶部排序、图库分类节点、Tag 控制、设置工具按钮，**20 组可见提示检查**。另核对显示中主题切换、单弹窗、鼠标 Leave 后按钮 Hover/Down 清理；桌面抓取可读、圆角无额外黑底。正常资源卡片原本没有普通 Tooltip，不伪造其提示来验收图片预览。
- 原生 QToolTip 的真实宿主深浅对照正常；独立配置/Library 的 `main.py --smoke-test` 启动退出通过。临时探针和生成数据在本地 DevData，不进入源码/Issue。
- Qt 控件输入及有限桌面截图不等于维护者最终体验。Win10、混合 DPI 和实时系统外观切换未验；尚不能解释未复现的其它合成型黑块。停止于本次定向范围，若仍出现需保留具体入口及主题/激活条件。

## TP-B：下一工作包的入口范围

### 第一阶段事实材料（2026-10-26）

本轮仅采集，详见 [TPB_COPY_FACTS.md](TPB_COPY_FACTS.md)：235条入口/状态记录（A94、B22、C103、D16），保留现有四语言、触发条件、实际业务及副作用。272个不同翻译源片段中，zh_TW/en/ja各缺23个精确键；另列动态绑定差异与未调用翻译的状态覆盖，不混为字典缺失。未改用户文字、翻译、断言或业务，也未开展GUI测试。

后文候选是此前源码入口调查，不代表当前可见性已核实：现QQ/TG的ImportBench隐藏旧配置卡片；TG导出菜单只复用旧按钮文字，未复制其长Tooltip。最新事实表已将隐藏旧文字、当前菜单及真实入库/导出链分开。正式文字取舍和四语言映射等待指导AI/负责人确认，TP-B尚未实施或验收。

按当前源码 AST 核对到 **138 处直接 Tooltip 赋值调用 / 38 个文件**：含 setToolTip、setTabToolTip、bind_text(..., setToolTip)。这是**调用点数**，不等于独立文案条数，也不含所有构造器、循环生成项、菜单文本和服务错误。下面按真实责任入口整理，避免按关键词全局替换。

| 入口族 | 主要源码入口 | 待治理对象 / 保护边界 |
|---|---|---|
| 顶部图库、管理与过滤 | `presentation/workbench.py`；`views/gallery_view.py` 的 `_build_command_bar`、`_show_filter_menu`、`_build_selection_more_menu` | 图标动作说明、搜索过滤、全选范围、加入/移动/删除区别；不能删除关键后果 |
| 左树与分类导航 | `presentation/sidebar.py`；`components/library_tree.py` 的 item ToolTipRole；`navigation.py` 的 SortCycleButton、层级标题、TabStrip | 当前排序与持久顺序、真实路径、子分类/直接内容计数；动态名称不是翻译键 |
| 图库分类/资源/快速面板 | `node_card.py`、`sticky_category.py`、`virtual_gallery.py`、`emoji_card.py`、`quick_panel.py`、`presentation/quick.py` | 分类路径/计数、缺失文件；正常资源普通提示为空，图片预览另审，不能诱发额外元数据查询 |
| 图片预览 | `components/hover_preview.py` 的名称、路径、分类、标签 | 长文本/文件信息的必要性、缩略/完整内容一致性；不输出私人资源清单作样例 |
| Tag 与折叠/索引控件 | `tag_panel.py`、`panel_host.py`、`section_index.py`、`sidebar_icons.py` | 展开/收起、筛选范围、标签计数、空白/全库含义；不修改四向操作与透明层 |
| 设置名称与副描述 | `views/settings_center.py` 的 `_page_*`；`setting_rows.py::SettingRow`；`presentation/settings.py` | 标题、hint、按钮、路径/颜色值；按功能读取配置行为与保存/取消/即时生效边界，再治理对应一组四语言 |
| 设置共享输入与颜色 | `interaction_controls.py`、`theme_color_card.py`、`ocr_controls.py`、`rotating_chevron_button.py` | 模式/颜色说明、展开状态、OCR 可选依赖；不把控件状态内部名直接呈现给用户 |
| 资源和分类菜单 | `views/gallery_view.py` 的 `_build_resource_menu`、`_build_node_context_menu`、`_show_node_menu`；`presentation/tools.py`；`SafeRoundMenu` 调用方 | 菜单项标题与动作后果、添加/移动、导出范围；菜单绘制组件不是文案所有者 |
| 确认与输入提示 | `components/dialogs.py::confirm/prompt_text` 及上述业务调用方；`library_setup.py`、`views/exchange_view.py` | 全局删除与移出分类、覆盖、外部副本、取消结果、资源库路径；保留风险和下一步指引 |
| QQ | `views/qq_scan_view.py`、通用 RotatingChevronButton、QQ 帮助 | 查询/扫描/导入/导出范围、第三方昵称查询告知；保持隐私信息与实际发送范围 |
| Telegram | `views/tg_sticker_view.py` 的配置/帮助/导入导出/恢复状态；`tg_batch_dialog.py` | Token/代理边界、恢复不等于下载完成、批量结果；不能为了短文案删除必要安全说明 |
| 相似/OCR/更新/关于 | `views/similarity_view.py`、`presentation/similarity.py`、`update_center.py`、`views/about_view.py`、`presentation/glyphs.py`、`main_window.py` / `window_shell.py` 的业务提示调用 | 删除副本、错误/版本、链接、诊断/更新结果；区分操作入口与说明、可恢复与最终失败 |
| 任务状态与错误 | `caption_feedback.py`、`feedback.py`、`state_tool_tip_manager.py` 的调用方及各工具工作线程 | 标题/进度/完成/失败、详情入口；保留必要原因，不将错误正文全部压缩为“失败” |
| 文字资源 | `services/i18n.py::t/bind_text/translated`；`translations/{zh,zh_TW,en,ja}.json` | 中文为直接原文，zh 字典缺键不自动算缺译；另三语言按实际 key/context 核对，动态值和占位符必须对应 |

### 已有依据的治理候选（本轮不改文案）

1. Telegram 导出按钮仍写“全部清洗入库到 ID 同名收藏夹，并导出为 ID.zip”：有内部处理用语且重复解释，zh_TW/en/ja 均缺少该精确键。`exportPackage()` 确实调用入库并导出流程，**不能简化成纯导出而隐去入库副作用**；下一轮先核对 ImportPackThread 的分类与错误结果再定稿。
2. `RotatingChevronButton` 的默认“展开/收起面板”直接赋中文且三语言均无精确键；QQ/TG 会覆盖部分实例的文本，要逐实例核对，不能把未覆盖默认与所有最终提示混为一谈。
3. “临时显示排序，不改动手动顺序”三语言已有对应，属于重要行为边界；界面动效/窗口毛玻璃四语言也有对应，不能因术语扫描就删掉说明或合并两种开关。
4. 旧键帽测试与实际“单击选中/单击发送”说明已失配；后续集中治理应将行为、文案和对应断言一起审阅，本轮不调整选择合同。
5. 长度、重复、AI 口吻及翻译语义不能仅由字符数或词命中判定。下一轮以“同一功能的设置名+副描述+按钮 Tooltip+菜单+确认+结果”为一组，核实可执行动作、重要限制和四语言含义；优先上述已确认缺译及术语，再分批处理其余入口。

本轮没有全量逐条语言审校，也没有确认所有提示都需要改写。沿用现有 i18n 和 README 门槛，不新建文案系统或重复规范。
