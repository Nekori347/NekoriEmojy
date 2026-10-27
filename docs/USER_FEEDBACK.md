# 常驻反馈与建议 · 2026-10-27

新增正式基础功能，不是Beta专属。基线4d58539，分支dev/post-0.2.1，源码及模板提交 **7e4c40d**。已实现、机器/实际Qt窗口验证，待维护者体验，尚未对外发布；记录提交及最终HEAD见CURRENT/#37。

## 接入与边界

- GalleryInterface._show_tools_menu：侧栏底部应用与工具菜单增加一个既有Action，不增加子菜单。
- AboutInformation：现有关于卡片内增加“反馈与建议”及“复制环境信息”两个既有PushButton，不新增页面或弹窗。
- 两处反馈都调用components/user_feedback.open_feedback，通过既有QDesktopServices.openUrl交给系统默认浏览器，地址固定为https://github.com/Nekori347/NekoriEmojy/issues/new/choose，无附加本地信息、查询参数、OAuth/API提交或自动上传。
- 打开失败才复制公共链接，用既有轻提示说明无法打开浏览器且链接已复制；不弹模态错误。该必要失败提示补齐四语言；三条正式文案精确采用本轮映射。“反馈与建议”复用原键，繁中/日文改为本轮定稿，没有重复键或重复入口。
- 关于页仅点击复制才读取批准环境字段。版本复用current_version，通道只复制version.json实际channel字段（不使用version_info默认development）；Windows来自platform，语言来自当前i18n，缩放来自当前窗口devicePixelRatioF，开发提交号复用现有version_info且仅源码检出环境有值时加入。不可取得的版本/通道/缩放/提交省略。
- 复制信息采用固定技术字段名：NekoriEmojy、Channel、Windows、UI language、Display scale、Development commit。没有用户名/用户路径、Library位置/资源、网络凭据/代理、配置原文、数据库/任务历史或日志。未新增诊断采集器、后台线程、数据库、设置或网络监听。

## GitHub表单

新增.github/ISSUE_TEMPLATE/01-bug-report.yml与02-feature-request.yml。使用YAML 1.2兼容的JSON流式语法，可用标准库校验结构，不安装额外解析依赖。Bug仅问题描述必填，其余四项可选；建议仅建议内容必填，其余两项可选。中英双语字段，欢迎任意语言，无强制搜索声明/环境清单或自动标签。没有config.yml禁用空白Issue，保留GitHub默认行为。

**模板仅在本地提交；进入GitHub默认分支后才对公众生效。** 未Push，不能把线上暂未显示模板算作本地失败；本轮也未测试登录或创建测试Issue。

## 最小验证

- 34项直接相邻测试通过（user_feedback、排序文案锁定、共享输入、通知交互）；随后8项直接功能/翻译检查重验通过，补核版本元数据缺失不会伪造字段或使复制失败。重叠测试不累加总数。
- 四语言真实菜单Action与关于页两个按钮持续刷新，12个入口绑定值逐项对应；复制成功的四语言另由直接功能测试核对；两入口各四语言8次实际信号路径均调用同一准确URL。单元测试还验证打开反馈不触发环境读取/复制、失败只复制公共URL、复制信息白名单/缺失字段、两表单结构及唯一必填项。
- 固定Demo实际Windows Qt运行源码7e4c40d，PID19808；真实菜单/关于页桌面截图各四语言共8张。通过实际复制按钮核对：0.2.1、元数据明确stable、Windows11实际Build、当前语言、100%缩放、开发提交7e4c40d1。不是虚构Stable/Beta或Git SHA。
- 在真实应用中对两入口记录URL后恢复原方法，实际调用一次系统默认浏览器，openUrl返回True。该结果只表示系统接受打开请求，不声称GitHub登录/提交或线上新模板已验收。失败路径采用受控返回False验证，没有更改系统浏览器设置。
- 原始截图/运行结果仅在DevData/ui-refresh/live-feedback本地私有保存，未进入Git或上传Issue。截图为真正可见Qt窗口桌面抓图，不是离屏控件或模拟图。快速切换语言时上一次短提示可能尚在其显示周期内，截图中旧提示不用于证明新一次复制反馈；每次点击生成的新反馈及按钮翻译分别核对。
- 无真实资源导入、导出、删除、下载或OCR任务；全部7表逐行不变（132资源、54分类、433混排等）。正式版、原Library/Suzu未操作，七处W01原差异未改未暂存，W02暂停、W03未启用。

截图及验证后关闭测试菜单/设置窗口，恢复原语言/窗口层级；临时入口禁用，最后通过固定脚本正常重启。最终Demo版本与PID见CURRENT。未Push、打包、发布或关闭Issue。停止本轮，等待人工体验。
