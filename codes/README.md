# 开发目录与工具

本目录用于实现课程项目。当前已建立目录、职责说明和独立 Conda 开发环境，尚无可执行节点或测试用例。

项目的教育教学用途和功能边界见[根目录 README](../README.md)，详细方案见[项目方案](../introduction/project_plan.md)。

## 工具选择

| 工具 | 用途 | 当前 MacBook 状态 |
| --- | --- | --- |
| Python | 协议、节点组织、网络、存储、监控和实验 | `blocknode` 环境为 Python 3.11.16；源码目标兼容 Python 3.11 及以上，跨版本兼容性待实际测试 |
| Conda | 隔离开发环境 | 已创建独立的 `blocknode` 环境，只包含 Python 3.11 及其基础依赖 |
| Git | 版本管理和团队协作 | 已检测到 Git 2.50.1 |
| Apple Command Line Tools / Clang | 后续原生 C/C++ 计算模块 | 已检测到 Clang 可执行文件；尚未进行编译验证 |
| 浏览器 | 后续本地 HTML/CSS/原生 JavaScript 监控页面 | 在监控阶段使用，不使用 Node.js、npm 或前端框架 |
| CMake | 后续原生代码的构建管理 | 当前 PATH 中未找到；当前阶段不需要安装 |

首版使用 Python 标准库：`hashlib`、`socket` / `asyncio`、`sqlite3` 和 `unittest`。这些模块已在 `blocknode` 环境导入成功；SHA-256 已使用已知结果核对，SQLite 3.53.4 的内存建表、写入和读取已通过验证。

SQLite 不需要单独运行数据库服务。本机也已有 `/usr/bin/sqlite3` 命令；程序使用开发环境的 Python `sqlite3` 模块操作本地数据库文件。

当前不需要安装额外的第三方 Python 业务包。不使用 Docker、Node.js、区块链平台或区块链 SDK。区块协议、PoW 搜索、选链、节点通信、同步和实验逻辑自行实现；基础哈希、套接字及 SQLite 能力使用标准库。

后续如确有必要引入额外 Python 包，统一记录到 `environment.yml` 并安装到 `blocknode` 环境，不安装到系统 Python 或 Conda base。

## 目录职责

```text
codes/
├── README.md
├── environment.yml        Conda 开发环境配置
├── src/
│   └── blocknode/
│       ├── chain/          区块、创世配置加载、编码、验证、选链、累计量
│       ├── compute/        Python 计算控制、多核工作组织、原生后端调用
│       ├── network/        消息协议、节点连接、广播、同步与重连
│       ├── storage/        本地区块和链头的持久化
│       └── monitoring/     节点指标、监控接口与本地页面
├── native/                 后续 C/C++ 计算后端
├── experiments/
│   ├── benchmarks/         固定工作量及多核、设备对比实验
│   └── simulation/         并行性能模型和出块事件仿真
├── tests/                  协议正确性及节点集成测试
├── config/                 后续统一创世配置和节点配置示例
└── scripts/                后续启动和实验执行脚本
```

目录以 `.gitkeep` 纳入 Git；尚未创建 Python 模块、包入口、配置样例或构建脚本。开始实现某个目录时再加入具体文件，不预先添加空类、接口或兜底实现。

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

环境验证不代表节点功能已经实现。当前还不能运行节点或执行有效的项目测试；包安装方式、CLI 和测试命令随首个可运行版本补充。

开发从单节点的创世块、区块编码、PoW、累计量与重启恢复开始，再在同一台 MacBook 的两个进程中验证网络协议，最后部署到 PC 和 Pi。
