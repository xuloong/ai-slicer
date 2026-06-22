const $ = (id) => document.getElementById(id);

const videoPath = $("videoPath");
const info = $("info");
const clipsEl = $("clips");
const totalDuration = $("totalDuration");
const thumbGrid = $("thumbGrid");
const exportResult = $("exportResult");
const autoSummary = $("autoSummary");
const clipInsights = $("clipInsights");
const previewPane = $("previewPane");
const clipPreview = $("clipPreview");
const previewState = $("previewState");
const historyList = $("historyList");
const storyboardList = $("storyboardList");
const storySummary = $("storySummary");
const storyboardPanel = $("storyboardPanel");
const thumbPanel = $("thumbPanel");
const highlightPanel = $("highlightPanel");
const packagePanel = $("packagePanel");
const storyboardTabBtn = $("storyboardTabBtn");
const thumbTabBtn = $("thumbTabBtn");
const highlightTabBtn = $("highlightTabBtn");
const packageTabBtn = $("packageTabBtn");
const outputDir = $("outputDir");
const taskProgress = $("taskProgress");
const taskMessage = $("taskMessage");
const taskPercent = $("taskPercent");
const taskBar = $("taskBar");
const cancelTaskBtn = $("cancelTaskBtn");
const arkApiKey = $("arkApiKey");
const ffmpegPath = $("ffmpegPath");
const wecomWebhookUrl = $("wecomWebhookUrl");
const usageLogName = $("usageLogName");
const usageLogDept = $("usageLogDept");
const configState = $("configState");
const ffmpegDetected = $("ffmpegDetected");
const settingsModal = $("settingsModal");
const setupHint = $("setupHint");
const aiRequirement = $("aiRequirement");
const packageTemplate = $("packageTemplate");
const packageBgm = $("packageBgm");
const stickersList = $("stickersList");
const bgmList = $("bgmList");
const focusList = $("focusList");
const focusRequirement = $("focusRequirement");
const templateEditorSelect = $("templateEditorSelect");
const templateName = $("templateName");
const templateStyle = $("templateStyle");
const templateDefaultBgm = $("templateDefaultBgm");
const OUTPUT_DIR_KEY = "highlightClient.outputDir";

outputDir.value = localStorage.getItem(OUTPUT_DIR_KEY) || "";

let clips = [];
let currentTaskId = "";
let packageTemplates = {};
let selectedPackageTemplate = "none";
let stickers = [];
let bgms = [];
let focusMarks = [];
let storyboardShots = [];
let storyboardSummary = "";

const ROLE_LABELS = {
  hook: "开头钩子",
  build: "剧情推进",
  turn: "反转冲突",
  ending: "结尾钩子",
  local: "本地高光",
};

const FALLBACK_TEMPLATES = {
  clean: {
    id: "clean",
    name: "干净包装",
    bgm: false,
    style: "clean",
    font_color: "white",
    box_color: "black@0.35",
    font_size: 38,
  },
  drama: {
    id: "drama",
    name: "短剧爆点",
    bgm: true,
    style: "drama",
    font_color: "yellow",
    box_color: "black@0.55",
    font_size: 44,
  },
  ad: {
    id: "ad",
    name: "广告强包装",
    bgm: true,
    style: "ad",
    font_color: "white",
    box_color: "red@0.55",
    font_size: 42,
  },
};

