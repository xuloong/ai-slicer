# 打包路线

## 推荐成品形态

- macOS: `.app` / `.dmg`
- Windows: `.exe` / `.msi`
- ffmpeg: 建议随安装包内置，或首次启动时引导用户选择路径。
- API Key: 不写入代码。用户在“设置”里填写，保存到本机 `user_config.json`。

## 一键构建脚本

macOS:

```bash
python3 -m pip install -r requirements-build.txt
./scripts/build_app.sh
```

Windows:

```bat
python -m pip install -r requirements-build.txt
scripts\build_app_windows.bat
```

脚本会先用 PyInstaller 把 `server.py` 打成 Tauri sidecar，再调用 `npm run build` 生成安装包。

## Windows 安装包

macOS 不能稳定直接产出 Windows `.exe/.msi`。请在 Windows 机器上运行：

```bat
python -m pip install -r requirements-build.txt
npm install
scripts\build_app_windows.bat
```

也可以把项目推到 GitHub 后手动触发 `.github/workflows/build-windows.yml`，构建产物会作为 `windows-bundles` artifact 上传。

## macOS 图标、签名和“已损坏”提示

`tauri.conf.json` 已配置 `bundle.icon`，macOS 包内会写入 `CFBundleIconFile = icon.icns`。

当前本地构建使用 ad-hoc 签名：

```json
"macOS": {
  "signingIdentity": "-",
  "hardenedRuntime": false
}
```

这能保证 App bundle 自身资源签名完整，避免因为未封存 `Info.plist` / 图标资源导致的“已损坏”。如果要发给不熟悉命令行的外部用户，仍建议使用 Apple Developer ID 证书签名并 notarize，否则部分 macOS 版本下载后可能仍会被 Gatekeeper 拦截。

正式分发需要：

1. Apple Developer 账号。
2. Developer ID Application 证书。
3. 配置 `APPLE_ID`、`APPLE_PASSWORD`、`APPLE_TEAM_ID`，或 App Store Connect API Key。
4. 重新执行 `npm run build`，让 Tauri 完成签名和公证。

临时内测时，如果用户确认来源可信但系统提示无法打开，可在用户本机执行：

```bash
xattr -dr com.apple.quarantine "/Applications/AI短视频创作工具.app"
```

这只是内测绕过方式，不建议作为正式交付方案。

## 当前 Tauri 骨架

当前目录已加入 Tauri 2 骨架：

```bash
npm install
npm run dev
npm run build
```

这版配置会打开 `http://127.0.0.1:8765`。开发阶段仍由 Python 后端提供本地服务。

## 下一步生产化

1. 把 macOS / Windows 对应的 ffmpeg 二进制放进 bundle resources，或在首次启动时引导用户选择路径。
2. 如需 macOS 本地 OCR 的完整体验，需要把 OCR 能力改成独立原生 helper，避免依赖用户安装 Xcode Command Line Tools。
3. 配置文件已写到用户配置目录；页面“设置”用于填写 API Key 和 ffmpeg 路径。

## 轻量分发

不做安装包时，可以直接分发：

- `highlight_client/`
- Windows 用户双击 `start_windows.bat`
- macOS 用户运行 `./start_mac.sh`

这种方式要求用户自行安装 Python 3 和 ffmpeg。
