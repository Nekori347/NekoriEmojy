# TP-B 最后一轮：剩余用户文案事实审查

## TP-B 第四批暨最后一批实施（2026-10-27）

基线 **ae7f5c7 / dev/post-0.2.1**；源码分三次本地提交：**934edfc**（相似工具/补译）、**33cf2e7**（交换反馈/实际写入统计）、**f19d92c**（更新/诊断/繁中勘误与直接回归）。本节是经维护者正式映射授权后的实施记录；下文61条事实表保留采集时源码/语言快照，不把旧原文表改成新的调查结果。文档提交/最终HEAD见CURRENT和#62。**已实现、机器验证、待人工验收**；TP-B四批授权实施已结束，停止主动文案开发。#62/#37仍Open，不等同人工体验或发布。

### 实施与责任层

- 锁定样本 `tests/fixtures/tpb_batch4_copy.json`：19个原中文源键补齐三语言；R1/R2为完整四语言结果模板；共29字段/116语言值，另1格繁中勘误。全部按获批原文接入，没有自行翻译。旧字典键保留；原扫描结果的3个碎片键不再用于当前结果，不补写无用历史译文。前三批锁定文字未改。
- SimilarityDialog在自身保存当前显示模板、参数和安全原错误详情；语言事件重新呈现当前状态及selected数量，不再让status/delete_button初始translated绑定重放旧值。重新扫描按钮沿现有bind_text更新源键。进度、失败、取消、完成/部分失败、重新匹配均有定向验证；语言切换不清空结果/选择、不改page。R1按实际groups与组成员entries计数，R2按failures，仅有失败时追加，各自翻译后格式化，不把组合文本再次t。
- 有效worker.cancelled走现有FeedbackHost `cancelled`终态，不再因旧failures或空error变为success/partial。不改扫描线程中断、特征缓存、感知哈希、阈值或删除业务/确认。已有相似删除确认及隔离真实文件删除回归保留。
- 分享包导入E1沿用saved/skipped数字，说明重复项仍可能合并分类/标签；现有warnings原文保留。分享导出E2沿用ExportSkip数量；主分享及侧栏export_node均取回现有manifest.skipped，只有非零才告知遗漏，同时保留已生成ZIP的目标路径，不将ZIP生成等同所有资源成功。
- 分类选择对话框的body增加E3自然换行静态说明；侧栏导出Action沿现有ToolTip绑定加入批准短句。不改变直接成员范围、分类路径匹配或递归规则，不增加确认步骤。
- NekoriPackageService.export仅在archive.write成功返回后增加written；不存在或OSError的资源计入skipped。现有返回字典resources改为真实成功数，增加skipped；nodes语义不变。没有改包内manifest结构/资源记录顺序、格式版本或原子发布。清单可能仍含缺失源记录，统计与清单数因此允许不同，界面明确显示“导出不完整”及written/skipped/目标路径。无遗漏维持原“导出完成”提示；取消/发布失败仍保护旧目标、清理临时文件。未额外解码、重读或改写来源文件。
- UpdateDialog与UpdateCheckButton仅自动下载入口改为“下载更新”；手动“获取更新”和已准备好的“重启并更新”保持。诊断仅替换D1副描述，不改日志/脱敏/环境摘要/导出采集范围。TPB4-001仅修正批准的现行源键繁中值，中文/英文/日文及旧兼容键不改。Hover预览完全未改。

### 验证与边界

- 共95个不同直接/相邻测试通过（分组执行，重复运行不额外计数）：本批18+实际Qt布局1、原相似工具12、导出范围3、导出取消/发布10、分享包兼容14、第一批12、第二批3、第三批9、TP-A5、#60生命周期8。实际收集清单亦为95项。
- 修改前最小回归曾捕获取消outcome、初值绑定重放、碎片结果/缺译、原生清单数冒充写入数及侧栏漏报；修正后通过。原生合成样本清单3条，1条有效/1条缺失/1条受控读取异常，实际写入1、遗漏2；ZIP可读，有效字节不变。界面结果另测written/skipped=3/0、1/2、0/3。分享包既有多分类/直接成员、重复合并、取消/失败保留目标文件测试通过。
- 前三批与本批组合首次运行39项，36项通过；3个旧“整个字典/整个设置源码永久不变”断言因本批明确授权变更而失败；现只纳入第四批锁定样本和已授权的export_nekori_package新责任。第二批其它方法仍AST逐项比较，前两批值不许改变；第三批及新增第四批继续精确比较整个字典，不接受额外未知变更。3项修正后通过，没有改用户文案以迎合旧断言。
- Win11 Windows Qt后端：本批18+布局1+TP-A5+#60 8，共32项通过。四语言×深浅8组真实分类对话框与8组真实诊断设置行；正常Qt布局、实际widget抓图核对，不只颜色/坐标断言。分类说明宽328px，中文/繁中高16、英/日高32；诊断说明宽264/264/228/225、高45/45/75/75，均满足heightForWidth且不与操作区相交。另有offscreen布局通过；检查英文浅色分类、日文深色诊断真实Qt截图。初次布局测试以owner子树找顶层弹窗未命中，测试程序已改为读取实际可见Qt顶层弹窗，未修改产品窗口关系。
- 独立配置/生成Library的main启动退出冒烟通过；加载HEAD宿主而非W01实验。网络入口被替身拒绝；没有真实更新检查/安装、QQ/TG任务、用户资源交换/删除或私人日志导出/上传。文件读写/删除回归只在测试生成目录。Windows检查不是Win10或其它DPI视觉验收，未测真实网络/磁盘末段异常的所有组合。

### 明确保留的未解决事项

1. E5：侧栏单分类导出会替换同名ZIP，尚无独立覆盖确认；本批未获批覆盖弹窗或改名，不宣称覆盖风险已修复，留#62产品待办。
2. E6：设置兼容包导入经ImportQueue的入口没有传递service.warnings；本批不改队列合同。现有能展示警告的入口仍保留详情，另一入口的丢失问题留独立技术待办。
3. Hover解码失败可能空图像属于独立容错/视觉问题，本批未修。不新增元数据、不改播放缓存或鼠标生命周期。
4. 包内缺失资源并未被伪造或修复；本批只准确告知遗漏。高层计数不保证任意底层I/O故障后每个归档成员都完整；已有发布失败保护保留，未扩展包格式/校验框架。

维护者仍需人工阅读四语言、理解新增副作用说明与相似工具实际状态，确认本机视觉及真实操作体验。#62不因机器通过关闭；不继续审查其它控件或重新润色前三批。七处W01原差异保留、W02暂停、W03不启用；固定Demo持续数据/顺序、正式版、原始Library和Suzu未操作。无Push/打包/发布。提交仅授权源码、翻译、测试与本记录，不含截图、日志、配置或实验。

## 以下为事实采集时的历史快照

基线 **da9f4e6 / dev/post-0.2.1**，2026-10-27。追踪#62/#37。只读源码/AST/翻译JSON；不运行真实任务或GUI。前三批锁定映射不重审、不改写。本报告没有建议替换表、翻译创作或业务修复授权。

## 1. 覆盖范围与摘要

共 **61 条TPB4记录**：通用交换17、相似图片16、Hover预览6、更新/关于/诊断22。去重后t静态源键105个；zh_TW缺22、en缺22、ja缺22，共66个键×语言单元；已存在译文占位符失配0个单元。服务原始错误和用户动态数据另列，不误计为缺译键。

- 优先复用TPB_COPY_FACTS.md的未展开入口、TPB_TOOL_FEEDBACK_FACTS.md的队列/重复决策边界及TOOLTIP_REVIEW.md的前三批当前状态。共有概念只引用，不重复前三批工具栏、设置、QQ/TG/OCR反馈。
- 主窗口信号关系只读HEAD：交换页分享包按钮接Gallery旧同步任务入口，原生包按钮接SettingsCenter方法；设置的兼容包按钮又走ImportQueue。不能因共用服务就声称三者有相同取消、警告、重复决策与恢复体验。
- zh直接显示源文；三语言t缺键显示[MISSING: 源键]。bind_text/translated信号刷新与直接setText(t(...))不同。服务原始异常、用户分类/名称/路径/标签不应自动视为t键；本报告不给任何真实私库值。
- 同一键/语义合并记录，互斥结果的条件在记录内完整区分。带变量模板给出完整原文及参数来源；原值字段用代码表达式说明，不伪造四语言用户数据。
- 高优先级结论见第3节；未亲自复现运行故障，语义冲突均附当前源码条件。没有把缺少错误文字自动判定为必须改写。

