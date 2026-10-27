# TP-B 第三批：工具任务反馈事实补采

## 实施状态附记（2026-10-27）

本报告主体固定为76a62da调查快照，不覆盖旧表及原冲突。正式第三批源码 **0680659** 已按负责人映射落实19个源键、TG独立导出三终态、OCR等待来源/计数、批量ZIP汇总、QQ真实终态日志/命名句，并修正已明确动态详情二次查译入口。旧表中的相应文字/缺译不能再当作当前实现结论。

31个字段/124语言值（OCR计数en/ja复用旧值）；38项不同用例、Win11四语言深浅16组批量对话框及8组OCR控件布局、独立启动冒烟通过，仍待人工。未真实运行工具任务/网络，不改下载/入库/OCR/去重/恢复规则。原报告归因中的故障条件仅在本批显示责任层修复，不宣称所有动态第三方错误已翻译。详细边界和几何见 [TOOLTIP_REVIEW.md](TOOLTIP_REVIEW.md) 顶部；锁定文本及绑定在tests/fixtures/tpb_batch3_copy.json。TP-B整体未标完成，不自动开始下一批。

基线：**3c6e214 / dev/post-0.2.1**，2026-10-27，#62/#37。只读源码/AST/四语言JSON；没有运行任何工具任务、联网、客户端、导入、导出、删除、OCR或GUI。本报告不包含替换措辞、翻译创作或业务修改，交指导AI制定第三批正式映射。

第一、二批锁定。TPB-220、222、225、226、229仅引用TOOLTIP_REVIEW.md和第一批fixture，不重复调查既有导出事实；TPB-211～219设置名称和说明不重抄，OCR仅补运行反馈。原TPB_COPY_FACTS.md保持历史基线。

## 一、摘要

本轮106条记录：QQ 44、Telegram 36、OCR 26。独立静态源键133个；缺失精确键：zh_TW 19、en 19、ja 19，共57个键×语言单元。数量只涵盖本表，不穷举动态异常。每条可有同一次反馈的标题和正文，不合成运行时键；互斥终态各自登记。相同共用队列文字只在QQ组记录，Telegram交叉使用。

### 当前可见入口与共同显示机制

- QQ：ImportBench来源目录、账号、分类、扫描，预览/详细信息、入库选中/全部、导出菜单/导出设置、帮助与日志。Telegram：ImportBench链接查询、连接设置、批量打包、预览、入库、导出菜单。build_import_tool隐藏旧topBar/configCard/actionBar；重挂载的输入和原按钮仍有效，不把隐藏旧折叠/高级配置文案算当前常驻体验。
- StateToolTipManager是任务反馈门面，不是TP-A悬停提示。它把show/update/finish交FeedbackHost/CaptionFeedback；fail的主可见正文为“操作未完成，请查看详情后重试。”，原错误存详情。clean_message去掉前导符号，下表保留源码原文，不假装这些符号一定原样显示。
- t精确查键，zh直显源文；三语言缺失显示[MISSING: 原键]，不是中文回退。普通t事件文本不是全部绑定式实时刷新。bind_text/translated具语言信号；批量表格、日志和已格式化状态需分开看。t(...).format保留模板信息，但再次t普通完整动态字符串仍按完整键查找。
- 下表原文与三语言均直接提取当前文件；缺失不补译。参数仅说明来源，不输出真实账号、文件名、路径、Token或原始日志。非中文字段列为“缺失”时真实t结果见共同机制。

### QQ真实执行链

QQDiscovery只枚举本地目录、读本地昵称缓存；扫描也本地处理。扫描完成只获得路径，再分批预览，不入库。导出确认后才get_display_name，缓存过期/缺失可能向uapis.cn发送QQ号码，3秒超时、24小时缓存，失败用号码，不上传图片。当前帮助与导出确认有同一隐私hint。导出QQExportWorker复制独立文件；同名后缀，APNG/Marketface按现有转换/提取，不是ZIP资源包。

入库走import_files_with_progress→ImportQueue.submit(operation)→QQImportWorker.run→save_file/add_image_to_category，创建/复用QQ_账号_分类。旧_on_import_progress/_on_import_finished没有绑定到当前operation的UI，不能用旧“合并去重”气泡冒充当前反馈。当前统一任务由图库_sync_background_tasks消费。

### Telegram真实执行链

查询获取包元数据后再懒加载预览，不等于全包下载。独立导出使用DownloadPackThread/download_pack，仅文件/可选ZIP，不入库。当前入库走ImportQueue(operation)→ImportPackThread，保存、分类关系均复用存储层与重复决策。

ImportPackThread下载获取失败计skipped_count，本地保存/分类失败另计fail_count；operation将两者放result.skipped，ImportThread._run_operation再累加到request.failed。主动重复跳过走context.skipped→request.skipped。最终通用反馈的“失败”不能仅据worker变量名解释为“跳过”；网络与本地原因要看详情。

批量TGBatchPackageDialog→BatchPackageWorker→TGPackageBatchRunner，解析/下载与有序入库/打包有界交错。批量类别名避免与库中已有分类或同批重名，ZIP也避重；不是单包ID复用分类的同一命名合同。ZIP成功存在才done，但可包含获取失败跳过项。

恢复仅默认凭据的官方明确401，锁内一次有界恢复；自定义Token不轮换，429/超时/DNS/代理故障不当成401。success仅验证凭据并继续原请求，后续仍可能失败。回调过滤旧worker、取消状态及当前恢复owner；入库通过stage传递。未实际运行取消时序。

### OCR真实执行链

仅ocr_auto启用且组件可用时自动识别新入库资源，不自动扫旧库。补充跳过已识别未变化项目、人工文字；重试筛failed。每项以revision/source验证后可靠提交。人工编辑manual=True、revision+1；自动/普通补充不覆盖人工，资源force覆盖需确认；重新识别全部仍保护人工内容。

停止增加generation、清未执行队列并中断进程，不撤销已提交文字。正常取消清检查点，强制全库重识别可用进程内resume_ids继续；持久中断/waiting_source用可靠清单resume未完成项，且overwrite=False，继续保护人工文字。QQ/TG operation则unsupported不能安全自动重放，不将“继续”都解释为重下全部。

组件安装先停止识别，临时解压/校验/启动检查后替换组件；成功立即ocr_auto=True，卸载立即关闭自动识别并保留文字/资源。失败不自动回滚已经保存的识别成果。commit_ocr失败状态保留旧text，empty是正常空结果，与failed不同。

## 二、详细事实
所有边界均为静态确认，未执行对应操作；没有实机/人工验收含义。位置是当前函数和字面量行号，同键可在多处调用。

## QQ

### TPB3-001 · 读取账号

- 入口/源码：fluent_ui/views/qq_scan_view.py:995 / populateUserComboBox。
- 条件：打开工具或重新选目录后启动QQDiscovery。
- 已完成步骤：尚未完成账号读取。
- 已写入/不能撤销/限制：本地枚举/本地缓存；不查询网络昵称；有效路径会写qq_data_path。
- 用户下一步：等待读取或重新选目录。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在读取 QQ 账号…|正在讀取 QQ 帳號…|Reading QQ accounts…|QQアカウントを読み込み中…|fluent_ui/views/qq_scan_view.py:1003|

### TPB3-002 · 目录缺失

- 入口/源码：fluent_ui/views/qq_scan_view.py:1007 / _discovery_ready。
- 条件：users结果无root。
- 已完成步骤：未找到根目录。
- 已写入/不能撤销/限制：不扫描/导入、不创建QQ数据目录。
- 用户下一步：手动选择数据目录。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|未找到 QQ 数据目录，请手动选择。|找不到 QQ 資料目錄，請手動選擇。|QQ data folder not found. Select it manually.|QQのデータフォルダーが見つかりません。手動で選択してください。|fluent_ui/views/qq_scan_view.py:1029|

### TPB3-003 · 账号为空

- 入口/源码：fluent_ui/views/qq_scan_view.py:1007 / _discovery_ready。
- 条件：users无items，写工具日志。
- 已完成步骤：本地枚举结束。
- 已写入/不能撤销/限制：不向QQ服务器查账号。
- 用户下一步：选择正确本地目录。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|未发现 QQ 账号，请选择包含数字账号文件夹的 Tencent Files 目录。|未發現 QQ 帳號，請選擇包含數字帳號資料夾的 Tencent Files 目錄。|No QQ accounts found. Select the Tencent Files folder containing numeric account folders.|QQアカウントが見つかりません。数字のアカウントフォルダーを含むTencent Filesフォルダーを選択してください。|fluent_ui/views/qq_scan_view.py:1030|

### TPB3-004 · 读取数据异常

- 入口/源码：fluent_ui/views/qq_scan_view.py:1007 / _discovery_ready。
- 条件：discovery结果有error。
- 已完成步骤：本次账号/分类读取失败。
- 已写入/不能撤销/限制：日志固定说明，不是所有系统异常的翻译。
- 用户下一步：重新选择目录。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|无法读取 QQ 数据，请重新选择目录。|無法讀取 QQ 資料，請重新選擇目錄。|Unable to read QQ data. Please select the folder again.|QQデータを読み込めません。フォルダーを選択し直してください。|fluent_ui/views/qq_scan_view.py:1027|

### TPB3-005 · 账号未选

- 入口/源码：fluent_ui/views/qq_scan_view.py:1189 / scanEmojis。
- 条件：扫描/导入/导出入口账号为空。
- 已完成步骤：尚未启动后续操作。
- 已写入/不能撤销/限制：无当前操作写入；notify与日志共用。
- 用户下一步：选择账号。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|❌ 你还没有选择QQ号呢，请先选择一个QQ号！|❌ 尚未選擇 QQ 號，請先選擇一個 QQ 號！|❌ No QQ account selected. Please select an account first!|❌ QQアカウントが選択されていません。先に選択してください！|fluent_ui/views/qq_scan_view.py:1192|

### TPB3-006 · 分类未选

- 入口/源码：fluent_ui/views/qq_scan_view.py:1189 / scanEmojis。
- 条件：扫描/导入/导出入口folder为空。
- 已完成步骤：尚未执行。
- 已写入/不能撤销/限制：无当前操作写入。
- 用户下一步：选择分类。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|❌ 你还没有选择表情分类呢，请先选择一个分类！|❌ 尚未選擇表情分類，請先選擇一個分類！|❌ No emote category selected. Please select one first!|❌ スタンプカテゴリが選択されていません。先に選択してください！|fluent_ui/views/qq_scan_view.py:1199|

### TPB3-007 · 本地分类目录缺失

