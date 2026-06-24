#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import base64
import hashlib
import hmac
import mimetypes
import socket
import statistics
import shutil
import ssl
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
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


def app_version() -> str:
    if os.environ.get("APP_VERSION"):
        return os.environ["APP_VERSION"].strip()
    for candidate in (
        DEV_ROOT / "src-tauri" / "tauri.conf.json",
        DEV_ROOT / "package.json",
        RESOURCE_ROOT / "src-tauri" / "tauri.conf.json",
        RESOURCE_ROOT / "package.json",
    ):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            version = str(data.get("version") or "").strip()
            if version:
                return version
        except Exception:
            continue
    return "0.1.0"


def app_data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "HighlightClient"


ROOT = DEV_ROOT
APP_VERSION = app_version()
STATIC = RESOURCE_ROOT / "static"
DATA_DIR = app_data_dir()
WORK = DATA_DIR / "work"
EXPORTS = DATA_DIR / "exports"
PREVIEWS = DATA_DIR / "previews"
DOWNLOADS = DATA_DIR / "downloads"
GENERATIONS = DATA_DIR / "generations"
CONFIG_FILE = DATA_DIR / "user_config.json"
HISTORY_FILE = DATA_DIR / "history.json"
ARK_CHAT_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
ARK_MODEL = "doubao-seed-2-0-pro-260215"
APIMART_IMAGE_URL = "https://api.apimart.ai/v1/images/generations"
APIMART_VIDEO_URL = "https://api.apimart.ai/v1/videos/generations"
APIMART_TASK_URL = "https://api.apimart.ai/v1/tasks"
APIMART_UPLOAD_IMAGE_URL = "https://api.apimart.ai/v1/uploads/images"
APIMART_UPLOAD_VIDEO_URL = "https://api.apimart.ai/v1/uploads/videos"
APIMART_UPLOAD_AUDIO_URL = "https://api.apimart.ai/v1/uploads/audios"
WECOM_APPID = "ww3356a195475005ac"
WECOM_AGENTID = "1000024"
WECOM_REDIRECT_URI = "https://sso.topsky.com/api/"
WECOM_STATE = "video"
WECOM_QR_CONNECT_URL = (
    "https://open.work.weixin.qq.com/wwopen/sso/qrConnect"
    f"?appid={WECOM_APPID}"
    f"&agentid={WECOM_AGENTID}"
    f"&redirect_uri={quote(WECOM_REDIRECT_URI, safe='')}"
    f"&state={WECOM_STATE}"
    "&lang=zh"
)
WECOM_LOGIN_URL = "https://sso.topsky.com/api/login/{code}"
DEFAULT_WECOM_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=e4a0df23-add9-4573-bcea-c606b9fac46a"
DEFAULT_ARK_API_KEY = "ark-8d0e9805-035e-4994-ba45-a09c7b51047c-34053"
DEFAULT_APIMART_API_KEY = "sk-rDsvyPdgzs1JpBmr7Y56lbtZjTxm36NTlE58iaTgrDq21AMA"
DEFAULT_TOS_ENDPOINT = "https://tos-cn-shanghai.volces.com"
DEFAULT_TOS_REGION = "cn-shanghai"
DEFAULT_TOS_BUCKET = "aivideo-topsky"
DEFAULT_TOS_ACCESS_KEY_ID = ""
DEFAULT_TOS_SECRET_ACCESS_KEY = ""
DEFAULT_TOS_PUBLIC_BASE_URL = "https://aivideo-topsky.tos-cn-shanghai.volces.com"
DEFAULT_TOS_OBJECT_PREFIX = "ai-short-video-generations"
DEFAULT_TLS_ENDPOINT = "https://tls-cn-shanghai.volces.com"
DEFAULT_TLS_REGION = "cn-shanghai"
DEFAULT_TLS_PROJECT_NAME = "aivideo"
DEFAULT_TLS_TOPIC_NAME = "client-usage"
DEFAULT_TLS_TTL_DAYS = 30
WECOM_SESSION_TTL = timedelta(hours=72)
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
DOWNLOADS.mkdir(parents=True, exist_ok=True)
GENERATIONS.mkdir(parents=True, exist_ok=True)
TASKS: dict[str, dict] = {}
TASK_LOCK = threading.Lock()
AUTH_LOCK = threading.Lock()
WECOM_SESSION: dict[str, object] = {}
TLS_LOCK = threading.Lock()
TLS_TOPIC_CACHE: dict[str, str] = {}


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


def storyboard_history_with_generated(all_shots: object, generated: list[dict], index: int | None = None) -> list[dict]:
    if isinstance(all_shots, list) and all_shots:
        history = [dict(shot) if isinstance(shot, dict) else shot for shot in all_shots[:24]]
        if index is not None and 0 <= index < len(history) and generated:
            if isinstance(history[index], dict):
                history[index].update(generated[0])
            else:
                history[index] = generated[0]
        elif len(generated) == len(history):
            history = generated[:24]
        elif generated:
            by_shot = {str(item.get("shot") or ""): item for item in generated if isinstance(item, dict)}
            for pos, shot in enumerate(history):
                if isinstance(shot, dict) and str(shot.get("shot") or "") in by_shot:
                    history[pos].update(by_shot[str(shot.get("shot") or "")])
        return [shot for shot in history if isinstance(shot, dict)]
    return generated[:24]


def ark_api_key_value(config: dict | None = None) -> str:
    return os.environ.get("ARK_API_KEY") or DEFAULT_ARK_API_KEY


def apimart_api_key_value(config: dict | None = None) -> str:
    return os.environ.get("APIMART_API_KEY") or DEFAULT_APIMART_API_KEY


def public_config() -> dict:
    config = load_config()
    api_key = ark_api_key_value(config)
    apimart_key = apimart_api_key_value(config)
    douyin_cookie = str(config.get("douyinCookie") or "").strip()
    return {
        "version": APP_VERSION,
        "hasArkApiKey": bool(api_key),
        "arkApiKeyMasked": f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 16 else "",
        "hasApimartApiKey": bool(apimart_key),
        "apimartApiKeyMasked": f"{apimart_key[:8]}...{apimart_key[-4:]}" if len(apimart_key) > 16 else "",
        "hasDouyinCookie": bool(douyin_cookie),
        "douyinCookieMasked": f"已配置，长度 {len(douyin_cookie)}" if douyin_cookie else "",
        "apimartImageSize": config.get("apimartImageSize", "9:16"),
        "apimartImageResolution": config.get("apimartImageResolution", "1k"),
        "apimartImageQuality": config.get("apimartImageQuality", "medium"),
        "seedanceDuration": config.get("seedanceDuration", 5),
        "seedanceResolution": config.get("seedanceResolution", "720p"),
        "seedanceSize": config.get("seedanceSize", "adaptive"),
        "seedanceAudio": bool(config.get("seedanceAudio", True)),
        "ffmpegPath": config.get("ffmpegPath", ""),
        "detectedFfmpegPath": detect_ffmpeg_path() or "",
        "downloadRetentionDays": download_retention_days(),
        "packageTemplate": config.get("packageTemplate", "none"),
        "packageTemplates": configured_package_templates(),
    }


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def wecom_webhook_url() -> str:
    return DEFAULT_WECOM_WEBHOOK_URL


def current_wecom_user() -> dict:
    with AUTH_LOCK:
        user = dict(WECOM_SESSION.get("userInfo") or {})
        token = str(WECOM_SESSION.get("token") or "")
        login_time = str(WECOM_SESSION.get("loginTime") or "")
        if user:
            try:
                if datetime.now() - datetime.strptime(login_time, "%Y-%m-%d %H:%M:%S") > WECOM_SESSION_TTL:
                    WECOM_SESSION.clear()
                    return {}
            except ValueError:
                WECOM_SESSION.clear()
                return {}
    if user:
        return {
            "username": str(user.get("username") or user.get("modifiedName") or user.get("englishname") or "").strip(),
            "deptName": str(user.get("deptName") or "").strip(),
            "companyName": str(user.get("companyName") or "").strip(),
            "email": str(user.get("email") or "").strip(),
            "id": str(user.get("id") or "").strip(),
            "token": token,
        }
    return {}


def auth_state() -> dict:
    user = current_wecom_user()
    return {"loggedIn": bool(user), "user": user}


def extract_wecom_code(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        return (parse_qs(parsed.query).get("code") or [""])[0].strip()
    match = re.search(r"(?:code=)?([A-Za-z0-9_-]{8,})", text)
    return match.group(1).strip() if match else text


def login_with_wecom_code(code: str) -> dict:
    code = extract_wecom_code(code)
    if not code:
        raise RuntimeError("未获取到企业微信登录 code。")
    request = urllib.request.Request(
        WECOM_LOGIN_URL.format(code=quote(code, safe="")),
        headers={"accept": "application/json"},
        method="GET",
    )
    try:
        raw = urllib.request.urlopen(request, timeout=20, context=ark_ssl_context()).read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"企业微信登录失败：HTTP {exc.code} {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接企业微信登录接口：{exc}") from exc
    data = json.loads(raw.decode("utf-8") or "{}")
    user = data.get("userInfo") if isinstance(data, dict) else None
    if not isinstance(user, dict) or not user:
        raise RuntimeError(str(data.get("desc") or data.get("message") or "企业微信登录信息为空。"))
    with AUTH_LOCK:
        WECOM_SESSION.clear()
        WECOM_SESSION.update({
            "token": data.get("token") or user.get("token") or "",
            "userInfo": user,
            "loginTime": now_text(),
        })
    notify_feature_used("企业微信登录", "扫码登录成功")
    return auth_state()


def usage_identity() -> tuple[str, str]:
    user = current_wecom_user()
    if user:
        return user.get("username") or "企业微信用户", user.get("deptName") or "未填写"
    return "未登录用户", "未登录部门"


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


def tls_config() -> dict[str, object]:
    return {
        "endpoint": (os.environ.get("TLS_ENDPOINT") or DEFAULT_TLS_ENDPOINT).strip(),
        "region": (os.environ.get("TLS_REGION") or DEFAULT_TLS_REGION).strip() or DEFAULT_TLS_REGION,
        "project_name": (os.environ.get("TLS_PROJECT_NAME") or DEFAULT_TLS_PROJECT_NAME).strip() or DEFAULT_TLS_PROJECT_NAME,
        "topic_name": (os.environ.get("TLS_TOPIC_NAME") or DEFAULT_TLS_TOPIC_NAME).strip() or DEFAULT_TLS_TOPIC_NAME,
        "ttl": int(os.environ.get("TLS_TTL_DAYS") or DEFAULT_TLS_TTL_DAYS),
        "access_key": (os.environ.get("TLS_ACCESS_KEY_ID") or os.environ.get("TOS_ACCESS_KEY_ID") or DEFAULT_TOS_ACCESS_KEY_ID).strip(),
        "secret_key": (os.environ.get("TLS_SECRET_ACCESS_KEY") or os.environ.get("TOS_SECRET_ACCESS_KEY") or DEFAULT_TOS_SECRET_ACCESS_KEY).strip(),
    }


def tls_client(config: dict | None = None):
    config = config or tls_config()
    from volcengine.tls.TLSService import TLSService
    return TLSService(
        str(config["endpoint"]),
        str(config["access_key"]),
        str(config["secret_key"]),
        str(config["region"]),
        timeout=20,
    )


def resolve_tls_topic_id(client, config: dict) -> str:
    cache_key = f"{config['endpoint']}|{config['region']}|{config['project_name']}|{config['topic_name']}"
    with TLS_LOCK:
        cached = TLS_TOPIC_CACHE.get(cache_key)
        if cached:
            return cached

    from volcengine.tls.tls_requests import CreateTopicRequest, DescribeProjectsRequest, DescribeTopicsRequest

    projects_resp = client.describe_projects(DescribeProjectsRequest(
        project_name=str(config["project_name"]),
        is_full_name=True,
        page_size=10,
    ))
    projects = projects_resp.get_projects()
    if not projects:
        raise RuntimeError(f"TLS 日志项目不存在：{config['project_name']}")
    project_id = projects[0].project_id

    topics_resp = client.describe_topics(DescribeTopicsRequest(
        project_id=project_id,
        topic_name=str(config["topic_name"]),
        is_full_name=True,
        page_size=10,
    ))
    topics = topics_resp.get_topics()
    topic_id = topics[0].topic_id if topics else ""
    if not topic_id:
        topic_id = client.create_topic(CreateTopicRequest(
            topic_name=str(config["topic_name"]),
            project_id=project_id,
            ttl=int(config.get("ttl") or DEFAULT_TLS_TTL_DAYS),
            shard_count=1,
            description="AI短视频创作工具客户端使用日志",
            auto_split=True,
        )).get_topic_id()

    with TLS_LOCK:
        TLS_TOPIC_CACHE[cache_key] = topic_id
    return topic_id


