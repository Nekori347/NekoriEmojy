# TP-B 用户文案事实采集（第一阶段）

## 一、采集摘要

调查基线：**732004a / dev/post-0.2.1**，2026-10-26。本文只保存现有文字及技术事实，不包含替换文案、翻译创作或表达取舍。TP-A 仍为已修复实际复现故障/机器验证/待人工。关联 #62/#37。

共 **235 条稳定编号记录**：A主图库 94、B Tag及共享控件 22、C设置 103、D三个重点问题 16。其中设置名称和完整副描述在同一入口记录内按“名称/副描述”分列，不截断长文；不同状态另建记录。共有 **272 个不同的已接入翻译源片段键**，不等于控件数或原138个调用点数。

复用上轮138调用/38文件入口族；本轮只读定向函数、AST展开设置声明及字典，不重新全仓盘点，不读取用户资源名/路径/账号。保护文件的业务引用读取Git HEAD版本，未将W01实验混作基线。

|覆盖指标|实际数量/定义|
|---|---|
|zh_TW 缺失|23 个不同源键；实际调用t时显示 [MISSING: 原键]，不是中文回退|
|en 缺失|23 个不同源键；实际调用t时显示 [MISSING: 原键]，不是中文回退|
|ja 缺失|23 个不同源键；实际调用t时显示 [MISSING: 原键]，不是中文回退|
|三语言合计缺失|69 个“源键×语言”单元，涉及22条入口记录；不把重复调用重复计数|
|原文直显/最终覆盖|4个不同源片段：旧旋转默认1条、删除工具栏最终覆盖3状态；不按字典缺译单元合计|
|格式占位符不一致|0 个记录×语言；按Formatter字段核对，不代表完成语义翻译审校|
|已确证的动态绑定冲突|2种：资源排序二次查译3状态×3非中文=9组合；删除工具栏_sync_command_bar后原文覆盖3状态×3非中文=9组合（随后语言事件可重译）；与字典缺失分开计数|
|其它已确证事实冲突|旧键帽测试1处子串失配；共享旋转类默认文字1处未绑定语言/状态。Telegram旧长Tooltip属于隐藏旧按钮，不等同当前菜单提示|

### 读表规则与共同机制

- 每条同时包含功能分组、界面入口、控件类型、四语言、键/生成方式、触发状态、业务、副作用/限制、源码函数和证据/未知。两张同编号表分别承担文字和行为字段，合起来是一条完整记录。
- 未特别注明的翻译键就是中文原文片段本身，区分换行/标点/大小写；表内保持完整文本，换行仅以HTML换行展示。名称/副描述是各自的精确键，不合并成一个键。
- services/i18n.py::_translate：zh直接返回原文；其它语言先查“原文::context”，再查无context原文，均不存在则 [MISSING: key]。本表采集入口无额外context；不以zh.json缺键判缺译。
- “缺失”表示字典无该精确键，括注真实MISSING显示；“未调用i18n”表示即使切语言仍保留硬编码值。用户名称/路径为原样动态数据，不需要翻译，本文不用真实值举例。
- bind_text/translated/SettingRow的标题和hint绑定language_changed；单次setToolTip(t(...))不自动构成实时绑定。触发重建/状态刷新时才再翻译的入口在绑定列说明；具体当前可见性未运行时不伪称桌面验证。
- 控件禁用不等于文字清空。全局Tooltip Enter路径检查isEnabled；ToolTip事件路径仍可读取现存文本。本文报告源码存储的状态文字和可见层来源，不保证每个禁用状态都会自动弹提示。
- 设置通则S：_track→_stage只保留pending；PREVIEW_KEYS且实时预览开启时写preview_values并发通知；save持久化，discard恢复。实时预览开关自身立即config.set，不属pending。软件图标、目录打开、OCR安装/任务等Action命令不受此通则撤回。

## 二、详细事实表

### A. 主图库日常高频入口

#### 主图库顶部

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-001|搜索名称、标签或关键词… / SearchLineEdit/placeholder|搜索名称、标签或关键词…|搜尋名稱、標籤或關鍵詞…|Search names, tags or keywords…|名前・タグ・キーワードを検索…|t/bind_text/translated：逐原文精确键|
|TPB-002|支持文件名、标签、分类名称和已保存的表情文字。 / SearchLineEdit/Tooltip|支持文件名、标签、分类名称和已保存的表情文字。|可搜尋檔名、標籤、分類名稱和已儲存的表情文字。|Search file names, tags, category names and saved emote text.|ファイル名、タグ、分類名、保存済みのスタンプテキストを検索できます。|t/bind_text/translated：逐原文精确键|
|TPB-003|筛选当前视图 / 工具按钮/Tooltip|筛选当前视图|篩選目前檢視|Filter current view|現在のビューを絞り込み|t/bind_text/translated：逐原文精确键|
|TPB-004|从剪贴板粘贴表情 (Ctrl+V) / SplitPushButton主体/Tooltip|从剪贴板粘贴表情 (Ctrl+V)|從剪貼簿貼上表情 (Ctrl+V)|Paste emotes from the clipboard (Ctrl+V)|クリップボードからスタンプを貼り付け (Ctrl+V)|t/bind_text/translated：逐原文精确键|
|TPB-005|导入表情 / 分裂箭头/Tooltip|导入表情|導入表情|Import emotes|スタンプを取り込み|t/bind_text/translated：逐原文精确键|
|TPB-006|导入文件… / 导入菜单/Action|导入文件…|匯入檔案…|Import files…|ファイルをインポート…|t/bind_text/translated：逐原文精确键|
|TPB-007|导入文件夹为分类… / 导入菜单/Action|导入文件夹为分类…|導入文件夾為分類…|Import folder as category…|フォルダをカテゴリとして取り込み…|t/bind_text/translated：逐原文精确键|
|TPB-008|缩略图大小 / SoftframeSlider及图标/Tooltip|缩略图大小|縮略圖大小|Thumbnail size|サムネイルサイズ|t/bind_text/translated：逐原文精确键|
|TPB-009|最近使用 / Checkable工具按钮/Tooltip|最近使用|最近使用|Recent|最近使ったスタンプ|t/bind_text/translated：逐原文精确键|
|TPB-010|回到顶部（PgUp） · 到底部（PgDown） / 浮动按钮/Tooltip|回到顶部（PgUp） · 到底部（PgDown）|回到頂端（PgUp） · 到底端（PgDown）|Top (PgUp) · Bottom (PgDown)|先頭へ（PgUp）・末尾へ（PgDown）|t/bind_text/translated：逐原文精确键|
|TPB-011|设置 / 工具按钮/Tooltip|设置|設定|Settings|設定|t/bind_text/translated：逐原文精确键|
|TPB-012|应用与工具 / 工具按钮/Tooltip|应用与工具|應用程式與工具|App and tools|アプリとツール|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-001|控件可见时；bind_text随语言更新|textChanged→set_search_keyword→单次搜索计时→_collect_entries。|当前content_scope与展开投影；搜索元数据由get_search_metadata提供。|fluent_ui/presentation/workbench.py:99 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-002|控件可见时；bind_text随语言更新|_collect_entries以normalize_search结果匹配get_search_metadata文本。|这里只核对查询链；每种格式的搜索命中未运行。|fluent_ui/presentation/workbench.py:100 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-003|控件可见时；bind_text随语言更新|打开FilterCheckboxFlyout；勾选更新FilterState。|清除入口同时清搜索、Tag过滤，不只是勾选项。|fluent_ui/presentation/workbench.py:103 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-004|控件可见时；bind_text随语言更新|handle_global_paste走已有剪贴板导入。|本轮未读取剪贴板；Ctrl+V为此局部命令提示，不是可配置全局导入组合。|fluent_ui/presentation/workbench.py:112 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-005|控件可见时；bind_text随语言更新|展开import_menu。|不在打开菜单时执行导入。|fluent_ui/presentation/workbench.py:113 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-006|控件可见时；bind_text随语言更新|_pick_import_files选择来源后入队。|取消文件选择不提交。|fluent_ui/presentation/workbench.py:116 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-007|控件可见时；bind_text随语言更新|sidebar.import_folder_as_node(content_scope_node())。|目录导入会创建分类层级；与单文件导入不同。|fluent_ui/presentation/workbench.py:116 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-008|控件可见时；bind_text随语言更新|60至300，步长10；_commit_thumbnail_size同步偏好。|直接图库调节不是设置中心待保存值；不改变原图尺寸。|fluent_ui/presentation/workbench.py:131 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-009|控件可见时；bind_text随语言更新|toggle_recent_view切换最近记录投影。|切入时保存搜索/过滤/排序，退出恢复；不改变分类成员。|fluent_ui/presentation/workbench.py:145 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-010|控件可见时；bind_text随语言更新|按钮单击滚到minimum；PgUp/PgDown在图库快捷键滚到minimum/maximum。|按钮单击不执行“到底部”；输入编辑控件不接受图库快捷键。|fluent_ui/presentation/workbench.py:172 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-011|控件可见时；bind_text随语言更新|发setting_requested，打开SettingsWindow。|未修改设置。|fluent_ui/presentation/workbench.py:185 / build_workbench；源码静态；本轮未运行GUI。|
|TPB-012|控件可见时；bind_text随语言更新|_show_tools_menu打开工具菜单。|仅打开入口。|fluent_ui/presentation/workbench.py:187 / build_workbench；源码静态；本轮未运行GUI。|

#### 分类导航

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-013|全部表情 / 根级导航标签|全部表情|全部表情|All emotes|すべてのスタンプ|t/bind_text/translated：逐原文精确键|
|TPB-014|新建分类入口 / 按钮Tooltip|在当前位置新建分类|在目前位置新增分類|New category in current location|現在の場所にカテゴリを作成|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-013|根入口显示；单击|gallery_view.set_node(ROOT)；root_count为当前资源数量。|用户分类名称另走原始节点数据。|fluent_ui/presentation/sidebar.py:24 / build_sidebar；源码静态；本轮未运行GUI。|
|TPB-014|单击|create_node(gallery_view.current_node)。|父级取正式current_node，不凭Relative Tab文本猜测。|fluent_ui/presentation/sidebar.py:32 / build_sidebar；源码静态；本轮未运行GUI。|

#### 分类菜单

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-015|打开 / Action|打开|打開|Open|開く|t/bind_text/translated：逐原文精确键|
|TPB-016|新建子分类 / Action|新建子分类|新建子分類|New subcategory|サブカテゴリを作成|t/bind_text/translated：逐原文精确键|
|TPB-017|重命名… / Action|重命名…|重命名…|Rename…|名前を変更…|t/bind_text/translated：逐原文精确键|
|TPB-018|设置分类图标… / Action|设置分类图标…|設置分類圖標…|Set category icon…|カテゴリアイコンを設定…|t/bind_text/translated：逐原文精确键|
|TPB-019|导入文件夹到此处… / Action|导入文件夹到此处…|導入文件夾到此處…|Import folder here…|ここにフォルダを取り込み…|t/bind_text/translated：逐原文精确键|
|TPB-020|导出此分类为表情合集… / Action|导出此分类为表情合集…|導出此分類為表情合集…|Export category package…|カテゴリをパッケージとして書き出し…|t/bind_text/translated：逐原文精确键|
|TPB-021|删除分类 / Action|删除分类|刪除分類|Delete Category|カテゴリを削除|t/bind_text/translated：逐原文精确键|
|TPB-022|新建根级分类 / Action|新建根级分类|新建根級分類|New root category|最上位のカテゴリを作成|t/bind_text/translated：逐原文精确键|
|TPB-023|导入文件夹为分类… / Action|导入文件夹为分类…|導入文件夾為分類…|Import folder as category…|フォルダをカテゴリとして取り込み…|t/bind_text/translated：逐原文精确键|
|TPB-024|打开 / Action|打开|打開|Open|開く|t/bind_text/translated：逐原文精确键|
|TPB-025|展开 / 折叠内容 / Action|展开 / 折叠内容|展開 / 摺疊內容|Expand / collapse content|内容を展開 / 折りたたむ|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-015|相应分类/根/图库节点右键|左树菜单各Action分别连接正式导航、create_node(node_id)、rename_node、set_node_icon、import_folder_as_node、export_node、delete_node。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:670 / _show_node_menu；源码静态；本轮未运行GUI。|
|TPB-016|相应分类/根/图库节点右键|左树菜单各Action分别连接正式导航、create_node(node_id)、rename_node、set_node_icon、import_folder_as_node、export_node、delete_node。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:685 / _show_node_menu；源码静态；本轮未运行GUI。|
|TPB-017|相应分类/根/图库节点右键|左树菜单各Action分别连接正式导航、create_node(node_id)、rename_node、set_node_icon、import_folder_as_node、export_node、delete_node。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:689 / _show_node_menu；源码静态；本轮未运行GUI。|
|TPB-018|相应分类/根/图库节点右键|左树菜单各Action分别连接正式导航、create_node(node_id)、rename_node、set_node_icon、import_folder_as_node、export_node、delete_node。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:693 / _show_node_menu；源码静态；本轮未运行GUI。|
|TPB-019|相应分类/根/图库节点右键|左树菜单各Action分别连接正式导航、create_node(node_id)、rename_node、set_node_icon、import_folder_as_node、export_node、delete_node。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:697 / _show_node_menu；源码静态；本轮未运行GUI。|
|TPB-020|相应分类/根/图库节点右键|左树菜单各Action分别连接正式导航、create_node(node_id)、rename_node、set_node_icon、import_folder_as_node、export_node、delete_node。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:702 / _show_node_menu；源码静态；本轮未运行GUI。|
|TPB-021|相应分类/根/图库节点右键|左树菜单各Action分别连接正式导航、create_node(node_id)、rename_node、set_node_icon、import_folder_as_node、export_node、delete_node。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:707 / _show_node_menu；源码静态；本轮未运行GUI。|
|TPB-022|相应分类/根/图库节点右键|分别创建ROOT子节点，或向ROOT导入目录层级。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:714 / _show_root_menu；源码静态；本轮未运行GUI。|
|TPB-023|相应分类/根/图库节点右键|分别创建ROOT子节点，或向ROOT导入目录层级。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:717 / _show_root_menu；源码静态；本轮未运行GUI。|
|TPB-024|相应分类/根/图库节点右键|右图库节点菜单：打开=set_node；展开/折叠=toggle_node_expansion，只改变图库内容展开状态。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:2638 / _build_node_context_menu；源码静态；本轮未运行GUI。|
|TPB-025|相应分类/根/图库节点右键|右图库节点菜单：打开=set_node；展开/折叠=toggle_node_expansion，只改变图库内容展开状态。|具体数据后果见分类删除/资源导出记录；同名打开在左树会调用tree.select_node，右图库直接set_node，不能合并成完全相同导航。|fluent_ui/views/gallery_view.py:2639 / _build_node_context_menu；源码静态；本轮未运行GUI。|

#### 分类名称排序

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-026|分类显示排序/手动顺序 / SortCycleButton/Tooltip|1：分类显示排序<br>2：手动顺序<br>3：临时显示排序，不改动手动顺序|1：分類顯示排序<br>2：手動順序<br>3：臨時顯示排序，不會改動手動順序|1：Category display order<br>2：Manual order<br>3：Temporary display order; the manual order is unchanged|1：カテゴリの表示順<br>2：手動の順序<br>3：一時的な表示順です。手動の並び順は変更されません|组合：t(title)+ · +t(label)+换行+t(边界说明)，组件键分别查译|
|TPB-027|分类显示排序/名称 A→Z / SortCycleButton/Tooltip|1：分类显示排序<br>2：名称 A→Z<br>3：临时显示排序，不改动手动顺序|1：分類顯示排序<br>2：名稱 A→Z<br>3：臨時顯示排序，不會改動手動順序|1：Category display order<br>2：Name A→Z<br>3：Temporary display order; the manual order is unchanged|1：カテゴリの表示順<br>2：名前 A→Z<br>3：一時的な表示順です。手動の並び順は変更されません|组合：t(title)+ · +t(label)+换行+t(边界说明)，组件键分别查译|
|TPB-028|分类显示排序/名称 Z→A / SortCycleButton/Tooltip|1：分类显示排序<br>2：名称 Z→A<br>3：临时显示排序，不改动手动顺序|1：分類顯示排序<br>2：名稱 Z→A<br>3：臨時顯示排序，不會改動手動順序|1：Category display order<br>2：Name Z→A<br>3：Temporary display order; the manual order is unchanged|1：カテゴリの表示順<br>2：名前 Z→A<br>3：一時的な表示順です。手動の並び順は変更されません|组合：t(title)+ · +t(label)+换行+t(边界说明)，组件键分别查译|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-026|三态循环；当前状态显示|sidebar.set_display_sort写sidebar_sort偏好，再由tree/SectionedProjection生成名称投影。|只保存显示模式，不重写节点兄弟手动位置。|fluent_ui/presentation/sidebar.py:36 / build_sidebar；模板实际位于navigation.py::SortCycleButton.refresh：t(title)+ · +t(label)+换行+t(边界说明)。|
|TPB-027|三态循环；当前状态显示|sidebar.set_display_sort写sidebar_sort偏好，再由tree/SectionedProjection生成名称投影。|只保存显示模式，不重写节点兄弟手动位置。|fluent_ui/presentation/sidebar.py:36 / build_sidebar；模板实际位于navigation.py::SortCycleButton.refresh：t(title)+ · +t(label)+换行+t(边界说明)。|
|TPB-028|三态循环；当前状态显示|sidebar.set_display_sort写sidebar_sort偏好，再由tree/SectionedProjection生成名称投影。|只保存显示模式，不重写节点兄弟手动位置。|fluent_ui/presentation/sidebar.py:36 / build_sidebar；模板实际位于navigation.py::SortCycleButton.refresh：t(title)+ · +t(label)+换行+t(边界说明)。|

#### 资源添加时间排序

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-029|表情显示排序/自定义顺序 / 工具按钮Tooltip|1：表情显示排序<br>2：自定义顺序|1：表情顯示排序<br>2：自訂順序|1：Emote display order<br>2：Custom order|1：スタンプの表示順<br>2：手動順|组合：先t两片再拼接后传bind_text；真实二次查译结果见冲突F1|
|TPB-030|表情显示排序/最近添加 / 工具按钮Tooltip|1：表情显示排序<br>2：最近添加|1：表情顯示排序<br>2：最近新增|1：Emote display order<br>2：Recently added|1：スタンプの表示順<br>2：新しく追加した順|组合：先t两片再拼接后传bind_text；真实二次查译结果见冲突F1|
|TPB-031|表情显示排序/最早添加 / 工具按钮Tooltip|1：表情显示排序<br>2：最早添加|1：表情顯示排序<br>2：最早新增|1：Emote display order<br>2：Oldest added|1：スタンプの表示順<br>2：古く追加した順|组合：先t两片再拼接后传bind_text；真实二次查译结果见冲突F1|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-029|当前resource_sort为对应模式|ResourceSort.project只在两个节点之间连续资源段内按library_added_seq排序，节点保持结构边界；模式config.set持久化。|不按名称排序，不改content手动顺序；原添加时间序号不是文件修改时间。|fluent_ui/views/gallery_view.py:3724 / _update_resource_sort_label；三语言组件键及最终组合绑定不同；不是一个已存在的整句翻译键。|
|TPB-030|当前resource_sort为对应模式|ResourceSort.project只在两个节点之间连续资源段内按library_added_seq排序，节点保持结构边界；模式config.set持久化。|不按名称排序，不改content手动顺序；原添加时间序号不是文件修改时间。|fluent_ui/views/gallery_view.py:3724 / _update_resource_sort_label；三语言组件键及最终组合绑定不同；不是一个已存在的整句翻译键。|
|TPB-031|当前resource_sort为对应模式|ResourceSort.project只在两个节点之间连续资源段内按library_added_seq排序，节点保持结构边界；模式config.set持久化。|不按名称排序，不改content手动顺序；原添加时间序号不是文件修改时间。|fluent_ui/views/gallery_view.py:3724 / _update_resource_sort_label；三语言组件键及最终组合绑定不同；不是一个已存在的整句翻译键。|

