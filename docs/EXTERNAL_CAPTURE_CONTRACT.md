# E-01 / #36：浏览器采集内部接收与预分类契约

2026-10-24；核对基线 `243f7ac`。状态：契约预留、待人工审阅；**没有实现外部接收端或浏览器采集功能**。以下 JSON 是未来内部适配层的语义约定，不是当前可调用 API。传输、认证和用户授权由实际接入阶段确定。

## 1. 当前能力与缺口

| 当前责任层 | 已有能力 | 尚未具备 |
| --- | --- | --- |
| `services/resource_import.py`：`ImportTarget`、`ResourceImporter.file/image/paths` | 单目标节点、可选混排插入位置；文件、QImage、目录；现有验证、编码与去重 | URL 下载入口、逐项多分类/标签请求、外部请求身份 |
| `fluent_ui/components/import_queue.py`：`ImportQueue.submit` | 一批 sources + 一个 ImportTarget；生成任务 ID；串行 worker、进度、取消、T-09 集中比较及 T-06 检查点 | 调用方 request_id、逐项预分类/标签参数、完整 item_id→资源结果映射 |
| `fluent_ui/views/gallery_view.py`：`ImportThread`、`DownloadThread` | worker 获取 HTTP(S) 图片后交现有 importer；临时下载清理 | 持久网络重试来源、网页采集、外部 URL 接收的安全与容量约束 |
| `services/clipboard.py`：`decode_mime_data`；`GalleryInterface.paste_clipboard_to` | MIME 优先选一类来源（文件、HTML 图片直链、图像、网络 URL/文本），再提交原队列 | 统一外部结构化接收接口；MIME 的 URL 识别不等于已验证图片内容 |
| `services/library_index.py` | 库 ID、稳定节点/资源 ID、同父级名称唯一、多分类成员关系、混排顺序；`assign_memberships` 批量关联 | 对外分类层级路径解析协议 |
| `services/storage.py`：`apply_tags/parse_tags` | 现有资源标签增删与去重；标签字符串以空格分隔 | ImportQueue 随项提交标签、采集来源 URL 持久化 |

支持后缀见 `StorageService.SUPPORTED_FORMATS`：PNG/APNG、JPEG、GIF、WebP、WebM、TGS、BMP、TIFF；最终仍取决于现有解码器/工具及实际内容。采集端交原文件/直链，不先统一转 PNG。Nekori 现有存储可能规范化静态格式，动态图沿既有编解码规则；不承诺字节原样保存。

现有下载只检查 Content-Type/部分后缀再读入响应体，有 10 秒请求超时，**未提供明确响应体大小上限**；不能据此宣称外部 URL 已安全接入。实际接入须在同一下载责任层确定大小及网络目的地/重定向政策，保留 importer 的实际内容验证。本轮不增加下载器或安全框架。

## 2. 最小请求结构（version 1）

| 字段 | 语义 |
| --- | --- |
| `version` | 固定为 1；不认识的版本拒绝 |
| `request_id`、`source` | 调用方非空请求标识、来源标识，例如 `browser_capture`；不是 ImportQueue task ID |
| `library_id` | 当前已打开库的稳定 ID；不允许通过请求打开/切换任意路径的库；不匹配拒绝 |
| `items` | 非空数组，按请求顺序；每项有本请求内唯一 `item_id` |
| `items[].input` | 二选一：`{"kind":"local_file","path":"绝对文件路径"}` 或 `{"kind":"image_url","url":"HTTP(S)图片直链"}`；此版本不接收目录、内存字节或任意网页 |
| `items[].source_page_url` | 可选原网页 HTTP(S) URL，只作来源说明，绝不作为下载地址；现有模型未持久保存，未来不得声称已存档 |
| `items[].categories` | 必填非空数组；每个引用仅选 `{"id":"稳定节点ID"}` 或 `{"path":["父级名称","子级名称"]}`；显式根层为 `{"id":"__library__"}` |
| `items[].tags` | 可选字符串数组，默认空；追加到实际接受资源，不替换原标签 |
| `allow_create_categories` | 必填布尔值；仅允许创建 path 中不存在的层级，不修复失效 ID |