## 2. 分组事实记录


## A · 通用导入／导出

### TPB4-001 · 原生交换入口说明

入口/证据：fluent_ui/views/exchange_view.py:26 / __init__。触发：交换页原生包两行。

已执行/真实结果：按钮由main_window HEAD信号连接到SettingsCenter原生导入/导出方法。

副作用、取消及失败边界：不是Suzu平面分享包；具体还原/合并规则见下条，不重新抄设置行。

翻译/刷新：ActionRow/SettingRow中的标题与副描述绑定；main_window只读HEAD核对。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导出整理结果|導出整理結果|Export library organization|整理したデータを書き出す|fluent_ui/views/exchange_view.py:55|
|表情、分类树、图标、标签与分类内混排顺序。|表情、分類樹、圖標、Tag 與分類內混排順序。|Emotes, category trees, icons, tags and mixed ordering.|スタンプ、カテゴリツリー、アイコン、タグ、混合の並び順です。|fluent_ui/views/exchange_view.py:55|
|导入 Nekori 表情合集|匯入 Nekori 表情合集|Import Nekori collection|Nekori コレクションをインポート|fluent_ui/views/exchange_view.py:56|
|恢复整理结果，并合并重复表情的分类关系。|恢復整理結果，并合并重復表情的分類關系。|Restore organization and merge duplicate memberships.|整理したデータを復元し、重複スタンプの関連を統合します。|fluent_ui/views/exchange_view.py:56|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-002 · 原生导出成功计数

入口/证据：fluent_ui/views/settings_center.py:558 / export_nekori_package。触发：service.export正常返回。

已执行/真实结果：ZIP原子发布后显示manifest资源/节点数和目标路径。

副作用、取消及失败边界：NekoriPackageService.export对缺失源不写入，对OSError仅print；返回仍是len(manifest.resources)，不是实际ZIP写入数。成功可遗漏资源；文件数不是完整性证明。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导出完成|匯出完成|Export Complete|エクスポート完了|fluent_ui/views/settings_center.py:580|
|表情 {value_0} 项，分类 {value_1} 个<br>{value_2}|表情 {value_0} 項，分類 {value_1} 個<br>{value_2}|{value_0} emotes, {value_1} categories<br>{value_2}|スタンプ {value_0} 件、カテゴリ {value_1} 件<br>{value_2}|fluent_ui/views/settings_center.py:580|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-003 · 原生导出停止

入口/证据：fluent_ui/views/settings_center.py:558 / export_nekori_package。触发：用户点击可取消导出，ExportCancelled被捕获。

已执行/真实结果：清临时.part，不发布新ZIP。

副作用、取消及失败边界：staged_export_path在末次取消检查后os.replace；旧目标只在成功发布被替换。不是恢复Library，因为导出未改Library。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导出已停止|缺失；t时显示 [MISSING: 导出已停止]|缺失；t时显示 [MISSING: 导出已停止]|缺失；t时显示 [MISSING: 导出已停止]|fluent_ui/views/settings_center.py:575|
|未完成的临时文件已清理，原有目标文件保持不变。|缺失；t时显示 [MISSING: 未完成的临时文件已清理，原有目标文件保持不变。]|缺失；t时显示 [MISSING: 未完成的临时文件已清理，原有目标文件保持不变。]|缺失；t时显示 [MISSING: 未完成的临时文件已清理，原有目标文件保持不变。]|fluent_ui/views/settings_center.py:575|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-004 · 原生导出失败

入口/证据：fluent_ui/views/settings_center.py:558 / export_nekori_package。触发：抛出未被内部吞掉的异常。

已执行/真实结果：未报告成功。

副作用、取消及失败边界：异常str(exc)送show_error详情；内部资源OSError被吞掉不进入此分支。

翻译/刷新：标题t；异常原值，不作为完整翻译键。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导出失败|導出失敗|Export failed|書き出しに失敗しました|fluent_ui/views/settings_center.py:578|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-005 · 原生导入格式与安全跳过

入口/证据：services/nekori_package.py:163 / import_package。触发：选ZIP提交自定义operation，校验清单。

已执行/真实结果：安全的资源继续_restore，包外资源引用跳过，旧不安全图标清空；warnings/errors随结果返回。

副作用、取消及失败边界：有50000条/8GiB总解压/16MiB清单限制；不把内部所有异常列全文。导入不是整库回滚事务，节点可先创建、资源逐项提交。

翻译/刷新：服务原始错误/警告，不调用t；经队列详情呈现。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|这不是 Nekori 原生表情合集：缺少 nekori.json|这不是 Nekori 原生表情合集：缺少 nekori.json（原样；此链未调用t）|这不是 Nekori 原生表情合集：缺少 nekori.json（原样；此链未调用t）|这不是 Nekori 原生表情合集：缺少 nekori.json（原样；此链未调用t）|services/nekori_package.py:197|
|表情合集格式不受支持|表情合集格式不受支持（原样；此链未调用t）|表情合集格式不受支持（原样；此链未调用t）|表情合集格式不受支持（原样；此链未调用t）|services/nekori_package.py:200|
|已跳过不安全的包外资源引用|已跳过不安全的包外资源引用（原样；此链未调用t）|已跳过不安全的包外资源引用（原样；此链未调用t）|已跳过不安全的包外资源引用（原样；此链未调用t）|services/nekori_package.py:208|
|已跳过不安全的分类图片图标引用|已跳过不安全的分类图片图标引用（原样；此链未调用t）|已跳过不安全的分类图片图标引用（原样；此链未调用t）|已跳过不安全的分类图片图标引用（原样；此链未调用t）|services/nekori_package.py:227|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-006 · 原生导入还原与合并

入口/证据：services/nekori_package.py:236 / _restore。触发：空库或已有内容库导入。

已执行/真实结果：空库按包中合法顺序序号还原；已有库同名同父节点复用，重复资源合并成员，已有资源字段不被新字段无条件覆盖；新增项可恢复标签/OCR/元数据。

副作用、取消及失败边界：旧成员与已有手动顺序保留，包序只整理新增位置；不是删除目标库后全量替换。用户跳过可使部分项不入库。队列终态/集中重复菜单复用TPB3-031～040，不重复采集。

翻译/刷新：动态结果由既有ImportQueue展示。

动态/不存在的显示字段：资源、节点、duplicates、orders、skipped、warnings结果字段；没有另一条专属完整还原成功声明。

四语言内容：均为上述动态原值/数值结构，或该字段根本未显示；无对应静态翻译键，不填补不存在译文。

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-007 · 兼容分享格式入口

入口/证据：fluent_ui/views/exchange_view.py:26 / __init__。触发：交换页Suzu分享包区域。

已执行/真实结果：导出平面版本1清单/分类，完整树用原生包。

副作用、取消及失败边界：不重做Suzu数据迁移、QQ/TG独立链；已有格式不等于所有图片格式皆可打包。

翻译/刷新：行标题/副描述通过既有SettingRow绑定。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导入分享包|導入分享包|Import share package|共有パッケージを取り込む|fluent_ui/views/exchange_view.py:61|
|读取平面分类和表情，并自动去重。|讀取平面分類和表情，并自動去重。|Read flat categories and emotes; skip duplicates.|カテゴリとスタンプを取り込み、重複を除きます。|fluent_ui/views/exchange_view.py:61|
|导出全部表情|導出全部表情|Export all emotes|すべてのスタンプを書き出す|fluent_ui/views/exchange_view.py:62|
|导出为 Suzu 平面分享格式。需要完整节点树时请使用 Nekori 表情合集。|導出為 Suzu 平面分享格式。需要完整節點樹時請使用 Nekori 表情合集。|Export as a flat Suzu share ZIP. Use a Nekori package to keep the category tree.|Suzu 共有 ZIP として書き出します。カテゴリツリーの保存には Nekori パッケージを使用してください。|fluent_ui/views/exchange_view.py:62|
|导出指定分类|匯出指定分類|Export Selected Categories|指定したカテゴリをエクスポート|fluent_ui/views/exchange_view.py:63|
|选择要分享的分类。|選擇要分享的分類。|Choose categories to share.|共有するカテゴリを選択します。|fluent_ui/views/exchange_view.py:63|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-008 · 分享导入忙碌

入口/证据：fluent_ui/views/gallery_view.py:3038 / _import_exchange_package。触发：Gallery.import_thread正在运行。