#### 过滤

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-032|无标签 / FilterOption/清除按钮|无标签|無標籤|No tags|タグなし|t/bind_text/translated：逐原文精确键|
|TPB-033|未分类 / FilterOption/清除按钮|未分类|未分類|Uncategorized|未分類|t/bind_text/translated：逐原文精确键|
|TPB-034|动图 / FilterOption/清除按钮|动图|動圖|Animated emotes|アニメーションスタンプ|t/bind_text/translated：逐原文精确键|
|TPB-035|静态表情 / FilterOption/清除按钮|静态表情|靜態表情|Static emotes|静止画|t/bind_text/translated：逐原文精确键|
|TPB-036|已失效的表情 / FilterOption/清除按钮|已失效的表情|Missing 表情|Missing emotes|欠落したスタンプ|t/bind_text/translated：逐原文精确键|
|TPB-037|清除筛选 / FilterOption/清除按钮|清除筛选|清除篩選|Clear filters|絞り込みを解除|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-032|点击筛选浮层选项|_update_filter写相应no_tag/unclassified/is_gif/is_static/missing并refresh_content；清除调用_clear_filter。|_matches_filter逐条件筛；活动Tag采用active_tags.issubset(tags)；清除同时清搜索与Tag。|fluent_ui/components/interaction_controls.py:172 / 类常量/声明；源码静态；本轮未运行GUI。|
|TPB-033|点击筛选浮层选项|_update_filter写相应no_tag/unclassified/is_gif/is_static/missing并refresh_content；清除调用_clear_filter。|_matches_filter逐条件筛；活动Tag采用active_tags.issubset(tags)；清除同时清搜索与Tag。|fluent_ui/components/interaction_controls.py:172 / 类常量/声明；源码静态；本轮未运行GUI。|
|TPB-034|点击筛选浮层选项|_update_filter写相应no_tag/unclassified/is_gif/is_static/missing并refresh_content；清除调用_clear_filter。|_matches_filter逐条件筛；活动Tag采用active_tags.issubset(tags)；清除同时清搜索与Tag。|fluent_ui/components/interaction_controls.py:172 / 类常量/声明；源码静态；本轮未运行GUI。|
|TPB-035|点击筛选浮层选项|_update_filter写相应no_tag/unclassified/is_gif/is_static/missing并refresh_content；清除调用_clear_filter。|_matches_filter逐条件筛；活动Tag采用active_tags.issubset(tags)；清除同时清搜索与Tag。|fluent_ui/components/interaction_controls.py:172 / 类常量/声明；源码静态；本轮未运行GUI。|
|TPB-036|点击筛选浮层选项|_update_filter写相应no_tag/unclassified/is_gif/is_static/missing并refresh_content；清除调用_clear_filter。|_matches_filter逐条件筛；活动Tag采用active_tags.issubset(tags)；清除同时清搜索与Tag。|fluent_ui/components/interaction_controls.py:172 / 类常量/声明；源码静态；本轮未运行GUI。|
|TPB-037|点击筛选浮层选项|_update_filter写相应no_tag/unclassified/is_gif/is_static/missing并refresh_content；清除调用_clear_filter。|_matches_filter逐条件筛；活动Tag采用active_tags.issubset(tags)；清除同时清搜索与Tag。|fluent_ui/components/interaction_controls.py:172 / __init__；源码静态；本轮未运行GUI。|

#### 资源右键菜单

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-038|发送表情 / Action/懒分类子菜单|发送表情|傳送表情|Send emote|スタンプを送信|t/bind_text/translated：逐原文精确键|
|TPB-039|加入分类 / Action/懒分类子菜单|加入分类|缺失；实际显示 [MISSING: 加入分类]|缺失；实际显示 [MISSING: 加入分类]|缺失；实际显示 [MISSING: 加入分类]|t/bind_text/translated：逐原文精确键|
|TPB-040|移动到分类 / Action/懒分类子菜单|移动到分类|移動至分類|Move to category|カテゴリに移動|t/bind_text/translated：逐原文精确键|
|TPB-041|从当前分类移除 / Action/懒分类子菜单|从当前分类移除|缺失；实际显示 [MISSING: 从当前分类移除]|缺失；实际显示 [MISSING: 从当前分类移除]|缺失；实际显示 [MISSING: 从当前分类移除]|t/bind_text/translated：逐原文精确键|
|TPB-042|编辑标签 / Action/懒分类子菜单|编辑标签|編輯標籤|Edit tags|タグを編集|t/bind_text/translated：逐原文精确键|
|TPB-043|在文件资源管理器中显示 / Action/懒分类子菜单|在文件资源管理器中显示|在檔案總管中顯示|Show in File Explorer|エクスプローラーで表示|t/bind_text/translated：逐原文精确键|
|TPB-044|复制文件路径 / Action/懒分类子菜单|复制文件路径|復制文件路徑|Copy file path|ファイルパスをコピー|t/bind_text/translated：逐原文精确键|
|TPB-045|导出所选表情 / Action/懒分类子菜单|导出所选表情|匯出所選表情|Export selected emotes|選択したスタンプをエクスポート|t/bind_text/translated：逐原文精确键|
|TPB-046|重新绑定文件… / Action/懒分类子菜单|重新绑定文件…|重新綁定文件…|Relink file…|ファイルを再リンク…|t/bind_text/translated：逐原文精确键|
|TPB-047|选择缩略图帧… / Action/懒分类子菜单|选择缩略图帧…|選擇縮略圖幀…|Choose thumbnail frame…|サムネイルのフレームを選択…|t/bind_text/translated：逐原文精确键|
|TPB-048|设为当前分类图标 / Action/懒分类子菜单|设为当前分类图标|設為目前分類圖示|Use as current category icon|現在のカテゴリのアイコンに設定|t/bind_text/translated：逐原文精确键|
|TPB-049|设为软件图标 / Action/懒分类子菜单|设为软件图标|設為軟體圖示|Set as app icon|アプリアイコンに設定|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-038|右键当前资源；若不在选中集合或含节点先单选当前资源|普通模式且ActionPolicy.send允许时调用use_resource(path)。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2674 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-039|右键当前资源；若不在选中集合或含节点先单选当前资源|CategoryTargetMenu以稳定节点ID回调assign_resources(copy=True)，增加成员关系。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2680 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-040|右键当前资源；若不在选中集合或含节点先单选当前资源|assign_resources(copy=False)按选中来源分组，只移除该来源关系；其它分类关系保留。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2680 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-041|右键当前资源；若不在选中集合或含节点先单选当前资源|_batch_remove_membership确认后仅remove_image_from_category(path,content_scope_node)。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2688 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-042|右键当前资源；若不在选中集合或含节点先单选当前资源|打开TagEditorDialog，通过现有资源标签服务提交。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2690 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-043|右键当前资源；若不在选中集合或含节点先单选当前资源|reveal_in_explorer(path)。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2694 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-044|右键当前资源；若不在选中集合或含节点先单选当前资源|_copy_paths把路径逐行写剪贴板；仅可复制路径的资源可用。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2696 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-045|右键当前资源；若不在选中集合或含节点先单选当前资源|_execute_batch_export复制实际存在文件到所选目录，重名加(n)。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2697 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-046|右键当前资源；若不在选中集合或含节点先单选当前资源|仅单个缺失资源；rebind_resource绑定新文件，保留身份相关业务。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2701 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-047|右键当前资源；若不在选中集合或含节点先单选当前资源|ActionPolicy.thumbnail_frame允许时FramePickerDialog，成功失效原缩略图缓存。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2703 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-048|右键当前资源；若不在选中集合或含节点先单选当前资源|仅非ROOT且set_icon允许；storage.set_node_icon(active_view,path)。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2705 / _build_resource_menu；源码静态；本轮未运行GUI。|
|TPB-049|右键当前资源；若不在选中集合或含节点先单选当前资源|_set_application_icon改变应用图标，非导入。|按ActionPolicy可用性/数量/活动分类控制；加入/移动不复制物理原件，导出复制文件不新增分类。|fluent_ui/views/gallery_view.py:2707 / _build_resource_menu；源码静态；本轮未运行GUI。|

#### 管理/选择状态

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-050|进入管理模式 / 按钮文本/Tooltip|进入管理模式|進入管理模式|Enter manage mode|管理モードに入る|t/bind_text/translated：逐原文精确键|
|TPB-051|退出管理模式 / 按钮文本/Tooltip|退出管理模式|退出管理模式|Exit manage mode|管理モードを終了|t/bind_text/translated：逐原文精确键|
|TPB-052|退出管理 / 按钮文本/Tooltip|退出管理|退出管理|Exit manage|管理を終了|t/bind_text/translated：逐原文精确键|
|TPB-053|清除选择 / 按钮文本/Tooltip|清除选择|清除選取|Clear selection|選択を解除|t/bind_text/translated：逐原文精确键|
|TPB-054|全选当前结果 / 按钮文本/Tooltip|全选当前结果|缺失；实际显示 [MISSING: 全选当前结果]|缺失；实际显示 [MISSING: 全选当前结果]|缺失；实际显示 [MISSING: 全选当前结果]|t/bind_text/translated：逐原文精确键|
|TPB-055|取消全选 / 按钮文本/Tooltip|取消全选|取消全選|Deselect all|すべての選択を解除|t/bind_text/translated：逐原文精确键|
|TPB-056|删除资源 / 按钮文本/Tooltip|删除资源|刪除表情|Delete emote|スタンプを削除|t/bind_text/translated：逐原文精确键|
|TPB-057|移除记录 / 按钮文本/Tooltip|移除记录|移除記錄|Remove record|記録を削除|t/bind_text/translated：逐原文精确键|
|TPB-058|此操作仅支持表情；请先取消所选分类节点。 / 按钮文本/Tooltip|此操作仅支持表情；请先取消所选分类节点。|缺失；实际显示 [MISSING: 此操作仅支持表情；请先取消所选分类节点。]|缺失；实际显示 [MISSING: 此操作仅支持表情；请先取消所选分类节点。]|缺失；实际显示 [MISSING: 此操作仅支持表情；请先取消所选分类节点。]|t/bind_text/translated：逐原文精确键|
|TPB-059|混合选择不能一次移动到分类；请分别选择节点或表情。 / 按钮文本/Tooltip|混合选择不能一次移动到分类；请分别选择节点或表情。|缺失；实际显示 [MISSING: 混合选择不能一次移动到分类；请分别选择节点或表情。]|缺失；实际显示 [MISSING: 混合选择不能一次移动到分类；请分别选择节点或表情。]|缺失；实际显示 [MISSING: 混合选择不能一次移动到分类；请分别选择节点或表情。]|t/bind_text/translated：逐原文精确键|
|TPB-060|计数/已选 {value_0} 项 / BodyLabel|已选 {value_0} 项|已選 {value_0} 項|{value_0} selected|{value_0} 件選択|t(key).format(...) 后 bind_text；_TranslatedText保留源键和参数|
|TPB-061|计数/已选 {value_0} 项（{value_1} 张表情，{value_2} 个节点） / BodyLabel|已选 {value_0} 项（{value_1} 张表情，{value_2} 个节点）|缺失；实际显示 [MISSING: 已选 {value_0} 项（{value_1} 张表情，{value_2} 个节点）]|缺失；实际显示 [MISSING: 已选 {value_0} 项（{value_1} 张表情，{value_2} 个节点）]|缺失；实际显示 [MISSING: 已选 {value_0} 项（{value_1} 张表情，{value_2} 个节点）]|t(key).format(...) 后 bind_text；_TranslatedText保留源键和参数|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-050|根据mode、投影、选中资源/节点类型切换状态|set_mode(manage)，取消悬停预览，资源单击选择。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1854 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-051|根据mode、投影、选中资源/节点类型切换状态|set_mode(normal)，清理选中集合。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1854 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-052|根据mode、投影、选中资源/节点类型切换状态|finish_selection→set_mode(normal)。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1885 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-053|根据mode、投影、选中资源/节点类型切换状态|普通模式上下文工具栏的finish_selection，同样回到normal并清选择。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1885 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-054|根据mode、投影、选中资源/节点类型切换状态|select_all_cards遍历entry_model.projected，不只已实例化卡片。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1881 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-055|根据mode、投影、选中资源/节点类型切换状态|select_all_cards在当前投影等于选中集合时清理。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1881 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-056|根据mode、投影、选中资源/节点类型切换状态|仅resource_only；_batch_delete→_delete_resource_ids全局删除。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1868 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-057|根据mode、投影、选中资源/节点类型切换状态|所选资源全部缺失时只移除索引相关记录。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1868 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-058|根据mode、投影、选中资源/节点类型切换状态|nodes存在时加入/标签/删除/更多禁用并显示此Tooltip。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1877 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-059|根据mode、投影、选中资源/节点类型切换状态|nodes和resources混选时移动按钮禁用并显示此Tooltip。|原始构造文字可能被本函数覆盖；禁用不清除toolTip字符串。|fluent_ui/views/gallery_view.py:1878 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-060|无节点/含节点两种分支|从稳定selected entries统计：value_0=条目，value_1=资源，value_2=节点。|同一资源按现有selection identity去重。|fluent_ui/views/gallery_view.py:1860 / _sync_command_bar；源码静态；本轮未运行GUI。|
|TPB-061|无节点/含节点两种分支|从稳定selected entries统计：value_0=条目，value_1=资源，value_2=节点。|同一资源按现有selection identity去重。|fluent_ui/views/gallery_view.py:1859 / _sync_command_bar；源码静态；本轮未运行GUI。|

#### 管理工具初始说明

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-062|复用已有资源加入目标分类，保留原分类关系和文件。 / 初始化Tooltip|复用已有资源加入目标分类，保留原分类关系和文件。|缺失；实际显示 [MISSING: 复用已有资源加入目标分类，保留原分类关系和文件。]|缺失；实际显示 [MISSING: 复用已有资源加入目标分类，保留原分类关系和文件。]|缺失；实际显示 [MISSING: 复用已有资源加入目标分类，保留原分类关系和文件。]|t/bind_text/translated：逐原文精确键|
|TPB-063|移动所选来源的分类关系；其它分类关系保留。 / 初始化Tooltip|移动所选来源的分类关系；其它分类关系保留。|缺失；实际显示 [MISSING: 移动所选来源的分类关系；其它分类关系保留。]|缺失；实际显示 [MISSING: 移动所选来源的分类关系；其它分类关系保留。]|缺失；实际显示 [MISSING: 移动所选来源的分类关系；其它分类关系保留。]|t/bind_text/translated：逐原文精确键|
|TPB-064|编辑所选资源的标签归属 / 初始化Tooltip|编辑所选资源的标签归属|缺失；实际显示 [MISSING: 编辑所选资源的标签归属]|缺失；实际显示 [MISSING: 编辑所选资源的标签归属]|缺失；实际显示 [MISSING: 编辑所选资源的标签归属]|t/bind_text/translated：逐原文精确键|
|TPB-065|调整来源分类中的持久位置；搜索或显示排序时不可用。 / 初始化Tooltip|调整来源分类中的持久位置；搜索或显示排序时不可用。|缺失；实际显示 [MISSING: 调整来源分类中的持久位置；搜索或显示排序时不可用。]|缺失；实际显示 [MISSING: 调整来源分类中的持久位置；搜索或显示排序时不可用。]|缺失；实际显示 [MISSING: 调整来源分类中的持久位置；搜索或显示排序时不可用。]|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-062|构造时bind_text；随后_sync_command_bar再次setToolTip|前三条在_sync_command_bar无节点分支被对应按钮.text()覆盖；调整位置原提示未被该循环覆盖。|不能把源码中的初始长Tooltip直接当作运行中最终提示。|fluent_ui/views/gallery_view.py:1109 / _build_command_bar；源码静态；本轮未运行GUI。|
|TPB-063|构造时bind_text；随后_sync_command_bar再次setToolTip|前三条在_sync_command_bar无节点分支被对应按钮.text()覆盖；调整位置原提示未被该循环覆盖。|不能把源码中的初始长Tooltip直接当作运行中最终提示。|fluent_ui/views/gallery_view.py:1114 / _build_command_bar；源码静态；本轮未运行GUI。|
|TPB-064|构造时bind_text；随后_sync_command_bar再次setToolTip|前三条在_sync_command_bar无节点分支被对应按钮.text()覆盖；调整位置原提示未被该循环覆盖。|不能把源码中的初始长Tooltip直接当作运行中最终提示。|fluent_ui/views/gallery_view.py:1119 / _build_command_bar；源码静态；本轮未运行GUI。|
|TPB-065|构造时bind_text；随后_sync_command_bar再次setToolTip|前三条在_sync_command_bar无节点分支被对应按钮.text()覆盖；调整位置原提示未被该循环覆盖。|不能把源码中的初始长Tooltip直接当作运行中最终提示。|fluent_ui/views/gallery_view.py:1125 / _build_command_bar；源码静态；本轮未运行GUI。|

#### 持久手动顺序

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-066|移到最前 / 调整位置菜单Action|移到最前|移到最前|Move to front|先頭に移動|t/bind_text/translated：逐原文精确键|
|TPB-067|移到最后 / 调整位置菜单Action|移到最后|移到最後|Move to back|末尾に移動|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-066|有选中且_exact_placement_available；搜索/非manual不可用|_move_selection_extreme按结构来源分组，set_content_order写持久顺序。|与显示排序不同；节点子树选择规范化，保留未移动条目相对顺序。|fluent_ui/views/gallery_view.py:1127 / _build_command_bar；源码静态；本轮未运行GUI。|
|TPB-067|有选中且_exact_placement_available；搜索/非manual不可用|_move_selection_extreme按结构来源分组，set_content_order写持久顺序。|与显示排序不同；节点子树选择规范化，保留未移动条目相对顺序。|fluent_ui/views/gallery_view.py:1127 / _build_command_bar；源码静态；本轮未运行GUI。|

#### 资源移出确认

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-068|移出选中表情的当前分类关系？ / 确认正文/副说明|移出选中表情的当前分类关系？|移除所選表情的目前分類關係？|Remove the selected emotes from their current categories?|選択したスタンプを現在のカテゴリから外しますか？|t/bind_text/translated：逐原文精确键|
|TPB-069|只删除分类关系，表情文件仍保留在表情库中。 / 确认正文/副说明|只删除分类关系，表情文件仍保留在表情库中。|只刪除分類關系，表情文件仍保留在表情庫中。|Only membership is removed; emote files stay in the library.|カテゴリとの関連だけを削除し、ファイルはライブラリに残します。|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-068|当前scope非ROOT并满足remove_from_category|确认才按当前scope删除所选资源成员关系。|不删除文件，不删除其它分类关系；取消不执行。|fluent_ui/views/gallery_view.py:2402 / _batch_remove_membership；源码静态；本轮未运行GUI。|
|TPB-069|当前scope非ROOT并满足remove_from_category|确认才按当前scope删除所选资源成员关系。|不删除文件，不删除其它分类关系；取消不执行。|fluent_ui/views/gallery_view.py:2403 / _batch_remove_membership；源码静态；本轮未运行GUI。|

