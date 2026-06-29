# 打包路线

## 推荐成品形态

- macOS: `.app` / `.dmg`
- Windows: `.exe` / `.msi`
- ffmpeg: 建议随安装包内置，或首次启动时引导用户选择路径。
- API Key: 当前版本由服务端默认配置统一提供，用户不需要在设置中填写。

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

## 自动更新

当前已接入 Tauri Updater，更新地址为 GitHub Releases 的：

```text
https://github.com/xuloong/ai-slicer/releases/latest/download/latest.json
```

发布流程：

1. 保存 updater 私钥。当前生成的私钥临时放在 `/private/tmp/ai-short-video-updater-v2.key`，请把文件内容保存到 GitHub Secrets:
   - `TAURI_SIGNING_PRIVATE_KEY`
   - `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` 留空即可，除非后续重新生成带密码的私钥。
2. 修改版本号，保持以下三个位置一致：
   - `highlight_client/package.json`
   - `highlight_client/package-lock.json`
   - `highlight_client/src-tauri/tauri.conf.json`
3. 推送 tag，例如：

```bash
git tag v0.1.1
git push origin v0.1.1
```

4. GitHub Actions 会运行 `.github/workflows/release-tauri.yml`，生成 macOS / Windows 安装包、更新包签名和 `latest.json`。Release 工作流会校验 `latest.json` 是否存在且同时包含 macOS / Windows 平台信息。
5. 已安装客户端启动后会自动检查一次更新；用户也可以在“设置”里点击“检查更新”。

注意：Tauri 更新包必须签名校验。私钥丢失后，已经安装的旧客户端将无法升级到后续版本，需要重新分发完整安装包。`v0.1.10` / `v0.1.11` / `v0.1.12` 发布时没有生成完整有效的 `latest.json`，因此需要用户手动安装 `v0.1.13` 或更新版本；从配置了新私钥、同时发布 macOS `app` 更新包，并由工作流手动生成 `latest.json` 的版本开始，后续版本才能通过“检查更新”自动升级。

## AI 生成素材日志和对象存储

调用 GPT-Image-2 / Seedance2.0 生成图片或视频后，程序会把提示词、模型参数、生成平台链接、本地路径写入企业微信使用日志。

生成图片和视频会默认同步上传到火山引擎对象存储。当前项目已内置默认 TOS 配置，如需在不同环境覆盖，请配置以下变量：

```bash
TOS_ENDPOINT=https://tos-cn-shanghai.volces.com
TOS_REGION=cn-shanghai
TOS_BUCKET=aivideo-topsky
TOS_ACCESS_KEY_ID=your-access-key-id
TOS_SECRET_ACCESS_KEY=your-secret-access-key
TOS_PUBLIC_BASE_URL=https://aivideo-topsky.tos-cn-shanghai.volces.com
TOS_OBJECT_PREFIX=ai-short-video-generations
```

`TOS_PUBLIC_BASE_URL` 可选；如果配置了自定义 CDN / 公开访问域名，日志会记录这个域名下的素材链接。对象存储上传失败时，生成流程不会中断，日志仍会记录 AI 平台返回链接和本地路径。

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
3. 配置文件已写到用户配置目录；页面“设置”用于填写 ffmpeg 路径、下载保留时间和一键成片模板。

## 轻量分发

不做安装包时，可以直接分发：

- `highlight_client/`
- Windows 用户双击 `start_windows.bat`
- macOS 用户运行 `./start_mac.sh`

这种方式要求用户自行安装 Python 3 和 ffmpeg。
