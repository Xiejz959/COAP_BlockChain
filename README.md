# 异构设备上的 PoW 区块链与并行计算性能评估

**Design and Performance Evaluation of a PoW Blockchain on Heterogeneous Devices**

> **本仓库仅用于 Computer Organization and Architecture 课程设计、教育教学和课堂演示。项目范围限定为封闭局域网内的区块计算、验证、同步、累计区块数展示及体系结构性能实验，不包含货币、资产交易或其他金融与经营功能。**
>
> **Educational use only.** This repository is a university course project for teaching and demonstrating blockchain mechanisms and computer architecture performance. It does not implement a cryptocurrency, token issuance, payments, asset trading, rewards, or financial services.

## 项目目的

计划在 MacBook、PC 和 Raspberry Pi 5 等设备上运行独立节点，通过实际程序观察 SHA-256 PoW 计算、区块广播、独立验证、分支处理和同步过程。

每接纳一个延伸当前链头的有效区块，累计区块数增加 1。累计区块数由当前采用链的高度派生，创世块不计入。它是观察系统进度与节点一致性的指标，没有持有人，不能转移、兑换或用于支付。

在这个教学应用上，比较通用计算实现与 ARM 指令加速、单核与多核、不同设备的性能，并分析计算、通信和资源竞争对系统表现的影响。

## 功能范围

计划实现的功能仅包括：

- 确定性创世配置、SHA-256 哈希链接与最小区块结构。
- PoW Nonce 搜索、区块生成及独立验证。
- 局域网节点通信、区块广播、持久化与同步。
- 临时分支处理、断线恢复及累计区块数展示。
- 节点监控、固定工作量基准、多核和异构设备性能比较。
- 由实测参数校准的性能模型与出块事件仿真。

**项目不包含，也不以以下功能为开发目标：**

- 货币、虚拟货币、代币或可转移积分的发行。
- 钱包、账户余额、节点间转账、支付或资产交易。
- 出块奖励、计算收益、购买、提现、兑换或现实资产锚定。
- 融资、投资、定价、交易撮合或任何金融与经营服务。
- 公共区块链接入、面向公众的节点服务或公网部署。

PoW 在本项目中仅作为有限时长教学实验中的计算与共识机制。找到满足难度要求的结果只会生成实验区块，不会产生货币、奖励或任何可交易权益。

## 运行边界

正式运行与课堂演示使用同一独立路由器下的封闭局域网，路由器不连接外网。依赖提前安装，程序和监控页面不依赖外部 API、在线 CDN、公共区块链或第三方组网服务。

GitHub 用于保存课程文档和后续源代码，不作为实验节点、计算服务或运行时依赖。

## 当前状态

**当前仅完成项目方案与用途说明，尚未实现新的节点程序。**

PoW 后端、多节点同步、分支处理、ARM 加速、监控页面、性能数据和离线部署均为计划内容，尚未通过实际验证。本仓库不提供生产环境系统或服务。

详细设计、课程对应、实验方法、四人分工、目录安排与开发里程碑见 [项目方案](introduction/project_plan.md)。

## 仓库内容

```text
README.md                       项目用途、范围与当前状态
introduction/project_plan.md    课程设计方案与实施计划
```

原有项目文件夹在本地保留，其后续职责记录在项目方案中。Git 不跟踪空文件夹；后续仅在实际实现需要时添加文件。