同一库、同一来源和 request_id 构成未来接收端的请求身份：本进程仍保留请求映射时，同内容重交返回原任务映射；不同内容重用 ID 返回 `request_conflict`。当前队列没有该映射，需未来适配层实现；本轮不建永久去重表。跨重启或映射释放后无请求级 exactly-once 保证，仍必须经过资源去重/用户决策；调用方不能无条件自动重发不明结果。

分类 ID 只在指定库内有效。path 从 ROOT 逐级按去除首尾空白后的完整名称解析，匹配当前同父级精确名称规则，不做全库名称搜索、模糊匹配或以 `/` 拆名称。相同名称在不同父级是不同身份；仅给末级名称找不到唯一明确路径时返回错误，不能回退 ROOT。显式 ROOT 与其它分类不可并列，避免把全库投影误当独立分类关系。

多个分类是同一资源的成员关系并集，不复制物理文件、不移除已有关系。请求没有排序参数：新成员按请求顺序追加至各目标混排流，已有成员不重新定位，既有节点/资源相对顺序保持。目标在执行前失效则该项失败，不改投其它节点。允许创建时，已存在父级内按现有创建/复用规则处理同名竞争，不自动改名。

标签去除首尾空白、去重，保留大小写语义；空标签或内部含空白的标签拒绝为 `invalid_tag`，避免与当前空格分隔存储冲突。复用已有资源时，追加分类/标签会影响该资源在所有视图中的同一身份，不生成私有标签副本；跳过不追加任何关系。标签词汇展示仍走现有标签责任层，不直接改写数据库。

## 3. 两个代表性请求

以下 ID 是说明用占位值，需替换为目标库真实 ID；第二例须有对应父级或明确允许创建。

单图片，指定一个已有分类：

```json
{
  "version": 1, "request_id": "capture-001", "source": "browser_capture",
  "library_id": "example-library", "allow_create_categories": false,
  "items": [{
    "item_id": "image-1",
    "input": {"kind": "local_file", "path": "C:\\Capture\\smile.gif"},
    "source_page_url": "https://example.com/post/1",
    "categories": [{"id": "example-node-smile"}], "tags": ["开心"]
  }]
}
```

批量图片，不同分类/标签，第一项有多个成员关系：

```json
{
  "version": 1, "request_id": "capture-002", "source": "browser_capture",
  "library_id": "example-library", "allow_create_categories": true,
  "items": [
    {"item_id": "a", "input": {"kind": "image_url", "url": "https://example.com/images/a.gif"},
     "categories": [{"id": "example-node-smile"}, {"path": ["收藏", "猫咪"]}], "tags": ["猫咪", "开心"]},
    {"item_id": "b", "input": {"kind": "local_file", "path": "C:\\Capture\\b.webp"},
     "categories": [{"path": ["收藏", "反应"]}], "tags": ["惊讶"]}
  ]
}
```

## 4. 接收、结果与错误

结构/库身份不合法：请求 `rejected`，没有任务、没有写入。结构合法后，逐项分类/来源语义验证失败记入该项，合法项可以继续；不承诺整批原子回滚。非终态请求为 `accepted/running/waiting_user`；最终为 `completed/partial/failed/cancelled`。`accepted` 仅表示受理，不表示已经入库。

未来适配结果至少返回 `request_id`、`task_ids`、请求状态和 `items[]`；每项有 `item_id`、关联 `task_ids`、状态、可选 `resource_id`、已应用分类 ID、标签及必要错误 code。任务可一对多关联，但同一实际任务始终沿用原通知 ID，不另发重复完成通知。

