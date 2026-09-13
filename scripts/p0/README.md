# P0 固定源码验证工具

这些是实际 P0 探针的可重跑版本，仅将暂存位置改为 `P0_WORK_DIR`。`prepare.py` 始终从固定 Git 提交提取原版源码，不会测试当前修改后的代码。测试素材由 Pillow 生成，不读取真实图库。

在隔离 Python 3.12 环境安装 `requirements/p0-windows-py312.lock.txt` 后，PowerShell 示例：

```powershell
$env:P0_WORK_DIR = 'D:\CodexScratch\new-p0-run'
python scripts/p0/prepare.py
python scripts/p0/run_p0_tests.py
python scripts/p0/run_p0_smoke.py
python scripts/p0/run_p0_behavior.py
Push-Location "$env:P0_WORK_DIR/p0-build-source"
python '<repo>/scripts/p0/run_p0_zig_build.py'
Pop-Location
python scripts/p0/measure_p0_build.py
```

必须使用全新的临时目录；工具拒绝覆盖已存在的用例。编译需要 Windows C# 编译器及 Nuitka 下载工具链的网络，缓存应指向工具临时目录。构建脚本保持原样，适配器仅增加 `--zig --jobs=4`。

启动探针使用 offscreen Qt、独立实例键、禁用全局热键和可选头像下载；不触碰正在运行的 SuzuEmojy，不代替原生 Windows 交互验收。原测试不变。服务探针要求正常初始化 exchange 目标 schema。

原版比较 ZIP 仅作内部体积基线，含上游跟踪的 data JSON，不是 NekoriEmojy 发布物。测量脚本记录的是 P0 已冻结环境；其他环境需同时保存实际版本，不能沿用记录中的版本标签。
