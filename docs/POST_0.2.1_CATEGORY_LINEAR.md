# 分类条线性视觉与交互修订

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
