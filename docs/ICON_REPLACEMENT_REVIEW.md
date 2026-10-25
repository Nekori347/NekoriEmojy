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