- 入口/源码：fluent_ui/views/qq_scan_view.py:1189 / scanEmojis。
- 条件：target_path为空或不存在。
- 已完成步骤：解析了账号/分类，未扫描。
- 已写入/不能撤销/限制：notify warning，不创建来源目录。
- 用户下一步：检查数据目录或切换分类。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|未找到该分类的本地目录，可能是该账号在本地未生成对应分类，或者路径不正确。|找不到此分類的本機資料夾，可能是帳號尚未在本機建立該分類，或路徑不正確。|The local category directory was not found. The category may not exist locally or the path may be incorrect.|カテゴリのローカルディレクトリが見つかりません。ローカルに作成されていないか、パスが正しくない可能性があります。|fluent_ui/views/qq_scan_view.py:1213|

### TPB3-008 · 扫描开始

- 入口/源码：fluent_ui/views/qq_scan_view.py:1189 / scanEmojis。
- 条件：来源有效，启动QQScanWorker。
- 已完成步骤：已清旧预览、记录上下文。
- 已写入/不能撤销/限制：仅本地筛选，尚未入库；folder来自当前分类键。
- 用户下一步：等待/任务取消。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在扫描表情合集...|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1232|
|正在扫描分类 [{folder}]...|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1232|

### TPB3-009 · 扫描空结果

- 入口/源码：fluent_ui/views/qq_scan_view.py:1251 / _on_scan_finished。
- 条件：非取消返回0路径。
- 已完成步骤：扫描结束。
- 已写入/不能撤销/限制：finish默认success不表示找到图片或入库。
- 用户下一步：换分类/目录重扫。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|扫描完成|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1269|
|未筛选出任何有效的表情合集表情|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1265|

### TPB3-010 · 扫描有结果

- 入口/源码：fluent_ui/views/qq_scan_view.py:1251 / _on_scan_finished。
- 条件：非取消返回有效路径。
- 已完成步骤：路径收集完成，开始分批预览。
- 已写入/不能撤销/限制：count不等于缩略图已全加载，更不等于入库数。
- 用户下一步：选中已加载项或全部导入/导出。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|扫描完成|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1269|
|共发现 {count} 个有效表情|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1269|

### TPB3-011 · 扫描停止

- 入口/源码：fluent_ui/views/qq_scan_view.py:1251 / _on_scan_finished。
- 条件：当前代次worker.was_cancelled。
- 已完成步骤：不应用返回列表。
- 已写入/不能撤销/限制：开始扫描时旧预览已清；不回滚历史入库。
- 用户下一步：重新扫描。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|扫描已停止|掃描已停止|Scan stopped|スキャンを停止しました|fluent_ui/views/qq_scan_view.py:1257|
|未应用本次扫描结果。|未套用本次掃描結果。|The results of this scan were not applied.|今回のスキャン結果は適用されていません。|fluent_ui/views/qq_scan_view.py:1257|

### TPB3-012 · 扫描失败

- 入口/源码：fluent_ui/views/qq_scan_view.py:1243 / _on_scan_failed。
- 条件：有效代次failed信号。
- 已完成步骤：未完成扫描。
- 已写入/不能撤销/限制：原str(error)放fail详情，主正文改通用错误摘要。
- 用户下一步：查详情、检查目录后重试。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|扫描失败|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1248|

### TPB3-013 · 预览缺失文件

- 入口/源码：fluent_ui/views/qq_scan_view.py:1107 / onItemSelectionChanged。
- 条件：选中项文件不存在。
- 已完成步骤：选择已发生。
- 已写入/不能撤销/限制：不删除库记录。
- 用户下一步：换项/重新扫描。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|文件不存在|檔案不存在|File does not exist|ファイルが存在しません|fluent_ui/views/qq_scan_view.py:1128|

### TPB3-014 · 预览元数据异常

- 入口/源码：fluent_ui/views/qq_scan_view.py:1107 / onItemSelectionChanged。
- 条件：格式/大小信息读取异常。
- 已完成步骤：未得到完整信息。
- 已写入/不能撤销/限制：error是本地异常，不枚举或编造其译文。
- 用户下一步：检查来源/换项。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|获取信息失败: {error}|取得資訊失敗：{error}|Failed to get information: {error}|情報の取得に失敗しました：{error}|fluent_ui/views/qq_scan_view.py:1155|

### TPB3-015 · 预览解码失败

- 入口/源码：fluent_ui/views/qq_scan_view.py:1107 / onItemSelectionChanged。
- 条件：QMovie/图片加载失败或预览异常。
- 已完成步骤：该项预览未成功。
- 已写入/不能撤销/限制：不是导入失败，也没有删除原件。
- 用户下一步：换项或重新扫描。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|表情加载失败|表情載入失敗|Failed to load emote|スタンプの読み込みに失敗しました|fluent_ui/views/qq_scan_view.py:1185|
|预览失败: {error}|預覽失敗：{error}|Preview failed: {error}|プレビューに失敗しました：{error}|fluent_ui/views/qq_scan_view.py:1187|

### TPB3-016 · 缺少输出目录

- 入口/源码：fluent_ui/views/qq_scan_view.py:1361 / exportSelected。
- 条件：导出前savePath为空。
- 已完成步骤：未开始复制。
- 已写入/不能撤销/限制：无新输出。
- 用户下一步：导出设置选择路径。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|❌ 你还没有选择保存路径呢，请先选择保存路径！|❌ 尚未選擇儲存路徑，請先選擇儲存路徑！|❌ No save path selected. Please select one first!|❌ 保存先が選択されていません。先に選択してください！|fluent_ui/views/qq_scan_view.py:1370|

### TPB3-017 · 未选导出项

- 入口/源码：fluent_ui/views/qq_scan_view.py:1361 / exportSelected。
- 条件：selectedItems为空。
- 已完成步骤：未复制。
- 已写入/不能撤销/限制：全部导出不限制已加载选择集。
- 用户下一步：选项或使用全部导出。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|请先在预览区选中表情后再导出！|請先在預覽區選取表情後再匯出！|Please select emotes in the preview area before exporting!|プレビューでスタンプを選択してからエクスポートしてください！|fluent_ui/views/qq_scan_view.py:1386|

### TPB3-018 · 选中导出确认

- 入口/源码：fluent_ui/views/qq_scan_view.py:1361 / exportSelected。
- 条件：输入与选择有效后弹确认。
- 已完成步骤：仅验证输入。
- 已写入/不能撤销/限制：确认后才查询昵称及复制；此处取消无本次输出。
- 用户下一步：确认/取消。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|确认导出选中|確認匯出所選|Confirm Export Selected|選択項目のエクスポートを確認|fluent_ui/views/qq_scan_view.py:1389|
|确定导出当前选中的 {count} 个表情？|要匯出目前選取的 {count} 個表情嗎？|Export the {count} selected emotes?|選択したスタンプ {count} 件をエクスポートしますか？|fluent_ui/views/qq_scan_view.py:1389|

### TPB3-019 · 全部导出确认

- 入口/源码：fluent_ui/views/qq_scan_view.py:1401 / exportAll。
- 条件：有完整路径列表；没有时先本地scan_emojis。
- 已完成步骤：收集范围不局限已加载缩略图。
- 已写入/不能撤销/限制：确认才复制，不入库。
- 用户下一步：确认/取消。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|确认导出全部|確認匯出全部|Confirm Export All|すべてエクスポートを確認|fluent_ui/views/qq_scan_view.py:1434|
|当前不管界面是否完全加载，将直接导出扫描到的该分类下所有 {count} 个表情？|不論介面是否完全載入，都要匯出此分類掃描到的全部 {count} 個表情嗎？|Export all {count} scanned emotes in this category, regardless of preview loading?|プレビューの読み込み状況に関係なく、このカテゴリのスタンプ {count} 件をすべてエクスポートしますか？|fluent_ui/views/qq_scan_view.py:1435|

### TPB3-020 · 昵称隐私告知

- 入口/源码：fluent_ui/views/qq_scan_view.py:1361 / exportSelected。
- 条件：导出确认hint和当前帮助入口。
- 已完成步骤：确认前未发本次昵称请求。
- 已写入/不能撤销/限制：确认后缓存缺失/过期才向uapis.cn发送所选QQ号码，24小时本地缓存；失败用账号命名。扫描/发现/导入不查询。
- 用户下一步：取消或继续导出。
- 翻译绑定/刷新：t(NICKNAME_NOTICE)；帮助拼接同键。服务证据services/qq_extractor.py:get_user_nickname/get_display_name；未读取真实缓存或联网。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|确认导出后，昵称缓存过期或缺失时会向第三方 uapis.cn 发送所选 QQ 号码，用于获取昵称并生成导出文件夹名；结果在本地缓存 24 小时。账号发现、扫描和导入不发起此查询。|確認匯出後，暱稱快取過期或缺少時會向第三方 uapis.cn 傳送所選 QQ 號碼，用於取得暱稱並產生匯出資料夾名稱；結果在本機快取 24 小時。帳號探索、掃描和匯入不會發起此查詢。|After you confirm export, if the nickname cache is missing or expired, the selected QQ number is sent to the third-party service uapis.cn to obtain a nickname for the export folder name. Results are cached locally for 24 hours. Account discovery, scanning and importing do not make this request.|エクスポートを確認した後、ニックネームのキャッシュがないか期限切れの場合、選択したQQ番号を第三者サービス uapis.cn に送信し、出力フォルダー名に使うニックネームを取得します。結果はローカルに24時間キャッシュされます。アカウントの検出、スキャン、インポートではこの問い合わせを行いません。|fluent_ui/views/qq_scan_view.py:35|

### TPB3-021 · 导出开始

- 入口/源码：fluent_ui/views/qq_scan_view.py:1287 / copy_files_with_progress。
- 条件：启动QQExportWorker。
- 已完成步骤：目标目录可能已创建。
- 已写入/不能撤销/限制：独立文件输出；Marketface取GIF，APNG尝试转GIF失败回落PNG；同名加后缀。
- 用户下一步：等待/取消。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在导出表情...|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1296|
|准备导出 {total} 个表情...|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1297|

### TPB3-022 · 导出进度

- 入口/源码：fluent_ui/views/qq_scan_view.py:1314 / _on_export_progress。
- 条件：成功复制后progress，done=copied_count。
- 已完成步骤：已有done个输出文件。
- 已写入/不能撤销/限制：缺失/失败项不增加done，不是已遍历数。
- 用户下一步：等待/取消、查日志。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在处理: {done}/{total} ({percent}%)|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1322|

### TPB3-023 · 导出全成功

