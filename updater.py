"""Self-update check against GitHub Releases.

Only meaningful for the packaged exe -- a dev checkout should just `git
pull`. Network calls run on a background thread; any failure (offline, rate
limited, no releases yet) is swallowed and just means no update banner shows,
never a popup or crash.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CURRENT_VERSION = "1.0.0"
REPO = "Zyrumi/duskfade-save-tools"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "DuskfadeSaveLoader.exe"


@dataclass
class UpdateInfo:
    version: str
    asset_url: str


def _parse_version(v: str) -> tuple[int, ...]:
    v = v.lstrip("vV")
    parts = []
    for p in v.split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


def check_for_update_async(on_found) -> None:
    """Calls on_found(UpdateInfo) on the Tk thread via `after` -- caller is
    responsible for marshalling back if needed. Here we just invoke it
    directly from the worker thread's perspective; save_loader.py schedules
    the actual UI update with `self.after(0, ...)`."""

    def worker():
        try:
            req = urllib.request.Request(
                API_URL, headers={"User-Agent": "duskfade-save-tools-updater"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read())
            tag = data.get("tag_name") or ""
            if not tag or not _is_newer(tag, CURRENT_VERSION):
                return
            asset_url = None
            for asset in data.get("assets", []):
                if asset.get("name") == ASSET_NAME:
                    asset_url = asset.get("browser_download_url")
                    break
            if not asset_url:
                return
            on_found(UpdateInfo(version=tag, asset_url=asset_url))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            pass

    threading.Thread(target=worker, daemon=True).start()


def download_and_apply(info: UpdateInfo, on_progress, on_error) -> None:
    """Downloads the new exe, then hands off to a helper .bat that waits for
    this process to exit, swaps the file, relaunches, and deletes itself --
    a running exe can't overwrite its own file on Windows, so the swap has
    to happen from outside the process."""

    def worker():
        try:
            exe_path = Path(sys.executable).resolve()
            new_path = exe_path.with_name(exe_path.stem + "_update.exe")
            req = urllib.request.Request(
                info.asset_url, headers={"User-Agent": "duskfade-save-tools-updater"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp, open(new_path, "wb") as f:
                total = int(resp.headers.get("Content-Length") or 0)
                read = 0
                chunk = resp.read(65536)
                while chunk:
                    f.write(chunk)
                    read += len(chunk)
                    if total:
                        on_progress(read / total)
                    chunk = resp.read(65536)

            bat_path = exe_path.with_name("_apply_update.bat")
            bat_path.write_text(
                "@echo off\r\n"
                ":wait\r\n"
                f'tasklist /fi "imagename eq {exe_path.name}" | find /i "{exe_path.name}" >nul\r\n'
                "if not errorlevel 1 (\r\n"
                "  timeout /t 1 /nobreak >nul\r\n"
                "  goto wait\r\n"
                ")\r\n"
                f'del "{exe_path}"\r\n'
                f'move /y "{new_path}" "{exe_path}"\r\n'
                f'start "" "{exe_path}"\r\n'
                'del "%~f0"\r\n'
            )
            subprocess.Popen(
                [str(bat_path)],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                close_fds=True,
            )
            on_progress(1.0)
            import os

            os._exit(0)  # skip Tk teardown -- the batch is already waiting on this pid
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            on_error(str(e))

    threading.Thread(target=worker, daemon=True).start()
