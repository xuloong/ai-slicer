const $ = (id) => document.getElementById(id);

const appShell = $("appShell");
const loginGate = $("loginGate");
const wecomLoginFrame = $("wecomLoginFrame");
const wecomLoginCode = $("wecomLoginCode");
const wecomLoginBtn = $("wecomLoginBtn");
const refreshWecomQrBtn = $("refreshWecomQrBtn");
const openWecomQrBtn = $("openWecomQrBtn");
const pasteWecomCallbackBtn = $("pasteWecomCallbackBtn");
const loginState = $("loginState");
const loginUserInfo = $("loginUserInfo");
const logoutBtn = $("logoutBtn");
const appVersion = $("appVersion");
const settingsVersion = $("settingsVersion");
const checkUpdateBtn = $("checkUpdateBtn");
const installUpdateBtn = $("installUpdateBtn");
const updateState = $("updateState");
const exportDiagnosticsBtn = $("exportDiagnosticsBtn");
const stopLocalServerBtn = $("stopLocalServerBtn");
const whisperModelState = $("whisperModelState");
const downloadWhisperModelBtn = $("downloadWhisperModelBtn");
const clearWhisperModelBtn = $("clearWhisperModelBtn");
const videoPath = $("videoPath");
const shareUrl = $("shareUrl");
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
const storyboardRefsList = $("storyboardRefsList");
const storyboardRefCount = $("storyboardRefCount");
const storyboardRefDescription = $("storyboardRefDescription");
const storyVideoRefsList = $("storyVideoRefsList");
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
const apimartImageSize = $("apimartImageSize");
const apimartImageResolution = $("apimartImageResolution");
const apimartImageQuality = $("apimartImageQuality");
const seedanceDuration = $("seedanceDuration");
const seedanceResolution = $("seedanceResolution");
const seedanceSize = $("seedanceSize");
const seedanceAudio = $("seedanceAudio");
const applyStoryVideoDefaultsBtn = $("applyStoryVideoDefaultsBtn");
const storyboardOutputDir = $("storyboardOutputDir");
const storyboardModelMode = $("storyboardModelMode");
const storyboardCreateRequirement = $("storyboardCreateRequirement");
const storyboardCreateDuration = $("storyboardCreateDuration");
const ffmpegPath = $("ffmpegPath");
const downloadRetentionDays = $("downloadRetentionDays");
const douyinCookie = $("douyinCookie");
const configState = $("configState");
const ffmpegDetected = $("ffmpegDetected");
const settingsModal = $("settingsModal");
const setupHint = $("setupHint");
const mediaModal = $("mediaModal");
const mediaModalTitle = $("mediaModalTitle");
const mediaModalBody = $("mediaModalBody");
const mediaModalDownload = $("mediaModalDownload");
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
storyboardOutputDir.value = localStorage.getItem(OUTPUT_DIR_KEY) || "";

let clips = [];
let currentTaskId = "";
let packageTemplates = {};
let selectedPackageTemplate = "none";
let stickers = [];
let bgms = [];
let focusMarks = [];
let storyboardShots = [];
let storyboardSummary = "";
let storyboardSourceName = "";
let storyboardRefs = [];
let storyVideoRefs = [];
let historyItems = [];
let historyVisibleCount = 10;
let currentWecomQrUrl = "";
let authPollTimer = 0;
let sessionCheckTimer = 0;
let wecomLoginInstance = null;
let autoUpdateChecked = false;
let pendingUpdateVersion = "";

const UPDATE_POLICY = {
  minSupportedVersion: "",
  criticalVersions: [],
};

function isCreativeStoryboardSource() {
  return storyboardSourceName === "创作分镜脚本";
}

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