#### 全局删除状态

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-070|删除选中的 {value_0} 个表情？ / 删除确认正文/分支hint|删除选中的 {value_0} 个表情？|刪除選中的 {value_0} 個表情？|Delete {value_0} selected emotes?|選択した {value_0} 件を削除しますか？|t/bind_text/translated：逐原文精确键|
|TPB-071|只删除索引记录，磁盘文件不会被改动。 / 删除确认正文/分支hint|只删除索引记录，磁盘文件不会被改动。|只刪除索引記錄，磁盤文件不會被改動。|Only the index record is deleted; disk files are unchanged.|索引の記録だけを削除し、ファイルは変更しません。|t/bind_text/translated：逐原文精确键|
|TPB-072|文件会进入 Windows 系统回收站，索引记录同时移除。 / 删除确认正文/分支hint|文件会进入 Windows 系统回收站，索引记录同时移除。|文件會進入 Windows 系統回收站，索引記錄同時移除。|Files move to the Recycle Bin and index records are removed.|ファイルをゴミ箱に移動し、索引の記録を削除します。|t/bind_text/translated：逐原文精确键|
|TPB-073|现有文件进入 Windows 回收站；失效表情只移除索引记录。 / 删除确认正文/分支hint|现有文件进入 Windows 回收站；失效表情只移除索引记录。|現有檔案移至 Windows 表情回收筒；失效表情只移除索引記錄。|Existing files go to the Windows Recycle Bin; missing emotes have only their records removed.|存在するファイルは Windows のゴミ箱へ移動し、見つからないスタンプは記録のみ削除します。|t/bind_text/translated：逐原文精确键|
|TPB-074|此操作影响资源及其所有分类关系，不只是从当前分类移除。 / 删除确认正文/分支hint|此操作影响资源及其所有分类关系，不只是从当前分类移除。|缺失；实际显示 [MISSING: 此操作影响资源及其所有分类关系，不只是从当前分类移除。]|缺失；实际显示 [MISSING: 此操作影响资源及其所有分类关系，不只是从当前分类移除。]|缺失；实际显示 [MISSING: 此操作影响资源及其所有分类关系，不只是从当前分类移除。]|t/bind_text/translated：逐原文精确键|
|TPB-075|Windows 回收站可能已接收拖放副本。此处确认是否删除图库原件；取消会保留原件，但不会移除回收站中的副本。 / 删除确认正文/分支hint|Windows 回收站可能已接收拖放副本。此处确认是否删除图库原件；取消会保留原件，但不会移除回收站中的副本。|Windows 資源回收筒可能已接收拖放副本。此處確認是否刪除圖庫原件；取消會保留原件，但不會移除資源回收筒中的副本。|Windows Recycle Bin may already contain the exported copies. Confirm whether to delete the library originals. Cancel keeps the originals, but does not remove copies from the Recycle Bin.|Windows のごみ箱にはドラッグ用コピーが既に入っている場合があります。ここではライブラリの原本を削除するか確認します。キャンセルすると原本は保持されますが、ごみ箱のコピーは削除されません。|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-070|数量正文；全部缺失/全部存在/部分缺失；recycle_drop额外说明分别显示|对资源ID快照重验后storage.delete_images_batch(expected_ids=...)。|已有文件进回收站；缺失项清记录；资源所有分类关系受影响。取消不执行此业务，不撤回Shell已接收的外拖副本。|fluent_ui/views/gallery_view.py:2451 / _delete_resource_ids；源码静态；本轮未运行GUI。|
|TPB-071|数量正文；全部缺失/全部存在/部分缺失；recycle_drop额外说明分别显示|对资源ID快照重验后storage.delete_images_batch(expected_ids=...)。|已有文件进回收站；缺失项清记录；资源所有分类关系受影响。取消不执行此业务，不撤回Shell已接收的外拖副本。|fluent_ui/views/gallery_view.py:2444 / _delete_resource_ids；源码静态；本轮未运行GUI。|
|TPB-072|数量正文；全部缺失/全部存在/部分缺失；recycle_drop额外说明分别显示|对资源ID快照重验后storage.delete_images_batch(expected_ids=...)。|已有文件进回收站；缺失项清记录；资源所有分类关系受影响。取消不执行此业务，不撤回Shell已接收的外拖副本。|fluent_ui/views/gallery_view.py:2445 / _delete_resource_ids；源码静态；本轮未运行GUI。|
|TPB-073|数量正文；全部缺失/全部存在/部分缺失；recycle_drop额外说明分别显示|对资源ID快照重验后storage.delete_images_batch(expected_ids=...)。|已有文件进回收站；缺失项清记录；资源所有分类关系受影响。取消不执行此业务，不撤回Shell已接收的外拖副本。|fluent_ui/views/gallery_view.py:2446 / _delete_resource_ids；源码静态；本轮未运行GUI。|
|TPB-074|数量正文；全部缺失/全部存在/部分缺失；recycle_drop额外说明分别显示|对资源ID快照重验后storage.delete_images_batch(expected_ids=...)。|已有文件进回收站；缺失项清记录；资源所有分类关系受影响。取消不执行此业务，不撤回Shell已接收的外拖副本。|fluent_ui/views/gallery_view.py:2447 / _delete_resource_ids；源码静态；本轮未运行GUI。|
|TPB-075|数量正文；全部缺失/全部存在/部分缺失；recycle_drop额外说明分别显示|对资源ID快照重验后storage.delete_images_batch(expected_ids=...)。|已有文件进回收站；缺失项清记录；资源所有分类关系受影响。取消不执行此业务，不撤回Shell已接收的外拖副本。|fluent_ui/views/gallery_view.py:2449 / _delete_resource_ids；源码静态；本轮未运行GUI。|

#### 分类结构确认

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-076|分类是逻辑关系，不会创建或移动磁盘目录。 / 新建hint/删除正文与hint|分类是逻辑关系，不会创建或移动磁盘目录。|分類是邏輯關系，不會創建或移動磁盤目錄。|Categories do not create or move folders on disk.|カテゴリ操作でディスクのフォルダは作成・移動されません。|t/bind_text/translated：逐原文精确键|
|TPB-077|删除分类“{value_0}”？ / 新建hint/删除正文与hint|删除分类“{value_0}”？|刪除分類“{value_0}”？|Delete category “{value_0}”?|カテゴリ「{value_0}」を削除しますか？|t/bind_text/translated：逐原文精确键|
|TPB-078|分类本身将被删除，表情文件不会删除。<br>其下 {child_count} 个子分类将提升到上一级。<br>直接属于该分类的 {emote_count} 张表情将移出分类。 / 新建hint/删除正文与hint|分类本身将被删除，表情文件不会删除。<br>其下 {child_count} 个子分类将提升到上一级。<br>直接属于该分类的 {emote_count} 张表情将移出分类。|分類本身將被刪除，表情檔案不會刪除。<br>其下 {child_count} 個子分類將提升到上一層。<br>直接屬於該分類的 {emote_count} 張表情將移出分類。|The category will be deleted; emote files will remain.<br>Its {child_count} child categories will move up one level.<br>Its {emote_count} directly associated emotes will be removed from this category.|カテゴリのみ削除し、スタンプのファイルは残します。<br>{child_count} 件の子カテゴリは一階層上に移動します。<br>直接属する {emote_count} 件のスタンプはこのカテゴリから外れます。|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-076|创建输入或删除确认|新建create_node；删除storage.delete_node→LibraryIndex.delete_node。|删除分类的子分类提升父级，表情本体保留；动态name/child_count/emote_count来自节点与node_counts，未取私人数据。|fluent_ui/views/gallery_view.py:526 / create_node；源码静态；本轮未运行GUI。|
|TPB-077|创建输入或删除确认|新建create_node；删除storage.delete_node→LibraryIndex.delete_node。|删除分类的子分类提升父级，表情本体保留；动态name/child_count/emote_count来自节点与node_counts，未取私人数据。|fluent_ui/views/gallery_view.py:633 / delete_node；源码静态；本轮未运行GUI。|
|TPB-078|创建输入或删除确认|新建create_node；删除storage.delete_node→LibraryIndex.delete_node。|删除分类的子分类提升父级，表情本体保留；动态name/child_count/emote_count来自节点与node_counts，未取私人数据。|fluent_ui/views/gallery_view.py:635 / delete_node；源码静态；本轮未运行GUI。|

#### Relative Tabs

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-079|分类Tab标签/Tooltip / TabStrip|&lt;当前分类显示名：动态用户内容&gt;|原样动态内容（非译文）|原样动态内容（非译文）|原样动态内容（非译文）|动态用户内容/原样|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-079|set_tabs(labels,current)时tabText与tabToolTip使用同一个label|_on_category_tab→set_relative_view(_tab_nodes[index])；不是set_node。|保持左树正式当前位置/展开/滚动语义；不按Tab文字解析身份。|fluent_ui/components/navigation.py:899 / set_tabs；用户分类名原样；无需也不能为其补造翻译。标签集合构建见gallery_view的_tab_nodes。|

#### 资源拖放选择

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-080|移动到「{name}」 / Drop后Action/禁用说明|移动到「{name}」|移動至「{name}」|Move to “{name}”|「{name}」へ移動|t/bind_text/translated：逐原文精确键|
|TPB-081|加入分类「{name}」 / Drop后Action/禁用说明|加入分类「{name}」|缺失；实际显示 [MISSING: 加入分类「{name}」]|缺失；实际显示 [MISSING: 加入分类「{name}」]|缺失；实际显示 [MISSING: 加入分类「{name}」]|t/bind_text/translated：逐原文精确键|
|TPB-082|全部表情来源项仅加入目标分类，其它分类关系保留 / Drop后Action/禁用说明|全部表情来源项仅加入目标分类，其它分类关系保留|缺失；实际显示 [MISSING: 全部表情来源项仅加入目标分类，其它分类关系保留]|缺失；实际显示 [MISSING: 全部表情来源项仅加入目标分类，其它分类关系保留]|缺失；实际显示 [MISSING: 全部表情来源项仅加入目标分类，其它分类关系保留]|t/bind_text/translated：逐原文精确键|
|TPB-083|全部表情已包含这些表情 / Drop后Action/禁用说明|全部表情已包含这些表情|全部表情已包含這些表情|All emotes already contains these items|すべてのスタンプに含まれています|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-080|真实释放后QTimer.singleShot回正常GUI，target非ROOT/混合ROOT来源/ROOT目标分支|菜单选移动或加入才_apply_drop_action，sources按拖动开始来源分组；target title来自稳定节点ID查到的原名。|取消只menu.close；悬停切Tab不提前执行此菜单或数据提交。ROOT来源不移除“全部表情”身份。|fluent_ui/views/gallery_view.py:3831 / request_resource_drop；源码静态；本轮未运行GUI。|
|TPB-081|真实释放后QTimer.singleShot回正常GUI，target非ROOT/混合ROOT来源/ROOT目标分支|菜单选移动或加入才_apply_drop_action，sources按拖动开始来源分组；target title来自稳定节点ID查到的原名。|取消只menu.close；悬停切Tab不提前执行此菜单或数据提交。ROOT来源不移除“全部表情”身份。|fluent_ui/views/gallery_view.py:3838 / request_resource_drop；源码静态；本轮未运行GUI。|
|TPB-082|真实释放后QTimer.singleShot回正常GUI，target非ROOT/混合ROOT来源/ROOT目标分支|菜单选移动或加入才_apply_drop_action，sources按拖动开始来源分组；target title来自稳定节点ID查到的原名。|取消只menu.close；悬停切Tab不提前执行此菜单或数据提交。ROOT来源不移除“全部表情”身份。|fluent_ui/views/gallery_view.py:3835 / request_resource_drop；源码静态；本轮未运行GUI。|
|TPB-083|真实释放后QTimer.singleShot回正常GUI，target非ROOT/混合ROOT来源/ROOT目标分支|菜单选移动或加入才_apply_drop_action，sources按拖动开始来源分组；target title来自稳定节点ID查到的原名。|取消只menu.close；悬停切Tab不提前执行此菜单或数据提交。ROOT来源不移除“全部表情”身份。|fluent_ui/views/gallery_view.py:3843 / request_resource_drop；源码静态；本轮未运行GUI。|

#### 持久手动顺序限制

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-084|请先清空搜索再调整手动顺序 / FeedbackHost.hint|请先清空搜索再调整手动顺序|請先清除搜尋再調整手動順序|Clear search before rearranging items|並べ替える前に検索を解除してください|t/bind_text/translated：逐原文精确键|
|TPB-085|当前是临时显示排序，请先切回手动顺序 / FeedbackHost.hint|当前是临时显示排序，请先切回手动顺序|目前為暫時顯示排序，請先切回手動順序|Switch to manual order before arranging items.|並べ替える前に手動順に戻してください|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-084|search非空或content_sort非manual|返回False，当前调整顺序命令不继续写库。|显示排序模式虽config持久化，但手动内容顺序不被临时投影重写。|fluent_ui/views/gallery_view.py:3749 / _manual_order_available；源码静态；本轮未运行GUI。|
|TPB-085|search非空或content_sort非manual|返回False，当前调整顺序命令不继续写库。|显示排序模式虽config持久化，但手动内容顺序不被临时投影重写。|fluent_ui/views/gallery_view.py:3752 / _manual_order_available；源码静态；本轮未运行GUI。|

#### 分类动态计数

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-086|表情库全部表情 · {value_0} 项 / Tree item ToolTipRole / NodeCard Tooltip|表情库全部表情 · {value_0} 项|表情庫全部表情 · {value_0} 項|All library emotes · {value_0} items|すべてのスタンプ · {value_0} 件|t(key).format(...)；NodeCard再bind_text保留_TranslatedText，Tree由刷新赋item|
|TPB-087|{value_0}<br>{value_1} 个子分类 · {value_2} 项直接内容 / Tree item ToolTipRole / NodeCard Tooltip|{value_0}<br>{value_1} 个子分类 · {value_2} 项直接内容|{value_0}<br>{value_1} 個子分類 · {value_2} 項直接內容|{value_0}<br>{value_1} subcategories · {value_2} direct items|{value_0}<br>サブカテゴリ {value_1} · 直接の項目 {value_2}|t(key).format(...)；NodeCard再bind_text保留_TranslatedText，Tree由刷新赋item|
|TPB-088|{value_0}<br>{value_1} 个子分类 · {value_2} 项内容 / Tree item ToolTipRole / NodeCard Tooltip|{value_0}<br>{value_1} 个子分类 · {value_2} 项内容|{value_0}<br>{value_1} 個子分類 · {value_2} 項內容|{value_0}<br>{value_1} subcategories · {value_2} items|{value_0}<br>サブカテゴリ {value_1} · 項目 {value_2}|t(key).format(...)；NodeCard再bind_text保留_TranslatedText，Tree由刷新赋item|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-086|根Tree/普通Tree/图库NodeCard三个对应入口|value_0为统计总资源数或用户节点原名，value_1为children，value_2为direct资源数或entry.total；各自按源参数，不互换。|动态名称不翻译；Tree“直接内容”和图库entry.total不是由同一个字面标签推断出来的范围。|fluent_ui/components/library_tree.py:331 / _set_item_counts；源码静态；本轮未运行GUI。|
|TPB-087|根Tree/普通Tree/图库NodeCard三个对应入口|value_0为统计总资源数或用户节点原名，value_1为children，value_2为direct资源数或entry.total；各自按源参数，不互换。|动态名称不翻译；Tree“直接内容”和图库entry.total不是由同一个字面标签推断出来的范围。|fluent_ui/components/library_tree.py:333 / _set_item_counts；源码静态；本轮未运行GUI。|
|TPB-088|根Tree/普通Tree/图库NodeCard三个对应入口|value_0为统计总资源数或用户节点原名，value_1为children，value_2为direct资源数或entry.total；各自按源参数，不互换。|动态名称不翻译；Tree“直接内容”和图库entry.total不是由同一个字面标签推断出来的范围。|fluent_ui/components/node_card.py:93 / __init__；源码静态；本轮未运行GUI。|

#### 资源删除菜单状态

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-089|从 Nekori 删除所选表情 / 资源右键Action|从 Nekori 删除所选表情|從 Nekori 刪除所選表情|Delete selected emotes from Nekori|選択したスタンプを Nekori から削除|t/bind_text/translated：逐原文精确键|
|TPB-091|删除表情（回收站） / 资源右键Action|删除表情（回收站）|刪除表情（回收站）|Delete emote (Recycle Bin)|スタンプを削除（ゴミ箱）|t/bind_text/translated：逐原文精确键|
|TPB-093|移除失效记录 / 资源右键Action|移除失效记录|移除失效記錄|Remove invalid record|無効な記録を削除|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-089|len(paths)!=1|_build_resource_menu的action辅助函数经translated(Action,ActionPolicy.delete_label(context))绑定当前文字。|三条是不同状态：批量、单个存在、单个缺失；删除仍需后续确认，不在菜单构造时执行。|services/action_policy.py:55 / delete_label；源码静态；本轮未运行GUI。|
|TPB-091|单资源且existing非空|_build_resource_menu的action辅助函数经translated(Action,ActionPolicy.delete_label(context))绑定当前文字。|三条是不同状态：批量、单个存在、单个缺失；删除仍需后续确认，不在菜单构造时执行。|services/action_policy.py:56 / delete_label；源码静态；本轮未运行GUI。|
|TPB-093|单资源且existing为空|_build_resource_menu的action辅助函数经translated(Action,ActionPolicy.delete_label(context))绑定当前文字。|三条是不同状态：批量、单个存在、单个缺失；删除仍需后续确认，不在菜单构造时执行。|services/action_policy.py:56 / delete_label；源码静态；本轮未运行GUI。|

#### 删除工具栏最终Tooltip

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-090|从 Nekori 删除所选表情 / 管理工具栏Tooltip状态覆盖|从 Nekori 删除所选表情|从 Nekori 删除所选表情（未调用i18n）|从 Nekori 删除所选表情（未调用i18n）|从 Nekori 删除所选表情（未调用i18n）|状态覆盖未调用i18n：最终直接setToolTip原返回值|
|TPB-092|删除表情（回收站） / 管理工具栏Tooltip状态覆盖|删除表情（回收站）|删除表情（回收站）（未调用i18n）|删除表情（回收站）（未调用i18n）|删除表情（回收站）（未调用i18n）|状态覆盖未调用i18n：最终直接setToolTip原返回值|
|TPB-094|移除失效记录 / 管理工具栏Tooltip状态覆盖|移除失效记录|移除失效记录（未调用i18n）|移除失效记录（未调用i18n）|移除失效记录（未调用i18n）|状态覆盖未调用i18n：最终直接setToolTip原返回值|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-090|len(paths)!=1；_sync_command_bar完成后的无节点分支|先bind_text设置已翻译提示，后for循环直接setToolTip(ActionPolicy.delete_label(context))返回的原中文。|此后language_changed可能由仍存在的_TextBinding改回译文；下一次_sync_command_bar会再次直接覆盖。|services/action_policy.py:55 / delete_label；实际覆盖入口gallery_view.py::_sync_command_bar:1876；这里不是称所有时间都无翻译。|
|TPB-092|单资源且existing非空；_sync_command_bar完成后的无节点分支|先bind_text设置已翻译提示，后for循环直接setToolTip(ActionPolicy.delete_label(context))返回的原中文。|此后language_changed可能由仍存在的_TextBinding改回译文；下一次_sync_command_bar会再次直接覆盖。|services/action_policy.py:56 / delete_label；实际覆盖入口gallery_view.py::_sync_command_bar:1876；这里不是称所有时间都无翻译。|
|TPB-094|单资源且existing为空；_sync_command_bar完成后的无节点分支|先bind_text设置已翻译提示，后for循环直接setToolTip(ActionPolicy.delete_label(context))返回的原中文。|此后language_changed可能由仍存在的_TextBinding改回译文；下一次_sync_command_bar会再次直接覆盖。|services/action_policy.py:56 / delete_label；实际覆盖入口gallery_view.py::_sync_command_bar:1876；这里不是称所有时间都无翻译。|

