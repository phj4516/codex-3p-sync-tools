[中文](README.zh-CN.md)

# Codex Sync

Cross-platform Codex conversation sync via GitHub (using third-party API). Push sessions from one device, pull on another — paths auto-converted between Windows and macOS. If you run into setup issues, ask an LLM for help.
- Third-party API reference: https://www.bilibili.com/video/BV1TvR2B7EiR/
- Related GitHub repos: https://github.com/BenedictKing/ccx, https://github.com/farion1231/cc-switch

## How it works

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

Syncs everything NOT excluded by `.gitignore` (sessions, rules, skills, plugins, etc.).  Sensitive files (`auth.json`, `config.toml`) and large files (`*.sqlite`) are never synced.

Path conversion: project paths in session files are automatically translated between Windows (`D:\working`) and macOS (`/Users/.../working`) using `pathmap.conf`.

## Quick Start

### 1. Prerequisites

- Python 3.8+
- Git
- `pip install pathspec` (and `pip install watchdog` if using background watcher)
- A private GitHub repo for sync data (create one: `codex-sync`)

### 2. One-time Setup (both devices)

```bash
# Clone this repo into ~/.codex/
cd ~/.codex
git clone https://github.com/YOUR_USERNAME/codex-sync-tools.git tools
# Or just copy these files:
#   sync.py, codex-watch.py, pathmap.conf.example, home.gitignore

# Copy and customize gitignore — edit to exclude files/folders you need
cp home.gitignore .gitignore

# Set up path mappings
cp pathmap.conf.example pathmap.conf
# Edit pathmap.conf with your project paths

# Edit sync.py: change SYNC_REPO to your private sync repo URL
```

### 3. First Push

Close Codex, then:

```bash
python ~/.codex/sync.py push
```

This auto-initializes the sync repo and pushes your sessions.

### 4. Pull on the other device

```bash
python ~/.codex/sync.py pull
```

## Commands

| Command   | What it does                                      |
|-----------|---------------------------------------------------|
| `push`    | Copy sessions + files to GitHub (path auto-convert) |
| `pull`    | Pull from GitHub to local `~/.codex/`             |
| `status`  | Show local vs remote session count                |

## Background Watcher (optional)

`codex-watch.py` runs in the background and:

- Auto-pulls when Codex starts
- Auto-pushes after 60s idle when sessions change

```bash
pip install watchdog
python ~/.codex/codex-watch.py
```

**Windows**: put `codex-watch.vbs` (edit paths inside) in `shell:startup`.

**macOS**: run via `launchd`.

## Files

| File                    | Purpose                                        |
|-------------------------|------------------------------------------------|
| `sync.py`               | Main sync script (push/pull/status)            |
| `codex-watch.py`        | Background auto-sync watcher (optional)        |
| `codex-watch.vbs`       | Windows silent launcher for codex-watch.py     |
| `pathmap.conf.example`  | Template for cross-platform path mappings      |
| `home.gitignore`        | `.gitignore` template for `~/.codex/`          |

## Path Mappings

`pathmap.conf` maps project paths between Windows and macOS:

```
# name = WindowsPath | macOSPath
working = D:\\working | /Users/name/working
learning = C:\\learning | /Users/name/learning
```

Only projects listed here get path conversion.  Project-less chats are unaffected.

## Important

- **Close Codex before push/pull** — avoids file locking conflicts. It's fine to use Codex with files open, just avoid running conversations simultaneously on both devices, or session records may be lost.
- Make sure to install required Python libraries (`pip install pathspec watchdog`), otherwise the scripts will not run.
- The sync repo is private — your conversation data stays yours.
- `auth.json`, `config.toml`, and SQLite databases are excluded by `.gitignore`.
