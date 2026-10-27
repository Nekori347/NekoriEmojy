# 分类条线性视觉与交互修订

最新微调（2026-10-24，32b23a6）：Tab顶部线继续绑定content_tab_rect，将两端安全内缩从3px改为8px，宽度max(0,主体宽度-16)，顶部位置/动画/翻页不变。标签栏7项目标通过，窄主体零宽保护补充后单项重验通过；仍待人工体验。本轮选择逻辑和进度仅只读调查，无相关功能修改。

## 当前规格：结构线原位变色、中性选中底面及Tab主体线宽

2026-10-24；本节为最新用户规格，替代下方旧合同的永久Accent竖线/Selected底边实线。分类源码e9ce7e8；标签源码3de1b1a。

- 已确认：上轮NodeCard按Selected切换横线起点及Y至底边，且没有本次要求的中性Selected表面。现在所有状态保持同一字体与布局，横线仅在名称和计数间居中绘制一次；Default双结构线为border_soft，Hover/Selected原位变accent()。Selected使用与EmojiCard同源surface_alt、alpha155的5px圆角承托，范围覆盖行内主要内容周围，不增加30px行高。Focus/Pressed仍独立；Sticky继承同一绘制与现有真实选择同步，容器渐变/push-off/归属未改。
- 拖动：复用现有QDrag/NODE_MIME/热点和Drop Contract，投影表面改为同一surface_alt（alpha230）。用户授权后实测Windows原生拖动：GetCursorInfo为可见，GetIconInfo实际游标bitmap429×51、热点74/18；Esc返回IgnoreAction、来源结束且数据不变。本轮未复现当前源码缺少投影，不以仅生成Pixmap宣称修复；不添加第二套overlay，辨识度与跟手仍待用户。原生结果DevData/category-linear/visual-native/result.json。
- 标签：TabStrip._target_line旧逻辑最多38px，错误独立于主体；改为content_tab_rect左右各3px安全内缩、顶部Y9，自动排除位置标签分隔间隙。保留既有动画、真实翻页按钮、可见区裁剪及几何同步，不恢复旧翻页逻辑。

验证：19项分类状态/复用/Qt投影/落点实际提交、Sticky嵌套/push-off/锚点、Tab切换/滚动/翻页/动画/缩放及工具栏测试通过。新增深浅主题与自定义Accent检查保证选中灰底持续、双线不移位、不出现第二条底边线；单像素横线对齐半像素以保证清晰。额外Windows平台2项真实Qt控件状态与Sticky折叠检查通过（与19项重叠，不累计独立测试数量）。日志visual-state-tests.log、visual-windows-tests.log。

当前机器验证未替代用户视觉签收；实际灰底强度、原生投影跟手及其它系统/DPI仍按人工边界保留。固定Demo/持续data不重置；七处W-01实验SHA256一致，T-07和无关业务不改，#55/#45/#24保持Open，不Push/发布。


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
