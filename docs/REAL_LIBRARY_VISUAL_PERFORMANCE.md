# GUI 长尾、视觉开关与缓存效率

2026-10-25；接管 `dfbd3e4`，分支 `dev/post-0.2.1`。延续
[真实库调查](REAL_LIBRARY_PERFORMANCE.md)和[三阶段修复](REAL_LIBRARY_PERFORMANCE_FIXES.md)，
不重开安全审计，不改窗口移动、T-06、T-07、QMovie 策略或指定帧算法。

## 实施结果

| 提交 | 内容 |
| --- | --- |
| `189182a` | `ui_animations_enabled=True`；外观→主题增加原有 SwitchRow。有限 UI 过渡统一经 visual.start_animation，关闭时 duration=0，保留 Qt 终值与 finished。保存时结束正在运行的 UI 过渡；任务装饰转为静态，但任务状态/进度仍更新。 |
| `185bf87` | `window_acrylic_enabled=True`；同页 SwitchRow，使用 Pending/Save/Discard。保存后重启生效，原反馈组件提示需要重启。启动 visual.configure 复用现有 NEKORI_OPAQUE_MATERIAL 进程级路径，实际向 Win32 提交 Accent=0；不改系统设置、宿主和材料文件。 |
| `f4a3408` | 增量 EntryModel 已取得的 nodes 快照继续供路径、返回子分支提示和 Relative Tabs 使用，避免再次读路径/子节点/标题。Tab 标签及当前项都未变时，不重复启动 250ms 呼出动画。无永久缓存和新选择状态。 |

两行使用现有高度、说明、强调色、未保存标记及四语言资源；无新页面、下拉框或数值预算设置。
不加入 PREVIEW_KEYS，点击不写盘、不实时切换材质；Save/Discard 与现有设置一致。

动效责任分为：按钮 Hover/开关滑块/指示线等装饰，标签面板及工具参数区的几何过渡，
选择/折叠/任务状态等业务提交，以及 QMovie 等内容播放。开关只影响前两者；已接入现有
按钮、导航、标签、Chevron、面板、设置组、工具参数区、提示淡入和卡片淡入入口。
原生窗口本身没有应用额外编写的显隐动画；Windows 自己的最小化/还原效果仍归系统管理，
本开关不修改全局 Windows 动画设置。悬停预览的等待时间也不是过渡动画，不作修改。

VirtualGallery 的已有导航动画避让仍在：开启时可能等侧栏指示动画结束；关闭时动画直接
结束，只剩原有下一事件轮次及 8ms 准备批次。没有移除分批机制或重写虚拟图库。

## 长尾归因与局部修正

修正前同一次增量刷新仍重复构造导航上下文。三次同步回调的聚焦 profile 中，
`_rebuild_context_strip` 累计约 106ms，完整回调约 433ms；修正后对应累计约 39ms，
回调约 308ms，SQLite 连接 27→18、execute 102→81。自然负载不恒定且 profile 有开销，
不用这个差值承诺固定提速比例。定向测试先捕获重复路径读取，再验证快照复用和 Tab 不重启动画。

剩余主要责任仍是 `EntryModel.sync → Index.resource_records/_resource_row` 的路径解析/查询、
计数与标签投影，以及分批控件准备/绘制；最终默认轮三次 EntryModel.sync 累计约 161ms，
`_resource_row` 累计约 122ms，`_rebuild_tag_panel` 约 35ms（存在嵌套，不能相加）。
没有足够证据将剩余全部长尾归于动画或毛玻璃，未改动查询身份规则、事务或排序合同。

## 有效视觉 A/B

同一隔离真实快照：4175 资源、122 节点、8475 关系；501 项与 51 项分类，缩略图 60px。
原库只读，正式进程不参与写测试。现有磁盘缩略图预热，每次新进程，内存缓存从启动构建；
不是冷磁盘基准。使用当前 PySide6 6.11.2 / Qt 6.11.2 / Windows 11，不使用新版专有 API。

