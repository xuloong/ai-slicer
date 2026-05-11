const $ = (id) => document.getElementById(id);

const videoPath = $("videoPath");
const info = $("info");
const clipsEl = $("clips");
const totalDuration = $("totalDuration");
const thumbGrid = $("thumbGrid");
const exportResult = $("exportResult");
const autoSummary = $("autoSummary");
const outputDir = $("outputDir");
const taskProgress = $("taskProgress");
const taskMessage = $("taskMessage");
const taskPercent = $("taskPercent");
const taskBar = $("taskBar");
const cancelTaskBtn = $("cancelTaskBtn");
const arkApiKey = $("arkApiKey");
const ffmpegPath = $("ffmpegPath");
const configState = $("configState");
const ffmpegDetected = $("ffmpegDetected");
const settingsModal = $("settingsModal");
const setupHint = $("setupHint");
const OUTPUT_DIR_KEY = "highlightClient.outputDir";

outputDir.value = localStorage.getItem(OUTPUT_DIR_KEY) || "";

let clips = [];
let currentTaskId = "";

function clock(seconds) {
  const value = Math.max(0, Math.round(Number(seconds) || 0));
  const m = Math.floor(value / 60);
  const s = value % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function renderClips() {
  clipsEl.innerHTML = "";
  clips.forEach((clip, index) => {
    const row = document.createElement("div");
    row.className = "clip";
    row.innerHTML = `
      <label>开始秒数<input type="number" min="0" step="0.1" value="${clip.start}"></label>
      <label>持续秒数<input type="number" min="0.1" step="0.1" value="${clip.duration}"></label>
      <button class="remove" title="删除片段">×</button>
      ${clip.reason || clip.dialogue ? `<div class="clipMeta"><strong>${clip.reason || "自动识别"}</strong>${clip.dialogue ? `：${clip.dialogue}` : ""}</div>` : ""}
    `;
    const [startInput, durationInput] = row.querySelectorAll("input");
    startInput.addEventListener("input", () => {
      clips[index].start = Number(startInput.value);
      updateTotal();
    });
    durationInput.addEventListener("input", () => {
      clips[index].duration = Number(durationInput.value);
      updateTotal();
    });
    row.querySelector("button").addEventListener("click", () => {
      clips.splice(index, 1);
      renderClips();
    });
    clipsEl.appendChild(row);
  });
  updateTotal();
}

function updateTotal() {
  const total = clips.reduce((sum, clip) => sum + Number(clip.duration || 0), 0);
  totalDuration.textContent = clock(total);
}

async function post(url, body) {
  const result = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await result.json();
  if (!result.ok) throw new Error(json.error || "请求失败");
  return json;
}

async function loadConfig() {
  try {
    const result = await fetch("/api/config");
    const data = await result.json();
    if (!result.ok) throw new Error(data.error || "设置读取失败");
    ffmpegPath.value = data.ffmpegPath || "";
    arkApiKey.placeholder = data.hasArkApiKey ? `已保存：${data.arkApiKeyMasked}` : "仅保存在本机配置文件中";
    configState.textContent = data.hasArkApiKey ? "AI Key 已配置" : "AI Key 未配置";
    ffmpegDetected.textContent = data.detectedFfmpegPath ? `检测到 ffmpeg：${data.detectedFfmpegPath}` : "未自动检测到 ffmpeg";
    const missing = [];
    if (!data.hasArkApiKey) missing.push("火山方舟 API Key");
    if (!data.detectedFfmpegPath && !data.ffmpegPath) missing.push("ffmpeg 路径");
    if (missing.length) {
      setupHint.hidden = false;
      setupHint.textContent = `首次使用建议先设置：${missing.join("、")}。普通本地识别需要 ffmpeg，AI识别高光需要 API Key。`;
    } else {
      setupHint.hidden = true;
      setupHint.textContent = "";
    }
    return data;
  } catch (error) {
    configState.textContent = error.message;
    return null;
  }
}

function openSettings() {
  settingsModal.hidden = false;
}

function closeSettings() {
  settingsModal.hidden = true;
}

$("settingsBtn").addEventListener("click", openSettings);
$("closeSettingsBtn").addEventListener("click", closeSettings);
settingsModal.addEventListener("click", (event) => {
  if (event.target === settingsModal) closeSettings();
});

$("pickFfmpegBtn").addEventListener("click", async () => {
  configState.textContent = "请选择 ffmpeg 可执行文件...";
  try {
    const data = await post("/api/pick-ffmpeg", {});
    ffmpegPath.value = data.path;
    configState.textContent = "已选择 ffmpeg，记得保存设置";
  } catch (error) {
    configState.textContent = error.message;
  }
});

$("saveConfigBtn").addEventListener("click", async () => {
  configState.textContent = "正在保存设置...";
  try {
    const payload = { ffmpegPath: ffmpegPath.value.trim() };
    if (arkApiKey.value.trim()) payload.arkApiKey = arkApiKey.value.trim();
    await post("/api/config", payload);
    arkApiKey.value = "";
    await loadConfig();
    configState.textContent = "设置已保存";
  } catch (error) {
    configState.textContent = error.message;
  }
});

function setProgress(progress, message) {
  taskProgress.hidden = false;
  const value = Math.max(0, Math.min(100, Math.round(progress || 0)));
  taskBar.style.width = `${value}%`;
  taskPercent.textContent = `${value}%`;
  taskMessage.textContent = message || "处理中...";
}

function finishTaskProgress() {
  currentTaskId = "";
  cancelTaskBtn.hidden = true;
  cancelTaskBtn.disabled = false;
}

cancelTaskBtn.addEventListener("click", async () => {
  if (!currentTaskId) return;
  cancelTaskBtn.disabled = true;
  setProgress(Number(taskPercent.textContent.replace("%", "")) || 0, "正在终止...");
  try {
    await post(`/api/task/${currentTaskId}/cancel`, {});
  } catch (error) {
    taskMessage.textContent = error.message;
    cancelTaskBtn.disabled = false;
  }
});

async function runTask(startUrl, body, onDone) {
  setProgress(1, "准备开始");
  const started = await post(startUrl, body);
  const taskId = started.taskId;
  if (!taskId) throw new Error("任务启动失败。");
  currentTaskId = taskId;
  cancelTaskBtn.hidden = false;
  cancelTaskBtn.disabled = false;

  try {
    while (true) {
      await new Promise((resolve) => setTimeout(resolve, 900));
      const result = await fetch(`/api/task/${taskId}`);
      const task = await result.json();
      if (!result.ok) throw new Error(task.error || "任务状态读取失败");
      setProgress(task.progress, task.message);
      if (task.status === "done") {
        setProgress(100, "完成");
        onDone(task.result);
        return task.result;
      }
      if (task.status === "cancelled") {
        throw new Error("已终止。");
      }
      if (task.status === "error") {
        throw new Error(task.error || task.message || "任务失败");
      }
    }
  } finally {
    finishTaskProgress();
  }
}

function showMediaInfo(data) {
  const media = data.info;
  info.innerHTML = `
    <div class="infoGrid">
      <div class="infoItem"><span>视频时长</span><strong>${media.duration}</strong></div>
      <div class="infoItem"><span>画面尺寸</span><strong>${media.resolution}</strong></div>
      <div class="infoItem"><span>画面比例</span><strong>${media.ratio}</strong></div>
      <div class="infoItem"><span>帧率</span><strong>${media.fps}</strong></div>
      <div class="infoItem"><span>视频编码</span><strong>${media.video}</strong></div>
      <div class="infoItem"><span>音频信息</span><strong>${media.audio}</strong></div>
      <div class="infoItem"><span>整体码率</span><strong>${media.bitrate}</strong></div>
    </div>
  `;
}

async function probeVideo() {
  info.textContent = "正在读取视频信息...";
  try {
    const data = await post("/api/probe", { path: videoPath.value });
    showMediaInfo(data);
  } catch (error) {
    info.textContent = error.message;
  }
}

$("pickVideoBtn").addEventListener("click", async () => {
  info.textContent = "请选择视频文件...";
  try {
    const data = await post("/api/pick-file", {});
    videoPath.value = data.path;
    await probeVideo();
  } catch (error) {
    info.textContent = error.message;
  }
});

$("pickDirBtn").addEventListener("click", async () => {
  exportResult.textContent = "请选择导出目录...";
  try {
    const data = await post("/api/pick-dir", {});
    outputDir.value = data.path;
    localStorage.setItem(OUTPUT_DIR_KEY, data.path);
    exportResult.textContent = `导出目录：${data.path}`;
  } catch (error) {
    exportResult.textContent = error.message;
  }
});

outputDir.addEventListener("change", () => {
  const value = outputDir.value.trim();
  if (value) localStorage.setItem(OUTPUT_DIR_KEY, value);
});

$("thumbBtn").addEventListener("click", async () => {
  thumbGrid.className = "grid empty";
  thumbGrid.textContent = "正在生成缩略图...";
  try {
    const data = await runTask("/api/thumbs", {
      path: videoPath.value,
      interval: Number($("interval").value),
    }, (taskResult) => {
      thumbGrid.className = "grid";
      thumbGrid.innerHTML = "";
      taskResult.thumbs.forEach((thumb) => {
        const card = document.createElement("button");
        card.className = "thumb";
        if (thumb.width && thumb.height) {
          card.style.setProperty("--thumb-ratio", `${thumb.width} / ${thumb.height}`);
        }
        card.innerHTML = `<img src="${thumb.src}" alt=""><time>${clock(thumb.time)}</time>`;
        card.addEventListener("click", () => {
          clips.push({ start: thumb.time, duration: 15 });
          renderClips();
        });
        thumbGrid.appendChild(card);
      });
    });
  } catch (error) {
    thumbGrid.className = "grid empty";
    thumbGrid.textContent = error.message;
  }
});

$("autoBtn").addEventListener("click", async () => {
  autoSummary.textContent = "正在用本地算法分析画面变化、字幕台词并合并自然段落...";
  try {
    await runTask("/api/auto", {
      path: videoPath.value,
      target: Number($("targetSeconds").value),
    }, (data) => {
      clips = data.clips.map((clip) => ({
        start: clip.start,
        duration: clip.duration,
        reason: clip.reason,
        dialogue: clip.dialogue,
      }));
      autoSummary.textContent = `${data.summary} 预计成片 ${data.duration}。`;
      renderClips();
    });
  } catch (error) {
    autoSummary.textContent = error.message;
  }
});

$("aiAutoBtn").addEventListener("click", async () => {
  autoSummary.textContent = "正在本地粗筛候选段落，并调用豆包 Seed 2.0 Pro 做剧情高光判断...";
  try {
    await runTask("/api/ai-auto", {
      path: videoPath.value,
      target: Number($("targetSeconds").value),
    }, (data) => {
      clips = data.clips.map((clip) => ({
        start: clip.start,
        duration: clip.duration,
        reason: clip.reason,
        dialogue: clip.dialogue,
      }));
      autoSummary.textContent = `${data.summary} 预计成片 ${data.duration}。`;
      renderClips();
    });
  } catch (error) {
    autoSummary.textContent = error.message;
  }
});

$("addClipBtn").addEventListener("click", () => {
  clips.push({ start: 0, duration: 15 });
  renderClips();
});

function rememberOutputDir() {
  if (outputDir.value.trim()) {
    localStorage.setItem(OUTPUT_DIR_KEY, outputDir.value.trim());
  }
}

function renderSegmentExportResult(data) {
  const items = data.segments.map((segment, index) => (
    `<li><span>片段 ${index + 1}，时长 ${segment.duration}</span><code>${segment.path}</code></li>`
  )).join("");
  exportResult.innerHTML = `
    <div class="exportStatus">
      <strong>片段导出完成</strong>
      <span>已导出 ${data.count} 个片段，并打开所在目录</span>
      <ul class="segmentList">${items}</ul>
    </div>
  `;
}

$("exportSegmentsBtn").addEventListener("click", async () => {
  exportResult.textContent = "正在导出片段，稍等一下...";
  try {
    const data = await post("/api/export-segments", {
      path: videoPath.value,
      outputDir: outputDir.value,
      clips,
    });
    rememberOutputDir();
    renderSegmentExportResult(data);
  } catch (error) {
    exportResult.textContent = error.message;
  }
});

$("exportBtn").addEventListener("click", async () => {
  exportResult.textContent = "正在导出，稍等一下...";
  try {
    const data = await post("/api/export", {
      path: videoPath.value,
      outputDir: outputDir.value,
      clips,
    });
    rememberOutputDir();
    exportResult.innerHTML = `
      <div class="exportStatus">
        <strong>导出完成</strong>
        <span>文件已在 Finder 中打开</span>
        <code>${data.path}</code>
        <span>时长：${data.duration}</span>
      </div>
    `;
  } catch (error) {
    exportResult.textContent = error.message;
  }
});

renderClips();
loadConfig().then((data) => {
  if (data && (!data.hasArkApiKey || (!data.detectedFfmpegPath && !data.ffmpegPath))) {
    openSettings();
  }
});
