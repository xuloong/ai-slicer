# AI切片神器

## macOS

```bash
./start_mac.sh
```

macOS 版本会使用系统文件选择器、AVFoundation 导出、Vision OCR。

## Windows

1. 安装 Python 3。
2. 安装 ffmpeg，并确保 `ffmpeg.exe` 在 `PATH` 中，或放在 `C:\ffmpeg\bin\ffmpeg.exe`。
3. 双击 `start_windows.bat`。
4. 打开 `http://127.0.0.1:8765/`。

Windows 版本使用 ffmpeg 导出，文件选择使用 tkinter，导出完成后用 Explorer 定位文件。本地 OCR 会自动跳过；AI 识别仍可使用关键帧和候选段落调用豆包模型。

## 设置

首次使用 `AI识别高光` 前，请在页面“设置”里填写火山方舟 API Key。Key 只保存在本机配置文件 `user_config.json`，不会写进前端页面。

如果自动找不到 ffmpeg，也可以在“设置”里手动选择 ffmpeg 可执行文件。

## 打包

见 [PACKAGING.md](./PACKAGING.md)。