- 入口/源码：fluent_ui/views/qq_scan_view.py:1325 / _on_export_finished。
- 条件：copied_count==total且未取消
- 已完成步骤：复制循环结束。
- 已写入/不能撤销/限制：成功文件保留，failed=total-copied_count含源缺失；都会尝试打开输出目录。日志仍无条件写成功导出。
- 用户下一步：看目录/日志，必要时重试。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导出完成|匯出完成|Export Complete|エクスポート完了|fluent_ui/views/qq_scan_view.py:1340|
|已导出 {done} 张表情，失败 {failed} 张|已匯出 {done} 張表情，失敗 {failed} 張|Exported {done} emotes; {failed} failed|エクスポート {done} 件、失敗 {failed} 件|fluent_ui/views/qq_scan_view.py:1341|

### TPB3-024 · 导出部分完成

- 入口/源码：fluent_ui/views/qq_scan_view.py:1325 / _on_export_finished。
- 条件：0<copied_count<total且未取消
- 已完成步骤：复制循环结束。
- 已写入/不能撤销/限制：成功文件保留，failed=total-copied_count含源缺失；都会尝试打开输出目录。日志仍无条件写成功导出。
- 用户下一步：看目录/日志，必要时重试。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导出部分完成|匯出部分完成|Export partially completed|エクスポートが一部完了しました|fluent_ui/views/qq_scan_view.py:1340|
|已导出 {done} 张表情，失败 {failed} 张|已匯出 {done} 張表情，失敗 {failed} 張|Exported {done} emotes; {failed} failed|エクスポート {done} 件、失敗 {failed} 件|fluent_ui/views/qq_scan_view.py:1341|

### TPB3-025 · 导出零成功

- 入口/源码：fluent_ui/views/qq_scan_view.py:1325 / _on_export_finished。
- 条件：copied_count==0<total且未取消
- 已完成步骤：复制循环结束。
- 已写入/不能撤销/限制：成功文件保留，failed=total-copied_count含源缺失；都会尝试打开输出目录。日志仍无条件写成功导出。
- 用户下一步：看目录/日志，必要时重试。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导出失败|導出失敗|Export failed|書き出しに失敗しました|fluent_ui/views/qq_scan_view.py:1340|
|已导出 {done} 张表情，失败 {failed} 张|已匯出 {done} 張表情，失敗 {failed} 張|Exported {done} emotes; {failed} failed|エクスポート {done} 件、失敗 {failed} 件|fluent_ui/views/qq_scan_view.py:1341|

### TPB3-026 · 导出停止

- 入口/源码：fluent_ui/views/qq_scan_view.py:1325 / _on_export_finished。
- 条件：was_cancelled=True。
- 已完成步骤：已复制count项。
- 已写入/不能撤销/限制：不回滚输出，此分支不自动开目录。
- 用户下一步：手动查看目录或重新导出。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导出已中断|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1333|
|已由用户手动中断，已导出 {count} 个表情文件|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1334|

### TPB3-027 · worker异常

- 入口/源码：fluent_ui/views/qq_scan_view.py:1522 / _on_worker_failed。
- 条件：例如创建目录failed。
- 已完成步骤：可能有部分输出。
- 已写入/不能撤销/限制：原error详情，无全量回滚保证。
- 用户下一步：查详情后排除本地问题。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|操作出错|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1526|

### TPB3-028 · 选中导入确认

- 入口/源码：fluent_ui/views/qq_scan_view.py:1528 / importSelected。
- 条件：有效预览选中后。
- 已完成步骤：尚未提交当前任务。
- 已写入/不能撤销/限制：确认后统一ImportQueue，创建/复用QQ_账号_分类。
- 用户下一步：确认/取消。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|确认导入选中|確認匯入所選|Confirm Import Selected|選択項目のインポートを確認|fluent_ui/views/qq_scan_view.py:1550|
|确定将当前选中的 {count} 个表情导入到表情库？（会经过自动清洗和去重过滤）|要將目前選取的 {count} 個表情匯入表情庫嗎？（將自動清理並去重）|Import the {count} selected emotes? They will be cleaned and deduplicated automatically.|選択したスタンプ {count} 件をインポートしますか？自動的に整理・重複排除されます。|fluent_ui/views/qq_scan_view.py:1551|

### TPB3-029 · 全部导入确认

- 入口/源码：fluent_ui/views/qq_scan_view.py:1561 / importAll。
- 条件：全部本地文件路径就绪。
- 已完成步骤：非仅已加载预览。
- 已写入/不能撤销/限制：确认后保存并归类，不查询昵称。
- 用户下一步：确认/取消。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|确认导入全部|確認匯入全部|Confirm Import All|すべてインポートを確認|fluent_ui/views/qq_scan_view.py:1588|
|当前不管界面是否完全加载，将直接导入扫描到的该分类下所有 {count} 个表情到表情库？（自动清洗和去重）|不論介面是否完全載入，都要將此分類掃描到的全部 {count} 個表情匯入表情庫嗎？（將自動清理並去重）|Import all {count} scanned emotes in this category? They will be cleaned and deduplicated automatically.|このカテゴリのスタンプ {count} 件をすべてインポートしますか？自動的に整理・重複排除されます。|fluent_ui/views/qq_scan_view.py:1589|

### TPB3-030 · 未选导入项

- 入口/源码：fluent_ui/views/qq_scan_view.py:1528 / importSelected。
- 条件：selectedItems为空。
- 已完成步骤：未排队。
- 已写入/不能撤销/限制：无当前入库写入。
- 用户下一步：选择项。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|请先在预览区选中表情后再导入！|請先在預覽區選取表情後再匯入！|Please select emotes in the preview area before importing!|プレビューでスタンプを選択してからインポートしてください！|fluent_ui/views/qq_scan_view.py:1547|

### TPB3-031 · 共用入库：waiting

- 入口/源码：fluent_ui/views/gallery_view.py:2876 / _sync_background_tasks。
- 条件：request.state=waiting
- 已完成步骤：waiting未处理；running逐项保存；finalizing可靠文件处理结束、files_finished更新投影。
- 已写入/不能撤销/限制：已可靠提交项不撤销；尚未最终完成。
- 用户下一步：等待/取消。
- 翻译绑定/刷新：ImportQueue.changed触发图库同步并t；QQ/TG入库共用此处，非旧_on_import_finished气泡。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|等待导入表情|等待匯入表情|Waiting to import emotes|スタンプのインポート待機中|fluent_ui/views/gallery_view.py:2883|

### TPB3-032 · 共用入库：running

- 入口/源码：fluent_ui/views/gallery_view.py:2876 / _sync_background_tasks。
- 条件：request.state=running
- 已完成步骤：waiting未处理；running逐项保存；finalizing可靠文件处理结束、files_finished更新投影。
- 已写入/不能撤销/限制：已可靠提交项不撤销；尚未最终完成。
- 用户下一步：等待/取消。
- 翻译绑定/刷新：ImportQueue.changed触发图库同步并t；QQ/TG入库共用此处，非旧_on_import_finished气泡。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在导入表情|正在匯入表情|Importing emotes|スタンプをインポート中|fluent_ui/views/gallery_view.py:2892|

### TPB3-033 · 共用入库：finalizing

- 入口/源码：fluent_ui/views/gallery_view.py:2876 / _sync_background_tasks。
- 条件：request.state=finalizing
- 已完成步骤：waiting未处理；running逐项保存；finalizing可靠文件处理结束、files_finished更新投影。
- 已写入/不能撤销/限制：已可靠提交项不撤销；尚未最终完成。
- 用户下一步：等待/取消。
- 翻译绑定/刷新：ImportQueue.changed触发图库同步并t；QQ/TG入库共用此处，非旧_on_import_finished气泡。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在更新图库|正在更新圖庫|Updating gallery|ギャラリーを更新中|fluent_ui/views/gallery_view.py:2891|

### TPB3-034 · 共用入库重复决策

- 入口/源码：fluent_ui/views/gallery_view.py:2876 / _sync_background_tasks。
- 条件：_show_batch置decision。
- 已完成步骤：可能已有非重复项保存并发files_finished。
- 已写入/不能撤销/限制：不会无提示覆盖；可在等待期间存在已写入结果。
- 用户下一步：使用集中重复决策。
- 翻译绑定/刷新：ImportQueue.changed触发图库同步并t；QQ/TG入库共用此处，非旧_on_import_finished气泡。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|等待处理重复表情（{count}）|等待處理重複表情（{count}）|Waiting for duplicate decisions ({count})|重複の処理待ち（{count}）|fluent_ui/views/gallery_view.py:2889|

### TPB3-035 · 共用重复决策按钮

- 入口/源码：fluent_ui/components/duplicate_dialog.py:72 / __init__。
- 条件：DuplicateBatchDialog显示。
- 已完成步骤：重复候选已建立。
- 已写入/不能撤销/限制：skip不新增；keep独立条目；reuse使用既有资源并继续分类关系。关闭把剩余choices置skip，不撤销先前结果。
- 用户下一步：逐项或全部应用，或跳过剩余。
- 翻译绑定/刷新：标题t，NekoriDialog按钮绑定；同一模块有多个__init__，实际定义见DuplicateBatchDialog。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|处理重复表情|處理重複表情|Resolve duplicate emotes|重複表情を処理|fluent_ui/components/duplicate_dialog.py:73|
|跳过此项|略過此項|Skip this item|この項目をスキップ|fluent_ui/components/duplicate_dialog.py:80|
|保留两者|保留兩者|Keep both|両方を保持|fluent_ui/components/duplicate_dialog.py:81|
|使用已存在文件导入|使用已存在檔案匯入|Use existing file|既存のファイルを使用|fluent_ui/components/duplicate_dialog.py:82|
|跳过剩余重复项|略過剩餘重複項目|Skip remaining duplicates|残りの重複をスキップ|fluent_ui/components/duplicate_dialog.py:83|

### TPB3-036 · 共用入库：success

- 入口/源码：fluent_ui/views/gallery_view.py:2876 / _sync_background_tasks。
- 条件：completed且failed==0
- 已完成步骤：已完成单元可靠保存；全失败也可能创建空分类。
- 已写入/不能撤销/限制：取消不删除资源/关系；成功含重复/主动跳过；网络获取失败与本地失败共计failed。
- 用户下一步：看图库与详情，必要时重新提供来源。
- 翻译绑定/刷新：ImportQueue.changed触发图库同步并t；QQ/TG入库共用此处，非旧_on_import_finished气泡。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导入处理完成|匯入處理完成|Import processing complete|インポート処理完了|fluent_ui/views/gallery_view.py:2897|
|新增 {saved} 张，已处理重复 {duplicates} 张，跳过 {skipped} 张，失败 {failed} 张|新增 {saved} 張，已處理重複 {duplicates} 張，略過 {skipped} 張，失敗 {failed} 張|Added {saved}, handled {duplicates} duplicates, skipped {skipped}, failed {failed} emotes|追加 {saved} 件、重複処理 {duplicates} 件、スキップ {skipped} 件、失敗 {failed} 件|fluent_ui/views/gallery_view.py:2881|

