# G-27 / #52：主图库回收站确认

2026-10-25，接管 `97c1fca`，源码提交 `3699239`。

**主图库已实际显示原有删除确认，并完成单张/批量确认与取消；已实现、机器验证、待人工验收。** 不关闭 Issue，不 Push、不发布。不是只有独立 probe 收到 CLSID。

## 产品与实现

维护者已批准“系统处理外拖副本后，由应用询问是否删除图库原件”，不再将是否需要该确认列为产品待决项。保留 `f21fa35`：外部标准文件格式只交付独立临时副本，不能移走受管理原件；内部资源与来源分类 MIME 保留。

当前 Qt/PySide6 6.11.2 不公开 IDataObject::SetData 的目标反馈，因此仅为主图库资源源端增加 `services/windows_resource_drag.py`。复用窗口库现有的 pywin32 COM 网关、Windows DoDragDrop 和标准 ImageList 拖动图像。没有新安装/升级依赖、没有自编平台插件、注入、Hook 或全局监控。分类节点和标签源端仍使用 QDrag，所有接收端仍使用原 Qt 事件和 Drop Contract。

1. EmojiCard 拖动开始时由 GalleryInterface 批量取得本次稳定资源 ID、Library 身份；与当前选择及后续 Relative 投影分离。
2. 原 QDrag 继续携带 MIME、Pixmap 与 hotspot；资源的 Windows 会话由局部 IDataObject/IDropSource 适配接收 TargetCLSID。内部二进制 MIME 按原长度交付，不加字符串 NUL。
3. CF_HDROP、Unicode/ANSI文本和 Qt 原有的文件URL表示都来自既有 `_files()` 临时副本提供器。内部排序不需要导出。原 Qt MIME 被销毁后，目标保留的数据对象仍可读取副本；原缓存七天回收规则不变。
4. **只以精确 CLSID_RecycleBin 识别回收站**；还要求正常释放、无取消、Logical Performed DropEffect 指示完成、实际交付了副本且没有准备错误。Move/Ignore 返回值不作为目标身份；不检查坐标、图标名或原件消失来猜测。
5. OLE 完整返回、原卡片与取消区清理后发出信号；GalleryInterface 用带 QObject 上下文的单次 GUI 排队调用，显示原来的 `dialogs.confirm`。不在 SetData、QueryContinueDrag 或 Shell Drop 内显示模态窗口。
6. `_batch_delete` 和回收站入口共用 `_delete_resource_ids`、ActionPolicy 及原 `StorageService.delete_images_batch`。确认前后按 ID 重新解析；使用已有批量读取接口，不新建分类索引/永久缓存或逐资源 SQLite 连接。真正删除时在原锁内再次校验 ID，防止路径被未确认资源占用。
7. 会话结束后冻结目标反馈；晚到通知不能影响下一个拖动。非 Windows、非原生窗口平台或缺少桥接能力时保留原安全 Qt 外拖，不猜测删除。

主图库以外的 QuickPanel 源端此次未接入新的确认回调，继续原来的安全副本行为；不得据此宣称所有资源显示入口都已完成该交互。当前实际原生验收覆盖主图库。

## 临时副本与提示

Windows 在目标身份反馈前已能读取 CF_HDROP 中的副本路径；TargetCLSID 不是可靠的预先否决接口。此前 Qt 对该格式返回 E_NOTIMPL 时系统仍会回收副本，不能用返回错误冒充撤销。

本轮不改变为未验证的虚拟文件传输，不查找同名回收站项目、不清空回收站。系统可能已经接收副本，取消 Nekori 确认并不撤回它。删除框四语言追加明确说明：

> Windows 回收站可能已接收拖放副本。此处确认是否删除图库原件；取消会保留原件，但不会移除回收站中的副本。

确认后，图库原件按原有全局删除业务进入回收站并删除记录与所有分类关系；因此可能同时存在先前副本和原件。取消只保证图库原件、记录和关系完整，不能描述为回收站没有收到文件。

## 实测中修正的两项接入缺陷

- **静止释放可能不结束**：OLE 的 grfKeyState 偶尔仍保持按下。采用 Qt 6.11.2 `QWindowsOleDropSource::QueryContinueDrag` 相同原则，在该回调内读取即时鼠标按键状态，并正常服务 Qt 事件；没有新增按键轮询线程或定时器。
- **Esc 后释放可能变成单击发送**：拖动结束已清理按下位置，但旧 mouseReleaseEvent 只看 `_is_dragging`。现在只有仍存在原按下位置的有效点击才触发选择/发送。复用原字段，不增加延迟发送、模拟点击或状态补丁链。原生补测已确认 Esc 不发送。