### B. Tag Panel 与共享展开控件

#### Tag折叠状态

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-095|收起标签 / EdgeDockPanelChrome/Tooltip|收起标签|收合標籤|Collapse tags|タグを折りたたむ|t(按expanded分支)；language_changed连接refresh_text|
|TPB-096|展开标签 / EdgeDockPanelChrome/Tooltip|展开标签|展開標籤|Expand tags|タグを展開|t(按expanded分支)；language_changed连接refresh_text|
|TPB-097|带筛选的收起提示 / chrome Tooltip|1：展开标签<br>2：标签筛选|1：展開標籤<br>2：標籤篩選|1：Expand tags<br>2：Tag filters|1：タグを展開<br>2：タグの絞り込み|组合：两个精确键+整数；set_active_filters执行时更新|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-095|expanded=True，四向相同；可见btn_collapse及其标题有效区域|同一panel.toggle_collapse_requested信号。|独立新建/排序/数量区域优先排除；停靠只改方向与几何，不改这两个状态文本。|fluent_ui/components/panel_host.py:63 / refresh_text；源码静态；本轮未运行GUI。|
|TPB-096|expanded=False，四向相同；收起chrome|同一toggle_collapse_requested信号。|独立新建/排序/数量区域优先排除；停靠只改方向与几何，不改这两个状态文本。|fluent_ui/components/panel_host.py:63 / refresh_text；源码静态；本轮未运行GUI。|
|TPB-097|names非空时：t(展开标签)+ · +len(names)+空格+t(标签筛选)|仅提示活动过滤个数；names来自图库active_tags。|数量非标签总量；未翻译标签名称本身。|fluent_ui/components/tag_panel.py:843 / set_active_filters；源码静态；本轮未运行GUI。|

#### Tag标题与操作

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-098|标签 / 标题/计数/按钮Tooltip|标签|標簽|Tags|タグ|t/bind_text/translated：逐原文精确键|
|TPB-099|{value_0} 个标签 / 标题/计数/按钮Tooltip|{value_0} 个标签|{value_0} 個標籤|{value_0} tags|{value_0} 個のタグ|t/bind_text/translated：逐原文精确键|
|TPB-100|新建标签 / 标题/计数/按钮Tooltip|新建标签|新增標籤|New tag|新しいタグ|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-098|当前面板；_fit_collapsed_identity根据空间决定计数可见性|title_label ToolTip及AccessibleName；展开标题文字同键。|收起时title_label和header_actions隐藏；底层toolTip文本未因此清除。|fluent_ui/components/tag_panel.py:578 / _fit_collapsed_identity；源码静态；本轮未运行GUI。|
|TPB-099|当前面板；_fit_collapsed_identity根据空间决定计数可见性|value_0=flow.count()；可见count_label只显示数字，Tooltip显示模板。|收起时title_label和header_actions隐藏；底层toolTip文本未因此清除。|fluent_ui/components/tag_panel.py:744 / _refresh_header；源码静态；本轮未运行GUI。|
|TPB-100|当前面板；_fit_collapsed_identity根据空间决定计数可见性|create_tag→model.create；新Tag属于全库而不是当前分类。|收起时title_label和header_actions隐藏；底层toolTip文本未因此清除。|fluent_ui/components/tag_panel.py:471 / __init__；源码静态；本轮未运行GUI。|

#### Tag排序

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-101|标签显示排序/手动顺序 / SortCycleButton/Tooltip|1：标签显示排序<br>2：手动顺序<br>3：临时显示排序，不改动手动顺序|1：標籤顯示排序<br>2：手動順序<br>3：臨時顯示排序，不會改動手動順序|1：Tag display order<br>2：Manual order<br>3：Temporary display order; the manual order is unchanged|1：タグの表示順<br>2：手動の順序<br>3：一時的な表示順です。手動の並び順は変更されません|组合：SortCycleButton.refresh逐片t；language_changed自动refresh|
|TPB-102|标签显示排序/名称 A→Z / SortCycleButton/Tooltip|1：标签显示排序<br>2：名称 A→Z<br>3：临时显示排序，不改动手动顺序|1：標籤顯示排序<br>2：名稱 A→Z<br>3：臨時顯示排序，不會改動手動順序|1：Tag display order<br>2：Name A→Z<br>3：Temporary display order; the manual order is unchanged|1：タグの表示順<br>2：名前 A→Z<br>3：一時的な表示順です。手動の並び順は変更されません|组合：SortCycleButton.refresh逐片t；language_changed自动refresh|
|TPB-103|标签显示排序/名称 Z→A / SortCycleButton/Tooltip|1：标签显示排序<br>2：名称 Z→A<br>3：临时显示排序，不改动手动顺序|1：標籤顯示排序<br>2：名稱 Z→A<br>3：臨時顯示排序，不會改動手動順序|1：Tag display order<br>2：Name Z→A<br>3：Temporary display order; the manual order is unchanged|1：タグの表示順<br>2：名前 Z→A<br>3：一時的な表示順です。手動の並び順は変更されません|组合：SortCycleButton.refresh逐片t；language_changed自动refresh|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-101|btn_sort三态循环；排序不因标签数量变而自动改变|set_sort写tag_sort偏好，SectionedProjection生成临时名称显示，manual才允许手动拖排。|不调用TagOrderModel.reorder来保存字母序；手动Tag顺序与分类兄弟顺序不同。|fluent_ui/components/tag_panel.py:468 / __init__；源码静态；本轮未运行GUI。|
|TPB-102|btn_sort三态循环；排序不因标签数量变而自动改变|set_sort写tag_sort偏好，SectionedProjection生成临时名称显示，manual才允许手动拖排。|不调用TagOrderModel.reorder来保存字母序；手动Tag顺序与分类兄弟顺序不同。|fluent_ui/components/tag_panel.py:468 / __init__；源码静态；本轮未运行GUI。|
|TPB-103|btn_sort三态循环；排序不因标签数量变而自动改变|set_sort写tag_sort偏好，SectionedProjection生成临时名称显示，manual才允许手动拖排。|不调用TagOrderModel.reorder来保存字母序；手动Tag顺序与分类兄弟顺序不同。|fluent_ui/components/tag_panel.py:468 / __init__；源码静态；本轮未运行GUI。|

#### Tag停靠菜单

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-104|顶部 / Checkable Action|顶部|頂部|Top|上|t/bind_text/translated：逐原文精确键|
|TPB-105|底部 / Checkable Action|底部|底部|Bottom|下|t/bind_text/translated：逐原文精确键|
|TPB-106|左侧 / Checkable Action|左侧|左側|Left|左|t/bind_text/translated：逐原文精确键|
|TPB-107|右侧 / Checkable Action|右侧|右側|Right|右|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-104|标题右键菜单；当前_placement对应选中|_request_position→host.set_placement，并sync_external_preference(tag_panel_placement)。|立即改变停靠并沿host配置保存，不改变Tag内容/选择；本轮不执行。|fluent_ui/components/tag_panel.py:709 / _show_position_menu；源码静态；本轮未运行GUI。|
|TPB-105|标题右键菜单；当前_placement对应选中|_request_position→host.set_placement，并sync_external_preference(tag_panel_placement)。|立即改变停靠并沿host配置保存，不改变Tag内容/选择；本轮不执行。|fluent_ui/components/tag_panel.py:709 / _show_position_menu；源码静态；本轮未运行GUI。|
|TPB-106|标题右键菜单；当前_placement对应选中|_request_position→host.set_placement，并sync_external_preference(tag_panel_placement)。|立即改变停靠并沿host配置保存，不改变Tag内容/选择；本轮不执行。|fluent_ui/components/tag_panel.py:709 / _show_position_menu；源码静态；本轮未运行GUI。|
|TPB-107|标题右键菜单；当前_placement对应选中|_request_position→host.set_placement，并sync_external_preference(tag_panel_placement)。|立即改变停靠并沿host配置保存，不改变Tag内容/选择；本轮不执行。|fluent_ui/components/tag_panel.py:709 / _show_position_menu；源码静态；本轮未运行GUI。|

#### Tag管理

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-108|标签属于整个表情库，不是当前分类的子项。 / 菜单/输入/确认|标签属于整个表情库，不是当前分类的子项。|標籤屬於整個表情庫，不是目前分類的子項目。|A tag belongs to the whole library, not to the current category.|タグはライブラリ全体に属し、現在の分類の子項目ではありません。|t/bind_text/translated：逐原文精确键|
|TPB-109|标签名 / 菜单/输入/确认|标签名|標籤名稱|Tag name|タグ名|t/bind_text/translated：逐原文精确键|
|TPB-110|重命名标签… / 菜单/输入/确认|重命名标签…|重新命名標籤…|Rename tag…|タグ名を変更…|t/bind_text/translated：逐原文精确键|
|TPB-111|删除标签 / 菜单/输入/确认|删除标签|刪除標籤|Delete tag|タグを削除|t/bind_text/translated：逐原文精确键|
|TPB-112|删除选中的 {value_0} 个标签 / 菜单/输入/确认|删除选中的 {value_0} 个标签|刪除選取的 {value_0} 個標籤|Delete the {value_0} selected tags|選択した {value_0} 個のタグを削除|t/bind_text/translated：逐原文精确键|
|TPB-113|删除标签 {value_0}？ / 菜单/输入/确认|删除标签 {value_0}？|刪除標籤 {value_0}？|Delete the tag {value_0}?|タグ {value_0} を削除しますか？|t/bind_text/translated：逐原文精确键|
|TPB-114|删除选中的 {value_0} 个标签？ / 菜单/输入/确认|删除选中的 {value_0} 个标签？|刪除選取的 {value_0} 個標籤？|Delete the {value_0} selected tags?|選択した {value_0} 個のタグを削除しますか？|t/bind_text/translated：逐原文精确键|
|TPB-115|只删除标签本身以及它与表情的关联，不会删除任何表情文件。 / 菜单/输入/确认|只删除标签本身以及它与表情的关联，不会删除任何表情文件。|只會刪除標籤本身以及它與表情的關聯，不會刪除任何表情檔案。|Only the tag and its links to emotes are removed; no emote file is deleted.|タグそのものとスタンプとの関連だけを削除します。スタンプのファイルは削除されません。|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-108|对应单选/多选/输入/确认状态|model.create后发tags_changed，消息内容保留用户name.strip()。|标签删除与资源删除不同；名称原样，不能因语言切换改写。|fluent_ui/components/tag_panel.py:768 / create_tag；源码静态；本轮未运行GUI。|
|TPB-109|对应单选/多选/输入/确认状态|输入标签名字；rename复用同名字段但对应model.rename。|标签删除与资源删除不同；名称原样，不能因语言切换改写。|fluent_ui/components/tag_panel.py:767 / create_tag；源码静态；本轮未运行GUI。|
|TPB-110|对应单选/多选/输入/确认状态|单选时调用_rename(name)，多选无此入口。|标签删除与资源删除不同；名称原样，不能因语言切换改写。|fluent_ui/components/tag_panel.py:830 / _show_context_menu；源码静态；本轮未运行GUI。|
|TPB-111|对应单选/多选/输入/确认状态|单选调用_delete([name])。|标签删除与资源删除不同；名称原样，不能因语言切换改写。|fluent_ui/components/tag_panel.py:834 / _show_context_menu；源码静态；本轮未运行GUI。|
|TPB-112|对应单选/多选/输入/确认状态|多选时value_0=len(selection)，调用_delete(selection)。|标签删除与资源删除不同；名称原样，不能因语言切换改写。|fluent_ui/components/tag_panel.py:838 / _show_context_menu；源码静态；本轮未运行GUI。|
|TPB-113|对应单选/多选/输入/确认状态|单选动态名称；用户名称不翻译。|标签删除与资源删除不同；名称原样，不能因语言切换改写。|fluent_ui/components/tag_panel.py:796 / _delete；源码静态；本轮未运行GUI。|
|TPB-114|对应单选/多选/输入/确认状态|多选动态数量。|标签删除与资源删除不同；名称原样，不能因语言切换改写。|fluent_ui/components/tag_panel.py:798 / _delete；源码静态；本轮未运行GUI。|
|TPB-115|对应单选/多选/输入/确认状态|确认后model.delete(names)，取消保持。|标签删除与资源删除不同；名称原样，不能因语言切换改写。|fluent_ui/components/tag_panel.py:801 / _delete；源码静态；本轮未运行GUI。|

#### Tag动态内容

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-116|Tag名称Tooltip / TagFlow|&lt;当前鼠标命中的Tag.name：动态用户内容&gt;|原样动态内容（非译文）|原样动态内容（非译文）|原样动态内容（非译文）|动态用户内容/原样|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-116|鼠标命中tag时；无命中为空|_items[hovered].name原样作为Tooltip；普通单击释放emit filter_requested。|Ctrl/Shift参与Tag自身选择/拖动，不意味着修改资源Tag；gallery.active_tags的过滤与管理选择不同。|fluent_ui/components/tag_panel.py:251 / mouseMoveEvent；源码静态；本轮未运行GUI。|

### C. 设置中心（按真实页面分组）

#### 常规/启动与窗口

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-117|开机自启动 / SwitchRow|名称：开机自启动<br>副描述：登录 Windows 后自动启动到托盘；移动程序后请重新开启。|名称：開機自啟動<br>副描述：登錄 Windows 后自動啟動到托盤；移動程序后請重新開啟。|名称：Launch at startup<br>副描述：Start in the tray at Windows sign-in. Re-enable after moving the app.|名称：自動起動<br>副描述：Windows ログイン時にトレイへ起動します。アプリ移動後は再設定してください。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-118|主窗口始终置顶 / SwitchRow|名称：主窗口始终置顶<br>副描述：让 Nekori 始终显示在其他窗口之上。|名称：主視窗始終置頂<br>副描述：讓 Nekori 始終顯示在其他窗口之上。|名称：Always on Top<br>副描述：Keep Nekori above other windows.|名称：常に最前面に表示<br>副描述：Nekori を常に最前面に表示します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-119|粘贴后自动隐藏主面板 / SwitchRow|名称：粘贴后自动隐藏主面板<br>副描述：复制并尝试粘贴后隐藏主面板，仍可用快捷键呼出。|名称：貼上後自動隱藏主面板<br>副描述：復制并嘗試粘貼后隱藏主面板，仍可用快捷鍵呼出。|名称：Hide main panel after pasting<br>副描述：Hide after copy/paste; reopen with the shortcut.|名称：貼り付け後にメインパネルを隠す<br>副描述：コピー・貼り付け後に非表示にします。ショートカットで再表示できます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-120|在任务栏显示应用图标 / SwitchRow|名称：在任务栏显示应用图标<br>副描述：关闭后不再占用任务栏入口，仍驻留托盘；下次显示主窗口或重启后生效。|名称：在工作列顯示應用程式圖示<br>副描述：關閉後僅保留系統匣入口；下次顯示主視窗或重新啟動後生效。|名称：Show app in taskbar<br>副描述：When off, keep only the tray entry. Takes effect next time the main window is shown or the app restarts.|名称：タスクバーに表示<br>副描述：オフの場合はトレイのみ使用します。次回のメイン画面表示または再起動時に反映されます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-117|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|save中AutostartService.set_enabled；不是仅写JSON。|设置键=autostart；不执行本轮修改。|fluent_ui/views/settings_center.py:232 / _page_startup；源码静态；本轮未运行GUI。|
|TPB-118|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|MainWindow.on_settings_changed→apply_window_flags。|设置键=always_on_top；不执行本轮修改。|fluent_ui/views/settings_center.py:248 / _page_startup；源码静态；本轮未运行GUI。|
|TPB-119|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|Gallery._on_send_finished仅SendResult.SENT且此键true才隐藏。|设置键=hide_main_after_paste；不执行本轮修改。|fluent_ui/views/settings_center.py:248 / _page_startup；源码静态；本轮未运行GUI。|
|TPB-120|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|show/窗口flags路径读取，源码副描述注明下次显示或重启；未实测时序。|设置键=show_taskbar_icon；不执行本轮修改。|fluent_ui/views/settings_center.py:248 / _page_startup；源码静态；本轮未运行GUI。|

#### 常规/托盘

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-121|左键单击 / ChoiceRow|名称：左键单击<br>副描述：单击托盘图标时执行此操作。|名称：左鍵單擊<br>副描述：點選系統匣圖示時執行此操作。|名称：Left click<br>副描述：Run this action when you click the tray icon.|名称：左クリック<br>副描述：トレイアイコンをクリックしたときに実行します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-122|左键双击 / ChoiceRow|名称：左键双击<br>副描述：双击托盘图标时执行此操作。|名称：左鍵連按兩下<br>副描述：連按兩下系統匣圖示時執行此操作。|名称：Left double-click<br>副描述：Run this action when you double-click the tray icon.|名称：左ダブルクリック<br>副描述：トレイアイコンをダブルクリックしたときに実行します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-123|中键单击 / ChoiceRow|名称：中键单击<br>副描述：按下鼠标中键时执行此操作。|名称：中鍵單擊<br>副描述：按下滑鼠中鍵時執行此操作。|名称：Middle click<br>副描述：Run this action when you middle-click the tray icon.|名称：中クリック<br>副描述：マウスの中ボタンを押したときに実行します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-124|右键单击 / InfoRow|名称：右键单击<br>副描述：右键固定打开托盘菜单，不能重新绑定。|名称：右鍵單擊<br>副描述：右鍵固定開啟系統匣選單，無法重新綁定。|名称：Right click<br>副描述：Right-click always opens the tray menu.|名称：右クリック<br>副描述：右クリックは常にトレイメニューを開きます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-121|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|MainWindow托盘手势分发读取此动作键；右键不参与重绑。|设置键=tray_left_click；不执行本轮修改。|fluent_ui/views/settings_center.py:266 / _page_tray；源码静态；本轮未运行GUI。|
|TPB-122|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|MainWindow托盘手势分发读取此动作键；右键不参与重绑。|设置键=tray_left_double_click；不执行本轮修改。|fluent_ui/views/settings_center.py:266 / _page_tray；源码静态；本轮未运行GUI。|
|TPB-123|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|MainWindow托盘手势分发读取此动作键；右键不参与重绑。|设置键=tray_middle_click；不执行本轮修改。|fluent_ui/views/settings_center.py:266 / _page_tray；源码静态；本轮未运行GUI。|
|TPB-124|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|只读InfoRow，固定打开托盘菜单。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:268 / _page_tray；源码静态；本轮未运行GUI。|

#### 常规/语言

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-125|界面语言 / ChoiceRow|名称：界面语言<br>副描述：更改软件的显示语言。|名称：界面語言<br>副描述：更改軟件的顯示語言。|名称：Display language<br>副描述：Change the display language.|名称：表示言語<br>副描述：表示言語を変更します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-125|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|save中i18n_engine.set_language；不在PREVIEW_KEYS。|设置键=language；不执行本轮修改。|fluent_ui/views/settings_center.py:281 / _page_language；ChoiceRow对language选项不调用t(label)：SUPPORTED_LANGUAGES按zh/zh_TW/en/ja显示简体中文/繁體中文/English/日本語，自称原样保留；并非缺译。|

