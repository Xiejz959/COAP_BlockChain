# 开发目录与工具

本目录用于实现课程项目。当前已完成 PoW、区块验证、SQLite 保存恢复、旁支保存、累计工作量选链、广播、分页同步、重连和只读 HTML 观测台。31 项自动测试通过，MacBook 和 Raspberry Pi 5 已通过局域网双向同步并完成计算与同步基准。

项目用途和边界见[根目录 README](../README.md)，详细方案见[项目方案](../introduction/project_plan.md)，实际规则见[协议说明](../introduction/protocol.md)，操作步骤见[单节点验收](../introduction/single_node_acceptance.md)和[双节点验收](../introduction/two_node_acceptance.md)。

## 工具选择

| 工具 | 用途 | 当前 MacBook 状态 |
| --- | --- | --- |
| Python | 协议、节点组织、网络、存储、监控和实验 | `blocknode` 环境为 Python 3.11.16；源码目标兼容 Python 3.11 及以上，跨版本兼容性待实际测试 |
| Conda | 隔离开发环境 | 已创建独立的 `blocknode` 环境，只包含 Python 3.11 及其基础依赖 |
| Git | 版本管理和团队协作 | 已检测到 Git 2.50.1 |
| Apple Command Line Tools / Clang | 后续原生 C/C++ 计算模块 | 已检测到 Clang 可执行文件；尚未进行编译验证 |
| 浏览器 | 本地 HTML/CSS/原生 JavaScript 监控页面 | 已实现，不使用 Node.js、npm 或前端框架 |
| CMake | 后续原生代码的构建管理 | 当前 PATH 中未找到；当前阶段不需要安装 |

首版使用 Python 标准库：`hashlib`、`socket` / `asyncio`、`sqlite3` 和 `unittest`。这些模块已在 `blocknode` 环境导入成功；SHA-256 已使用已知结果核对，SQLite 3.53.4 的内存建表、写入和读取已通过验证。

SQLite 不需要单独运行数据库服务。本机也已有 `/usr/bin/sqlite3` 命令；程序使用开发环境的 Python `sqlite3` 模块操作本地数据库文件。

当前不需要安装额外的第三方 Python 业务包。不使用 Docker、Node.js、区块链平台或区块链 SDK。区块协议、PoW 搜索、选链、网络消息与恢复逻辑自行编写，哈希、TCP、SQLite 和固定工作量基准均使用 Python 标准库。

后续如确有必要引入额外 Python 包，统一记录到 `environment.yml` 并安装到 `blocknode` 环境，不安装到系统 Python 或 Conda base。

## 目录职责

```text
codes/
├── README.md
├── environment.yml        Conda 开发环境配置
├── pyproject.toml         本地 Python 包配置，无运行时第三方依赖
├── src/
│   └── blocknode/
│       ├── __main__.py     已实现有限区块数计算、状态输出和错误报告
│       ├── chain/          区块、创世配置、编码和验证
│       ├── compute/        已实现单进程参考计算；多核和原生后端待实现
│       ├── network/        已实现 TCP 消息、广播、分页同步与重连
│       ├── storage/        SQLite 区块图、当前链、累计工作量选链和恢复
│       └── monitoring/     已实现状态快照、只读 HTTP、原生 HTML/CSS/JS 页面
├── native/                 后续 C/C++ 计算后端
├── experiments/
│   ├── benchmarks/         固定工作量及多核、设备对比实验
│   └── simulation/         并行性能模型和出块事件仿真
├── tests/                  已有协议、存储和 CLI 测试
├── config/genesis.json     固定网络与创世配置
└── scripts/                后续启动和实验执行脚本
```

已实现目录包含实际代码，其余目录继续用 `.gitkeep` 保留。不预先添加空类、接口或兜底实现。

`chain/` 的规则不依赖硬件后端；`compute/` 搜索候选结果，最终由 `chain/` 验证；`network/` 接收的区块也必须先验证，再影响链头和累计量。原生优化不能改变协议规则。

## 数据与文档位置

- 架构、协议、部署和方案文档放在项目根目录下的 `introduction/`。
- 架构图和报告图片放在 `figures/`。
- 参考资料放在 `materials/`。
- 实验原始数据及分析输出放在 `results/`。
- LaTeX 报告放在 `latex compiler/`。
- 节点运行数据计划放在 `codes/data/<node-id>/`，各进程使用独立目录；该目录由后续实现按需创建，不提交 Git。
- 原生构建输出计划放在 `codes/build/`，不提交 Git。

## 开发环境

当前 MacBook 的环境已创建，开发前启用：

```bash
conda activate blocknode
python --version
```

其他设备需要复现环境时，从 `codes/` 使用：

```bash
conda env create --file environment.yml
conda activate blocknode
```

不在 Conda 环境内再创建一层 venv。此配置仅声明 Python 3.11 及其基础依赖，不锁定 Mac 专属路径或构建。其他操作系统和 Pi 上的环境创建仍需实际验证。