### TPB3-037 · 共用入库：partial

- 入口/源码：fluent_ui/views/gallery_view.py:2876 / _sync_background_tasks。
- 条件：completed且failed>0
- 已完成步骤：已完成单元可靠保存；全失败也可能创建空分类。
- 已写入/不能撤销/限制：取消不删除资源/关系；成功含重复/主动跳过；网络获取失败与本地失败共计failed。
- 用户下一步：看图库与详情，必要时重新提供来源。
- 翻译绑定/刷新：ImportQueue.changed触发图库同步并t；QQ/TG入库共用此处，非旧_on_import_finished气泡。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导入部分完成|匯入部分完成|Import partially completed|インポートが一部完了しました|fluent_ui/views/gallery_view.py:2897|
|新增 {saved} 张，已处理重复 {duplicates} 张，跳过 {skipped} 张，失败 {failed} 张|新增 {saved} 張，已處理重複 {duplicates} 張，略過 {skipped} 張，失敗 {failed} 張|Added {saved}, handled {duplicates} duplicates, skipped {skipped}, failed {failed} emotes|追加 {saved} 件、重複処理 {duplicates} 件、スキップ {skipped} 件、失敗 {failed} 件|fluent_ui/views/gallery_view.py:2881|

### TPB3-038 · 共用入库：failed

- 入口/源码：fluent_ui/views/gallery_view.py:2876 / _sync_background_tasks。
- 条件：failed>0且无saved/duplicates，terminal failed
- 已完成步骤：已完成单元可靠保存；全失败也可能创建空分类。
- 已写入/不能撤销/限制：取消不删除资源/关系；成功含重复/主动跳过；网络获取失败与本地失败共计failed。
- 用户下一步：看图库与详情，必要时重新提供来源。
- 翻译绑定/刷新：ImportQueue.changed触发图库同步并t；QQ/TG入库共用此处，非旧_on_import_finished气泡。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导入失败|導入失敗|Import failed|取り込みに失敗しました|fluent_ui/views/gallery_view.py:3059|
|新增 {saved} 张，已处理重复 {duplicates} 张，跳过 {skipped} 张，失败 {failed} 张|新增 {saved} 張，已處理重複 {duplicates} 張，略過 {skipped} 張，失敗 {failed} 張|Added {saved}, handled {duplicates} duplicates, skipped {skipped}, failed {failed} emotes|追加 {saved} 件、重複処理 {duplicates} 件、スキップ {skipped} 件、失敗 {failed} 件|fluent_ui/views/gallery_view.py:2881|

### TPB3-039 · 共用入库：cancelled

- 入口/源码：fluent_ui/views/gallery_view.py:2876 / _sync_background_tasks。
- 条件：cancelled，可能worker正在协作收尾
- 已完成步骤：已完成单元可靠保存；全失败也可能创建空分类。
- 已写入/不能撤销/限制：取消不删除资源/关系；成功含重复/主动跳过；网络获取失败与本地失败共计failed。
- 用户下一步：看图库与详情，必要时重新提供来源。
- 翻译绑定/刷新：ImportQueue.changed触发图库同步并t；QQ/TG入库共用此处，非旧_on_import_finished气泡。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导入处理已停止|匯入處理已停止|Import processing stopped|インポート処理を停止しました|fluent_ui/views/gallery_view.py:2897|
|新增 {saved} 张，已处理重复 {duplicates} 张，跳过 {skipped} 张，失败 {failed} 张|新增 {saved} 張，已處理重複 {duplicates} 張，略過 {skipped} 張，失敗 {failed} 張|Added {saved}, handled {duplicates} duplicates, skipped {skipped}, failed {failed} emotes|追加 {saved} 件、重複処理 {duplicates} 件、スキップ {skipped} 件、失敗 {failed} 件|fluent_ui/views/gallery_view.py:2881|

### TPB3-040 · 共用恢复选项

- 入口/源码：fluent_ui/views/gallery_view.py:2936 / _recovery_options。
- 条件：interrupted/waiting_source/OCR恢复入口。
- 已完成步骤：已有单元不需重做。
- 已写入/不能撤销/限制：QQ/TG自定义operation标unsupported，不能安全重放；放弃只清任务凭据，不删成果。
- 用户下一步：可靠清单才可继续，否则重新提供来源。
- 翻译绑定/刷新：构造时t；错误str(exc)再t可能缺精确键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|继续仅处理未完成部分；放弃不会删除已完成成果。|繼續僅處理未完成部分；放棄不會刪除已完成成果。|Continue processes only unfinished work. Abandoning keeps completed results.|再開すると未完了の処理のみ実行します。破棄しても完了した結果は削除されません。|fluent_ui/views/gallery_view.py:2941|
|查看恢复选项|檢視復原選項|Recovery options|復元オプション|fluent_ui/views/gallery_view.py:2918|
|继续任务|繼續工作|Continue task|タスクを再開|fluent_ui/views/gallery_view.py:2950|
|暂不继续|暫不繼續|Not now|後で再開|fluent_ui/views/gallery_view.py:2951|
|放弃任务|放棄工作|Abandon task|タスクを破棄|fluent_ui/views/gallery_view.py:2952|

### TPB3-041 · 扫描/导入全部来源为空

- 入口/源码：fluent_ui/views/qq_scan_view.py:1561 / importAll。
- 条件：全部导入/导出在需要时本地补扫后仍无路径。
- 已完成步骤：未提交队列/输出worker。
- 已写入/不能撤销/限制：notify使用共同摘要；日志另有导入/导出的具体说明。
- 用户下一步：检查分类与本地目录后重扫。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|该分类下未发现任何有效的表情文件！|此分類找不到有效的表情檔案！|No valid emote files found in this category!|このカテゴリに有効なスタンプが見つかりません！|fluent_ui/views/qq_scan_view.py:1431|

### TPB3-042 · 已有操作忙碌

- 入口/源码：fluent_ui/views/qq_scan_view.py:1287 / copy_files_with_progress。
- 条件：_current_worker仍在运行，阻止同工具复制/入库重入。
- 已完成步骤：之前任务仍在执行。
- 已写入/不能撤销/限制：不是失败或取消先前任务，新的请求不执行。
- 用户下一步：等待或停止先前任务。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|当前有正在进行的操作，请稍候或先中止当前任务！|缺失|缺失|缺失|fluent_ui/views/qq_scan_view.py:1290|

### TPB3-043 · 缺少Library服务

- 入口/源码：fluent_ui/views/qq_scan_view.py:1448 / import_files_with_progress。
- 条件：window没有storage。
- 已完成步骤：本次入库未排队。
- 已写入/不能撤销/限制：既显示fail也notify error；已存在库内容不改。
- 用户下一步：检查工具宿主，查看错误。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导入失败|導入失敗|Import failed|取り込みに失敗しました|fluent_ui/views/qq_scan_view.py:1458|
|无法获取表情合集表情库存储服务！|無法取得表情合集表情庫儲存服務！|The emote storage service is unavailable!|スタンプの保存サービスを利用できません！|fluent_ui/views/qq_scan_view.py:1458|

### TPB3-044 · 共用错误主摘要

- 入口/源码：fluent_ui/components/state_tool_tip_manager.py:35 / fail。
- 条件：门面fail；notify error且正文不是绑定文本时也采用此摘要。
- 已完成步骤：不能统一推断具体步骤，依原任务而定。
- 已写入/不能撤销/限制：原error正文放详情，不代表所有结果均回滚。
- 用户下一步：查看任务详情，依据原因决定重试。
- 翻译绑定/刷新：fail事件时t；不逐条翻译原异常。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|操作未完成，请查看详情后重试。|操作未完成，請檢視詳情後重試。|The operation could not be completed. Check the details and try again.|操作を完了できませんでした。詳細を確認して再試行してください。|fluent_ui/components/state_tool_tip_manager.py:39|

## Telegram

### TPB3-045 · 查询空输入

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1399 / startParsePack。
- 条件：strip后空。
- 已完成步骤：未访问网络。
- 已写入/不能撤销/限制：无库写入。
- 用户下一步：输入链接/包名。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|请先输入 Telegram 表情链接或包名！|請先輸入 Telegram 表情連結或套組名稱！|Please enter a Telegram emote link or pack name first!|先に Telegram スタンプのリンクまたはパック名を入力してください！|fluent_ui/views/tg_sticker_view.py:1405|

### TPB3-046 · 查询进行中

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1399 / startParsePack。
- 条件：启动ParsePackThread。
- 已完成步骤：清空旧pack/预览缓存。
- 已写入/不能撤销/限制：开始查询元数据，不是入库或完整下载。
- 用户下一步：等待/停止。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在解析 Telegram 表情合集...|缺失|缺失|缺失|fluent_ui/views/tg_sticker_view.py:1424|
|正在解析表情合集 [{link}] ...|缺失|缺失|缺失|fluent_ui/views/tg_sticker_view.py:1422|

### TPB3-047 · 查询完成

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1444 / _onParseSuccess。
- 条件：当前worker返回pack。
- 已完成步骤：合集元数据就绪，随后懒加载缩略图。
- 已写入/不能撤销/限制：“已加载”不等于全包文件下载或入库。
- 用户下一步：选项、入库或导出。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|解析完成|缺失|缺失|缺失|fluent_ui/views/tg_sticker_view.py:1464|
|已加载《{title}》，共 {total} 张表情|缺失|缺失|缺失|fluent_ui/views/tg_sticker_view.py:1465|

### TPB3-048 · 查询失败

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1472 / _onParseFailed。
- 条件：当前worker failed。
- 已完成步骤：current_pack清空。
- 已写入/不能撤销/限制：动态error先t(error_msg)，再送fail详情；未知整串可MISSING。
- 用户下一步：查详情/检查输入或连接重试。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|解析失败|解析失敗|Parse Failed|解析失敗|fluent_ui/views/tg_sticker_view.py:1479|

### TPB3-049 · 文件导出开始

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1769 / _executeDownload。
- 条件：导出选中/全部。
- 已完成步骤：DownloadPackThread启动。
- 已写入/不能撤销/限制：独立文件下载/转换/可选ZIP，不入Library；不是TPB220/222。
- 用户下一步：等待/取消。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在导出 Telegram 表情...|缺失|缺失|缺失|fluent_ui/views/tg_sticker_view.py:1795|
|准备导出 {count} 张表情|缺失|缺失|缺失|fluent_ui/views/tg_sticker_view.py:1796|