#### 常规/配置管理

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-126|导出设置 / ActionRow|名称：导出设置<br>副描述：把当前应用设置写入一个 JSON 文件。|名称：匯出設定<br>副描述：把當前應用設置寫入一個 JSON 文件。|名称：Export options<br>副描述：Export current settings as JSON.|名称：書き出し設定<br>副描述：現在の設定を JSON ファイルに書き出します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-127|导入设置 / ActionRow|名称：导入设置<br>副描述：从 JSON 文件恢复应用设置。|名称：導入設置<br>副描述：從 JSON 文件恢復應用設置。|名称：Import settings<br>副描述：Load application settings from JSON.|名称：設定をインポート<br>副描述：JSON ファイルから設定を読み込みます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-128|恢复全部默认 / ActionRow|名称：恢复全部默认<br>副描述：把所有应用设置恢复到程序默认值；不会改动表情库内容。|名称：恢復全部默認<br>副描述：把所有應用設置恢復到程序默認值；不會改動表情庫內容。|名称：Reset all settings<br>副描述：Reset settings without changing library content.|名称：すべて初期値に戻す<br>副描述：ライブラリを変更せずに設定を初期値に戻します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-200|导出设置/导出… / ActionRow/SuzuExportRow按钮|导出…|導出…|Export…|書き出し…|t/bind_text/translated：逐原文精确键|
|TPB-203|导入设置/导入… / ActionRow/SuzuExportRow按钮|导入…|導入…|Import…|取り込み…|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-126|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|_export_settings写config.config快照，排除window_geometry/window_screen；不含pending。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:642 / _page_settings_file；初始副描述为表内原文；_page_settings_file末尾调用_set_dirty，非dirty时export_hint.set_hint空串，dirty时改为未保存修改提示。当前有效描述不能仅按构造字面量认定。|
|TPB-127|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|_import_settings检查JSON对象、已知键/类型/范围后_stage；未直接保存。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:646 / _page_settings_file；源码静态；本轮未运行GUI。|
|TPB-128|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|确认后将default_config逐键_stage；不立即持久化，也不改Library。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:649 / _page_settings_file；源码静态；本轮未运行GUI。|
|TPB-200|此设置行按钮可用时单击|_export_settings写config.config快照，排除window_geometry/window_screen；不含pending。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:644 / _page_settings_file；按钮所属设置行：导出设置。|
|TPB-203|此设置行按钮可用时单击|_import_settings检查JSON对象、已知键/类型/范围后_stage；未直接保存。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:648 / _page_settings_file；按钮所属设置行：导入设置。|

#### 外观/主题

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-129|界面模式 / ModeRow|界面模式|界面模式|Appearance mode|表示モード|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-130|界面模式/选项 system / ModeRow/选项|跟随系统|跟隨系統|System Default|システムに従う|Choice/Mode选项t(label)并随语言刷新|
|TPB-131|界面模式/选项 light / ModeRow/选项|浅色|淺色|Light|ライト|Choice/Mode选项t(label)并随语言刷新|
|TPB-132|界面模式/选项 dark / ModeRow/选项|深色|深色|Dark|ダーク|Choice/Mode选项t(label)并随语言刷新|
|TPB-133|界面动效 / SwitchRow|名称：界面动效<br>副描述：控制窗口及界面的过渡动画，不影响表情动图播放。|名称：介面動效<br>副描述：控制視窗及介面的過渡動畫，不影響表情動圖播放。|名称：Interface animations<br>副描述：Control window and interface transitions without affecting animated emoji playback.|名称：UIアニメーション<br>副描述：ウィンドウとUIの切り替えアニメーションを設定します。絵文字の動画再生には影響しません。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-134|窗口毛玻璃 / SwitchRow|名称：窗口毛玻璃<br>副描述：控制窗口背景的毛玻璃效果；关闭后使用不透明背景。|名称：視窗毛玻璃<br>副描述：控制視窗背景的毛玻璃效果；關閉後使用不透明背景。|名称：Window blur<br>副描述：Control frosted window backgrounds; turn off to use an opaque background.|名称：ウィンドウのぼかし<br>副描述：ウィンドウ背景のぼかしを設定します。オフにすると不透明な背景になります。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-176|主题强调色 / AccentRow|主题强调色|主題強調色|Accent color|アクセントカラー|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-129|PREVIEW_KEYS：实时预览开启时可暂时生效，保存持久化；关闭预览/放弃会恢复。|MainWindow选择Theme.DARK/LIGHT/AUTO并更新主题。|设置键=appearance_mode；不执行本轮修改。|fluent_ui/views/settings_center.py:356 / _page_theme；源码静态；本轮未运行GUI。|
|TPB-130|当前存储值或待保存value=system|MainWindow选择Theme.DARK/LIGHT/AUTO并更新主题。|设置键=appearance_mode；不执行本轮修改。|fluent_ui/views/settings_center.py:356 / _page_theme；源码静态；本轮未运行GUI。|
|TPB-131|当前存储值或待保存value=light|MainWindow选择Theme.DARK/LIGHT/AUTO并更新主题。|设置键=appearance_mode；不执行本轮修改。|fluent_ui/views/settings_center.py:356 / _page_theme；源码静态；本轮未运行GUI。|
|TPB-132|当前存储值或待保存value=dark|MainWindow选择Theme.DARK/LIGHT/AUTO并更新主题。|设置键=appearance_mode；不执行本轮修改。|fluent_ui/views/settings_center.py:356 / _page_theme；源码静态；本轮未运行GUI。|
|TPB-133|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|save后finish_ui_animations并发motion_changed；不在PREVIEW_KEYS。|设置键=ui_animations_enabled；不执行本轮修改。|fluent_ui/views/settings_center.py:362 / _page_theme；源码静态；本轮未运行GUI。|
|TPB-134|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|save仅保存并通知“窗口毛玻璃设置将在重启后生效。”；重启后UiTheme.configure选择Opaque。|设置键=window_acrylic_enabled；不执行本轮修改。|fluent_ui/views/settings_center.py:366 / _page_theme；源码静态；本轮未运行GUI。|
|TPB-176|颜色选择，config key=accent_color|_stage进入PREVIEW_KEYS；局部颜色即时，accent_commit_timer合并全局预览，save持久化，discard恢复。|本轮不执行HSV或改变预览机制。|fluent_ui/components/setting_rows.py:172 / __init__；源码静态；本轮未运行GUI。|

#### 外观/表情库布局

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-135|缩略图大小 / RangeRow|名称：缩略图大小<br>副描述：调整主面板中表情的显示大小。<br>也可在主面板中直接调整，或按住 Ctrl 滚动滚轮。<br>两处调整会同步生效。|名称：縮略圖大小<br>副描述：調整主面板中表情的顯示大小。<br>也可在主面板中直接調整，或按住 Ctrl 捲動滾輪。<br>兩處調整會同步生效。|名称：Thumbnail size<br>副描述：Adjust emote size in the main panel.<br>You can also use the main panel control or hold Ctrl while scrolling.<br>Both controls stay in sync.|名称：サムネイルサイズ<br>副描述：メインパネルのスタンプの表示サイズを調整します。<br>メインパネルの操作部、または Ctrl を押しながらホイールでも調整できます。<br>どちらの変更も同期されます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-136|分类栏显示方式 / ModeRow|名称：分类栏显示方式<br>副描述：切换分类树与分类图标视图。<br>也可通过分类栏顶部按钮快速切换。|名称：分類欄顯示方式<br>副描述：切換分類樹與分類圖示檢視。<br>也可透過分類欄頂部按鈕快速切換。|名称：Category sidebar view<br>副描述：Switch between category tree and icon views.<br>You can also use the button at the top of the category sidebar.|名称：カテゴリ欄の表示方式<br>副描述：カテゴリのツリー表示とアイコン表示を切り替えます。<br>カテゴリ欄の上部ボタンでも切り替えられます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-137|分类栏显示方式/选项 tree / ModeRow/选项|分类树|分類樹|Category tree|カテゴリツリー|Choice/Mode选项t(label)并随语言刷新|
|TPB-138|分类栏显示方式/选项 categorized_icons / ModeRow/选项|分类图标|分類圖標|Category icon|カテゴリアイコン|Choice/Mode选项t(label)并随语言刷新|
|TPB-139|显示分类名称 / SwitchRow|名称：显示分类名称<br>副描述：在分类图标视图下显示分类名称。|名称：顯示分類名稱<br>副描述：在分類圖示檢視下顯示分類名稱。|名称：Show category names<br>副描述：Show category names in icon view.|名称：カテゴリ名を表示<br>副描述：アイコン表示でカテゴリ名を表示します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-140|分类树图标大小 / RangeRow|名称：分类树图标大小<br>副描述：调整分类树中的图标尺寸。|名称：分類樹圖示大小<br>副描述：調整分類樹中的圖示尺寸。|名称：Category tree icon size<br>副描述：Adjust icon size in the category tree.|名称：カテゴリツリーのアイコンサイズ<br>副描述：カテゴリツリーのアイコンサイズを調整します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-141|图库节点图标大小 / RangeRow|名称：图库节点图标大小<br>副描述：独立调整右侧图库分类节点的图标尺寸。|名称：缺失；实际显示 [MISSING: 图库节点图标大小]<br>副描述：缺失；实际显示 [MISSING: 独立调整右侧图库分类节点的图标尺寸。]|名称：缺失；实际显示 [MISSING: 图库节点图标大小]<br>副描述：缺失；实际显示 [MISSING: 独立调整右侧图库分类节点的图标尺寸。]|名称：缺失；实际显示 [MISSING: 图库节点图标大小]<br>副描述：缺失；实际显示 [MISSING: 独立调整右侧图库分类节点的图标尺寸。]|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-142|标签面板位置 / SpatialRow|名称：标签面板位置<br>副描述：选择标签面板在表情库中的停靠位置。<br>点击示意窗口的对应边缘进行调整。|名称：標籤面板位置<br>副描述：選擇標籤面板在表情庫中的停靠位置。<br>點擊示意視窗的對應邊緣進行調整。|名称：Tag panel placement<br>副描述：Choose where the tag panel docks in the library.<br>Click the corresponding edge of the preview window.|名称：タグパネルの位置<br>副描述：ライブラリ内のタグパネルの配置位置を選びます。<br>図のウィンドウで配置したい辺をクリックしてください。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-135|PREVIEW_KEYS：实时预览开启时可暂时生效，保存持久化；关闭预览/放弃会恢复。|Gallery._apply_thumbnail_size，只改显示大小；图库快捷入口另直接提交。|设置键=thumbnail_size；不执行本轮修改。|fluent_ui/views/settings_center.py:374 / _page_gallery_display；源码静态；本轮未运行GUI。|
|TPB-136|PREVIEW_KEYS：实时预览开启时可暂时生效，保存持久化；关闭预览/放弃会恢复。|MainWindow→sidebar.apply_presentation。|设置键=sidebar_mode；不执行本轮修改。|fluent_ui/views/settings_center.py:379 / _page_gallery_display；源码静态；本轮未运行GUI。|
|TPB-137|当前存储值或待保存value=tree|MainWindow→sidebar.apply_presentation。|设置键=sidebar_mode；不执行本轮修改。|fluent_ui/views/settings_center.py:379 / _page_gallery_display；源码静态；本轮未运行GUI。|
|TPB-138|当前存储值或待保存value=categorized_icons|MainWindow→sidebar.apply_presentation。|设置键=sidebar_mode；不执行本轮修改。|fluent_ui/views/settings_center.py:379 / _page_gallery_display；源码静态；本轮未运行GUI。|
|TPB-139|PREVIEW_KEYS：实时预览开启时可暂时生效，保存持久化；关闭预览/放弃会恢复。|仅categorized_icons模式该行Enabled；不改业务分类名。|设置键=sidebar_show_labels；不执行本轮修改。|fluent_ui/views/settings_center.py:384 / _page_gallery_display；源码静态；本轮未运行GUI。|
|TPB-140|PREVIEW_KEYS：实时预览开启时可暂时生效，保存持久化；关闭预览/放弃会恢复。|sidebar.apply_presentation；与图库节点图标独立。|设置键=sidebar_icon_size；不执行本轮修改。|fluent_ui/views/settings_center.py:391 / _page_gallery_display；源码静态；本轮未运行GUI。|
|TPB-141|PREVIEW_KEYS：实时预览开启时可暂时生效，保存持久化；关闭预览/放弃会恢复。|图库配置刷新路径；不改左树设置。|设置键=gallery_node_icon_size；不执行本轮修改。|fluent_ui/views/settings_center.py:395 / _page_gallery_display；源码静态；本轮未运行GUI。|
|TPB-142|PREVIEW_KEYS：实时预览开启时可暂时生效，保存持久化；关闭预览/放弃会恢复。|MainWindow→tag_panel_host.set_placement，四向同一状态源。|设置键=tag_panel_placement；不执行本轮修改。|fluent_ui/views/settings_center.py:399 / _page_gallery_display；源码静态；本轮未运行GUI。|

#### 外观/快速面板

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-143|快速面板缩略图大小 / RangeRow|快速面板缩略图大小|快速面板縮圖大小|Quick panel thumbnail size|クイックパネルのサムネイルサイズ|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-144|面板宽度 / RangeRow|名称：面板宽度<br>副描述：快速调用面板的宽度。|名称：面板寬度<br>副描述：快速調用面板的寬度。|名称：Panel width<br>副描述：Quick panel width.|名称：パネルの幅<br>副描述：クイックパネルの幅です。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-145|面板高度 / RangeRow|名称：面板高度<br>副描述：快速调用面板的高度。|名称：面板高度<br>副描述：快速調用面板的高度。|名称：Panel height<br>副描述：Quick panel height.|名称：パネルの高さ<br>副描述：クイックパネルの高さです。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-143|PREVIEW_KEYS：实时预览开启时可暂时生效，保存持久化；关闭预览/放弃会恢复。|MainWindow→quick_panel._apply_thumbnail_size。|设置键=quick_panel_thumbnail_size；不执行本轮修改。|fluent_ui/views/settings_center.py:406 / _page_quick_panel；源码静态；本轮未运行GUI。|
|TPB-144|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|QuickPanel.__init__及show_at_cursor读取quick_panel_width；每次唤醒按最新配置resize宽度，不要求重启。|设置键=quick_panel_width；不执行本轮修改。|fluent_ui/views/settings_center.py:409 / _page_quick_panel；源码静态；本轮未运行GUI。|
|TPB-145|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|QuickPanel.__init__及show_at_cursor读取quick_panel_height；每次唤醒按最新配置resize高度，不要求重启。|设置键=quick_panel_height；不执行本轮修改。|fluent_ui/views/settings_center.py:413 / _page_quick_panel；源码静态；本轮未运行GUI。|

#### 外观/软件图标

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-146|当前软件图标 / SettingRow|名称：当前软件图标<br>副描述：用于主窗口、任务栏和托盘。<br>动图使用已选的缩略图帧；未选择时使用第一帧。|名称：目前軟體圖示<br>副描述：用於主視窗、工作列和系統匣。<br>動圖使用已選的縮圖影格；未選擇時使用第一格。|名称：Current app icon<br>副描述：Used by the main window, taskbar and tray.<br>Animations use the chosen thumbnail frame, or the first frame if none was chosen.|名称：現在のアプリアイコン<br>副描述：メインウィンドウ、タスクバー、トレイに使用します。<br>アニメーションは選択済みのサムネイルフレームを使用し、未選択の場合は最初のフレームを使用します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-146|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|选择/恢复通过ApplicationIconService立即执行并保存；不进入pending，Discard不能撤销。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:427 / _page_app_icon；源码静态；本轮未运行GUI。|

#### 交互/快捷键

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-147|全局快捷键导入表情 / SwitchRow|名称：全局快捷键导入表情<br>副描述：在其它应用中复制后，直接导入根层资源。|名称：全域快速鍵匯入表情<br>副描述：在其他應用程式複製後，直接匯入根層資源。|名称：Global clipboard import<br>副描述：Import copied emotes directly into the library root.|名称：グローバルキーで絵文字を取り込む<br>副描述：他のアプリでコピーした画像をライブラリのルートに取り込みます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-148|导入快捷键 / HotkeyRow|导入快捷键|匯入快速鍵|Import shortcut|取り込みショートカット|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-149|唤醒快捷键 / HotkeyRow|名称：唤醒快捷键<br>副描述：全局显示 / 隐藏主面板。|名称：喚醒快捷鍵<br>副描述：全局顯示 / 隱藏主面板。|名称：Wake-up Hotkey<br>副描述：Show or hide the main window globally.|名称：ウェイクアップホットキー<br>副描述：グローバルショートカットでメイン画面を表示・非表示にします。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-150|快速面板快捷键 / HotkeyRow|名称：快速面板快捷键<br>副描述：全局呼出快速表情面板。|名称：快速面板快捷鍵<br>副描述：全局呼出快速表情面板。|名称：Quick Panel Hotkey<br>副描述：Open the quick panel globally.|名称：クイックパネルホットキー<br>副描述：グローバルショートカットでクイックパネルを開きます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-151|主面板 / SwitchRow|名称：主面板<br>副描述：按 Esc 隐藏主面板。|名称：主面板<br>副描述：按 Esc 隱藏主面板。|名称：Main panel<br>副描述：Press Esc to hide the main panel.|名称：メインパネル<br>副描述：Esc でメインパネルを隠します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-152|快速面板 / SwitchRow|名称：快速面板<br>副描述：按 Esc 隐藏快速面板。|名称：快速面板<br>副描述：按 Esc 隱藏快速面板。|名称：Quick panel<br>副描述：Press Esc to hide the quick panel.|名称：クイックパネル<br>副描述：Esc でクイックパネルを隠します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-147|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|save时clipboard_import_command.configure，注册失败返回False不保存。|设置键=clipboard_import_enabled；不执行本轮修改。|fluent_ui/views/settings_center.py:503 / _page_hotkeys；源码静态；本轮未运行GUI。|
|TPB-148|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|save前校验组合且与主/快速面板组合不冲突；configure成功才保存。|设置键=clipboard_import_hotkey；不执行本轮修改。|fluent_ui/views/settings_center.py:507 / _page_hotkeys；源码静态；本轮未运行GUI。|
|TPB-149|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|save发settings_changed→bind_global_hotkey。|设置键=global_hotkey；不执行本轮修改。|fluent_ui/views/settings_center.py:511 / _page_hotkeys；_hotkeys_valid会在main/quick冲突时覆盖hint、无冲突时清空；表内副描述是构造时原文。首帧/跨页具体显示先后本轮未运行。|
|TPB-150|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|save发settings_changed→bind_global_hotkey。|设置键=quick_panel_hotkey；不执行本轮修改。|fluent_ui/views/settings_center.py:515 / _page_hotkeys；_hotkeys_valid会在main/quick冲突时覆盖hint、无冲突时清空；表内副描述是构造时原文。首帧/跨页具体显示先后本轮未运行。|
|TPB-151|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|MainWindow.keyPressEvent/eventFilter读取esc_hide_main；Popup/Modal/快捷键录入优先，图库有选择时先consume_escape。适用条件下hide_window_group。|设置键=esc_hide_main；不执行本轮修改。|fluent_ui/views/settings_center.py:520 / _page_hotkeys；源码静态；本轮未运行GUI。|
|TPB-152|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|QuickPanel.keyPressEvent在Esc且esc_hide_quick为真时hide_panel并accept；否则交给父类。|设置键=esc_hide_quick；不执行本轮修改。|fluent_ui/views/settings_center.py:520 / _page_hotkeys；源码静态；本轮未运行GUI。|

