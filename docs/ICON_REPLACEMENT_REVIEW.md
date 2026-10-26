# 顶部耳朵连接规格纠正与两项半透明状态（2026-10-26）

基线aa5850d；边框源码 **d3feb31**，已实现/机器验证/待维护者体验。此前把“开放”处理为耳朵下方整段不画线，规格不完整；本轮按维护者最终合同纠正：**外轮廓连续，耳朵与工作区之间有水平分割线，仅分割线两端开放**。下方旧记录的“开底/断点”仅保留历史，不再作为完整验收标准。

## 边框实际修改

仍由 `AttachedTabRow` 唯一拥有Gallery顶部基线、真实耳朵曲线及内部水平分割线；颜色/1.4px/0.5px基准、b9afec9的左下曲率及工作区下角AA处理不变。

- 左侧原有Tab viewport裁剪会截掉位于正文外7px内的底部外展曲线。现在仅在最下8px带内保留该曲线的绘制空间，正文/标签/翻页及点击裁剪不改；外侧基线端点与曲线足点使用相同边界。
- 右侧工具耳朵末端原来可能超出画布，导致曲线在连接完成前被裁掉。现在将足点约束到真实工作区外边线的0.5px基准，不移动工具容器/内部控件、不改变有效命中。
- 两个耳朵的内部水平分割线都保留；其两端相对正文边各内缩约6px，不与竖边封成矩形。不是删除整段，不用背景块遮线，不叠加第二轮廓。工具组仍无填充/选中/整体Hover/动画，左侧选中短线与原位动画不改。

新用例先复现“选中耳朵中心与端部同色、没有内部分割线”失败，再检查分割线存在、端部开口、左右连接足点和原AA边缘。最终组合 **32项通过**（边框/滑条、UI刷新、Tab切换/滚动/动画/工具、#60状态），启动冒烟NEKORI_STARTUP_OK。初次两个断言未计入画布0.5px夹取边界，修正为真实边界后通过；未因测试修改产品几何。Win11实际Qt深浅、1180/860px前后图已看（私有 `details-connection-*`），无新的明显断开/粗线；未称人工/Win10/混合DPI最终验收。

## 半透明：两个独立、仍然保留的未交付需求

| 组件 | 已核实的现状 | 本轮实际状态 |
|---|---|---|
| Relative Tabs / category_tabs | `workbench.py`将43px AttachedTabRow放在ContentPane之前；图库卡片在QScrollArea/viewport内且受其裁剪。真实几何核对显示两者不重叠。选中耳朵目前仍为原surface填充，移除/加Alpha只会显示基础父表面，不会显示图库。 | **未实现真实透图，未提交Alpha颜色替代，也没有已通过的透图合成原型**；首次单独登记此需求，不沿用TagPanel阻碍冒充其状态。 |
| Tag Panel / TagPanelHost | 同一QSplitter按四个停靠方向把TagPanel和图库分配给互斥区域；现有标题和主体后面没有图库卡片。Alpha同样只能透父表面。 | **UI-C需求保留/未实现**。同材质、标题略实/主体更透的目标未取消，不能凭非重叠布局记作完成。 |

现有Acrylic合成的是窗口背后的桌面，不等于Qt图库内容透出；普通Alpha与高成本模糊必须分开判断。本轮不改材质开关。

### 最小可行方向，均未接入且待指导AI决定

1. **顶部Relative Tabs**：保留现有前景Tab控件和事件入口，让同一个图库viewport绘制区域向上延伸约一行，并以前景Tab叠放；使用顶部内容内缩保持未滚动时首行位置，再让滚动后的资源实际经过Tab后方。继续复用原卡片池/缩略图缓存，不复制截图或另建资源缓存。必须协调flow原点/滚动范围、Sticky、自动滚动、拖放命中和固定预览遮挡，明确遮住的区域不接收图库输入。它需要批准局部视口重叠合同，不能作为无影响的Alpha参数修改直接交付；增加的可见缓冲和重绘成本尚未实测。
2. **四向Tag Panel**：单一图库绘制层覆盖整个Workspace，原Tag面板作为前景Dock叠放，保留其方向/尺寸记忆/控件；确认标题与主体浓度后用Alpha合成。尤其左右停靠会改变图库可用绘制宽度、列数和锚点，需重新约定被遮内容及命中/拖放边界。若继续严格保留当前非重叠空间分配，无法从同一真实布局直接透出不存在于其后的卡片。本轮不擅自变更，也不以任意缩略图底图模拟“下层内容”。