已执行/真实结果：拒绝启动另一次该入口导入。

副作用、取消及失败边界：此处判定对象是旧import_thread，不据此推断能阻止全部ImportQueue并发；本轮不改调度。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导入中|導入中|Importing|取り込み中|fluent_ui/views/gallery_view.py:3042|
|请等待当前导入任务完成|請等待當前導入任務完成|Wait for the current import to finish|現在の取り込みが終わるまでお待ちください|fluent_ui/views/gallery_view.py:3042|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-009 · 分享导入完成与合并

入口/证据：fluent_ui/views/gallery_view.py:3038 / _import_exchange_package。触发：run_exchange_task非取消入口正常返回(saved,skipped)。

已执行/真实结果：刷新图库；重复时仍可能合并分类关系/标签，skipped主要表示复用而非完全无操作。

副作用、取消及失败边界：service.warnings拼接原文但仍show_success。settings.import_suzu_share同服务通过ImportQueue，返回tuple不携带warnings属性；两入口反馈不完全相同。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导入完成|匯入完成|Import Complete|インポート完了|fluent_ui/views/gallery_view.py:2974|
|新增 {value_0} 个，跳过 {value_1} 个|新增 {value_0} 個，跳過 {value_1} 個|Added {value_0}; skipped {value_1}|追加 {value_0} 件、スキップ {value_1} 件|fluent_ui/views/gallery_view.py:3054|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-010 · 分享导入失败

入口/证据：fluent_ui/views/gallery_view.py:3038 / _import_exchange_package。触发：service.import_zip或后续refresh异常。

已执行/真实结果：可能先创建分类/写入图标/保存若干资源。

副作用、取消及失败边界：_import_into_library抛“导入中断；已保存…已合并…”；已有逐项提交不撤销。当前交换页run_exchange_task未传cancellable=True，没有任务取消按钮；选文件取消在启动前返回。

翻译/刷新：固定标题t，正文异常原值详情。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导入失败|導入失敗|Import failed|取り込みに失敗しました|fluent_ui/views/gallery_view.py:3059|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-011 · 分享导出分类范围

入口/证据：fluent_ui/views/gallery_view.py:3064 / _export_selected_categories_exchange_package。触发：全部分类列表复选；至少勾一项才可确认；没分类拒绝。

已执行/真实结果：selected_categories传ExchangeExportService。

副作用、取消及失败边界：服务按精确转义分类路径选择直接成员，不默认含整棵子树；选父不等于选子。列表是category_labels生成的路径身份，不仅末级名称。取消对话框不导出。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|选择要导出的分类|選擇要導出的分類|Choose categories to export|書き出すカテゴリを選択|fluent_ui/views/gallery_view.py:3072|
|无法导出|無法導出|Cannot export|書き出しできません|fluent_ui/views/gallery_view.py:2577|
|请先创建分类|請先創建分類|Create a category first|先にカテゴリを作成してください|fluent_ui/views/gallery_view.py:2357|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-012 · 分享导出完成/跳过

入口/证据：fluent_ui/views/gallery_view.py:3090 / _export_exchange_package。触发：export_zip返回manifest；有skipped则notice，无则toast。

已执行/真实结果：ZIP已发布，显示路径；有跳过则显数量。

副作用、取消及失败边界：ExportSkip既包含类型不支持，也包含文件读取失败/PNG解码失败；统一叫“不支持”并不覆盖全部原因。零有效项也可能产空包并显示完成，不能把完成理解为每个源都导出。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导出完成|匯出完成|Export Complete|エクスポート完了|fluent_ui/views/gallery_view.py:2595|
|表情合集已保存到<br>{value_0}|表情合集已保存到<br>{value_0}|Package saved to<br>{value_0}|パッケージの保存先<br>{value_0}|fluent_ui/views/gallery_view.py:3106|
|跳过 {count} 个不支持的文件|跳過 {count} 個不支援的檔案|Skipped {count} unsupported files|未対応のファイル {count} 件をスキップしました|fluent_ui/views/gallery_view.py:3108|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-013 · 侧栏分类导出

入口/证据：fluent_ui/views/gallery_view.py:645 / export_node。触发：选择目录后按节点名.zip导出平面分享包，正常返回。

已执行/真实结果：目标是该分类直接成员，不默认子树。

副作用、取消及失败边界：未接收/检查service.export_zip返回的skipped，可能跳过仍只成功通知。目标已存在时此入口只选目录，没有保存文件对话框的覆盖确认；成功时原子替换旧ZIP。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导出完成|匯出完成|Export Complete|エクスポート完了|fluent_ui/views/gallery_view.py:2595|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-014 · 通用导出覆盖与错误

入口/证据：fluent_ui/views/gallery_view.py:3090 / _export_exchange_package。触发：保存目标后遇异常。

已执行/真实结果：失败/取消的.part清理；旧目标保持；成功则替换。

副作用、取消及失败边界：主入口getSaveFileName使用Qt默认保存对话框，可有标准覆盖确认，无第二自定义确认；侧栏目录入口不同。后续异常详情可能包含路径，报告不举真实值。

翻译/刷新：标题t，未知详情原值；不穷举格式/IO异常。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导出失败|導出失敗|Export failed|書き出しに失敗しました|fluent_ui/views/gallery_view.py:666|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-015 · 分卷入口与进行中

入口/证据：fluent_ui/views/exchange_view.py:86 / _split_package。触发：选输入ZIP、输出目录后启动非cancellable任务。

已执行/真实结果：校验分享格式，再按完整资源组成新卷。

副作用、取消及失败边界：是Suzu分享包格式，不是任意ZIP/原生包；没有任务取消按钮，启动前任一文件选择取消则无操作。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|表情合集切割分卷|表情合集切割分卷|Split emote package|スタンプパックを分割|fluent_ui/views/exchange_view.py:93|
|选择分卷保存文件夹|選擇分卷儲存資料夾|Choose volume output folder|分割ファイルの保存先を選択|fluent_ui/views/exchange_view.py:98|
|正在切割表情合集|正在切割表情合集|Splitting emote package|スタンプパックを分割中|fluent_ui/views/exchange_view.py:104|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-016 · 分卷完成

入口/证据：fluent_ui/views/exchange_view.py:86 / _split_package。触发：split_package返回全部卷。

已执行/真实结果：新建唯一输出目录，校验实际卷大小和资源内容完整性后返回。

副作用、取消及失败边界：按资源不拆图像；单个资源加清单/图标超100MB则失败；失败清本次新目录，不覆盖原ZIP/前次卷。成功不是已经导回库。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|分卷完成|分卷完成|Split complete|分割完了|fluent_ui/views/exchange_view.py:107|
|已生成 {count} 个分卷，每卷不超过 100 MB，表情内容保持不变。<br>保存位置：{path}<br>请通过“导入表情合集”逐卷导入，分类会自动合并。|已產生 {count} 個分卷，每卷不超過 100 MB，表情內容保持不變。<br>儲存位置：{path}<br>請透過「匯入表情合集」逐卷匯入，分類會自動合併。|Created {count} volumes, each no larger than 100 MB, with unchanged emote contents.<br>Saved to: {path}<br>Use Import emote package for each volume; categories merge automatically.|スタンプを変更せず、各100 MB以下のファイルを{count}個作成しました。<br>保存先：{path}<br>「スタンプパックを読み込む」で各巻を読み込むと、分類が自動的に統合されます。|fluent_ui/views/exchange_view.py:108|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-017 · 分卷失败

入口/证据：fluent_ui/views/exchange_view.py:86 / _split_package。触发：格式、卷大小、校验或IO异常。

已执行/真实结果：可能建过本次唯一目录，异常时服务清理。

副作用、取消及失败边界：未知异常原值notice error，不译整串；无“取消后原样”错误承诺。

翻译/刷新：标题t；服务动态详情不查译。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|分卷失败|分卷失敗|Split failed|分割に失敗しました|fluent_ui/views/exchange_view.py:113|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

## B · 相似图片

### TPB4-018 · 相似工具范围与提示

入口/证据：fluent_ui/presentation/similarity.py:13 / build_similarity。触发：打开现用相似图片工具。

已执行/真实结果：只是选择扫描范围/类型，未修改资源。