#### 交互/发送

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-153|主面板单击表情 / ModeRow|名称：主面板单击表情<br>副描述：单击选中：单击表情后，按 Enter 发送。<br>单击发送：单击表情后立即发送。<br>两种模式均支持拖动表情至聊天窗口。<br>快速面板始终使用单击发送。|名称：主面板點選表情<br>副描述：單擊選取：點擊表情後，按 Enter 傳送。<br>單擊傳送：點擊表情後立即傳送。<br>兩種模式均支援拖曳表情至聊天視窗。<br>快速面板一律使用單擊傳送。|名称：Clicking an emote in the main panel<br>副描述：Click to select: click an emote, then press Enter to send.<br>Click to send: send immediately when clicked.<br>Both modes support dragging emotes into a chat window.<br>The quick panel always sends on click.|名称：メインパネルでのスタンプのクリック<br>副描述：クリックで選択：選択後、Enter で送信します。<br>クリックで送信：クリックするとすぐに送信します。<br>どちらもチャットへのドラッグに対応しています。<br>クイックパネルでは常にクリックで送信します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-154|主面板单击表情/选项 select / ModeRow/选项|单击选中|單擊選取|Click to select|クリックで選択|Choice/Mode选项t(label)并随语言刷新|
|TPB-155|主面板单击表情/选项 send / ModeRow/选项|单击发送|單擊傳送|Click to send|クリックで送信|Choice/Mode选项t(label)并随语言刷新|
|TPB-156|发送时将静态图转为 GIF / SwitchRow|名称：发送时将静态图转为 GIF<br>副描述：复制静态图时转为单帧 GIF，避免在聊天软件中显示为超大原图。|名称：發送時將靜態圖轉為 GIF<br>副描述：復制靜態圖時轉為單幀 GIF，避免在聊天軟件中顯示為超大原圖。|名称：Send static emotes as GIF<br>副描述：Convert static emotes to a single-frame GIF for chat apps.|名称：静止画を GIF として送信<br>副描述：チャットでスタンプが大きく表示されないよう、1 フレームの GIF に変換します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-153|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|on_image_clicked / _sync_view_shortcuts / _view_key：normal+select可Enter发送；manage不发送，修饰键仍选择。|设置键=gallery_click_action；不执行本轮修改。|fluent_ui/views/settings_center.py:526 / _page_send；源码静态；本轮未运行GUI。|
|TPB-154|当前存储值或待保存value=select|on_image_clicked / _sync_view_shortcuts / _view_key：normal+select可Enter发送；manage不发送，修饰键仍选择。|设置键=gallery_click_action；不执行本轮修改。|fluent_ui/views/settings_center.py:526 / _page_send；源码静态；本轮未运行GUI。|
|TPB-155|当前存储值或待保存value=send|on_image_clicked / _sync_view_shortcuts / _view_key：normal+select可Enter发送；manage不发送，修饰键仍选择。|设置键=gallery_click_action；不执行本轮修改。|fluent_ui/views/settings_center.py:526 / _page_send；源码静态；本轮未运行GUI。|
|TPB-156|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|ClipboardService复制路径读取；仅静态转单帧GIF，动图非此开关。|设置键=convert_static_to_gif；不执行本轮修改。|fluent_ui/views/settings_center.py:531 / _page_send；源码静态；本轮未运行GUI。|

#### 交互/悬停预览

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-157|预览浮窗大小 / RangeRow|名称：预览浮窗大小<br>副描述：鼠标悬停时弹出的大图尺寸。|名称：預覽浮窗大小<br>副描述：鼠標懸停時彈出的大圖尺寸。|名称：Preview Popup Size<br>副描述：Size of the hover preview.|名称：プレビューポップアップのサイズ<br>副描述：ホバープレビューのサイズです。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-158|预览延迟 / RangeRow|名称：预览延迟<br>副描述：鼠标停留多久后弹出预览。|名称：預覽延遲<br>副描述：鼠標停留多久后彈出預覽。|名称：Preview delay<br>副描述：Delay before the hover preview appears.|名称：プレビューの遅延<br>副描述：ホバープレビューを表示するまでの時間です。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-159|表情预览位置 / ModeRow|名称：表情预览位置<br>副描述：固定：停靠在表情区右下角，被遮挡时移到左下；浮动：跟随鼠标。|名称：表情預覽位置<br>副描述：固定：停靠在表情區右下角，受遮擋時移到左下；浮動：跟隨滑鼠。|名称：Preview position<br>副描述：Fixed: bottom-right of the gallery, moving left if obstructed. Floating: follows the pointer.|名称：プレビュー位置<br>副描述：固定：ギャラリー右下に表示し、重なる場合は左下に移動。フローティング：ポインターに追従。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-160|表情预览位置/选项 fixed / ModeRow/选项|固定|固定|Fixed|固定|Choice/Mode选项t(label)并随语言刷新|
|TPB-161|表情预览位置/选项 floating / ModeRow/选项|浮动|浮動|Floating|フローティング|Choice/Mode选项t(label)并随语言刷新|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-157|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|Gallery及QuickPanel.get_preview_size读取preview_size，HoverPreviewController在show_preview调用时取得；保存后后续预览使用新值。|设置键=preview_size；不执行本轮修改。|fluent_ui/views/settings_center.py:1101 / _page_hover_preview；源码静态；本轮未运行GUI。|
|TPB-158|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|Gallery.on_settings_changed→preview_controller.set_delay。|设置键=preview_delay；不执行本轮修改。|fluent_ui/views/settings_center.py:1105 / _page_hover_preview；源码静态；本轮未运行GUI。|
|TPB-159|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|MainWindow→Gallery.apply_preview_position。|设置键=preview_position；不执行本轮修改。|fluent_ui/views/settings_center.py:1109 / _page_hover_preview；源码静态；本轮未运行GUI。|
|TPB-160|当前存储值或待保存value=fixed|MainWindow→Gallery.apply_preview_position。|设置键=preview_position；不执行本轮修改。|fluent_ui/views/settings_center.py:1109 / _page_hover_preview；源码静态；本轮未运行GUI。|
|TPB-161|当前存储值或待保存value=floating|MainWindow→Gallery.apply_preview_position。|设置键=preview_position；不执行本轮修改。|fluent_ui/views/settings_center.py:1109 / _page_hover_preview；源码静态；本轮未运行GUI。|

#### 表情与数据/表情库管理

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-162|当前表情库 / FullPathRow|名称：当前表情库<br>副描述：表情和分类保存在以下目录；可选中文字复制完整路径。|名称：當前表情庫<br>副描述：表情與分類儲存在以下目錄；可選取文字複製完整路徑。|名称：Current library<br>副描述：Emotes and categories are stored below. Select the text to copy the full path.|名称：現在のライブラリ<br>副描述：スタンプと分類の保存先です。文字を選択してパスをコピーできます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-163|选择 / 重新连接表情库 / ActionRow|名称：选择 / 重新连接表情库<br>副描述：保存后需要重启程序才会切换到新的表情库。|名称：選擇 / 重新連接表情庫<br>副描述：保存后需要重啟程序才會切換到新的表情庫。|名称：Choose / reconnect library<br>副描述：Restart after saving to switch libraries.|名称：ライブラリを選択・再接続<br>副描述：保存後に再起動するとライブラリが切り替わります。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-164|最近使用上限 / RangeRow|名称：最近使用上限<br>副描述：设置最近使用记录中显示的表情数量。<br>主面板与快速面板共用此设置。|名称：最近使用上限<br>副描述：設定最近使用記錄中顯示的表情數量。<br>主面板與快速面板共用此設定。|名称：Recent items limit<br>副描述：Set how many emotes to show in recent history.<br>The main and quick panels share this setting.|名称：最近使った項目の上限<br>副描述：最近の履歴に表示するスタンプ数を設定します。<br>メインパネルとクイックパネルで共通です。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-165|检查表情状态 / ActionRow|名称：检查表情状态<br>副描述：检查表情文件是否仍然存在。<br>找不到的表情会标记为已失效，不会删除记录。|名称：檢查表情狀態<br>副描述：檢查表情檔案是否仍然存在。<br>找不到的表情會標記為已失效，不會刪除記錄。|名称：Check emote status<br>副描述：Check whether the emote files are still available.<br>Missing emotes are marked as unavailable; their records are kept.|名称：スタンプの状態を確認<br>副描述：スタンプファイルが存在するか確認します。<br>見つからないスタンプは無効として表示し、記録は残します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-166|在文件管理器中打开 / ActionRow|名称：在文件管理器中打开<br>副描述：直接查看表情库中的真实表情文件。|名称：在文件管理器中打開<br>副描述：直接查看表情庫中的真實表情文件。|名称：Show in File Explorer<br>副描述：View the actual files in your library.|名称：エクスプローラーで開く<br>副描述：ライブラリの実際のファイルを表示します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-196|选择 / 重新连接表情库/选择文件夹… / ActionRow/SuzuExportRow按钮|选择文件夹…|選擇文件夾…|Choose folder…|フォルダを選択…|t/bind_text/translated：逐原文精确键|
|TPB-197|检查表情状态/立即检查 / ActionRow/SuzuExportRow按钮|立即检查|立即檢查|Check now|今すぐ確認|t/bind_text/translated：逐原文精确键|
|TPB-198|在文件管理器中打开/打开表情库目录 / ActionRow/SuzuExportRow按钮|打开表情库目录|打開表情庫目錄|Open library folder|ライブラリフォルダを開く|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-162|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|_library_path显示storage.library_root；FullPathRow保留完整路径供复制，本报告不采真实值。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:299 / _page_library；源码静态；本轮未运行GUI。|
|TPB-163|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|_choose_library先check_target，stage library_path；save准备目录并写配置，需重启才换当前Storage。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:302 / _page_library；源码静态；本轮未运行GUI。|
|TPB-164|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|MainWindow发storage.recent_changed，主/快速面板共用记录。|设置键=recent_limit；不执行本轮修改。|fluent_ui/views/settings_center.py:306 / _page_library；源码静态；本轮未运行GUI。|
|TPB-165|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|_check_library→storage.cleanup_dead_links；统计missing；显示检查结果。不删除记录。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:310 / _page_library；源码静态；本轮未运行GUI。|
|TPB-166|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|_open_library→QDesktopServices.openUrl(当前Library本地目录)。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:313 / _page_library；源码静态；本轮未运行GUI。|
|TPB-196|此设置行按钮可用时单击|_choose_library先check_target，stage library_path；save准备目录并写配置，需重启才换当前Storage。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:305 / _page_library；按钮所属设置行：选择 / 重新连接表情库。|
|TPB-197|此设置行按钮可用时单击|_check_library→storage.cleanup_dead_links；统计missing；显示检查结果。不删除记录。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:312 / _page_library；按钮所属设置行：检查表情状态。|
|TPB-198|此设置行按钮可用时单击|_open_library→QDesktopServices.openUrl(当前Library本地目录)。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:315 / _page_library；按钮所属设置行：在文件管理器中打开。|

#### 表情与数据/表情合集

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-167|导出 Nekori 表情合集 / ActionRow|名称：导出 Nekori 表情合集<br>副描述：保存全部表情，以及分类、图标、标签与排列顺序。|名称：匯出 Nekori 表情合集<br>副描述：儲存全部表情，以及分類、圖示、標籤與排列順序。|名称：Export Nekori collection<br>副描述：Save all emotes, categories, icons, tags and ordering.|名称：Nekori コレクションをエクスポート<br>副描述：すべてのスタンプ、分類、アイコン、タグ、並び順を保存します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-168|导入 Nekori 表情合集 / ActionRow|名称：导入 Nekori 表情合集<br>副描述：恢复表情合集中的内容与排列顺序。<br>重复表情由你选择如何处理。|名称：匯入 Nekori 表情合集<br>副描述：還原表情合集中的內容與排列順序。<br>重複表情由你選擇如何處理。|名称：Import Nekori collection<br>副描述：Restore the collection contents and order.<br>You decide how to handle duplicate emotes.|名称：Nekori コレクションをインポート<br>副描述：コレクションの内容と並び順を復元します。<br>重複するスタンプの処理方法を選べます。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-169|导入 Suzu 兼容表情合集 / ActionRow|名称：导入 Suzu 兼容表情合集<br>副描述：导入 Suzu 分享的表情与标签。<br>Suzu 格式不包含完整分类与排列顺序。|名称：匯入 Suzu 相容表情合集<br>副描述：匯入 Suzu 分享的表情與標籤。<br>Suzu 格式不包含完整分類與排列順序。|名称：Import Suzu-compatible collection<br>副描述：Import emotes and tags shared from Suzu.<br>Suzu files do not include the full category structure and ordering.|名称：Suzu 互換コレクションをインポート<br>副描述：Suzu で共有されたスタンプとタグを取り込みます。<br>Suzu 形式には完全な分類と並び順は含まれません。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-170|导出 Suzu 兼容表情合集 / SuzuExportRow|名称：导出 Suzu 兼容表情合集<br>副描述：将表情导出为 Suzu 兼容的分享格式。<br>不包含 Nekori 的完整分类和排序信息。|名称：匯出 Suzu 相容表情合集<br>副描述：將表情匯出為 Suzu 相容的分享格式。<br>不包含 Nekori 的完整分類和排序資訊。|名称：Export Suzu-compatible collection<br>副描述：Export emotes in a Suzu-compatible share format.<br>Nekori's full categories and ordering are not included.|名称：Suzu 互換コレクションをエクスポート<br>副描述：表情を Suzu 互換の共有形式でエクスポートします。<br>Nekori の分類と並び順の情報は完全には含まれません。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-171|拆分表情合集 / ActionRow|名称：拆分表情合集<br>副描述：将表情 ZIP 拆分为不超过 100MB 的分享包。|名称：分割表情合集<br>副描述：將表情 ZIP 分割為不超過 100MB 的分享包。|名称：Split package<br>副描述：Split a emote ZIP into share packages up to 100 MB.|名称：パッケージを分割<br>副描述：スタンプZIPを100MB以下の共有パッケージに分割します。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-199|导出 Nekori 表情合集/导出… / ActionRow/SuzuExportRow按钮|导出…|導出…|Export…|書き出し…|t/bind_text/translated：逐原文精确键|
|TPB-201|导入 Nekori 表情合集/导入… / ActionRow/SuzuExportRow按钮|导入…|導入…|Import…|取り込み…|t/bind_text/translated：逐原文精确键|
|TPB-202|导入 Suzu 兼容表情合集/导入… / ActionRow/SuzuExportRow按钮|导入…|導入…|Import…|取り込み…|t/bind_text/translated：逐原文精确键|
|TPB-204|导出 Suzu 兼容表情合集/导出全部… / ActionRow/SuzuExportRow按钮|导出全部…|匯出全部…|Export all…|すべてエクスポート…|t/bind_text/translated：逐原文精确键|
|TPB-205|导出 Suzu 兼容表情合集/选择分类… / ActionRow/SuzuExportRow按钮|选择分类…|選擇分類…|Choose categories…|カテゴリを選択…|t/bind_text/translated：逐原文精确键|
|TPB-206|拆分表情合集/拆分… / ActionRow/SuzuExportRow按钮|拆分…|分割…|Split…|分割…|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-167|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|export_nekori_package→NekoriPackageService.export，全库包；目标用户选择，支持安全取消。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:538 / _page_packages；源码静态；本轮未运行GUI。|
|TPB-168|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|import_nekori_package→统一ImportQueue的operation，重复项走已有决策。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:542 / _page_packages；源码静态；本轮未运行GUI。|
|TPB-169|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|import_suzu_share→ExchangeImportService.import_zip→统一队列。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:548 / _page_packages；源码静态；本轮未运行GUI。|
|TPB-170|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|_legacy_share(all/categories)→Gallery既有兼容分享导出，不等同原生全结构包。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:553 / _page_packages；源码静态；本轮未运行GUI。|
|TPB-171|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|_legacy_share(split)→exchange_interface._split_package；100MB边界实现本轮未展开。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:555 / _page_packages；源码静态；本轮未运行GUI。|
|TPB-199|此设置行按钮可用时单击|export_nekori_package→NekoriPackageService.export，全库包；目标用户选择，支持安全取消。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:541 / _page_packages；按钮所属设置行：导出 Nekori 表情合集。|
|TPB-201|此设置行按钮可用时单击|import_nekori_package→统一ImportQueue的operation，重复项走已有决策。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:545 / _page_packages；按钮所属设置行：导入 Nekori 表情合集。|
|TPB-202|此设置行按钮可用时单击|import_suzu_share→ExchangeImportService.import_zip→统一队列。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:551 / _page_packages；按钮所属设置行：导入 Suzu 兼容表情合集。|
|TPB-204|此设置行按钮可用时单击|_legacy_share(all/categories)→Gallery既有兼容分享导出，不等同原生全结构包。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:554 / _page_packages；按钮所属设置行：导出 Suzu 兼容表情合集。|
|TPB-205|此设置行按钮可用时单击|_legacy_share(all/categories)→Gallery既有兼容分享导出，不等同原生全结构包。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:554 / _page_packages；按钮所属设置行：导出 Suzu 兼容表情合集。|
|TPB-206|此设置行按钮可用时单击|_legacy_share(split)→exchange_interface._split_package；100MB边界实现本轮未展开。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:556 / _page_packages；按钮所属设置行：拆分表情合集。|

#### 表情与数据/Suzu迁移

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-172|Suzu 迁移 / ActionRow|名称：Suzu 迁移<br>副描述：从 Suzu 复制表情、分类与标签。<br>迁移前可预览，原有 Suzu 数据不受影响。|名称：Suzu 遷移<br>副描述：從 Suzu 複製表情、分類與標籤。<br>遷移前可預覽，原有 Suzu 資料不受影響。|名称：Suzu migration<br>副描述：Copy emotes, categories and tags from Suzu.<br>Preview before migration; original Suzu data is unchanged.|名称：Suzu から移行<br>副描述：Suzu のスタンプ、カテゴリ、タグをコピーします。<br>移行前に確認でき、元の Suzu データには影響しません。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-207|Suzu 迁移/从本机 Suzu 迁移 / ActionRow/SuzuExportRow按钮|从本机 Suzu 迁移|從本機 Suzu 遷移|Migrate from local Suzu|このPCの Suzu から移行|t/bind_text/translated：逐原文精确键|
|TPB-208|Suzu 迁移/从表情压缩包迁移 / ActionRow/SuzuExportRow按钮|从表情压缩包迁移|從表情壓縮包遷移|Migrate from an emote archive|スタンプのアーカイブから移行|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-172|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|本机入口SuzuInstanceDialog预览选择，再排队migration；ZIP入口preview_package后确认，再排队。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:606 / _page_migration；源码静态；本轮未运行GUI。|
|TPB-207|此设置行按钮可用时单击|本机入口SuzuInstanceDialog预览选择，再排队migration；ZIP入口preview_package后确认，再排队。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:609 / _page_migration；按钮所属设置行：Suzu 迁移。|
|TPB-208|此设置行按钮可用时单击|本机入口SuzuInstanceDialog预览选择，再排队migration；ZIP入口preview_package后确认，再排队。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:610 / _page_migration；按钮所属设置行：Suzu 迁移。|