两方案只是责任层明确的最小候选方向，未实现、未作性能验收。高成本模糊如后续获批应沿现有Acrylic开关/回退，不引入截图循环、后台采样或全量卡片重绘。边框可独立验收，不能据此勾选任何半透明完成项。

#24/#37同步、保持Open；七处W01实验、W03未启用候选、W02暂停、#57/T06/T07和真实数据保护不变。不Push/发布。

---

## 以下为上一轮定向修正记录

# UI-B边框及共享滑条定向修正（2026-10-26）

基线4c420ec，源码 **b9afec9**。仅修改 `components/navigation.py`、`components/softframe.py` 及两份相关测试。已实现/机器验证/待维护者视觉验收，不Push/打包/发布；图标/三色线、UI-C和窗口宿主未改。

- **工具组左下**：原WorkspaceTools路径直接从底部垂直上行，没有耳朵下部外展圆角。现与活动Tab复用真实 `open_ear_path`，在AttachedTabRow内绘制，可超出工具容器左界完成曲线；内部控件及工具容器几何不变。容器仍是无填充静态布局，无组级Hover/动画/选中。
- **顶部重叠**：原行基线y=h−0.7、Tab路径y=h−0.5，且分别由父行/子Tab/工具容器绘制，连接点存在不同像素基准及重叠端帽。Gallery的AttachedTabRow现统一拥有基线、两种耳朵表面/轮廓，用同一y/1.4px/FlatCap与真实分段区间；Tab只继续画文字、Hover和原位呼出线。Settings/独立Tab原绘制不改。不是以背景块遮盖边线。
- **左右下角**：原ContentPane将同一圆角转为整数QRegion，切掉自身轮廓部分覆盖像素。实际控件“带Mask/移除Mask”像素对照先失败；Gallery专用Mask现为已有曲线留一个逻辑像素抗锯齿余量，并限制在原widget矩形内，绘制路径/圆角/布局均不变。没有新增覆盖层、边框或改顶层窗口Region；TagPanelHost未修改。
- **共享滑条**：原hasFocus无条件画强调圈，所以鼠标点击后焦点不走即持续高亮；自有拖动、Hover还需在释放/失去捕获/隐藏后校准。SoftframeSlider复用 `focus_input()`、`pointer_hits()`，键盘来源才画焦点圈；鼠标焦点仍保留。释放/失活/禁用/隐藏清理临时拖动，并按实际柄命中恢复Hover或Normal，数值/track/page/keyboard/tracking/wheel原语义不变。统一覆盖主图库缩略图、Settings RangeRow、AccentPicker HSV/RGB、缩略帧对话框、Similarity阈值等现有调用者，不逐入口打补丁。

**验证**：三个最小用例先失败后转绿（鼠标焦点图像、工具左下曲线、左右下角抗锯齿裁剪）。定向组合30项通过（新滑条H/V释放/捕获/数值、UI刷新、Tab动画/翻页/工具、#60生命周期）；相邻17项通过（原ContentPane裁剪、设置滚轮/色彩保存取消、虚拟图库与标签拖放）；补验8项通过（新用例复核与实际缩略图柄拖动端点、轨道点击、配置值及端点边缘），组间有交叉。隔离启动输出NEKORI_STARTUP_OK。

Win11实际Qt窗口深浅、1180/860px前后画面及下角放大图已查看，私有生成证据在DevData/ui-refresh/details-*与corners-*。这些是Qt窗口渲染和自动输入，不冒称全系统鼠标拖动/其它DPI/Win10或人工最终验收。一次测试错误地以普通QEvent构造HoverLeave导致原生事件强制转换崩溃；已改为正确QHoverEvent，未加业务绕过或将该脚本错误归入旧崩溃Issue。

