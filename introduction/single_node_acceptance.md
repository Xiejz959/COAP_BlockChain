# MacBook 单节点验收

本文验收不启用网络时的单节点行为。网络、分支及重连另见[双节点验收](two_node_acceptance.md)。网页、多核和原生优化仍未实现。

## 准备

```bash
conda activate blocknode
cd "/Users/xiejz959/Xiejz/College/computer organization & archtecture/project/codes"
python --version
python -m blocknode --help
```

当前 MacBook 已将本地项目以可编辑方式安装到 `blocknode`。其他机器创建环境后，在 `codes/` 执行：

```bash
python -m pip install --no-index --no-deps --no-build-isolation -e .
```

命令只安装当前仓库，不下载第三方包，需要环境已有 setuptools；当前 Conda 环境具备。修改源码后无需重新安装。

## 第一次生成三个区块

从 `codes/` 使用尚未使用的数据目录：

```bash
python -m blocknode --config config/genesis.json --data-dir data/macbook --blocks 3
```

预期输出的关键部分：

```text
START height=0 accepted_block_count=0 ...
BLOCK height=1 accepted_block_count=1 ...
BLOCK height=2 accepted_block_count=2 ...
BLOCK height=3 accepted_block_count=3 ...
STOP height=3 accepted_block_count=3 ...
```

区块行同时包含哈希、Nonce、尝试次数和搜索耗时。当前目标下，有效区块哈希以 `0000` 开头。不同目录的节点标识随机，因此非创世区块哈希与耗时不固定。

## 重启后再生成两块

```bash
python -m blocknode --config config/genesis.json --data-dir data/macbook --blocks 2
```

应从 `START height=3 accepted_block_count=3` 开始，生成第 4、5 块，以 `STOP height=5 accepted_block_count=5` 结束。

检查这次 START 的 `head` 等于上次 STOP 的 `head`，两次 START 的 `node_id` 相同。恢复时会验证整条链，不只读取计数。

## 验证累计量保持为五

```bash
python -m blocknode --config config/genesis.json --data-dir data/macbook --blocks 0
sqlite3 data/macbook/chain.sqlite3 "SELECT COUNT(*) AS stored_blocks, MAX(height) AS accepted_block_count FROM blocks;"
```

程序仅输出高度和累计量为 5 的 START、STOP，没有 BLOCK 行。SQLite 应输出 `6|5`，即一个创世块和五个计数区块。

上述数字适用于首次使用该目录。重复执行会继续追加；需要重新演示时换一个新的数据目录，不删除或覆盖原库。

## 自动测试

```bash
python -m unittest discover -s tests -v -b
```

当前完整测试应显示 28 项通过和 `OK`，包含单节点及网络测试。单节点部分覆盖固定创世哈希、编码边界、有效与无效 PoW、父块和高度、版本和网络、目标值、重复计数、重启恢复、坏库及 CLI。完整测试需要本机回环端口权限。

测试使用临时目录，不修改 `data/macbook`。

## 开发验证记录

环境：MacBook ARM64、Conda `blocknode`、Python 3.11.16、SQLite 3.53.4。

已验证本地可编辑安装、CLI 帮助、17 项自动测试。实际在 `data/dev-check-20261107` 分别运行 3、2、0 块，得到累计量 3、5、5，SQLite 查询为 `6|5`。

上述记录为最初单节点阶段；后续本机多节点验证见双节点验收。PC、Pi、真实局域网和体系结构优化仍未验证。