副作用、取消及失败边界：长操作hint已hide，不计可见入口；“副本”词不构成精确字节重复证明，实际是感知哈希阈值候选。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|扫描后对比表情，勾选需要删除的副本。点击表情可放大。|掃描後比較表情，勾選要刪除的副本。點擊表情可放大。|Compare scanned emotes and select copies to delete. Click an emote to enlarge it.|スキャン後に比較し、削除するコピーを選択します。スタンプをクリックすると拡大できます。|fluent_ui/presentation/similarity.py:19|
|范围|範圍|Scope|範囲|fluent_ui/presentation/similarity.py:20|
|仅静态图|缺失；t时显示 [MISSING: 仅静态图]|缺失；t时显示 [MISSING: 仅静态图]|缺失；t时显示 [MISSING: 仅静态图]|fluent_ui/presentation/similarity.py:25|
|仅动图|缺失；t时显示 [MISSING: 仅动图]|缺失；t时显示 [MISSING: 仅动图]|缺失；t时显示 [MISSING: 仅动图]|fluent_ui/presentation/similarity.py:25|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-019 · 阈值标签

入口/证据：fluent_ui/presentation/similarity.py:13 / build_similarity。触发：滑条0～16，默认6。

已执行/真实结果：影响Hamming距离阈值，松大严小；可复用已有特征重新匹配。

副作用、取消及失败边界：不是相似百分比。静态63位AC感知哈希；动图8样本至少7组距离不超阈值，不要求原文件相同。

翻译/刷新：标签t/translated，数值直接显示；没有单独百分比说明。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|严格|嚴格|Strict|厳密|fluent_ui/presentation/similarity.py:30|
|宽松|寬鬆|Loose|緩い|fluent_ui/presentation/similarity.py:32|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-020 · 初始/范围变更

入口/证据：fluent_ui/views/similarity_view.py:265 / invalidate。触发：范围/图种变化触发invalidate。

已执行/真实结果：清当前特征、结果和勾选；未删除资源。

副作用、取消及失败边界：初始status原为translated“选择范围后点击开始扫描。”；后续setText不更新原绑定，语言切换有可能重放初始源而覆盖当前进度/终态。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|范围已变更，请点击开始扫描。|缺失；t时显示 [MISSING: 范围已变更，请点击开始扫描。]|缺失；t时显示 [MISSING: 范围已变更，请点击开始扫描。]|缺失；t时显示 [MISSING: 范围已变更，请点击开始扫描。]|fluent_ui/views/similarity_view.py:271|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-021 · 扫描/重匹配

入口/证据：fluent_ui/views/similarity_view.py:307 / start_worker。触发：未有worker、未删除中；features=None扫描，否则重匹配已有特征。

已执行/真实结果：清当前结果/选择，后台扫描或匹配。

副作用、取消及失败边界：扫描写专用特征缓存，不改源图/Library分类关系；重匹配不是重新导入或去重删除。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|正在扫描…|缺失；t时显示 [MISSING: 正在扫描…]|缺失；t时显示 [MISSING: 正在扫描…]|缺失；t时显示 [MISSING: 正在扫描…]|fluent_ui/views/similarity_view.py:314|
|正在重新匹配…|缺失；t时显示 [MISSING: 正在重新匹配…]|缺失；t时显示 [MISSING: 正在重新匹配…]|缺失；t时显示 [MISSING: 正在重新匹配…]|fluent_ui/views/similarity_view.py:314|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-022 · 阶段进度

入口/证据：fluent_ui/views/similarity_view.py:333 / on_progress。触发：worker.report的phase为扫描或匹配。

已执行/真实结果：status为已翻译phase+current/total。

副作用、取消及失败边界：计数是阶段工作单元，不是已确认重复/已删除数。

翻译/刷新：仅phase t；数字直接插入。

动态/不存在的显示字段：f'{t(phase)}：{current} / {total}'；phase只由扫描/匹配两固定阶段提供。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|扫描|缺失；t时显示 [MISSING: 扫描]|缺失；t时显示 [MISSING: 扫描]|缺失；t时显示 [MISSING: 扫描]|fluent_ui/views/similarity_view.py:66|
|匹配|缺失；t时显示 [MISSING: 匹配]|缺失；t时显示 [MISSING: 匹配]|缺失；t时显示 [MISSING: 匹配]|fluent_ui/views/similarity_view.py:69|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-023 · 扫描结果与跳过

入口/证据：fluent_ui/views/similarity_view.py:337 / worker_finished。触发：worker未error/cancelled。

已执行/真实结果：groups/entries更新，failures显示数量与前20项文件错误tooltip。

副作用、取消及失败边界：entries是分组成员数，不是重复文件数。扫描仅写缓存。失败项导致partial，没失败success。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

动态/不存在的显示字段：结果按组数/成员数拼接，真实文件名和异常进入tooltip；报告不列任何私人值。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|扫描完成：|缺失；t时显示 [MISSING: 扫描完成：]|缺失；t时显示 [MISSING: 扫描完成：]|缺失；t时显示 [MISSING: 扫描完成：]|fluent_ui/views/similarity_view.py:352|
|组疑似相似表情|缺失；t时显示 [MISSING: 组疑似相似表情]|缺失；t时显示 [MISSING: 组疑似相似表情]|缺失；t时显示 [MISSING: 组疑似相似表情]|fluent_ui/views/similarity_view.py:352|
|张表情|張表情|emotes|枚のスタンプ|fluent_ui/views/similarity_view.py:353|
|个文件无法读取，已跳过|缺失；t时显示 [MISSING: 个文件无法读取，已跳过]|缺失；t时显示 [MISSING: 个文件无法读取，已跳过]|缺失；t时显示 [MISSING: 个文件无法读取，已跳过]|fluent_ui/views/similarity_view.py:354|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-024 · 结果排列规则

入口/证据：fluent_ui/views/similarity_view.py:371 / render_page。触发：渲染每页最多36成员，可跨组分页。

已执行/真实结果：组序由service静态优先、路径排序及锚点贪心分组生成；组内不是相似度得分排名。

副作用、取消及失败边界：没有可见相似度百分比/排序控件。anchor组成员不等于两两精确一致，组亦不代表传递闭包。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|相似组|相似群組|Similarity group|類似グループ|fluent_ui/views/similarity_view.py:194|
|动图|動圖|Animated emotes|アニメーションスタンプ|fluent_ui/views/similarity_view.py:388|
|静态图|靜態圖|Static image|静止画|fluent_ui/views/similarity_view.py:388|
|续|缺失；t时显示 [MISSING: 续]|缺失；t时显示 [MISSING: 续]|缺失；t时显示 [MISSING: 续]|fluent_ui/views/similarity_view.py:390|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-025 · 空结果

入口/证据：fluent_ui/views/similarity_view.py:371 / render_page。触发：当前页无entries；包括初始、失效重置、扫描无候选或取消后。

已执行/真实结果：仅显示空列表。

副作用、取消及失败边界：不能仅凭此句推断扫描已成功完成或库里无重复；结合status判断。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|暂无相似表情|暫無相似表情|No similar emotes|類似スタンプはありません|fluent_ui/views/similarity_view.py:415|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-026 · 扫描失败

入口/证据：fluent_ui/views/similarity_view.py:337 / worker_finished。触发：worker.error存在。

已执行/真实结果：features=None，未得到完整结果。

副作用、取消及失败边界：正文拼原异常，不作t错误；可能已有特征缓存，未删资源。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|扫描失败：|缺失；t时显示 [MISSING: 扫描失败：]|缺失；t时显示 [MISSING: 扫描失败：]|缺失；t时显示 [MISSING: 扫描失败：]|fluent_ui/views/similarity_view.py:343|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-027 · 取消请求/完成

入口/证据：fluent_ui/views/similarity_view.py:364 / cancel。触发：取消请求时requestInterruption；worker_finished见worker.cancelled。

已执行/真实结果：取消前已提交缓存保留，未删除资源。

副作用、取消及失败边界：cancel_button原控件hide，实际反馈任务提供cancel=self.cancel。worker_finished.finish outcome不看cancelled：无error/failures时为success，有旧failures为partial，和取消正文不一致。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|正在取消…|缺失；t时显示 [MISSING: 正在取消…]|缺失；t时显示 [MISSING: 正在取消…]|缺失；t时显示 [MISSING: 正在取消…]|fluent_ui/views/similarity_view.py:368|
|已取消，已完成的特征缓存可在下次扫描时复用。|缺失；t时显示 [MISSING: 已取消，已完成的特征缓存可在下次扫描时复用。]|缺失；t时显示 [MISSING: 已取消，已完成的特征缓存可在下次扫描时复用。]|缺失；t时显示 [MISSING: 已取消，已完成的特征缓存可在下次扫描时复用。]|fluent_ui/views/similarity_view.py:346|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-028 · 预览与删除勾选