验证脚本也曾过早把 DragEnter 当作完成；随后以最终源返回及 Qt Drop 时间线核验。Root 专用投影没有普通分类的子标签，最后的悬停样例改为真实父节点下 A/B。没有为迁就样例修改产品导航规则。

## 验证结果

均为生成 PNG、独立配置与 Library 的真实 MainWindow，三个保护宿主模块从 Git HEAD 加载，不运行七处 W-01 实验。正式版和原始 Library 未操作。Windows 11、当前显示环境；不外推 Win10/DPI/全部客户端。

| 场景 | 实际结果 |
| --- | --- |
| 单张拖入真实回收站 → 取消 | 原有 NekoriDialog 可见；OLE 已结束；原件、资源记录、两分类关系及混排逐行不变 |
| 批量两张 → 取消 | 一次真实确认，取消后同上，无部分删除 |
| 单张 → 确认 | 原有删除按钮实际执行；一个原件及资源记录移除，全部分类关系清理，剩余顺序正确 |
| 批量两张 → 确认 | 一次真实确认，两个资源按原业务删除；无失效引用，剩余节点/资源相对顺序保持 |
| 普通 Explorer 文件夹 | 外拖完成，目标不是回收站；无删除确认，图库数据不变 |
| Esc | 修正后无删除确认、无单击发送、数据不变；输入状态恢复 NoButton、取消区消失 |
| 受控延迟文件接收端 | 返回后延迟读取副本成功，文件独立；无删除确认。未向实际聊天客户端发送消息 |
| 内部资源排序 | Qt接收原MIME、实际排序提交；资源/分类关系及文件不变；进程退出后重读顺序一致 |
| 标签停留切换后 Esc | 确实进入目标 Relative 分类；左树身份/展开/滚动不变；源卡片未错绑；无数据提交和确认 |
| 拖动投影与结束 | 既有缩略图/hotspot通过原生拖动图像显示；生成素材上的实际截图有投影；结束无残留模态/取消区 |

这些是不同阶段的有界原生证据，并非每项都重复执行在同一进程；确认与取消均连续进行了单/批量操作，另有连续文件夹/Esc/内部操作检查旧状态。初次滞留及 Esc 误发送均先保留失败证据，再针对性补测，没有把失败轮计成通过。

回归：34项主图库管理/外拖/标签落点/新增协议检查通过；最终补充批量ID读取、锁内身份核对及兼容文件URL后，14项直接相关检查通过（与前组重叠，不相加宣传）。新增检查含真实 Qt 确认按钮、取消数据完整性、过期 ID、错误 Library、晚到反馈、未完成/取消/准备失败不触发删除，以及异步数据对象生命周期。

剩余人工边界：维护者正常主图库体验；真实 QQ/Telegram 等聊天投放（本轮未真实发送）；Win10、其它 DPI；QuickPanel 确认接入未包含；本轮没有重建 Portable/Installer，上一轮38c2910候选包不含新功能。窗口/后续拖动响应正常的证据不等于整个宿主菜单长期稳定性验收，不借本轮关闭 #50。

## 定位与证据

- 源码：`services/windows_resource_drag.py`、`services/external_drag.py`、`EmojiCard.mouseMoveEvent/mouseReleaseEvent`、`GalleryInterface._resource_drag_snapshot/_recycle_drag_completed/_delete_resource_ids`、`StorageService.delete_images_batch`，以及四语言提示。
- 私有记录：`DevData/recycle-integration/first-native-results.json`（两种取消）、`confirmed-native-results.json`（两种确认/普通文件夹）、`compat-native-results.json`（Esc/延迟读取/内部排序）、`product-results.json`（最终标签切换）、`restart-persistence.json`。初始未执行或失败项未计通过。
- 默认人工入口仍为 `DevData/Demo/Start-Demo.cmd`，不重置持续数据与排序。
- 既有研究与原始出处：[候选/原生研究](POST_0.2.1_RELEASE_CANDIDATE.md)。关键原生释放行为参见 [Qt 6.11.2 qwindowsdrag.cpp](https://github.com/qt/qtbase/blob/v6.11.2/src/plugins/platforms/windows/qwindowsdrag.cpp)；COM 网关与所有权复用 [pywin32 IDataObject](https://github.com/mhammond/pywin32/blob/main/com/win32com/src/extensions/PyIDataObject.cpp)。