### TPB3-050 · 文件导出进度

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1816 / _onDownloadProgress。
- 条件：download_pack逐项回调。
- 已完成步骤：done包含失败尝试。
- 已写入/不能撤销/限制：message来自原始中文f-string/异常，未单独t；文件存在不代表入库。
- 用户下一步：查进度/日志。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导出进度 [{done}/{total}]: {message}|匯出進度 [{done}/{total}]：{message}|Export progress [{done}/{total}]: {message}|エクスポート進捗 [{done}/{total}]：{message}|fluent_ui/views/tg_sticker_view.py:1818|

### TPB3-051 · 文件导出全成功

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1824 / _onDownloadFinished。
- 条件：fail_count==0
- 已完成步骤：download_pack返回；可选ZIP已处理。
- 已写入/不能撤销/限制：outcome分别success/partial/error，但标题和正文均同一全成功模板；不回滚文件，尝试开目录。
- 用户下一步：查看输出/日志；失败可重新提交。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导出完成|匯出完成|Export Complete|エクスポート完了|fluent_ui/views/tg_sticker_view.py:1833|
|🎉 全部提取成功! 成功导出 {success} 张, 失败 {failed} 张。|🎉 全部擷取成功！成功匯出 {success} 張，失敗 {failed} 張。|🎉 Extraction complete! Exported {success} emotes successfully, {failed} failed.|🎉 すべての抽出が完了しました！{success} 件を正常にエクスポート、{failed} 件が失敗しました。|fluent_ui/views/tg_sticker_view.py:1829|

### TPB3-052 · 文件导出部分成功

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1824 / _onDownloadFinished。
- 条件：success_count>0且fail_count>0
- 已完成步骤：download_pack返回；可选ZIP已处理。
- 已写入/不能撤销/限制：outcome分别success/partial/error，但标题和正文均同一全成功模板；不回滚文件，尝试开目录。
- 用户下一步：查看输出/日志；失败可重新提交。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导出完成|匯出完成|Export Complete|エクスポート完了|fluent_ui/views/tg_sticker_view.py:1833|
|🎉 全部提取成功! 成功导出 {success} 张, 失败 {failed} 张。|🎉 全部擷取成功！成功匯出 {success} 張，失敗 {failed} 張。|🎉 Extraction complete! Exported {success} emotes successfully, {failed} failed.|🎉 すべての抽出が完了しました！{success} 件を正常にエクスポート、{failed} 件が失敗しました。|fluent_ui/views/tg_sticker_view.py:1829|

### TPB3-053 · 文件导出零成功

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1824 / _onDownloadFinished。
- 条件：success_count==0且fail_count>0
- 已完成步骤：download_pack返回；可选ZIP已处理。
- 已写入/不能撤销/限制：outcome分别success/partial/error，但标题和正文均同一全成功模板；不回滚文件，尝试开目录。
- 用户下一步：查看输出/日志；失败可重新提交。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导出完成|匯出完成|Export Complete|エクスポート完了|fluent_ui/views/tg_sticker_view.py:1833|
|🎉 全部提取成功! 成功导出 {success} 张, 失败 {failed} 张。|🎉 全部擷取成功！成功匯出 {success} 張，失敗 {failed} 張。|🎉 Extraction complete! Exported {success} emotes successfully, {failed} failed.|🎉 すべての抽出が完了しました！{success} 件を正常にエクスポート、{failed} 件が失敗しました。|fluent_ui/views/tg_sticker_view.py:1829|

### TPB3-054 · 文件导出异常

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1850 / _onDownloadFailed。
- 条件：抛异常且非取消。
- 已完成步骤：可能已有独立文件。
- 已写入/不能撤销/限制：动态error整串t后进入fail详情，不回滚。
- 用户下一步：查详情后重试。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|导出失败|導出失敗|Export failed|書き出しに失敗しました|fluent_ui/views/tg_sticker_view.py:1855|

### TPB3-055 · 共用停止反馈

- 入口/源码：fluent_ui/components/state_tool_tip_manager.py:41 / cancel。
- 条件：StateToolTipManager.cancel且task_active。
- 已完成步骤：已完成处理保留。
- 已写入/不能撤销/限制：下载线程取消不再发finished_all/failed，由门面取消收尾。
- 用户下一步：查看已有结果，必要时重新开始。
- 翻译绑定/刷新：门面t+FeedbackHost.clean_message；QQ也复用。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|操作已停止|操作已停止|Operation stopped|操作を停止しました|fluent_ui/components/state_tool_tip_manager.py:44|
|已完成的处理结果会保留。|已完成的處理結果會保留。|Results already completed will be kept.|完了した処理の結果は残ります。|fluent_ui/components/state_tool_tip_manager.py:44|

### TPB3-056 · 连接恢复：start

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1282 / _on_recovery_status。
- 条件：RECOVERY_MESSAGES[start]；仅默认凭据官方401进入恢复。
- 已完成步骤：官方明确401确认原凭据失效。
- 已写入/不能撤销/限制：锁内有界恢复，非自定义Token；429/超时/DNS/代理故障不按401换凭据。成功不等于包完成。取消/旧worker更新受过滤。
- 用户下一步：等待/取消；失败可重试或自定义Token。
- 翻译绑定/刷新：worker Qt recovery_status→_on_recovery_status或batch._progress；入库用队列stage；各消费者t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|默认连接凭据已失效，正在尝试恢复连接…|預設連線憑據已失效，正在嘗試恢復連線…|The default connection credentials have expired. Trying to restore the connection…|既定の接続認証情報が無効です。接続の復旧を試みています…|services/tg_public_config.py:14|

### TPB3-057 · 连接恢复：fetch

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1282 / _on_recovery_status。
- 条件：RECOVERY_MESSAGES[fetch]；仅默认凭据官方401进入恢复。
- 已完成步骤：读取公开候选来源。
- 已写入/不能撤销/限制：锁内有界恢复，非自定义Token；429/超时/DNS/代理故障不按401换凭据。成功不等于包完成。取消/旧worker更新受过滤。
- 用户下一步：等待/取消；失败可重试或自定义Token。
- 翻译绑定/刷新：worker Qt recovery_status→_on_recovery_status或batch._progress；入库用队列stage；各消费者t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在检查可用的公开连接配置…|正在檢查可用的公開連線設定…|Checking available public connection settings…|利用可能な公開接続設定を確認しています…|services/tg_public_config.py:15|

### TPB3-058 · 连接恢复：verify

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1282 / _on_recovery_status。
- 条件：RECOVERY_MESSAGES[verify]；仅默认凭据官方401进入恢复。
- 已完成步骤：取得候选，getMe验证中。
- 已写入/不能撤销/限制：锁内有界恢复，非自定义Token；429/超时/DNS/代理故障不按401换凭据。成功不等于包完成。取消/旧worker更新受过滤。
- 用户下一步：等待/取消；失败可重试或自定义Token。
- 翻译绑定/刷新：worker Qt recovery_status→_on_recovery_status或batch._progress；入库用队列stage；各消费者t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在验证连接，请稍候…|正在驗證連線，請稍候…|Verifying the connection. Please wait…|接続を確認しています。しばらくお待ちください…|fluent_ui/views/tg_sticker_view.py:1364|

### TPB3-059 · 连接恢复：success

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1282 / _on_recovery_status。
- 条件：RECOVERY_MESSAGES[success]；仅默认凭据官方401进入恢复。
- 已完成步骤：候选已验证并尝试缓存，继续原请求。
- 已写入/不能撤销/限制：锁内有界恢复，非自定义Token；429/超时/DNS/代理故障不按401换凭据。成功不等于包完成。取消/旧worker更新受过滤。
- 用户下一步：等待/取消；失败可重试或自定义Token。
- 翻译绑定/刷新：worker Qt recovery_status→_on_recovery_status或batch._progress；入库用队列stage；各消费者t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|连接已恢复，正在继续原操作…|連線已恢復，正在繼續原操作…|Connection restored. Continuing the original operation…|接続が復旧しました。元の操作を続行しています…|services/tg_public_config.py:17|

### TPB3-060 · 连接恢复：failed

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1282 / _on_recovery_status。
- 条件：RECOVERY_MESSAGES[failed]；仅默认凭据官方401进入恢复。
- 已完成步骤：未恢复，原任务按真实结果失败。
- 已写入/不能撤销/限制：锁内有界恢复，非自定义Token；429/超时/DNS/代理故障不按401换凭据。成功不等于包完成。取消/旧worker更新受过滤。
- 用户下一步：等待/取消；失败可重试或自定义Token。
- 翻译绑定/刷新：worker Qt recovery_status→_on_recovery_status或batch._progress；入库用队列stage；各消费者t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|暂时无法恢复默认连接，可稍后重试或使用自定义 Bot Token。|暫時無法恢復預設連線，可稍後重試或使用自訂 Bot Token。|The default connection could not be restored. Try again later or use a custom Bot Token.|既定の接続を復旧できませんでした。後で再試行するか、独自の Bot Token を使用してください。|services/tg_public_config.py:18|

### TPB3-061 · 连接测试成功

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1371 / _onConnectionResult。
- 条件：bot_ok=True。
- 已完成步骤：Bot API测试完成。
- 已写入/不能撤销/限制：不是所有图片下载/入库都已验证；channel/bot为返回值。
- 用户下一步：继续合集查询。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|连通性测试|連線測試|Connection Test|接続テスト|fluent_ui/views/tg_sticker_view.py:1364|
|✅ 连接成功!<br><br>通道: {channel}<br>Bot 名称: @{bot}|✅ 連線成功！<br><br>通道：{channel}<br>Bot 名稱：@{bot}|✅ Connection successful!<br><br>Channel: {channel}<br>Bot name: @{bot}|✅ 接続に成功しました！<br><br>経路：{channel}<br>Bot 名：@{bot}|fluent_ui/views/tg_sticker_view.py:1376|

### TPB3-062 · 连接测试失败

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1371 / _onConnectionResult。
- 条件：bot_ok=False。
- 已完成步骤：未证明连接可用。
- 已写入/不能撤销/限制：error字段先t：动态错误值无键时MISSING；外层msg由t(...).format生成_TranslatedText，再t(msg)可重新render，不是此处必然二次缺译。fail通用正文，原结果进详情。
- 用户下一步：查看详情/修连接参数。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|连通性测试|連線測試|Connection Test|接続テスト|fluent_ui/views/tg_sticker_view.py:1364|
|❌ 连接失败: {error}|❌ 連線失敗：{error}|❌ Connection failed: {error}|❌ 接続に失敗しました：{error}|fluent_ui/views/tg_sticker_view.py:1386|