function clock(seconds) {
  const value = Math.max(0, Math.round(Number(seconds) || 0));
  const m = Math.floor(value / 60);
  const s = value % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function displayAction(action) {
  return action === "AI圈画重点" ? "AI识别重点" : (action || "任务");
}

function switchContentTab(tab) {
  const panels = {
    storyboard: storyboardPanel,
    thumb: thumbPanel,
    highlight: highlightPanel,
    package: packagePanel,
  };
  const tabs = {
    storyboard: storyboardTabBtn,
    thumb: thumbTabBtn,
    highlight: highlightTabBtn,
    package: packageTabBtn,
  };
  Object.entries(panels).forEach(([key, panel]) => {
    panel.hidden = key !== tab;
  });
  Object.entries(tabs).forEach(([key, button]) => {
    const active = key === tab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
}

function renderStoryboard(summary = "") {
  storyboardSummary = summary || "";
  storySummary.textContent = summary || "";
  if (!storyboardShots.length) {
    storyboardList.className = "storyboardList empty";
    storyboardList.textContent = "生成后会在这里展示镜号、时间、画面、景别、运镜、字幕和剪辑建议。";
    return;
  }
  storyboardList.className = "storyboardList";
  storyboardList.innerHTML = storyboardShots.map((shot, index) => `
    <article class="storyShot">
      <div class="storyShotHead">
        <strong>镜头 ${shot.shot || index + 1}</strong>
        <span>${clock(shot.start)} - ${clock(shot.end)}</span>
      </div>
      <div class="storyField"><b>画面</b><span>${escapeHtml(shot.scene || "根据画面内容推进")}</span></div>
      <div class="storyMeta">
        <span><b>景别</b>${escapeHtml(shot.shotType || "中景")}</span>
        <span><b>运镜</b>${escapeHtml(shot.camera || "稳定跟随")}</span>
      </div>
      <div class="storyField"><b>内容</b><span>${escapeHtml(shot.action || "展示关键动作或卖点")}</span></div>
      ${shot.dialogue ? `<div class="storyField"><b>台词</b><span>${escapeHtml(shot.dialogue)}</span></div>` : ""}
      ${shot.caption ? `<div class="storyField"><b>字幕</b><span>${escapeHtml(shot.caption)}</span></div>` : ""}
      <div class="storyField"><b>剪辑建议</b><span>${escapeHtml(shot.edit || "自然衔接到下一镜")}</span></div>
    </article>
  `).join("");
}

function renderClips() {
  clipsEl.innerHTML = "";
  clips.forEach((clip, index) => {
    const row = document.createElement("div");
    row.className = "clip";
    row.innerHTML = `
      <label>开始秒数<input type="number" min="0" step="0.1" value="${clip.start}"></label>
      <label>持续秒数<input type="number" min="0.1" step="0.1" value="${clip.duration}"></label>
      <div class="clipTools">
        <button class="previewClip" title="预览片段">▶</button>
        <button class="remove" title="删除片段">×</button>
      </div>
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
    row.querySelector(".previewClip").addEventListener("click", () => {
      previewClip(index);
    });
    row.querySelector(".remove").addEventListener("click", () => {
      clips.splice(index, 1);
      renderClips();
      renderInsights();
    });
    clipsEl.appendChild(row);
  });
  updateTotal();
  renderInsights();
}

function updateTotal() {
  const total = clips.reduce((sum, clip) => sum + Number(clip.duration || 0), 0);
  totalDuration.textContent = clock(total);
}

function renderInsights() {
  if (!clips.length) {
    clipInsights.className = "insights empty";
    clipInsights.textContent = "识别后会在这里展示片段依据。";
    return;
  }
  clipInsights.className = "insights";
  clipInsights.innerHTML = clips.map((clip, index) => `
    <div class="insight">
      <strong>${index + 1}. ${ROLE_LABELS[clip.role] || "高光片段"} · ${clock(clip.duration)}</strong>
      <span>${clip.reason || "保留相对完整的剧情段落"}</span>
      ${clip.dialogue ? `<small>${clip.dialogue}</small>` : ""}
    </div>
  `).join("");
}

async function previewClip(index) {
  const clip = clips[index];
  if (!clip) return;
  previewPane.hidden = false;
  previewState.textContent = `正在生成片段 ${index + 1} 的预览...`;
  try {
    const data = await post("/api/preview", {
      path: videoPath.value,
      clip,
    });
    clipPreview.src = `${data.url}?t=${Date.now()}`;
    previewState.textContent = `预览片段 ${index + 1}：${data.duration}`;
    await clipPreview.play().catch(() => {});
  } catch (error) {
    previewState.textContent = error.message;
  }
}

async function loadHistory() {
  try {
    const result = await fetch("/api/history");
    const data = await result.json();
    if (!result.ok) throw new Error(data.error || "历史记录读取失败");
    renderHistory(data.items || []);
  } catch (error) {
    historyList.className = "historyList empty";
    historyList.textContent = error.message;
  }
}

function renderHistory(items) {
  items = items.filter((item) => item.action !== "导出分镜脚本");
  if (!items.length) {
    historyList.className = "historyList empty";
    historyList.textContent = "暂无历史记录。";
    return;
  }
  historyList.className = "historyList";
  historyList.innerHTML = items.map((item) => `
    <button class="historyItem" type="button" data-id="${item.id}">
      <strong>${displayAction(item.action)} · ${item.videoName || "未命名视频"}</strong>
      <span>${item.time || ""}</span>
      <small>${item.summary || item.duration || item.output || ""}</small>
    </button>
  `).join("");
  historyList.querySelectorAll(".historyItem").forEach((button) => {
    button.addEventListener("click", () => {
      const item = items.find((value) => value.id === button.dataset.id);
      if (!item) return;
      if (item.video) videoPath.value = item.video;
      if (Array.isArray(item.clips) && item.clips.length) {
        clips = item.clips.map((clip) => ({
          start: clip.start,
          duration: clip.duration,
          reason: clip.reason,
          dialogue: clip.dialogue,
          role: clip.role,
          score: clip.score,
        }));
        autoSummary.textContent = item.summary || `${item.action} 的历史片段已载入。`;
        renderClips();
        switchContentTab("highlight");
      }
      if (Array.isArray(item.storyboard) && item.storyboard.length) {
        storyboardShots = item.storyboard;
        renderStoryboard(item.summary || "历史分镜脚本已载入。");
        switchContentTab("storyboard");
      }
    });
  });
}

function renderTimedAssets(listEl, items, kind) {
  if (!items.length) {
    listEl.className = "assetList empty";
    listEl.textContent = kind === "sticker" ? "暂无贴图素材。" : "暂无 BGM 素材。";
    return;
  }
  listEl.className = "assetList";
  listEl.innerHTML = "";
  items.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "assetRow";
    row.innerHTML = `
      <label class="field assetPath">
        <span>${kind === "sticker" ? "贴图文件" : "BGM 文件"}</span>
        <span class="pathPicker">
          <input value="${escapeHtml(item.path || "")}" placeholder="${kind === "sticker" ? "选择 PNG/JPG/WebP 图片" : "选择 MP3/WAV/M4A 音频"}">
          <button type="button" class="pickAsset">选择</button>
        </span>
      </label>
      <label class="field">
        <span>开始秒数</span>
        <input class="assetStart" type="number" min="0" step="0.1" value="${Number(item.start || 0)}">
      </label>
      <label class="field">
        <span>结束秒数</span>
        <input class="assetEnd" type="number" min="0.1" step="0.1" value="${Number(item.end || 5)}">
      </label>
      <button type="button" class="removeAsset" title="删除">×</button>
    `;
    const pathInput = row.querySelector(".assetPath input");
    const startInput = row.querySelector(".assetStart");
    const endInput = row.querySelector(".assetEnd");
    pathInput.addEventListener("input", () => {
      items[index].path = pathInput.value.trim();
    });
    startInput.addEventListener("input", () => {
      items[index].start = Number(startInput.value);
    });
    endInput.addEventListener("input", () => {
      items[index].end = Number(endInput.value);
    });
    row.querySelector(".pickAsset").addEventListener("click", async () => {
      exportResult.textContent = kind === "sticker" ? "请选择贴图图片..." : "请选择 BGM 音频...";
      try {
        const data = await post(kind === "sticker" ? "/api/pick-logo" : "/api/pick-bgm", {});
        items[index].path = data.path;
        pathInput.value = data.path;
        if (kind === "bgm") packageBgm.checked = true;
        exportResult.textContent = kind === "sticker" ? "已选择贴图。" : "已选择 BGM。";
      } catch (error) {
        exportResult.textContent = error.message;
      }
    });
    row.querySelector(".removeAsset").addEventListener("click", () => {
      items.splice(index, 1);
      if (kind === "sticker") renderTimedAssets(stickersList, stickers, "sticker");
      else renderTimedAssets(bgmList, bgms, "bgm");
    });
    listEl.appendChild(row);
  });
}

function renderFocusMarks() {
  if (!focusMarks.length) {
    focusList.className = "assetList empty";
    focusList.textContent = "暂无重点标记。";
    return;
  }
  focusList.className = "assetList focusList";
  focusList.innerHTML = "";
  focusMarks.forEach((mark, index) => {
    const row = document.createElement("div");
    row.className = "focusItem";
    row.innerHTML = `
      <input class="focusToggle" type="checkbox" ${mark.selected === false ? "" : "checked"} aria-label="是否使用这个重点">
      <span>
        <strong>${index + 1}. ${clock(mark.start)} - ${clock(mark.end)}</strong>
        <small>${escapeHtml(mark.reason || "AI识别出的重点内容")}</small>
      </span>
      <select class="focusEffect" aria-label="重点突出形式">
        <option value="circle">圈画</option>
        <option value="zoom">放大抖动</option>
      </select>
    `;
    const toggle = row.querySelector(".focusToggle");
    const effect = row.querySelector(".focusEffect");
    effect.value = mark.effect || "circle";
    toggle.addEventListener("change", (event) => {
      focusMarks[index].selected = event.target.checked;
    });
    effect.addEventListener("change", (event) => {
      focusMarks[index].effect = event.target.value;
    });
    focusList.appendChild(row);
  });
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
    wecomWebhookUrl.value = data.wecomWebhookUrl || "";
    usageLogName.value = data.usageLogName || "";
    usageLogDept.value = data.usageLogDept || "";
    packageTemplates = normalizeTemplates(data.packageTemplates || FALLBACK_TEMPLATES);
    selectedPackageTemplate = data.packageTemplate || "none";
    renderTemplateOptions(selectedPackageTemplate);
    renderTemplateEditor(packageTemplates[selectedPackageTemplate] ? selectedPackageTemplate : templateEditorSelect.value);
    packageBgm.checked = getSelectedTemplate().bgm !== false;
    arkApiKey.placeholder = data.hasArkApiKey ? `已保存：${data.arkApiKeyMasked}` : "仅保存在本机配置文件中";
    configState.textContent = data.hasArkApiKey ? "AI Key 已配置" : "AI Key 未配置";
    ffmpegDetected.textContent = data.detectedFfmpegPath ? `检测到 ffmpeg：${data.detectedFfmpegPath}` : "未自动检测到 ffmpeg";
    const missing = [];
    if (!data.usageLogName) missing.push("姓名");
    if (!data.usageLogDept) missing.push("部门");
    if (!data.hasArkApiKey) missing.push("火山方舟 API Key");
    if (!data.detectedFfmpegPath && !data.ffmpegPath) missing.push("ffmpeg 路径");
    if (missing.length) {
      setupHint.hidden = false;
      setupHint.textContent = `首次使用建议先设置：${missing.join("、")}。姓名和部门会用于使用日志，普通本地识别需要 ffmpeg，AI识别高光需要 API Key。`;
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

function normalizeTemplates(templates) {
  const source = templates && typeof templates === "object" ? templates : FALLBACK_TEMPLATES;
  const normalized = {};
  Object.entries(source).forEach(([key, template]) => {
    const id = String(template.id || key || "").trim();
    if (!id) return;
    normalized[id] = {
      id,
      name: String(template.name || id).trim(),
      bgm: template.bgm !== false,
      style: ["drama", "ad", "clean"].includes(template.style) ? template.style : "clean",
      font_color: String(template.font_color || "white").trim(),
      box_color: String(template.box_color || "black@0.45").trim(),
      font_size: Math.max(24, Math.min(72, Number(template.font_size) || 40)),
    };
  });
  return Object.keys(normalized).length ? normalized : { ...FALLBACK_TEMPLATES };
}

function getSelectedTemplate() {
  if (packageTemplate.value === "none") {
    return { id: "none", name: "不使用模板", bgm: false, style: "clean" };
  }
  return packageTemplates[packageTemplate.value] || packageTemplates[selectedPackageTemplate] || packageTemplates.drama || Object.values(packageTemplates)[0] || FALLBACK_TEMPLATES.drama;
}

function renderTemplateOptions(selectedId) {
  const options = Object.values(packageTemplates).map((template) => (
    `<option value="${escapeHtml(template.id)}">${escapeHtml(template.name)}</option>`
  )).join("");
  packageTemplate.innerHTML = `<option value="none">不使用模板</option>${options}`;
  templateEditorSelect.innerHTML = options;
  const nextPackageId = selectedId === "none" || packageTemplates[selectedId] ? selectedId : "none";
  const nextEditorId = packageTemplates[selectedId] ? selectedId : Object.keys(packageTemplates)[0];
  packageTemplate.value = nextPackageId;
  templateEditorSelect.value = nextEditorId;
  selectedPackageTemplate = nextPackageId;
}

function renderTemplateEditor(templateId) {
  const template = packageTemplates[templateId] || getSelectedTemplate();
  if (!template) return;
  templateEditorSelect.value = template.id;
  templateName.value = template.name || "";
  templateStyle.value = template.style || "clean";
  templateDefaultBgm.checked = template.bgm !== false;
}

function readTemplateEditor() {
  const currentId = templateEditorSelect.value || "template";
  return {
    id: currentId,
    name: templateName.value.trim() || "未命名模板",
    bgm: templateDefaultBgm.checked,
    style: templateStyle.value,
    font_color: "white",
    box_color: "black@0.45",
    font_size: 40,
  };
}

function configNeedsSetup(data) {
  return data && (!data.usageLogName || !data.usageLogDept || !data.hasArkApiKey || (!data.detectedFfmpegPath && !data.ffmpegPath));
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
    if (templateEditorSelect.value) {
      const currentPackageTemplate = packageTemplate.value;
      const editedTemplate = readTemplateEditor();
      packageTemplates[editedTemplate.id] = editedTemplate;
      renderTemplateOptions(currentPackageTemplate);
      renderTemplateEditor(editedTemplate.id);
    }
    const payload = {
      ffmpegPath: ffmpegPath.value.trim(),
      wecomWebhookUrl: wecomWebhookUrl.value.trim(),
      usageLogName: usageLogName.value.trim(),
      usageLogDept: usageLogDept.value.trim(),
      packageTemplate: packageTemplate.value,
      packageTemplates,
    };
    if (arkApiKey.value.trim()) payload.arkApiKey = arkApiKey.value.trim();
    await post("/api/config", payload);
    arkApiKey.value = "";
    await loadConfig();
    configState.textContent = "设置已保存";
  } catch (error) {
    configState.textContent = error.message;
  }
});

$("addStickerBtn").addEventListener("click", () => {
  stickers.push({ path: "", start: 0, end: Math.max(5, Math.round(clips.reduce((sum, clip) => sum + Number(clip.duration || 0), 0)) || 5) });
  renderTimedAssets(stickersList, stickers, "sticker");
});

$("addBgmBtn").addEventListener("click", () => {
  bgms.push({ path: "", start: 0, end: Math.max(5, Math.round(clips.reduce((sum, clip) => sum + Number(clip.duration || 0), 0)) || 5) });
  packageBgm.checked = true;
  renderTimedAssets(bgmList, bgms, "bgm");
});

packageTemplate.addEventListener("change", () => {
  selectedPackageTemplate = packageTemplate.value;
  const template = getSelectedTemplate();
  packageBgm.checked = template.bgm !== false;
});

templateEditorSelect.addEventListener("change", () => {
  renderTemplateEditor(templateEditorSelect.value);
});

$("addTemplateBtn").addEventListener("click", () => {
  const id = `custom_${Date.now().toString(36)}`;
  packageTemplates[id] = {
    ...getSelectedTemplate(),
    id,
    name: "新模板",
  };
  renderTemplateOptions(id);
  renderTemplateEditor(id);
  configState.textContent = "已新增模板，调整后点击保存模板或保存设置。";
});

$("updateTemplateBtn").addEventListener("click", () => {
  const template = readTemplateEditor();
  packageTemplates[template.id] = template;
  renderTemplateOptions(template.id);
  renderTemplateEditor(template.id);
  configState.textContent = "模板已更新，点击保存设置后生效。";
});

$("deleteTemplateBtn").addEventListener("click", () => {
  const id = templateEditorSelect.value;
  if (Object.keys(packageTemplates).length <= 1) {
    configState.textContent = "至少保留一个模板。";
    return;
  }
  delete packageTemplates[id];
  const nextId = Object.keys(packageTemplates)[0];
  renderTemplateOptions(nextId);
  renderTemplateEditor(nextId);
  configState.textContent = "模板已删除，点击保存设置后生效。";
});

$("quickStoryboardBtn").addEventListener("click", () => {
  switchContentTab("storyboard");
});

$("quickThumbBtn").addEventListener("click", () => {
  switchContentTab("thumb");
});

$("quickHighlightBtn").addEventListener("click", () => {
  switchContentTab("highlight");
});

$("quickPackageBtn").addEventListener("click", () => {
  switchContentTab("package");
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
  switchContentTab("thumb");
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
        const ratioWidth = thumb.displayWidth || thumb.width;
        const ratioHeight = thumb.displayHeight || thumb.height;
        if (ratioWidth && ratioHeight) {
          card.style.setProperty("--thumb-ratio", `${ratioWidth} / ${ratioHeight}`);
        }
        card.innerHTML = `<img src="${thumb.src}" alt=""><time>${clock(thumb.time)}</time>`;
        card.addEventListener("click", () => {
          clips.push({ start: thumb.time, duration: 15, reason: "从缩略图手动添加", role: "local" });
          renderClips();
        });
        thumbGrid.appendChild(card);
      });
      loadHistory();
    });
  } catch (error) {
    thumbGrid.className = "grid empty";
    thumbGrid.textContent = error.message;
  }
});

$("autoBtn").addEventListener("click", async () => {
  switchContentTab("highlight");
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
        role: clip.role,
        score: clip.score,
      }));
      autoSummary.textContent = `${data.summary} 预计成片 ${data.duration}。`;
      renderClips();
      loadHistory();
    });
  } catch (error) {
    autoSummary.textContent = error.message;
  }
});

$("aiAutoBtn").addEventListener("click", async () => {
  switchContentTab("highlight");
  autoSummary.textContent = "正在本地粗筛候选段落，并调用豆包 Seed 2.0 Pro 做剧情高光判断...";
  try {
    await runTask("/api/ai-auto", {
      path: videoPath.value,
      target: Number($("targetSeconds").value),
      requirement: aiRequirement.value.trim(),
    }, (data) => {
      clips = data.clips.map((clip) => ({
        start: clip.start,
        duration: clip.duration,
        reason: clip.reason,
        dialogue: clip.dialogue,
        role: clip.role,
        score: clip.score,
      }));
      autoSummary.textContent = `${data.summary} 预计成片 ${data.duration}。`;
      renderClips();
      loadHistory();
    });
  } catch (error) {
    autoSummary.textContent = error.message;
  }
});

$("addClipBtn").addEventListener("click", () => {
  switchContentTab("highlight");
  clips.push({ start: 0, duration: 15, reason: "手动添加片段", role: "local" });
  renderClips();
});

function rememberOutputDir() {
  if (outputDir.value.trim()) {
    localStorage.setItem(OUTPUT_DIR_KEY, outputDir.value.trim());
  }
}

function packagePayload() {
  return {
    template: packageTemplate.value,
    bgm: packageBgm.checked,
    focusMarks: focusMarks
      .filter((mark) => mark.selected !== false)
      .map((mark) => ({ ...mark, effect: mark.effect || "circle" })),
    stickers: stickers
      .map((item) => ({ path: String(item.path || "").trim(), start: Number(item.start || 0), end: Number(item.end || 0) }))
      .filter((item) => item.path && item.end > item.start),
    bgms: bgms
      .map((item) => ({ path: String(item.path || "").trim(), start: Number(item.start || 0), end: Number(item.end || 0) }))
      .filter((item) => item.path && item.end > item.start),
  };
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
  switchContentTab("highlight");
  exportResult.textContent = "正在导出片段，稍等一下...";
  try {
    const data = await post("/api/export-segments", {
      path: videoPath.value,
      outputDir: outputDir.value,
      clips,
    });
    rememberOutputDir();
    renderSegmentExportResult(data);
    loadHistory();
  } catch (error) {
    exportResult.textContent = error.message;
  }
});

$("exportBtn").addEventListener("click", async () => {
  switchContentTab("highlight");
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
    loadHistory();
  } catch (error) {
    exportResult.textContent = error.message;
  }
});

$("aiFocusBtn").addEventListener("click", async () => {
  switchContentTab("package");
  exportResult.textContent = "正在识别视频重点...";
  try {
    await runTask("/api/ai-focus", {
      path: videoPath.value,
      clips,
      requirement: focusRequirement.value.trim(),
    }, (data) => {
      focusMarks = (data.focusMarks || []).map((mark) => ({ ...mark, selected: true, effect: mark.effect || "circle" }));
      renderFocusMarks();
      exportResult.textContent = data.summary || `已生成 ${focusMarks.length} 个重点标记。`;
      loadHistory();
    });
  } catch (error) {
    exportResult.textContent = error.message;
  }
});

$("storyboardBtn").addEventListener("click", async () => {
  switchContentTab("storyboard");
  storySummary.textContent = "正在分析视频内容并生成分镜脚本...";
  try {
    await runTask("/api/storyboard", {
      path: videoPath.value,
    }, (data) => {
      storyboardShots = data.shots || [];
      renderStoryboard(data.summary || `已生成 ${storyboardShots.length} 个分镜。`);
      loadHistory();
    });
  } catch (error) {
    storySummary.textContent = error.message;
  }
});

$("exportStoryboardBtn").addEventListener("click", async () => {
  switchContentTab("storyboard");
  const summaryToExport = storyboardSummary;
  storySummary.textContent = "正在导出分镜脚本...";
  try {
    const data = await post("/api/export-storyboard", {
      path: videoPath.value,
      summary: summaryToExport,
      shots: storyboardShots,
    });
    rememberOutputDir();
    storySummary.innerHTML = `分镜脚本已导出：<code>${escapeHtml(data.path)}</code>`;
    loadHistory();
  } catch (error) {
    storySummary.textContent = error.message;
  }
});

$("oneClickBtn").addEventListener("click", async () => {
  switchContentTab("package");
  exportResult.textContent = "正在一键成片，正在处理素材...";
  try {
    const data = await post("/api/one-click", {
      path: videoPath.value,
      outputDir: outputDir.value,
      clips,
      package: packagePayload(),
    });
    rememberOutputDir();
    exportResult.innerHTML = `
      <div class="exportStatus">
        <strong>一键成片完成</strong>
        <span>已完成素材处理，并打开所在目录</span>
        <code>${data.path}</code>
        <span>时长：${data.duration}</span>
      </div>
    `;
    loadHistory();
  } catch (error) {
    exportResult.textContent = error.message;
  }
});

renderClips();
renderTimedAssets(stickersList, stickers, "sticker");
renderTimedAssets(bgmList, bgms, "bgm");
renderFocusMarks();
renderStoryboard();
storyboardTabBtn.addEventListener("click", () => switchContentTab("storyboard"));
thumbTabBtn.addEventListener("click", () => switchContentTab("thumb"));
highlightTabBtn.addEventListener("click", () => switchContentTab("highlight"));
packageTabBtn.addEventListener("click", () => switchContentTab("package"));
$("refreshHistoryBtn").addEventListener("click", loadHistory);
(async function init() {
  const config = await loadConfig();
  if (configNeedsSetup(config)) {
    openSettings();
  }
  loadHistory();
})();
