# 分类条线性视觉与交互修订

## 最新合同修订：主题身份、真实选择与拖动投影

2026-10-24；源码f69d482。上一轮615ab47未通过用户视觉验收，本节替代“点击后无持续选择提示”的不完整规格，历史记录保留作为上下文。

- 身份装饰：NodeCard._paint_row恢复统一动态accent()的2px/18px短竖线，主题变化沿原theme信号刷新；普通条/Sticky共用。
- 状态：Selected仍来自原selected_keys→set_selected，不新建模型。Selected用固定内容起点的2px主题色底部实线与稍高字重；Hover/Pressed仅增强单条中性结构线，不能盖过Selected。无整行选中填充；键盘焦点为独立点线轮廓。保持默认30px、较大图标自适应及Chevron/主体原有语义。GalleryInterface._sync_command_bar补齐Sticky在选择提交时的即时状态同步，解决不滚动时代理显示滞后；复用仍清理临时Hover/Pressed。
- 拖动：此前抓取宽标题缩入72×72且热点固定36/36，造成投影几乎不可辨认。现在复用图片的Qt QDrag/pixmap/hotspot机制和原NODE_MIME/统一Drop Contract，NodeCard.drag_pixmap以同一内容画法生成最大420px宽、实际行高的中性半透明标题；省略无交互意义Chevron，热点取按下位置并约束在投影内。来源绘制45%透明，finally恢复；Chevron不建立拖动起点。未改排序、归属或投放引擎，Sticky仍不启动拖动。

验证：17项分类状态/Sticky/图标/WP-B定向通过；15项管理模式/外部原件保护相邻回归通过；新增分类Before/After/Into/Append反馈和实际顺序/父子提交1项通过，共33个不同测试目标。新建节点样本最初错误使用快照刷新，改用现有增量刷新后单项通过，未因此修改产品刷新架构。已有pos()弃用警告不扩展处理。

Windows Qt实际控件：contract_states.py完成Default、Hover、Selected、Selected+Hover、Sticky+Selected、push-off、嵌套真实折叠/锚点、自定义accent、深/浅主题、48px图标及780px窄窗口截图。单控件进程级QT_SCALE_FACTOR=1.5实测DPR1.5/56px逻辑行高；不冒称系统全局DPI切换。

拖动Qt投影及热点（428×38含透明边距，控件测试热点64/16）与来源45%绘制、Ignore/Move返回收尾已验证。随后用户授权独占鼠标，Windows真实系统指针三次拖动：Esc取消、工具栏无效落点释放均返回IgnoreAction，原顺序/父子关系不变且来源拖动结束；合法INTO显示独立归入轮廓，释放后分类真实parent_id更新至目标，已只读重开SQLite确认。原生热点74/18，截图native-escape/native-invalid/native-into.png及native-result.json。成功投放后的专项采样最初仍查询已从源列表移出的行而StopIteration，因此第三次返回值未保存；不重跑无收益场景，改以数据库父子结果确认实际提交，不把采样脚本错误作为产品缺陷。截图捕获不包含系统拖动图层，另提供实际QDrag pixmap native-projection.png；实际跟手程度与颜色辨识仍待用户签收。早期无系统输入的OLE计时取消实验已停止，无产品补丁。

截图：DevData/category-linear/contract/{default,hover,selected,selected-hover,sticky-selected,sticky-selected-hover,dragging-source,drag-native-pixmap,dark-custom-selected,large-icon,narrow-large-icon,nested-selected,push-off,dpi-150-large-selected}.png。QDrag投影图是实际生成的Qt pixmap，不是屏幕原生跟随轨迹截图。

七处W-01实验哈希仍一致；T-07及Sticky归属/push-off算法未改；#55/#45仍Open、未人工签收。固定Demo与持续data保持；无Push/发布/正式数据改动。

## 上轮交付记录（尚未通过人工验收）

2026-10-24；dev/post-0.2.1；源码615ab47；G-24 #45及独立视觉需求#55。已实现/机器验证，待人工验收。

## 原因与修正

吸附层原先实色fillRect在圆角高亮外暴露矩形，不涉及窗口轮廓或DWM。NodeCard将业务is_selected画成持续填充，正常模式点击会保留该选择身份；另已捕获虚拟节点复用继承旧Hover。不能仅将问题解释为Focus。

NodeCard保留业务选择身份，删除整行选择/Hover填充。统一图标、标题、单横线、计数和箭头布局，默认22px图标对应30px行高；用户放大图标时保留实际尺寸并增长行高，不更改资源卡片网格。Hover仅强调原横线，Pressed释放即结束，键盘焦点以标题下方点线区别。复用/隐藏清理临时状态，显示及移动边界同步当前命中，不使用轮询或每帧全库遍历。StickyCategory改为中性透明渐变并复用同一绘制，不更改归属、push-off、折叠与锚点算法。FlowIndex与控件共享行高函数。

## 验证与证据

`tests/test_category_linear.py tests/test_wpc_icons.py tests/test_sticky_category.py tests/test_tree_collapsed_selection.py tests/test_management_mode.py`：24 passed（65.83秒），仅已有Qt pos弃用警告。包含普通/管理模式点击释放、复用、键盘折叠、独立图标尺寸、吸附嵌套/push-off、左树折叠选中、管理及安全取消相邻回归。

Windows实际Qt控件使用DevData/category-linear/windows_states.py在专项隔离数据中验证；WINDOWS_LINEAR_PASS windows，结果windows-result.json。使用Qt输入事件，未占用用户系统指针，不能等同真实鼠标及人工审美验收。普通/吸附行高均30，底部透明像素、真实折叠和锚点通过。

完整图库截图均位于DevData/category-linear：normal-default.png、normal-hover.png、normal-pressed.png、normal-released.png、normal-manage-released.png、sticky-default.png、sticky-hover.png、sticky-released.png、push-off.png、nested-sticky.png、nested-collapsed.png。

## 交付边界

默认验收入口仍DevData/Demo/Start-Demo.cmd，持续data不重置。专项windows-data仅为可丢弃测试数据，不成为第二主Demo。七处原W-01实验SHA256逐项保持（protected-before/after.json）；T-07未改。Win10、其它系统DPI及深色主题视觉未做本轮实际验收。中性渐变透明度、紧凑密度及焦点提示仍待用户体验。#45/#55保持Open，不勾验收、不Push/发布、不修改真实库。
