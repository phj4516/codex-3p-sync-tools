#!/usr/bin/env python3
"""codex-watch.py ? Background watcher for Codex sync.

Runs continuously in the background:
  1. Detects when Codex starts ? auto-pull
  2. Watches sessions/ ? auto-push after 60s idle

Usage:
  python codex-watch.py

Set as a system service:
  Windows: Task Scheduler (trigger: at logon)
  macOS:   launchd (RunAtLoad)

Requires: watchdog (pip install watchdog)
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    print("watchdog not installed. Run: pip install watchdog")
    sys.exit(1)

CODEX_HOME = Path.home() / ".codex"
SYNC_SCRIPT = CODEX_HOME / "sync.py"
SESSIONS_DIR = CODEX_HOME / "sessions"
IDLE_SECONDS = 60
PROCESS_CHECK_INTERVAL = 5  # seconds

IS_WINDOWS = sys.platform == "win32"


# ?? Process detection ????????????????????????????????????????????

def is_codex_running() -> bool:
    if IS_WINDOWS:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq codex.exe"],
            capture_output=True, text=True,
        )
        return "codex.exe" in r.stdout
    else:
        r = subprocess.run(["pgrep", "-x", "Codex"], capture_output=True)
        return r.returncode == 0


def process_watch_loop():
    """Poll for Codex process.  When it appears, run pull once."""
    was_running = is_codex_running()
    while True:
        time.sleep(PROCESS_CHECK_INTERVAL)
        running = is_codex_running()
        if running and not was_running:
            t = time.strftime("%H:%M:%S")
            print(f"[{t}] Codex started, pulling...")
            subprocess.run([sys.executable, str(SYNC_SCRIPT), "pull"])
            print(f"[{t}] Pull done")
        was_running = running


# ?? Session file watcher ?????????????????????????????????????????

class SessionHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_activity = time.time()
        self.lock = threading.Lock()

    def _touch(self):
        with self.lock:
            self.last_activity = time.time()

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".jsonl"):
            self._touch()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".jsonl"):
            self._touch()


def push_loop(handler: SessionHandler):
    """Background: push after IDLE_SECONDS of no session file changes."""
    last_push = 0.0
    while True:
        time.sleep(5)
        with handler.lock:
            idle = time.time() - handler.last_activity
        if idle >= IDLE_SECONDS and (time.time() - last_push) >= IDLE_SECONDS:
            last_push = time.time()
            t = time.strftime("%H:%M:%S")
            print(f"[{t}] Auto-pushing...")
            subprocess.run([sys.executable, str(SYNC_SCRIPT), "push"])
            print(f"[{t}] Push done")


# ?? Main ?????????????????????????????????????????????????????????

def main():
    if not SYNC_SCRIPT.exists():
        print(f"sync.py not found at {SYNC_SCRIPT}")
        sys.exit(1)

    print(f"codex-watch started")
    print(f"  Process monitor : check every {PROCESS_CHECK_INTERVAL}s")
    print(f"  File watcher    : {SESSIONS_DIR}")
    print(f"  Push after      : {IDLE_SECONDS}s idle")
    print()

    # Start process watcher thread
    proc_thread = threading.Thread(target=process_watch_loop, daemon=True)
    proc_thread.start()

    # Start session file watcher
    handler = SessionHandler()
    observer = Observer()
    observer.schedule(handler, str(SESSIONS_DIR), recursive=True)
    observer.start()

    push_thread = threading.Thread(target=push_loop, args=(handler,), daemon=True)
    push_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
