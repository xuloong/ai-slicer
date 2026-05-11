#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import base64
import statistics
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from PIL import Image, ImageChops, ImageStat

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
CONFIG_FILE = DATA_DIR / "user_config.json"
ARK_CHAT_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
ARK_MODEL = "doubao-seed-2-0-pro-260215"
FFMPEG_CANDIDATES = [
    "/Applications/QQBrowser.app/Contents/Frameworks/QQBrowser Framework.framework/Versions/21.0.6.203/FFmpeg/bin/ffmpeg",
    "/opt/homebrew/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "C:/ffmpeg/bin/ffmpeg.exe",
]

DATA_DIR.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)
EXPORTS.mkdir(parents=True, exist_ok=True)
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


def public_config() -> dict:
    config = load_config()
    api_key = os.environ.get("ARK_API_KEY") or config.get("arkApiKey", "")
    return {
        "hasArkApiKey": bool(api_key),
        "arkApiKeyMasked": f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 16 else "",
        "ffmpegPath": config.get("ffmpegPath", ""),
        "detectedFfmpegPath": detect_ffmpeg_path() or "",
    }


def detect_ffmpeg_path() -> str | None:
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


def ark_api_key() -> str:
    key = os.environ.get("ARK_API_KEY") or load_config().get("arkApiKey", "")
    if not key:
        raise RuntimeError("请先在设置里填写火山方舟 API Key。")
    return key


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
        with urllib.request.urlopen(request, timeout=600) as resp:
            ensure_not_cancelled(task_id)
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"火山方舟接口请求失败：HTTP {exc.code} {detail[-800:]}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接火山方舟接口：{exc}")
    return data["choices"][0]["message"]["content"]


def parse_ai_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def analyze_ai_highlights(video: Path, target_seconds: float = 180.0, task_id: str | None = None) -> dict:
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
        "task": "从候选短剧片段中选择适合剪成高光视频的片段。要求开头吸睛，中段剧情顺畅，结尾有钩子；优先保留完整情节单元，不要把一个关键对白拆断。",
        "target_seconds": target_seconds,
        "video_duration": round(analysis["duration"], 1),
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
        })
    if not clips:
        clips = windows_to_clips(select_local_windows(analysis, target_seconds))
    return {
        "clips": clips,
        "duration": seconds_to_clock(sum(clip["duration"] for clip in clips)),
        "summary": ai.get("summary") or f"AI 已基于 {len(candidates)} 个候选段落完成高光筛选。",
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
    for file, time in files:
        width, height = Image.open(file).size
        thumbs.append({
            "src": f"/work/{job}/{file.name}",
            "time": time,
            "width": width,
            "height": height,
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


def choose_folder() -> str:
    if is_macos():
        script = 'POSIX path of (choose folder with prompt "选择导出视频保存目录")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "已取消选择。")
        return result.stdout.strip()
    return choose_with_tkinter(kind="folder")


def choose_with_tkinter(kind: str) -> str:
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
    temp_dir = Path(tempfile.mkdtemp(prefix="highlight_export_"))
    part_paths = []
    try:
        for index, clip in enumerate(clips, start=1):
            start = float(clip["start"])
            duration = float(clip["duration"])
            if duration <= 0:
                continue
            part = temp_dir / f"part_{index:03d}.mp4"
            result = run([
                ffmpeg_path(), "-hide_banner", "-y",
                "-ss", f"{start:.3f}", "-i", str(input_path),
                "-t", f"{duration:.3f}",
                "-map", "0:v:0", "-map", "0:a:0?",
                "-c", "copy", "-avoid_negative_ts", "make_zero",
                str(part),
            ], timeout=240)
            if result.returncode != 0:
                raise RuntimeError((result.stderr or result.stdout)[-1500:])
            part_paths.append(part)
        if not part_paths:
            raise RuntimeError("至少需要一个有效片段。")

        list_file = temp_dir / "concat.txt"
        list_file.write_text(
            "\n".join(f"file '{path.as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for path in part_paths),
            encoding="utf-8",
        )
        concat = run([
            ffmpeg_path(), "-hide_banner", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", "-movflags", "+faststart",
            str(output_path),
        ], timeout=240)
        if concat.returncode != 0:
            raise RuntimeError((concat.stderr or concat.stdout)[-1500:])
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def export_video(input_path: Path, output_path: Path, clips: list[dict]) -> None:
    if is_macos():
        script = Path(tempfile.gettempdir()) / f"highlight_export_{uuid.uuid4().hex}.swift"
        script.write_text(make_swift_export(input_path, output_path, clips), encoding="utf-8")
        env = os.environ.copy()
        env["CLANG_MODULE_CACHE_PATH"] = str(WORK / ".clang-cache")
        result = subprocess.run(["swift", str(script)], text=True, capture_output=True, env=env, timeout=240)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout)[-1500:])
    else:
        export_with_ffmpeg(input_path, output_path, clips)


def export_clip_segments(input_path: Path, output_dir: Path, clips: list[dict]) -> list[dict]:
    exported = []
    for index, clip in enumerate(clips, start=1):
        start = float(clip.get("start", 0))
        duration = float(clip.get("duration", 0))
        if duration <= 0:
            continue
        output = output_dir / f"highlight_segment_{index:02d}_{uuid.uuid4().hex[:6]}.mp4"
        export_video(input_path, output, [clip])
        exported.append({
            "path": str(output),
            "start": start,
            "duration": seconds_to_clock(duration),
        })
    if not exported:
        raise RuntimeError("至少需要一个有效片段。")
    return exported


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

            if self.path == "/api/config":
                payload = read_json(self)
                config = load_config()
                if "arkApiKey" in payload:
                    value = str(payload.get("arkApiKey", "")).strip()
                    if value:
                        config["arkApiKey"] = value
                if "ffmpegPath" in payload:
                    config["ffmpegPath"] = str(payload.get("ffmpegPath", "")).strip()
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
                task_id = start_task("生成缩略图", lambda tid: generate_thumbnails(video, interval, task_id=tid))
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/auto":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                target = float(payload.get("target", 180))
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                task_id = start_task("识别高光", lambda tid: analyze_visual_highlights(video, target_seconds=target, task_id=tid))
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/ai-auto":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                target = float(payload.get("target", 180))
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                task_id = start_task("AI识别高光", lambda tid: analyze_ai_highlights(video, target_seconds=target, task_id=tid))
                response(self, 200, {"taskId": task_id})
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
                output_dir.mkdir(parents=True, exist_ok=True)
                output = output_dir / f"highlight_{uuid.uuid4().hex[:8]}.mp4"
                export_video(video, output, clips)
                reveal_in_finder(output)
                total = sum(float(clip.get("duration", 0)) for clip in clips)
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
                output_dir.mkdir(parents=True, exist_ok=True)
                segments = export_clip_segments(video, output_dir, clips)
                reveal_in_finder(Path(segments[0]["path"]))
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
