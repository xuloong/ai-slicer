#!/usr/bin/env python3
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAURI_BIN = ROOT / "src-tauri" / "binaries"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list[str], cwd: Path = ROOT) -> str:
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    return result.stdout


def target_triple() -> str:
    try:
        output = run(["rustc", "-vV"])
        for line in output.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass

    machine = platform.machine().lower()
    system = platform.system().lower()
    if system == "darwin":
        return "aarch64-apple-darwin" if machine in {"arm64", "aarch64"} else "x86_64-apple-darwin"
    if system == "windows":
        return "x86_64-pc-windows-msvc"
    if system == "linux":
        return "x86_64-unknown-linux-gnu"
    raise SystemExit("无法判断 target triple，请先安装 Rust 或手动调整脚本。")


def main() -> None:
    pyinstaller = shutil.which("pyinstaller")
    if not pyinstaller:
        raise SystemExit("找不到 pyinstaller。请先运行：python -m pip install pyinstaller")

    TAURI_BIN.mkdir(parents=True, exist_ok=True)
    sep = ";" if os.name == "nt" else ":"
    add_data = f"static{sep}static"
    run([
        pyinstaller,
        "--clean",
        "--onefile",
        "--name",
        "highlight-server",
        "--add-data",
        add_data,
        "server.py",
    ])

    suffix = ".exe" if os.name == "nt" else ""
    built = DIST / f"highlight-server{suffix}"
    if not built.exists():
        raise SystemExit(f"PyInstaller 输出不存在：{built}")

    triple = target_triple()
    target = TAURI_BIN / f"highlight-server-{triple}{suffix}"
    shutil.copy2(built, target)
    if os.name != "nt":
        target.chmod(0o755)

    print(f"sidecar ready: {target}")


if __name__ == "__main__":
    main()
