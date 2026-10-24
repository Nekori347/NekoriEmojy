# W-06 / #12 全局剪贴板导入

2026-10-24，dev/post-0.2.1，接管75a5385；源码d369a3b。已实现并完成必要机器验证，待人工体验，不Push/发布。

## 机制与入口

- services/import_hotkey.py：Windows RegisterHotKey(NULL, id, MOD_NOREPEAT | modifiers, vk)，绑定Qt主线程而不是主窗口HWND；QAbstractNativeEventFilter只转发WM_HOTKEY，QueuedConnection执行命令。无新增键盘Hook、剪贴板轮询或常驻线程。参考[Microsoft RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey)。
- 设置→交互→快捷键：默认启用Ctrl+Alt+V，可修改、禁用及通过现有默认值功能恢复。四语言已补齐。配置保存前注册新组合，成功才解除旧组合；占用失败保留旧组合和未保存的编辑，显示失败。保存失败时恢复旧配置/注册。启动失败会提示且在设置显示实际失败状态；不假报生效。Ctrl+V保留普通粘贴用途。
- main.py和固定Demo均在单实例判定/主程序初始化后安装一次；第二实例不注册。aboutToQuit解除注册，不依赖显示、最小化或隐藏生命周期，不编辑受保护main_window。
- ClipboardImportCommand→GalleryInterface.paste_clipboard_to→ClipboardService.get_data_from_clipboard→原ImportQueue/ImportThread/ResourceImporter。普通粘贴仍走同一解析/队列；没有新导入任务种类、去重算法或下载器。
- 全局命令显式ImportTarget(ROOT, None)，沿现有根层混排规则，不读当前分类/Relative Tab/选择来决定位置，不导航。文件URL优先于同源图片表示，文件/GIF/直接URL不统一转PNG；纯图片数据沿原QImage入口。

## 等待、重复与反馈

原批次集中重复比较/逐项决定/全部应用保持。后台来源且主窗口非活动时不创建决策窗，队列保持decision；用户主动打开激活Nekori后才展示同一批次窗口。无复制弹窗链，无自动跳过。等待/取消沿原任务身份；关闭、取消会解除等待。

隐藏时使用现有托盘反馈，显示时用原toast；成功、失败、取消和待处理重复项分别提示。仍在运行/下载/等待决策的同一全局请求不再受理新导入，MOD_NOREPEAT阻止按住键的自动重复；结束后允许再次主动导入并按原去重决策处理。

## 验证与边界

- Windows原生平台运行tests/test_clipboard_hotkey.py前6项及test_wpf_import.py：13项通过；新增直链GIF真实HTTP下载/保存独立1项通过，共14个不同目标。最后Ctrl+V限制后重验parser单项通过，不重复计数。
- Windows真实系统组合键输入：窗口可见、最小化、隐藏均收到；重复keydown不增加激活。实际RegisterHotKey冲突用独立进程占用验证，换绑后旧键可重新注册、新键仍占用，禁用和close释放。
- 真SettingsCenter控件/保存路径：配置冲突阻止保存，修改/禁用/重读配置正确。共享剪贴板命令验证文件+图片双MIME仅一次提交，QImage、URL、无效输入和活动任务重复触发。
- 隔离真实Gallery/Library：当前分类保持，纯图片新增到ROOT，原父分类混排不变。重复资源在后台无弹窗，激活后复用保持多分类关系；等待取消保留文件和关系。既有WP-F集中决定、部分成功/取消和任务身份7项相邻回归通过。
- 直链GIF通过本地HTTP服务走原DownloadThread入库，保存后仍GIF且2帧；无真实外部聊天客户端发送。不能据此宣称所有聊天客户端/网络来源或安装包已验收。
- 固定Demo保持DevData/Demo/Start-Demo.cmd及data；持续数据与顺序在重启前后核对。W-01七处原有未提交实验未编辑/未混入；T-07、#56、#24及其它工作包不修改。

人工验收：其它程序复制实际表情后按Ctrl+Alt+V，检查隐藏运行、托盘反馈、设置状态及重复项决策体验。Issue #12/#37保持Open、不勾选最终完成。
