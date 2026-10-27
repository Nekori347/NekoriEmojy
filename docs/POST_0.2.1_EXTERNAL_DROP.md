# G-27 / #52：外部拖放原件保护与持续 Demo

2026-10-23，基点 eaa68cc，dev/post-0.2.1。独立新增 P0；不改正式v0.2.1、真实用户资源、Library模型或其它工作包。

## 实际根因和修复

EmojiCard.mouseMoveEvent 将真实 Library 文件路径同时放入 text/uri-list 和 text/plain，允许Copy/Move；没有应用删除确认和索引同步。隔离资源属于两个分类，真实系统鼠标拖入Windows回收站后，原文件被移走，两条关系和资源记录仍在；QDrag.exec 返回 **IgnoreAction**。因此不能仅检测MoveAction，也不能事后发现文件消失才确认。

`f21fa35`：services/external_drag.py 的 ResourceDragMimeData 保留内部 RESOURCE_MIME 路径合同，仅在外部索取文件数据时生成独立物理副本，文件URL和文本全部使用副本路径。没有硬链接，没有改变Library关系/排序；内部DragSession无需触发文件导出。准备失败时不给原件/部分批次URL，沿现有对话框反馈错误，四语言同步。

文件导出位于app数据的cache/external_drag/drag-*，每批唯一目录，重复文件名各自保留；拖放返回后不立即删除，以支持聊天客户端延迟读取。新进程首次外部导出清理7天前自有缓存，清理路径核实在该缓存根目录内。没有修改剪贴板发送、图片格式或聊天发送设置。

## 回收站确认的真实边界

**本轮完成原件保护，没有实现回收站触发应用删除确认。** 回收站接收的只是导出副本，图库不改变；删除受管理资源仍使用应用内已有确认规则。

Microsoft说明回收站通过IDataObject::SetData的CFSTR_TARGETCLSID传回CLSID，不能从普通Copy/Move反馈推断。Qt6.11.2对应Windows实现的SetData仅处理Performed DropEffect，不把TargetCLSID送回QMimeData。当前Qt高层路径无法可靠识别并介入；没有增加位置猜测、事后弹窗、补文件或删除失效索引的补丁，也没有重写原生OLE框架。该交互继续在#52待实现/验收。

官方依据：[Qt拖放](https://doc.qt.io/qt-6/dnd.html)、[Microsoft回收站场景](https://learn.microsoft.com/en-us/windows/win32/shell/datascenarios#dropping-files-on-the-recycle-bin)、[Shell格式](https://learn.microsoft.com/en-us/windows/win32/shell/clipboard#cfstr_targetclsid)、[Qt6.11.2实际SetData实现](https://github.com/qt/qtbase/blob/v6.11.2/src/plugins/platforms/windows/qwindowsole.cpp#L106)。

## 定向验证

- `tests/test_external_drag.py` 4项：真实QMimeData URL/文本转换、内部合同及不导出、独立物理文件、同名文件/延迟读取、第二文件复制失败不泄露部分批次、旧缓存清理。连同原WP-B三个真实控件/数据回归，共7项通过；最后强化部分失败场景后4项再次通过。
- 真实Windows原生鼠标：桌面Progman、资源管理器文件夹、回收站、Esc中断。桌面/文件夹实际得到有效图片；回收站只移走副本；每种情况的原件字节均与拖前相同，资源记录及两个分类关系完整。返回动作分别观察到Copy、Move及Ignore，不拿动作码当安全判断。
- 已协调用户空闲窗口进行最终四场原生复测；此前用户同时操作鼠标导致的未命中/中断运行不作产品失败结论。桌面最终运行实际成功，但测试收回样本用rename跨盘失败；随后验证副本与原件一致并用跨盘移动收回，原始错误与修正结果均保留。没有清空系统回收站或处理任何非测试文件。
- 既有应用内删除：真实Qt对话框按钮测试（offscreen，不占系统鼠标），取消保留原文件/记录/两关系，确认调用既有Windows回收逻辑并移除全部关系，新进程确认删除已持久化。不是回收站确认交互的验收。
- 四种外部拖放后分别以新进程重新打开隔离Library，文件可读/像素正确，记录和两关系完整。原输入文件与入库后PNG可能有正常编码差异；完整字节对照基于入库后、拖放前原件，不错误比较入库前编码。
- 文件URL/扩展名/原始字节交付保留，未改聊天发送路径。**没有向实际QQ/聊天会话发送消息，具体客户端接收仍待正常使用验收**，不以Shell通过代替所有聊天软件通过。

环境：本机Windows11 Insider、PySide6 6.11.2/Python3.12.10。Win10、特殊Shell扩展、超大批次/远程磁盘、7天后仍未读取文件的客户端未实测。原始脚本与结果：DevData/external-drop。

## 统一开发 Demo

固定入口 `DevData/Demo/Start-Demo.cmd`，核心脚本 `Source/tools/development_demo.py`。检查当前dev分支，使用当前源码；仅三个有原W-01未提交实验的宿主模块读取当前Git HEAD，不再锁旧SHA，不改实验文件。无平行源码副本。

数据固定在 `DevData/Demo/data`，首次承接post-021-qq的隔离数据副本（旧目录保留），之后只初始化一次、持续保留，不每批重建/清空。QQ合成样本复用历史专项目录。启动入口先用专属QLocalSocket请求旧主Demo正常退出；15秒仍未断开则拒绝启动第二份，不强杀。用户可从标题/DevData/Demo/runtime.json确认实际HEAD、PID、数据目录。

post-021-wpe/wpe2/wpf/qq/wpb继续保留为历史专项入口和证据，不默认同时运行。复杂复现/破坏性测试另用external-drop等独立库；发行候选仍在接近发布时独立验证，Demo通过不等同打包产物通过。本批不Push、不发布，Issue保持Open，#37不勾选。
