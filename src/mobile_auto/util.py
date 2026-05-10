"""Utility functions for mobile-auto."""

import json
import os
import subprocess
from pathlib import Path


def ensure_dir(path: str) -> str:
    """Ensure directory exists, create if needed."""
    os.makedirs(path, exist_ok=True)
    return path


def run_cmd(cmd: list, timeout: int = 60, env: dict = None) -> tuple:
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError:
        return -1, "", "Command not found"


def get_app_bundle_id(app_alias: str) -> str:
    """Resolve app alias to bundle ID."""
    KNOWN = {
        "xiaohongshu": "com.xingin.xiaohongshu",
        "linkedin": "com.linkedin.LinkedIn",
        "wechat": "com.tencent.xin",
        "weibo": "com.sina.weibo",
        "x": "com.twitter.twitter-mac",
    }
    return KNOWN.get(app_alias.lower(), app_alias)


def write_json(path: str, data: dict):
    """Write JSON file with pretty formatting."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
