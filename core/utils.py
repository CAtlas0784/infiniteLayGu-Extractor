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

class InterruptedJobError(Exception):
    """Exception raised when an extraction job is cancelled by the user."""
    pass

class ProgressLogger:
    """Simple callback logger for GUI and CLI progress updates with cancellation support."""
    def __init__(self, callback: Optional[Callable[[str, float], None]] = None):
        self.callback = callback
        self._cancelled = False
        self._active_processes = []

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self):
        """Signal cancellation and terminate any active subprocesses."""
        self._cancelled = True
        self.log("[CANCEL] User requested to stop the current job. Halting operations...")
        for proc in list(self._active_processes):
            try:
                if proc and proc.poll() is None:
                    proc.terminate()
                    time.sleep(0.05)
                    if proc.poll() is None:
                        proc.kill()
            except Exception:
                pass
        self._active_processes.clear()

    def register_process(self, proc):
        """Register an active subprocess so it can be terminated on cancel."""
        if self._cancelled:
            try:
                proc.kill()
            except Exception:
                pass
            raise InterruptedJobError("Task was cancelled.")
        if proc not in self._active_processes:
            self._active_processes.append(proc)

    def unregister_process(self, proc):
        """Unregister a finished subprocess."""
        if proc in self._active_processes:
            try:
                self._active_processes.remove(proc)
            except ValueError:
                pass

    def check_cancelled(self):
        """Check if cancellation was requested and raise InterruptedJobError if so."""
        if self._cancelled:
            raise InterruptedJobError("Extraction cancelled by user.")

    def log(self, message: str, progress: float = -1.0):
        print(f"[{time.strftime('%H:%M:%S')}] {message}")
        sys.stdout.flush()
        if self.callback:
            try:
                self.callback(message, progress)
            except Exception:
                pass