function localImageSrc(path) {
  return path ? `/local-image?path=${encodeURIComponent(path)}` : "";
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

function openMediaModal({ type = "image", src = "", title = "预览", downloadName = "" } = {}) {
  if (!src) return;
  mediaModalTitle.textContent = title;
  mediaModalBody.innerHTML = type === "video"
    ? `<video src="${escapeHtml(src)}" controls autoplay></video>`
    : `<img src="${escapeHtml(src)}" alt="${escapeHtml(title)}">`;
  if (downloadName) {
    mediaModalDownload.hidden = false;
    mediaModalDownload.href = src;
    mediaModalDownload.download = downloadName;
  } else {
    mediaModalDownload.hidden = true;
    mediaModalDownload.removeAttribute("href");
    mediaModalDownload.removeAttribute("download");
  }
  mediaModal.hidden = false;
}

function closeMediaModal() {
  mediaModal.hidden = true;
  mediaModalBody.innerHTML = "";
}

mediaModal.addEventListener("click", (event) => {
  if (event.target === mediaModal) closeMediaModal();
});

$("closeMediaModalBtn").addEventListener("click", closeMediaModal);

function renderStoryboard(summary = "") {
  storyboardSummary = summary || "";
  storySummary.textContent = summary || "";
  if (!storyboardShots.length) {
    storyboardList.className = "storyboardList empty";
    storyboardList.textContent = "生成后会在这里展示镜号、时间、画面、景别、运镜、字幕和剪辑建议。";
    return;
  }
  storyboardList.className = "storyboardList";
  storyboardList.innerHTML = storyboardShots.map((shot, index) => {
    const editing = Boolean(shot.editing);
    const videoDuration = storyVideoDuration(shot, seedanceDuration.value);
    const videoResolution = normalizeStoryVideoResolution(shot.videoResolution || seedanceResolution.value);
    const videoSize = normalizeStoryVideoSize(shot.videoSize || seedanceSize.value);
    const videoAudio = Boolean(shot.videoAudio ?? (seedanceAudio.checked || seedanceAudio.defaultChecked));
    const hasImage = Boolean(shot.imageSrc);
    const hasVideo = Boolean(shot.videoSrc);
    const imageLoading = Boolean(shot.imageLoading);
    const videoLoading = Boolean(shot.videoLoading);
    const imageDownloadName = `storyboard_shot_${String(index + 1).padStart(2, "0")}.png`;
    const videoDownloadName = `storyboard_shot_${String(index + 1).padStart(2, "0")}.mp4`;
    const timeHtml = editing ? `
        <span class="storyTimeEdit">
          <input class="storyEdit storyTimeInput" data-field="start" type="number" min="0" step="0.1" value="${Number(shot.start || 0)}">
          <em>-</em>
          <input class="storyEdit storyTimeInput" data-field="end" type="number" min="0" step="0.1" value="${Number(shot.end || 0)}">
        </span>
    ` : `<span>${clock(shot.start)} - ${clock(shot.end)}</span>`;
    const editButtons = editing ? `
        <button class="storySaveEditBtn" type="button">保存</button>
        <button class="storyCancelEditBtn" type="button">取消</button>
    ` : `<button class="storyEditBtn" type="button">编辑</button>`;
    const scriptHtml = editing ? `
          <label class="storyField editable"><b>画面</b><textarea class="storyEdit" data-field="scene" rows="2">${escapeHtml(shot.scene || "根据画面内容推进")}</textarea></label>
          <div class="storyMeta editableMeta">
            <label><b>景别</b><input class="storyEdit" data-field="shotType" value="${escapeHtml(shot.shotType || "中景")}"></label>
            <label><b>运镜</b><input class="storyEdit" data-field="camera" value="${escapeHtml(shot.camera || "稳定跟随")}"></label>
          </div>
          <label class="storyField editable"><b>内容</b><textarea class="storyEdit" data-field="action" rows="2">${escapeHtml(shot.action || "展示关键动作或卖点")}</textarea></label>
          <label class="storyField editable"><b>台词</b><textarea class="storyEdit" data-field="dialogue" rows="2">${escapeHtml(shot.dialogue || "")}</textarea></label>
          <label class="storyField editable"><b>字幕</b><textarea class="storyEdit" data-field="caption" rows="2">${escapeHtml(shot.caption || "")}</textarea></label>
          <label class="storyField editable"><b>剪辑建议</b><textarea class="storyEdit" data-field="edit" rows="2">${escapeHtml(shot.edit || "自然衔接到下一镜")}</textarea></label>
    ` : `
          <div class="storyField"><b>画面</b><span>${escapeHtml(shot.scene || "根据画面内容推进")}</span></div>
          <div class="storyMeta">
            <span><b>景别</b>${escapeHtml(shot.shotType || "中景")}</span>
            <span><b>运镜</b>${escapeHtml(shot.camera || "稳定跟随")}</span>
          </div>
          <div class="storyField"><b>内容</b><span>${escapeHtml(shot.action || "展示关键动作或卖点")}</span></div>
          ${shot.dialogue ? `<div class="storyField"><b>台词</b><span>${escapeHtml(shot.dialogue)}</span></div>` : ""}
          ${shot.caption ? `<div class="storyField"><b>字幕</b><span>${escapeHtml(shot.caption)}</span></div>` : ""}
          <div class="storyField"><b>剪辑建议</b><span>${escapeHtml(shot.edit || "自然衔接到下一镜")}</span></div>
    `;
    const imageHtml = imageLoading ? `
      <div class="storyImageColumn storyImageEmpty storyMediaLoading">
        <div class="storyMediaTitle">分镜图</div>
        <div class="storyLoadingBody">
          <span class="spinner"></span>
          <strong>正在生成分镜图...</strong>
        </div>
      </div>
    ` : hasImage ? `
      <div class="storyImageColumn">
        <figure class="storyAsset storyImageAsset">
          <div class="storyMediaTitle">分镜图</div>
          <button class="storyImageOpen" type="button" title="点击放大浏览">
            <img src="${escapeHtml(shot.imageSrc)}" alt="分镜图 ${index + 1}">
          </button>
          <figcaption>
            <button class="storyRegenerateImageBtn" type="button">重生成图</button>
            <a href="${escapeHtml(shot.imageSrc)}" download="${escapeHtml(imageDownloadName)}">下载</a>
          </figcaption>
        </figure>
      </div>
    ` : `
      <div class="storyImageColumn storyImageEmpty">
        <div class="storyMediaTitle">分镜图</div>
        <button class="storyGenerateImageBtn" type="button">生成本镜图</button>
      </div>
    `;
    const videoHtml = videoLoading ? `
      <aside class="storyVideoPreview storyVideoEmpty storyMediaLoading">
        <div class="storyMediaTitle">分镜视频</div>
        <div class="storyLoadingBody">
          <span class="spinner"></span>
          <strong>正在生成分镜视频...</strong>
        </div>
      </aside>
    ` : hasVideo ? `
      <aside class="storyVideoPreview">
        <div class="storyMediaTitle">分镜视频</div>
        <button class="storyVideoOpen" type="button" title="点击放大播放">
          <video src="${escapeHtml(shot.videoSrc)}" muted preload="metadata"></video>
        </button>
        <div class="storyVideoActions">
          <a href="${escapeHtml(shot.videoSrc)}" download="${escapeHtml(videoDownloadName)}">下载</a>
        </div>
      </aside>
    ` : `
      <aside class="storyVideoPreview storyVideoEmpty">
        <div class="storyMediaTitle">分镜视频</div>
        <span>视频生成后显示在这里</span>
      </aside>
    `;
    return `
    <article class="storyShot ${hasImage ? "hasImage" : ""} ${hasVideo ? "hasVideo" : ""} ${editing ? "editing" : ""}">
      <div class="storyShotHead">
        <strong>镜头 ${shot.shot || index + 1}</strong>
        ${timeHtml}
        <span class="storyEditActions">${editButtons}</span>
      </div>
      <div class="storyBody">
        <div class="storyScriptColumn">
          ${scriptHtml}
          <div class="storyVideoControls" data-index="${index}">
            <strong>视频片段</strong>
            <label>
              <span>时长</span>
              <input class="storyVideoDuration" type="number" min="4" max="15" value="${videoDuration}">
              <span>秒</span>
            </label>
            <label>
              <span>清晰度</span>
              <select class="storyVideoResolution">
                <option value="480p" ${videoResolution === "480p" ? "selected" : ""}>480p</option>
                <option value="720p" ${videoResolution === "720p" ? "selected" : ""}>720p</option>
                <option value="1080p" ${videoResolution === "1080p" ? "selected" : ""}>1080p</option>
              </select>
            </label>
            <label>
              <span>比例</span>
              <select class="storyVideoSize">
                <option value="adaptive" ${videoSize === "adaptive" ? "selected" : ""}>自适应</option>
                <option value="9:16" ${videoSize === "9:16" ? "selected" : ""}>9:16</option>
                <option value="16:9" ${videoSize === "16:9" ? "selected" : ""}>16:9</option>
                <option value="1:1" ${videoSize === "1:1" ? "selected" : ""}>1:1</option>
                <option value="3:4" ${videoSize === "3:4" ? "selected" : ""}>3:4</option>
                <option value="4:3" ${videoSize === "4:3" ? "selected" : ""}>4:3</option>
                <option value="21:9" ${videoSize === "21:9" ? "selected" : ""}>21:9</option>
              </select>
            </label>
            <label class="storyVideoAudio">
              <input class="storyVideoAudioInput" type="checkbox" ${videoAudio ? "checked" : ""}>
              <span>声音</span>
            </label>
            <button class="storyGenerateVideoBtn" type="button">生成本镜视频</button>
          </div>
        </div>
        ${imageHtml}
        ${videoHtml}
      </div>
    </article>
  `;
  }).join("");
  bindStoryboardVideoControls();
}

function normalizeStoryVideoDuration(value) {
  const number = Number(value || 5);
  return Math.max(4, Math.min(15, Number.isFinite(number) ? Math.round(number) : 5));
}

function storyShotDuration(shot, fallback = 5) {
  const start = Number(shot?.start);
  const end = Number(shot?.end);
  if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
    return normalizeStoryVideoDuration(end - start);
  }
  return normalizeStoryVideoDuration(shot?.videoDuration ?? fallback);
}

function storyVideoDuration(shot, fallback = 5) {
  if (shot?.videoDurationManual) {
    return normalizeStoryVideoDuration(shot.videoDuration ?? fallback);
  }
  return storyShotDuration(shot, fallback);
}

function normalizeStoryVideoResolution(value) {
  return ["480p", "720p", "1080p"].includes(value) ? value : "720p";
}

function normalizeStoryVideoSize(value) {
  return ["adaptive", "9:16", "16:9", "1:1", "3:4", "4:3", "21:9"].includes(value) ? value : "adaptive";
}

function normalizeImageQuality(value) {
  return ["auto", "low", "medium", "high"].includes(value) ? value : "medium";
}

function cleanStoryboardShot(shot) {
  const { editing, draft, imageLoading, videoLoading, ...rest } = shot || {};
  return rest;
}

function storyboardPayload() {
  return storyboardShots.map(cleanStoryboardShot);
}

function currentStoryVideoDefaults() {
  return {
    videoDuration: normalizeStoryVideoDuration(seedanceDuration.value),
    videoResolution: normalizeStoryVideoResolution(seedanceResolution.value),
    videoSize: normalizeStoryVideoSize(seedanceSize.value),
    videoAudio: Boolean(seedanceAudio.checked),
  };
}

function rememberStoryboardOutputDir() {
  const value = storyboardOutputDir.value.trim();
  if (value) {
    localStorage.setItem(OUTPUT_DIR_KEY, value);
    outputDir.value = value;
  }
}