def send_tls_log(record: dict[str, object]) -> None:
    try:
        from volcengine.tls.tls_requests import PutLogsV2Logs, PutLogsV2Request

        config = tls_config()
        if not config["access_key"] or not config["secret_key"]:
            return
        client = tls_client(config)
        topic_id = resolve_tls_topic_id(client, config)
        log = PutLogsV2Logs(
            source=socket.gethostname() or "client",
            filename="ai-short-video-client",
            log_tags={"app": "AI短视频创作工具", "version": APP_VERSION},
        )
        contents = {}
        for key, value in record.items():
            if value is None:
                continue
            if isinstance(value, (dict, list)):
                contents[key] = json.dumps(value, ensure_ascii=False)[:8000]
            else:
                contents[key] = str(value)[:8000]
        log.add_log(contents, log_time=int(time.time()))
        client.put_logs_v2(PutLogsV2Request(topic_id, log))
    except Exception:
        pass


def notify_tls(record: dict[str, object]) -> None:
    threading.Thread(target=send_tls_log, args=(record,), daemon=True).start()


def usage_log_base(event_type: str, feature: str) -> dict[str, object]:
    user, dept = usage_identity()
    current_user = current_wecom_user()
    return {
        "event_type": event_type,
        "feature": feature,
        "user": user,
        "dept": dept,
        "company": current_user.get("companyName", ""),
        "email": current_user.get("email", ""),
        "user_id": current_user.get("id", ""),
        "version": APP_VERSION,
        "time": now_text(),
        "platform": sys.platform,
    }


def notify_feature_used(feature: str, details: str = "") -> None:
    user, dept = usage_identity()
    lines = [
        "AI短视频创作工具功能使用通知",
        f"> 姓名：{user}",
        f"> 部门：{dept}",
        f"> 版本：{APP_VERSION}",
        f"> 功能：{feature}",
        f"> 时间：{now_text()}",
    ]
    if details:
        lines.append(f"> 详情：{details[:2500]}")
    notify_wecom("\n".join(lines))
    record = usage_log_base("feature", feature)
    record["details"] = details
    notify_tls(record)


def compact_log_text(value: object, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1] + "…"


def tos_config() -> dict[str, str]:
    endpoint = (os.environ.get("TOS_ENDPOINT") or DEFAULT_TOS_ENDPOINT).strip().rstrip("/")
    if endpoint and not endpoint.startswith(("http://", "https://")):
        endpoint = f"https://{endpoint}"
    bucket = (os.environ.get("TOS_BUCKET") or DEFAULT_TOS_BUCKET).strip()
    access_key = (os.environ.get("TOS_ACCESS_KEY_ID") or DEFAULT_TOS_ACCESS_KEY_ID).strip()
    secret_key = (os.environ.get("TOS_SECRET_ACCESS_KEY") or DEFAULT_TOS_SECRET_ACCESS_KEY).strip()
    region = (os.environ.get("TOS_REGION") or DEFAULT_TOS_REGION).strip() or DEFAULT_TOS_REGION
    return {
        "endpoint": endpoint,
        "bucket": bucket,
        "access_key": access_key,
        "secret_key": secret_key,
        "region": region,
        "service": os.environ.get("TOS_SERVICE", "tos").strip() or "tos",
        "prefix": os.environ.get("TOS_OBJECT_PREFIX", DEFAULT_TOS_OBJECT_PREFIX).strip().strip("/") or DEFAULT_TOS_OBJECT_PREFIX,
        "public_base_url": (os.environ.get("TOS_PUBLIC_BASE_URL") or DEFAULT_TOS_PUBLIC_BASE_URL).strip().rstrip("/"),
        "acl": os.environ.get("TOS_ACL", "").strip(),
    }


def tos_enabled() -> bool:
    config = tos_config()
    return bool(config["endpoint"] and config["bucket"] and config["access_key"] and config["secret_key"])