入口/证据：fluent_ui/views/similarity_view.py:139 / __init__。触发：GroupPreview放大，键盘导航/Del。

已执行/真实结果：显示文件名、宽高、KB、动图时长和所属分类原值，翻页含全局及组内序号；只改变owner.selected集合，关闭预览不提交删除。

副作用、取消及失败边界：没有独立“保留一个/移出分类”操作；未勾选就是保留候选，不会自动选唯一正确原件。

翻译/刷新：本记录源键来自GroupPreview.__init__；构造时t，不是SimilarityWorker构造。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|相似表情预览|相似表情預覽|Similar emote preview|類似スタンプのプレビュー|fluent_ui/views/similarity_view.py:140|
|上一张|缺失；t时显示 [MISSING: 上一张]|缺失；t时显示 [MISSING: 上一张]|缺失；t时显示 [MISSING: 上一张]|fluent_ui/views/similarity_view.py:154|
|下一张|缺失；t时显示 [MISSING: 下一张]|缺失；t时显示 [MISSING: 下一张]|缺失；t时显示 [MISSING: 下一张]|fluent_ui/views/similarity_view.py:155|
|选择删除|缺失；t时显示 [MISSING: 选择删除]|缺失；t时显示 [MISSING: 选择删除]|缺失；t时显示 [MISSING: 选择删除]|fluent_ui/views/similarity_view.py:158|
|← / ↑ 上一张，→ / ↓ 下一张；跨组浏览，Del 切换删除勾选。|←／↑ 上一張，→／↓ 下一張；可跨群組瀏覽，Del 切換刪除勾選。|← / ↑ Previous, → / ↓ Next; browse across groups. Del toggles selection for deletion.|←／↑ 前へ、→／↓ 次へ（グループ間も移動）。Del で削除対象を切り替えます。|fluent_ui/views/similarity_view.py:164|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-029 · 清空选择/删除数量

入口/证据：fluent_ui/views/similarity_view.py:458 / update_selection。触发：选择/取消勾选更新按钮；清空选择只清set。

已执行/真实结果：按钮标题拼selected数量。

副作用、取消及失败边界：不删除数据。初始按钮translated源为删除所选（0），之后setText拼count；语言信号可把已选非零按钮重放为0，直到再更新选择。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|删除所选|缺失；t时显示 [MISSING: 删除所选]|缺失；t时显示 [MISSING: 删除所选]|缺失；t时显示 [MISSING: 删除所选]|fluent_ui/views/similarity_view.py:459|
|清空选择|清除選取|Clear Selection|選択を解除|fluent_ui/presentation/similarity.py:42|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-030 · 确认全局删除

入口/证据：fluent_ui/views/similarity_view.py:468 / delete_selected。触发：有勾选，用户明确确认。

已执行/真实结果：调用StorageService.delete_images_batch。

副作用、取消及失败边界：全局删除原件/索引/所有成员关系，不是移出当前分类，也非只清结果页；缺失原件仅清失效索引。Windows Shell回收失败不会回退unlink；取消确认无删除。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|确认删除|確認刪除|Confirm deletion|削除の確認|fluent_ui/views/similarity_view.py:471|
|将把所选表情移入 Windows 回收站，并移除索引及分类关系。<br>已选择 {count} 张表情。<br>疑似相似不代表内容相同，请确认已逐张比较。|將所選表情移至 Windows 資源回收筒，並移除索引及分類關係。<br>已選取 {count} 張表情。<br>相似不代表內容相同，請先逐張比較。|Move the selected emotes to the Windows Recycle Bin and remove their index and category links.<br>{count} emotes selected.<br>Similar emotes may differ. Compare each one before deleting.|選択したスタンプを Windows のごみ箱に移動し、インデックスとカテゴリの関連付けを削除します。<br>選択中：{count} 枚。<br>類似候補でも内容は異なる場合があります。一枚ずつ確認してください。|fluent_ui/views/similarity_view.py:471|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-031 · 删除进行中

入口/证据：fluent_ui/views/similarity_view.py:468 / delete_selected。触发：确认后启动ExchangeWorker。

已执行/真实结果：逐项移动回收站并forget_resource。

副作用、取消及失败边界：UI未传cancel_check且feedback task无cancel，删除不能按扫描取消；关窗等待收尾，不中断已删项。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|正在删除所选表情…|缺失；t时显示 [MISSING: 正在删除所选表情…]|缺失；t时显示 [MISSING: 正在删除所选表情…]|缺失；t时显示 [MISSING: 正在删除所选表情…]|fluent_ui/views/similarity_view.py:480|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-032 · 删除失败/部分

入口/证据：fluent_ui/views/similarity_view.py:503 / deletion_finished。触发：worker.error、库刷新异常或result.failed。

已执行/真实结果：已删文件和已移除关系不自动撤销；仅保留仍存在文件重建候选。

副作用、取消及失败边界：有deleted用partial，否则error；数据库移除失败时文件可能已回收，记录留Missing。只有异常详情，不创造每种系统错误译文。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|删除失败：|缺失；t时显示 [MISSING: 删除失败：]|缺失；t时显示 [MISSING: 删除失败：]|缺失；t时显示 [MISSING: 删除失败：]|fluent_ui/views/similarity_view.py:496|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-033 · 预览不可读取

入口/证据：fluent_ui/views/similarity_view.py:79 / __init__。触发：ImageLabel读取QImage为空。

已执行/真实结果：卡片仍可呈现其它信息。

副作用、取消及失败边界：预览失败不证明资源已删除，也不等于文件内容相同。

翻译/刷新：源键在ImageLabel.__init__；事件时t。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|无法预览|無法預覽|Preview unavailable|プレビューできません|fluent_ui/views/similarity_view.py:94|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

## C · 图片Hover预览

### TPB4-034 · 分类说明

入口/证据：fluent_ui/components/hover_preview.py:199 / update_texts。触发：show_preview及language_changed刷新。

已执行/真实结果：有category_str显示分类前缀与原分类文本；无则无分类。

副作用、取消及失败边界：用户分类串不译，多个分类来自当前库关系；不是当前导航位置。

翻译/刷新：update_texts绑定语言信号，仅前缀t；category原值。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|分类|分類|Category|カテゴリ|fluent_ui/components/hover_preview.py:201|
|无分类|無分類|Uncategorized|未分類|fluent_ui/components/hover_preview.py:201|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-035 · 文件名与路径

入口/证据：fluent_ui/components/hover_preview.py:203 / update_identity。触发：get_preview_info提供basename和库相对路径，异常时path回退basename。

已执行/真实结果：name/path标签用原值，显示时name/path存在才visible；path tooltip另改绝对image_path。

副作用、取消及失败边界：中间省略视觉文本，Tooltip可看完整值；相对正文/绝对tooltip不应误描述为全局匿名。纯本地显示不代表上传。

翻译/刷新：无翻译键；四语言都显示同一个用户数据值。

动态/不存在的显示字段：正文name=basename(image_path)，path=index.relative_path(image_path)；tooltip=os.path.abspath(image_path)。无真实值样例。

四语言内容：均为上述动态原值/数值结构，或该字段根本未显示；无对应静态翻译键，不填补不存在译文。

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-036 · 标签元数据

入口/证据：fluent_ui/components/hover_preview.py:235 / show_preview。触发：keyword_str经StorageService.parse_tags→TagItem。

已执行/真实结果：复用TagFlow绘制；无标签则隐藏。

副作用、取消及失败边界：最多两行显示，长chip限制宽度；完整keyword_str为tooltip。不是把OCR文字当Tag，用户标签不译。

翻译/刷新：四语言均原数据；无独立静态源键。

动态/不存在的显示字段：parse_tags(keyword_str)及完整keyword_str tooltip；不输出用户Tag样例。

四语言内容：均为上述动态原值/数值结构，或该字段根本未显示；无对应静态翻译键，不填补不存在译文。

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-037 · OCR文字元数据

入口/证据：fluent_ui/components/hover_preview.py:235 / show_preview。触发：info.ocr_text非空。

已执行/真实结果：折叠空白为一行、按宽度尾部省略；无值隐藏标题带。

副作用、取消及失败边界：仅显示已有OCR/人工文本，不在Hover触发识别、不写数据或标签；内容原值。