function bindStoryboardVideoControls() {
  storyboardList.querySelectorAll(".storyEditBtn").forEach((button) => {
    const row = button.closest(".storyShot")?.querySelector(".storyVideoControls");
    const index = Number(row?.dataset.index);
    button.addEventListener("click", () => {
      if (!storyboardShots[index]) return;
      storyboardShots[index].draft = { ...storyboardShots[index] };
      storyboardShots[index].editing = true;
      renderStoryboard(storyboardSummary);
    });
  });
  storyboardList.querySelectorAll(".storySaveEditBtn").forEach((button) => {
    const row = button.closest(".storyShot")?.querySelector(".storyVideoControls");
    const index = Number(row?.dataset.index);
    button.addEventListener("click", () => {
      if (!storyboardShots[index]) return;
      delete storyboardShots[index].draft;
      storyboardShots[index].editing = false;
      renderStoryboard(storyboardSummary);
      storySummary.textContent = `镜头 ${index + 1} 修改已保存。`;
    });
  });
  storyboardList.querySelectorAll(".storyCancelEditBtn").forEach((button) => {
    const row = button.closest(".storyShot")?.querySelector(".storyVideoControls");
    const index = Number(row?.dataset.index);
    button.addEventListener("click", () => {
      if (!storyboardShots[index]) return;
      const draft = storyboardShots[index].draft;
      storyboardShots[index] = draft ? { ...draft, editing: false } : { ...storyboardShots[index], editing: false };
      delete storyboardShots[index].draft;
      renderStoryboard(storyboardSummary);
    });
  });
  storyboardList.querySelectorAll(".storyEdit").forEach((input) => {
    const article = input.closest(".storyShot");
    const row = article?.querySelector(".storyVideoControls");
    const index = Number(row?.dataset.index);
    input.addEventListener("input", () => {
      if (!storyboardShots[index]) return;
      if (["start", "end"].includes(input.dataset.field)) {
        storyboardShots[index][input.dataset.field] = Math.max(0, Number(input.value || 0));
      } else {
        storyboardShots[index][input.dataset.field] = input.value;
      }
    });
  });
  storyboardList.querySelectorAll(".storyVideoControls").forEach((row) => {
    const index = Number(row.dataset.index);
    const durationInput = row.querySelector(".storyVideoDuration");
    const resolutionSelect = row.querySelector(".storyVideoResolution");
    const sizeSelect = row.querySelector(".storyVideoSize");
    const audioInput = row.querySelector(".storyVideoAudioInput");
    const generateButton = row.querySelector(".storyGenerateVideoBtn");
    durationInput.addEventListener("input", () => {
      storyboardShots[index].videoDuration = normalizeStoryVideoDuration(durationInput.value);
      storyboardShots[index].videoDurationManual = true;
    });
    resolutionSelect.addEventListener("change", () => {
      storyboardShots[index].videoResolution = normalizeStoryVideoResolution(resolutionSelect.value);
    });
    sizeSelect.addEventListener("change", () => {
      storyboardShots[index].videoSize = normalizeStoryVideoSize(sizeSelect.value);
    });
    audioInput.addEventListener("change", () => {
      storyboardShots[index].videoAudio = audioInput.checked;
    });
    generateButton.addEventListener("click", () => generateStoryboardVideo(index));
  });
  storyboardList.querySelectorAll(".storyGenerateImageBtn, .storyRegenerateImageBtn").forEach((button) => {
    const article = button.closest(".storyShot");
    const row = article?.querySelector(".storyVideoControls");
    const index = Number(row?.dataset.index);
    button.addEventListener("click", () => generateSingleStoryboardImage(index));
  });
  storyboardList.querySelectorAll(".storyImageOpen").forEach((button) => {
    const article = button.closest(".storyShot");
    const row = article?.querySelector(".storyVideoControls");
    const index = Number(row?.dataset.index);
    button.addEventListener("click", () => {
      const shot = storyboardShots[index];
      openMediaModal({
        type: "image",
        src: shot?.imageSrc,
        title: `镜头 ${index + 1} 分镜图`,
        downloadName: `storyboard_shot_${String(index + 1).padStart(2, "0")}.png`,
      });
    });
  });
  storyboardList.querySelectorAll(".storyVideoOpen").forEach((button) => {
    const article = button.closest(".storyShot");
    const row = article?.querySelector(".storyVideoControls");
    const index = Number(row?.dataset.index);
    button.addEventListener("click", () => {
      const shot = storyboardShots[index];
      openMediaModal({
        type: "video",
        src: shot?.videoSrc,
        title: `镜头 ${index + 1} 分镜视频`,
        downloadName: `storyboard_shot_${String(index + 1).padStart(2, "0")}.mp4`,
      });
    });
  });
}

function renderStoryboardRefs() {
  storyboardRefCount.textContent = `${storyboardRefs.length}/16`;
  if (!storyboardRefs.length) {
    storyboardRefsList.className = "referenceList empty";
    storyboardRefsList.textContent = "";
    return;
  }
  storyboardRefsList.className = "referenceList";
  storyboardRefsList.innerHTML = "";
  storyboardRefs.forEach((ref, index) => {
    const isAiRef = ref.source === "ai" || ref.prompt;
    const editingPrompt = Boolean(ref.editingPrompt);
    const previewSrc = ref.src || localImageSrc(ref.path || "");
    const preview = previewSrc
      ? `<button class="referencePreview" type="button" title="点击放大浏览"><img src="${escapeHtml(previewSrc)}" alt="参考图 ${index + 1}"></button>`
      : `<span class="referencePreview referencePlaceholder"><b>${index + 1}</b></span>`;
    const title = escapeHtml(ref.title || (isAiRef ? "AI参考图" : "用户上传"));
    const path = escapeHtml(ref.path || "");
    const row = document.createElement("div");
    row.className = `referenceItem ${isAiRef ? "aiReferenceItem" : "uploadedReferenceItem"} ${editingPrompt ? "editingPrompt" : ""}`;
    row.innerHTML = `
      <div class="referenceCardHead">
        <strong title="${title}">${title}</strong>
      </div>
      ${preview}
      <div class="referenceCardActions">
        ${isAiRef ? `<button type="button" class="editReferencePrompt" title="${editingPrompt ? "收起提示词" : "修改提示词"}">${editingPrompt ? "收起" : "修改"}</button>` : ""}
        <button type="button" class="removeReference" title="删除">删除</button>
      </div>
      <div class="referenceText">
        ${isAiRef && editingPrompt ? `<textarea class="referencePrompt" rows="3" placeholder="可调整提示词后重新生成">${escapeHtml(ref.prompt || "")}</textarea>` : ""}
        ${!isAiRef ? `<small>用户上传</small><code>${path}</code>` : ""}
      </div>
      ${isAiRef && editingPrompt ? `<button type="button" class="regenerateReference">重新生成</button>` : ""}
    `;
    const previewButton = row.querySelector(".referencePreview");
    if (previewButton) {
      previewButton.addEventListener("click", () => {
        openMediaModal({
          type: "image",
          src: storyboardRefs[index].src || localImageSrc(storyboardRefs[index].path || ""),
          title: storyboardRefs[index].title || `参考图 ${index + 1}`,
          downloadName: `reference_${String(index + 1).padStart(2, "0")}.png`,
        });
      });
    }
    const editButton = row.querySelector(".editReferencePrompt");
    if (editButton) {
      editButton.addEventListener("click", () => {
        storyboardRefs[index].editingPrompt = !storyboardRefs[index].editingPrompt;
        renderStoryboardRefs();
      });
    }
    const promptInput = row.querySelector(".referencePrompt");
    if (promptInput) {
      promptInput.addEventListener("input", () => {
        storyboardRefs[index].prompt = promptInput.value;
      });
    }
    const regenerateButton = row.querySelector(".regenerateReference");
    if (regenerateButton) {
      regenerateButton.addEventListener("click", () => regenerateStoryboardReference(index));
    }
    row.querySelector(".removeReference").addEventListener("click", () => {
      storyboardRefs.splice(index, 1);
      renderStoryboardRefs();
    });
    storyboardRefsList.appendChild(row);
  });
}

function videoRefLabel(type) {
  return { image: "参考图", video: "参考视频", audio: "参考声音" }[type] || "参考素材";
}

function videoRefLimit(type) {
  return type === "image" ? 9 : 3;
}

function renderStoryVideoRefs() {
  if (!storyVideoRefs.length) {
    storyVideoRefsList.className = "videoReferenceList empty";
    storyVideoRefsList.textContent = "可添加参考图、参考视频或参考声音，用于 Seedance2.0 生成分镜视频。";
    return;
  }
  storyVideoRefsList.className = "videoReferenceList";
  storyVideoRefsList.innerHTML = storyVideoRefs.map((ref, index) => `
    <div class="videoReferenceItem">
      <strong>${videoRefLabel(ref.type)}</strong>
      <span>${escapeHtml(ref.title || ref.path || ref.url || "")}</span>
      <button type="button" class="removeVideoReference" data-index="${index}" title="删除">×</button>
    </div>
  `).join("");
  storyVideoRefsList.querySelectorAll(".removeVideoReference").forEach((button) => {
    button.addEventListener("click", () => {
      storyVideoRefs.splice(Number(button.dataset.index), 1);
      renderStoryVideoRefs();
    });
  });
}