#### 关于/软件信息

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-173|版本 / SettingRow|版本|版本|Version|バージョン|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-174|启动时自动检查更新 / SwitchRow|名称：启动时自动检查更新<br>副描述：后台检查，每24小时最多一次；不会自动下载或安装。|名称：啟動時自動檢查更新<br>副描述：在背景檢查，每24小時最多一次；不會自動下載或安裝。|名称：Check for updates at startup<br>副描述：Check in the background at most once every 24 hours; never download or install automatically.|名称：起動時に更新を確認<br>副描述：バックグラウンドで24時間に1回まで確認します。自動でダウンロードやインストールは行いません。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-175|诊断资料 / ActionRow|名称：诊断资料<br>副描述：查看本地日志，或导出脱敏日志与版本环境；不包含表情资源及应用配置。|名称：診斷資料<br>副描述：查看本機日誌，或匯出已去識別化的日誌與版本環境；不包含表情資源及應用程式設定。|名称：Diagnostics<br>副描述：Open local logs or export redacted logs and version information; excludes emotes and app settings.|名称：診断情報<br>副描述：ローカルログの表示、または個人情報を除去したログと実行環境の書き出し。表情画像や設定は含みません。|SettingRow使用translated绑定名称/KeycapLabel hint；Choice/Mode选项另列|
|TPB-209|诊断资料/查看日志 / ActionRow/SuzuExportRow按钮|查看日志|查看日誌|View logs|ログを表示|t/bind_text/translated：逐原文精确键|
|TPB-210|诊断资料/导出诊断资料… / ActionRow/SuzuExportRow按钮|导出诊断资料…|匯出診斷資料…|Export diagnostics…|診断情報を書き出す…|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-173|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|VersionLabel显示current_version；更新按钮另开现有UpdateCenter。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:660 / _page_about；源码静态；本轮未运行GUI。|
|TPB-174|一般pending设置保存后持久化；本行不属于PREVIEW_KEYS。|保存偏好；自动检查属于启动调度，手动检查入口独立，不自动下载。|设置键=auto_check_updates；不执行本轮修改。|fluent_ui/views/settings_center.py:669 / _page_about；源码静态；本轮未运行GUI。|
|TPB-175|非普通pending控件，见对应操作；ActionRow按钮立即启动自己的命令。|_open_logs打开日志目录；_export_diagnostics用户指定ZIP目标并调用脱敏导出；不上传。|不将此类即时命令误写成普通Save/Discard流程。|fluent_ui/views/settings_center.py:673 / _page_about；源码静态；本轮未运行GUI。|
|TPB-209|此设置行按钮可用时单击|_open_logs打开日志目录；_export_diagnostics用户指定ZIP目标并调用脱敏导出；不上传。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:675 / _page_about；按钮所属设置行：诊断资料。|
|TPB-210|此设置行按钮可用时单击|_open_logs打开日志目录；_export_diagnostics用户指定ZIP目标并调用脱敏导出；不上传。|同名按钮在不同设置行分开记录，不把导入导出范围合并；取消用户选择不继续该命令。|fluent_ui/views/settings_center.py:675 / _page_about；按钮所属设置行：诊断资料。|

#### 设置通用操作

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-177|实时预览 / 页脚按钮|实时预览|實時預覽|Live preview|ライブプレビュー|t/bind_text/translated：逐原文精确键|
|TPB-178|本页默认 / 页脚按钮|本页默认|本頁默認|Reset page|ページを初期化|t/bind_text/translated：逐原文精确键|
|TPB-179|放弃修改 / 页脚按钮|放弃修改|放棄修改|Discard|変更を破棄|t/bind_text/translated：逐原文精确键|
|TPB-180|保存 / 页脚按钮|保存|保存|Save|保存|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-177|当前设置页；Save/Discard按dirty，Save还需_hotkeys_valid|_on_preview_toggled立即config.set(settings_preview)，仅PREVIEW_KEYS使用临时preview_values。|此开关自身不是待保存项目；关掉撤回临时预览，不清pending。|fluent_ui/views/settings_center.py:76 / _build_footer；源码静态；本轮未运行GUI。|
|TPB-178|当前设置页；Save/Discard按dirty，Save还需_hotkeys_valid|_restore_page_defaults确认后载入本页可追踪键的默认值。|有pending时入口禁用/函数返回；载入后仍需保存，可放弃。|fluent_ui/views/settings_center.py:84 / _build_footer；源码静态；本轮未运行GUI。|
|TPB-179|当前设置页；Save/Discard按dirty，Save还需_hotkeys_valid|discard撤销pending和preview_values，重新填已保存配置。|不能撤回此前即时软件图标、OCR安装等独立操作。|fluent_ui/views/settings_center.py:85 / _build_footer；源码静态；本轮未运行GUI。|
|TPB-180|当前设置页；Save/Discard按dirty，Save还需_hotkeys_valid|save验证并持久化pending；逐键发settings_changed。|热键注册/库准备失败返回False；毛玻璃单独提示重启。|fluent_ui/views/settings_center.py:86 / _build_footer；源码静态；本轮未运行GUI。|

#### 设置状态变体

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-181|未保存的修改 / 状态Label/行hint/通知|未保存的修改|未保存的修改|Unsaved changes|未保存の変更|t/bind_text/translated：逐原文精确键|
|TPB-182|未保存修改不会包含在导出文件中。 / 状态Label/行hint/通知|未保存修改不会包含在导出文件中。|未儲存的修改不會包含在匯出檔案中。|Unsaved changes are excluded from the exported file.|未保存の変更はエクスポートされません。|t/bind_text/translated：逐原文精确键|
|TPB-183|窗口毛玻璃设置将在重启后生效。 / 状态Label/行hint/通知|窗口毛玻璃设置将在重启后生效。|視窗毛玻璃設定將在重新啟動後生效。|The window blur setting will take effect after restarting.|ウィンドウのぼかし設定は再起動後に適用されます。|t/bind_text/translated：逐原文精确键|
|TPB-184|保存并重启后，将使用下面的表情库。 / 状态Label/行hint/通知|保存并重启后，将使用下面的表情库。|儲存並重新啟動後，將使用下面的表情庫。|Save and restart to use the library below.|保存して再起動すると、このライブラリに切り替わります。|t/bind_text/translated：逐原文精确键|
|TPB-185|保存后重启切换表情库。 / 状态Label/行hint/通知|保存后重启切换表情库。|儲存後重新啟動以切換表情庫。|Restart after saving to switch libraries.|保存後に再起動するとライブラリが切り替わります。|t/bind_text/translated：逐原文精确键|
|TPB-186|唤醒快捷键与快速面板快捷键不能相同 / 状态Label/行hint/通知|唤醒快捷键与快速面板快捷键不能相同|喚醒快捷鍵與快速面板快捷鍵不能相同|Main and quick panel shortcuts must differ|メイン画面とクイックパネルのショートカットは別にしてください|t/bind_text/translated：逐原文精确键|
|TPB-187|导入快捷键不能与唤醒或快速面板快捷键相同。 / 状态Label/行hint/通知|导入快捷键不能与唤醒或快速面板快捷键相同。|匯入快速鍵不可與喚醒或快速面板快速鍵相同。|The import shortcut must differ from the main and quick panel shortcuts.|取り込みキーはメイン画面・クイックパネルのキーと別にしてください。|t/bind_text/translated：逐原文精确键|
|TPB-188|快捷键已生效 / 状态Label/行hint/通知|快捷键已生效|快速鍵已生效|Shortcut active|ショートカットは有効です|t/bind_text/translated：逐原文精确键|
|TPB-189|快捷键未启用 / 状态Label/行hint/通知|快捷键未启用|快速鍵未啟用|Shortcut inactive|ショートカットは無効です|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-181|仅对应条件分支；与其它状态不合并|dirty_label在pending非空时显示，否则空字符串。|不更改对应业务；未运行本轮GUI。|fluent_ui/views/settings_center.py:791 / _set_dirty；源码静态；本轮未运行GUI。|
|TPB-182|仅对应条件分支；与其它状态不合并|设置导出行在dirty时set_hint；非dirty时传空字符串。|不更改对应业务；未运行本轮GUI。|fluent_ui/views/settings_center.py:800 / _set_dirty；源码静态；本轮未运行GUI。|
|TPB-183|仅对应条件分支；与其它状态不合并|保存含window_acrylic_enabled后发需要重启通知。|不更改对应业务；未运行本轮GUI。|fluent_ui/views/settings_center.py:863 / save；源码静态；本轮未运行GUI。|
|TPB-184|仅对应条件分支；与其它状态不合并|通过check_target后_stage并更新library_info hint。|不更改对应业务；未运行本轮GUI。|fluent_ui/views/settings_center.py:339 / _choose_library；源码静态；本轮未运行GUI。|
|TPB-185|仅对应条件分支；与其它状态不合并|恢复已保存库路径时重新set_hint。|不更改对应业务；未运行本轮GUI。|fluent_ui/views/settings_center.py:923 / discard；源码静态；本轮未运行GUI。|
|TPB-186|仅对应条件分支；与其它状态不合并|main/quick规范化相同则提示冲突、Save不可用。|状态文字反映本地判断；实际OS热键可用性需configure注册结果。|fluent_ui/views/settings_center.py:876 / _hotkeys_valid；源码静态；本轮未运行GUI。|
|TPB-187|仅对应条件分支；与其它状态不合并|clipboard组合与main/quick相同则错误；只校验文本组合，不等同系统注册成功。|状态文字反映本地判断；实际OS热键可用性需configure注册结果。|fluent_ui/views/settings_center.py:889 / _hotkeys_valid；源码静态；本轮未运行GUI。|
|TPB-188|仅对应条件分支；与其它状态不合并|command存在且hotkey.binding非空，无error时提示。|状态文字反映本地判断；实际OS热键可用性需configure注册结果。|fluent_ui/views/settings_center.py:895 / _hotkeys_valid；源码静态；本轮未运行GUI。|
|TPB-189|仅对应条件分支；与其它状态不合并|无binding且无其他error时提示。|状态文字反映本地判断；实际OS热键可用性需configure注册结果。|fluent_ui/views/settings_center.py:895 / _hotkeys_valid；源码静态；本轮未运行GUI。|

#### 常规/托盘选项

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-190|切换主面板 / ChoiceRow选项|切换主面板|切換主面板|Toggle main panel|メインパネル切替|t/bind_text/translated：逐原文精确键|
|TPB-191|显示主面板 / ChoiceRow选项|显示主面板|顯示主面板|Show main panel|メインパネル表示|t/bind_text/translated：逐原文精确键|
|TPB-192|切换快速面板 / ChoiceRow选项|切换快速面板|切換快速面板|Toggle quick panel|クイックパネル切替|t/bind_text/translated：逐原文精确键|
|TPB-193|显示快速面板 / ChoiceRow选项|显示快速面板|顯示快速面板|Show quick panel|クイックパネル表示|t/bind_text/translated：逐原文精确键|
|TPB-194|打开设置 / ChoiceRow选项|打开设置|開啟設定|Open settings|設定を開く|t/bind_text/translated：逐原文精确键|
|TPB-195|无操作 / ChoiceRow选项|无操作|無操作|No action|何もしない|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-190|左单击/双击/中键三个ChoiceRow共用选项|保存对应tray_*动作值，MainWindow托盘手势分发。|右键固定菜单，不使用此选项；三个同义调用合并列出。|fluent_ui/views/settings_center.py:255 / _page_tray；源码静态；本轮未运行GUI。|
|TPB-191|左单击/双击/中键三个ChoiceRow共用选项|保存对应tray_*动作值，MainWindow托盘手势分发。|右键固定菜单，不使用此选项；三个同义调用合并列出。|fluent_ui/views/settings_center.py:255 / _page_tray；源码静态；本轮未运行GUI。|
|TPB-192|左单击/双击/中键三个ChoiceRow共用选项|保存对应tray_*动作值，MainWindow托盘手势分发。|右键固定菜单，不使用此选项；三个同义调用合并列出。|fluent_ui/views/settings_center.py:256 / _page_tray；源码静态；本轮未运行GUI。|
|TPB-193|左单击/双击/中键三个ChoiceRow共用选项|保存对应tray_*动作值，MainWindow托盘手势分发。|右键固定菜单，不使用此选项；三个同义调用合并列出。|fluent_ui/views/settings_center.py:256 / _page_tray；源码静态；本轮未运行GUI。|
|TPB-194|左单击/双击/中键三个ChoiceRow共用选项|保存对应tray_*动作值，MainWindow托盘手势分发。|右键固定菜单，不使用此选项；三个同义调用合并列出。|fluent_ui/views/settings_center.py:257 / _page_tray；源码静态；本轮未运行GUI。|
|TPB-195|左单击/双击/中键三个ChoiceRow共用选项|保存对应tray_*动作值，MainWindow托盘手势分发。|右键固定菜单，不使用此选项；三个同义调用合并列出。|fluent_ui/views/settings_center.py:257 / _page_tray；源码静态；本轮未运行GUI。|

#### 表情与数据/文字识别

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-211|本地文字识别组件 / InfoRow/SwitchRow|名称：本地文字识别组件<br>副描述：安装后可在本地识别表情中的文字。<br>卸载组件不会删除已有识别结果或人工修改。|名称：本機文字識別元件<br>副描述：安裝後可在本機識別表情中的文字。<br>解除安裝不會刪除已有識別結果或人工修改。|名称：Local text recognition component<br>副描述：Recognize text in emotes locally after installation.<br>Uninstalling keeps recognized text and your edits.|名称：ローカル文字認識コンポーネント<br>副描述：インストール後、スタンプの文字をローカルで認識できます。<br>アンインストールしても認識結果や手動編集は残ります。|t/bind_text/translated：逐原文精确键|
|TPB-212|自动识别新表情 / InfoRow/SwitchRow|名称：自动识别新表情<br>副描述：新表情导入完成后，自动在后台识别文字。<br>不会自动识别表情库中的已有表情。|名称：自動識別新表情<br>副描述：新表情匯入完成後，自動在背景識別文字。<br>不會自動識別表情庫中的已有表情。|名称：Recognize newly imported emotes<br>副描述：Recognize text in the background after new emotes are imported.<br>Existing emotes in the library are not scanned automatically.|名称：新しいスタンプを自動認識<br>副描述：新しいスタンプのインポート後、バックグラウンドで文字を認識します。<br>既存のスタンプは自動では認識しません。|t/bind_text/translated：逐原文精确键|
|TPB-213|后台文字识别 / InfoRow/SwitchRow|名称：后台文字识别<br>副描述：补充识别会跳过已完成且未变化的表情。<br>人工修改会保留；停止后可以继续。|名称：背景文字識別<br>副描述：補充識別會跳過已完成且未變更的表情。<br>人工修改會保留；停止後可以繼續。|名称：Background text recognition<br>副描述：Recognize remaining emotes, skipping completed and unchanged ones.<br>Your edits are preserved. You can stop and continue later.|名称：バックグラウンド文字認識<br>副描述：認識済みで変更のないスタンプはスキップします。<br>手動編集は保持され、停止後も続きから処理できます。|t/bind_text/translated：逐原文精确键|
|TPB-214|安装组件… / 按钮/分裂按钮|安装组件…|安裝元件…|Install component…|インストール…|translated/bind_text；部分分裂按钮由group(label,callback)绑定|
|TPB-215|卸载 / 按钮/分裂按钮|卸载|卸載|Uninstall|アンインストール|translated/bind_text；部分分裂按钮由group(label,callback)绑定|
|TPB-216|重试失败项 / 按钮/分裂按钮|重试失败项|重試失敗項|Retry failed items|失敗分を再試行|translated/bind_text；部分分裂按钮由group(label,callback)绑定|
|TPB-217|补充识别 / 按钮/分裂按钮|补充识别|補充識別|Recognize remaining emotes|未完了分を認識|translated/bind_text；部分分裂按钮由group(label,callback)绑定|
|TPB-218|停止 / 按钮/分裂按钮|停止|停止|Stop|停止|translated/bind_text；部分分裂按钮由group(label,callback)绑定|
|TPB-219|更多… / 按钮/分裂按钮|更多…|更多…|More…|その他…|translated/bind_text；部分分裂按钮由group(label,callback)绑定|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-211|_page_ocr创建OcrSettings，storage存在时|安装/卸载是独立服务命令；不是SettingsCenter.pending。|本轮未安装组件或扫描文件；状态/详情错误由服务刷新，不改已有结果。|fluent_ui/components/ocr_controls.py:79 / __init__；源码静态；本轮未运行GUI。|
|TPB-212|_page_ocr创建OcrSettings，storage存在时|key ocr_auto由center._track；安装完成installed()会sync_external_preference(ocr_auto,True)，卸载成功会改False。|本轮未安装组件或扫描文件；状态/详情错误由服务刷新，不改已有结果。|fluent_ui/components/ocr_controls.py:93 / __init__；源码静态；本轮未运行GUI。|
|TPB-213|_page_ocr创建OcrSettings，storage存在时|supplement/retry/cancel操作即时控制OcrService，不等保存。|本轮未安装组件或扫描文件；状态/详情错误由服务刷新，不改已有结果。|fluent_ui/components/ocr_controls.py:96 / __init__；源码静态；本轮未运行GUI。|
|TPB-214|按available/installing/library_busy控制显示/Enabled；禁用不清原文字|install：有release URL走service.install，否则用户选本地组件ZIP。|取消保留已完成结果，不是回滚已写入文字。|fluent_ui/components/ocr_controls.py:86 / __init__；源码静态；本轮未运行GUI。|
|TPB-215|按available/installing/library_busy控制显示/Enabled；禁用不清原文字|uninstall确认后移除组件；识别/人工文字保留。|取消保留已完成结果，不是回滚已写入文字。|fluent_ui/components/ocr_controls.py:88 / __init__；源码静态；本轮未运行GUI。|
|TPB-216|按available/installing/library_busy控制显示/Enabled；禁用不清原文字|service.supplement(failed_only=True)。|取消保留已完成结果，不是回滚已写入文字。|fluent_ui/components/ocr_controls.py:115 / __init__；源码静态；本轮未运行GUI。|
|TPB-217|按available/installing/library_busy控制显示/Enabled；禁用不清原文字|service.supplement()。|取消保留已完成结果，不是回滚已写入文字。|fluent_ui/components/ocr_controls.py:117 / __init__；源码静态；本轮未运行GUI。|
|TPB-218|按available/installing/library_busy控制显示/Enabled；禁用不清原文字|installing时置install_cancel，否则service.cancel()。|取消保留已完成结果，不是回滚已写入文字。|fluent_ui/components/ocr_controls.py:118 / __init__；源码静态；本轮未运行GUI。|
|TPB-219|按available/installing/library_busy控制显示/Enabled；禁用不清原文字|show_more：重新识别全部表情、查看详情。|取消保留已完成结果，不是回滚已写入文字。|fluent_ui/components/ocr_controls.py:109 / __init__；源码静态；本轮未运行GUI。|

### D. 三项独立问题