### TPB3-063 · 连接测试回调异常

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1371 / _onConnectionResult。
- 条件：测试结果处理抛异常。
- 已完成步骤：测试未正常结束。
- 已写入/不能撤销/限制：error为动态异常，不创造固定译文。
- 用户下一步：查详情再试。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|测试出错|測試出錯|Test failed|テストに失敗しました|fluent_ui/views/tg_sticker_view.py:1393|
|发生异常: {error}|發生例外：{error}|An exception occurred: {error}|例外が発生しました：{error}|fluent_ui/views/tg_sticker_view.py:1393|

### TPB3-064 · 重置连接参数

- 入口/源码：fluent_ui/views/tg_sticker_view.py:1325 / resetConfig。
- 条件：连接设置中重置。
- 已完成步骤：仅清空Token/反代/代理字段。
- 已写入/不能撤销/限制：没有网络验证；新请求重新从UI构造downloader。
- 用户下一步：测试连接/重新查询。
- 翻译绑定/刷新：事件发生时t或QQ _tf精确查键；动态参数随后format。既有文本不保证随语言变化立即重译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|✅ 已恢复默认网络与 Token 配置|✅ 已恢復預設網路與 Token 設定|✅ Network and Token settings have been restored to defaults|✅ ネットワークと Token の設定をデフォルトに戻しました|fluent_ui/views/tg_sticker_view.py:1330|

### TPB3-065 · 批量输入错误

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:161 / _start。
- 条件：没有链接或目录。
- 已完成步骤：未开worker。
- 已写入/不能撤销/限制：无新入库/输出。
- 用户下一步：补输入。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|请输入 TG 链接并选择保存目录。|請輸入 TG 連結並選擇儲存目錄。|Enter TG links and choose an output folder.|TG リンクと保存先を入力してください。|fluent_ui/components/tg_batch_dialog.py:167|

### TPB3-066 · 批量等待

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:161 / _start。
- 条件：合法输入每行建等待行。
- 已完成步骤：尚未处理。
- 已写入/不能撤销/限制：输入禁用，不等于任务成功。
- 用户下一步：等待/取消。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|等待中|等待中|Waiting|待機中|fluent_ui/components/tg_batch_dialog.py:171|

### TPB3-067 · 批量启动

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:161 / _start。
- 条件：worker启动。
- 已完成步骤：解析/下载/入库导出有界交错。
- 已写入/不能撤销/限制：单包失败继续后包，不回滚前包。
- 用户下一步：等待/取消。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在批量打包...|正在批次打包...|Processing batch...|一括処理中...|fluent_ui/components/tg_batch_dialog.py:183|

### TPB3-068 · 批量行：parse

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:186 / _progress。
- 条件：runner报告parse。
- 已完成步骤：元数据查询中。
- 已写入/不能撤销/限制：已保存资源/ZIP保留；done不等于每张图片成功，failed不等于无副作用。
- 用户下一步：双击行看详情，失败包需要时重新提交。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|解析中|解析中|Parsing|解析中|fluent_ui/components/tg_batch_dialog.py:198|

### TPB3-069 · 批量行：parsed

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:186 / _progress。
- 条件：runner报告parsed。
- 已完成步骤：元数据就绪。
- 已写入/不能撤销/限制：已保存资源/ZIP保留；done不等于每张图片成功，failed不等于无副作用。
- 用户下一步：双击行看详情，失败包需要时重新提交。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|等待下载|等待下載|Waiting to download|ダウンロード待ち|fluent_ui/components/tg_batch_dialog.py:198|

### TPB3-070 · 批量行：download

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:186 / _progress。
- 条件：runner报告download。
- 已完成步骤：资源下载中。
- 已写入/不能撤销/限制：已保存资源/ZIP保留；done不等于每张图片成功，failed不等于无副作用。
- 用户下一步：双击行看详情，失败包需要时重新提交。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|下载中|下載中|Downloading|ダウンロード中|fluent_ui/components/tg_batch_dialog.py:198|

### TPB3-071 · 批量行：ready

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:186 / _progress。
- 条件：runner报告ready。
- 已完成步骤：下载future结束但可含失败。
- 已写入/不能撤销/限制：已保存资源/ZIP保留；done不等于每张图片成功，failed不等于无副作用。
- 用户下一步：双击行看详情，失败包需要时重新提交。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|等待入库|等待入庫|Waiting to import|保存待ち|fluent_ui/components/tg_batch_dialog.py:199|

### TPB3-072 · 批量行：import

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:186 / _progress。
- 条件：runner报告import。
- 已完成步骤：创建独立分类并逐项保存。
- 已写入/不能撤销/限制：已保存资源/ZIP保留；done不等于每张图片成功，failed不等于无副作用。
- 用户下一步：双击行看详情，失败包需要时重新提交。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|入库中|入庫中|Importing|保存中|fluent_ui/components/tg_batch_dialog.py:199|

### TPB3-073 · 批量行：export

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:186 / _progress。
- 条件：runner报告export。
- 已完成步骤：可靠入库后导出ZIP。
- 已写入/不能撤销/限制：已保存资源/ZIP保留；done不等于每张图片成功，failed不等于无副作用。
- 用户下一步：双击行看详情，失败包需要时重新提交。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|打包中|打包中|Packaging|パック作成中|fluent_ui/components/tg_batch_dialog.py:199|

### TPB3-074 · 批量行：done

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:186 / _progress。
- 条件：runner报告done。
- 已完成步骤：ZIP存在，可含获取失败跳过项。
- 已写入/不能撤销/限制：已保存资源/ZIP保留；done不等于每张图片成功，failed不等于无副作用。
- 用户下一步：双击行看详情，失败包需要时重新提交。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|已完成|已完成|Completed|完了|fluent_ui/components/tg_batch_dialog.py:200|

### TPB3-075 · 批量行：failed

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:186 / _progress。
- 条件：runner报告failed。
- 已完成步骤：该包异常，不阻止下一包。
- 已写入/不能撤销/限制：已保存资源/ZIP保留；done不等于每张图片成功，failed不等于无副作用。
- 用户下一步：双击行看详情，失败包需要时重新提交。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|失败|失敗|Failed|失敗|fluent_ui/components/tg_batch_dialog.py:200|

### TPB3-076 · 批量行：cancelled

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:186 / _progress。
- 条件：runner报告cancelled。
- 已完成步骤：未完成包被取消。
- 已写入/不能撤销/限制：已保存资源/ZIP保留；done不等于每张图片成功，failed不等于无副作用。
- 用户下一步：双击行看详情，失败包需要时重新提交。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|已取消|已取消|Cancelled|キャンセル|fluent_ui/components/tg_batch_dialog.py:200|

### TPB3-077 · 批量完成详情

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:42 / _process。
- 条件：importer无fatal错误且output ZIP存在。
- 已完成步骤：入库与ZIP完成。
- 已写入/不能撤销/限制：success含复用；skipped指获取失败；仍计包status done。
- 用户下一步：看ZIP或行详情。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|已导出：处理成功 {success} 张，获取失败跳过 {skipped} 张。|已匯出：成功處理 {success} 張，取得失敗略過 {skipped} 張。|Exported: {success} processed, {skipped} skipped due to download failures.|エクスポート済み：成功 {success} 枚、取得失敗でスキップ {skipped} 枚。|fluent_ui/components/tg_batch_dialog.py:84|

### TPB3-078 · 批量总结束

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:226 / _finished。
- 条件：无worker.error，按results.status计包数。
- 已完成步骤：各包终态已定。
- 已写入/不能撤销/限制：成功包可含图片跳过，不是图片成功数。
- 用户下一步：查看详情/重提失败链接。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|批量处理结束：成功 {success} 包，失败 {failed} 包，取消 {cancelled} 包。|批次處理結束：成功 {success} 包，失敗 {failed} 包，取消 {cancelled} 包。|Batch finished: {success} succeeded, {failed} failed, {cancelled} cancelled.|一括処理終了：成功 {success} 件、失敗 {failed} 件、キャンセル {cancelled} 件。|fluent_ui/components/tg_batch_dialog.py:236|

### TPB3-079 · 批量顶层失败

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:226 / _finished。
- 条件：worker.error非空。
- 已完成步骤：可能已完成一些包。
- 已写入/不能撤销/限制：追加原异常，未终态行置failed；不删已生成ZIP。
- 用户下一步：查详情排错。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|批量打包失败|批次打包失敗|Batch failed|一括作成に失敗|fluent_ui/components/tg_batch_dialog.py:231|

### TPB3-080 · 批量取消收尾

- 入口/源码：fluent_ui/components/tg_batch_dialog.py:243 / reject。
- 条件：运行中取消/关窗。
- 已完成步骤：发cancel_event，暂禁关闭，等待finished。
- 已写入/不能撤销/限制：ZIP保留；可能另有已入库而未生成ZIP的资源同样保留。
- 用户下一步：等待收尾再关闭。
- 翻译绑定/刷新：构造/进度事件t；Dialog未连接language_changed完整重建已存在表格。动态message完整串再t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在取消，等待当前操作收尾；已完成的 ZIP 将保留。|正在取消，等待目前操作收尾；已完成的 ZIP 將保留。|Cancelling after current operations finish. Completed ZIPs will be kept.|現在の操作の終了を待ってキャンセルします。完成した ZIP は保持されます。|fluent_ui/components/tg_batch_dialog.py:249|

## OCR

### TPB3-081 · 组件状态：installed

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：component.installed为真，且无下载/安装/失败/取消覆盖分支。
- 已完成步骤：下载收字节，安装含解压/校验/启动检查；installed为验证通过。
- 已写入/不能撤销/限制：安装前停止识别；成功立即ocr_auto=True；失败/取消不删旧文字。
- 用户下一步：等待/停止；失败看详情并重选包。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|已安装|已安裝|Installed|インストール済み|fluent_ui/components/ocr_controls.py:179|

### TPB3-082 · 组件状态：absent

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：component.installed为假，且无下载/安装/失败/取消覆盖分支。
- 已完成步骤：下载收字节，安装含解压/校验/启动检查；installed为验证通过。
- 已写入/不能撤销/限制：安装前停止识别；成功立即ocr_auto=True；失败/取消不删旧文字。
- 用户下一步：等待/停止；失败看详情并重选包。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|未安装|未安裝|Not installed|未インストール|fluent_ui/components/ocr_controls.py:179|