七处W01实验保持，W03不启用，#9继续Open并暂停调查；#57/T06/T07/原Library与正式版不动。固定Demo重启前后以完整业务表/行序对照，记录于CURRENT。#24/#60/#37同步并保持Open；不新增Issue或改变追踪总数。细节仍待维护者实际视觉体验。

---

## 以下为前轮UI交付记录

# 发布后局部 UI 实施（2026-10-26）

基线3989346 / dev/post-0.2.1。本轮按维护者新附件批准的固定图标及UI合同实施，**UI-A `d9f98d9`、UI-B `f7afc8b` 已实现/机器验证/待人工视觉与操作验收；UI-C未实现，保留待产品决策**。不Push/打包/发布，不继续W-02调查。

## 实际交付

| 工作包 | 实现及责任层 |
|---|---|
| UI-A 图标 | icons.py沿原QSvgRenderer/主题色缓存加入局部语义图标；sidebar/workbench/SortCycleButton/ResourceSortIcon/TagPanel/资源右键仅更新批准绑定。剪贴板主操作保留ClipboardImportIcon；不更改通用ADD/MENU/SORT、字母排序或闲置排序菜单。树模式仅该入口用2.25描边，按钮尺寸不变；新分类整体镜像，sticker保留原版填充轮廓。 |
| UI-A 设置 | 实时预览与更多移入同一现有导航底部行，均32px高。ButtonPaint只为该开关提供透明中性轮廓及开/关对比度；沿原Hover/Pressed/键盘输入来源，不新增状态事实源。眼睛/闭眼、保存/放弃及实时预览语义不变。 |
| UI-A 卡片 | 既有is_selected/_hovered为输入：Selected单轮廓1.5px、Hover优先2px，顶部线保持原方向位置、收敛至约56%宽度。没有修改选择集合、发送/Enter、拖放或卡片绑定/缩略图。原视觉回归断言仅按新批准线长更新，居中/内缩/不越界保护保留。 |
| UI-B 双层线 | HeadingBand在Hierarchy灰线下绘制三色等长段，总长含两个间隙为灰线0.618；垂直净距2px、色线2px。按维护者最后澄清，灰线右端/高度不变，左端延至标题前横向刻度线的既有左端（axis_left=2）；三色组同起点，内部两间隙各取组宽4%，段长与间隙均随新总长同步。标题/搜索和应用身份线不变。 |
| UI-B 工作区 | Gallery专用ContentPane中性轮廓1.4px、圆角不变，包围资源和四向Tag Dock整体。Settings等其它ContentPane不随之加重。 |
| UI-B 开放连接 | AttachedTabRow单独拥有整行基线，按Qt真实tabRect/scroll-button裁剪及工具组矩形分段；TabStrip保留耳朵轮廓与原位呼出，仅让出Gallery基线，未以实心矩形遮线。WorkspaceTools只画一套静态透明开底轮廓，无组级Hover/Checked/动画；内留白容纳原历史26px及滑块28px命中/高亮，组高38px仍在原43px标签行内。 |

Tab几何变化、滚动、隐藏/显示及Qt tabLayoutChange触发行级局部更新，不执行SQL、全库投影、卡片重建或持续采样；没有修改任何Windows宿主代码。实际图标资源与固定上游版本、衍生关系及许可证统一记录在 THIRD_PARTY_NOTICES.md 和既有 assets/icons 许可位置，没有运行时网络依赖或新图标库。

补充规格以维护者最新澄清为准：**保持右端不变，延长左端对齐标题前横向刻度轴**，取代前条“保持左端、向末端延长”的表述。不是把整组线平移；灰线左端24→2，右端保持rail.width()，三色重新按增加后的总长计算。新增长度/起点/比例检查及相邻工具栏用例2项通过。

## UI-C 的实际阻碍

`TagPanelHost.set_placement()`将同一个TagPanel与图库workspace插入QSplitter两个互斥区域，`apply_extent()`将空间分配给二者。TOP/BOTTOM/LEFT/RIGHT展开时，两区域实际几何均**不重叠**；TagPanel当前在自身区域绘制surface_alt，图库不在它后面。关掉该底色或加Alpha只能看到父表面，不能看到表情。

