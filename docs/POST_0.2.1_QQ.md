# QQ 工具：定位、预览与任务生命周期

2026-10-23，基点 510e639，dev/post-0.2.1。用户补充指令恢复 QQ 调查；不扩大到 OCR 实现。T-10/#50 记录宿主二级操作持续失效，T-11/#51 记录 QQ 定位/预览/停止缺陷，两者不预设同因。

## 已确认并修复（待人工体验）

| 提交 | 实际原因及改动 |
| --- | --- |
| dc2179d | 工具关闭后 discovery_closed 没有在再显示时复位；数字账号目录被当作 Tencent Files 根目录。showEvent 恢复发现，QQDiscovery 规范根路径并保留首选账号；账号/分类加载状态与业务忙碌状态组合管理，空结果和失败结束加载。 |
| d002233 | loadMoreEmojis 在 GUI 连续读取并完整解码100项，嵌套 processEvents 排除用户输入；扫描 cancel 是空方法，返回/关闭同步等待。QQPreviewWorker 后台读取、解码、缩放 QImage，GUI 仅建立图标；扫描遍历检查协作取消，原任务反馈提供停止。关闭作废 generation，取消工具所属任务并由 finished 清理，不逐线程阻塞 GUI。 |
| 49ee000 | Fluent ComboBox 在 index=0 时调用 setPlaceholderText 会覆盖首项实际显示。先设置空列表占位再填入项目，保留首项标签。补充 Marketface/APNG 实际解码回归。 |
| c45117d | 全选逐项 setSelected 触发重复 selectionChanged 和详情工作。使用 Qt 原生 selectAll，一次提交选择，30项真实控件对照29次信号降为1次。 |
| 79b4d06 | INI 解码错误地要求正文含中文，完全 ASCII 的有效路径被拒绝并进入其它目录探测。按目标节、严格解码及既有 ConfigParser/路径检查读取；覆盖 ASCII、UTF-8 BOM、UTF-16、GB18030。 |

主要源码：fluent_ui/views/qq_scan_view.py（QQDiscovery、QQScanWorker、QQPreviewWorker、shutdown/_finish_shutdown、_discovery_ready、loadMoreEmojis、全选）；services/qq_extractor.py（扫描检查点、目录/INI读取）。新增状态文案四语言同步。没有替换 QQ UI、Library 或任务框架。

关闭工具仅取消其发现/扫描/预览/导出。已交给共享 ImportQueue 的导入继续由队列负责，不取消无关导入。应用真正退出时，aboutToQuit 发出取消并在所有 QQ Worker 上共享最多2秒等待预算，不强杀线程；阻塞系统 I/O 超过预算的环境尚未验证，不能保证所有外部文件系统均能及时退出。

## 证据与边界

- 本地 Source QQ 页面从 v0.2.1 至本批基点无改动；确认缺陷来自原路径，不据此认定正式用户的全部现象已修复。
- 100张2048×2048隔离 PNG、真实 QApplication.exec：旧方法调用3166.41ms、主线程心跳最大间隔386.98ms；新方法提交0.39ms、最大20.6ms，100项可用总时长3245.22→2758.59ms。旧方法期间排除用户输入；这些不是单项 paint 统计。原始对照及脚本在 DevData/post-021-qq/preview-{before,after}.json、preview_probe.py。
- 定向命令：`.venv/Scripts/python.exe -X faulthandler -m pytest tests/test_qq_lifecycle.py tests/test_qq_extractor.py tests/test_qq_apng_conversion.py tests/test_qq_scan_view_layout.py -q`：20 passed，4 subtests passed。覆盖新旧发现结果竞态/空目录/重新打开、真实扫描取消、关闭预览/丢弃结果、Marketface源字节不变和APNG播放、全选及编码路径。
- 真实系统指针/Windows原生输入：原生目录选择器选择合成账号目录；预览中、关闭工具后、导入后均成功从宿主右键创建/删除分类、打开其它工具；实际索引记录与可见窗口核对，不只检查回调。
- 16项 QQ 导入全部成功；关闭 QQ 工具后共享队列仍完成。1500文件实际扫描由任务停止入口取消；120文件导出在文件边界停止，已完成14文件保留（仅测试注入每文件4ms用于控制取消窗口，不作性能证据）。全流程结束 QQ Worker=0，原生托盘右键退出成功。
- 另一次按 main.py 顺序先创建 QApplication 的隔离启动：预览 Worker 活动时从原生托盘右键退出，aboutToQuit 后 Worker=0，进程退出码0。结果 native-active-exit-results.json。完整流程 native-complete-results.json；原生界面截图在同目录 screenshots。
- Windows 11 家庭版 Insider Preview、PySide6 6.11.2、Python3.12.10 实测。QQ 单项详情的原有解码路径未全面后台化；Win10、多显示器/混合DPI、阻塞/远程磁盘和真实用户长会话未测。

**T-10/#50 未复现、未宣称修复。** 当前对照没有观察到持续全局菜单锁定；没有删除全局任务保护或修改模态/窗口宿主。OCR 非本轮动态验证范围。自动化曾遇遮挡/未命中及测试误用 Storage.node 的回退语义；最终以实际命中和 storage.index.node 的存储结果为准。

**独立待定位证据**：补充测试中快速替换发现目录，两次发生原生访问冲突，堆栈在新 QQDiscovery/QThread 构造，另一个发现任务仍活动；原始栈 discovery-native-fault.log。改变测试导入时点后定向测试通过；父对象对照不能证明 parent 是原因。未确定 C++ 根因，未增加 parentless线程或串行调度补丁，不能等同于用户的全局交互失效或正式版闪退。保留在 T-07/#35 线索中。

## 上游参考与保护

有限读取 QQFavoriteExtract v1.5.5 对应 workers/emoji_scanner/workspace/user_service，及提交 4ef41e8a32、50a8e95741。复用后台 QImage、协作取消/过期结果、Qt 批量选择的机制，未整份移植加载提示系统。保留本地 Marketface、APNG、多分类导入、昵称本地缓存及国际化。

G-04 d322366、G-06 85aac5d、G-22 57f50e6 及 WP-E/F 不改，验收见 POST_0.2.1_WPB.md；G-05/#17仍有产品语义缺口。原七处未提交文件按 SHA256 保护不混入提交。Issue 均 Open，#37不勾选；不Push、不发布、不修改v0.2.1或真实用户库。

## 统一 Demo

`DevData/post-021-qq/Start-Demo.cmd`，操作说明同目录 README.md。仅合成 QQ 路径、图库及导出目录。为了不启用七处原 W-01 实验，沿用379a047的已提交三个窗口宿主模块，其余使用本轮源码；不复制完整工程。用户只需正常使用，不需操作采样按键。