翻译/刷新：四语言均原数据，不作为t源。

动态/不存在的显示字段：str(info.get('ocr_text') or '').strip()；PreviewText.setText将空白合一，paintEvent尾部省略。

四语言内容：均为上述动态原值/数值结构，或该字段根本未显示；无对应静态翻译键，不填补不存在译文。

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-038 · 尺寸与格式显示边界

入口/证据：fluent_ui/views/gallery_view.py:3522 / get_preview_info。触发：核对当前主图库Hover信息字典。

已执行/真实结果：只返回name/path/ocr_text；尺寸由QImageReader用于图像适配。

副作用、取消及失败边界：当前Popup没有显示尺寸/格式/文件字节数的专用文案。不要将相似图片description中的尺寸/时长误认为Hover字段，也不新增不存在的译文。

翻译/刷新：无静态源键/对应显示。

动态/不存在的显示字段：get_preview_info返回3字段；show_preview读取尺寸但未建立宽高/格式信息Label。

四语言内容：均为上述动态原值/数值结构，或该字段根本未显示；无对应静态翻译键，不填补不存在译文。

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-039 · 缺失/解码失败

入口/证据：fluent_ui/components/hover_preview.py:235 / show_preview。触发：image_path不存在直接return；静态read为空不设pixmap，末尾仍show。

已执行/真实结果：缺失来源不新开预览；解码失败可能出现元数据与空图像。

副作用、取消及失败边界：没有专用“文件不存在/读取失败”文字；不可凭空填四语言。controller进入前已取消旧popup。动图错误未连接专门用户状态。

翻译/刷新：无静态错误文案，静默/空图像的显示边界。

动态/不存在的显示字段：exists→return；QImageReader.read.isNull()只跳过setPixmap；QMovie没有新文字回调。

四语言内容：均为上述动态原值/数值结构，或该字段根本未显示；无对应静态翻译键，不填补不存在译文。

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

## D · 更新、关于与诊断

### TPB4-040 · 检查进行中

入口/证据：fluent_ui/components/update_dialog.py:164 / check。触发：手动open或check，channel可用。

已执行/真实结果：仅获取发布信息、比较版本。

副作用、取消及失败边界：没有下载/安装。开发无channel不访问公开端点。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|当前版本|目前版本|Current version|現在のバージョン|fluent_ui/components/update_dialog.py:76|
|正在检查更新…|正在檢查更新…|Checking for updates…|更新を確認中…|fluent_ui/components/update_dialog.py:78|
|检查更新|檢查更新|Check for updates|更新を確認|fluent_ui/components/update_dialog.py:91|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-041 · 开发渠道无公开更新

入口/证据：fluent_ui/components/update_dialog.py:164 / check。触发：channel_available=False。

已执行/真实结果：未发检查请求，release_changed(None)。

副作用、取消及失败边界：不等于已确认正式版为最新。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|当前为开发版，暂未提供公开更新。|目前為開發版，尚未提供公開更新。|This development build has no public updates yet.|開発版のため、公開更新はまだありません。|fluent_ui/components/update_dialog.py:168|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-042 · 检查无新版本

入口/证据：fluent_ui/components/update_dialog.py:176 / _checked。触发：service返回None且非unpublished。

已执行/真实结果：当前latest版本不高于本地；只完成检查。

副作用、取消及失败边界：没有“已安装新版”承诺；不用旧字典“已是最新版”代替当前显示。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|暂未发现可用更新|尚未發現可用更新|No updates available|利用可能な更新はありません|fluent_ui/components/update_dialog.py:182|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-043 · 尚无发布版本

入口/证据：fluent_ui/components/update_dialog.py:176 / _checked。触发：last_check_status=unpublished。

已执行/真实结果：404/空发布结果，无可下载发行物。

副作用、取消及失败边界：不是网络失败，也不是已升级。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|目前没有可用的发布版本。|目前沒有可用的發佈版本。|No published version is available yet.|現在利用できる公開バージョンはありません。|fluent_ui/components/update_dialog.py:182|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-044 · 发现更新

入口/证据：fluent_ui/components/update_dialog.py:176 / _checked。触发：release存在。

已执行/真实结果：显示版本/说明；未下载。

副作用、取消及失败边界：notes是远端release.body原值，以PlainText显示，不翻译；内容真实性不在本轮核验。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|最新可用版本|最新可用版本|Latest available version|最新バージョン|fluent_ui/components/update_dialog.py:190|
|有可用更新|有可用更新|Update available|更新があります|fluent_ui/components/update_dialog.py:191|
|有可用更新，暂未获取更新说明。|有可用更新，暫未取得更新說明。|An update is available. Release notes are not available yet.|更新があります。更新内容はまだ取得できていません。|fluent_ui/components/update_dialog.py:191|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-045 · 获取/立即更新动作

入口/证据：fluent_ui/components/update_dialog.py:218 / action。触发：release未prepared。

已执行/真实结果：有manifest且可更新则点击下载；manual_only或无本地manifest打开发布页。

副作用、取消及失败边界：“立即更新”此时不是立即安装，下一阶段仍需重启确认；外部页面动作不验证用户是否已更新。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|立即更新|立即更新|Update now|今すぐ更新|fluent_ui/components/update_dialog.py:195|
|获取更新|取得更新|Get update|更新を取得|fluent_ui/components/update_dialog.py:198|
|打开发布页|開啟發布頁|Open releases|リリースページを開く|fluent_ui/components/update_dialog.py:96|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-046 · 下载校验

入口/证据：fluent_ui/components/update_dialog.py:218 / action。触发：可自动更新release点击action。

已执行/真实结果：下载到.update并校验长度/digest、解压manifest/flavor/version，写ready。

副作用、取消及失败边界：校验失败进_error，不修改当前安装；取消清下载ZIP和未完成stage；不是续传承诺。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|正在下载并校验更新…|正在下載並驗證更新…|Downloading and verifying update…|更新をダウンロードして検証中…|fluent_ui/components/update_dialog.py:237|
|取消下载|取消下載|Cancel download|ダウンロードを中止|fluent_ui/components/update_dialog.py:94|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-047 · 下载取消

入口/证据：fluent_ui/components/update_dialog.py:126 / _run。触发：UpdateWorker.cancelled。

已执行/真实结果：取消本次下载准备；恢复动作按钮可用。

副作用、取消及失败边界：cancel按钮只在cancellable下载显示。检查和安装也复用_run，但没有同一可见取消按钮；关闭/稍后不是取消下载，closeEvent未调用service.cancel。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|下载已取消|已取消下載|Download cancelled|ダウンロードを中止しました|fluent_ui/components/update_dialog.py:143|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-048 · 更新准备好

入口/证据：fluent_ui/components/update_dialog.py:212 / _prepared。触发：下载/校验就绪或open_manual发现ready。

已执行/真实结果：本地已有可安装stage，尚未替换程序。

副作用、取消及失败边界：缓存ready检查不等于安装成功；程序版本仍旧。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|更新已准备好，点击重启后安装|更新已準備好，點擊重新啟動後安裝|Update ready. Restart to install.|更新の準備ができました。再起動してインストールできます|fluent_ui/components/update_dialog.py:214|
|重启并更新|重新啟動並更新|Restart and update|再起動して更新|fluent_ui/components/update_dialog.py:215|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-049 · 有任务时阻止安装

入口/证据：fluent_ui/components/update_dialog.py:218 / action。触发：prepared且active_tasks非空。

已执行/真实结果：不启动安装器。

副作用、取消及失败边界：不会取消既有任务或承诺自动排队安装，用户稍后重试。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|请等待导入、导出和后台任务结束后再更新|請等待匯入、匯出與背景工作結束後再更新|Wait for imports, exports and background tasks to finish before updating.|インポート、エクスポート、バックグラウンド処理の完了後に更新してください|fluent_ui/components/update_dialog.py:223|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-050 · 安装前确认

入口/证据：fluent_ui/components/update_dialog.py:218 / action。触发：prepared、无活跃任务，确认。

已执行/真实结果：launch_installer复制并验证本机helper，等handshake，成功后app quit。

副作用、取消及失败边界：这里只能证明安装器已准备，不是最终安装成功。未打开安装器/旧数据实测，本轮不运行。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|现在退出软件并安装更新？用户数据将保留。|現在退出軟體並安裝更新？使用者資料將保留。|Exit now and install the update? Your data will be preserved.|終了して更新をインストールしますか？ユーザーデータは保持されます。|fluent_ui/components/update_dialog.py:225|
|正在准备重启更新…|正在準備重新啟動更新…|Preparing to restart and update…|再起動の準備中…|fluent_ui/components/update_dialog.py:230|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-051 · 更新错误

