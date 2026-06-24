#!/usr/bin/env python3
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAURI_BIN = ROOT / "src-tauri" / "binaries"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
PRIVATE_CONFIG = ROOT / "private_config.json"
PRIVATE_CONFIG_SAMPLE = ROOT / "private_config.sample.json"
WHISPER_MODELS = ROOT / "models" / "whisper"


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


def ensure_private_config() -> None:
    if PRIVATE_CONFIG.exists():
        return
    config = {}
    if PRIVATE_CONFIG_SAMPLE.exists():
        try:
            loaded = json.loads(PRIVATE_CONFIG_SAMPLE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
        except Exception:
            pass
    for key in (
        "ARK_API_KEY",
        "APIMART_API_KEY",
        "TOS_ENDPOINT",
        "TOS_REGION",
        "TOS_BUCKET",
        "TOS_ACCESS_KEY_ID",
        "TOS_SECRET_ACCESS_KEY",
        "TOS_PUBLIC_BASE_URL",
        "TOS_OBJECT_PREFIX",
        "TLS_ENDPOINT",
        "TLS_REGION",
        "TLS_PROJECT_NAME",
        "TLS_TOPIC_NAME",
        "TLS_ACCESS_KEY_ID",
        "TLS_SECRET_ACCESS_KEY",
        "WHISPER_MODEL",
        "WHISPER_REPO_ID",
        "BUNDLE_WHISPER_MODEL",
    ):
        value = os.environ.get(key, "").strip()
        if value:
            config[key] = value
    PRIVATE_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def private_config_value(key: str, default: str = "") -> str:
    if os.environ.get(key, "").strip():
        return os.environ[key].strip()
    for candidate in (PRIVATE_CONFIG, PRIVATE_CONFIG_SAMPLE):
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        value = str(data.get(key) or "").strip()
        if value:
            return value
    return default


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() not in {"0", "false", "no", "off", "否"}


def ensure_whisper_model() -> Path | None:
    if not truthy(os.environ.get("BUNDLE_WHISPER_MODEL", "1")):
        return None
    model_name = private_config_value("WHISPER_MODEL", "base")
    target = WHISPER_MODELS / model_name
    required = ("model.bin", "config.json")
    if target.exists() and all((target / name).exists() for name in required):
        return target
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        raise SystemExit(f"无法下载 Whisper 模型：缺少 huggingface_hub，{exc}") from exc
    repo_id = private_config_value("WHISPER_REPO_ID", f"Systran/faster-whisper-{model_name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading whisper model: {repo_id} -> {target}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target),
        local_dir_use_symlinks=False,
        allow_patterns=[
            "config.json",
            "model.bin",
            "tokenizer.json",
            "vocabulary.*",
            "preprocessor_config.json",
        ],
    )
    return target


def main() -> None:
    pyinstaller = shutil.which("pyinstaller")
    if not pyinstaller:
        raise SystemExit("找不到 pyinstaller。请先运行：python -m pip install pyinstaller")

    ensure_private_config()
    whisper_model = ensure_whisper_model()
    TAURI_BIN.mkdir(parents=True, exist_ok=True)
    sep = ";" if os.name == "nt" else ":"
    add_data = f"static{sep}static"
    private_config_data = f"private_config.json{sep}."
    command = [
        pyinstaller,
        "--clean",
        "--onefile",
        "--name",
        "highlight-server",
        "--add-data",
        add_data,
        "--add-data",
        private_config_data,
    ]
    if whisper_model:
        command.extend([
            "--add-data",
            f"{whisper_model}{sep}models/whisper/{whisper_model.name}",
        ])
    command.extend([
        "--collect-data",
        "certifi",
        "--collect-binaries",
        "imageio_ffmpeg",
        "--collect-all",
        "yt_dlp",
        "--collect-all",
        "tos",
        "--collect-all",
        "volcengine",
        "--collect-all",
        "faster_whisper",
        "--collect-all",
        "ctranslate2",
        "--collect-all",
        "tokenizers",
        "server.py",
    ])
    run(command)

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