function addStoryVideoRef(ref) {
  const count = storyVideoRefs.filter((item) => item.type === ref.type).length;
  if (count >= videoRefLimit(ref.type)) {
    storySummary.textContent = `${videoRefLabel(ref.type)}最多 ${videoRefLimit(ref.type)} 个。`;
    return;
  }
  storyVideoRefs.push(ref);
  renderStoryVideoRefs();
}

function storyVideoReferencesPayload() {
  const merged = storyVideoRefs.map((ref) => ({ ...ref }));
  const seen = new Set(merged.map((ref) => ref.storageUrl || ref.url || ref.path || ref.src).filter(Boolean));
  storyboardRefs.forEach((ref, index) => {
    const storageUrl = ref.storageUrl || ref.imageStorageUrl || "";
    const url = storageUrl || ref.url || ref.imageUrl || "";
    const key = url || ref.path || ref.src;
    if (!key || seen.has(key)) return;
    seen.add(key);
    merged.push({
      type: "image",
      path: ref.path || "",
      url,
      storageUrl,
      storagePath: ref.storagePath || ref.imageStoragePath || "",
      src: ref.src || "",
      title: ref.title || `分镜参考图 ${index + 1}`,
    });
  });
  return merged;
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
    historyItems = (data.items || []).filter((item) => item.action !== "导出分镜脚本");
    historyVisibleCount = 10;
    renderHistory();
  } catch (error) {
    historyList.className = "historyList empty";
    historyList.textContent = error.message;
  }
}