### TPB3-083 · 组件状态：downloading

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：install_state==downloading，百分比在total非零时追加。
- 已完成步骤：下载收字节，安装含解压/校验/启动检查；installed为验证通过。
- 已写入/不能撤销/限制：安装前停止识别；成功立即ocr_auto=True；失败/取消不删旧文字。
- 用户下一步：等待/停止；失败看详情并重选包。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在下载|正在下載|Downloading|ダウンロード中|fluent_ui/components/ocr_controls.py:181|

### TPB3-084 · 组件状态：installing

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：非downloading且installing为真；包括checking阶段。
- 已完成步骤：下载收字节，安装含解压/校验/启动检查；installed为验证通过。
- 已写入/不能撤销/限制：安装前停止识别；成功立即ocr_auto=True；失败/取消不删旧文字。
- 用户下一步：等待/停止；失败看详情并重选包。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在安装|正在安裝|Installing|インストール中|fluent_ui/components/ocr_controls.py:184|

### TPB3-085 · 组件状态：failed

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：非运行安装且install_state==failed。
- 已完成步骤：下载收字节，安装含解压/校验/启动检查；installed为验证通过。
- 已写入/不能撤销/限制：安装前停止识别；成功立即ocr_auto=True；失败/取消不删旧文字。
- 用户下一步：等待/停止；失败看详情并重选包。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|安装失败|安裝失敗|Installation failed|インストール失敗|fluent_ui/components/ocr_controls.py:185|

### TPB3-086 · 组件状态：cancelled

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：非运行安装且install_state==cancelled。
- 已完成步骤：下载收字节，安装含解压/校验/启动检查；installed为验证通过。
- 已写入/不能撤销/限制：安装前停止识别；成功立即ocr_auto=True；失败/取消不删旧文字。
- 用户下一步：等待/停止；失败看详情并重选包。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|已取消安装|已取消安裝|Installation cancelled|インストールをキャンセルしました|fluent_ui/components/ocr_controls.py:186|

### TPB3-087 · 安装错误摘要

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：install_error非空。
- 已完成步骤：当前安装未成功。
- 已写入/不能撤销/限制：详情原install_error，不等同识别失败。
- 用户下一步：看详情/换包。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|组件安装失败，请检查组件包或查看详情。|元件安裝失敗，請檢查元件包或查看詳細資料。|Installation failed. Check the component package or view details.|インストールに失敗しました。パッケージを確認するか、詳細をご覧ください。|fluent_ui/components/ocr_controls.py:193|

### TPB3-088 · 无在线组件

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：release没有url。
- 已完成步骤：未下载。
- 已写入/不能撤销/限制：install改选本地ZIP，取消选择不开始安装。
- 用户下一步：选择本地包。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|在线组件尚未发布，请选择本地组件包安装。|線上元件尚未發布，請選擇本機元件包安裝。|The online component is not published yet. Choose a local component package.|オンライン配布は未公開です。ローカルのコンポーネントパッケージを選択してください。|fluent_ui/components/ocr_controls.py:188|

### TPB3-089 · 卸载确认

- 入口/源码：fluent_ui/components/ocr_controls.py:164 / uninstall。
- 条件：点击卸载。
- 已完成步骤：确认前未卸载。
- 已写入/不能撤销/限制：确认后cancel、close进程、删组件、ocr_auto=False；不删文字/资源。
- 用户下一步：确认/取消。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|卸载 OCR|卸載 OCR|Uninstall OCR|OCR をアンインストール|fluent_ui/components/ocr_controls.py:165|
|停止识别并移除 OCR 组件？已识别文字和人工修改会保留。|停止識別並移除 OCR 組件？已識別文字和人工修改會保留。|Stop recognition and remove OCR? Recognized text and manual edits will be kept.|認識を停止して OCR を削除しますか？認識済みの文字と手動編集は残ります。|fluent_ui/components/ocr_controls.py:165|

### TPB3-090 · 卸载失败

- 入口/源码：fluent_ui/components/ocr_controls.py:164 / uninstall。
- 条件：service.uninstall异常。
- 已完成步骤：可能已停止识别/关闭进程。
- 已写入/不能撤销/限制：删除组件结果取决异常，无原子回滚承诺。
- 用户下一步：查看原异常、检查占用。
- 翻译绑定/刷新：标题t，dialogs.message正文str(exc)原值；不补译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|卸载失败|卸載失敗|Uninstall failed|アンインストール失敗|fluent_ui/components/ocr_controls.py:167|

### TPB3-091 · 设置任务：running

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：summary.state=running，TASKS映射。
- 已完成步骤：completed表示所有单元处理结束，running尚在队列。
- 已写入/不能撤销/限制：可含failed/skipped；停止不撤销文字。
- 用户下一步：运行可停止，结束可补充/重试，持久中断从任务栏恢复。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|正在识别|正在識別|Recognizing|認識中|fluent_ui/components/ocr_controls.py:11|

### TPB3-092 · 设置任务：completed

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：summary.state=completed，TASKS映射。
- 已完成步骤：completed表示所有单元处理结束，running尚在队列。
- 已写入/不能撤销/限制：可含failed/skipped；停止不撤销文字。
- 用户下一步：运行可停止，结束可补充/重试，持久中断从任务栏恢复。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|识别完成|識別完成|Recognition complete|認識完了|fluent_ui/components/ocr_controls.py:11|

### TPB3-093 · 设置任务：cancelled

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：summary.state=cancelled，TASKS映射。
- 已完成步骤：completed表示所有单元处理结束，running尚在队列。
- 已写入/不能撤销/限制：可含failed/skipped；停止不撤销文字。
- 用户下一步：运行可停止，结束可补充/重试，持久中断从任务栏恢复。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|已停止识别|已停止識別|Recognition stopped|認識を停止しました|fluent_ui/components/ocr_controls.py:11|

### TPB3-094 · 设置任务：interrupted

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：summary.state=interrupted，TASKS映射。
- 已完成步骤：completed表示所有单元处理结束，running尚在队列。
- 已写入/不能撤销/限制：可含failed/skipped；停止不撤销文字。
- 用户下一步：运行可停止，结束可补充/重试，持久中断从任务栏恢复。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|上次识别已中断|上次識別已中斷|Previous recognition was interrupted|前回の認識は中断されました|fluent_ui/components/ocr_controls.py:11|

### TPB3-095 · 设置任务：idle

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：summary.state=idle，TASKS映射。
- 已完成步骤：completed表示所有单元处理结束，running尚在队列。
- 已写入/不能撤销/限制：可含failed/skipped；停止不撤销文字。
- 用户下一步：运行可停止，结束可补充/重试，持久中断从任务栏恢复。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|暂无识别任务|暫無識別任務|No recognition task|認識タスクはありません|fluent_ui/components/ocr_controls.py:11|

### TPB3-096 · 设置任务：来源等待

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：summary.state=waiting_source，TASKS缺此键。
- 已完成步骤：来源不可用，仍有未完成单元。
- 已写入/不能撤销/限制：设置页回退idle，而图库任务栏显示未完成OCR任务。
- 用户下一步：连回来源/看恢复选项。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|暂无识别任务|暫無識別任務|No recognition task|認識タスクはありません|fluent_ui/components/ocr_controls.py:11|

### TPB3-097 · 设置任务计数

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：summary.total非0。
- 已完成步骤：done变量=done+failed+skipped。
- 已写入/不能撤销/限制：已完成不是识别成功数；跳过含人工/未变化/资源变化。
- 用户下一步：结合失败/跳过数判断。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|已完成 {done} / {total} 张<br>失败 {failed} 张 · 跳过 {skipped} 张|已完成 {done} / {total} 張<br>失敗 {failed} 張 · 跳過 {skipped} 張|Processed {done} / {total} emotes<br>Failed: {failed} · Skipped: {skipped}|処理済み {done} / {total} 枚<br>失敗 {failed} 枚 · スキップ {skipped} 枚|fluent_ui/components/ocr_controls.py:203|

### TPB3-098 · 任务错误摘要

- 入口/源码：fluent_ui/components/ocr_controls.py:177 / refresh。
- 条件：summary.error非空。
- 已完成步骤：可能部分成功或等待来源。
- 已写入/不能撤销/限制：固定摘要，不等于所有资源失败。
- 用户下一步：看详情/重试失败。
- 翻译绑定/刷新：service.changed经80ms单次合并refresh，language_changed也refresh；事件中t精确查键。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|部分表情未能识别，请查看详情或重试。|部分表情未能識別，請查看詳細資料或重試。|Some emotes could not be recognized. View details or retry.|一部のスタンプを認識できませんでした。詳細を確認するか再試行してください。|fluent_ui/components/ocr_controls.py:204|

### TPB3-099 · 错误详情

- 入口/源码：fluent_ui/components/ocr_controls.py:151 / show_details。
- 条件：更多→查看详情。
- 已完成步骤：读取install_error优先，其次summary.error，均空用回退。
- 已写入/不能撤销/限制：只读；不隐藏/撤销已存成果。
- 用户下一步：关闭详情。
- 翻译绑定/刷新：标题/空回退t；真实异常直接setPlainText，不再译。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|文字识别详情|文字識別詳細資料|Text recognition details|文字認識の詳細|fluent_ui/components/ocr_controls.py:152|
|暂无错误详情|目前沒有錯誤詳細資料。|No error details.|エラーの詳細はありません。|fluent_ui/components/ocr_controls.py:154|

### TPB3-100 · 图库OCR任务

- 入口/源码：fluent_ui/views/gallery_view.py:2876 / _sync_background_tasks。
- 条件：OCR job running/completed/cancelled/interrupted/waiting_source。
- 已完成步骤：done同样是处理总数；有failed时按done/skipped决定partial/error。
- 已写入/不能撤销/限制：已提交文字保留，取消全库force任务可在进程内继续剩余。
- 用户下一步：停止/继续/查看恢复选项。
- 翻译绑定/刷新：service.changed触发sync；正文job.error可再t，详情原文。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|表情 {done}/{total} 张，失败 {failed} 张，跳过 {skipped} 张|表情 {done}/{total} 張，失敗 {failed} 張，跳過 {skipped} 張|Emotes {done}/{total}, failed {failed}, skipped {skipped}|スタンプ {done}/{total} 件、失敗 {failed} 件、スキップ {skipped} 件|fluent_ui/views/gallery_view.py:2926|
|文字识别已停止|文字識別已停止|Text recognition stopped|文字認識を停止しました|fluent_ui/views/gallery_view.py:2927|
|发现未完成 OCR 任务|發現未完成 OCR 工作|Unfinished OCR task found|未完了のOCRタスクが見つかりました|fluent_ui/views/gallery_view.py:2930|

### TPB3-101 · 人工内容覆盖确认