入口/证据：fluent_ui/components/update_dialog.py:153 / _error。触发：检查/下载/校验/启动安装器任一阶段异常。

已执行/真实结果：_checking时清release并标error；原error用notes.setPlainText显示。

副作用、取消及失败边界：通用标题不区分失败阶段，详情保留。已准备包可保留；不是“检查成功=更新成功”。

翻译/刷新：对话框构造/事件时t，未连接language_changed完整刷新全部既有状态。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|更新失败，请重试或打开发布页|更新失敗，請重試或開啟發布頁|Update failed. Retry or open the release page.|更新に失敗しました。再試行するかリリースページを開いてください|fluent_ui/components/update_dialog.py:159|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-052 · 设置按钮状态

入口/证据：fluent_ui/components/update_center.py:75 / refresh。触发：UpdateCheckButton读center.state/release。

已执行/真实结果：检查中禁用，其它标题由可用包/manifest决定。

副作用、取消及失败边界：按钮/UpdateBadge绑定语言及center.changed，可即时换语；没有新增“安装完成”状态。

翻译/刷新：本条定位UpdateBadge/UpdateCheckButton同名refresh，实际文字在UpdateCheckButton.refresh；字面量精确行附后。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|检查中…|檢查中…|Checking…|確認中…|fluent_ui/components/update_center.py:78|
|检查更新|檢查更新|Check for updates|更新を確認|fluent_ui/components/update_center.py:78|
|立即更新|立即更新|Update now|今すぐ更新|fluent_ui/components/update_center.py:79|
|获取更新|取得更新|Get update|更新を取得|fluent_ui/components/update_center.py:79|
|更新失败，请重试或打开发布页|更新失敗，請重試或開啟發布頁|Update failed. Retry or open the release page.|更新に失敗しました。再試行するかリリースページを開いてください|fluent_ui/components/update_center.py:81|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-053 · 当前版本与版本点

入口/证据：fluent_ui/views/settings_center.py:657 / _page_about。触发：Settings关于页版本行。

已执行/真实结果：current_version读本地version.json，否则fallback；小点表示release存在。

副作用、取消及失败边界：红点/版本提示不是正在下载、已安装新版本。版本和公开品牌名原值，非用户资源。

翻译/刷新：设置行绑定；VersionLabel数值原字符串，不翻译。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|版本|版本|Version|バージョン|fluent_ui/views/settings_center.py:660|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-054 · 关于说明与资源信息

入口/证据：fluent_ui/views/about_view.py:21 / __init__。触发：Settings嵌入AboutInformation。

已执行/真实结果：展示本地软件定位、作者/项目参考/框架资源/许可证。

副作用、取消及失败边界：这些不是隐私数据上传告知；作者/框架/字体品牌不翻译。外链由QDesktopServices打开。

翻译/刷新：bind_text标题、语言信号refresh_texts许可证；固定品牌原值。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|本地表情管理|本機表情管理|Local emote manager|ローカルスタンプ管理|fluent_ui/views/about_view.py:28|
|作者|作者|Author|作者|fluent_ui/views/about_view.py:30|
|项目参考与相关工具|專案參考與相關工具|Project references and tools|参考プロジェクトと関連ツール|fluent_ui/views/about_view.py:41|
|字体、图标与界面资源|字型、圖示與介面資源|Fonts, icons and interface resources|フォント・アイコン・UI素材|fluent_ui/views/about_view.py:42|
|框架与许可证|框架與授權條款|Framework and license|フレームワークとライセンス|fluent_ui/views/about_view.py:43|
|表情版权归各自作者所有|表情版權歸各自作者所有|Emotes belong to their respective authors|各スタンプの権利はそれぞれの作者に帰属します|fluent_ui/views/about_view.py:64|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-055 · 关于外部链接

入口/证据：fluent_ui/views/about_view.py:57 / open_link。触发：作者按钮/项目链接/许可证点击。

已执行/真实结果：打开系统浏览器；AUTHOR_LINKS指向GitHub/X/B站公开作者页，SOURCES为Suzu/NekoriSoftframe/QQFavoriteExtract，许可证为仓库LICENSE。

副作用、取消及失败边界：Tooltip是公开固定URL或品牌名；本轮不访问网页，不确认链接现在是否存活或页面内容。不是向浏览器传私人资源。

翻译/刷新：无四语言源键，品牌/URL四语言相同。

动态/不存在的显示字段：AUTHOR_LINKS / SOURCES及GPL-3.0链接常量；label/toolTip原值，refresh_texts对HTML属性escape。

四语言内容：均为上述动态原值/数值结构，或该字段根本未显示；无对应静态翻译键，不填补不存在译文。

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-056 · 查看日志失败

入口/证据：fluent_ui/views/settings_center.py:690 / _open_logs。触发：install诊断目录返回None或QDesktopServices打开失败。

已执行/真实结果：尝试打开本地目录。

副作用、取消及失败边界：仅打开目录，不生成ZIP或上传；无法打开不代表日志已经丢失。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|无法打开日志目录|無法開啟日誌目錄|Cannot open the log folder|ログフォルダーを開けません|fluent_ui/views/settings_center.py:696|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-057 · 诊断导出说明

入口/证据：fluent_ui/views/settings_center.py:657 / _page_about。触发：现有关于诊断行。

已执行/真实结果：主动选ZIP目标，打包有限日志与environment.json及内存近期上下文。

副作用、取消及失败边界：此前TPB-209/210按钮名不重采；本条只补导出内容事实。不是自动上传或整库备份。

翻译/刷新：ActionRow标题/副描述绑定。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|诊断资料|診斷資料|Diagnostics|診断情報|fluent_ui/views/settings_center.py:674|
|查看本地日志，或导出脱敏日志与版本环境；不包含表情资源及应用配置。|查看本機日誌，或匯出已去識別化的日誌與版本環境；不包含表情資源及應用程式設定。|Open local logs or export redacted logs and version information; excludes emotes and app settings.|ローカルログの表示、または個人情報を除去したログと実行環境の書き出し。表情画像や設定は含みません。|fluent_ui/views/settings_center.py:674|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-058 · 诊断导出进行中

入口/证据：fluent_ui/views/settings_center.py:698 / _export_diagnostics。触发：用户选目标后cancellable run_exchange_task。

已执行/真实结果：列内部已管理日志，最多3 Python+2 native；每份最多512KiB，写前redact。

副作用、取消及失败边界：ZIP另有版本/Python/Qt/OS/build/machine、runtime_context环境及最多64近期摘要；不读图片/数据库/配置原文，不主动联网。

翻译/刷新：导出标题t；写入日志消息在services.diagnostic_export事件时t。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|导出诊断资料|匯出診斷資料|Export diagnostics|診断情報を書き出す|fluent_ui/views/settings_center.py:703|
|写入脱敏诊断日志|寫入已去識別化的診斷日誌|Writing redacted diagnostic logs|個人情報を除去した診断ログを書き込み中|services/diagnostic_export.py:58|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-059 · 诊断导出成功

入口/证据：fluent_ui/views/settings_center.py:698 / _export_diagnostics。触发：staged_export_path成功发布。

已执行/真实结果：用户所选ZIP已生成，显示路径。

副作用、取消及失败边界：0日志也可生成environment.json；成功不是日志覆盖所有崩溃。用户手动导出的ZIP不纳内部自动清理，需自行发送给开发者。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|诊断导出完成|診斷匯出完成|Diagnostics exported|診断情報を書き出しました|fluent_ui/views/settings_center.py:710|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-060 · 诊断导出取消

入口/证据：fluent_ui/views/settings_center.py:698 / _export_diagnostics。触发：取消文件选择或导出协作检查抛ExportCancelled。

已执行/真实结果：选择取消未执行；中途取消清.part不替换旧目标。

副作用、取消及失败边界：不删内部日志/已完成数据，也不清理以前用户ZIP；取消临界点由staged末次检查控制。

翻译/刷新：事件/构造时t精确查键；除明确bind_text/translated处，不保证已显示状态随语言切换即时更新。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|诊断导出已取消|已取消診斷匯出|Diagnostic export cancelled|診断情報の書き出しをキャンセルしました|fluent_ui/views/settings_center.py:706|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

