[English](README.md)

# Codex Sync

通过 GitHub 实现 Codex 跨平台对话同步（使用第三方API）。在一台设备上 push，另一台设备上 pull — Windows 与 macOS 之间的项目路径自动转换。 如果安装有问题可以问问LLM。
- 使用第三方API的参考资料：https://www.bilibili.com/video/BV1TvR2B7EiR/?spm_id_from=333.337.search-card.all.click
- 相关的github库：https://github.com/BenedictKing/ccx、https://github.com/farion1231/cc-switch

## 工作原理

```
  Windows                         macOS
┌──────────┐                  ┌──────────┐
│ ~/.codex │ ── push ──> GitHub <── pull ── │ ~/.codex │
│ sessions │                  │ sessions │
│ rules/   │                  │ rules/   │
│ skills/  │                  │ skills/  │
│ ...      │                  │ ...      │
└──────────┘                  └──────────┘
```

同步 `.gitignore` 未排除的所有内容（sessions、rules、skills、plugins 等）。敏感文件（`auth.json`、`config.toml`）和大文件（`*.sqlite`）永远不会被同步。

路径转换：通过 `pathmap.conf`，会话文件中的项目路径在 Windows（`D:\working`）和 macOS（`/Users/.../working`）之间自动转换。

## 快速开始

### 1. 环境要求

- Python 3.8+
- Git
- `pip install pathspec`（如使用后台监控还需 `pip install watchdog`）
- 一个用于存储同步数据的 GitHub 私有仓库（创建 `codex-sync`）

### 2. 一次性配置（两台设备都需要）

```bash
# 将本仓库克隆到 ~/.codex/
cd ~/.codex
git clone https://github.com/YOUR_USERNAME/codex-sync-tools.git tools
# 或直接复制以下文件：
#   sync.py, codex-watch.py, pathmap.conf.example, home.gitignore

# 复制并配置 gitignore,修改为你需要的屏蔽的文件或文件夹
.gitignore

# 配置路径映射
cp pathmap.conf.example pathmap.conf
# 编辑 pathmap.conf，填入你的项目路径

# 编辑 sync.py：将 SYNC_REPO 改为你的私有同步仓库地址
```

### 3. 首次 Push

关闭 Codex，然后：

```bash
python ~/.codex/sync.py push
```

脚本会自动初始化同步仓库并推送你的会话数据。

### 4. 在另一台设备上 Pull

```bash
python ~/.codex/sync.py pull
```

## 命令

| 命令     | 作用                                               |
|----------|----------------------------------------------------|
| `push`   | 将会话和文件复制到 GitHub（自动路径转换）             |
| `pull`   | 从 GitHub 拉取到本地 `~/.codex/`                    |
| `status` | 查看本地与远程会话数量对比                            |

## 后台监控（可选）

`codex-watch.py` 在后台运行，自动完成：

- Codex 启动时自动 pull
- 会话文件变更后闲置 60 秒自动 push

```bash
pip install watchdog
python ~/.codex/codex-watch.py
```

**Windows**：将 `codex-watch.vbs`（先修改内部路径）放入 `shell:startup`。

**macOS**：通过 `launchd` 运行。

## 文件说明

| 文件                    | 用途                              |
|-------------------------|-----------------------------------|
| `sync.py`               | 主同步脚本（push/pull/status）      |
| `codex-watch.py`        | 后台自动同步监控（可选）             |
| `codex-watch.vbs`       | Windows 静默启动器                 |
| `pathmap.conf.example`  | 跨平台路径映射模板                  |
| `home.gitignore`        | `~/.codex/` 的 `.gitignore` 模板  |

## 路径映射

`pathmap.conf` 定义 Windows 与 macOS 之间的项目路径对应关系：

```
# name = WindowsPath | macOSPath
working = D:\\working | /Users/name/working
learning = C:\\learning | /Users/name/learning
```

只有在此列出的项目才会进行路径转换，项目无关的对话不受影响。

## 注意事项

- **push/pull 前关闭 Codex** — 避免文件锁定冲突，本地使用时候，打开期间也不影响使用，只不过不能同时进行对话，否则会导致对话记录被删除。
- 注意需要安装好watchdog、pathspec等py文件中必要的库，否则代码无法正常执行
- 同步仓库应为私有 — 你的对话数据仅属于你自己。
- `auth.json`、`config.toml` 及 SQLite 数据库已被 `.gitignore` 排除。