- 入口/源码：fluent_ui/components/ocr_controls.py:14 / request_recognition。
- 条件：force=True且存在manual资源。
- 已完成步骤：尚未提交本次覆盖。
- 已写入/不能撤销/限制：仅确认后overwrite=True；成功且revision/source匹配才替换，失败保留旧text。
- 用户下一步：确认重新识别/取消。
- 翻译绑定/刷新：函数调用时t。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|重新识别文字|重新識別文字|Recognize text again|文字を再認識|fluent_ui/components/ocr_controls.py:22|
|选中表情包含人工修改的文字。重新识别成功后将替换这些文字，是否继续？|選中表情包含人工修改的文字。重新識別成功後將替換這些文字，是否繼續？|Some selected emotes have edited text. Successful recognition will replace it. Continue?|選択したエモートには手動編集した文字があります。認識に成功すると置き換わります。続けますか？|fluent_ui/components/ocr_controls.py:23|

### TPB3-102 · 编辑文字说明

- 入口/源码：fluent_ui/components/ocr_controls.py:54 / edit_text。
- 条件：资源菜单编辑文字。
- 已完成步骤：读取现有text。
- 已写入/不能撤销/限制：保存设置manual=True、revision+1，不加标签；取消不保存本次输入。
- 用户下一步：编辑保存/取消。
- 翻译绑定/刷新：构造时t，保存service.edit→LibraryIndex.edit_ocr_text。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|这些文字用于搜索，不会添加为标签。保存后的人工修改不会被自动识别覆盖。|這些文字用於搜索，不會添加爲標籤。保存後的人工修改不會被自動識別覆蓋。|This text is used for search, not tags. Saved manual edits are protected from automatic recognition.|検索用の文字で、タグには追加されません。保存した手動編集は自動認識で上書きされません。|fluent_ui/components/ocr_controls.py:60|

### TPB3-103 · 资源状态：unrecognized

- 入口/源码：fluent_ui/components/ocr_controls.py:54 / edit_text。
- 条件：info.status经STATES映射；未知默认尚未识别。
- 已完成步骤：empty是正常无文字，failed是异常，ready是识别状态。
- 已写入/不能撤销/限制：失败commit保留旧text，显示状态本身不修改数据。
- 用户下一步：编辑或需要时重新识别。
- 翻译绑定/刷新：弹窗构造t(STATES...)。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|尚未识别|尚未識別|Not recognized yet|未認識|fluent_ui/components/ocr_controls.py:10|

### TPB3-104 · 资源状态：ready

- 入口/源码：fluent_ui/components/ocr_controls.py:54 / edit_text。
- 条件：info.status经STATES映射；未知默认尚未识别。
- 已完成步骤：empty是正常无文字，failed是异常，ready是识别状态。
- 已写入/不能撤销/限制：失败commit保留旧text，显示状态本身不修改数据。
- 用户下一步：编辑或需要时重新识别。
- 翻译绑定/刷新：弹窗构造t(STATES...)。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|已识别|已識別|Recognized|認識済み|fluent_ui/components/ocr_controls.py:10|

### TPB3-105 · 资源状态：empty

- 入口/源码：fluent_ui/components/ocr_controls.py:54 / edit_text。
- 条件：info.status经STATES映射；未知默认尚未识别。
- 已完成步骤：empty是正常无文字，failed是异常，ready是识别状态。
- 已写入/不能撤销/限制：失败commit保留旧text，显示状态本身不修改数据。
- 用户下一步：编辑或需要时重新识别。
- 翻译绑定/刷新：弹窗构造t(STATES...)。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|未发现文字|未發現文字|No text found|文字が見つかりません|fluent_ui/components/ocr_controls.py:10|

### TPB3-106 · 资源状态：failed

- 入口/源码：fluent_ui/components/ocr_controls.py:54 / edit_text。
- 条件：info.status经STATES映射；未知默认尚未识别。
- 已完成步骤：empty是正常无文字，failed是异常，ready是识别状态。
- 已写入/不能撤销/限制：失败commit保留旧text，显示状态本身不修改数据。
- 用户下一步：编辑或需要时重新识别。
- 翻译绑定/刷新：弹窗构造t(STATES...)。
- 未核实边界：本轮未运行此任务；实际网络返回、取消收尾时序、存量窗口语言切换外观未验证。

|中文源键|zh_TW|en|ja|字面量位置|
|---|---|---|---|---|
|识别失败|識別失敗|Recognition failed|認識失敗|fluent_ui/components/ocr_controls.py:10|

## 三、已确认冲突与指导AI设计优先级

按用户可见性、误解后果和行为风险排序；不提供替换措辞。

1. 高：Telegram独立文件导出_onDownloadFinished对全成功、部分和零成功无条件使用“🎉 全部提取成功!”正文及“导出完成”标题，但outcome已partial/error，数量本身真实。这里不是已锁定TPB220/222的入库导出。
2. 高：动态整串再t可能遮掉真正结果。连接结果内部t(res.error)可能遇动态无键；外层t(msg)识别_TranslatedText并render，不应误判为同一问题；_onParseFailed/_onDownloadFailed对动态error整体t；批量_progress将已格式化多行结果再t。模板有译文不代表完整插值结果有键，无键时必然MISSING。此为源码路径条件证明，不宣称GUI实测。
各语言强度也不同：该模板en为Extraction complete，并未说all success；zh/繁中仍为全部成功，ja为全部抽出完成。只记录不同承诺，不拟译文。
3. 中高：QQ/TG通用入库的失败来源被合并。Telegram网络获取失败、库保存失败都可变request.failed；用户主动跳过另计skipped。后续文案必须对应实际消费者，不能按旧worker变量名设计。
4. 中：OCR等待来源的summary.state=waiting_source在设置页TASKS未映射，回退“暂无识别任务”；图库任务栏实际显示未完成OCR任务。“已完成done”还包括failed/skipped，“识别完成”不是全部识别成功。
5. 中：批量成功包数含有获取失败跳过的done包。行详情有skipped，但总结束只数done/failed/cancelled；不能将成功包数当全部图片成功。
6. 中：QQ导出主反馈已分流，但工具日志_on_export_finished仍无条件写“✅ 成功导出 {count} 个表情文件！”，零成功同样写。showHelp称输出文件夹以QQ号开头，实际昵称成功时前缀为昵称（账号），并非号码开头。
7. 信息边界：取消不是撤销。当前通用停止、QQ导出停止、批量保留ZIP都符合已有行为；批量还可能保留已入库而未ZIP的资源。没有依据把“保留ZIP”理解成只留下ZIP。
8. 信息边界：自定义Token无效的服务异常仍写“高级配置”，当前入口为“连接设置”。本轮只记位置差异，不恢复隐藏旧界面，不创建新的错误文案。

### 当前无新增行为冲突证据、语义已有支持的项目

- QQ扫描发现数/取消未应用结果，能与本地扫描阶段对应；不承诺入库。
- QQ导出主终态与已导出/失败数量已有正确分流；本轮不推翻已有部分成功机制。
- 昵称告知的第三方、发送对象、确认后触发、24小时缓存、扫描/入库不查询，与实际链路一致。
- 恢复五阶段与真实操作绑定，success只继续原操作；自定义Token和网络故障边界明确。
- OCR人工文字保护、成功重识别覆盖确认、卸载保留文字、停止保留完成结果，有存储层支持。
- TPB220/222/225/226/229及第二批均保持原样。上述判断仅指未发现行为矛盾，不代替四语言风格审校或最终验收。

## 四、动态正文和非完整翻译边界

- 共享错误门面标题t，主摘要为“操作未完成，请查看详情后重试。”，原content放详情。表中记录的动态错误不是必然直接主屏正文；StateToolTipManager.fail、notify(kind=error)的未绑定原字符串还会转详情。
- Telegram服务download_pack进度由“已下载/下载失败/ZIP阶段”中文f-string和运行参数生成，_onDownloadProgress只译外层模板，不译message。批量_progress反过来对整个message再t；原始信息、模板译文、动态整串缺键是三个不同事实。
- Telegram错误来源为Bot API error.description、HTTP、requests超时/代理/DNS、源文件不可用、格式处理/本地IO。只说明这些来源与_safe_error脱敏，不列真实返回、不输出认证URL或Token。自定义Token固定无效异常由_request_api/download_file_bytes抛出，不参与自动公共恢复。
- QQ异常日志可拼原文件名/系统错误，本轮不读取真实日志；view.log保存内存快照，超过2000缩至最后1000。日志窗不是每条文字的实时翻译控件。
- OCR.show_details优先install_error，其次summary.error，原样显示；固定摘要有译文不证明动态异常有译文。图库job.error有t分支，详情仍保留原文。
- OCR.refresh绑定language_changed；QQ.update_texts更新部分静态标签/空详情，TG.update_texts仅格式选项/summary；批量表格没有完整实时换语重建。已打开窗口是否由其它导航重建，本轮未运行，不外推始终即时刷新。
- 共用恢复窗口还会显示来源不可靠、删除来源任务需核对、无清单等动态reason；QQ/TG自定义operation因unsupported阻止自动继续。放弃只忘记任务，不删完成成果。未为内部所有恢复reason另建重复记录。

## 五、后续与未验证范围

只覆盖当前可见/影响理解的任务反馈，不采隐藏configCard/actionBar旧默认文案，不采全部第三方异常栈、Worker脚本帮助或无界服务错误。旧QQ/TG入库回调未被当前operation绑定，不能计作当前UI问题。

源码定位已区分同名__init__，重复决策记录指向DuplicateBatchDialog实际定义；恢复五阶段入口指向实际UI消费者_on_recovery_status，字面量表另列RECOVERY_MESSAGES源位置。报告不改业务来解决事实冲突。

所有四语言仅当前JSON值，没有补写不存在的译文。缺失数量仅精确键存在性，不等于语义差异数量；自然语言是否需要改由指导AI决定。动态参数来自当前任务对象/来源/计数，不以真实私人值作例子。

本轮没有启动GUI、固定Demo、正式版、QQ/TG客户端，也没有下载/导入/导出/OCR/安装/卸载/删除或修改任何资源数据；无运行结果验证、无跨Windows/DPI承诺。取消时序、线程收尾延迟、实际HTTP返回、外部应用读取、设备断连与组件在线发行状态仍待相应独立验证。

仅新增本报告和必要项目记录；第一、二批锁定文案/翻译/测试及业务UI不动。W01七处实验原样，W02暂停、W03不启用，原Library/Demo/Suzu未操作。不Push/打包/发布。完成调查后停止，#62继续部分完成，等待指导AI第三批正式映射。