def tos4_signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    key_date = hmac.new(("TOS4" + secret_key).encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256).digest()
    key_region = hmac.new(key_date, region.encode("utf-8"), hashlib.sha256).digest()
    key_service = hmac.new(key_region, service.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(key_service, b"request", hashlib.sha256).digest()


def quote_object_key(value: str) -> str:
    return "/".join(quote(part, safe="") for part in value.split("/"))


def tos_public_url(object_key: str, request_url: str = "") -> str:
    config = tos_config()
    if config["public_base_url"]:
        return f"{config['public_base_url']}/{quote_object_key(object_key)}"
    return request_url


def upload_to_tos(path: Path, kind: str = "asset") -> dict:
    if not tos_enabled():
        return {"enabled": False, "objectKey": "", "url": "", "uploadUrl": "", "error": "TOS 未配置"}
    if not path.exists() or not path.is_file():
        return {"enabled": True, "objectKey": "", "url": "", "uploadUrl": "", "error": f"文件不存在：{path}"}
    config = tos_config()
    parsed = urlparse(config["endpoint"])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"enabled": True, "objectKey": "", "url": "", "uploadUrl": "", "error": f"TOS endpoint 无效：{config['endpoint']}"}
    date_stamp = datetime.utcnow().strftime("%Y%m%d")
    amz_date = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.name).strip("._") or f"{uuid.uuid4().hex}{path.suffix}"
    object_key = f"{config['prefix']}/{date_stamp}/{uuid.uuid4().hex[:12]}_{safe_name}"
    upload_host = parsed.netloc if parsed.netloc.startswith(f"{config['bucket']}.") else f"{config['bucket']}.{parsed.netloc}"
    canonical_uri = f"/{quote_object_key(object_key)}"
    request_url = f"{parsed.scheme}://{upload_host}{canonical_uri}"
    public_url = tos_public_url(object_key, request_url)
    body = path.read_bytes()
    payload_hash = hashlib.sha256(body).hexdigest()
    content_type = mimetypes.guess_type(path.name)[0] or ("video/mp4" if kind == "video" else "image/png")
    try:
        import tos
        sdk_endpoint = parsed.netloc.removeprefix(f"{config['bucket']}.")
        client = tos.TosClientV2(
            config["access_key"],
            config["secret_key"],
            sdk_endpoint,
            config["region"],
        )
        with path.open("rb") as file:
            client.put_object(
                config["bucket"],
                object_key,
                content=file,
                content_type=content_type,
            )
        return {"enabled": True, "objectKey": object_key, "url": public_url, "uploadUrl": request_url, "error": ""}
    except ImportError:
        pass
    except Exception as exc:
        return {"enabled": True, "objectKey": object_key, "url": public_url, "uploadUrl": request_url, "error": f"TOS SDK 上传失败：{exc}"}

    headers = {
        "Host": upload_host,
        "x-tos-content-sha256": payload_hash,
        "x-tos-date": amz_date,
    }
    if config["acl"]:
        headers["x-tos-acl"] = config["acl"]
    signed_header_names = sorted(headers.keys(), key=str.lower)
    canonical_headers = "".join(f"{name.lower()}:{headers[name]}\n" for name in signed_header_names)
    signed_headers = ";".join(name.lower() for name in signed_header_names)
    canonical_request = "\n".join([
        "PUT",
        canonical_uri,
        "",
        canonical_headers,
        signed_headers,
        payload_hash,
    ])
    scope = f"{date_stamp}/{config['region']}/{config['service']}/request"
    string_to_sign = "\n".join([
        "TOS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signature = hmac.new(
        tos4_signing_key(config["secret_key"], date_stamp, config["region"], config["service"]),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers["Authorization"] = (
        "TOS4-HMAC-SHA256 "
        f"Credential={config['access_key']}/{scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    headers["Content-Type"] = content_type
    request = urllib.request.Request(request_url, data=body, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(request, timeout=240, context=ark_ssl_context()) as resp:
            if resp.status >= 300:
                return {"enabled": True, "objectKey": object_key, "url": public_url, "uploadUrl": request_url, "error": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return {"enabled": True, "objectKey": object_key, "url": public_url, "uploadUrl": request_url, "error": f"HTTP {exc.code}: {body_text[:500]}"}
    except Exception as exc:
        return {"enabled": True, "objectKey": object_key, "url": public_url, "uploadUrl": request_url, "error": str(exc)}
    return {"enabled": True, "objectKey": object_key, "url": public_url, "uploadUrl": request_url, "error": ""}


def store_generated_asset(path: Path, kind: str, task_id: str | None = None) -> dict:
    if not tos_enabled():
        return {"enabled": False, "objectKey": "", "url": "", "uploadUrl": "", "error": "TOS 未配置"}
    return upload_to_tos(path, kind=kind)


def notify_generation_asset(feature: str, prompt: str, params: dict, storage: dict | str = "", source_url: str = "", local_path: str = "") -> None:
    user, dept = usage_identity()
    param_text = "，".join(f"{key}={value}" for key, value in params.items() if value not in {"", None})
    storage_data = storage if isinstance(storage, dict) else {"url": str(storage or ""), "objectKey": "", "error": ""}
    storage_url = str(storage_data.get("url") or "")
    storage_key = str(storage_data.get("objectKey") or "")
    storage_error = str(storage_data.get("error") or "")
    lines = [
        "AI短视频创作工具生成素材通知",
        f"> 姓名：{user}",
        f"> 部门：{dept}",
        f"> 版本：{APP_VERSION}",
        f"> 功能：{feature}",
        f"> 时间：{now_text()}",
    ]
    if param_text:
        lines.append(f"> 参数：{param_text}")
    lines.append(f"> 提示词：{compact_log_text(prompt, 1300) or '未记录到提示词'}")
    if storage_key:
        lines.append(f"> 对象存储路径：{storage_key}")
    if storage_url:
        lines.append(f"> 对象存储链接：{storage_url}")
    if storage_error:
        lines.append(f"> 对象存储状态：上传失败：{compact_log_text(storage_error, 260)}")
    if source_url:
        lines.append(f"> 生成平台链接：{source_url}")
    if local_path:
        lines.append(f"> 本地路径：{local_path}")
    notify_wecom("\n".join(lines))
    record = usage_log_base("generation_asset", feature)
    record.update({
        "prompt": prompt,
        "params": params,
        "storage_path": storage_key,
        "storage_url": storage_url,
        "storage_error": storage_error,
        "source_url": source_url,
        "local_path": local_path,
    })
    notify_tls(record)


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


def extract_share_url(value: str) -> str:
    match = re.search(r"https?://[^\s<>'\"，。；、]+", value or "")
    if not match:
        raise RuntimeError("没有识别到有效链接，请粘贴抖音或小红书分享链接。")
    return match.group(0).rstrip(").,，。")


def download_retention_days() -> int:
    try:
        return max(0, int(load_config().get("downloadRetentionDays", 30)))
    except (TypeError, ValueError):
        return 30


def cleanup_old_downloads() -> int:
    days = download_retention_days()
    if days <= 0:
        return 0
    cutoff = datetime.now().timestamp() - days * 86400
    removed = 0
    for item in DOWNLOADS.iterdir():
        try:
            if item.stat().st_mtime >= cutoff:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed += 1
        except Exception:
            continue
    return removed


def needs_fresh_cookies_error(error: object) -> bool:
    text = str(error or "").lower()
    return "fresh cookies" in text or "cookies" in text and "needed" in text


def browser_profile_names(browser: str) -> list[str]:
    if is_macos():
        roots = {
            "chrome": Path.home() / "Library" / "Application Support" / "Google" / "Chrome",
            "edge": Path.home() / "Library" / "Application Support" / "Microsoft Edge",
            "firefox": Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles",
        }
    elif is_windows():
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        roaming = Path(os.environ.get("APPDATA", ""))
        roots = {
            "chrome": local / "Google" / "Chrome" / "User Data",
            "edge": local / "Microsoft" / "Edge" / "User Data",
            "firefox": roaming / "Mozilla" / "Firefox" / "Profiles",
        }
    else:
        roots = {
            "chrome": Path.home() / ".config" / "google-chrome",
            "edge": Path.home() / ".config" / "microsoft-edge",
            "firefox": Path.home() / ".mozilla" / "firefox",
        }
    root = roots.get(browser)
    if not root or not root.exists():
        return []
    if browser == "firefox":
        return [item.name for item in root.iterdir() if (item / "cookies.sqlite").exists()]
    return [item.name for item in root.iterdir() if (item / "Cookies").exists()]


def browser_cookie_sources() -> list[tuple[str, tuple]]:
    configured = str(load_config().get("downloadCookieBrowser") or "auto").strip().lower()
    if configured and configured not in {"auto", "none", "off"}:
        profiles = browser_profile_names(configured)
        return [(f"{configured} {profile}", (configured, profile, None, None)) for profile in profiles] or [(configured, (configured, None, None, None))]
    if configured in {"none", "off"}:
        return []
    if is_macos():
        browsers = ["chrome", "edge", "safari", "firefox"]
    if is_windows():
        browsers = ["chrome", "edge", "firefox"]
    if not is_macos() and not is_windows():
        browsers = ["chrome", "edge", "firefox"]
    sources: list[tuple[str, tuple]] = []
    for browser in browsers:
        profiles = browser_profile_names(browser)
        if profiles:
            sources.extend((f"{browser} {profile}", (browser, profile, None, None)) for profile in profiles)
        else:
            sources.append((browser, (browser, None, None, None)))
    return sources


def browser_cookie_cli_arg(source: tuple) -> str:
    browser, profile, keyring, container = (list(source) + [None, None, None, None])[:4]
    parts = [str(browser)]
    if profile:
        parts.append(str(profile))
    if keyring:
        parts.append(str(keyring))
    if container:
        parts.append(str(container))
    return ":".join(parts)


def configured_douyin_cookie() -> str:
    return str(load_config().get("douyinCookie") or os.environ.get("DOUYIN_COOKIE") or "").strip()


def parse_cookie_header(cookie_text: str) -> list[tuple[str, str]]:
    text = cookie_text.strip()
    text = re.sub(r"^\s*cookie\s*:\s*", "", text, flags=re.I)
    pairs = []
    for part in re.split(r";\s*", text):
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        pairs.append((name, value))
    return pairs


def write_douyin_cookie_file(out_dir: Path) -> str:
    pairs = parse_cookie_header(configured_douyin_cookie())
    if not pairs:
        return ""
    cookie_file = out_dir / "douyin_cookies.txt"
    domains = [".douyin.com", "douyin.com", ".iesdouyin.com", ".snssdk.com", ".amemv.com"]
    lines = ["# Netscape HTTP Cookie File"]
    expiry = str(int((datetime.now() + timedelta(days=30)).timestamp()))
    for domain in domains:
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        for name, value in pairs:
            lines.append("\t".join([domain, include_subdomains, "/", "TRUE", expiry, name, value]))
    cookie_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(cookie_file)


def douyin_mobile_headers(referer: str = "https://www.douyin.com/") -> dict[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 aweme_32.0.0",
        "Referer": referer,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    cookie = configured_douyin_cookie()
    if cookie:
        headers["Cookie"] = cookie
    return headers


def decode_douyin_escaped_url(value: str) -> str:
    return (
        value
        .replace(chr(92) + "u002F", "/")
        .replace(chr(92) + "/", "/")
        .replace("&amp;", "&")
    )


def extract_douyin_video_id(value: str) -> str:
    match = re.search(r"/video/(\d+)", value or "")
    if match:
        return match.group(1)
    match = re.search(r"aweme_id[=:](\d+)", value or "")
    return match.group(1) if match else ""


def fetch_douyin_page(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers=douyin_mobile_headers())
    with urllib.request.urlopen(request, timeout=30, context=ark_ssl_context()) as resp:
        final_url = resp.geturl()
        html_text = resp.read().decode("utf-8", errors="replace")
    return final_url, html_text


def extract_douyin_play_url(html_text: str) -> str:
    candidates = re.findall(r"https:[^\"<>]+aweme\.snssdk\.com[^\"<>]+", html_text or "")
    for raw_url in candidates:
        url = decode_douyin_escaped_url(raw_url)
        if "/aweme/v1/play" in url:
            return url
    return ""


def extract_douyin_title(html_text: str, fallback: str) -> str:
    for pattern in (r'"desc":"([^"]+)"', r'"share_title":"([^"]+)"', r"<title>(.*?)</title>"):
        match = re.search(pattern, html_text or "", flags=re.S)
        if match:
            value = match.group(1)
            if chr(92) + "u" in value or chr(92) + "/" in value:
                value = value.encode("utf-8").decode("unicode_escape", errors="ignore")
            value = re.sub(r"\s+", " ", value).strip()
            if value:
                return value[:80]
    return fallback


def safe_filename(value: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value or "")).strip(" ._")
    return text or "douyin_video"


def download_direct_video_url(url: str, output: Path, referer: str, task_id: str | None = None) -> Path:
    ensure_not_cancelled(task_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers=douyin_mobile_headers(referer))
    with urllib.request.urlopen(request, timeout=60, context=ark_ssl_context()) as resp:
        content_type = str(resp.headers.get("content-type") or "").lower()
        if "video" not in content_type and "octet-stream" not in content_type:
            preview = resp.read(300).decode("utf-8", errors="replace")
            raise RuntimeError(f"播放地址没有返回视频数据：{content_type} {preview[:120]}")
        total = int(resp.headers.get("content-length") or 0)
        done = 0
        with output.open("wb") as file:
            while True:
                ensure_not_cancelled(task_id)
                chunk = resp.read(1024 * 512)
                if not chunk:
                    break
                file.write(chunk)
                done += len(chunk)
                if task_id and total:
                    task_update(task_id, 30 + int(min(1.0, done / max(1, total)) * 55), "正在下载抖音视频")
    return output


def download_douyin_from_page(url: str, out_dir: Path, task_id: str | None = None) -> dict:
    if task_id:
        task_update(task_id, 22, "正在尝试从抖音页面提取播放地址")
    page_url, html_text = fetch_douyin_page(url)
    play_url = extract_douyin_play_url(html_text)
    if not play_url:
        raise RuntimeError("没有从抖音页面中找到可下载播放地址。")
    video_id = extract_douyin_video_id(page_url) or uuid.uuid4().hex[:10]
    title = extract_douyin_title(html_text, f"douyin_{video_id}")
    output = out_dir / f"{safe_filename(title)[:70]}_{video_id}.mp4"
    download_direct_video_url(play_url, output, page_url, task_id=task_id)
    if task_id:
        task_update(task_id, 96, "正在读取下载视频信息")
    duration = media_duration_seconds(output)
    return {
        "path": str(output),
        "url": url,
        "title": title,
        "duration": seconds_to_clock(duration) if duration > 0 else "未知",
        "method": "douyin_page_fallback",
    }


def download_cookie_help() -> str:
    return (
        "抖音要求使用新鲜 Cookie 才能下载。请在设置里粘贴抖音 Cookie，或先在本机浏览器打开并刷新一次抖音后重试。"
    )


def ytdlp_base_options(out_dir: Path, hook) -> dict:
    options = {
        "outtmpl": str(out_dir / "%(title).80s_%(id)s.%(ext)s"),
        "format": "bv*+ba/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Referer": "https://www.douyin.com/",
        },
    }
    cookie_file = write_douyin_cookie_file(out_dir)
    if cookie_file:
        options["cookiefile"] = cookie_file
    return options


def run_ytdlp_download(yt_dlp, url: str, options: dict, task_id: str | None = None) -> tuple[dict, str]:
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        ensure_not_cancelled(task_id)
        filename = ydl.prepare_filename(info)
        if options.get("merge_output_format") and Path(filename).suffix.lower() != ".mp4":
            filename = str(Path(filename).with_suffix(".mp4"))
        return info, filename


def download_video_from_url(share_text: str, task_id: str | None = None) -> dict:
    cleanup_old_downloads()
    url = extract_share_url(share_text)
    job = uuid.uuid4().hex[:10]
    out_dir = DOWNLOADS / job
    out_dir.mkdir(parents=True, exist_ok=True)
    if task_id:
        task_update(task_id, 8, "正在解析分享链接")

    try:
        import yt_dlp
    except Exception:
        yt_dlp = None

    if yt_dlp is not None:
        downloaded: list[str] = []

        def hook(info: dict) -> None:
            ensure_not_cancelled(task_id)
            status = info.get("status")
            if status == "downloading":
                total = info.get("total_bytes") or info.get("total_bytes_estimate") or 0
                done = info.get("downloaded_bytes") or 0
                percent = 20 + int(min(1.0, done / max(1, total)) * 65) if total else 30
                if task_id:
                    task_update(task_id, percent, "正在下载视频")
            elif status == "finished":
                filename = info.get("filename")
                if filename:
                    downloaded.append(filename)
                if task_id:
                    task_update(task_id, 88, "正在整理视频文件")

        options = ytdlp_base_options(out_dir, hook)
        last_error: Exception | None = None
        try:
            info, filename = run_ytdlp_download(yt_dlp, url, options, task_id=task_id)
        except TaskCancelled:
            raise
        except Exception as exc:
            last_error = exc
            if not needs_fresh_cookies_error(exc):
                raise RuntimeError(f"下载失败：{exc}") from exc
            for label, cookie_source in browser_cookie_sources():
                ensure_not_cancelled(task_id)
                if task_id:
                    task_update(task_id, 18, f"抖音需要 Cookie，正在尝试读取 {label} Cookie")
                cookie_options = dict(options)
                cookie_options.pop("cookiefile", None)
                cookie_options["cookiesfrombrowser"] = cookie_source
                try:
                    info, filename = run_ytdlp_download(yt_dlp, url, cookie_options, task_id=task_id)
                    break
                except TaskCancelled:
                    raise
                except Exception as cookie_exc:
                    last_error = cookie_exc
            else:
                try:
                    return download_douyin_from_page(url, out_dir, task_id=task_id)
                except Exception as fallback_exc:
                    raise RuntimeError(f"下载失败：{download_cookie_help()} fallback 也失败：{fallback_exc} 原始错误：{last_error}") from fallback_exc
        candidates = [Path(item) for item in downloaded]
        candidates.append(Path(filename))
        candidates.extend(sorted(out_dir.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True))
        video = next((item for item in candidates if item.exists() and item.is_file() and item.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}), None)
        if not video:
            raise RuntimeError("下载完成但没有找到视频文件。")
        if task_id:
            task_update(task_id, 96, "正在读取下载视频信息")
        duration = media_duration_seconds(video)
        return {
            "path": str(video),
            "url": url,
            "title": str(info.get("title") or video.stem),
            "duration": seconds_to_clock(duration) if duration > 0 else "未知",
        }

    binary = shutil.which("yt-dlp")
    if not binary:
        raise RuntimeError("当前环境缺少 yt-dlp，无法下载抖音/小红书视频。请重新打包新版客户端，或安装 yt-dlp。")
    if task_id:
        task_update(task_id, 20, "正在下载视频")
    output = out_dir / "%(title).80s_%(id)s.%(ext)s"
    command = [
        binary, "--no-playlist", "-f", "bv*+ba/best",
        "--merge-output-format", "mp4", "--referer", "https://www.douyin.com/",
        "-o", str(output), url,
    ]
    cookie_file = write_douyin_cookie_file(out_dir)
    if cookie_file:
        command[1:1] = ["--cookies", cookie_file]
    result = run(command, timeout=None, task_id=task_id)
    if result.returncode != 0 and needs_fresh_cookies_error(result.stderr):
        for label, cookie_source in browser_cookie_sources():
            ensure_not_cancelled(task_id)
            if task_id:
                task_update(task_id, 18, f"抖音需要 Cookie，正在尝试读取 {label} Cookie")
            result = run([
                binary, "--no-playlist", "-f", "bv*+ba/best",
                "--merge-output-format", "mp4", "--referer", "https://www.douyin.com/",
                "--cookies-from-browser", browser_cookie_cli_arg(cookie_source),
                "-o", str(output), url,
            ], timeout=None, task_id=task_id)
            if result.returncode == 0:
                break
    if result.returncode != 0:
        if needs_fresh_cookies_error(result.stderr):
            try:
                return download_douyin_from_page(url, out_dir, task_id=task_id)
            except Exception as fallback_exc:
                raise RuntimeError(f"下载失败：{download_cookie_help()} fallback 也失败：{fallback_exc} 原始错误：{result_tail(result, 900)}") from fallback_exc
        raise RuntimeError(result_tail(result, 1200))
    video = next((item for item in sorted(out_dir.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True) if item.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}), None)
    if not video:
        raise RuntimeError("下载完成但没有找到视频文件。")
    duration = media_duration_seconds(video)
    return {"path": str(video), "url": url, "title": video.stem, "duration": seconds_to_clock(duration) if duration > 0 else "未知"}


def ark_api_key() -> str:
    key = ark_api_key_value()
    if not key:
        raise RuntimeError("火山方舟默认 API Key 不可用，请联系管理员。")
    return key


def apimart_api_key() -> str:
    key = apimart_api_key_value()
    if not key:
        raise RuntimeError("AI 生成默认 API Key 不可用，请联系管理员。")
    return key


def ark_ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            pass
    return ssl.create_default_context()


def json_request(method: str, url: str, payload: dict | None = None, token: str | None = None, timeout: int = 120) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"content-type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ark_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI 生成接口请求失败：HTTP {exc.code} {body[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接 AI 生成接口：{exc}") from exc


def image_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"


def media_mime_type(path: Path, kind: str) -> str:
    suffix = path.suffix.lower()
    if kind == "video":
        if suffix == ".mov":
            return "video/quicktime"
        if suffix == ".webm":
            return "video/webm"
        if suffix == ".mkv":
            return "video/x-matroska"
        return "video/mp4"
    if suffix == ".wav":
        return "audio/wav"
    if suffix == ".m4a":
        return "audio/mp4"
    if suffix == ".aac":
        return "audio/aac"
    if suffix == ".flac":
        return "audio/flac"
    return "audio/mpeg"


def apimart_upload_image(path: Path, task_id: str | None = None) -> str:
    ensure_not_cancelled(task_id)
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"参考图不存在：{path}")
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise RuntimeError(f"参考图格式不支持：{path.name}")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise RuntimeError(f"参考图超过 20MB：{path.name}")
    boundary = f"----apimart-{uuid.uuid4().hex}"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {image_mime_type(path)}\r\n\r\n"
    ).encode("utf-8")
    body = header + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        APIMART_UPLOAD_IMAGE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {apimart_api_key()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180, context=ark_ssl_context()) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"参考图上传失败：HTTP {exc.code} {body_text[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法上传参考图到 AI 生成接口：{exc}") from exc
    url = result.get("url") if isinstance(result, dict) else ""
    if not url:
        raise RuntimeError(f"上传参考图未返回 URL：{json.dumps(result, ensure_ascii=False)[:800]}")
    return str(url)