| 项状态 | 确切含义 |
| --- | --- |
| `queued/running` | 尚未取得完整业务结果 |
| `waiting_user` | T-09 等待集中重复决策；不是完成或 100% |
| `imported` | 新资源与请求分类/标签均完成 |
| `reused` | 用户/既有规则接受复用，分类/标签均完成；不是跳过 |
| `kept` | 现有“保留两者”完成并取得独立资源身份，分类/标签均完成 |
| `skipped` | 用户跳过；不增加该项分类/标签 |
| `failed/cancelled` | 未完整完成；如资源已接纳而后续关系失败，返回实际 resource_id、已应用关系与失败阶段，不谎称整体成功或撤销已接受资源 |

必要错误包括 `invalid_request`、`unsupported_version`、`library_mismatch`、`request_conflict`、`invalid_category`、`category_not_found`、`invalid_tag`、`source_unavailable`、`download_failed`、`invalid_resource`、`metadata_failed`。原因用简短可读文本，不向调用方暴露内部数据库路径。结果中的类别是未来适配契约，当前 ImportRequest 的聚合计数/paths 不能直接替代逐项结果。

## 5. 与现有流水线及 T-06 衔接

未来接收适配层先验证结构、库与分类，再将来源交原 ImportQueue → ImportThread → ResourceImporter。下载沿原 worker，重复沿 T-09 单一集中比较（复用/保留两者/跳过、全部应用），不能按每个分类重复导入同一来源来模拟多成员关系，也不能逐项调用同步 importer 取代队列。

目前一个队列请求只有一个目标，无逐项结果及标签提交。未来实际接入须补齐可靠 item→已接受资源映射，再复用 Index 批量成员关系与 Storage 标签服务；必要的分类/标签结果与恢复责任必须明确后才开放完整请求。**当前按单目标分组提交并不能完整满足本契约**；本轮不实现分组器、不扩展检查点、不新建资源 API。

| 来源/阶段 | 当前 T-06 能力与承诺边界 |
| --- | --- |
| 稳定本地文件，不删除来源 | 已有冻结清单、来源身份检查和提交凭据；重启由用户确认继续，来源改变/缺失或目标失效不静默改投 |
| 网络 URL | 运行时可下载；重启后需重新提供/获取，不把临时文件当稳定来源，不自动安全重放 |
| QImage/内存 | 现有桌面入口可导入，但易失、不可可靠恢复；本契约 v1 不接收 |
| keep/replace 执行结果不明、delete_after、operation | 沿 T-06 既有禁止盲重放边界；外部契约不授权替换或删除来源 |
| 预分类多成员及标签后处理 | 尚无 E-01 恢复凭据；不能宣称 T-06 已覆盖这部分。未来实现需明确未完成阶段再接入，不更改本轮恢复逻辑 |

外部输入不可信：文件仅作可读输入，分类 path 是逻辑名称数组，绝不拼接为文件系统目录；不能指定 Library 存储名、数据库、覆盖路径或执行命令。现有导入验证不能代替传输授权和输入容量控制。本轮不开端口、不确定协议、不新增权限系统或 Eagle 依赖。

## 6. 本轮映射核对与后续责任

| 核对场景 | 结论 |
| --- | --- |
| 单图片→已有分类 | 可映射现有单目标队列，仍缺外部接收/身份映射 |
| 批量不同分类/标签、多成员 | 数据模型可表达；现有队列参数与逐项结果不足，未来须补适配 |
| 同名/歧义分类 | 仅完整逐级路径或稳定 ID；失败不回退 |
| 重复资源 | 原 T-09 决策；等待不算成功，复用可追加关系 |
| URL/易失来源 | 沿 T-06 不可可靠自动继续边界，不能伪装成本地文件 |
| 错误输入 | 请求拒绝或逐项失败与真实部分结果区分，不把已受理当已导入 |

以上为源码/API 映射核对，不是不存在的网络端到端测试。两例 JSON 已解析检查；本轮无业务源码修改、无网络客户端、无 Demo 数据操作。未来插件负责取得原始文件/图片直链、提供真实分类选择、保存请求身份并理解异步结果；传输、授权、大小限制及来源持久化在实际接入阶段另行落实。#36 保持 Open，待人工审阅契约，不标记采集功能完成。