| 指标 | 默认 Acrylic+动效 | 仅关闭动效 | 仅关闭 Acrylic |
| --- | --- | --- | --- |
| 首轮可见卡片全部绑定 | 941ms | 809ms | 1112ms |
| 预热回访可见卡片全部绑定 | 586ms | 324ms | 558ms |
| 预热导航阶段 Qt Paint 事件数 | 702 | 463 | 676 |
| 三次增量同步回调 | 109 / 105 / 92ms | 104 / 113 / 97ms | 109 / 111 / 113ms |
| 导航/唤醒/预览心跳 p50/p95/max | 10.2 / 29.5 / 111.2ms | 10.1 / 25.0 / 144.8ms | 10.2 / 25.0 / 120.5ms |
| 预热导航阶段进程 CPU 累计 | 0.953s | 0.922s | 0.938s |
| 最后工作集 | 509.8MiB | 510.0MiB | 511.3MiB |

“全部绑定”包括多次 8ms 批次、事件循环及等待，并非 GUI 连续阻塞这么久。Paint 是 Qt
控件绘制事件计数，不是 DWM 呈现帧数。关闭动效减少本轮导航绘制和等待，但未消除同步
回调长尾，心跳最大值也不单调改善。纯色没有显示稳定的 GUI/CPU/内存收益，保持默认开启。

本轮早段 25 秒自然样本可用内存 8045–8607MiB、CPU 42.7–77.0%；不是反馈的物理内存
超过 80% 情景，也不是各轮严格同步的恒定压力。不模拟耗尽内存，不据这些数据判断硬缺页因果。

采样校正：早期 cards_ready 等了整个缓冲区且有截止，不能当可见卡片完成；最终改为检查
真实可见 occurrence 的绑定。早期 QTest 轮询中，中间帧缓存等待未在 5 秒内完成；切换为
真实 QEventLoop 后，同一 5 秒界限得到完整异步结果。最终视觉组也采用 QEventLoop，避免
Python 后台任务被测试等待影响。旧原始文件保留但不混入上述表格；连续三次无让出的旧
profile 心跳也不当成生产的一次 GUI 阻塞。

## 材质、窗口与验证边界

受保护 `materials.py/main_window.py/window_shell.py` 没有修改。设置只在启动读取，借助
已有本进程不透明路径，不实时预览、不重建 HWND、不改 Mask/圆角/窗口按钮策略。
开启仍由原系统透明偏好、高对比和平台支持判断；诊断环境变量仍可强制关闭。

Win11 实际主窗口、SettingsWindow、ToolWindow：Acrylic=4/背景 Alpha=12；关闭时实际
原生 Accent=0/Alpha=255。分别完成最大化、还原、隐藏重显、最小化恢复及 HWND 恒定检查，
Qt/Win32 最大化状态一致，设置/工具内容区域跟随窗口。

用户授权的原生输入：先因前台检查失败而停止，未发鼠标；测试脚本一次 AttachThreadInput
激活后立即解除，并在每个输入落点检查真实顶层 HWND。最终两种材质×三个窗口的原生
右下角缩放都取得 +30/+20 位移，最大化/还原按钮有效。标题拖动仅纯色主窗口取得约
+70/+36 的有效位移，其余样本位移为零，不能据此比较拖动性能，也不归因为 Acrylic 故障。
没有继续反复争抢鼠标，完整标题拖动与边缘视觉仍需正常使用体验。

两轮末尾六次 DwmFlush 往返分别约 9.9–18.5ms 与 3.2–12.3ms；只能描述该调用等待，
不是单窗口 FPS、光标跟随误差或合成 CPU。窗口阶段进程 CPU 累计并未随纯色一致下降。
没有 ETW/GPU 呈现跟踪，不能宣布 Win10 W-03 修复。W-03 候选仍未启用。

## 缓存盘点和取舍

