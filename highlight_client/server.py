#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import base64
import statistics
import shutil
import ssl
import subprocess
import sys
import tempfile
import textwrap
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from PIL import Image, ImageChops, ImageStat

try:
    import certifi
except Exception:
    certifi = None

try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None

DEV_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", DEV_ROOT))


def app_data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "HighlightClient"


ROOT = DEV_ROOT
STATIC = RESOURCE_ROOT / "static"
DATA_DIR = app_data_dir()
WORK = DATA_DIR / "work"
EXPORTS = DATA_DIR / "exports"
PREVIEWS = DATA_DIR / "previews"
CONFIG_FILE = DATA_DIR / "user_config.json"
HISTORY_FILE = DATA_DIR / "history.json"
ARK_CHAT_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
ARK_MODEL = "doubao-seed-2-0-pro-260215"
FFMPEG_CANDIDATES = [
    "/opt/homebrew/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/Applications/QQBrowser.app/Contents/Frameworks/QQBrowser Framework.framework/Versions/21.0.6.203/FFmpeg/bin/ffmpeg",
    "C:/ffmpeg/bin/ffmpeg.exe",
]

DATA_DIR.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)
EXPORTS.mkdir(parents=True, exist_ok=True)
PREVIEWS.mkdir(parents=True, exist_ok=True)
TASKS: dict[str, dict] = {}
TASK_LOCK = threading.Lock()


class TaskCancelled(Exception):
    pass


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_config(config: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def default_package_templates() -> dict[str, dict]:
    return {
        "clean": {
            "id": "clean",
            "name": "干净包装",
            "bgm": False,
            "style": "clean",
            "font_color": "white",
            "box_color": "black@0.35",
            "font_size": 38,
        },
        "drama": {
            "id": "drama",
            "name": "短剧爆点",
            "bgm": True,
            "style": "drama",
            "font_color": "yellow",
            "box_color": "black@0.55",
            "font_size": 44,
        },
        "ad": {
            "id": "ad",
            "name": "广告强包装",
            "bgm": True,
            "style": "ad",
            "font_color": "white",
            "box_color": "red@0.55",
            "font_size": 42,
        },
    }


def normalize_package_templates(raw: object) -> dict[str, dict]:
    source = raw if isinstance(raw, dict) else default_package_templates()
    templates: dict[str, dict] = {}
    for fallback_id, raw_template in source.items():
        if not isinstance(raw_template, dict):
            continue
        template_id = str(raw_template.get("id") or fallback_id).strip()
        if not template_id:
            continue
        style = str(raw_template.get("style") or "clean").strip()
        if style not in {"clean", "drama", "ad"}:
            style = "clean"
        try:
            font_size = int(raw_template.get("font_size", 40))
        except (TypeError, ValueError):
            font_size = 40
        templates[template_id] = {
            "id": template_id,
            "name": str(raw_template.get("name") or template_id).strip()[:40],
            "bgm": bool(raw_template.get("bgm", True)),
            "style": style,
            "font_color": str(raw_template.get("font_color") or "white").strip()[:24],
            "box_color": str(raw_template.get("box_color") or "black@0.45").strip()[:24],
            "font_size": max(24, min(72, font_size)),
        }
    return templates or default_package_templates()


def configured_package_templates() -> dict[str, dict]:
    return normalize_package_templates(load_config().get("packageTemplates"))


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_history(items: list[dict]) -> None:
    HISTORY_FILE.write_text(json.dumps(items[:80], ensure_ascii=False, indent=2), encoding="utf-8")


def append_history(action: str, video: Path | None = None, **extra: object) -> None:
    item = {
        "id": uuid.uuid4().hex[:10],
        "time": now_text(),
        "action": action,
    }
    if video:
        item.update({"video": str(video), "videoName": video.name})
    item.update(extra)
    save_history([item, *load_history()])


def public_config() -> dict:
    config = load_config()
    api_key = os.environ.get("ARK_API_KEY") or config.get("arkApiKey", "")
    return {
        "hasArkApiKey": bool(api_key),
        "arkApiKeyMasked": f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 16 else "",
        "ffmpegPath": config.get("ffmpegPath", ""),
        "detectedFfmpegPath": detect_ffmpeg_path() or "",
        "wecomWebhookUrl": config.get("wecomWebhookUrl", ""),
        "usageLogName": config.get("usageLogName", ""),
        "usageLogDept": config.get("usageLogDept", ""),
        "packageTemplate": config.get("packageTemplate", "none"),
        "packageTemplates": configured_package_templates(),
    }


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def wecom_webhook_url() -> str:
    return os.environ.get("WECOM_WEBHOOK_URL") or load_config().get("wecomWebhookUrl", "")


def usage_identity() -> tuple[str, str]:
    config = load_config()
    name = str(config.get("usageLogName", "")).strip()
    dept = str(config.get("usageLogDept", "")).strip()
    if not name:
        name = os.environ.get("USER") or os.environ.get("USERNAME") or "本机用户"
    if not dept:
        dept = "未填写"
    return name, dept


def send_wecom_webhook(content: str) -> None:
    url = wecom_webhook_url()
    if not url:
        return
    payload = json.dumps({
        "msgtype": "markdown",
        "markdown": {"content": content[:3900]},
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10, context=ark_ssl_context()).read()
    except Exception:
        pass


def notify_wecom(content: str) -> None:
    threading.Thread(target=send_wecom_webhook, args=(content,), daemon=True).start()


def notify_feature_used(feature: str, details: str = "") -> None:
    user, dept = usage_identity()
    lines = [
        "AI切片神器功能使用通知",
        f"> 姓名：{user}",
        f"> 部门：{dept}",
        f"> 功能：{feature}",
        f"> 时间：{now_text()}",
    ]
    if details:
        lines.append(f"> 详情：{details[:500]}")
    notify_wecom("\n".join(lines))


def detect_ffmpeg_path() -> str | None:
    if imageio_ffmpeg is not None:
        try:
            bundled = imageio_ffmpeg.get_ffmpeg_exe()
            if bundled and Path(bundled).exists():
                return bundled
        except Exception:
            pass
    for candidate in FFMPEG_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return shutil.which("ffmpeg")


def ffmpeg_path() -> str:
    configured = load_config().get("ffmpegPath", "")
    if configured and Path(configured).exists():
        return configured
    found = detect_ffmpeg_path()
    if found:
        return found
    raise RuntimeError("找不到 ffmpeg。请在设置里填写 ffmpeg 路径，或把 ffmpeg 加入系统 PATH。")


def ffprobe_path() -> str | None:
    candidates = []
    configured = load_config().get("ffmpegPath", "")
    if configured:
        ffmpeg = Path(configured)
        candidates.append(str(ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix.lower() == ".exe" else "ffprobe")))
    detected = detect_ffmpeg_path()
    if detected:
        ffmpeg = Path(detected)
        candidates.append(str(ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix.lower() == ".exe" else "ffprobe")))
    candidates.append("ffprobe")
    for candidate in candidates:
        if Path(candidate).is_file() or shutil.which(candidate):
            return candidate
    return None


def parse_ratio(value: str) -> float | None:
    match = re.match(r"^\s*(\d+)\s*:\s*(\d+)\s*$", value or "")
    if not match:
        return None
    left = float(match.group(1))
    right = float(match.group(2))
    if left <= 0 or right <= 0:
        return None
    return left / right


def video_display_size(video: Path, fallback: tuple[int, int] | None = None) -> tuple[int, int]:
    fallback_width, fallback_height = fallback or (16, 9)
    probe = ffprobe_path()
    if not probe:
        return fallback_width, fallback_height
    try:
        result = run([
            probe, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,display_aspect_ratio,sample_aspect_ratio:stream_side_data=rotation",
            "-of", "json", str(video),
        ], timeout=30)
    except Exception:
        return fallback_width, fallback_height
    if result.returncode != 0:
        return fallback_width, fallback_height
    try:
        data = json.loads(result.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
    except (json.JSONDecodeError, IndexError, TypeError):
        return fallback_width, fallback_height
    try:
        width = int(stream.get("width") or fallback_width)
        height = int(stream.get("height") or fallback_height)
    except (TypeError, ValueError):
        width, height = fallback_width, fallback_height
    ratio = parse_ratio(str(stream.get("display_aspect_ratio") or ""))
    if not ratio:
        sar = parse_ratio(str(stream.get("sample_aspect_ratio") or ""))
        if sar:
            ratio = (width * sar) / max(1, height)
    rotation = 0
    for item in stream.get("side_data_list") or []:
        try:
            rotation = int(float(item.get("rotation") or 0))
        except (TypeError, ValueError):
            rotation = 0
        if rotation:
            break
    if abs(rotation) % 180 == 90:
        ratio = (1 / ratio) if ratio else None
        width, height = height, width
    if ratio and ratio > 0:
        if ratio >= 1:
            return max(1, round(height * ratio)), max(1, height)
        return max(1, width), max(1, round(width / ratio))
    return max(1, width), max(1, height)


def ark_api_key() -> str:
    key = os.environ.get("ARK_API_KEY") or load_config().get("arkApiKey", "")
    if not key:
        raise RuntimeError("请先在设置里填写火山方舟 API Key。")
    return key


def ark_ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            pass
    return ssl.create_default_context()


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_windows() -> bool:
    return sys.platform.startswith("win")


def task_cancel_requested(task_id: str | None) -> bool:
    if not task_id:
        return False
    with TASK_LOCK:
        task = TASKS.get(task_id, {})
        return bool(task.get("cancel_requested")) or task.get("status") == "cancelled"


def ensure_not_cancelled(task_id: str | None) -> None:
    if task_cancel_requested(task_id):
        raise TaskCancelled("任务已终止。")


def register_process(task_id: str | None, process: subprocess.Popen) -> None:
    if not task_id:
        return
    with TASK_LOCK:
        task = TASKS.setdefault(task_id, {})
        task.setdefault("processes", set()).add(process)


def unregister_process(task_id: str | None, process: subprocess.Popen) -> None:
    if not task_id:
        return
    with TASK_LOCK:
        processes = TASKS.get(task_id, {}).get("processes")
        if processes:
            processes.discard(process)


def terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=3)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def task_cancel(task_id: str) -> bool:
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return False
        task["cancel_requested"] = True
        task["status"] = "cancelled"
        task["message"] = "已终止"
        processes = list(task.get("processes", set()))
    for process in processes:
        terminate_process(process)
    return True