### TPB4-061 · 诊断导出失败

入口/证据：fluent_ui/views/settings_center.py:698 / _export_diagnostics。触发：日志目录链接校验、读取、ZIP写入或目标IO异常。

已执行/真实结果：不宣布文件成功，异常进show_error详情。

副作用、取消及失败边界：旧目标在原子发布前保持；可能已建父目录，但不新增资源数据。

翻译/刷新：标题t，详情原异常，不翻译成另一个概括。

|中文源文|zh_TW当前值|en当前值|ja当前值|字面量位置|
|---|---|---|---|---|
|诊断导出失败|診斷匯出失敗|Diagnostic export failed|診断情報の書き出しに失敗しました|fluent_ui/views/settings_center.py:714|

未确认：本轮无实际任务或GUI；对话框原生覆盖交互、特殊数据、线程时序及已打开窗口外观不冒充实测。

## 3. 已证实的高优先级语义冲突

1. **原生导出完成数量可能超过实际资源文件数。** NekoriPackageService.export遍历manifest.resources，source.is_file为假不写、OSError仅print；末尾返回清单len。SettingsCenter仍“导出完成/表情N项”。这是缺失/读取失败条件下源码可达的不一致，不宣称实测库里已有这种文件。
2. **侧栏分类导出丢弃跳过信息。** export_node不接返回manifest，仍show_success；主分享导出则至少显示skipped数。主入口“不支持的文件”也将读取/PNG解码失败统一归作“不支持”，与服务的多种ExportSkip原因不一致。
3. **相似扫描取消正文与结果类型不一致。** worker_finished在worker.cancelled分支设置取消正文，却只按worker.error/旧failures决定finish outcome；无两者时传success。取消只保留特征缓存，不删资源；不能借此声称取消已清理所有痕迹。
4. **相似状态与删除数量绑定可能被语言事件重放初值。** presenter用translated建立初始status和删除所选（0）；后续setText不更新binding.source。对同一存活实例触发language_changed时，绑定会重放初始指令/0，与现有结果或selected集合不一致，直到后续更新。只作静态信号链确认，不冒充GUI复现。
5. **分享包导入重复“跳过”仍可能改变已有资源。** _import_into_library重复时仍合并成员/标签才skipped+=1；正文仅“新增…跳过…”。“跳过”没有明确承诺完全无改动，但需要指导AI结合真实副作用决定是否补充说明，不能将其误作无操作。
6. **分享导入警告与终态在两个入口不同。** Gallery入口附warnings但仍show_success；Settings兼容导入自定义operation只返回tuple，未把service.warnings送统一队列。图标跳过可能不在该入口的任务详情反映。不是所有警告都代表资源失败，不在本轮改变统计。
7. **“导出指定分类”范围是直接成员，不自动子树。** 主选择对话框只让选分类；服务按精确转义路径选择，子分类必须单独选择。这是需要交接的重要未充分表达范围，不由Codex决定改为递归导出。
8. **更新检查并没有冒充安装成功的确证。** 当前无新版本是“暂未发现可用更新”，无发行物另有文案；下载后是“更新已准备好”，重启需确认。没有发现“检查完成就已安装”文字。安装helper握手只表示可退出交接，不证明升级后新版本正常。
9. **Hover不存在尺寸/格式与读取失败文字。** 此为显示信息缺口/实际边界，不将不存在的字段假定为缺译或虚构译文；指导AI自行决定是否需要纳入最终文案合同。

### 无新增语义冲突依据的保护项

相似确认明确写“疑似相似不代表内容相同”；勾选不立即删除，确认才全局回收原件和关系，清空选择不改资源。通用导出停止的临时文件/旧目标保证由staged_export_path支持。分卷不拆完整图片、每卷实际校验大小、失败清本次新目录。诊断主动本地导出，不自动上传、不读取图片/Library/配置原文。这些不因风格偏好进入必改清单。

## 4. 缺译、绑定与占位符

本表静态t键按精确JSON核对：zh_TW 22、en 22、ja 22缺失；占位符已存在值失配0。缺键逐条在表内标明，数量不是全软件剩余缺译统计，不包括前三批已审定键的再次盘点。

- 相似工具取消/扫描结果由固定片段拼接；GroupPreview标题和卡片元数据多为构造/事件t，没有整个对话框统一language_changed重建。status/delete_button已有binding反而有初值覆盖问题，和普通未刷新需区分。
- Hover只翻译分类前缀/无分类，名字/路径/标签/OCR本就不译；名称和路径长时中间省略，OCR一行尾省略，Tag最多两行，不能把这些原值视为缺译。path正文相对、tooltip绝对，参数来源不同。
- 交换服务进度有未经过t的中文工作单元前缀/资源名。run_exchange_task可取消时直接str(message)作为阶段标题，非取消时也传原message，不因外层标题有译文就声称阶段全译。稳定前缀与动态资源名要分开，不能整串查译。
- SettingsCenter原生导出run_exchange_task传“正在导出 Nekori 表情合集”，标题经过t；service进度工作单元、异常原值不t。此类动态/服务内容本轮只记录机制，不穷举全部底层错误字符串。
- 更新_error notes.setPlainText(error)、发布说明notes.setPlainText，未知网络/磁盘/校验错误不再整串查译；没有新增第三批已修动态MISSING的同一模式证据。更新对话框内部固定labels未见统一语言信号重建；UpdateCheckButton/Badge则有语言刷新。
- 未发现本表已存在译文的格式占位符不匹配时，不据此推断四语言语义完全一致；语义取舍仍由指导AI决定。服务原始错误三语言原样不算字典缺失，但可能不适合普通用户，报告不代拟译文。

### 诊断导出内容与隐私边界

diagnostic_export只取内部已管理exceptions.log及2轮转、最多2 native日志，每份读取上限512KiB；日志文本经URL、认证头、键值凭据、绝对私人路径和长数字等规则脱敏，再写入ZIP。environment.json记录版本、Python/Qt/OS/machine、内部限制及runtime_context。运行环境摘要含构建号、窗口角色、DPI/材质状态、拖动汇总，近期事件最多64条、仅事件代码和获准标量，不采聊天/按键原文。

metadata直接来自受控环境结构，不再对整份metadata套文本redact；日志脱敏属于规则处理，不能保证任意非结构化私人字串全部匿名。导出不包含配置文件原文、资源图片或整个索引数据库，不读取用户Library作报告；系统架构machine不是机器名/显示器序列号。突然进程终止时内存未落盘上下文可能丢失，用户导出的ZIP不被14天内部清理管理。需要发送时由用户另行分享，不自动上传。说明应基于这些实际范围，由指导AI决定是否需要更详细告知，不修改采集范围。

## 5. 尚不能确认

- 本轮没有导入/导出/删除/清理/安装/上传、相似扫描、更新检查网络或GUI；静态分支和字典结果不等于实际发布包/系统操作验收。
- 系统原生文件保存对话框在具体Qt/Windows配置下的覆盖确认外观、磁盘权限/回收站容量、不可读文件与数据库错误交叉时序未实测。
- 不断电/崩溃条件下的完整回滚、helper安装后的版本与失败回退不由当前更新对话框文字证明；本轮不运行安装器，不改更新算法。
- 同一存活窗口的语言信号链可以源码确认；实际用户导航是否销毁重建窗口、各DPI下截断/长文布局、失活与激活的显示时序没有实测。
- 特殊导入包格式或源引用的全部错误不穷举，仍以既有验证机制为准。导入和更新详细错误可原语言显示，不能声称所有系统异常均四语言。
- 真正可读性、是否需要补充副作用/范围、四语言表达强弱与最终文案均交指导AI判断。本文不提出替换方案，也不暗自修复业务。

## 6. 不再继续调查的明确边界

前三批锁定映射、QQ/TG/OCR任务反馈、集中重复处理/自定义operation恢复合同只交叉引用，不重复采集。Suzu原始库迁移不属于通用资源交换本轮展开范围；仅解释当前分享包和原生包。相似图片不增加自动保留/自动删除/移出分类功能。Hover不改解码、缓存、生命周期或视觉；更新不改网络、安装器；诊断不改采集/留存/脱敏范围。

W01七处原工作树修改保留、W02暂停、W03不启用；正式版、真实Library、固定Demo及Suzu数据未操作。仅报告与必要记录，不改文案/JSON/测试/UI/业务，不Push/打包/发布。提交后停止，等待指导AI最后一组正式四语言映射。
