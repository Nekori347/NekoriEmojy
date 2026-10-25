# HSV 拖动定向调查（2026-10-26）

**仅调查，未修改颜色业务、节流、线程或主题状态模型。** 基线 `aa0da3a`；脚本 `tools/profile_hsv_interaction.py` 复用现有隔离 Qt fixture。5 个生成资源，Settings 880×680，offscreen，每条路径 72 次变化，8ms 输入间隔，开启 cProfile；数字包含探针成本，不等同实际桌面拖动延迟或大型图库结论。

## 真实调用链

- 色谱：`HSSpectrum._pick → changed → AccentColorPicker._spectrum_changed → set_color`。
- HSV 滑条：`SoftframeSlider.setValue → valueChanged → _hsv_changed → set_color`。
- `set_color` 阻断反馈信号后同步三个 slider、三个 number box、HEX、色谱选点及比较色块，再发一次 colorChanged；没有等待全局主题完成才更新局部颜色。
- `AccentRow.choose_color` 立即更新本行色块/文本，复用已有 40ms 单次合并计时器发 changed；`SettingsCenter._stage` 记录 pending/preview_values，实时预览开启时发 accent_preview，并重启已有 160ms 最终主题提交计时器。
- `MainWindow.on_settings_changed('accent_preview') → UiTheme.preview_accent` 只通知局部绘制；`accent_color → _update_background → UiTheme.refresh` 做完整样式/主题提交。两者不同，不应把最终提交耗时当作每帧 HSV 解码。
- 脚本重放同一个 preview_accent/refresh 分支，含生成图库与设置页面；没有实例化主窗口材质、QuickPanel 或 DWM，不能据此覆盖它们的耗时。

## 测量（ms）

“本地”包含值及信号同步；“至绘制”再包含紧接着的一轮 processEvents。最终全局提交单列，不混入逐次局部数字。

| 实时预览 | 路径 | 本地 p50 / p95 / max | 至绘制 p50 / p95 / max | accent_preview / 最终提交 |
|---|---|---|---|---|
| 关 | 色谱 | 0.761 / 1.232 / 1.634 | 3.873 / 4.937 / 5.492 | 0 / 0 |
| 关 | HSV 滑条 | 0.786 / 1.151 / 1.727 | 3.954 / 5.068 / 5.884 | 0 / 0 |
| 关 | 已有色块 owner 更新 | 0.384 / 0.731 / 1.681 | 2.374 / 3.280 / 5.486 | 0 / 0 |
| 开 | 色谱 | 0.736 / 1.162 / 2.428 | 3.875 / 4.944 / 7.027 | 22 / 1 |
| 开 | HSV 滑条 | 0.745 / 1.200 / 1.561 | 4.051 / 5.038 / 5.640 | 24 / 1 |
| 开 | 已有色块 owner 更新 | 0.369 / 0.876 / 1.377 | 2.352 / 3.737 / 4.348 | 20 / 1 |

色块 owner 路径直接更新 AccentRow，再经过同一合并计时器，用于分离 HSV 字段同步的附加成本；不是另一个已实现的颜色模型或物理鼠标测试。

三次最终完整主题提交分别 **179.663 / 194.071 / 213.817ms**；普通 accent_preview 发出约 0.09–0.22ms。cProfile 观察到三次 refresh 合计 0.588s、setStyleSheet 256 次合计 0.432s；统计有包含关系，不相加。局部更新、全局 repaint 和重设样式必须区分。

原始结果与调用统计仅在 `DevData/host-regression/hsv/result.json`、`profile.txt`，可重跑脚本；无私人资源、目录或凭据。

## 结论与后续最小候选

1. 本次小样本未发现 HSV 独有的长时间同步门槛；HSV 字段同步比 owner 色块多约 0.4ms。不能用它否认真实桌面/高负载反馈。
2. 已确认最终完整主题刷新存在约 180–214ms 同步成本，且三条路径共享；优先候选应在 UiTheme 的最终样式提交责任层核查重复工作，而非增加 HSV 节流或线程。尚未实施。
3. 若拖动中间停顿超过现有 160ms，可能进入完整提交；这是调用链推断，本轮没有采集真实高负载拖动来确认发生频率。
4. 6 条路线都断言保留最后颜色；已有 `test_accent_preview_cancel_accept_save_discard` 也通过，覆盖取消、接受、保存及放弃。没有丢弃最终颜色来换取数字。
5. 实时预览开关与更多按钮均高 32px，但目前在导航区域不同的行；开关 Checked 使用 ButtonPaint 的 selected 表面，不是 Hover。眼睛/闭眼及未来弱线框/对齐要求留作 UI-A 依据，本轮未顺带改布局。

后续仍需真实桌面／高负载环境验证。没有修改 W-01/W-03、T-06/T-07 或动效、材质开关。