def run(
    cmd: list[str],
    timeout: int | None = 120,
    task_id: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    ensure_not_cancelled(task_id)
    process = subprocess.Popen(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    register_process(task_id, process)
    try:
        remaining = timeout
        while True:
            ensure_not_cancelled(task_id)
            try:
                stdout, stderr = process.communicate(timeout=0.5 if timeout is None else min(0.5, max(0.01, remaining)))
                return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                if timeout is None:
                    continue
                remaining = max(0.0, remaining - 0.5)
                if remaining <= 0:
                    terminate_process(process)
                    raise subprocess.TimeoutExpired(cmd, timeout)
    finally:
        unregister_process(task_id, process)


def task_update(task_id: str, progress: int, message: str, **extra: object) -> None:
    with TASK_LOCK:
        task = TASKS.setdefault(task_id, {})
        if task.get("cancel_requested"):
            return
        task.update({"progress": max(0, min(100, progress)), "message": message})
        task.update(extra)


def task_done(task_id: str, result: dict) -> None:
    with TASK_LOCK:
        if TASKS[task_id].get("cancel_requested"):
            TASKS[task_id].update({"status": "cancelled", "message": "已终止", "progress": TASKS[task_id].get("progress", 0)})
            return
        TASKS[task_id].update({"status": "done", "progress": 100, "message": "完成", "result": result})


def task_error(task_id: str, error: Exception | str) -> None:
    with TASK_LOCK:
        if isinstance(error, TaskCancelled) or TASKS[task_id].get("cancel_requested"):
            TASKS[task_id].update({"status": "cancelled", "message": "已终止", "error": ""})
            return
        TASKS[task_id].update({"status": "error", "message": str(error), "error": str(error)})


def start_task(name: str, worker) -> str:
    task_id = uuid.uuid4().hex[:12]
    with TASK_LOCK:
        TASKS[task_id] = {"id": task_id, "name": name, "status": "running", "progress": 1, "message": "准备开始"}

    def run_worker() -> None:
        try:
            task_done(task_id, worker(task_id))
        except Exception as exc:
            task_error(task_id, exc)

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()
    return task_id


def parse_duration(stderr: str) -> str:
    for line in stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            return line.split("Duration:", 1)[1].split(",", 1)[0].strip()
    return "未知"


def parse_duration_seconds(stderr: str) -> float:
    duration = parse_duration(stderr)
    if duration == "未知":
        return 0.0
    hours, minutes, seconds = duration.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_media_info(stderr: str) -> dict:
    info = {
        "duration": parse_duration(stderr),
        "video": "未检测到",
        "audio": "未检测到",
        "resolution": "未知",
        "ratio": "未知",
        "fps": "未知",
        "bitrate": "未知",
    }
    for line in stderr.splitlines():
        text = line.strip()
        if "Duration:" in text and "bitrate:" in text:
            info["bitrate"] = text.split("bitrate:", 1)[1].strip()
        if " Video: " in text or text.startswith("Stream") and "Video:" in text:
            after = text.split("Video:", 1)[1].strip()
            info["video"] = after.split(",", 1)[0].strip()
            for part in [item.strip() for item in after.split(",")]:
                if "x" in part and part.split(" ")[0].replace("x", "").isdigit():
                    info["resolution"] = part.split(" ")[0]
                if "DAR" in part:
                    info["ratio"] = part.split("DAR", 1)[1].split("]", 1)[0].strip()
                if "fps" in part:
                    info["fps"] = part.strip()
        if " Audio: " in text or text.startswith("Stream") and "Audio:" in text:
            after = text.split("Audio:", 1)[1].strip()
            pieces = [item.strip() for item in after.split(",")]
            info["audio"] = ", ".join(pieces[:3])
    return info


def seconds_to_clock(value: float) -> str:
    value = max(0, float(value))
    minutes, seconds = divmod(int(round(value)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def make_ocr_swift(image_dir: Path, fps: int) -> str:
    return textwrap.dedent(
        f"""
        import Foundation
        import Vision
        import ImageIO

        let imageDir = URL(fileURLWithPath: {json.dumps(str(image_dir))}, isDirectory: true)
        let fps = Double({fps})
        let files = (try FileManager.default.contentsOfDirectory(at: imageDir, includingPropertiesForKeys: nil))
            .filter {{ $0.pathExtension.lowercased() == "jpg" }}
            .sorted {{ $0.lastPathComponent < $1.lastPathComponent }}

        var results: [[String: Any]] = []

        for (index, file) in files.enumerated() {{
            guard let source = CGImageSourceCreateWithURL(file as CFURL, nil),
                  let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {{
                continue
            }}

            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = true
            request.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
            request.minimumTextHeight = 0.032

            let handler = VNImageRequestHandler(cgImage: image, options: [:])
            do {{
                try handler.perform([request])
                let texts = (request.results ?? [])
                    .compactMap {{ $0.topCandidates(1).first?.string }}
                    .filter {{ !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }}
                if !texts.isEmpty {{
                    results.append([
                        "time": Double(index) / fps,
                        "text": texts.joined(separator: " ")
                    ])
                }}
            }} catch {{
                continue
            }}
        }}

        let data = try JSONSerialization.data(withJSONObject: results, options: [])
        FileHandle.standardOutput.write(data)
        """
    )


def extract_dialogue(video: Path, out_dir: Path, task_id: str | None = None) -> list[dict]:
    ensure_not_cancelled(task_id)
    if not is_macos():
        if task_id:
            task_update(task_id, 48, "当前系统未启用本地 OCR，跳过台词识别")
        return []
    if task_id:
        task_update(task_id, 28, "正在抽取字幕画面")
    ocr_dir = out_dir / "ocr"
    ocr_dir.mkdir(exist_ok=True)
    fps = 1
    pattern = ocr_dir / "subtitle_%06d.jpg"
    extract = run([
        ffmpeg_path(), "-hide_banner", "-y", "-i", str(video),
        "-vf", f"fps={fps},scale=540:-1", str(pattern)
    ], timeout=None, task_id=task_id)
    if extract.returncode != 0:
        return []

    ensure_not_cancelled(task_id)
    if task_id:
        task_update(task_id, 48, "正在 OCR 识别台词")
    script = Path(tempfile.gettempdir()) / f"highlight_ocr_{uuid.uuid4().hex}.swift"
    script.write_text(make_ocr_swift(ocr_dir, fps), encoding="utf-8")
    env = os.environ.copy()
    env["CLANG_MODULE_CACHE_PATH"] = str(WORK / ".clang-cache")
    result = run(["swift", str(script)], env=env, timeout=None, task_id=task_id)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    # Collapse repeated OCR results from consecutive frames.
    collapsed = []
    previous_text = ""
    for row in rows:
        ensure_not_cancelled(task_id)
        text = clean_dialogue_text(" ".join(str(row.get("text", "")).split()))
        if not text:
            continue
        if text == previous_text and collapsed:
            collapsed[-1]["end"] = float(row.get("time", 0)) + 1
            continue
        collapsed.append({"time": float(row.get("time", 0)), "end": float(row.get("time", 0)) + 1, "text": text})
        previous_text = text
    return collapsed


def clean_dialogue_text(text: str) -> str:
    cleaned = text
    noise_patterns = [
        r"《?利[刃列]玫瑰》?",
        r"短剧[虚虛]构",
        r"请勿模[仿份]",
        r"诺勿模[仿份]",
        r"东南[亚業业]某地",
        r"珍爱生命",
        r"远[离離高]赌[博搏]",
        r"运[离離高]赌[博搏]",
    ]
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, " ", cleaned)
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9？！?!，,。:：]+", " ", cleaned)
    noise_tokens = ("模", "赌博", "賭博", "赌搏", "東南", "东南", "菜地", "某地", "生命", "远商", "远腐", "远襄")
    cleaned = " ".join(
        part for part in cleaned.split()
        if len(part) > 1 and not any(token in part for token in noise_tokens)
    )
    return cleaned.strip()


def dialogue_score(texts: list[str]) -> tuple[float, list[str]]:
    joined = "".join(texts)
    if not joined:
        return 0.0, []

    signals = {
        "金额/筹码": ["万", "钱", "到账", "转账", "输", "赢", "赌", "牌", "筹码", "网贷", "赔", "加"],
        "冲突/压力": ["不可能", "骗", "出千", "认账", "必须", "不答应", "怕", "压", "不服", "少了", "算了"],
        "反转/疑问": ["到底", "什么", "怎么", "为什么", "难道", "不会", "原来", "特殊", "秘密"],
        "动作推进": ["再玩", "一局", "开牌", "看牌", "洗牌", "骰子", "包", "让我", "这把"],
        "悬念钩子": ["若若", "知道", "完整版", "下一方链接", "真牛", "到底是什么"],
    }
    score = min(len(joined) / 18, 3.0)
    reasons = []
    for reason, keywords in signals.items():
        hits = sum(joined.count(keyword) for keyword in keywords)
        if hits:
            score += hits * 2.2
            reasons.append(reason)
    if "？" in joined or "?" in joined:
        score += 2.0
        reasons.append("疑问句")
    if "！" in joined or "!" in joined:
        score += 1.2
        reasons.append("强情绪")
    return score, sorted(set(reasons))


def build_highlight_analysis(video: Path, task_id: str | None = None) -> dict:
    ensure_not_cancelled(task_id)
    job = uuid.uuid4().hex[:10]
    out_dir = WORK / f"auto_{job}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if task_id:
        task_update(task_id, 6, "正在读取视频信息")
    probe = run([ffmpeg_path(), "-hide_banner", "-i", str(video)], timeout=120, task_id=task_id)
    duration = parse_duration_seconds(probe.stderr)
    if duration <= 0:
        raise RuntimeError("无法读取视频时长。")

    fps = 2
    pattern = out_dir / "frame_%06d.jpg"
    if task_id:
        task_update(task_id, 15, "正在抽取分析帧")
    extract = run([
        ffmpeg_path(), "-hide_banner", "-y", "-i", str(video),
        "-vf", f"fps={fps},scale=96:-1", str(pattern)
    ], timeout=None, task_id=task_id)
    if extract.returncode != 0:
        raise RuntimeError(extract.stderr[-1200:])

    files = sorted(out_dir.glob("frame_*.jpg"))
    if len(files) < 4:
        raise RuntimeError("可分析画面太少。")

    dialogues = extract_dialogue(video, out_dir, task_id=task_id)

    if task_id:
        task_update(task_id, 68, "正在检测自然边界")
    diffs: list[tuple[float, float]] = []
    previous = None
    for index, file in enumerate(files):
        if index % 50 == 0:
            ensure_not_cancelled(task_id)
        image = Image.open(file).convert("L")
        if previous is not None:
            delta = ImageStat.Stat(ImageChops.difference(previous, image)).mean[0]
            diffs.append((index / fps, delta))
        previous = image

    values = [value for _, value in diffs]
    median = statistics.median(values)
    mad = statistics.median([abs(value - median) for value in values]) or 1.0
    threshold = max(median + mad * 3.0, statistics.quantiles(values, n=5)[3])

    boundaries = [0.0]
    last = 0.0
    for pos, (time, value) in enumerate(diffs[1:-1], start=1):
        if pos % 200 == 0:
            ensure_not_cancelled(task_id)
        left = diffs[pos - 1][1]
        right = diffs[pos + 1][1]
        if value >= threshold and value >= left and value >= right and time - last >= 5.0:
            boundaries.append(time)
            last = time
    boundaries.append(duration)

    # Long scenes are split at their strongest internal visual turn, so one topic
    # does not swallow the whole result.
    changed = True
    while changed:
        ensure_not_cancelled(task_id)
        changed = False
        expanded = [boundaries[0]]
        for start, end in zip(boundaries, boundaries[1:]):
            if end - start > 52:
                inner = [(time, value) for time, value in diffs if start + 10 <= time <= end - 10]
                if inner:
                    cut = max(inner, key=lambda item: item[1])[0]
                    expanded.extend([cut, end])
                    changed = True
                else:
                    expanded.append(end)
            else:
                expanded.append(end)
        boundaries = sorted(set(round(item, 1) for item in expanded))

    shots = []
    for shot_index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        if shot_index % 50 == 0:
            ensure_not_cancelled(task_id)
        if end - start < 3:
            continue
        local = [value for time, value in diffs if start <= time < end]
        activity = sum(local) / len(local) if local else median
        peak = max(local) if local else median
        shot_texts = [item["text"] for item in dialogues if start <= item["time"] < end]
        text_score, text_reasons = dialogue_score(shot_texts)
        shots.append({
            "start": start,
            "end": end,
            "duration": end - start,
            "activity": activity,
            "peak": peak,
            "text_score": text_score,
            "texts": shot_texts,
            "text_reasons": text_reasons,
        })

    windows = []
    for i in range(len(shots)):
        if i % 50 == 0:
            ensure_not_cancelled(task_id)
        total = 0.0
        score_sum = 0.0
        peak = 0.0
        text_score = 0.0
        text_reasons = []
        texts = []
        for j in range(i, min(len(shots), i + 8)):
            shot = shots[j]
            total += shot["duration"]
            score_sum += shot["activity"] * shot["duration"]
            peak = max(peak, shot["peak"])
            text_score += shot["text_score"]
            text_reasons.extend(shot["text_reasons"])
            texts.extend(shot["texts"])
            if 14 <= total <= 45:
                score = score_sum / total + peak * 0.35 + text_score * 1.75
                if shots[i]["start"] < duration * 0.18:
                    score *= 1.12
                windows.append({
                    "start": shots[i]["start"],
                    "end": shots[j]["end"],
                    "duration": total,
                    "score": score,
                    "text_reasons": sorted(set(text_reasons)),
                    "sample_text": " / ".join(texts[:3]),
                })
            if total > 45:
                break

    if task_id:
        task_update(task_id, 82, "正在生成候选高光段落")
    return {
        "duration": duration,
        "boundaries": boundaries,
        "dialogues": dialogues,
        "windows": windows,
    }


def select_local_windows(analysis: dict, target_seconds: float) -> list[dict]:
    windows = analysis["windows"]
    selected = []
    used: list[tuple[float, float]] = []
    for window in sorted(windows, key=lambda item: item["score"], reverse=True):
        overlap = any(not (window["end"] <= start or window["start"] >= end) for start, end in used)
        if overlap:
            continue
        selected.append(window)
        used.append((window["start"], window["end"]))
        if sum(item["duration"] for item in selected) >= target_seconds:
            break

    selected = sorted(selected, key=lambda item: item["start"])
    if sum(item["duration"] for item in selected) > target_seconds + 25:
        while selected and sum(item["duration"] for item in selected) > target_seconds + 10:
            selected.pop()
    return selected


def windows_to_clips(selected: list[dict]) -> list[dict]:
    return [
        {
            "start": round(item["start"], 1),
            "duration": round(item["duration"], 1),
            "reason": "、".join(item.get("text_reasons") or ["自然边界合并段落"]),
            "dialogue": item.get("sample_text", ""),
            "role": "local",
            "score": round(float(item.get("score", 0)), 2),
        }
        for item in selected
    ]


def analyze_visual_highlights(video: Path, target_seconds: float = 180.0, task_id: str | None = None) -> dict:
    analysis = build_highlight_analysis(video, task_id=task_id)
    ensure_not_cancelled(task_id)
    if task_id:
        task_update(task_id, 90, "正在挑选高光片段")
    selected = select_local_windows(analysis, target_seconds)
    clips = windows_to_clips(selected)
    return {
        "clips": clips,
        "duration": seconds_to_clock(sum(clip["duration"] for clip in clips)),
        "summary": f"检测到 {len(analysis['boundaries'])} 个自然边界，识别到 {len(analysis['dialogues'])} 条台词线索，合并出 {len(clips)} 个相对完整的高光段落。",
    }


def frame_data_url(video: Path, time: float, out_dir: Path, index: int, task_id: str | None = None) -> str:
    ensure_not_cancelled(task_id)
    out = out_dir / f"ai_frame_{index:03d}.jpg"
    result = run([
        ffmpeg_path(), "-hide_banner", "-y", "-ss", f"{time:.2f}", "-i", str(video),
        "-frames:v", "1", "-vf", "scale=360:-1", str(out)
    ], timeout=None, task_id=task_id)
    if result.returncode != 0 or not out.exists():
        return ""
    data = base64.b64encode(out.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def call_ark_chat(content: list[dict], task_id: str | None = None) -> str:
    ensure_not_cancelled(task_id)
    payload = {
        "model": ARK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是短剧高光剪辑师。只输出严格 JSON，不要输出解释文字。",
            },
            {"role": "user", "content": content},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    request = urllib.request.Request(
        ARK_CHAT_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ark_api_key()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600, context=ark_ssl_context()) as resp:
            ensure_not_cancelled(task_id)
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"火山方舟接口请求失败：HTTP {exc.code} {detail[-800:]}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接火山方舟接口：{exc}")
    return data["choices"][0]["message"]["content"]


def parse_ai_json(text: str) -> dict:
    decoder = json.JSONDecoder()
    cleaned = text.strip()
    try:
        value, _ = decoder.raw_decode(cleaned)
    except json.JSONDecodeError:
        value = None
    if isinstance(value, dict):
        return value
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise RuntimeError(f"AI 返回内容不是可解析的 JSON：{text[:300]}")


def analyze_ai_highlights(
    video: Path,
    target_seconds: float = 180.0,
    requirement: str = "",
    task_id: str | None = None,
) -> dict:
    analysis = build_highlight_analysis(video, task_id=task_id)
    ensure_not_cancelled(task_id)
    if task_id:
        task_update(task_id, 84, "正在整理 AI 候选片段")
    candidates = sorted(analysis["windows"], key=lambda item: item["score"], reverse=True)[:16]
    candidates = sorted(candidates, key=lambda item: item["start"])
    ai_dir = WORK / f"ai_{uuid.uuid4().hex[:10]}"
    ai_dir.mkdir(parents=True, exist_ok=True)

    compact = []
    content: list[dict] = []
    for idx, item in enumerate(candidates, start=1):
        ensure_not_cancelled(task_id)
        compact.append({
            "id": idx,
            "start": round(item["start"], 1),
            "end": round(item["end"], 1),
            "duration": round(item["duration"], 1),
            "local_score": round(item["score"], 2),
            "local_reasons": item.get("text_reasons", []),
            "dialogue": item.get("sample_text", ""),
        })

    instruction = {
        "task": "从候选短剧片段中选择适合剪成高光视频的片段。要求开头吸睛，中段剧情顺畅，结尾有钩子；优先保留完整情节单元，不要把一个关键对白拆断。若用户提供了自定义要求，请在不破坏剧情连贯性的前提下优先满足。",
        "target_seconds": target_seconds,
        "video_duration": round(analysis["duration"], 1),
        "user_requirement": requirement,
        "output_schema": {
            "clips": [
                {
                    "candidate_id": "number",
                    "start": "number 秒，可在候选范围内微调",
                    "duration": "number 秒",
                    "reason": "中文，说明高光原因",
                    "dialogue": "关键台词或画面依据",
                    "role": "hook|build|turn|ending",
                }
            ],
            "summary": "中文总结",
        },
        "candidates": compact,
    }
    content.append({
        "type": "text",
        "text": json.dumps(instruction, ensure_ascii=False),
    })

    for idx, item in enumerate(candidates, start=1):
        ensure_not_cancelled(task_id)
        middle = item["start"] + item["duration"] / 2
        if task_id:
            task_update(task_id, 84 + int(idx / max(1, len(candidates)) * 8), f"正在抽取 AI 关键帧 {idx}/{len(candidates)}")
        data_url = frame_data_url(video, middle, ai_dir, idx, task_id=task_id)
        if data_url:
            content.append({"type": "text", "text": f"候选 {idx} 的中间关键帧，时间 {middle:.1f} 秒。"})
            content.append({"type": "image_url", "image_url": {"url": data_url}})

    if task_id:
        task_update(task_id, 94, "正在调用豆包 Seed 2.0 Pro")
    ai_text = call_ark_chat(content, task_id=task_id)
    if task_id:
        task_update(task_id, 98, "正在解析 AI 返回结果")
    ai = parse_ai_json(ai_text)
    clips = []
    for clip in ai.get("clips", []):
        start = float(clip.get("start", 0))
        duration = float(clip.get("duration", 0))
        if duration <= 0:
            continue
        clips.append({
            "start": round(start, 1),
            "duration": round(duration, 1),
            "reason": str(clip.get("reason", "AI剧情理解")),
            "dialogue": str(clip.get("dialogue", "")),
            "role": str(clip.get("role", "turn")),
        })
    if not clips:
        clips = windows_to_clips(select_local_windows(analysis, target_seconds))
    return {
        "clips": clips,
        "duration": seconds_to_clock(sum(clip["duration"] for clip in clips)),
        "summary": ai.get("summary") or f"AI 已基于 {len(candidates)} 个候选段落完成高光筛选。",
    }


def focus_sample_times(video: Path, clips: list[dict]) -> tuple[float, list[dict]]:
    valid_clips = [clip for clip in clips if float(clip.get("duration", 0) or 0) > 0]
    if valid_clips:
        total = sum(float(clip.get("duration", 0)) for clip in valid_clips)
        samples = []
        cursor = 0.0
        for index, clip in enumerate(valid_clips[:8], start=1):
            start = float(clip.get("start", 0))
            duration = float(clip.get("duration", 0))
            mid = start + duration / 2
            samples.append({
                "id": index,
                "source_time": mid,
                "output_time": cursor + duration / 2,
                "start": cursor,
                "end": cursor + duration,
            })
            cursor += duration
        return total, samples

    duration = media_duration_seconds(video)
    if duration <= 0:
        raise RuntimeError("无法读取原片时长。")
    count = min(8, max(3, int(duration // 20) + 1))
    step = duration / (count + 1)
    samples = [
        {
            "id": index,
            "source_time": step * index,
            "output_time": step * index,
            "start": max(0.0, step * index - 2.0),
            "end": min(duration, step * index + 2.0),
        }
        for index in range(1, count + 1)
    ]
    return duration, samples


def normalize_focus_marks(raw: object, samples: list[dict], duration: float) -> list[dict]:
    if not isinstance(raw, list):
        return []
    sample_map = {int(item["id"]): item for item in samples}
    marks = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            sample_id = int(item.get("sample_id") or item.get("id") or 0)
            sample = sample_map.get(sample_id)
            start = float(item.get("start", sample["start"] if sample else 0))
            end = float(item.get("end", sample["end"] if sample else start + 3))
            x = float(item.get("x", 0.25))
            y = float(item.get("y", 0.25))
            w = float(item.get("w", 0.5))
            h = float(item.get("h", 0.35))
        except (TypeError, ValueError):
            continue
        effect = str(item.get("effect", "circle")).strip().lower()
        if effect not in {"circle", "zoom"}:
            effect = "circle"
        start = max(0.0, min(duration, start))
        end = max(start + 0.3, min(duration, end))
        x = max(0.0, min(0.95, x))
        y = max(0.0, min(0.95, y))
        w = max(0.05, min(1.0 - x, w))
        h = max(0.05, min(1.0 - y, h))
        marks.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "x": round(x, 4),
            "y": round(y, 4),
            "w": round(w, 4),
            "h": round(h, 4),
            "effect": effect,
            "reason": str(item.get("reason", "需要突出展示的重点"))[:80],
        })
    return marks[:12]


def analyze_ai_focus(video: Path, clips: list[dict], requirement: str = "", task_id: str | None = None) -> dict:
    duration, samples = focus_sample_times(video, clips)
    focus_dir = WORK / f"focus_{uuid.uuid4().hex[:10]}"
    focus_dir.mkdir(parents=True, exist_ok=True)
    content: list[dict] = [{
        "type": "text",
        "text": json.dumps({
            "task": "识别视频画面中最值得突出强调的重点区域，例如商品、价格、人物表情、关键动作、按钮、对比结果或冲突焦点。请只返回严格 JSON。",
            "user_requirement": requirement or "用户没有指定重点内容，请优先寻找价格、优惠信息、商品主体、关键卖点、重要按钮、对比结果、人物表情或动作焦点。",
            "coordinate_rule": "所有坐标都用 0-1 的相对比例，x/y 是左上角，w/h 是宽高。",
            "time_rule": "start/end 使用最终导出视频时间轴。每个 sample 已提供对应 output_time、start、end。请根据画面内容自行决定强调持续时间，重点出现多久就持续多久，不必固定时长。",
            "output_schema": {
                "focusMarks": [{
                    "sample_id": "number",
                    "start": "number",
                    "end": "number",
                    "x": "0-1",
                    "y": "0-1",
                    "w": "0-1",
                    "h": "0-1",
                    "reason": "中文说明重点是什么",
                }],
                "summary": "中文总结",
            },
            "samples": samples,
        }, ensure_ascii=False),
    }]
    for index, sample in enumerate(samples, start=1):
        ensure_not_cancelled(task_id)
        if task_id:
            task_update(task_id, 15 + int(index / max(1, len(samples)) * 55), f"正在抽取重点识别帧 {index}/{len(samples)}")
        data_url = frame_data_url(video, sample["source_time"], focus_dir, index, task_id=task_id)
        if data_url:
            content.append({"type": "text", "text": f"sample_id={sample['id']}，最终时间={sample['output_time']:.1f}秒，原片时间={sample['source_time']:.1f}秒。"})
            content.append({"type": "image_url", "image_url": {"url": data_url}})
    if task_id:
        task_update(task_id, 82, "正在调用豆包识别重点区域")
    ai = parse_ai_json(call_ark_chat(content, task_id=task_id))
    marks = normalize_focus_marks(ai.get("focusMarks", []), samples, duration)
    if not marks:
        raise RuntimeError("AI 没有返回可用的重点区域，请换一段视频或稍后重试。")
    return {
        "focusMarks": marks,
        "summary": ai.get("summary") or f"已生成 {len(marks)} 个重点标记。",
        "duration": seconds_to_clock(duration),
    }


def storyboard_sample_times(video: Path) -> tuple[float, list[dict]]:
    duration = media_duration_seconds(video)
    if duration <= 0:
        raise RuntimeError("无法读取原片时长。")
    count = min(12, max(6, int(duration // 25) + 1))
    step = duration / (count + 1)
    samples = []
    for index in range(1, count + 1):
        time = step * index
        samples.append({
            "id": index,
            "time": round(time, 1),
            "suggested_start": round(max(0.0, time - step / 2), 1),
            "suggested_end": round(min(duration, time + step / 2), 1),
        })
    return duration, samples


def normalize_storyboard(raw: object, duration: float) -> list[dict]:
    if not isinstance(raw, list):
        return []
    shots = []
    fallback_span = duration / max(1, min(12, len(raw) or 1))
    for index, item in enumerate(raw[:24], start=1):
        if not isinstance(item, dict):
            continue
        try:
            start = float(item.get("start", (index - 1) * fallback_span))
            end = float(item.get("end", start + fallback_span))
        except (TypeError, ValueError):
            start = (index - 1) * fallback_span
            end = start + fallback_span
        start = max(0.0, min(duration, start))
        end = max(start + 0.3, min(duration, end))
        shots.append({
            "shot": str(item.get("shot") or index).strip()[:12],
            "start": round(start, 1),
            "end": round(end, 1),
            "scene": str(item.get("scene") or item.get("visual") or "画面内容").strip()[:180],
            "shotType": str(item.get("shotType") or item.get("shot_type") or "中景").strip()[:40],
            "camera": str(item.get("camera") or "稳定镜头").strip()[:80],
            "action": str(item.get("action") or "展示关键动作").strip()[:180],
            "dialogue": str(item.get("dialogue") or "").strip()[:160],
            "caption": str(item.get("caption") or "").strip()[:120],
            "edit": str(item.get("edit") or "自然衔接").strip()[:160],
        })
    return shots


def analyze_ai_storyboard(video: Path, requirement: str = "", task_id: str | None = None) -> dict:
    duration, samples = storyboard_sample_times(video)
    storyboard_dir = WORK / f"storyboard_{uuid.uuid4().hex[:10]}"
    storyboard_dir.mkdir(parents=True, exist_ok=True)
    content: list[dict] = [{
        "type": "text",
        "text": json.dumps({
            "task": "根据视频代表帧和时间信息，生成可执行的中文分镜脚本。请只返回严格 JSON，不要输出解释文字。",
            "video_duration": round(duration, 1),
            "user_requirement": requirement or "用户没有额外要求，请按视频内容生成适合短视频剪辑和复刻拍摄的分镜脚本。",
            "writing_rule": "每个镜头要相对独立，时间段连续且覆盖主要内容。描述要具体，避免空泛。广告素材要突出卖点、价格、优惠、动作和转化点；剧情素材要突出人物、冲突、转折和钩子。",
            "output_schema": {
                "shots": [{
                    "shot": "镜号",
                    "start": "开始秒数",
                    "end": "结束秒数",
                    "scene": "画面描述",
                    "shotType": "景别，如特写/近景/中景/全景",
                    "camera": "运镜或镜头调度",
                    "action": "人物/商品/画面动作",
                    "dialogue": "关键台词，没有则空字符串",
                    "caption": "建议字幕/花字，没有则空字符串",
                    "edit": "剪辑节奏、转场或音效建议",
                }],
                "summary": "中文总结这个视频的分镜逻辑和成片方向",
            },
            "samples": samples,
        }, ensure_ascii=False),
    }]
    for index, sample in enumerate(samples, start=1):
        ensure_not_cancelled(task_id)
        if task_id:
            task_update(task_id, 12 + int(index / max(1, len(samples)) * 58), f"正在抽取分镜参考帧 {index}/{len(samples)}")
        data_url = frame_data_url(video, sample["time"], storyboard_dir, index, task_id=task_id)
        if data_url:
            content.append({"type": "text", "text": f"sample_id={sample['id']}，原片时间={sample['time']:.1f}秒，建议覆盖 {sample['suggested_start']:.1f}-{sample['suggested_end']:.1f} 秒。"})
            content.append({"type": "image_url", "image_url": {"url": data_url}})
    if task_id:
        task_update(task_id, 82, "正在调用豆包生成分镜脚本")
    ai = parse_ai_json(call_ark_chat(content, task_id=task_id))
    if task_id:
        task_update(task_id, 96, "正在整理分镜脚本")
    shots = normalize_storyboard(ai.get("shots") or ai.get("storyboard") or [], duration)
    if not shots:
        raise RuntimeError("AI 没有返回可用的分镜脚本，请换一段视频或稍后重试。")
    return {
        "shots": shots,
        "summary": ai.get("summary") or f"已根据视频内容生成 {len(shots)} 个分镜。",
        "duration": seconds_to_clock(duration),
    }


def generate_thumbnails(video: Path, interval: int, task_id: str | None = None) -> dict:
    ensure_not_cancelled(task_id)
    if task_id:
        task_update(task_id, 8, "正在准备缩略图目录")
    job = uuid.uuid4().hex[:10]
    out_dir = WORK / job
    out_dir.mkdir(parents=True, exist_ok=True)
    probe = run([ffmpeg_path(), "-hide_banner", "-i", str(video)], timeout=120, task_id=task_id)
    duration = parse_duration_seconds(probe.stderr)
    if duration <= 0:
        raise RuntimeError("无法读取视频时长。")

    times = [float(value) for value in range(0, max(1, int(duration)), interval)]
    if not times:
        times = [0.0]
    if task_id:
        task_update(task_id, 25, "正在抽取缩略图")

    files = []
    for index, time in enumerate(times):
        ensure_not_cancelled(task_id)
        if task_id:
            progress = 25 + int(index / max(1, len(times)) * 60)
            task_update(task_id, progress, f"正在抽取缩略图 {index + 1}/{len(times)}")
        file = out_dir / f"shot_{index + 1:04d}.jpg"
        result = run([
            ffmpeg_path(), "-hide_banner", "-y",
            "-ss", f"{time:.2f}", "-i", str(video),
            "-frames:v", "1", "-q:v", "3", str(file)
        ], timeout=None, task_id=task_id)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-1200:])
        if file.exists():
            files.append((file, time))

    if task_id:
        task_update(task_id, 88, "正在整理缩略图")
    ensure_not_cancelled(task_id)
    thumbs = []
    display_size = None
    for file, time in files:
        width, height = Image.open(file).size
        if display_size is None:
            display_size = video_display_size(video, (width, height))
        display_width, display_height = display_size
        thumbs.append({
            "src": f"/work/{job}/{file.name}",
            "time": time,
            "width": width,
            "height": height,
            "displayWidth": display_width,
            "displayHeight": display_height,
        })
    return {"job": job, "thumbs": thumbs}


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("content-length", "0"))
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8") or "{}")


def choose_file() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择要剪辑的视频")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "已取消选择。")
        return result.stdout.strip()
    return choose_with_tkinter(kind="file")


def choose_binary() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择 ffmpeg 可执行文件")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "已取消选择。")
        return result.stdout.strip()
    return choose_with_tkinter(kind="binary")


def choose_logo() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择贴图图片")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "已取消选择。")
        return result.stdout.strip()
    return choose_with_tkinter(kind="logo")


def choose_bgm() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择 BGM 音频")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "已取消选择。")
        return result.stdout.strip()
    return choose_with_tkinter(kind="bgm")


def choose_folder() -> str:
    if is_macos():
        script = 'POSIX path of (choose folder with prompt "选择导出视频保存目录")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "已取消选择。")
        return result.stdout.strip()
    return choose_with_tkinter(kind="folder")


def default_storyboard_name(video: Path) -> str:
    base = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", video.stem, flags=re.UNICODE).strip("._") or "video"
    return f"{base}_storyboard.md"


def choose_storyboard_output(video: Path) -> str:
    default_name = default_storyboard_name(video)
    if is_macos():
        script = f'POSIX path of (choose file name with prompt "保存分镜脚本" default name "{default_name}")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "已取消选择。")
        return result.stdout.strip()
    return choose_with_tkinter(kind="storyboard", default_name=default_name)


def choose_with_tkinter(kind: str, default_name: str = "") -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError("当前系统无法打开文件选择器，请手动输入路径。") from exc
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    if kind == "file":
        path = filedialog.askopenfilename(
            title="选择要剪辑的视频",
            filetypes=[
                ("视频文件", "*.mp4 *.mov *.m4v *.mkv *.avi *.webm"),
                ("所有文件", "*.*"),
            ],
        )
    elif kind == "binary":
        path = filedialog.askopenfilename(
            title="选择 ffmpeg 可执行文件",
            filetypes=[
                ("ffmpeg", "ffmpeg.exe ffmpeg"),
                ("所有文件", "*.*"),
            ],
        )
    elif kind == "logo":
        path = filedialog.askopenfilename(
            title="选择贴图图片",
            filetypes=[
                ("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("所有文件", "*.*"),
            ],
        )
    elif kind == "bgm":
        path = filedialog.askopenfilename(
            title="选择 BGM 音频",
            filetypes=[
                ("音频文件", "*.mp3 *.wav *.m4a *.aac *.flac"),
                ("所有文件", "*.*"),
            ],
        )
    elif kind == "storyboard":
        path = filedialog.asksaveasfilename(
            title="保存分镜脚本",
            defaultextension=".md",
            initialfile=default_name or "storyboard.md",
            filetypes=[
                ("Markdown 文档", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*"),
            ],
        )
    else:
        path = filedialog.askdirectory(title="选择导出视频保存目录")
    root.destroy()
    if not path:
        raise RuntimeError("已取消选择。")
    return path


def reveal_in_finder(path: Path) -> None:
    if is_macos():
        subprocess.Popen(["open", "-R", str(path)])
    elif is_windows():
        subprocess.Popen(["explorer", f"/select,{path}"])
    else:
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(path.parent)])


def response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", "application/json; charset=utf-8")
    handler.send_header("content-length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_swift_export(input_path: Path, output_path: Path, clips: list[dict]) -> str:
    clip_lines = []
    for clip in clips:
        start = float(clip["start"])
        duration = float(clip["duration"])
        if duration <= 0:
            continue
        clip_lines.append(f"Clip(start: {start:.3f}, duration: {duration:.3f})")
    if not clip_lines:
        raise ValueError("至少需要一个有效片段。")

    return textwrap.dedent(
        f"""
        import AVFoundation
        import Foundation

        struct Clip {{ let start: Double; let duration: Double }}

        let input = URL(fileURLWithPath: {json.dumps(str(input_path))})
        let output = URL(fileURLWithPath: {json.dumps(str(output_path))})
        try? FileManager.default.removeItem(at: output)
        let clips = [{", ".join(clip_lines)}]

        let asset = AVURLAsset(url: input)
        let composition = AVMutableComposition()

        let videoTracks = try await asset.loadTracks(withMediaType: .video)
        let audioTracks = try await asset.loadTracks(withMediaType: .audio)

        guard let sourceVideo = videoTracks.first,
              let videoTrack = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid) else {{
            fputs("Could not prepare video track.\\n", stderr)
            exit(1)
        }}

        let sourceAudio = audioTracks.first
        let audioTrack = sourceAudio == nil ? nil : composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)

        videoTrack.preferredTransform = try await sourceVideo.load(.preferredTransform)
        var cursor = CMTime.zero
        for clip in clips {{
            let range = CMTimeRange(start: CMTime(seconds: clip.start, preferredTimescale: 600),
                                    duration: CMTime(seconds: clip.duration, preferredTimescale: 600))
            do {{
                try videoTrack.insertTimeRange(range, of: sourceVideo, at: cursor)
                if let sourceAudio = sourceAudio, let audioTrack = audioTrack {{
                    try audioTrack.insertTimeRange(range, of: sourceAudio, at: cursor)
                }}
                cursor = cursor + range.duration
            }} catch {{
                fputs("Insert failed: \\(error)\\n", stderr)
                exit(1)
            }}
        }}

        guard let export = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetPassthrough) else {{
            fputs("Could not create export session.\\n", stderr)
            exit(1)
        }}
        export.outputURL = output
        export.outputFileType = .mp4
        export.shouldOptimizeForNetworkUse = true

        let sema = DispatchSemaphore(value: 0)
        export.exportAsynchronously {{ sema.signal() }}
        sema.wait()

        if export.status != .completed {{
            fputs("Export failed: \\(export.error?.localizedDescription ?? "unknown")\\n", stderr)
            exit(1)
        }}
        print(CMTimeGetSeconds(composition.duration))
        """
    )


def export_with_ffmpeg(input_path: Path, output_path: Path, clips: list[dict]) -> None:
    valid_clips = [
        {
            "start": max(0.0, float(clip.get("start", 0))),
            "duration": float(clip.get("duration", 0)),
        }
        for clip in clips
        if float(clip.get("duration", 0)) > 0
    ]
    if not valid_clips:
        raise RuntimeError("至少需要一个有效片段。")

    if len(valid_clips) == 1:
        clip = valid_clips[0]
        result = run([
            ffmpeg_path(), "-hide_banner", "-y",
            "-ss", f"{clip['start']:.3f}", "-i", str(input_path),
            "-t", f"{clip['duration']:.3f}",
            "-map", "0:v:0", "-map", "0:a:0?",
            "-c", "copy", "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            str(output_path),
        ], timeout=None)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout)[-1500:])
        return

    errors = []
    for include_audio in (True, False):
        command = [ffmpeg_path(), "-hide_banner", "-y"]
        for clip in valid_clips:
            command.extend([
                "-ss", f"{clip['start']:.3f}",
                "-t", f"{clip['duration']:.3f}",
                "-i", str(input_path),
            ])

        chains = []
        pieces = []
        for index in range(len(valid_clips)):
            chains.append(f"[{index}:v:0]setpts=PTS-STARTPTS[v{index}]")
            pieces.append(f"[v{index}]")
            if include_audio:
                chains.append(f"[{index}:a:0]asetpts=PTS-STARTPTS[a{index}]")
                pieces.append(f"[a{index}]")
        chains.append(f"{''.join(pieces)}concat=n={len(valid_clips)}:v=1:a={1 if include_audio else 0}[v]{'[a]' if include_audio else ''}")

        command.extend(["-filter_complex", ";".join(chains), "-map", "[v]"])
        if include_audio:
            command.extend(["-map", "[a]"])
        command.extend([
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p",
        ])
        if include_audio:
            command.extend(["-c:a", "aac", "-b:a", "160k"])
        else:
            command.append("-an")
        command.extend(["-movflags", "+faststart", str(output_path)])

        result = run(command, timeout=None)
        if result.returncode == 0:
            return
        errors.append((result.stderr or result.stdout)[-1500:])

    raise RuntimeError(errors[-1] if errors else "导出失败。")


def export_video(input_path: Path, output_path: Path, clips: list[dict]) -> None:
    export_with_ffmpeg(input_path, output_path, clips)


def escape_drawtext(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")


def default_hook_text(clips: list[dict]) -> str:
    if not clips:
        return "高光来了"
    first = clips[0]
    dialogue = str(first.get("dialogue", "")).strip()
    reason = str(first.get("reason", "")).strip()
    text = dialogue or reason or "高光来了"
    return text[:18]


def package_templates() -> dict[str, dict]:
    return configured_package_templates()


def has_audio_stream(video: Path) -> bool:
    result = run([ffmpeg_path(), "-hide_banner", "-i", str(video)], timeout=60)
    return "Audio:" in result.stderr


def media_duration_seconds(video: Path) -> float:
    result = run([ffmpeg_path(), "-hide_banner", "-i", str(video)], timeout=60)
    return parse_duration_seconds(result.stderr)


def output_name_for(video: Path, suffix: str, output_dir: Path) -> Path:
    base = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", video.stem, flags=re.UNICODE).strip("._") or "video"
    candidate = output_dir / f"{base}_{suffix}.mp4"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        candidate = output_dir / f"{base}_{suffix}_{index}.mp4"
        if not candidate.exists():
            return candidate
    return output_dir / f"{base}_{suffix}_{uuid.uuid4().hex[:6]}.mp4"


def output_doc_name_for(video: Path, suffix: str, output_dir: Path, ext: str) -> Path:
    base = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", video.stem, flags=re.UNICODE).strip("._") or "video"
    clean_ext = ext.lstrip(".") or "txt"
    candidate = output_dir / f"{base}_{suffix}.{clean_ext}"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        candidate = output_dir / f"{base}_{suffix}_{index}.{clean_ext}"
        if not candidate.exists():
            return candidate
    return output_dir / f"{base}_{suffix}_{uuid.uuid4().hex[:6]}.{clean_ext}"


def markdown_cell(value: object) -> str:
    return str(value or "").replace("\n", " ").replace("|", "\\|").strip()


def clean_storyboard_summary(summary: str) -> str:
    value = str(summary or "").strip()
    blocked = {"正在导出分镜脚本...", "正在分析视频内容并生成分镜脚本..."}
    return "" if value in blocked else value


def export_storyboard_file(video: Path, output_path: Path, summary: str, shots: object) -> Path:
    normalized = normalize_storyboard(shots, max(1.0, media_duration_seconds(video)))
    if not normalized:
        raise RuntimeError("请先生成分镜脚本，再导出。")
    output = output_path.expanduser()
    if output.suffix == "":
        output = output.with_suffix(".md")
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = clean_storyboard_summary(summary)
    lines = [
        f"# {video.stem} 分镜脚本",
        "",
        f"- 生成时间：{now_text()}",
        f"- 原视频：{video.name}",
    ]
    if summary:
        lines.extend(["", f"## 总结", "", str(summary).strip()])
    lines.extend([
        "",
        "## 分镜表",
        "",
        "| 镜号 | 时间 | 画面 | 景别 | 运镜 | 内容 | 台词 | 字幕 | 剪辑建议 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for shot in normalized:
        time_range = f"{seconds_to_clock(float(shot['start']))}-{seconds_to_clock(float(shot['end']))}"
        lines.append(
            "| "
            + " | ".join([
                markdown_cell(shot.get("shot")),
                markdown_cell(time_range),
                markdown_cell(shot.get("scene")),
                markdown_cell(shot.get("shotType")),
                markdown_cell(shot.get("camera")),
                markdown_cell(shot.get("action")),
                markdown_cell(shot.get("dialogue")),
                markdown_cell(shot.get("caption")),
                markdown_cell(shot.get("edit")),
            ])
            + " |"
        )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def packaged_filter(template: dict, options: dict, duration: float, clips: list[dict]) -> str:
    filters = ["format=yuv420p"]
    if template.get("style") == "drama":
        filters.append("eq=contrast=1.06:saturation=1.08")
    elif template.get("style") == "ad":
        filters.append("eq=contrast=1.08:saturation=1.12")
    return ",".join(filters)


def logo_overlay_position(position: str) -> tuple[str, str]:
    return {
        "top-left": ("24", "24"),
        "top-right": ("W-w-24", "24"),
        "bottom-left": ("24", "H-h-24"),
        "bottom-right": ("W-w-24", "H-h-24"),
    }.get(position, ("W-w-24", "24"))


def timed_assets(raw: object, duration: float, media_type: str) -> list[dict]:
    if not isinstance(raw, list):
        return []
    assets = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        path_raw = str(item.get("path", "")).strip()
        if not path_raw:
            continue
        path = Path(path_raw).expanduser()
        if not path.exists() or not path.is_file():
            continue
        try:
            start = max(0.0, float(item.get("start", 0)))
            end = min(duration, max(start, float(item.get("end", duration))))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        assets.append({
            "path": path,
            "start": start,
            "end": end,
            "duration": end - start,
            "type": media_type,
        })
    return assets


def circle_focus_filter(source: str, target: str, mark: dict) -> str:
    x = mark["x"]
    y = mark["y"]
    w = mark["w"]
    h = mark["h"]
    start = mark["start"]
    end = mark["end"]
    enable = f"between(t,{start:.3f},{end:.3f})"
    return (
        f"[{source}]"
        f"drawbox=x=max(0\\,iw*{x:.4f}-14):y=max(0\\,ih*{y:.4f}-14):w=min(iw\\,iw*{w:.4f}+28):h=min(ih\\,ih*{h:.4f}+28):color=yellow@0.12:t=fill:enable='{enable}',"
        f"drawbox=x=max(0\\,iw*{x:.4f}-8):y=max(0\\,ih*{y:.4f}-10):w=min(iw\\,iw*{w:.4f}+16):h=min(ih\\,ih*{h:.4f}+20):color=yellow@0.88:t=5:enable='{enable}',"
        f"drawbox=x=max(0\\,iw*{x:.4f}-2):y=max(0\\,ih*{y:.4f}-4):w=min(iw\\,iw*{w:.4f}+8):h=min(ih\\,ih*{h:.4f}+10):color=orange@0.70:t=3:enable='{enable}'[{target}]"
    )


def zoom_focus_filters(source: str, target: str, mark: dict, index: int) -> list[str]:
    start = float(mark["start"])
    end = float(mark["end"])
    duration = max(0.3, end - start)
    center_x = max(0.02, min(0.98, float(mark["x"]) + float(mark["w"]) / 2))
    center_y = max(0.02, min(0.98, float(mark["y"]) + float(mark["h"]) / 2))
    levels = [1.10, 1.035, 1.145, 1.025]
    base = f"focus{index}_base"
    src_labels = [f"focus{index}_src{part}" for part in range(len(levels))]
    filters = [f"[{source}]split={len(levels) + 1}[{base}]{''.join(f'[{label}]' for label in src_labels)}"]
    previous = base
    for part, (src_label, zoom) in enumerate(zip(src_labels, levels), start=1):
        part_start = start + duration * (part - 1) / len(levels)
        part_end = start + duration * part / len(levels)
        if part == len(levels):
            part_end = end
        zoomed = f"focus{index}_zoom{part}"
        overlaid = target if part == len(levels) else f"focus{index}_out{part}"
        filters.append(
            f"[{src_label}]"
            f"scale=trunc(iw*{zoom:.3f}/2)*2:trunc(ih*{zoom:.3f}/2)*2,"
            f"crop=w=trunc(iw/{zoom:.3f}/2)*2:h=trunc(ih/{zoom:.3f}/2)*2:"
            f"x=min(max(0\\,iw*{center_x:.4f}-ow/2)\\,iw-ow):"
            f"y=min(max(0\\,ih*{center_y:.4f}-oh/2)\\,ih-oh)[{zoomed}]"
        )
        filters.append(
            f"[{previous}][{zoomed}]overlay=0:0:enable='between(t,{part_start:.3f},{part_end:.3f})'[{overlaid}]"
        )
        previous = overlaid
    return filters


def export_packaged_video(input_path: Path, output_path: Path, clips: list[dict], options: dict) -> None:
    template_id = str(options.get("template") or "drama")
    templates = package_templates()
    if template_id == "none":
        template = {"id": "none", "name": "不使用模板", "bgm": False, "style": "clean"}
    else:
        template = templates.get(template_id) or templates.get("drama") or next(iter(templates.values()))
    valid_clips = [clip for clip in clips if float(clip.get("duration", 0) or 0) > 0]
    owns_temp = bool(valid_clips)
    if owns_temp:
        temp = WORK / f"packaged_base_{uuid.uuid4().hex[:8]}.mp4"
        export_video(input_path, temp, valid_clips)
        duration = sum(max(0.0, float(clip.get("duration", 0))) for clip in valid_clips)
    else:
        temp = input_path
        duration = media_duration_seconds(input_path)
        if duration <= 0:
            raise RuntimeError("无法读取原片时长。")
    video_filter = packaged_filter(template, options, duration, clips)
    command = [ffmpeg_path(), "-hide_banner", "-y", "-i", str(temp)]
    next_input = 1
    stickers = timed_assets(options.get("stickers"), duration, "sticker")
    bgms = timed_assets(options.get("bgms"), duration, "bgm")
    focus_marks = normalize_focus_marks(options.get("focusMarks", []), [], duration)
    sticker_inputs = []
    for sticker in stickers:
        command.extend(["-i", str(sticker["path"])])
        sticker_inputs.append({**sticker, "input": next_input})
        next_input += 1
    use_bgm = bool(options.get("bgm", template.get("bgm", True)))
    bgm_inputs = []
    if use_bgm and bgms:
        for bgm in bgms:
            command.extend(["-stream_loop", "-1", "-i", str(bgm["path"])])
            bgm_inputs.append({**bgm, "input": next_input, "volume": "0.18"})
            next_input += 1
    elif use_bgm:
        command.extend(["-f", "lavfi", "-i", "sine=frequency=96:sample_rate=44100"])
        bgm_inputs.append({
            "path": None,
            "start": 0.0,
            "end": duration,
            "duration": duration,
            "input": next_input,
            "volume": "0.05",
        })
        next_input += 1
    has_audio = has_audio_stream(temp)

    video_parts = [f"[0:v]{video_filter}[v0]"]
    current_video = "v0"
    for index, sticker in enumerate(sticker_inputs, start=1):
        sticker_label = f"sticker{index}"
        next_video = f"v{index}"
        video_parts.append(f"[{sticker['input']}:v]format=rgba[{sticker_label}]")
        video_parts.append(
            f"[{current_video}][{sticker_label}]overlay=0:0:enable='between(t,{sticker['start']:.3f},{sticker['end']:.3f})':format=auto[{next_video}]"
        )
        current_video = next_video
    for index, mark in enumerate(focus_marks, start=1):
        next_video = f"vf{index}"
        if mark.get("effect") == "zoom":
            video_parts.extend(zoom_focus_filters(current_video, next_video, mark, index))
        else:
            video_parts.append(circle_focus_filter(current_video, next_video, mark))
        current_video = next_video
    video_parts.append(f"[{current_video}]copy[v]")

    audio_parts = []
    if bgm_inputs:
        audio_labels = []
        if has_audio:
            audio_parts.append("[0:a:0]volume=0.86[a0]")
            audio_labels.append("[a0]")
        for index, bgm in enumerate(bgm_inputs, start=1):
            label = f"bgm{index}"
            delay = int(float(bgm["start"]) * 1000)
            audio_parts.append(
                f"[{bgm['input']}:a]volume={bgm['volume']},atrim=0:{bgm['duration']:.3f},asetpts=PTS-STARTPTS,adelay={delay}|{delay}[{label}]"
            )
            audio_labels.append(f"[{label}]")
        mix_duration = "first" if has_audio else "longest"
        if len(audio_labels) == 1:
            audio_parts.append(f"{audio_labels[0]}apad,atrim=0:{duration:.3f}[a]")
        else:
            audio_parts.append(f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:duration={mix_duration}:dropout_transition=2,apad,atrim=0:{duration:.3f}[a]")
        command.extend(["-filter_complex", ";".join([*video_parts, *audio_parts]), "-map", "[v]", "-map", "[a]"])
    else:
        command.extend(["-filter_complex", ";".join(video_parts), "-map", "[v]", "-map", "0:a:0?"])
    command.extend([
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(output_path),
    ])
    result = run(command, timeout=None)
    if owns_temp:
        try:
            temp.unlink(missing_ok=True)
        except Exception:
            pass
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout)[-1600:])


def export_clip_segments(input_path: Path, output_dir: Path, clips: list[dict]) -> list[dict]:
    exported = []
    for index, clip in enumerate(clips, start=1):
        start = float(clip.get("start", 0))
        duration = float(clip.get("duration", 0))
        if duration <= 0:
            continue
        output = output_name_for(input_path, f"cut_{index}", output_dir)
        export_video(input_path, output, [clip])
        exported.append({
            "path": str(output),
            "start": start,
            "duration": seconds_to_clock(duration),
        })
    if not exported:
        raise RuntimeError("至少需要一个有效片段。")
    return exported


def preview_clip(input_path: Path, clip: dict) -> dict:
    start = max(0.0, float(clip.get("start", 0)))
    duration = min(90.0, max(0.1, float(clip.get("duration", 0))))
    output = PREVIEWS / f"preview_{uuid.uuid4().hex[:10]}.mp4"
    export_video(input_path, output, [{"start": start, "duration": duration}])
    return {
        "url": f"/previews/{output.name}",
        "path": str(output),
        "start": round(start, 1),
        "duration": seconds_to_clock(duration),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/":
            self.send_static(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            file_path = STATIC / path.removeprefix("/static/")
            content_type = "text/css" if file_path.suffix == ".css" else "application/javascript"
            self.send_static(file_path, content_type)
            return
        if path.startswith("/work/"):
            self.send_static(WORK / path.removeprefix("/work/"), "image/jpeg")
            return
        if path.startswith("/exports/"):
            self.send_static(EXPORTS / path.removeprefix("/exports/"), "video/mp4")
            return
        if path.startswith("/previews/"):
            self.send_static(PREVIEWS / path.removeprefix("/previews/"), "video/mp4")
            return
        if path.startswith("/api/task/"):
            task_id = path.removeprefix("/api/task/")
            with TASK_LOCK:
                task = dict(TASKS.get(task_id, {}))
                task.pop("processes", None)
            if not task:
                response(self, 404, {"error": "任务不存在。"})
                return
            response(self, 200, task)
            return
        if path == "/api/config":
            response(self, 200, public_config())
            return
        if path == "/api/history":
            response(self, 200, {"items": load_history()[:30]})
            return
        response(self, 404, {"error": "Not found"})

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)

            if path.startswith("/api/task/") and path.endswith("/cancel"):
                task_id = path.removeprefix("/api/task/").removesuffix("/cancel").strip("/")
                if not task_cancel(task_id):
                    response(self, 404, {"error": "任务不存在。"})
                    return
                response(self, 200, {"ok": True})
                return

            if self.path == "/api/probe":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                result = run([ffmpeg_path(), "-hide_banner", "-i", str(video)], timeout=30)
                response(self, 200, {"info": parse_media_info(result.stderr), "raw": result.stderr})
                return

            if self.path == "/api/pick-file":
                response(self, 200, {"path": choose_file()})
                return

            if self.path == "/api/pick-dir":
                response(self, 200, {"path": choose_folder()})
                return

            if self.path == "/api/pick-ffmpeg":
                response(self, 200, {"path": choose_binary()})
                return

            if self.path == "/api/pick-logo":
                response(self, 200, {"path": choose_logo()})
                return

            if self.path == "/api/pick-bgm":
                response(self, 200, {"path": choose_bgm()})
                return

            if self.path == "/api/config":
                payload = read_json(self)
                config = load_config()
                if "arkApiKey" in payload:
                    value = str(payload.get("arkApiKey", "")).strip()
                    if value:
                        config["arkApiKey"] = value
                if "ffmpegPath" in payload:
                    config["ffmpegPath"] = str(payload.get("ffmpegPath", "")).strip()
                if "wecomWebhookUrl" in payload:
                    config["wecomWebhookUrl"] = str(payload.get("wecomWebhookUrl", "")).strip()
                if "usageLogName" in payload:
                    config["usageLogName"] = str(payload.get("usageLogName", "")).strip()
                if "usageLogDept" in payload:
                    config["usageLogDept"] = str(payload.get("usageLogDept", "")).strip()
                if "packageTemplate" in payload:
                    config["packageTemplate"] = str(payload.get("packageTemplate", "")).strip()
                if "packageTemplates" in payload:
                    config["packageTemplates"] = normalize_package_templates(payload.get("packageTemplates"))
                save_config(config)
                response(self, 200, public_config())
                return

            if self.path == "/api/thumbs":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                interval = max(3, int(payload.get("interval", 10)))
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                notify_feature_used("生成缩略图", f"视频：{video.name}，间隔：{interval} 秒")
                def worker(tid: str) -> dict:
                    result = generate_thumbnails(video, interval, task_id=tid)
                    append_history("生成缩略图", video, summary=f"生成 {len(result.get('thumbs', []))} 张缩略图", interval=interval)
                    return result
                task_id = start_task("生成缩略图", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/auto":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                target = float(payload.get("target", 180))
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                notify_feature_used("识别高光", f"视频：{video.name}，目标时长：{target:g} 秒")
                def worker(tid: str) -> dict:
                    result = analyze_visual_highlights(video, target_seconds=target, task_id=tid)
                    append_history("识别高光", video, summary=result.get("summary", ""), duration=result.get("duration", ""), clips=result.get("clips", [])[:12])
                    return result
                task_id = start_task("识别高光", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/ai-auto":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                target = float(payload.get("target", 180))
                requirement = str(payload.get("requirement", "")).strip()[:1000]
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                detail = f"视频：{video.name}，目标时长：{target:g} 秒"
                if requirement:
                    detail += f"，要求：{requirement}"
                notify_feature_used("AI识别高光", detail)
                def worker(tid: str) -> dict:
                    result = analyze_ai_highlights(video, target_seconds=target, requirement=requirement, task_id=tid)
                    append_history("AI识别高光", video, summary=result.get("summary", ""), duration=result.get("duration", ""), requirement=requirement, clips=result.get("clips", [])[:12])
                    return result
                task_id = start_task("AI识别高光", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/ai-focus":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                clips = payload.get("clips", [])
                requirement = str(payload.get("requirement", "")).strip()[:1000]
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                detail = f"视频：{video.name}，片段数：{len(clips)}"
                if requirement:
                    detail += f"，要求：{requirement}"
                notify_feature_used("AI识别重点", detail)
                def worker(tid: str) -> dict:
                    result = analyze_ai_focus(video, clips, requirement=requirement, task_id=tid)
                    append_history("AI识别重点", video, summary=result.get("summary", ""), duration=result.get("duration", ""), requirement=requirement, focusMarks=result.get("focusMarks", [])[:12])
                    return result
                task_id = start_task("AI识别重点", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/storyboard":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                requirement = str(payload.get("requirement", "")).strip()[:1000]
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                detail = f"视频：{video.name}"
                if requirement:
                    detail += f"，要求：{requirement}"
                notify_feature_used("生成分镜脚本", detail)
                def worker(tid: str) -> dict:
                    result = analyze_ai_storyboard(video, requirement=requirement, task_id=tid)
                    append_history("生成分镜脚本", video, summary=result.get("summary", ""), duration=result.get("duration", ""), requirement=requirement, storyboard=result.get("shots", [])[:24])
                    return result
                task_id = start_task("生成分镜脚本", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/export-storyboard":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                summary = str(payload.get("summary", "")).strip()[:2000]
                shots = payload.get("shots", [])
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                output = export_storyboard_file(video, Path(choose_storyboard_output(video)), summary, shots)
                reveal_in_finder(output)
                notify_feature_used("导出分镜脚本", f"视频：{video.name}，镜头数：{len(shots) if isinstance(shots, list) else 0}")
                response(self, 200, {"path": str(output), "count": len(shots) if isinstance(shots, list) else 0})
                return

            if self.path == "/api/preview":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                clip = payload.get("clip", {})
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                result = preview_clip(video, clip)
                response(self, 200, result)
                return

            if self.path == "/api/export":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                output_dir_raw = payload.get("outputDir") or str(EXPORTS)
                output_dir = Path(output_dir_raw).expanduser()
                clips = payload.get("clips", [])
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                notify_feature_used("导出成片", f"视频：{video.name}，片段数：{len(clips)}")
                output_dir.mkdir(parents=True, exist_ok=True)
                output = output_name_for(video, "final", output_dir)
                export_video(video, output, clips)
                reveal_in_finder(output)
                total = sum(float(clip.get("duration", 0)) for clip in clips)
                append_history("导出成片", video, summary=f"导出 {len(clips)} 个片段", output=str(output), duration=seconds_to_clock(total), clips=clips[:12])
                response(self, 200, {
                    "url": f"/exports/{output.name}",
                    "path": str(output),
                    "duration": seconds_to_clock(total),
                })
                return

            if self.path == "/api/one-click":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                output_dir_raw = payload.get("outputDir") or str(EXPORTS)
                output_dir = Path(output_dir_raw).expanduser()
                clips = payload.get("clips", [])
                package = payload.get("package", {})
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                output_dir.mkdir(parents=True, exist_ok=True)
                output = output_name_for(video, "autofinal", output_dir)
                clip_count_text = len(clips) if clips else "原片"
                notify_feature_used("一键成片", f"视频：{video.name}，片段：{clip_count_text}，模板：{package.get('template', 'drama')}")
                export_packaged_video(video, output, clips, package)
                reveal_in_finder(output)
                total = sum(float(clip.get("duration", 0)) for clip in clips) if clips else media_duration_seconds(video)
                summary = f"套用包装导出 {len(clips)} 个片段" if clips else "基于原片完成一键成片"
                append_history("一键成片", video, summary=summary, output=str(output), duration=seconds_to_clock(total), clips=clips[:12], package=package)
                response(self, 200, {
                    "url": f"/exports/{output.name}",
                    "path": str(output),
                    "duration": seconds_to_clock(total),
                })
                return

            if self.path == "/api/export-segments":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                output_dir_raw = payload.get("outputDir") or str(EXPORTS)
                output_dir = Path(output_dir_raw).expanduser()
                clips = payload.get("clips", [])
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                notify_feature_used("导出片段", f"视频：{video.name}，片段数：{len(clips)}")
                output_dir.mkdir(parents=True, exist_ok=True)
                segments = export_clip_segments(video, output_dir, clips)
                reveal_in_finder(Path(segments[0]["path"]))
                append_history("导出片段", video, summary=f"导出 {len(segments)} 个独立片段", outputDir=str(output_dir), segments=segments[:12])
                response(self, 200, {"segments": segments, "count": len(segments)})
                return

            response(self, 404, {"error": "Unknown API"})
        except Exception as exc:
            response(self, 500, {"error": str(exc)})

    def send_static(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists() or not file_path.is_file():
            response(self, 404, {"error": "Not found"})
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Highlight client running at http://127.0.0.1:{port}")
    server.serve_forever()