function renderHistory() {
  if (!historyItems.length) {
    historyList.className = "historyList empty";
    historyList.textContent = "暂无历史记录。";
    return;
  }
  const items = historyItems.slice(0, historyVisibleCount);
  historyList.className = "historyList";
  historyList.innerHTML = items.map((item) => `
    <button class="historyItem" type="button" data-id="${item.id}">
      <strong>${displayAction(item.action)}${item.videoName ? ` · ${item.videoName}` : ""}</strong>
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
      if (Array.isArray(item.references)) {
        storyboardRefs = item.references.map((ref) => ({ ...ref, editingPrompt: false })).filter((ref) => ref.path || ref.src || ref.prompt);
        renderStoryboardRefs();
        if (!Array.isArray(item.storyboard) || !item.storyboard.length) {
          storySummary.textContent = item.summary || "历史参考图已载入。";
          switchContentTab("storyboard");
        }
      }
      if (Array.isArray(item.videoReferences)) {
        storyVideoRefs = item.videoReferences.filter((ref) => ref.path || ref.url);
        renderStoryVideoRefs();
      }
      if (Array.isArray(item.storyboard) && item.storyboard.length) {
        storyboardShots = item.storyboard;
        storyboardSourceName = item.sourceName || item.videoName || "历史分镜脚本";
        renderStoryboard(item.summary || "历史分镜脚本已载入。");
        switchContentTab("storyboard");
      }
    });
  });
  if (historyVisibleCount < historyItems.length) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "historyMore";
    more.textContent = `向下滚动加载更多（${historyVisibleCount}/${historyItems.length}）`;
    more.addEventListener("click", () => loadMoreHistory(false));
    historyList.appendChild(more);
  }
}

function loadMoreHistory(keepPosition = true) {
  if (historyVisibleCount >= historyItems.length) return;
  const previousTop = historyList.scrollTop;
  historyVisibleCount = Math.min(historyVisibleCount + 10, historyItems.length);
  renderHistory();
  if (keepPosition) {
    historyList.scrollTop = previousTop;
  }
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

function resetVideoDerivedState() {
  clips = [];
  storyboardShots = [];
  storyboardSummary = "";
  storyboardSourceName = "";
  storyboardRefs = [];
  storyVideoRefs = [];
  stickers = [];
  bgms = [];
  focusMarks = [];

  renderStoryboard();
  renderStoryboardRefs();
  renderStoryVideoRefs();
  renderClips();
  renderTimedAssets(stickersList, stickers, "sticker");
  renderTimedAssets(bgmList, bgms, "bgm");
  renderFocusMarks();

  thumbGrid.className = "grid empty";
  thumbGrid.textContent = "点击“生成缩略图”后在这里选点。";
  autoSummary.textContent = "";
  exportResult.textContent = "";
  focusRequirement.value = "";
  packageBgm.checked = getSelectedTemplate().bgm !== false;

  previewPane.hidden = true;
  previewState.textContent = "";
  clipPreview.pause();
  clipPreview.removeAttribute("src");
  clipPreview.load();
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

async function getJson(url) {
  const result = await fetch(url);
  const json = await result.json();
  if (!result.ok) throw new Error(json.error || "请求失败");
  return json;
}

function showLoginGate(message = "") {
  if (sessionCheckTimer) {
    clearInterval(sessionCheckTimer);
    sessionCheckTimer = 0;
  }
  appShell.hidden = true;
  loginGate.hidden = false;
  loginState.textContent = message || "请使用企业微信扫码登录。";
}

function showAppShell(user = {}) {
  if (authPollTimer) {
    clearInterval(authPollTimer);
    authPollTimer = 0;
  }
  if (sessionCheckTimer) clearInterval(sessionCheckTimer);
  sessionCheckTimer = window.setInterval(async () => {
    try {
      const state = await getJson("/api/auth/status");
      if (!state.loggedIn) {
        showLoginGate("登录已超过 72 小时，请重新扫码登录。");
        await loadWecomQr();
      }
    } catch {
      // Ignore transient status check errors.
    }
  }, 60000);
  loginGate.hidden = true;
  appShell.hidden = false;
  const name = user.username || "企业微信用户";
  const dept = user.deptName || "未填写部门";
  loginUserInfo.textContent = `${name} · ${dept}`;
  configState.textContent = `已登录：${name}（${dept}）`;
}

async function enterAppAfterLogin(user = {}) {
  showAppShell(user);
  const config = await loadConfig();
  if (configNeedsSetup(config)) {
    openSettings();
  }
  await loadHistory();
  scheduleAutoUpdateCheck();
}

function tauriInvoke() {
  const globalInvoke = window.__TAURI__?.core?.invoke || window.__TAURI__?.tauri?.invoke;
  if (globalInvoke) return globalInvoke;
  const internalInvoke = window.__TAURI_INTERNALS__?.invoke;
  if (internalInvoke) return (cmd, args) => internalInvoke(cmd, args);
  return null;
}

function withTimeout(promise, ms, message) {
  let timer = null;
  const timeout = new Promise((_, reject) => {
    timer = window.setTimeout(() => reject(new Error(message)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => {
    if (timer) window.clearTimeout(timer);
  });
}

function parseVersionParts(version) {
  return String(version || "")
    .replace(/^v/i, "")
    .split(/[.-]/)
    .map((part) => Number.parseInt(part, 10))
    .map((value) => (Number.isFinite(value) ? value : 0));
}

function compareVersions(left, right) {
  const a = parseVersionParts(left);
  const b = parseVersionParts(right);
  const length = Math.max(a.length, b.length, 3);
  for (let index = 0; index < length; index += 1) {
    const diff = (a[index] || 0) - (b[index] || 0);
    if (diff !== 0) return diff > 0 ? 1 : -1;
  }
  return 0;
}

function currentAppVersion() {
  const text = appVersion?.textContent || settingsVersion?.textContent || "";
  const match = text.match(/v?(\d+\.\d+\.\d+)/i);
  return match ? match[1] : "";
}

function isForceUpdateVersion(version) {
  const current = currentAppVersion();
  if (UPDATE_POLICY.minSupportedVersion && current && compareVersions(current, UPDATE_POLICY.minSupportedVersion) < 0) {
    return true;
  }
  return UPDATE_POLICY.criticalVersions.includes(String(version || "").replace(/^v/i, ""));
}

function setPendingUpdate(version) {
  pendingUpdateVersion = String(version || "").replace(/^v/i, "");
  if (installUpdateBtn) installUpdateBtn.hidden = !pendingUpdateVersion;
}

async function installPendingUpdate(version = pendingUpdateVersion) {
  const invoke = tauriInvoke();
  if (!invoke) {
    if (updateState) updateState.textContent = "自动更新仅在安装后的客户端中可用。";
    return;
  }
  const targetVersion = String(version || pendingUpdateVersion || "").replace(/^v/i, "");
  if (checkUpdateBtn) checkUpdateBtn.disabled = true;
  if (installUpdateBtn) installUpdateBtn.disabled = true;
  if (updateState) updateState.textContent = targetVersion ? `正在下载并安装 v${targetVersion}...` : "正在下载并安装更新...";
  try {
    const message = await withTimeout(
      invoke("install_update_if_available"),
      300000,
      "下载或安装更新超时，请稍后重试，或手动下载安装包。"
    );
    if (updateState) updateState.textContent = message || "更新已安装，正在重启";
  } catch (error) {
    if (updateState) updateState.textContent = `安装更新失败：${error?.message || error}`;
    if (checkUpdateBtn) checkUpdateBtn.disabled = false;
    if (installUpdateBtn) installUpdateBtn.disabled = false;
  }
}

async function checkForAppUpdate({ silent = false, promptOnFound = false } = {}) {
  const invoke = tauriInvoke();
  if (!invoke) {
    if (!silent && updateState) updateState.textContent = "自动更新仅在安装后的客户端中可用。";
    return;
  }
  if (checkUpdateBtn) checkUpdateBtn.disabled = true;
  if (!silent && updateState) updateState.textContent = "正在检查更新，请稍候...";
  try {
    const version = await withTimeout(
      invoke("check_for_update"),
      30000,
      "检查更新超时，请确认当前网络可以访问 GitHub Release 后重试。"
    );
    if (!version) {
      setPendingUpdate("");
      if (!silent && updateState) updateState.textContent = "当前已是最新版本";
      return;
    }
    setPendingUpdate(version);
    const forceUpdate = isForceUpdateVersion(version);
    if (updateState) updateState.textContent = forceUpdate
      ? `发现关键更新 v${version}，需要更新后继续使用。`
      : `发现新版本 v${version}，可在设置中点击“立即更新”。`;
    if (forceUpdate) {
      window.alert(`发现关键更新 v${version}，需要更新后继续使用。`);
      openSettings();
      return;
    }
    if (promptOnFound) {
      window.setTimeout(() => {
        if (window.confirm(`发现新版本 v${version}，是否现在更新？`)) {
          installPendingUpdate(version);
        }
      }, 100);
    }
  } catch (error) {
    if (!silent && updateState) updateState.textContent = `检查更新失败：${error?.message || error}`;
  } finally {
    if (checkUpdateBtn) checkUpdateBtn.disabled = false;
  }
}

function scheduleAutoUpdateCheck() {
  if (autoUpdateChecked) return;
  autoUpdateChecked = true;
  window.setTimeout(() => {
    checkForAppUpdate({ silent: true, promptOnFound: true });
  }, 2500);
}

async function logoutWecom() {
  logoutBtn.disabled = true;
  try {
    await post("/api/auth/logout", {});
    loginUserInfo.textContent = "未登录";
    configState.textContent = "已退出";
    if (wecomLoginCode) wecomLoginCode.value = "";
    showLoginGate("已退出，请重新扫码登录。");
    await loadWecomQr();
  } catch (error) {
    configState.textContent = error.message;
  } finally {
    logoutBtn.disabled = false;
  }
}

function startAuthPolling() {
  if (authPollTimer) clearInterval(authPollTimer);
  let attempts = 0;
  authPollTimer = window.setInterval(async () => {
    attempts += 1;
    try {
      const state = await getJson("/api/auth/status");
      if (state.loggedIn) {
        await enterAppAfterLogin(state.user || {});
        return;
      }
    } catch {
      // Ignore transient polling errors.
    }
    if (attempts === 12) {
      loginState.textContent = "暂未收到登录结果，请确认手机端已点击确认；如二维码过期，可点击刷新。";
    }
  }, 2000);
}

async function loadWecomQr() {
  try {
    const data = await getJson("/api/auth/qr");
    currentWecomQrUrl = data.url;
    if (wecomLoginInstance?.destroyed) {
      try {
        wecomLoginInstance.destroyed();
      } catch {
        // The official widget cleans up best-effort.
      }
    }
    wecomLoginFrame.innerHTML = "";
    if (window.WwLogin) {
      wecomLoginInstance = new window.WwLogin({
        id: "wecomLoginFrame",
        appid: data.appid,
        agentid: data.agentid,
        redirect_uri: encodeURIComponent(data.redirectUri),
        state: data.state || "video",
        lang: "zh",
      });
    } else {
      wecomLoginFrame.innerHTML = `<iframe title="企业微信扫码登录" src="${escapeHtml(data.url)}"></iframe>`;
    }
    loginState.textContent = "暂未收到登录结果，请确认手机端已点击确认；如二维码过期，可点击刷新。";
    startAuthPolling();
  } catch (error) {
    loginState.textContent = error.message;
  }
}

async function pasteWecomCallback() {
  if (!navigator.clipboard?.readText) {
    loginState.textContent = "当前环境无法直接读取剪贴板，请手动粘贴跳转链接或 code。";
    return;
  }
  try {
    const text = (await navigator.clipboard.readText()).trim();
    if (!text) {
      loginState.textContent = "剪贴板为空，请复制扫码成功后的跳转链接或 code。";
      return;
    }
    wecomLoginCode.value = text;
    loginState.textContent = "已粘贴，请点击完成登录。";
  } catch {
    loginState.textContent = "没有剪贴板读取权限，请手动粘贴跳转链接或 code。";
  }
}

function extractCodeFromText(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  try {
    const url = new URL(text);
    return url.searchParams.get("code") || "";
  } catch {
    const match = text.match(/(?:code=)?([A-Za-z0-9_-]{8,})/);
    return match ? match[1] : text;
  }
}

function isTrustedWecomOrigin(origin) {
  try {
    const hostname = new URL(origin).hostname;
    return hostname === "work.weixin.qq.com" || hostname.endsWith(".work.weixin.qq.com") || hostname === "tencent.com" || hostname.endsWith(".tencent.com");
  } catch {
    return false;
  }
}

async function handleWecomLoginMessage(event) {
  if (!isTrustedWecomOrigin(event.origin) || typeof event.data !== "string") return;
  const code = extractCodeFromText(event.data);
  if (!code) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  if (wecomLoginCode) wecomLoginCode.value = event.data;
  await submitWecomLogin(event.data);
}

async function submitWecomLogin(value) {
  const code = extractCodeFromText(value);
  if (!code) {
    loginState.textContent = "请先粘贴扫码后的跳转链接或 code。";
    return false;
  }
  if (wecomLoginBtn) wecomLoginBtn.disabled = true;
  loginState.textContent = "正在校验企业微信登录...";
  try {
    const state = await post("/api/auth/login", { code });
    await enterAppAfterLogin(state.user || {});
    return true;
  } catch (error) {
    loginState.textContent = error.message;
    return false;
  } finally {
    if (wecomLoginBtn) wecomLoginBtn.disabled = false;
  }
}

async function initAuth() {
  const callbackCode = extractCodeFromText(window.location.href);
  if (callbackCode) {
    showLoginGate("检测到企业微信回调 code，正在自动登录...");
    const loggedIn = await submitWecomLogin(callbackCode);
    if (loggedIn) {
      window.history.replaceState({}, document.title, "/");
      return true;
    }
  }
  try {
    const state = await getJson("/api/auth/status");
    if (state.loggedIn) {
      await enterAppAfterLogin(state.user || {});
      return true;
    }
  } catch {
    // Fall through to login gate.
  }
  showLoginGate("正在准备企业微信二维码...");
  await loadWecomQr();
  return false;
}

async function loadConfig() {
  try {
    const result = await fetch("/api/config");
    const data = await result.json();
    if (!result.ok) throw new Error(data.error || "设置读取失败");
    const versionText = `版本 v${data.version || "0.1.1"}`;
    if (appVersion) appVersion.textContent = versionText;
    if (settingsVersion) settingsVersion.textContent = `当前${versionText}`;
    renderWhisperModelState(data.whisperModel);
    ffmpegPath.value = data.ffmpegPath || "";
    downloadRetentionDays.value = String(data.downloadRetentionDays ?? 30);
    if (douyinCookie) {
      douyinCookie.value = "";
      douyinCookie.placeholder = data.hasDouyinCookie ? `${data.douyinCookieMasked || "已配置抖音 Cookie"}；如需更新请重新粘贴` : "抖音下载失败时粘贴浏览器请求里的 Cookie";
    }
    apimartImageSize.value = data.apimartImageSize || "auto";
    apimartImageResolution.value = data.apimartImageResolution || "1k";
    apimartImageQuality.value = normalizeImageQuality(data.apimartImageQuality || "medium");
    seedanceDuration.value = String(normalizeStoryVideoDuration(data.seedanceDuration ?? 5));
    seedanceResolution.value = normalizeStoryVideoResolution(data.seedanceResolution || "720p");
    seedanceSize.value = normalizeStoryVideoSize(data.seedanceSize || "adaptive");
    seedanceAudio.checked = data.seedanceAudio !== false;
    packageTemplates = normalizeTemplates(data.packageTemplates || FALLBACK_TEMPLATES);
    selectedPackageTemplate = data.packageTemplate || "none";
    renderTemplateOptions(selectedPackageTemplate);
    renderTemplateEditor(packageTemplates[selectedPackageTemplate] ? selectedPackageTemplate : templateEditorSelect.value);
    packageBgm.checked = getSelectedTemplate().bgm !== false;
    configState.textContent = "";
    ffmpegDetected.textContent = data.detectedFfmpegPath ? `检测到 ffmpeg：${data.detectedFfmpegPath}` : "未自动检测到 ffmpeg";
    const missing = [];
    if (!data.detectedFfmpegPath && !data.ffmpegPath) missing.push("ffmpeg 路径");
    if (missing.length) {
      setupHint.hidden = false;
      setupHint.textContent = `首次使用建议先设置：${missing.join("、")}。普通本地识别和导出需要 ffmpeg。`;
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

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!value) return "";
  if (value < 1024 * 1024) return `${Math.round(value / 1024)}KB`;
  if (value < 1024 * 1024 * 1024) return `${Math.round(value / 1024 / 1024)}MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)}GB`;
}

function renderWhisperModelState(state) {
  if (!whisperModelState) return;
  if (!state) {
    whisperModelState.textContent = "模型状态：未读取";
    return;
  }
  const size = formatBytes(state.sizeBytes);
  const suffix = size ? `，${size}` : "";
  whisperModelState.textContent = `模型状态：${state.model || "base"}，${state.source || "未知"}${suffix}`;
  if (downloadWhisperModelBtn) downloadWhisperModelBtn.disabled = Boolean(state.ready);
  if (clearWhisperModelBtn) clearWhisperModelBtn.disabled = !state.cached;
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
  return data && (!data.detectedFfmpegPath && !data.ffmpegPath);
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

checkUpdateBtn?.addEventListener("click", () => {
  checkForAppUpdate({ silent: false });
});

installUpdateBtn?.addEventListener("click", () => {
  installPendingUpdate();
});

exportDiagnosticsBtn?.addEventListener("click", async () => {
  configState.textContent = "正在导出诊断信息...";
  try {
    const data = await post("/api/export-diagnostics", {});
    configState.textContent = `诊断信息已导出：${data.path}`;
  } catch (error) {
    configState.textContent = error.message;
  }
});

stopLocalServerBtn?.addEventListener("click", async () => {
  const invoke = tauriInvoke();
  if (!invoke) {
    configState.textContent = "关闭本地服务仅在安装后的客户端中可用。";
    return;
  }
  const confirmed = window.confirm("关闭本地服务后，当前客户端页面会停止响应。确定要关闭吗？");
  if (!confirmed) return;
  stopLocalServerBtn.disabled = true;
  configState.textContent = "正在关闭本地服务...";
  try {
    const message = await invoke("stop_local_server");
    configState.textContent = message || "本地服务已关闭";
  } catch (error) {
    configState.textContent = `关闭本地服务失败：${error?.message || error}`;
    stopLocalServerBtn.disabled = false;
  }
});

downloadWhisperModelBtn?.addEventListener("click", async () => {
  configState.textContent = "正在下载语音识别模型...";
  try {
    await runTask("/api/whisper/download", {}, (data) => {
      renderWhisperModelState(data);
      configState.textContent = "语音识别模型已准备好";
    });
    await loadConfig();
  } catch (error) {
    configState.textContent = error.message;
  }
});

clearWhisperModelBtn?.addEventListener("click", async () => {
  configState.textContent = "正在清理语音识别模型...";
  try {
    const data = await post("/api/whisper/clear", {});
    renderWhisperModelState(data);
    configState.textContent = "语音识别模型缓存已清理";
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
      downloadRetentionDays: Number(downloadRetentionDays.value || 30),
      seedanceDuration: normalizeStoryVideoDuration(seedanceDuration.value),
      seedanceResolution: normalizeStoryVideoResolution(seedanceResolution.value),
      seedanceSize: normalizeStoryVideoSize(seedanceSize.value),
      seedanceAudio: Boolean(seedanceAudio.checked),
      packageTemplate: packageTemplate.value,
      packageTemplates,
    };
    if (douyinCookie?.value.trim()) {
      payload.douyinCookie = douyinCookie.value.trim();
    }
    await post("/api/config", payload);
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

$("addStoryboardRefBtn").addEventListener("click", () => {
  if (storyboardRefs.length >= 16) {
    storySummary.textContent = "参考图最多 16 张。";
    return;
  }
  storySummary.textContent = "请选择分镜参考图...";
  post("/api/pick-reference-image", {}).then((data) => {
    if (data.path) {
      storyboardRefs.push({
        path: data.path,
        src: data.src || localImageSrc(data.path),
        title: data.path.split(/[\\/]/).pop() || "用户上传",
      });
      renderStoryboardRefs();
      storySummary.textContent = "已添加参考图。可在下方说明每张图是什么。";
    }
  }).catch((error) => {
    storySummary.textContent = error.message;
  });
});

$("generateStoryboardRefsBtn").addEventListener("click", async () => {
  switchContentTab("storyboard");
  if (!storyboardShots.length) {
    storySummary.textContent = "请先生成分镜脚本，再生成 AI 参考图。";
    return;
  }
  if (storyboardRefs.length >= 16) {
    storySummary.textContent = "参考图最多 16 张。";
    return;
  }
  storySummary.textContent = "正在调用 GPT-Image-2 生成参考图...";
  try {
    await runTask("/api/storyboard-reference-images", {
      shots: storyboardPayload(),
      existingCount: storyboardRefs.length,
      existingReferences: storyboardRefs,
      size: apimartImageSize.value || "auto",
      resolution: apimartImageResolution.value || "1k",
      quality: normalizeImageQuality(apimartImageQuality.value),
    }, (data) => {
      const refs = (data.references || []).slice(0, Math.max(0, 16 - storyboardRefs.length));
      storyboardRefs = storyboardRefs.concat(refs);
      renderStoryboardRefs();
      storySummary.textContent = data.summary || `已生成 ${refs.length} 张 AI 参考图。`;
    });
  } catch (error) {
    storySummary.textContent = error.message;
  }
});

async function regenerateStoryboardReference(index) {
  const ref = storyboardRefs[index];
  if (!ref) return;
  const prompt = String(ref.prompt || "").trim();
  if (!prompt) {
    storySummary.textContent = "请先填写参考图提示词。";
    return;
  }
  storySummary.textContent = `正在重新生成参考图 ${index + 1}...`;
  try {
    await runTask("/api/storyboard-reference-image", {
      prompt,
      title: ref.title || `参考图 ${index + 1}`,
      index,
      existingReferences: storyboardRefs,
      size: apimartImageSize.value || "auto",
      resolution: apimartImageResolution.value || "1k",
      quality: normalizeImageQuality(apimartImageQuality.value),
    }, (data) => {
      if (data.reference) {
        storyboardRefs[index] = data.reference;
        renderStoryboardRefs();
      }
      storySummary.textContent = data.summary || `参考图 ${index + 1} 已重新生成。`;
    });
  } catch (error) {
    storySummary.textContent = error.message;
  }
}

$("clearStoryboardRefsBtn").addEventListener("click", () => {
  storyboardRefs = [];
  renderStoryboardRefs();
  storySummary.textContent = "已清空参考图。";
});

$("useGeneratedVideosBtn").addEventListener("click", () => {
  const generated = storyboardShots
    .filter((shot) => shot.videoUrl || shot.videoSrc)
    .slice(0, 3)
    .map((shot, index) => ({
      type: "video",
      url: shot.videoStorageUrl || shot.videoUrl || "",
      storageUrl: shot.videoStorageUrl || "",
      storagePath: shot.videoStoragePath || "",
      src: shot.videoSrc || "",
      path: shot.videoPath || "",
      title: `已生成视频 ${shot.shot || index + 1}`,
    }));
  if (!generated.length) {
    storySummary.textContent = "当前还没有已生成的分镜视频。";
    return;
  }
  generated.forEach(addStoryVideoRef);
  storySummary.textContent = `已添加 ${generated.length} 个已生成视频作为参考。`;
});

$("addStoryVideoRefImageBtn").addEventListener("click", () => {
  post("/api/pick-reference-image", {}).then((data) => {
    if (data.path) {
      addStoryVideoRef({ type: "image", path: data.path, title: data.path.split(/[\\/]/).pop() });
      storySummary.textContent = "已添加视频参考图。";
    }
  }).catch((error) => {
    storySummary.textContent = error.message;
  });
});

$("addStoryVideoRefVideoBtn").addEventListener("click", () => {
  post("/api/pick-reference-video", {}).then((data) => {
    if (data.path) {
      addStoryVideoRef({ type: "video", path: data.path, title: data.path.split(/[\\/]/).pop() });
      storySummary.textContent = "已添加参考视频。";
    }
  }).catch((error) => {
    storySummary.textContent = error.message;
  });
});

$("addStoryVideoRefAudioBtn").addEventListener("click", () => {
  post("/api/pick-reference-audio", {}).then((data) => {
    if (data.path) {
      addStoryVideoRef({ type: "audio", path: data.path, title: data.path.split(/[\\/]/).pop() });
      storySummary.textContent = "已添加参考声音。";
    }
  }).catch((error) => {
    storySummary.textContent = error.message;
  });
});

$("clearStoryVideoRefsBtn").addEventListener("click", () => {
  storyVideoRefs = [];
  renderStoryVideoRefs();
  storySummary.textContent = "已清空视频参考素材。";
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
    resetVideoDerivedState();
    videoPath.value = data.path;
    await probeVideo();
  } catch (error) {
    info.textContent = error.message;
  }
});

$("openDownloadsBtn").addEventListener("click", async () => {
  try {
    const data = await post("/api/open-downloads", {});
    info.textContent = `下载目录：${data.path}`;
  } catch (error) {
    info.textContent = error.message;
  }
});

shareUrl.addEventListener("focus", async () => {
  if (shareUrl.value.trim() || !navigator.clipboard?.readText) return;
  try {
    const text = (await navigator.clipboard.readText()).trim();
    if (/https?:\/\//.test(text)) {
      shareUrl.value = text;
    }
  } catch {
    // Clipboard permission may be unavailable in some desktop webviews.
  }
});

$("downloadShareBtn").addEventListener("click", async () => {
  const value = shareUrl.value.trim();
  if (!value) {
    info.textContent = "请先粘贴抖音或小红书分享链接。";
    return;
  }
  info.textContent = "正在准备下载分享视频...";
  try {
    await runTask("/api/download-link", { url: value }, async (data) => {
      resetVideoDerivedState();
      videoPath.value = data.path;
      info.textContent = `下载完成：${data.title || data.path}`;
      await probeVideo();
      loadHistory();
    });
  } catch (error) {
    info.textContent = error.message;
  }
});

$("pickDirBtn").addEventListener("click", async () => {
  exportResult.textContent = "请选择导出目录...";
  try {
    const data = await post("/api/pick-dir", {});
    outputDir.value = data.path;
    storyboardOutputDir.value = data.path;
    localStorage.setItem(OUTPUT_DIR_KEY, data.path);
    exportResult.textContent = `导出目录：${data.path}`;
  } catch (error) {
    exportResult.textContent = error.message;
  }
});

outputDir.addEventListener("change", () => {
  const value = outputDir.value.trim();
  if (value) {
    localStorage.setItem(OUTPUT_DIR_KEY, value);
    storyboardOutputDir.value = value;
  }
});

historyList.addEventListener("scroll", () => {
  if (historyList.classList.contains("empty")) return;
  if (historyVisibleCount >= historyItems.length) return;
  const nearBottom = historyList.scrollTop + historyList.clientHeight >= historyList.scrollHeight - 80;
  if (nearBottom) loadMoreHistory();
});

historyList.addEventListener("wheel", (event) => {
  if (event.deltaY <= 0) return;
  if (historyList.classList.contains("empty")) return;
  if (historyVisibleCount >= historyItems.length) return;
  const nearBottom = historyList.scrollTop + historyList.clientHeight >= historyList.scrollHeight - 120;
  if (nearBottom) loadMoreHistory();
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
  autoSummary.textContent = "正在本地粗筛候选段落，并调用豆包模型做剧情高光判断...";
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
      modelMode: storyboardModelMode ? storyboardModelMode.value : "fast",
    }, (data) => {
      storyboardShots = data.shots || [];
      storyboardSourceName = videoPath.value ? "" : "视频分镜脚本";
      renderStoryboard(data.summary || `已生成 ${storyboardShots.length} 个分镜。`);
      loadHistory();
    });
  } catch (error) {
    storySummary.textContent = error.message;
  }
});

$("storyboardCreateBtn").addEventListener("click", async () => {
  switchContentTab("storyboard");
  const requirement = storyboardCreateRequirement.value.trim();
  const duration = Math.max(10, Math.min(180, Number(storyboardCreateDuration.value || 60)));
  if (!requirement) {
    storySummary.textContent = "请先输入短视频创作要求。";
    storyboardCreateRequirement.focus();
    return;
  }
  storySummary.textContent = "正在根据创作要求生成分镜脚本...";
  try {
    await runTask("/api/storyboard-create", {
      requirement,
      duration,
      modelMode: storyboardModelMode ? storyboardModelMode.value : "fast",
    }, (data) => {
      storyboardShots = data.shots || [];
      storyboardSourceName = data.sourceName || "创作分镜脚本";
      renderStoryboard(data.summary || `已创作 ${storyboardShots.length} 个分镜。`);
      loadHistory();
    });
  } catch (error) {
    storySummary.textContent = error.message;
  }
});

$("storyboardImagesBtn").addEventListener("click", async () => {
  switchContentTab("storyboard");
  if (!storyboardShots.length) {
    storySummary.textContent = "请先生成分镜脚本，再生成分镜图。";
    return;
  }
  storySummary.textContent = "正在调用 GPT-Image-2 生成分镜图...";
  storyboardShots = storyboardShots.map((shot) => ({ ...shot, imageLoading: true }));
  renderStoryboard(storyboardSummary);
  try {
    await runTask("/api/storyboard-images", {
      shots: storyboardPayload(),
      allShots: storyboardPayload(),
      references: storyboardRefs.filter((ref) => ref.path && ref.path.trim()).slice(0, 16),
      referenceDescription: storyboardRefDescription.value.trim(),
      size: apimartImageSize.value || "auto",
      resolution: apimartImageResolution.value || "1k",
      quality: normalizeImageQuality(apimartImageQuality.value),
    }, (data) => {
      storyboardShots = data.shots || storyboardShots;
      renderStoryboard(data.summary || `已生成 ${storyboardShots.length} 张分镜图。`);
      loadHistory();
    });
  } catch (error) {
    storyboardShots = storyboardShots.map((shot) => ({ ...shot, imageLoading: false }));
    renderStoryboard(storyboardSummary);
    storySummary.textContent = error.message;
  }
});

async function generateSingleStoryboardImage(index) {
  switchContentTab("storyboard");
  const shot = storyboardShots[index];
  if (!shot) {
    storySummary.textContent = "请选择要生成分镜图的镜头。";
    return;
  }
  storySummary.textContent = `正在调用 GPT-Image-2 生成镜头 ${index + 1} 的分镜图...`;
  storyboardShots[index] = { ...storyboardShots[index], imageLoading: true };
  renderStoryboard(storyboardSummary);
  try {
    await runTask("/api/storyboard-images", {
      shots: [cleanStoryboardShot(shot)],
      allShots: storyboardPayload(),
      index,
      references: storyboardRefs.filter((ref) => ref.path && ref.path.trim()).slice(0, 16),
      referenceDescription: storyboardRefDescription.value.trim(),
      size: apimartImageSize.value || "auto",
      resolution: apimartImageResolution.value || "1k",
      quality: normalizeImageQuality(apimartImageQuality.value),
    }, (data) => {
      const nextShot = (data.shots || [])[0];
      if (nextShot) {
        storyboardShots[index] = {
          ...storyboardShots[index],
          imageLoading: false,
          imageUrl: nextShot.imageUrl,
          imageTaskId: nextShot.imageTaskId,
          imagePath: nextShot.imagePath,
          imageSrc: nextShot.imageSrc,
        };
      } else if (storyboardShots[index]) {
        storyboardShots[index] = { ...storyboardShots[index], imageLoading: false };
      }
      renderStoryboard(`镜头 ${index + 1} 分镜图已生成。`);
      loadHistory();
    });
  } catch (error) {
    if (storyboardShots[index]) {
      storyboardShots[index] = { ...storyboardShots[index], imageLoading: false };
      renderStoryboard(storyboardSummary);
    }
    storySummary.textContent = error.message;
  }
}

async function generateStoryboardVideo(index) {
  switchContentTab("storyboard");
  const shot = storyboardShots[index];
  if (!shot) {
    storySummary.textContent = "请选择要生成的视频镜头。";
    return;
  }
  const defaults = currentStoryVideoDefaults();
  const payloadShot = {
    ...shot,
    videoDuration: storyVideoDuration(shot, defaults.videoDuration),
    videoResolution: normalizeStoryVideoResolution(shot.videoResolution || defaults.videoResolution),
    videoSize: normalizeStoryVideoSize(shot.videoSize || defaults.videoSize),
    videoAudio: Boolean(shot.videoAudio ?? defaults.videoAudio),
  };
  storyboardShots[index] = { ...payloadShot, videoLoading: true };
  renderStoryboard(storyboardSummary);
  storySummary.textContent = `正在生成镜头 ${index + 1} 的视频片段...`;
  try {
    await runTask("/api/storyboard-video", {
      shot: cleanStoryboardShot(payloadShot),
      allShots: storyboardPayload(),
      index,
      references: storyVideoReferencesPayload(),
      ...defaults,
      videoDuration: payloadShot.videoDuration,
      videoResolution: payloadShot.videoResolution,
      videoSize: payloadShot.videoSize,
      videoAudio: payloadShot.videoAudio,
    }, (data) => {
      const nextShot = data.shot || (data.shots || [])[0];
      if (nextShot) {
        storyboardShots[index] = { ...nextShot, videoLoading: false };
      } else if (storyboardShots[index]) {
        storyboardShots[index] = { ...storyboardShots[index], videoLoading: false };
      }
      renderStoryboard(data.summary || `镜头 ${index + 1} 视频片段已生成。`);
      loadHistory();
    });
  } catch (error) {
    if (storyboardShots[index]) {
      storyboardShots[index] = { ...storyboardShots[index], videoLoading: false };
      renderStoryboard(storyboardSummary);
    }
    storySummary.textContent = error.message;
  }
}

applyStoryVideoDefaultsBtn.addEventListener("click", () => {
  const defaults = currentStoryVideoDefaults();
  storyboardShots = storyboardShots.map((shot) => ({
    ...shot,
    videoResolution: defaults.videoResolution,
    videoSize: defaults.videoSize,
    videoAudio: defaults.videoAudio,
  }));
  renderStoryboard(storyboardSummary || (storyboardShots.length ? "已应用视频生成参数。" : ""));
});

$("saveStoryboardEditsBtn").addEventListener("click", () => {
  switchContentTab("storyboard");
  const summary = storyboardSummary;
  storyboardShots = storyboardShots.map((shot) => {
    const clean = cleanStoryboardShot(shot);
    clean.editing = false;
    return clean;
  });
  renderStoryboard(summary);
  storySummary.textContent = storyboardShots.length ? "分镜修改已保存到当前任务，导出分镜会使用修改后的内容。" : "暂无可保存的分镜。";
});

$("pickStoryboardDirBtn").addEventListener("click", async () => {
  switchContentTab("storyboard");
  storySummary.textContent = "请选择分镜视频导出目录...";
  try {
    const data = await post("/api/pick-dir", {});
    storyboardOutputDir.value = data.path;
    rememberStoryboardOutputDir();
    storySummary.textContent = `导出目录：${data.path}`;
  } catch (error) {
    storySummary.textContent = error.message;
  }
});

storyboardOutputDir.addEventListener("change", rememberStoryboardOutputDir);

$("mergeStoryboardVideosBtn").addEventListener("click", async () => {
  switchContentTab("storyboard");
  storySummary.textContent = "正在合并分镜视频...";
  try {
    const data = await post("/api/storyboard-merge-videos", {
      path: isCreativeStoryboardSource() ? "" : videoPath.value,
      outputDir: storyboardOutputDir.value,
      shots: storyboardPayload(),
      sourceName: storyboardSourceName || "创作分镜脚本",
    });
    rememberStoryboardOutputDir();
    storySummary.innerHTML = `合并完成：<code>${escapeHtml(data.path)}</code>`;
    loadHistory();
  } catch (error) {
    storySummary.textContent = error.message;
  }
});

$("exportStoryboardVideosBtn").addEventListener("click", async () => {
  switchContentTab("storyboard");
  storySummary.textContent = "正在导出分镜视频...";
  try {
    const data = await post("/api/storyboard-export-videos", {
      path: isCreativeStoryboardSource() ? "" : videoPath.value,
      outputDir: storyboardOutputDir.value,
      shots: storyboardPayload(),
      sourceName: storyboardSourceName || "创作分镜脚本",
    });
    rememberStoryboardOutputDir();
    storySummary.innerHTML = `已导出 ${data.count} 个分镜视频：<code>${escapeHtml(data.outputDir)}</code>`;
    loadHistory();
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
      path: isCreativeStoryboardSource() ? "" : videoPath.value,
      summary: summaryToExport,
      shots: storyboardPayload(),
      sourceName: storyboardSourceName || "创作分镜脚本",
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
renderStoryboardRefs();
renderStoryVideoRefs();
storyboardTabBtn.addEventListener("click", () => switchContentTab("storyboard"));
thumbTabBtn.addEventListener("click", () => switchContentTab("thumb"));
highlightTabBtn.addEventListener("click", () => switchContentTab("highlight"));
packageTabBtn.addEventListener("click", () => switchContentTab("package"));
$("refreshHistoryBtn").addEventListener("click", loadHistory);
refreshWecomQrBtn?.addEventListener("click", loadWecomQr);
openWecomQrBtn?.addEventListener("click", () => {
  if (!currentWecomQrUrl) {
    loadWecomQr();
    return;
  }
  window.open(currentWecomQrUrl, "_blank", "noopener,noreferrer");
  loginState.textContent = "已打开外部扫码页。手机确认后，请复制扫码页最终跳转地址栏里的链接或 code，回到这里粘贴并完成登录。";
});
pasteWecomCallbackBtn?.addEventListener("click", pasteWecomCallback);
logoutBtn.addEventListener("click", logoutWecom);
wecomLoginBtn?.addEventListener("click", async () => {
  await submitWecomLogin(wecomLoginCode.value);
});
wecomLoginCode?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    wecomLoginBtn.click();
  }
});
window.addEventListener("message", handleWecomLoginMessage, true);
(async function init() {
  const loggedIn = await initAuth();
  if (!loggedIn) return;
})();