def apimart_upload_media(path: Path, kind: str, task_id: str | None = None) -> str:
    ensure_not_cancelled(task_id)
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"参考素材不存在：{path}")
    if kind == "video":
        endpoint = APIMART_UPLOAD_VIDEO_URL
        allowed = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
        label = "参考视频"
    else:
        endpoint = APIMART_UPLOAD_AUDIO_URL
        allowed = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
        label = "参考声音"
    if path.suffix.lower() not in allowed:
        raise RuntimeError(f"{label}格式不支持：{path.name}")
    boundary = f"----apimart-{uuid.uuid4().hex}"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {media_mime_type(path, kind)}\r\n\r\n"
    ).encode("utf-8")
    body = header + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {apimart_api_key()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300, context=ark_ssl_context()) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{label}上传失败：HTTP {exc.code} {body_text[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法上传{label}到 AI 生成接口：{exc}") from exc
    url = result.get("url") if isinstance(result, dict) else ""
    if not url:
        raise RuntimeError(f"上传{label}未返回 URL：{json.dumps(result, ensure_ascii=False)[:800]}")
    return str(url)


def apimart_submit(url: str, payload: dict, task_id: str | None = None) -> str:
    ensure_not_cancelled(task_id)
    result = json_request("POST", url, payload, token=apimart_api_key(), timeout=120)
    if int(result.get("code", 0)) != 200:
        raise RuntimeError(f"AI 生成任务提交失败：{json.dumps(result, ensure_ascii=False)[:800]}")
    data = result.get("data")
    first = data[0] if isinstance(data, list) and data else {}
    remote_task_id = first.get("task_id") or first.get("id")
    if not remote_task_id:
        raise RuntimeError(f"AI 生成任务未返回任务 ID：{json.dumps(result, ensure_ascii=False)[:800]}")
    return str(remote_task_id)


def apimart_poll(remote_task_id: str, task_id: str | None = None, base_progress: int = 10, span: int = 70, timeout_seconds: int = 1800) -> dict:
    started = datetime.now().timestamp()
    while True:
        ensure_not_cancelled(task_id)
        elapsed = datetime.now().timestamp() - started
        if elapsed > timeout_seconds:
            raise RuntimeError("AI 生成任务等待超时，请稍后重试，或降低清晰度后再生成。")
        result = json_request("GET", f"{APIMART_TASK_URL}/{remote_task_id}?language=zh", token=apimart_api_key(), timeout=60)
        if int(result.get("code", 0)) != 200:
            raise RuntimeError(f"AI 生成任务查询失败：{json.dumps(result, ensure_ascii=False)[:800]}")
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        status = str(data.get("status") or "").lower()
        try:
            remote_progress = max(0, min(100, int(float(data.get("progress")))))
        except (TypeError, ValueError):
            remote_progress = min(95, int(elapsed / max(1, timeout_seconds) * 100))
        if task_id:
            task_update(task_id, base_progress + int(remote_progress / 100 * span), f"AI 生成中：{status or 'processing'} {remote_progress}%")
        if status == "completed":
            return data
        if status in {"failed", "cancelled", "canceled"}:
            message = data.get("error") or data.get("message") or data.get("fail_reason") or status
            raise RuntimeError(f"AI 生成任务失败：{message}")
        threading.Event().wait(3)


def result_urls(task_data: dict, kind: str) -> list[str]:
    result = task_data.get("result") if isinstance(task_data.get("result"), dict) else {}
    items = result.get(kind)
    urls: list[str] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, dict):
                value = item.get("url") or item.get("urls") or item.get("video_url") or item.get("image_url")
                if isinstance(value, list):
                    urls.extend(str(url) for url in value if url)
                elif value:
                    urls.append(str(value))
    elif isinstance(items, str):
        urls.append(items)
    return urls


def download_result_url(url: str, output: Path, task_id: str | None = None) -> Path:
    ensure_not_cancelled(task_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"user-agent": "AI-Slicer/1.0"})
    with urllib.request.urlopen(request, timeout=240, context=ark_ssl_context()) as resp:
        output.write_bytes(resp.read())
    return output


def generation_public_path(path: Path) -> str:
    return f"/generations/{path.relative_to(GENERATIONS).as_posix()}"


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
                return subprocess.CompletedProcess(cmd, process.returncode, safe_text(stdout), safe_text(stderr))
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


def safe_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def command_tail(result: subprocess.CompletedProcess[str], limit: int = 1200) -> str:
    text = safe_text(getattr(result, "stderr", "")) or safe_text(getattr(result, "stdout", ""))
    return text[-limit:] or "命令执行失败，但没有返回错误详情。"


def result_tail(result: subprocess.CompletedProcess[str], limit: int = 1500) -> str:
    text = safe_text(getattr(result, "stderr", "")) or safe_text(getattr(result, "stdout", ""))
    return text[-limit:] or "命令执行失败，但没有返回错误详情。"


def parse_duration(stderr: object) -> str:
    for line in safe_text(stderr).splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            return line.split("Duration:", 1)[1].split(",", 1)[0].strip()
    return "未知"


def parse_duration_seconds(stderr: object) -> float:
    duration = parse_duration(stderr)
    if duration == "未知":
        return 0.0
    try:
        hours, minutes, seconds = duration.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (TypeError, ValueError):
        return 0.0


def parse_media_info(stderr: object) -> dict:
    stderr_text = safe_text(stderr)
    info = {
        "duration": parse_duration(stderr_text),
        "video": "未检测到",
        "audio": "未检测到",
        "resolution": "未知",
        "ratio": "未知",
        "fps": "未知",
        "bitrate": "未知",
    }
    for line in stderr_text.splitlines():
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
    if result.returncode != 0 or not safe_text(result.stdout).strip():
        return []
    try:
        rows = json.loads(safe_text(result.stdout))
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
        raise RuntimeError(f"无法读取视频时长，请确认 ffmpeg 可用且视频文件能正常打开。{command_tail(probe, 500)}")

    fps = 2
    pattern = out_dir / "frame_%06d.jpg"
    if task_id:
        task_update(task_id, 15, "正在抽取分析帧")
    extract = run([
        ffmpeg_path(), "-hide_banner", "-y", "-i", str(video),
        "-vf", f"fps={fps},scale=96:-1", str(pattern)
    ], timeout=None, task_id=task_id)
    if extract.returncode != 0:
        raise RuntimeError(command_tail(extract, 1200))

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
    try:
        content_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"火山方舟接口返回结构异常：{json.dumps(data, ensure_ascii=False)[:800]}") from exc
    if not safe_text(content_text).strip():
        raise RuntimeError("火山方舟接口返回了空内容，请稍后重试或检查 API Key / 模型权限。")
    return safe_text(content_text)