## 安装与运行

从 `codes/` 安装当前仓库，不联网下载第三方包；当前 MacBook 已安装：

```bash
python -m pip install --no-index --no-deps --no-build-isolation -e .
```

以下命令从 `codes/` 执行：

```bash
python -m blocknode --help
python -m blocknode --config config/genesis.json --data-dir data/macbook --blocks 3
python -m blocknode --config config/genesis.json --data-dir data/macbook --blocks 2
python -m blocknode --config config/genesis.json --data-dir data/macbook --blocks 0
python -m unittest discover -s tests -v -b
```

首次使用该目录，累计量依次为 3、5、5。`--blocks` 是本次额外出块数，默认 0。已有目录会恢复并继续使用，坏库或错误配置直接报错，不自动重建。一个数据目录仅供一个进程使用。

## 本机双节点

使用两个终端和两个不同的数据目录，分别运行：

```bash
python -m blocknode --config config/genesis.json --data-dir data/net-a --listen 127.0.0.1:9001 --blocks 0
```

```bash
python -m blocknode --config config/genesis.json --data-dir data/net-b --listen 127.0.0.1:9002 --peer 127.0.0.1:9001 --blocks 3
```

新目录应在同步后达到相同高度 3 和相同链头。完成指定本地出块数后仍保持服务，按 Ctrl+C 退出。没有 `--listen` 时保持原有有限运行行为，不开启网络。

仅支持明确的回环或 RFC1918 私网 IPv4 地址，拒绝公网地址、域名和 `0.0.0.0`。`--peer` 可重复；连接失败或 TCP 检测到断开后每秒重新尝试。该地址无权决定区块有效性。

旧单节点库在验证后事务性增加区块图，不清空已有链。等工作量保留当前分支，严格更高工作量才切换；比较高度时必须同时比较链头。已验证 MacBook 回环连接、受控进程重启以及 MacBook 和 Pi 的局域网双向同步。

## 本地只读观测台

从 `codes/` 运行：

```bash
python -m blocknode --config config/genesis.json --data-dir data/ui-a --listen 127.0.0.1:9201 --dashboard 127.0.0.1:8080 --blocks 5
```

浏览器访问 `http://127.0.0.1:8080`。使用不同终端启动 peer 后可观察连接和同步。完整命令、数据含义及截图说明见[观测台验收](../introduction/dashboard_acceptance.md)。HTTP 线程只读取状态快照，不直接操作 SQLite；页面不包含修改节点状态的功能。

## 固定工作量基准

从 `codes/` 或树莓派部署目录运行，将 `--device` 换成实际设备名称。

```bash
PYTHONPATH=src python3 experiments/benchmarks/fixed_work.py \
  --config config/genesis.json --device 'Raspberry Pi 5' --attempts 5000000
```

默认预热 2 轮、正式测量 10 轮。两台设备使用同一份 114 字节区块头模板，每轮遍历 Nonce 0 到 4,999,999，即使命中目标也继续到末尾。计时包含 Nonce 编码、SHA-256 和目标比较。JSON 输出记录每轮耗时、吞吐、命中数、末次哈希及运行环境。结果来自单进程，未绑定 CPU 核心。

2026 年 11 月 9 日的原始数据见 [MacBook Air M5](../results/pow-single-process-macbook-m5-20261109.json) 和 [Raspberry Pi 5](../results/pow-single-process-pi5-20261109.json)。所有轮次均命中 78 次，末次哈希一致。Pi 测量前后温度为 33.65 °C、39.15 °C，两次读取的 `get_throttled` 均为 `0x0`。

在 Pi 上分别使用 `--workers 1`、`--workers 2`、`--workers 3`、`--workers 4` 重跑同一工作量。多个进程各扫描互不重叠的 Nonce 范围，进程池在两次预热和正式测量之间复用，正式耗时包含任务提交和结果汇总。[多进程原始数据](../results/pow-parallel-pi5-20261109.json)

## 同步负载基准

在 MacBook 上用独立数据目录生成固定链，再启动一个 `--blocks 0` 的局域网发送节点。记录其高度、链头和监听地址。在 Pi 的部署目录运行以下命令，替换发送端地址和链头。

```bash
PYTHONPATH=src python3 experiments/benchmarks/sync_under_load.py \
  --config config/genesis.json --peer MAC_LAN_IP:9101 \
  --head SENDER_HEAD_HASH --height 75 --trials 30
```

每次试验创建新的 SQLite 库，验证同一条链。每种条件预热一次，正式测量按固定随机种子交错执行 0、1、4 个独立 PoW 负载进程，每种 30 次。追平耗时从 Pi 发起 TCP 连接算到目标链头通过验证并入库。每块另记录 `BlockStore.accept` 耗时，覆盖验证、选链和 SQLite 持久化。负载进程持续计算但不向网络发布区块。

[同步原始数据](../results/sync-under-load-pi5-20261109.json) · [实验汇总](../results/experiment-summary-20261109.md)