- GalleryThumbnails 与旧 ThumbnailCache 使用同一全局 QPixmapCache，总默认上限 128MiB；
  并非各自 128MiB。两个命名空间可能为同一资源保存不同尺寸/帧的表示；QLabel 显示缩放
  表示、QImage 解码中间量、QMovie、图标及 Qt 分配器也在该预算之外，所以不是进程内存上限。
- Gallery 磁盘 PNG 由库身份/资源 ID/文件修订/尺寸档/帧索引决定，当前没有大小或年龄硬预算。
  私有测试目录约 635 个、13.7MiB。仅记录现状，不借此建立清理器或第二缓存。
- 视口按可见优先及上下缓冲区请求；两条已有解码线程，离开视口撤去待开始请求，已运行任务
  完成后核对卡片身份。QPixmapCache LRU 淘汰，原 idle 不再清空；本轮没有改预算/线程数。
- 默认有效组回访已有 251 次内存命中，额外源 GIF 解码为 0；隐藏重显后这些计数不再增加。
  可能仍发生必要重绑，不能将重绑直接算作重解码。
- 真实 20.4MB、671×770、170 帧 GIF 的第 85 帧：后台源解码约 730ms，可靠附着约 737ms；
  清除该实验内存项后磁盘 PNG 约 2.8ms；再读内存约 0.15ms。三次图像相等，源解码计数保持
  1，磁盘/内存分别命中 1。说明现有非零帧缓存有效，不需要每次重解原 GIF。
- 64/256MiB 探索均未得到稳定的长尾收益，准备/命中数量也有差异。64MiB 轮工作集较小不
  足以独立证明预算效果；256MiB 没有体现值得支付的稳定收益。保留 128MiB，不新增 MB 设置
  或自适应管理器。系统压力→缓存淘汰→输入延迟的因果仍未取得，不能排除真实高压力问题。
- QMovie 继续 CacheNone，每次预览隐藏时停止/解除/删除，静态 pixmap 也释放；关闭 UI 动效
  仍观察到 GIF 帧更新。没有静态化资源、改 CacheAll 或改 Pillow 指定帧算法。

## 验证、证据及人工入口

设置 5 项定向测试通过，包含 Pending/Save/Discard、持久化、运行中终态与 finished、实际
GIF 继续播放、两种主题和四种语言。标签折叠/翻页/通知栏 41 项通过；快照与增量/Tab 14 项、
G-16/导航及菜单图标 7 项通过（组合有重复，不相加虚报不同用例数）。
固定 Demo 持续数据和完整混排顺序在更新前后核对；不增加长期专项 Demo。

私有证据：`DevData/real-library-perf/visual-verified-*-events.json`/profile、
`windows-native-final-*-events.json`、`frame-cache-verified-events.json`、
`system-visual-options.json`。仅隔离脚本新增测量，正常程序没有常驻性能采样。

人工入口仍为 `DevData/Demo/Start-Demo.cmd`；开关在外观→主题。待人工视觉与正常操作验收，
特别是原生拖动、其它 DPI/Win10 和自然高内存压力。本轮不 Push、不发布、不关闭 Issue。

参考策略与实际 API：[Qt 6.11 动画](https://doc.qt.io/qtforpython-6.11/PySide6/QtCore/QAbstractAnimation.html)、
[Qt 6.11 QPixmapCache](https://doc.qt.io/qtforpython-6.11/PySide6/QtGui/QPixmapCache.html)、
[Windows 独立动画/透明开关](https://support.microsoft.com/en-us/accessibility/windows/make-it-easier-to-focus-on-tasks)、
[DWM 性能边界](https://learn.microsoft.com/en-us/windows/win32/dwm/bestpractices-ovw)、
[KDE 效果分组](https://docs.kde.org/stable_kf6/en/kwin/kcontrol/kwineffects/index.html)、
[Gwenview 低资源取舍](https://docs.kde.org/trunk_kf6/en/gwenview/gwenview/configadvanced.html)。
仅借鉴分离视觉偏好、缓存命中与资源成本的策略，未引入外部架构或依赖。