#### Telegram导出

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-220|当前Telegram“导出”菜单项及输入标题 / Action/输入/确认/任务反馈|导出为表情合集|匯出為表情合集|Export as emote collection|コレクションに書き出す|t精确键；现菜单只有button.text，无旧Tooltip绑定|
|TPB-221|旧exportPackageButton Tooltip / Action/输入/确认/任务反馈|将当前表情合集全部清洗入库到 ID 同名收藏夹，并导出为 ID.zip|缺失；实际显示 [MISSING: 将当前表情合集全部清洗入库到 ID 同名收藏夹，并导出为 ID.zip]|缺失；实际显示 [MISSING: 将当前表情合集全部清洗入库到 ID 同名收藏夹，并导出为 ID.zip]|缺失；实际显示 [MISSING: 将当前表情合集全部清洗入库到 ID 同名收藏夹，并导出为 ID.zip]|t精确键；现菜单只有button.text，无旧Tooltip绑定|
|TPB-222|Telegram package_id输入正文 / Action/输入/确认/任务反馈|请输入表情合集 ID（同时作为收藏夹名称和 ZIP 文件名）：|請輸入表情合集 ID（同時作為收藏夾名稱與 ZIP 檔名）：|Enter the collection ID (also used as the collection name and ZIP filename):|コレクション ID（保存名と ZIP ファイル名）を入力：|t精确键；现菜单只有button.text，无旧Tooltip绑定|
|TPB-223|Telegram空ID反馈 / Action/输入/确认/任务反馈|表情合集 ID 不能为空|表情合集 ID 不可為空|Package ID cannot be empty|スタンプパック ID を入力してください|t精确键；现菜单只有button.text，无旧Tooltip绑定|
|TPB-224|Telegram覆盖确认 / Action/输入/确认/任务反馈|文件已存在，是否覆盖？<br>{path}|檔案已存在，是否覆寫？<br>{path}|The file already exists. Overwrite it?<br>{path}|ファイルが存在します。上書きしますか？<br>{path}|t精确键；现菜单只有button.text，无旧Tooltip绑定|
|TPB-225|Telegram任务状态 / Action/输入/确认/任务反馈|正在下载并清洗表情...|缺失；实际显示 [MISSING: 正在下载并清洗表情...]|缺失；实际显示 [MISSING: 正在下载并清洗表情...]|缺失；实际显示 [MISSING: 正在下载并清洗表情...]|t精确键；现菜单只有button.text，无旧Tooltip绑定|
|TPB-226|Telegram入库部分失败错误 / Action/输入/确认/任务反馈|表情入库未全部成功，未导出表情合集。请使用相同 ID 重试以补齐索引和收藏夹。|缺失；实际显示 [MISSING: 表情入库未全部成功，未导出表情合集。请使用相同 ID 重试以补齐索引和收藏夹。]|缺失；实际显示 [MISSING: 表情入库未全部成功，未导出表情合集。请使用相同 ID 重试以补齐索引和收藏夹。]|缺失；实际显示 [MISSING: 表情入库未全部成功，未导出表情合集。请使用相同 ID 重试以补齐索引和收藏夹。]|t精确键；现菜单只有button.text，无旧Tooltip绑定|
|TPB-227|Telegram无可导出错误 / Action/输入/确认/任务反馈|没有可导出的表情，所有表情均获取失败。|沒有可匯出的表情，所有表情均取得失敗。|No emotes to export: all emotes failed to download.|すべてのスタンプの取得に失敗したため、エクスポートできません。|t精确键；现菜单只有button.text，无旧Tooltip绑定|
|TPB-228|Telegram成功/部分结果摘要 / Action/输入/确认/任务反馈|处理成功 {imported} 张，重复合并 {duplicated} 张，获取失败跳过 {skipped} 张。|成功處理 {imported} 張，重複合併 {duplicated} 張，取得失敗略過 {skipped} 張。|Processed {imported}, merged {duplicated} duplicates, skipped {skipped} download failures.|処理成功 {imported} 枚、重複統合 {duplicated} 枚、取得失敗でスキップ {skipped} 枚。|t精确键；现菜单只有button.text，无旧Tooltip绑定|
|TPB-229|Telegram失败标题 / Action/输入/确认/任务反馈|表情合集导出失败|缺失；实际显示 [MISSING: 表情合集导出失败]|缺失；实际显示 [MISSING: 表情合集导出失败]|缺失；实际显示 [MISSING: 表情合集导出失败]|t精确键；现菜单只有button.text，无旧Tooltip绑定|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-220|ImportBench.show_exports复制exportPackageButton.text，单击触发隐藏原button.click|exportPackage先询问package_id/目录/覆盖再启动ImportPackThread。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:1902 / exportPackage；源码静态；本轮未运行GUI。|
|TPB-221|_init_ui赋值；随后build_import_tool隐藏actionBar，现导出菜单未复制此Tooltip|这是保留在旧按钮上的长提示；不能当作当前菜单已显示的说明。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:917 / _init_ui；源码静态；本轮未运行GUI。|
|TPB-222|选择“导出为表情合集”后|用户ID去首尾空格；用于category_name及os.path.join(directory,ID+.zip)。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:1903 / exportPackage；源码静态；本轮未运行GUI。|
|TPB-223|用户接受输入但strip后为空|notify后return；此时未启动入库。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:1910 / exportPackage；源码静态；本轮未运行GUI。|
|TPB-224|目标ZIP已存在|拒绝则return；接受后才启动线程。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:1916 / exportPackage；源码静态；本轮未运行GUI。|
|TPB-225|启动线程前tooltip.show|标题为正在导出表情合集；后续_onImportProgress更新内容。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:1919 / exportPackage；源码静态；本轮未运行GUI。|
|TPB-226|export_path存在且fail_count&gt;0|抛错，不进入_export_resource_package；已成功save_file和分类成员不回滚。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:616 / run；源码静态；本轮未运行GUI。|
|TPB-227|imported_count=0；可能所有下载均skipped|抛错；分类add_category可能已经执行，是否新增取决于现有分类解析。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:618 / run；源码静态；本轮未运行GUI。|
|TPB-228|finished_all且_current_worker_signal有效|显示计数；skipped来自下载失败，failed或skipped使outcome=partial。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:1939 / _onPackageFinished；源码静态；本轮未运行GUI。|
|TPB-229|worker.failed且当前任务有效|refresh_library后tooltip.fail；不删除先前已入库内容。|目标分类可能已有内容；导出选中分类当前全部可导出成员，而非只本批成功项；完整副作用见TG事实链。|fluent_ui/views/tg_sticker_view.py:1955 / _onPackageFailed；源码静态；本轮未运行GUI。|

#### 共享旋转控件

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-230|展开/收起面板 / RotatingChevronButton默认Tooltip|展开/收起面板|展开/收起面板（未调用i18n）|展开/收起面板（未调用i18n）|展开/收起面板（未调用i18n）|硬编码/未调用i18n|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-230|控件构造时直接setToolTip中文；调用方可覆盖|默认仅显示文字；不代表当前状态；类自身旋转不更新Tooltip。|当前QQ/TG旧configCard被ImportBench隐藏；Tag Panel不用这个类。|fluent_ui/components/rotating_chevron_button.py:32 / __init__；zh_TW/en/ja精确键缺失；但由于未调用t，实际默认仍是中文，不会出现MISSING。|

#### QQ/TG旧折叠控件

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-231|收起配置面板 / RotatingChevronButton调用方覆盖|收起配置面板|缺失；实际显示 [MISSING: 收起配置面板]|缺失；实际显示 [MISSING: 收起配置面板]|缺失；实际显示 [MISSING: 收起配置面板]|t/bind_text/translated：逐原文精确键|
|TPB-232|展开配置面板 / RotatingChevronButton调用方覆盖|展开配置面板|缺失；实际显示 [MISSING: 展开配置面板]|缺失；实际显示 [MISSING: 展开配置面板]|缺失；实际显示 [MISSING: 展开配置面板]|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-231|旧配置卡片展开/收起时覆盖；QQ refresh_texts还按isVisible更新|QQ/TG现collapse_config/expand_config有presentation时提前返回ImportBench.set_config_expanded（只隐藏summaryRow），不会执行旧动画分支。|保留源码状态文本不等于当前可见入口；不提出恢复旧控件方案。|fluent_ui/views/tg_sticker_view.py:758 / _init_ui；QQ位置见qq_scan_view.py:456/801/824/895；TG见758/1201/1222。|
|TPB-232|旧配置卡片展开/收起时覆盖；QQ refresh_texts还按isVisible更新|QQ/TG现collapse_config/expand_config有presentation时提前返回ImportBench.set_config_expanded（只隐藏summaryRow），不会执行旧动画分支。|保留源码状态文本不等于当前可见入口；不提出恢复旧控件方案。|fluent_ui/views/tg_sticker_view.py:1201 / collapse_config；QQ位置见qq_scan_view.py:456/801/824/895；TG见758/1201/1222。|

#### TG旧高级折叠控件

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-233|展开高级设置 / RotatingChevronButton旧实例|展开高级设置|缺失；实际显示 [MISSING: 展开高级设置]|缺失；实际显示 [MISSING: 展开高级设置]|缺失；实际显示 [MISSING: 展开高级设置]|t/bind_text/translated：逐原文精确键|
|TPB-234|收起高级设置 / RotatingChevronButton旧实例|收起高级设置|缺失；实际显示 [MISSING: 收起高级设置]|缺失；实际显示 [MISSING: 收起高级设置]|缺失；实际显示 [MISSING: 收起高级设置]|t/bind_text/translated：逐原文精确键|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-233|toggleAdvBtn初始或旧toggleAdvancedSettings分支|当前presentation存在时toggleAdvancedSettings改为open_network，旧advWidget可见性分支不执行。|现连接设置独立对话框，不将旧按钮默认状态当作当前网络对话框状态。|fluent_ui/views/tg_sticker_view.py:830 / _init_ui；源码静态；本轮未运行GUI。|
|TPB-234|toggleAdvBtn初始或旧toggleAdvancedSettings分支|当前presentation存在时toggleAdvancedSettings改为open_network，旧advWidget可见性分支不执行。|现连接设置独立对话框，不将旧按钮默认状态当作当前网络对话框状态。|fluent_ui/views/tg_sticker_view.py:1311 / toggleAdvancedSettings；源码静态；本轮未运行GUI。|

#### 键帽旧断言

|编号|入口 / 控件|现有中文原文（片段）|现有 zh_TW|现有 en|现有 ja|翻译键或生成方式|
|---|---|---|---|---|---|---|
|TPB-235|test_ui_polish旧子串断言 / 测试字面量|拖到聊天窗口|不适用（测试原字面量）|不适用（测试原字面量）|不适用（测试原字面量）|测试字面量/不翻译|

|编号|触发条件 / 实际显示状态|对应业务行为|重要副作用 / 限制|源码 / 函数 / 事实证据及未确认|
|---|---|---|---|---|
|TPB-235|测试读取gallery_click_action.hint_label|实际现有说明含“拖动表情至聊天窗口”，不含该旧子串；前轮已做新/HEAD原Tooltip对照均失败。|本轮不运行此GUI测试，不改断言；不是据此证明所有聊天客户端投放成功。|tests/test_ui_polish.py:162 / test_keycaps_are_painted_objects_and_wrap_without_losing_text；完整说明见C/交互发送；Enter键帽由KeycapLabel解析。|

### Telegram 导出：完整事实链（D组记录的共同证据）

1. 当前可见路径是presentation/tools.py::ImportBench.show_exports：从隐藏旧按钮复制text/Enabled，Action触发button.click；没有复制旧按钮Tooltip。exportPackageButton原属于actionBar，build_import_tool隐藏该容器。故“全部清洗入库…”精确键虽确实缺失，但不是已证明当前正常菜单展示的长提示。
2. exportPackage检查current_pack/all_stickers及无运行任务；询问package_id（默认pack.title）、strip非空、选择目录；拼directory/(ID+.zip)，目标已存在先确认覆盖。此前取消均return，未启动入库。未核验特殊文件名/同名层级冲突的运行表现，不推断安全或兼容结果。
3. ImportPackThread.run先storage.add_category(category_name)，再并发下载；按下载完成顺序逐个storage.save_file(strict=True)后add_image_to_category(strict=True)。save_file负责既有资源验证/去重；is_dup计入重复数；ImportSkipped被单独跳过。不是只把临时下载打ZIP。
4. 分类不是每次必新建：StorageService.add_category先resolve_category，已解析到则复用，否则创建ROOT节点。resolve_category可按转义分类路径映射、稳定ID或根级同名解析；保留类别名“全部表情/未分类”等有特殊ROOT语义。因此不能在未限定输入时承诺总是新建同名分类或只修改新分类。
5. 文件入库与分类关联逐项完成；后面一项关联/下载/ZIP失败没有整批回滚。取消检查可以在下一项/下一阶段停止；ThreadPoolExecutor可能等待已有下载结束，不能从cancel标志推断立即停网。finally只清理临时下载目录；已入库资源/成员、可能已创建的空分类保留。
6. export_path且fail_count>0：抛错，不导出包；imported_count=0也抛错。下载获取失败记skipped而非fail_count；只要存在已入库项且无入库fail，可导出部分结果并在完成摘要列skipped。不能把所有失败类别压成同一个计数。
7. _export_resource_package调用ExchangeExportService.export_zip(export_scope=categories,selected_categories=[category_name],package_id=category_name)。_storage_scope按完整转义分类标签精确选取，不隐含整个子树；读取该分类当前全部可导出资源，因此已存在同名分类的旧成员也可能进入ZIP，不限本次新下载。
8. 该ZIP为现有Suzu兼容交换包，不是Nekori全结构nkpkg包：catalog.json/manifest.json、资源assets及可用图标等由ExchangeExportService写入；source_url非空时再加TG.txt。未承诺保留Nekori完整混排顺序。目标名为用户ID+.zip。
9. 在目标目录TemporaryDirectory中写temporary/package.zip；非空检查后，且未取消才os.replace到用户目标。失败/取消前的旧目标保持，临时目录退出清理；若替换已经完成后再取消，现有代码没有撤回已完成替换。不能把停止理解成回滚。
10. _onPackageFinished先校验_current_worker_signal，刷新Library，展示成功/重复/获取失败跳过数量；failed或skipped则partial。_onPackageFailed同样刷新并结束失败；取消走_cancelActiveThreads/tooltip.cancel。没有重跑下载或向真实Token发请求，本轮只核对源码。

## 三、需要指导 AI 决策的事实冲突（不提供替换文字）

F1. 资源排序最终Tooltip不是简单逐片翻译：_update_resource_sort_label把t(标题)+分隔符+t(状态)交给bind_text，_TextBinding.refresh又t(source)。字符串加法丢失_TranslatedText.source；无整句组合键时非中文显示MISSING。以下直接调用现有翻译引擎和_TextBinding.refresh，使用普通内存接收对象所得，未创建GUI或改语言配置：

|状态|zh 实际绑定结果|zh_TW 实际绑定结果|en 实际绑定结果|ja 实际绑定结果|
|---|---|---|---|---|
|自定义顺序|表情显示排序 · 自定义顺序|[MISSING: 表情顯示排序 · 自訂順序]|[MISSING: Emote display order · Custom order]|[MISSING: スタンプの表示順 · 手動順]|
|最近添加|表情显示排序 · 最近添加|[MISSING: 表情顯示排序 · 最近新增]|[MISSING: Emote display order · Recently added]|[MISSING: スタンプの表示順 · 新しく追加した順]|
|最早添加|表情显示排序 · 最早添加|[MISSING: 表情顯示排序 · 最早新增]|[MISSING: Emote display order · Oldest added]|[MISSING: スタンプの表示順 · 古く追加した順]|

F2. _build_command_bar创建加入/移动/标签的长说明，但_sync_command_bar无节点时将其Tooltip覆盖为button.text()；混选/节点时再替换成禁用原因。故初始化说明与当前有效提示不是同一显示状态。本轮不判断应保留哪一条。
F3. 旋转控件默认中文未绑定i18n、也不跟随旋转角度更新；当前QQ/TG旧实例被ImportBench隐藏且调用方大多覆盖默认。这是一个类默认缺口和存量隐藏入口，不能计成每个现用折叠按钮都未翻译。Tag的EdgeDockPanelChrome另有状态/语言刷新。
F4. 旧键帽测试期待“拖到聊天窗口”，实际设置说明是“拖动表情至聊天窗口”。业务还有normal/manage、Ctrl/Shift、多选、缺失文件、焦点和Enter单资源约束。本文不判断正式文案怎么写，也不修改测试来掩盖此差异。
F5. Telegram导出实际会入库/复用分类及旧成员、部分失败可留下已入库内容；当前菜单只显示导出按钮名称，旧长Tooltip未随Action迁移。需要负责人判断哪些事实应在何处表达，本文不补造用户提示。
F6. 文本绑定刷新不是统一能力：SettingRow/translated/bind_text实时绑定，TagFlow/Relative Tabs用户内容原样；TG若干setToolTip(t(...))只在创建或状态变化刷新。当前ImportBench自身若干按钮直接PushButton(t(...))也未见bind_text；未运行切语言时保留“未确认”，不宣称全部四语言实时更新。

F7. 删除工具栏的最终Tooltip在_sync_command_bar中直接取ActionPolicy.delete_label原中文，覆盖前面的bind_text翻译；资源右键菜单同样三条则通过translated绑定。这个同功能不同入口/刷新时点的差异只作事实记录，不修代码。

Tag补充：flow.count是当前标签投影数量，并非已选数；_rebuild_tag_panel在搜索/最近/FilterState有效时从当前_entries计Tag，其它时候project(content_scope_node)覆盖该分类子树；活动Tag即使计数为0仍追加保留。标题数量被窄空间隐藏时不表示Tag被删除。

### 逐项缺失键（只列事实，不填译文）

|源键|缺失的语言|
|---|---|
|从当前分类移除|zh_TW,en,ja|
|全选当前结果|zh_TW,en,ja|
|全部表情来源项仅加入目标分类，其它分类关系保留|zh_TW,en,ja|
|加入分类|zh_TW,en,ja|
|加入分类「{name}」|zh_TW,en,ja|
|图库节点图标大小|zh_TW,en,ja|
|复用已有资源加入目标分类，保留原分类关系和文件。|zh_TW,en,ja|
|将当前表情合集全部清洗入库到 ID 同名收藏夹，并导出为 ID.zip|zh_TW,en,ja|
|展开配置面板|zh_TW,en,ja|
|展开高级设置|zh_TW,en,ja|
|已选 {value_0} 项（{value_1} 张表情，{value_2} 个节点）|zh_TW,en,ja|
|收起配置面板|zh_TW,en,ja|
|收起高级设置|zh_TW,en,ja|
|正在下载并清洗表情...|zh_TW,en,ja|
|此操作仅支持表情；请先取消所选分类节点。|zh_TW,en,ja|
|此操作影响资源及其所有分类关系，不只是从当前分类移除。|zh_TW,en,ja|
|混合选择不能一次移动到分类；请分别选择节点或表情。|zh_TW,en,ja|
|独立调整右侧图库分类节点的图标尺寸。|zh_TW,en,ja|
|移动所选来源的分类关系；其它分类关系保留。|zh_TW,en,ja|
|编辑所选资源的标签归属|zh_TW,en,ja|
|表情入库未全部成功，未导出表情合集。请使用相同 ID 重试以补齐索引和收藏夹。|zh_TW,en,ja|
|表情合集导出失败|zh_TW,en,ja|
|调整来源分类中的持久位置；搜索或显示排序时不可用。|zh_TW,en,ja|

## 四、暂未展开的入口

- 沿用TOOLTIP_REVIEW.md：图片Hover预览元数据长文字、完整导入/恢复/重复决策状态矩阵、外部格式所有异常、QQ扫描/导出/昵称隐私的完整说明、TG帮助/网络恢复/批量下载/所有错误、相似图片结果/阈值、OCR各安装/任务错误、更新与关于、完整任务通知详情。
- 本轮C包含相应设置入口名称/副描述和必要操作，不等于深入审核这些服务全部结果。同名ActionRow按钮已按所属设置行分开记录，不把泛用“导出…”当作统一业务。
- 未穷举所有38文件全部Tooltip，未全量逐条语义审校四语言；未因词汇、长度或未改数量判断文案优劣。

## 五、已验证与未验证边界

- 已验证：HEAD源码定向阅读；AST纯数据展开设置声明/循环，所有录入原文回查源码字面量；四个JSON精确键和格式字段比对；用现有翻译函数复现资源排序二次查译。全文没有生成替换文案或新译文。
- 静态证据不能等同实际用户验收：本轮没有启动/重启Demo，没有发送、拖放、导入、删除、下载、OCR、QQ扫描或GUI回归。TP-A/#60/窗口等原测试结论不在本轮重测。正式版、原Library、Suzu数据未访问。
- 未确认：各非预览配置保存后的首次可见时点（记录内逐项标注）、全部禁用控件实际弹提示行为、跨语言切换后每个非绑定入口是否由其它导航重建、特殊Telegram ID/分类同名路径的实机边界、真实客户端发送/异步读取和网络失败具体时序。
- 动态名称/路径只记录参数来源，不采集真实值；没有Token、私人截图或用户库清单。七处W01实验未编辑/暂存，W02暂停/W03不启用。

本文完成的是TP-B第一阶段事实材料；正式表达取舍与四语言映射等待指导AI/负责人确认。TP-B没有因此标为实现或人工验收通过。
