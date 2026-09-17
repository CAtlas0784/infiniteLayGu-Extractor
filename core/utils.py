import os
import sys
import json
import time
from typing import Callable, Optional

def get_base_dir() -> str:
    """Return the root directory of ananta_asset_extractor."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_config() -> dict:
    """Load config.json from root directory with fallbacks."""
    base = get_base_dir()
    cfg_path = os.path.join(base, "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load config.json: {e}")
    return {}

def save_config(cfg: dict):
    """Save configuration dictionary to config.json."""
    base = get_base_dir()
    cfg_path = os.path.join(base, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def resolve_path(path: str) -> str:
    """Convert relative paths relative to base dir or keep absolute."""
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(get_base_dir(), path))

def format_size(num_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"

class ProgressLogger:
    """Simple callback logger for GUI and CLI progress updates."""
    def __init__(self, callback: Optional[Callable[[str, float], None]] = None):
        self.callback = callback

    def log(self, message: str, progress: float = -1.0):
        print(f"[{time.strftime('%H:%M:%S')}] {message}")
        sys.stdout.flush()
        if self.callback:
            try:
                self.callback(message, progress)
            except Exception:
                pass
