# MacBook 双节点验收

本阶段使用两个独立 Python 进程、两个端口和两个 SQLite 数据目录，所有连接仅走 `127.0.0.1`。不需要路由器、外网、额外包或公网入口。

当前 MacBook 已安装本地包，网络目录可以直接导入。两份数据目录的 node_id 必须各自初始化，不要复制一个节点的数据库作为另一个节点。

## 1. 两个终端的准备

在每个终端执行：

```bash
conda activate blocknode
cd "/Users/xiejz959/Xiejz/College/computer organization & archtecture/project/codes"
```

以下计数适用于首次使用 `data/net-a` 和 `data/net-b`。已有目录会恢复并继续使用；重新演示时改用新的目录，不自动重置原库。

## 2. 终端 A：启动验证节点

```bash
python -m blocknode --config config/genesis.json --data-dir data/net-a --listen 127.0.0.1:9001 --blocks 0
```

应看到 `START height=0` 和 `LISTEN address=127.0.0.1:9001`。终端保持运行。这里的 `--blocks 0` 表示不主动计算，仍会验证和同步对端区块。

## 3. 终端 B：连接 A 并计算三块

```bash
python -m blocknode --config config/genesis.json --data-dir data/net-b --listen 127.0.0.1:9002 --peer 127.0.0.1:9001 --blocks 3
```

应看到 `PEER_CONNECTED` 和本地出块记录。B 完成三块后输出 `COMPUTE_DONE local_blocks=3`，保持监听，不自动退出。

A 会输出 `RECEIVED` 或 `SYNC`；最终两端均为 `height=3 accepted_block_count=3`，且 `head` 相同。B 的计算可能在握手前完成，随后同步同样属于正确行为；实时广播另有自动测试验证。

用第三个终端检查持久化结果：

```bash
sqlite3 data/net-a/chain.sqlite3 "SELECT height, lower(hex(hash)) FROM blocks ORDER BY height DESC LIMIT 1;"
sqlite3 data/net-b/chain.sqlite3 "SELECT height, lower(hex(hash)) FROM blocks ORDER BY height DESC LIMIT 1;"
```

两行应完全一致。比较高度和哈希，不能只比较累计数。

## 4. 离线节点补块

1. 在 B 按 Ctrl+C，使 B 离线。
2. 在 A 按 Ctrl+C，再在 A 执行：

```bash
python -m blocknode --config config/genesis.json --data-dir data/net-a --listen 127.0.0.1:9001 --blocks 2
```

A 应从高度 3 恢复，增加至 5 并保持监听。

3. 在 B 重新执行：

```bash
python -m blocknode --config config/genesis.json --data-dir data/net-b --listen 127.0.0.1:9002 --peer 127.0.0.1:9001 --blocks 0
```

B 应先显示 `START height=3`，随后连接、补齐两块，最终达到高度 5，并与 A 链头一致。

另一个自动测试验证了服务端停止并在相同端口恢复时，仍运行的客户端无需重启即可按配置重连和补块。自动重连以 TCP 已检测到断开为前提，尚未验证拔掉真实网络连接时的检测时长。

## 5. 自动测试与分支验证

```bash
python -m unittest discover -s tests -v -b
```

应显示 28 项通过和 `OK`。`-b` 在测试成功时隐藏节点日志，在失败时保留诊断输出。网络测试需要本机回环端口权限。

覆盖内容包括：

- 原单节点协议、坏库处理、累计量与重启恢复。
- 旧单链数据库的事务性升级。
- 真实 TCP 广播、握手拒绝和 75 块分页同步。
- 等工作量时保留各自链头，分支延长后按累计工作量收敛。
- 重组后计数取当前链高度，旁支不额外计数，重启仍保留分支。
- 显式 peer 自动重连、离线节点补齐历史。
- 两个独立 CLI 进程的 3 块同步、退出、重启和追平至 5 块。
- 回环与私网地址限制，拒绝公网、域名及通配监听。

最后在两个节点终端分别按 Ctrl+C。网络服务会结束，SQLite 数据继续保留。

## 当前验证范围

已验证 MacBook 上的回环 TCP、真实双进程和受控的停止重启。没有启动网页、没有安装网络框架、没有向公网发布节点。没有验证 PC、Pi、真实局域网部署、多核、原生加速或完整性能实验。