def parse_ai_json(text: object) -> dict:
    decoder = json.JSONDecoder()
    text = safe_text(text)
    cleaned = text.strip()
    if not cleaned:
        raise RuntimeError("AI 返回内容为空，无法生成结果。")
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
    count = min(18, max(8, int(duration // 18) + 1))
    step = duration / (count + 1)
    half_window = min(7.5, step / 2)
    samples = []
    for index in range(1, count + 1):
        time = step * index
        samples.append({
            "id": index,
            "time": round(time, 1),
            "suggested_start": round(max(0.0, time - half_window), 1),
            "suggested_end": round(min(duration, time + half_window), 1),
        })
    return duration, samples


def storyboard_dialogue_timeline(dialogues: list[dict], limit: int = 120) -> list[dict]:
    timeline = []
    for item in dialogues[:limit]:
        try:
            start = float(item.get("time", 0))
            end = float(item.get("end", start + 1))
        except (TypeError, ValueError):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        timeline.append({
            "start": round(start, 1),
            "end": round(max(start, end), 1),
            "text": text[:120],
        })
    return timeline


def dialogue_for_range(dialogues: list[dict], start: float, end: float) -> str:
    texts = []
    for item in dialogues:
        try:
            text_start = float(item.get("time", 0))
            text_end = float(item.get("end", text_start + 1))
        except (TypeError, ValueError):
            continue
        if text_end < start or text_start > end:
            continue
        text = str(item.get("text") or "").strip()
        if text and text not in texts:
            texts.append(text)
        if len(" / ".join(texts)) >= 150:
            break
    return " / ".join(texts)[:160]


def storyboard_prompt_payload(duration: float, requirement: str = "", samples: list[dict] | None = None, dialogue_timeline: list[dict] | None = None, direct_video: bool = False) -> dict:
    task = "根据完整视频内容生成可执行的中文分镜脚本。请只返回严格 JSON，不要输出解释文字。" if direct_video else "根据视频代表帧、时间信息和字幕台词线索，生成可执行的中文分镜脚本。请只返回严格 JSON，不要输出解释文字。"
    writing_rule = (
        "每个镜头要相对独立，单个镜头时长根据实际内容决定，但不要超过15秒；时间段尽量连续且覆盖主要内容。"
        "描述要具体，避免空泛。广告素材要突出卖点、价格、优惠、动作和转化点；剧情素材要突出人物、冲突、转折和钩子。"
    )
    if direct_video:
        writing_rule += "请尽量结合视频画面、字幕和可识别语音判断真实台词；无法确认的台词返回空字符串，不要凭空改写或编造。"
    else:
        writing_rule += "dialogue 字段只能引用字幕台词线索中对应时间段能确认的内容，无法确认就返回空字符串，不要凭空改写或编造台词。"
    payload = {
        "task": task,
        "video_duration": round(duration, 1),
        "user_requirement": requirement or "用户没有额外要求，请按视频内容生成适合短视频剪辑和复刻拍摄的分镜脚本。",
        "writing_rule": writing_rule,
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
    }
    if samples:
        payload["samples"] = samples
    if dialogue_timeline:
        payload["dialogue_timeline"] = dialogue_timeline
    return payload


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
        start = max(0.0, min(max(0.0, duration - 0.3), start))
        end = max(start + 0.3, min(duration, start + 15.0, end))
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


def analyze_ai_storyboard_by_video_url(video: Path, requirement: str = "", task_id: str | None = None) -> dict:
    duration = media_duration_seconds(video)
    if duration <= 0:
        raise RuntimeError("无法读取原片时长。")
    if task_id:
        task_update(task_id, 8, "正在上传完整视频给豆包分析")
    storage = store_generated_asset(video, "video", task_id=task_id)
    video_url = str(storage.get("url") or "")
    if not video_url or storage.get("error"):
        raise RuntimeError(f"完整视频上传失败：{storage.get('error') or '未返回公网 URL'}")
    content: list[dict] = [
        {"type": "text", "text": json.dumps(storyboard_prompt_payload(duration, requirement, direct_video=True), ensure_ascii=False)},
        {"type": "video_url", "video_url": {"url": video_url}},
    ]
    if task_id:
        task_update(task_id, 32, "正在调用豆包直接解析完整视频")
    ai = parse_ai_json(call_ark_chat(content, task_id=task_id))
    shots = normalize_storyboard(ai.get("shots") or ai.get("storyboard") or [], duration)
    if not shots:
        raise RuntimeError("豆包未基于完整视频返回可用分镜。")
    return {
        "shots": shots,
        "summary": (ai.get("summary") or f"已根据完整视频生成 {len(shots)} 个分镜。") + "（已尝试直接上传完整视频给豆包分析）",
        "duration": seconds_to_clock(duration),
        "videoStorageUrl": video_url,
        "videoStoragePath": storage.get("objectKey", ""),
    }


def analyze_ai_storyboard(video: Path, requirement: str = "", task_id: str | None = None) -> dict:
    try:
        return analyze_ai_storyboard_by_video_url(video, requirement=requirement, task_id=task_id)
    except Exception as direct_exc:
        fallback_reason = compact_log_text(direct_exc, 260)
        if task_id:
            task_update(task_id, 6, "完整视频直传不可用，改用抽帧分析")
    duration, samples = storyboard_sample_times(video)
    storyboard_dir = WORK / f"storyboard_{uuid.uuid4().hex[:10]}"
    storyboard_dir.mkdir(parents=True, exist_ok=True)
    if task_id:
        task_update(task_id, 10, "正在识别字幕台词")
    dialogues = extract_dialogue(video, storyboard_dir, task_id=task_id)
    dialogue_timeline = storyboard_dialogue_timeline(dialogues)
    content: list[dict] = [{
        "type": "text",
        "text": json.dumps(storyboard_prompt_payload(duration, requirement, samples=samples, dialogue_timeline=dialogue_timeline), ensure_ascii=False),
    }]
    for index, sample in enumerate(samples, start=1):
        ensure_not_cancelled(task_id)
        if task_id:
            task_update(task_id, 52 + int(index / max(1, len(samples)) * 25), f"正在抽取分镜参考帧 {index}/{len(samples)}")
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
    if dialogue_timeline:
        for shot in shots:
            text = dialogue_for_range(dialogue_timeline, float(shot.get("start", 0)), float(shot.get("end", 0)))
            if text:
                shot["dialogue"] = text
    return {
        "shots": shots,
        "summary": (ai.get("summary") or f"已根据视频内容生成 {len(shots)} 个分镜。") + f"（完整视频直传失败，已回退抽帧分析：{fallback_reason}）",
        "duration": seconds_to_clock(duration),
    }


def storyboard_image_prompt(shot: dict, index: int, reference_notes: str = "") -> str:
    parts = [
        "请生成一张适合短视频广告分镜的高清画面，真实商业摄影质感，主体清晰，构图干净，可直接作为视频首帧。",
        "必须保持核心人物一致：同一张脸、同一发型、同一服装轮廓、同一年龄气质、同一肤色和体型；不同镜头只改变姿态、表情、景别和机位。",
        "如果提供了参考图，请优先保持参考图中的人物脸型、五官比例、发型、服装、商品外观、场景空间和整体风格一致；不要随意更换核心人物或场景设定。",
        f"镜头{shot.get('shot') or index}",
        f"画面：{shot.get('scene') or ''}",
        f"景别：{shot.get('shotType') or ''}",
        f"运镜参考：{shot.get('camera') or ''}",
        f"动作/卖点：{shot.get('action') or ''}",
    ]
    if reference_notes:
        parts.append(f"参考图说明：{reference_notes}")
    if shot.get("caption"):
        parts.append(f"可视化重点：{shot.get('caption')}")
    return "\n".join(str(part).strip() for part in parts if str(part).strip())[:2400]


def storyboard_video_prompt(shot: dict, index: int) -> str:
    parts = [
        "根据分镜生成自然流畅的短视频片段，真实广告片质感，动作连贯，镜头稳定，不要出现变形文字和错误字幕。",
        f"镜头{shot.get('shot') or index}",
        f"画面：{shot.get('scene') or ''}",
        f"动作：{shot.get('action') or ''}",
        f"运镜：{shot.get('camera') or '轻微推进'}",
        f"剪辑节奏：{shot.get('edit') or '自然衔接'}",
    ]
    if shot.get("dialogue"):
        parts.append(f"剧情/台词参考：{shot.get('dialogue')}")
    if shot.get("caption"):
        parts.append(f"重点信息参考：{shot.get('caption')}")
    return "\n".join(str(part).strip() for part in parts if str(part).strip())[:1800]


def normalize_generation_shots(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    shots = []
    for index, item in enumerate(raw[:24], start=1):
        if isinstance(item, dict):
            shot = dict(item)
            shot.setdefault("shot", str(index))
            shots.append(shot)
    return shots


def normalize_reference_images(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    refs = []
    for item in raw[:16]:
        if isinstance(item, str):
            path = item.strip()
            title = ""
            prompt = ""
            source = "upload"
            src = ""
        elif isinstance(item, dict):
            path = str(item.get("path") or "").strip()
            title = str(item.get("title") or "").strip()[:80]
            prompt = str(item.get("prompt") or "").strip()[:1600]
            source = str(item.get("source") or "upload").strip()[:20]
            src = str(item.get("src") or "").strip()
            url = str(item.get("url") or "").strip()
            storage_url = str(item.get("storageUrl") or item.get("imageStorageUrl") or "").strip()
            storage_path = str(item.get("storagePath") or item.get("imageStoragePath") or "").strip()
        else:
            path = ""
            title = ""
            prompt = ""
            source = "upload"
            src = ""
            url = ""
            storage_url = ""
            storage_path = ""
        if not path:
            continue
        refs.append({
            "path": path,
            "title": title,
            "prompt": prompt,
            "source": source,
            "src": src,
            "url": url,
            "storageUrl": storage_url,
            "storagePath": storage_path,
        })
    return refs


def reference_notes_text(refs: list[dict], description: str = "") -> str:
    parts = []
    if description:
        parts.append(f"用户说明：{description.strip()[:1000]}")
    for index, ref in enumerate(refs, start=1):
        note = str(ref.get("title") or "").strip() or Path(str(ref.get("path") or "")).stem
        prompt = str(ref.get("prompt") or "").strip()
        if prompt:
            note = f"{note}，提示词：{prompt[:260]}"
        parts.append(f"第{index}张参考图：{note}")
    return "；".join(parts)[:1200]


def upload_reference_asset_url(ref: dict, kind: str, task_id: str | None = None) -> str:
    storage_url = str(ref.get("storageUrl") or ref.get("imageStorageUrl") or ref.get("videoStorageUrl") or "").strip()
    if storage_url:
        return storage_url
    path_text = str(ref.get("path") or "").strip()
    if path_text:
        storage = store_generated_asset(Path(path_text).expanduser(), kind, task_id=task_id)
        if storage.get("url") and not storage.get("error"):
            ref["storageUrl"] = storage.get("url", "")
            ref["storagePath"] = storage.get("objectKey", "")
            ref["storageError"] = ""
            ref["url"] = storage.get("url", "")
            return str(storage.get("url") or "")
        raise RuntimeError(f"参考素材上传到对象存储失败：{storage.get('error') or '未返回公网 URL'}")
    url = str(ref.get("url") or "").strip()
    if url:
        return url
    raise RuntimeError("参考素材缺少本地路径或公网 URL。")


def upload_reference_images(refs: list[dict], task_id: str | None = None) -> list[str]:
    urls = []
    for index, ref in enumerate(refs, start=1):
        ensure_not_cancelled(task_id)
        if task_id:
            task_update(task_id, 3 + int(index / max(1, len(refs)) * 14), f"正在上传参考图到对象存储 {index}/{len(refs)}")
        url = upload_reference_asset_url(ref, "image", task_id=task_id)
        ref["url"] = url
        urls.append(url)
    return urls


def batch_storyboard_image_prompt(batch: list[tuple[int, dict]], reference_notes: str = "") -> str:
    lines = [
        f"请一次生成 {len(batch)} 张短视频分镜图，按下面镜头顺序一一对应输出。每张图都是独立分镜，但人物、商品、场景和整体视觉风格必须保持一致。",
        "每张图只能表现对应镜头的画面内容、动作和场景，不要把其他镜头的动作、道具、字幕或场景混入当前镜头。",
        "先在内部建立统一角色设定：同一人物在所有图中必须保持同一张脸、五官比例、发型、服装轮廓、年龄气质、肤色和体型。不要把同一角色画成不同人。",
        "如果参考图说明中包含人物、商品或场景，请把它们作为全片视觉锚点；若包含上一批生成图，请严格延续上一批中的人物形象和画面风格。",
        "真实商业摄影质感，主体清晰，构图干净，可直接作为视频首帧。不要在画面里生成难以阅读的文字。",
    ]
    if reference_notes:
        lines.append(f"参考图说明：{reference_notes}")
    for index, shot in batch:
        lines.extend([
            f"图{index} / 镜头{shot.get('shot') or index}",
            f"画面：{shot.get('scene') or ''}",
            f"景别：{shot.get('shotType') or ''}",
            f"运镜参考：{shot.get('camera') or ''}",
            f"动作/卖点：{shot.get('action') or ''}",
        ])
        if shot.get("caption"):
            lines.append(f"可视化重点：{shot.get('caption')}")
    return "\n".join(str(line).strip() for line in lines if str(line).strip())[:4000]


def storyboard_reference_prompt_schema(shots: list[dict]) -> str:
    lines = [
        "请分析下面的短视频分镜脚本，提取后续生成分镜图最需要固定一致的视觉参考元素。",
        "优先提取：主要人物、核心商品、关键场景、品牌/画面风格。最多返回6个参考图提示词。",
        "每个提示词用于 GPT-Image-2 生成一张参考图，必须具体描述外貌、服装、产品形态、场景细节、材质、色调和商业摄影风格。",
        "只返回严格 JSON，不要输出解释文字。",
        json.dumps({
            "output_schema": {
                "references": [{
                    "title": "参考图名称，如 女主形象/产品外观/客厅场景",
                    "type": "character/product/scene/style",
                    "prompt": "中文生图提示词，具体可执行，不要出现不可控的长文字和字幕",
                }],
            },
            "shots": [{
                "shot": shot.get("shot"),
                "scene": shot.get("scene"),
                "shotType": shot.get("shotType"),
                "camera": shot.get("camera"),
                "action": shot.get("action"),
                "dialogue": shot.get("dialogue"),
                "caption": shot.get("caption"),
            } for shot in shots[:24]],
        }, ensure_ascii=False),
    ]
    return "\n".join(lines)[:6000]


def normalize_reference_prompts(raw: object) -> list[dict]:
    items = raw.get("references") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    refs = []
    for index, item in enumerate(items[:6], start=1):
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            continue
        title = str(item.get("title") or item.get("name") or f"AI参考图 {index}").strip()[:80]
        ref_type = str(item.get("type") or "visual").strip()[:30]
        refs.append({
            "title": title,
            "type": ref_type,
            "prompt": prompt[:1600],
        })
    return refs


def fallback_reference_prompts(shots: list[dict]) -> list[dict]:
    text = "；".join(
        str(value).strip()
        for shot in shots[:8]
        for value in [shot.get("scene"), shot.get("action"), shot.get("caption")]
        if str(value or "").strip()
    )[:1200]
    return [{
        "title": "整体视觉风格",
        "type": "style",
        "prompt": f"根据以下分镜内容生成短视频广告的统一视觉参考图，真实商业摄影质感，主体清晰，风格一致，适合作为后续分镜图的风格锚点：{text}",
    }]


def generate_reference_prompt_items(shots: list[dict], task_id: str | None = None) -> list[dict]:
    if task_id:
        task_update(task_id, 8, "正在分析分镜脚本并提取参考元素")
    try:
        ai = parse_ai_json(call_ark_chat([{"type": "text", "text": storyboard_reference_prompt_schema(shots)}], task_id=task_id))
        refs = normalize_reference_prompts(ai)
    except Exception:
        refs = []
    return refs or fallback_reference_prompts(shots)


def generate_reference_image_from_prompt(prompt: str, title: str = "AI参考图", size: str = "9:16", resolution: str = "1k", quality: str = "medium", out_dir: Path | None = None, index: int = 1, task_id: str | None = None) -> dict:
    size = size if size in {"auto", "1:1", "3:2", "2:3", "4:3", "3:4", "4:5", "16:9", "9:16", "21:9"} or re.match(r"^\d+x\d+$", size or "") else "9:16"
    resolution = resolution if resolution in {"1k", "2k", "4k"} else "1k"
    quality = normalize_image_quality(quality)
    out_dir = out_dir or (GENERATIONS / f"refs_{uuid.uuid4().hex[:10]}")
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": "gpt-image-2-official",
        "prompt": prompt[:1600],
        "size": size,
        "resolution": resolution,
        "quality": quality,
        "n": 1,
    }
    remote_task_id = apimart_submit(APIMART_IMAGE_URL, payload, task_id=task_id)
    task_data = apimart_poll(remote_task_id, task_id=task_id, base_progress=20, span=65, timeout_seconds=900)
    urls = result_urls(task_data, "images")
    if not urls:
        raise RuntimeError("GPT-Image-2 没有返回参考图。")
    output = download_result_url(urls[0], out_dir / f"reference_{index:02d}.png", task_id=task_id)
    storage = store_generated_asset(output, "image", task_id=task_id)
    notify_generation_asset(
        "AI生成参考图完成",
        prompt,
        {
            "标题": title[:80],
            "模型": payload["model"],
            "比例": size,
            "清晰度": resolution,
            "质量": quality,
        },
        storage=storage,
        source_url=urls[0],
        local_path=str(output),
    )
    return {
        "path": str(output),
        "src": generation_public_path(output),
        "url": urls[0],
        "storageUrl": storage.get("url", ""),
        "storagePath": storage.get("objectKey", ""),
        "storageError": storage.get("error", ""),
        "title": title[:80],
        "prompt": prompt[:1600],
        "source": "ai",
    }


def generate_storyboard_reference_images(shots_raw: object, size: str = "9:16", resolution: str = "1k", quality: str = "medium", existing_count: int = 0, task_id: str | None = None) -> dict:
    shots = normalize_generation_shots(shots_raw)
    if not shots:
        raise RuntimeError("请先生成分镜脚本，再生成 AI 参考图。")
    max_count = max(0, min(6, 16 - int(existing_count or 0)))
    if max_count <= 0:
        raise RuntimeError("参考图最多 16 张，请先删除一些参考图。")
    prompts = generate_reference_prompt_items(shots, task_id=task_id)[:max_count]
    out_dir = GENERATIONS / f"refs_{uuid.uuid4().hex[:10]}"
    refs = []
    for index, item in enumerate(prompts, start=1):
        ensure_not_cancelled(task_id)
        if task_id:
            task_update(task_id, 18 + int((index - 1) / max(1, len(prompts)) * 74), f"正在生成 AI 参考图 {index}/{len(prompts)}")
        refs.append(generate_reference_image_from_prompt(
            item["prompt"],
            title=item["title"],
            size=size,
            resolution=resolution,
            quality=quality,
            out_dir=out_dir,
            index=index,
            task_id=task_id,
        ))
    return {
        "references": refs,
        "count": len(refs),
        "outputDir": str(out_dir),
        "summary": f"已生成 {len(refs)} 张 AI 参考图，可调整提示词后重新生成。",
    }


def normalize_image_quality(value: object) -> str:
    text = str(value or "medium").strip()
    return text if text in {"auto", "low", "medium", "high"} else "medium"


def generate_storyboard_images(shots_raw: object, size: str = "9:16", resolution: str = "1k", quality: str = "medium", references_raw: object = None, reference_description: str = "", task_id: str | None = None) -> dict:
    shots = normalize_generation_shots(shots_raw)
    if not shots:
        raise RuntimeError("请先生成分镜脚本，再生成分镜图。")
    size = size if size in {"auto", "1:1", "3:2", "2:3", "4:3", "3:4", "4:5", "16:9", "9:16", "21:9"} or re.match(r"^\d+x\d+$", size or "") else "9:16"
    resolution = resolution if resolution in {"1k", "2k", "4k"} else "1k"
    quality = normalize_image_quality(quality)
    references = normalize_reference_images(references_raw)
    reference_urls = upload_reference_images(references, task_id=task_id) if references else []
    reference_notes = reference_notes_text(references, reference_description)
    job = uuid.uuid4().hex[:10]
    out_dir = GENERATIONS / job / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    batches = [list(enumerate(shots[start:start + 4], start=start + 1)) for start in range(0, len(shots), 4)]
    token_span = max(1, len(batches))
    loop_start = 20 if references else 3
    loop_span = 77 if references else 94
    anchor_url = ""
    for batch_index, batch in enumerate(batches, start=1):
        ensure_not_cancelled(task_id)
        if task_id:
            task_update(task_id, loop_start + int((batch_index - 1) / token_span * loop_span), f"正在提交分镜图批次 {batch_index}/{len(batches)}")
        batch_reference_urls = list(reference_urls)
        batch_reference_notes = reference_notes
        if anchor_url and anchor_url not in batch_reference_urls and len(batch_reference_urls) < 16:
            batch_reference_urls.append(anchor_url)
            batch_reference_notes = (batch_reference_notes + "；" if batch_reference_notes else "") + "上一批生成的第1张图是全片人物与风格锚点，后续分镜必须延续同一人物形象。"
        batch_prompt = batch_storyboard_image_prompt(batch, reference_notes=batch_reference_notes)
        payload = {
            "model": "gpt-image-2-official",
            "prompt": batch_prompt,
            "size": size,
            "resolution": resolution,
            "quality": quality,
            "n": len(batch),
        }
        if batch_reference_urls:
            payload["image_urls"] = batch_reference_urls
        remote_task_id = apimart_submit(APIMART_IMAGE_URL, payload, task_id=task_id)
        task_data = apimart_poll(remote_task_id, task_id=task_id, base_progress=loop_start + int((batch_index - 1) / token_span * loop_span), span=max(3, int(60 / token_span)), timeout_seconds=900)
        urls = result_urls(task_data, "images")
        if len(urls) < len(batch):
            raise RuntimeError(f"第 {batch_index} 批分镜图只返回了 {len(urls)} 张，少于请求的 {len(batch)} 张。")
        for (index, shot), url in zip(batch, urls):
            output = download_result_url(url, out_dir / f"shot_{index:02d}.png", task_id=task_id)
            storage = store_generated_asset(output, "image", task_id=task_id)
            shot.update({
                "imageUrl": url,
                "imageStorageUrl": storage.get("url", ""),
                "imageStoragePath": storage.get("objectKey", ""),
                "imageStorageError": storage.get("error", ""),
                "imageTaskId": remote_task_id,
                "imagePath": str(output),
                "imageSrc": generation_public_path(output),
                "imagePrompt": storyboard_image_prompt(shot, index, reference_notes=batch_reference_notes),
            })
            notify_generation_asset(
                "生成分镜图完成",
                payload["prompt"],
                {
                    "镜头": shot.get("shot") or index,
                    "批次": f"{batch_index}/{len(batches)}",
                    "模型": payload["model"],
                    "比例": size,
                    "清晰度": resolution,
                    "质量": quality,
                    "参考图数量": len(batch_reference_urls),
                },
                storage=storage,
                source_url=url,
                local_path=str(output),
            )
            if not anchor_url:
                anchor_url = storage.get("url") or url
    return {
        "shots": shots,
        "count": len(shots),
        "outputDir": str(out_dir),
        "references": references,
        "summary": f"已生成 {len(shots)} 张分镜图。" + (f" 已使用 {len(references)} 张参考图保持一致性。" if references else ""),
    }


def normalize_seedance_duration(value: object, fallback: int = 5) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = fallback
    return max(4, min(15, number))


def storyboard_shot_video_duration(shot: dict, fallback: int = 5) -> int:
    if normalize_bool(shot.get("videoDurationManual"), False):
        return normalize_seedance_duration(shot.get("videoDuration"), fallback)
    try:
        start = float(shot.get("start", 0))
        end = float(shot.get("end", 0))
        if end > start:
            return normalize_seedance_duration(end - start, fallback)
    except (AttributeError, TypeError, ValueError):
        pass
    return normalize_seedance_duration(shot.get("videoDuration"), fallback)


def normalize_seedance_resolution(value: object, fallback: str = "720p") -> str:
    text = str(value or fallback).strip()
    return text if text in {"480p", "720p", "1080p"} else "720p"


def normalize_seedance_size(value: object, fallback: str = "adaptive") -> str:
    text = str(value or fallback).strip()
    return text if text in {"adaptive", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9"} else "adaptive"


def normalize_bool(value: object, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def normalize_story_video_references(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    refs = []
    for item in raw[:15]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "").strip()
        if kind not in {"image", "video", "audio"}:
            continue
        path = str(item.get("path") or "").strip()
        url = str(item.get("url") or "").strip()
        storage_url = str(item.get("storageUrl") or item.get("imageStorageUrl") or item.get("videoStorageUrl") or "").strip()
        storage_path = str(item.get("storagePath") or item.get("imageStoragePath") or item.get("videoStoragePath") or "").strip()
        src = str(item.get("src") or "").strip()
        title = str(item.get("title") or "").strip()[:80]
        if not path and not url and not storage_url:
            continue
        refs.append({"type": kind, "path": path, "url": url, "storageUrl": storage_url, "storagePath": storage_path, "src": src, "title": title})
    return refs


def resolve_story_video_reference_urls(refs: list[dict], task_id: str | None = None) -> tuple[list[str], list[str], list[str], list[dict]]:
    image_urls: list[str] = []
    video_urls: list[str] = []
    audio_urls: list[str] = []
    resolved: list[dict] = []
    for index, ref in enumerate(refs, start=1):
        ensure_not_cancelled(task_id)
        kind = ref.get("type")
        url = str(ref.get("storageUrl") or ref.get("url") or "").strip()
        if not str(ref.get("storageUrl") or "").strip():
            if kind == "image":
                if task_id:
                    task_update(task_id, 2, f"正在上传视频参考图到对象存储 {index}")
                url = upload_reference_asset_url(ref, "image", task_id=task_id)
            elif kind == "video":
                if task_id:
                    task_update(task_id, 2, f"正在上传参考视频到对象存储 {index}")
                url = upload_reference_asset_url(ref, "video", task_id=task_id)
            elif kind == "audio":
                if task_id:
                    task_update(task_id, 2, f"正在上传参考声音到对象存储 {index}")
                url = upload_reference_asset_url(ref, "audio", task_id=task_id)
        next_ref = dict(ref)
        next_ref["url"] = url
        resolved.append(next_ref)
        if kind == "image" and len(image_urls) < 9:
            image_urls.append(url)
        elif kind == "video" and len(video_urls) < 3:
            video_urls.append(url)
        elif kind == "audio" and len(audio_urls) < 3:
            audio_urls.append(url)
    return image_urls, video_urls, audio_urls, resolved


def generate_storyboard_videos(shots_raw: object, duration: int = 5, resolution: str = "720p", size: str = "adaptive", generate_audio: bool = True, references_raw: object = None, task_id: str | None = None) -> dict:
    shots = normalize_generation_shots(shots_raw)
    if not shots:
        raise RuntimeError("请先生成分镜脚本，再生成视频片段。")
    duration = normalize_seedance_duration(duration)
    resolution = normalize_seedance_resolution(resolution)
    size = normalize_seedance_size(size)
    generate_audio = normalize_bool(generate_audio, True)
    video_references = normalize_story_video_references(references_raw)
    ref_image_urls, ref_video_urls, ref_audio_urls, resolved_references = resolve_story_video_reference_urls(video_references, task_id=task_id) if video_references else ([], [], [], [])
    job = uuid.uuid4().hex[:10]
    out_dir = GENERATIONS / job / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    token_span = max(1, len(shots))
    for index, shot in enumerate(shots, start=1):
        ensure_not_cancelled(task_id)
        if task_id:
            task_update(task_id, 3 + int((index - 1) / token_span * 94), f"正在提交视频片段 {index}/{len(shots)}")
        shot_duration = storyboard_shot_video_duration(shot, duration)
        shot_resolution = normalize_seedance_resolution(shot.get("videoResolution"), resolution)
        shot_size = normalize_seedance_size(shot.get("videoSize"), size)
        shot_audio = normalize_bool(shot.get("videoAudio"), generate_audio)
        payload = {
            "model": "doubao-seedance-2.0",
            "prompt": storyboard_video_prompt(shot, index),
            "resolution": shot_resolution,
            "duration": shot_duration,
            "generate_audio": shot_audio,
        }
        image_urls = []
        image_url = str(shot.get("imageStorageUrl") or shot.get("imageUrl") or "").strip()
        if image_url:
            image_urls.append(image_url)
        for url in ref_image_urls:
            if url not in image_urls and len(image_urls) < 9:
                image_urls.append(url)
        if image_urls:
            payload["image_urls"] = image_urls
            payload["size"] = shot_size
        else:
            payload["size"] = shot_size if shot_size != "adaptive" else "9:16"
        if ref_video_urls:
            payload["video_urls"] = ref_video_urls[:3]
        if ref_audio_urls:
            if not image_urls and not ref_video_urls:
                raise RuntimeError("参考声音需要同时提供参考图或参考视频。")
            payload["audio_urls"] = ref_audio_urls[:3]
        remote_task_id = apimart_submit(APIMART_VIDEO_URL, payload, task_id=task_id)
        task_data = apimart_poll(remote_task_id, task_id=task_id, base_progress=5 + int((index - 1) / token_span * 88), span=max(3, int(70 / token_span)), timeout_seconds=1800)
        urls = result_urls(task_data, "videos")
        if not urls:
            raise RuntimeError(f"第 {index} 个视频片段没有返回视频 URL。")
        output = download_result_url(urls[0], out_dir / f"shot_{index:02d}.mp4", task_id=task_id)
        storage = store_generated_asset(output, "video", task_id=task_id)
        shot.update({
            "videoUrl": urls[0],
            "videoStorageUrl": storage.get("url", ""),
            "videoStoragePath": storage.get("objectKey", ""),
            "videoStorageError": storage.get("error", ""),
            "videoTaskId": remote_task_id,
            "videoPath": str(output),
            "videoSrc": generation_public_path(output),
            "videoPrompt": payload["prompt"],
            "videoDuration": shot_duration,
            "videoResolution": shot_resolution,
            "videoSize": shot_size,
            "videoAudio": shot_audio,
            "videoReferences": resolved_references,
        })
        notify_generation_asset(
            "生成分镜视频完成",
            payload["prompt"],
            {
                "镜头": shot.get("shot") or index,
                "模型": payload["model"],
                "时长": f"{shot_duration}秒",
                "清晰度": shot_resolution,
                "比例": shot_size,
                "声音": "是" if shot_audio else "否",
                "参考图数量": len(image_urls),
                "参考视频数量": len(ref_video_urls),
                "参考声音数量": len(ref_audio_urls),
            },
            storage=storage,
            source_url=urls[0],
            local_path=str(output),
        )
    return {
        "shots": shots,
        "count": len(shots),
        "outputDir": str(out_dir),
        "summary": f"已生成 {len(shots)} 个视频片段。",
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
        raise RuntimeError(f"无法读取视频时长，请确认 ffmpeg 可用且视频文件能正常打开。{command_tail(probe, 500)}")

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
            raise RuntimeError(command_tail(result, 1200))
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
            raise RuntimeError(safe_text(result.stderr).strip() or "已取消选择。")
        return safe_text(result.stdout).strip()
    return choose_with_tkinter(kind="file")


def choose_binary() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择 ffmpeg 可执行文件")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(safe_text(result.stderr).strip() or "已取消选择。")
        return safe_text(result.stdout).strip()
    return choose_with_tkinter(kind="binary")


def choose_logo() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择贴图图片" of type {"public.image", "png", "jpg", "jpeg", "webp", "bmp", "gif", "heic", "heif"})'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(safe_text(result.stderr).strip() or "已取消选择。")
        return safe_text(result.stdout).strip()
    return choose_with_tkinter(kind="logo")


def choose_reference_image() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择分镜参考图" of type {"public.image", "png", "jpg", "jpeg", "webp", "bmp", "gif", "heic", "heif"})'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(safe_text(result.stderr).strip() or "已取消选择。")
        return safe_text(result.stdout).strip()
    return choose_with_tkinter(kind="logo")


def choose_reference_video() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择视频参考素材" of type {"public.movie", "mp4", "mov", "m4v", "webm", "mkv"})'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(safe_text(result.stderr).strip() or "已取消选择。")
        return safe_text(result.stdout).strip()
    return choose_with_tkinter(kind="file")


def choose_reference_audio() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择声音参考素材" of type {"public.audio", "mp3", "wav", "m4a", "aac", "flac"})'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(safe_text(result.stderr).strip() or "已取消选择。")
        return safe_text(result.stdout).strip()
    return choose_with_tkinter(kind="bgm")


def choose_bgm() -> str:
    if is_macos():
        script = 'POSIX path of (choose file with prompt "选择 BGM 音频")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(safe_text(result.stderr).strip() or "已取消选择。")
        return safe_text(result.stdout).strip()
    return choose_with_tkinter(kind="bgm")


def choose_folder() -> str:
    if is_macos():
        script = 'POSIX path of (choose folder with prompt "选择导出视频保存目录")'
        result = run(["osascript", "-e", script], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(safe_text(result.stderr).strip() or "已取消选择。")
        return safe_text(result.stdout).strip()
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
            raise RuntimeError(safe_text(result.stderr).strip() or "已取消选择。")
        return safe_text(result.stdout).strip()
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


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if is_macos():
        subprocess.Popen(["open", str(path)])
    elif is_windows():
        subprocess.Popen(["explorer", str(path)])
    else:
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(path)])


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
            raise RuntimeError(result_tail(result, 1500))
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
        errors.append(result_tail(result, 1500))

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
    return "Audio:" in safe_text(result.stderr)


def media_duration_seconds(video: Path) -> float:
    result = run([ffmpeg_path(), "-hide_banner", "-i", str(video)], timeout=60)
    return parse_duration_seconds(result.stderr)


def media_pixel_size(video: Path) -> tuple[int, int]:
    result = run([ffmpeg_path(), "-hide_banner", "-i", str(video)], timeout=60)
    info = parse_media_info(result.stderr)
    match = re.search(r"(\d+)x(\d+)", str(info.get("resolution") or ""))
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1080, 1920


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
        raise RuntimeError(result_tail(result, 1600))


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


def generated_storyboard_videos(shots_raw: object) -> list[tuple[int, Path]]:
    shots = normalize_generation_shots(shots_raw)
    videos: list[tuple[int, Path]] = []
    for index, shot in enumerate(shots, start=1):
        path = Path(str(shot.get("videoPath") or "")).expanduser()
        if path.exists() and path.is_file():
            videos.append((index, path))
    if not videos:
        raise RuntimeError("还没有可导出的分镜视频，请先在镜头里生成视频片段。")
    return videos


def export_storyboard_video_files(video: Path, output_dir: Path, shots_raw: object) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = []
    for index, source in generated_storyboard_videos(shots_raw):
        output = output_name_for(video, f"story_{index}", output_dir)
        shutil.copy2(source, output)
        exported.append({
            "path": str(output),
            "source": str(source),
            "shot": index,
        })
    return exported


def merge_storyboard_video_files(video: Path, output_dir: Path, shots_raw: object) -> Path:
    videos = generated_storyboard_videos(shots_raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_name_for(video, "story_final", output_dir)
    target_width, target_height = media_pixel_size(videos[0][1])
    target_width = max(2, target_width // 2 * 2)
    target_height = max(2, target_height // 2 * 2)

    command = [ffmpeg_path(), "-hide_banner", "-y"]
    for _, source in videos:
        command.extend(["-i", str(source)])

    audio_inputs: list[tuple[int, str]] = []
    next_input = len(videos)
    for index, (_, source) in enumerate(videos):
        if has_audio_stream(source):
            audio_inputs.append((index, f"[{index}:a:0]asetpts=PTS-STARTPTS,aresample=48000[a{index}]"))
            continue
        duration = max(0.1, media_duration_seconds(source))
        command.extend(["-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"])
        audio_inputs.append((index, f"[{next_input}:a]asetpts=PTS-STARTPTS[a{index}]"))
        next_input += 1

    filters = []
    concat_parts = []
    for index in range(len(videos)):
        filters.append(
            f"[{index}:v:0]setpts=PTS-STARTPTS,"
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{index}]"
        )
        concat_parts.append(f"[v{index}][a{index}]")
    filters.extend(filter_text for _, filter_text in audio_inputs)
    filters.append(f"{''.join(concat_parts)}concat=n={len(videos)}:v=1:a=1[v][a]")

    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(output),
    ])
    result = run(command, timeout=None)
    if result.returncode != 0:
        raise RuntimeError(result_tail(result, 1600))
    return output


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
        if path in {"/", "/auth/callback"}:
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
        if path.startswith("/generations/"):
            file_path = GENERATIONS / path.removeprefix("/generations/")
            content_type = "video/mp4" if file_path.suffix.lower() == ".mp4" else "image/png"
            self.send_static(file_path, content_type)
            return
        if path == "/local-image":
            query = parse_qs(parsed.query)
            image_path = Path(query.get("path", [""])[0]).expanduser()
            content_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
                ".bmp": "image/bmp",
                ".heic": "image/heic",
                ".heif": "image/heif",
            }
            content_type = content_types.get(image_path.suffix.lower())
            if not content_type:
                response(self, 400, {"error": "不支持预览该图片格式。"})
                return
            self.send_static(image_path, content_type)
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
        if path == "/api/auth/status":
            response(self, 200, auth_state())
            return
        if path == "/api/auth/qr":
            response(self, 200, {
                "url": WECOM_QR_CONNECT_URL,
                "appid": WECOM_APPID,
                "agentid": WECOM_AGENTID,
                "redirectUri": WECOM_REDIRECT_URI,
                "state": WECOM_STATE,
            })
            return
        if path == "/api/history":
            response(self, 200, {"items": load_history()[:30]})
            return
        response(self, 404, {"error": "Not found"})

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)

            if self.path == "/api/auth/login":
                payload = read_json(self)
                state = login_with_wecom_code(payload.get("code") or payload.get("url"))
                response(self, 200, state)
                return

            if self.path == "/api/auth/logout":
                with AUTH_LOCK:
                    WECOM_SESSION.clear()
                response(self, 200, auth_state())
                return

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

            if self.path == "/api/pick-reference-image":
                picked = choose_reference_image()
                response(self, 200, {"path": picked, "src": f"/local-image?path={quote(picked)}"})
                return

            if self.path == "/api/pick-reference-video":
                response(self, 200, {"path": choose_reference_video()})
                return

            if self.path == "/api/pick-reference-audio":
                response(self, 200, {"path": choose_reference_audio()})
                return

            if self.path == "/api/pick-bgm":
                response(self, 200, {"path": choose_bgm()})
                return

            if self.path == "/api/open-downloads":
                open_folder(DOWNLOADS)
                response(self, 200, {"path": str(DOWNLOADS)})
                return

            if self.path == "/api/config":
                payload = read_json(self)
                config = load_config()
                if "apimartImageSize" in payload:
                    config["apimartImageSize"] = str(payload.get("apimartImageSize", "9:16")).strip() or "9:16"
                if "apimartImageResolution" in payload:
                    config["apimartImageResolution"] = str(payload.get("apimartImageResolution", "1k")).strip() or "1k"
                if "seedanceDuration" in payload:
                    try:
                        config["seedanceDuration"] = normalize_seedance_duration(payload.get("seedanceDuration", 5))
                    except (TypeError, ValueError):
                        config["seedanceDuration"] = 5
                if "seedanceResolution" in payload:
                    config["seedanceResolution"] = normalize_seedance_resolution(payload.get("seedanceResolution", "720p"))
                if "seedanceSize" in payload:
                    config["seedanceSize"] = normalize_seedance_size(payload.get("seedanceSize", "adaptive"))
                if "seedanceAudio" in payload:
                    config["seedanceAudio"] = normalize_bool(payload.get("seedanceAudio"), True)
                if "ffmpegPath" in payload:
                    config["ffmpegPath"] = str(payload.get("ffmpegPath", "")).strip()
                if "downloadRetentionDays" in payload:
                    try:
                        config["downloadRetentionDays"] = max(0, int(payload.get("downloadRetentionDays", 30)))
                    except (TypeError, ValueError):
                        config["downloadRetentionDays"] = 30
                if "douyinCookie" in payload:
                    douyin_cookie = str(payload.get("douyinCookie") or "").strip()
                    if douyin_cookie:
                        config["douyinCookie"] = douyin_cookie[:12000]
                if "packageTemplate" in payload:
                    config["packageTemplate"] = str(payload.get("packageTemplate", "")).strip()
                if "packageTemplates" in payload:
                    config["packageTemplates"] = normalize_package_templates(payload.get("packageTemplates"))
                save_config(config)
                cleanup_old_downloads()
                response(self, 200, public_config())
                return

            if self.path == "/api/download-link":
                payload = read_json(self)
                share_text = str(payload.get("url", "")).strip()
                if not share_text:
                    response(self, 400, {"error": "请先粘贴抖音或小红书分享链接。"})
                    return
                share_url = extract_share_url(share_text)
                notify_feature_used("下载分享视频", f"链接：{share_url}")
                def worker(tid: str) -> dict:
                    result = download_video_from_url(share_text, task_id=tid)
                    append_history("下载分享视频", Path(result.get("path", "")), summary=f"来源：{result.get('url', '')}", duration=result.get("duration", ""))
                    return result
                task_id = start_task("下载分享视频", worker)
                response(self, 200, {"taskId": task_id})
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

            if self.path == "/api/storyboard-images":
                payload = read_json(self)
                shots = payload.get("shots", [])
                all_shots = payload.get("allShots", [])
                shot_index = payload.get("index")
                references = payload.get("references", [])
                reference_description = str(payload.get("referenceDescription", "")).strip()[:1200]
                config = load_config()
                size = str(payload.get("size") or config.get("apimartImageSize") or "9:16")
                resolution = str(payload.get("resolution") or config.get("apimartImageResolution") or "1k")
                quality = normalize_image_quality(payload.get("quality") or config.get("apimartImageQuality") or "medium")
                notify_feature_used("生成分镜图", f"镜头数：{len(shots) if isinstance(shots, list) else 0}，参考图：{len(references) if isinstance(references, list) else 0}，比例：{size}，清晰度：{resolution}，质量：{quality}")
                def worker(tid: str) -> dict:
                    result = generate_storyboard_images(shots, size=size, resolution=resolution, quality=quality, references_raw=references, reference_description=reference_description, task_id=tid)
                    try:
                        index_value = int(shot_index) if shot_index is not None else None
                    except (TypeError, ValueError):
                        index_value = None
                    storyboard_history = storyboard_history_with_generated(all_shots, result.get("shots", []) if isinstance(result.get("shots"), list) else [], index=index_value)
                    append_history("生成分镜图", None, summary=result.get("summary", ""), storyboard=storyboard_history, references=result.get("references", [])[:16])
                    return result
                task_id = start_task("生成分镜图", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/storyboard-reference-images":
                payload = read_json(self)
                shots = payload.get("shots", [])
                existing_count = int(payload.get("existingCount") or 0)
                existing_references = normalize_reference_images(payload.get("existingReferences", []))
                size = str(payload.get("size") or "9:16")
                resolution = str(payload.get("resolution") or "1k")
                quality = normalize_image_quality(payload.get("quality") or "medium")
                notify_feature_used("AI生成参考图", f"镜头数：{len(shots) if isinstance(shots, list) else 0}，比例：{size}，清晰度：{resolution}，质量：{quality}")
                def worker(tid: str) -> dict:
                    result = generate_storyboard_reference_images(shots, size=size, resolution=resolution, quality=quality, existing_count=existing_count, task_id=tid)
                    history_refs = (existing_references + (result.get("references", []) if isinstance(result.get("references"), list) else []))[:16]
                    append_history("AI生成参考图", None, summary=result.get("summary", ""), references=history_refs, storyboard=shots[:24] if isinstance(shots, list) else [])
                    return result
                task_id = start_task("AI生成参考图", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/storyboard-reference-image":
                payload = read_json(self)
                prompt = str(payload.get("prompt") or "").strip()[:1600]
                title = str(payload.get("title") or "AI参考图").strip()[:80]
                index = int(payload.get("index") or 0) + 1
                existing_references = normalize_reference_images(payload.get("existingReferences", []))
                size = str(payload.get("size") or "9:16")
                resolution = str(payload.get("resolution") or "1k")
                quality = normalize_image_quality(payload.get("quality") or "medium")
                if not prompt:
                    response(self, 400, {"error": "请先填写参考图提示词。"})
                    return
                notify_feature_used("重新生成参考图", f"标题：{title}，比例：{size}，清晰度：{resolution}，质量：{quality}")
                def worker(tid: str) -> dict:
                    ref = generate_reference_image_from_prompt(prompt, title=title, size=size, resolution=resolution, quality=quality, index=index, task_id=tid)
                    history_refs = list(existing_references)
                    if 0 <= index - 1 < len(history_refs):
                        history_refs[index - 1] = ref
                    else:
                        history_refs.append(ref)
                    append_history("重新生成参考图", None, summary=f"{title} 已重新生成。", references=history_refs[:16])
                    return {
                        "reference": ref,
                        "summary": f"{title} 已重新生成。",
                    }
                task_id = start_task("重新生成参考图", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/storyboard-videos":
                payload = read_json(self)
                shots = payload.get("shots", [])
                config = load_config()
                duration = int(payload.get("duration") or config.get("seedanceDuration") or 5)
                resolution = str(payload.get("resolution") or config.get("seedanceResolution") or "720p")
                size = str(payload.get("size") or config.get("seedanceSize") or "adaptive")
                references = payload.get("references", [])
                generate_audio = normalize_bool(payload.get("generateAudio"), bool(config.get("seedanceAudio", True)))
                notify_feature_used("生成视频片段", f"镜头数：{len(shots) if isinstance(shots, list) else 0}，时长：{duration} 秒，清晰度：{resolution}，比例：{size}，声音：{'是' if generate_audio else '否'}")
                def worker(tid: str) -> dict:
                    result = generate_storyboard_videos(shots, duration=duration, resolution=resolution, size=size, generate_audio=generate_audio, references_raw=references, task_id=tid)
                    append_history("生成视频片段", None, summary=result.get("summary", ""), storyboard=result.get("shots", [])[:24], videoReferences=normalize_story_video_references(references)[:15], outputDir=result.get("outputDir", ""))
                    return result
                task_id = start_task("生成视频片段", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/storyboard-video":
                payload = read_json(self)
                shot = payload.get("shot", {})
                all_shots = payload.get("allShots", [])
                index = int(payload.get("index", 0)) + 1
                config = load_config()
                if not isinstance(shot, dict):
                    response(self, 400, {"error": "请选择有效的分镜镜头。"})
                    return
                fallback_duration = storyboard_shot_video_duration(shot, normalize_seedance_duration(config.get("seedanceDuration") or 5))
                duration_value = payload.get("videoDuration") if "videoDuration" in payload else payload.get("duration")
                duration = normalize_seedance_duration(duration_value, fallback_duration) if normalize_bool(shot.get("videoDurationManual"), False) else fallback_duration
                resolution = normalize_seedance_resolution(payload.get("videoResolution") or payload.get("resolution") or config.get("seedanceResolution") or "720p")
                size = normalize_seedance_size(payload.get("videoSize") or payload.get("size") or config.get("seedanceSize") or "adaptive")
                references = payload.get("references", [])
                generate_audio = normalize_bool(payload.get("videoAudio") if "videoAudio" in payload else payload.get("generateAudio"), bool(config.get("seedanceAudio", True)))
                notify_feature_used("生成单个分镜视频", f"镜头：{index}，时长：{duration} 秒，清晰度：{resolution}，比例：{size}，声音：{'是' if generate_audio else '否'}")
                def worker(tid: str) -> dict:
                    current = dict(shot)
                    current.update({
                        "videoDuration": duration,
                        "videoResolution": resolution,
                        "videoSize": size,
                        "videoAudio": generate_audio,
                    })
                    result = generate_storyboard_videos([current], duration=duration, resolution=resolution, size=size, generate_audio=generate_audio, references_raw=references, task_id=tid)
                    generated = (result.get("shots") or [current])[0]
                    storyboard_history = storyboard_history_with_generated(all_shots, [generated], index=index - 1)
                    append_history("生成单个分镜视频", None, summary=f"镜头 {index} 视频片段已生成。", storyboard=storyboard_history, videoReferences=normalize_story_video_references(references)[:15], outputDir=result.get("outputDir", ""))
                    return {
                        "shot": generated,
                        "summary": f"镜头 {index} 视频片段已生成。",
                        "outputDir": result.get("outputDir", ""),
                    }
                task_id = start_task("生成单个分镜视频", worker)
                response(self, 200, {"taskId": task_id})
                return

            if self.path == "/api/storyboard-export-videos":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                output_dir = Path(payload.get("outputDir") or str(EXPORTS)).expanduser()
                shots = payload.get("shots", [])
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                output_dir.mkdir(parents=True, exist_ok=True)
                exported = export_storyboard_video_files(video, output_dir, shots)
                reveal_in_finder(Path(exported[0]["path"]))
                notify_feature_used("导出分镜视频", f"视频：{video.name}，数量：{len(exported)}")
                append_history("导出分镜视频", video, summary=f"导出 {len(exported)} 个分镜视频", outputDir=str(output_dir), segments=exported[:12])
                response(self, 200, {"segments": exported, "count": len(exported), "outputDir": str(output_dir)})
                return

            if self.path == "/api/storyboard-merge-videos":
                payload = read_json(self)
                video = Path(payload.get("path", "")).expanduser()
                output_dir = Path(payload.get("outputDir") or str(EXPORTS)).expanduser()
                shots = payload.get("shots", [])
                if not video.exists():
                    response(self, 400, {"error": "视频文件不存在。"})
                    return
                output = merge_storyboard_video_files(video, output_dir, shots)
                reveal_in_finder(output)
                notify_feature_used("合并分镜视频", f"视频：{video.name}，镜头数：{len(generated_storyboard_videos(shots))}")
                append_history("合并分镜视频", video, summary="按分镜顺序合并视频片段", output=str(output))
                response(self, 200, {"path": str(output), "outputDir": str(output_dir)})
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