Win11原生Qt样本与四向控件测试均核对非重叠。没有既有图像合成层可直接复用；要真正透图至少需要批准改变重叠/空间分配合同，或另一种明确的背景呈现方案。按附件8.2，本轮不擅自决定，也不交付伪透明、不加滚动截图/模糊/后台采样。因此 **UI-C暂无源码提交**，原Tag四向折叠/ResizeHandle/记忆及固定预览边界保持。待指导AI确认这一实际约束后再安排。

## 验证与限制

- UI-A及相邻组合22项：首次21通过，既有正常呼出动画用例在固定340ms等待时仍在回弹帧而失败；单独复核该用例通过。没有改动画时长、关键帧或用延时业务补偿使其通过；保留此次时序敏感性记录。
- UI-B：tab_toolbar_layout + tab_overflow + shared_interaction_lifecycle **20项通过**；包括关闭动效静态终态、原位向上中间帧、滚轮不切换、翻页和Hover清理。
- test_ui_refresh **5项通过**：14/16/18/20px实际SVG渲染与刷新绑定、同级设置几何/透明Checked底面、Hover优先单轮廓、真实分段不绘制区域/窄窗、三色像素比例及四向非重叠证明。
- unified_selection + category_tab_drop + tag_panel_collapse + virtual_gallery + external_drag **44项通过**，保护混排/菜单取消与合法目标、四向折叠及尺寸记忆、renderer复用/身份、外拖独立副本。上述组有交叉，不相加冒充独立总数；Qt模拟不等于新一轮Windows OLE/真实聊天客户端验收。
- Win11原生Qt独立MainWindow/Settings窗口生成样本：深浅主题、1180/860px主窗口、预览开/关及四向Dock截图已实际查看；设置两控件顶部/高度相同，工具组安全留白和断点可见，四向无重叠。截图/数据仅保留私有DevData/ui-refresh，未读取真实Library。
- 隔离启动冒烟NEKORI_STARTUP_OK；release_layout清单 **2项通过**，新增SVG/许可沿原资源清单收集。未构建发行包，不称实际载荷已验收。

本轮未重跑W-02连续缩放/八方向研究、全量安全或性能套件。Win10/混合DPI/高DPI真实桌面、全聊天客户端未验证；图标重量、灰框/三色线及设置对比度仍由维护者最终体验。#9持续Open并暂停主动调查，#60既有结论保留。固定Demo持续数据按前后完整表行核对，不按历史数量回填；七处W01实验不暂存，W03未启用。

---

## 以下为阶段A历史记录（当时尚未批准实装，不代表当前状态）

# 图标替换：阶段 A 视觉确认

2026-10-25 · 核对基线 `48254b1` / `dev/post-0.2.1`。**仅准备候选与对照图，未替换运行图标，等待维护者确认。**

完整对照：[icon-comparison.png](assets/icon-review/icon-comparison.png)。候选目录：`docs/assets/icon-review/svg/`。可复现脚本：`tools/render_icon_review.py`，在 Source 使用 `.venv/Scripts/python.exe tools/render_icon_review.py`。仅创建 offscreen 控件，不连接 Library、配置或固定 Demo；不需要系统鼠标。

## 来源与资源

- [Tabler Icons Outline](https://github.com/tabler/tabler-icons/tree/a4ce1404bc6d24d3c365afe7b258d6bf6f48d62d/icons/outline)，固定提交 `a4ce1404bc6d24d3c365afe7b258d6bf6f48d62d`。7 个上游 SVG、MIT 授权及各文件 Git blob 来源见 `assets/icon-review/provenance.json` 与 `LICENSE-Tabler.txt`。
- [Nekori Softframe](https://github.com/Nekori347/Nekori-Softframe/tree/a1d98cac0ad5a5dc7a9c9230f93159ff1c728fb5)，本地 Reference 同提交。沿用描边语义、实际渲染尺寸校准、现有字体与语义色板，不重做布局。
- `mood-plus`、`tag-plus`、`menu-order`、`clock-down`、`clock-up` 为待新增运行资源，目前只在文档候选目录。
- `playlist-add.svg` 保留原版；`playlist-add-mirrored.svg` 在 SVG 根元素内部包裹 `translate(24 0) scale(-1 1)`，三条横线和加号整体水平镜像。没有镜像按钮或布局，没有遮盖底块。
- 当前 `list-tree.svg` 已是 Tabler 24×24、stroke 2；与本次上游版本的可见路径一致。另备 `list-tree-stroke-2.25.svg`，仅调整描边，**为视觉候选而非已批准规格**。不直接覆盖共用 MENU。
- A→Z / Z→A 两份候选逐字节复制当前本地 SVG，保持原样。
- 共 11 份 SVG（包含原版、衍生版和两份字母排序）；透明、`fill="none"`、`currentColor`、圆端点/连接。最终经现有主题颜色替换与 QSvgRenderer 路径即可使用，不安装图标库。

## 最新绑定清单

表中“纳入”均指**确认后的阶段 B 范围**，本次未实装。路径均相对 Source；行号基于上述基线。

| 功能 | 控件 / 创建函数 | 当前 → 目标 | 共享情况 | 纳入范围 |
|---|---|---|---|---|
| 分类树模式 | `CategorySidebar.btn_view_mode`；`presentation/sidebar.py:19` `build_sidebar()`；`views/gallery_view.py:417` `apply_presentation()` 更新 | `MENU/list-tree` → 原版与 2.25 候选待确认 | MENU 是通用定义；此按钮切换图标模式时仍用 TILES/layout-grid | 是，仅树模式控件；初始化与模式刷新同时覆盖 |
| 新建分类按钮 | `CategorySidebar.btn_new`；`presentation/sidebar.py:31` `build_sidebar()` | ADD/plus → playlist-add-mirrored | ADD 不能全局替换 | 是；原创建父级/位置规则不变 |
| 导入菜单触发 | `g.btn_paste.dropButton`；`presentation/workbench.py:90` `build_workbench()` | IMPORT/folder-input → mood-plus | SplitPushButton 的两个按钮行为独立 | 是，仅 dropButton |
| 剪贴板粘贴 | `g.btn_paste.button`；同上 | `ClipboardImportIcon()` → 保留 | 通过 `presentation/glyphs.py` 现有组合绘制 | 否 |
| 分类显示排序 | `CategorySidebar.btn_sort`；`presentation/sidebar.py:33` | SORT/sort-descending → menu-order；ASC/DESC 字母图标保留 | 与标签共用 `SortCycleButton.refresh()`，`components/navigation.py:53` | 是，全部三个状态 |
| 标签显示排序 | `TagPanel.btn_sort`；`components/tag_panel.py` 构造器 | 同分类显示排序 | 同一个 SortCycleButton 类，不同状态实例/数据投影 | 是，全部三个状态 |
| 新建标签 | `TagPanel.btn_new`；`components/tag_panel.py:467`；`apply_placement_axis():606` | ADD/plus → tag-plus | 上/下/左/右停靠重新安置同一个按钮，不复制资源 | 是；保留全局标签成员关系语义 |
| 资源显示排序 | `g.btn_content_sort`；`presentation/workbench.py:100`；`views/gallery_view.py:3711` `_update_resource_sort_label()` | MANUAL:SORT → menu-order；RECENT:TIME_DESC → clock-down；OLDEST:TIME_ASC → clock-up | 独立资源状态映射；与前两者共享目标手动图标定义，不共享排序数据语义 | 是，全部三个状态 |
| 资源排序菜单 | `views/gallery_view.py:3720` `_build_resource_sort_menu()` / resource_sort_actions | 当前定义为无图标 QAction | 全库引用核对仅有定义，无调用；现行入口为点击循环 | 否，不启用闲置菜单、不添加图标 |
| 左树右键新建根/子/同级分类 | `views/gallery_view.py:668` `_show_node_menu()`、`:712` `_show_root_menu()` | 无图标 → 保留 | QAction 为纯文字 | 否 |
| 图库空白右键新建分类 | `views/gallery_view.py:1038`，`show_content_menu()` 中 node QAction | ADD/plus | 同功能但独立入口，已有图标 | 本次工具按钮预览未包含；后续若同步，使用同一镜像定义，不全局改 ADD |
| 标签空白右键新建标签 | `components/tag_panel.py:749` `_show_context_menu()` | 无图标 → 保留 | QAction 为纯文字 | 否 |
| 管理栏溢出“移到最前/最后” | `views/gallery_view.py:2498` `_build_selection_more_menu()` | SORT/sort-descending → 保留 | 是持久位置操作，不是本次三个显示排序按钮 | 否；避免全局重映射 SORT 导致连带改变 |

上述行号用于定位，后续实装先核对最新源码。其余 ADD/SORT 调用包括 `interaction_controls.ResourceSortIcon.render()` 的初始资源按钮图标；其后由 `_update_resource_sort_label()` 更新。阶段 B 应与同一个手动图标定义一致，不留下初始化/刷新两种图标。

## 实际尺寸与对照说明

| 位置 | 按钮尺寸 | iconSize | 当前间距 |
|---|---:|---:|---:|
| 左侧树模式、新分类 | 24×24 | 14×14 | header spacing 2；margins(2,0,2,2) |
| 分类/标签 SortCycleButton | 24×24 | 16×16 | 分类沿 header；标签在自己的 header |
| 资源剪贴板/导入/管理/排序 | 32×32 | 18×18 | row spacing 4；Split 内 spacing 4 |
| 标签新建（停靠后） | 20×20 | 14×14 | axis strip；与排序不在同一行 |

PNG 上半区为 24/20/16px 实际像素的 SVG 与深底对比，中间为 64px 放大和树图标 14px 样本，下半区为真实项目控件的 1:1 offscreen 工具栏模拟。左栏使用常见 220px header；模拟画布不代表新布局。标签样本文字为虚构，不读取实际资源。无业务状态变化，也不是应用全窗口截图。

树按钮“细”的事实来源是 14px 实际渲染：stroke 2 相当于约 1.17px；候选 2.25 相当于约 1.31px。重新绑定同一图标不能解决这个差异。20px 的两者约为 1.67/1.88px。候选没有擅自改变按钮或 iconSize。

16px 下 clock 箭头与 tag-plus 的细部更密，20px 更容易辨认；实际新建标签/分类只有 14px，必须结合下方工具栏判断。原始路径自然避让角标，本次无额外遮罩。是否采用树图标 2.25 描边仍由视觉确认决定。

## 阶段 B 最小范围（未执行）

1. 将批准的 SVG 从文档候选目录加入现有 `fluent_ui/assets/icons/`；沿用 icons.py 的 currentColor/主题绘制，不增加运行时网络。
2. 在 icons.py 增加局部语义定义（例如手动显示排序、创建分类、创建标签、导入菜单、树模式候选），不改变通用 ADD/MENU/SORT 的其它消费者。
3. 仅更新上表纳入的 sidebar/workbench、SortCycleButton、TagPanel、树模式刷新、资源状态映射及其初始 ResourceSortIcon。字母排序资源原样保留，时间排序仍是添加时间。
4. 图库右键已有图标的新建分类作为重复入口已列明，未默默扩入；无图标右键不增加图标。不得为闲置资源排序菜单增加新行为。
5. 确认后再检查实际应用深浅主题、Hover、模式变化、标签停靠和有限 GUI 回归。本阶段不声称已实装或人工验收。

## 本阶段验证与保护

- QSvgRenderer 验证 11 份候选有效、viewBox 为 24×24、透明主题描边；确认 AZ/ZA 与现资源完全一致。
- 镜像只对完整 SVG 内容组应用一次；原资源保持不动；list-tree 可见路径与上游一致。
- 已实际生成并查看一张完整 PNG，含 9 状态、4 组放大、3 区工具栏当前/候选浅色/候选深色。
- 无实际程序图标绑定、运行资源、布局、业务逻辑修改；不重启固定 Demo、不访问其数据库，不触碰原始 Library。固定 Demo 持续数据/排序保持不变。
- 七处 W-01 未提交实验保留；W-03、G-27、T-06/T-07及其它工作包不改。没有创建或关闭 Issue，没有 Push/发布。停止于阶段 A 视觉审阅。
