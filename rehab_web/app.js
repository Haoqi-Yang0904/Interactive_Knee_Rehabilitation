const LANDMARK = {
  NOSE: 0,
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
  LEFT_ELBOW: 13,
  RIGHT_ELBOW: 14,
  LEFT_WRIST: 15,
  RIGHT_WRIST: 16,
  LEFT_HIP: 23,
  RIGHT_HIP: 24,
  LEFT_KNEE: 25,
  RIGHT_KNEE: 26,
  LEFT_ANKLE: 27,
  RIGHT_ANKLE: 28,
  LEFT_HEEL: 29,
  RIGHT_HEEL: 30,
  LEFT_FOOT_INDEX: 31,
  RIGHT_FOOT_INDEX: 32,
};

const CONFIG = {
  targetAngle: 120,
  holdGoalSeconds: 6,
  holdStartSeconds: 2,
  sideViewMaxTorsoWidthRatio: 0.55,
  visibilityThreshold: 0.2,
  frameMargin: 0.05,
  angleStableWindowSeconds: 0.7,
  angleStableRangeDegrees: 6,
  legSwitchConfirmFrames: 6,
  legSwitchScoreMargin: 0.35,
  distalSwitchConfirmFrames: 4,
  distalLockBonus: 0.18,
  pointSmoothingAlpha: 0.35,
  pointSmoothingMaxStep: 0.045,
  angleSmoothingAlpha: 0.3,
  voiceCooldownMs: 7000,
  preferredVideoWidth: 1280,
  preferredVideoHeight: 720,
};

const SHOULDER_CONFIG = {
  holdGoalSeconds: 6,
  holdStartSeconds: 2,
  frontViewMinTorsoWidthRatio: 0.28,
  sideViewMaxTorsoWidthRatio: 0.55,
  trunkLeanMaxDegrees: 10,
  sideTrunkLeanMaxDegrees: 12,
  elbowStraightMinAngle: 150,
  armBentCheckStartAngle: 20,
  externalRotationElbowTarget: 90,
  externalRotationElbowTolerance: 20,
  externalRotationUpperArmMaxAngle: 25,
  planeDeviationMax: 0.34,
  armSwitchConfirmFrames: 6,
  armSwitchScoreMargin: 0.35,
};

const FEEDBACK_MESSAGES = {
  start: [
    "膝关节训练已经开始，请侧身站稳，把双肩到脚放进镜头里。",
  ],
  far: [
    "挺好的，咱们慢慢来。先把身体放稳，膝盖再往里弯一点。",
    "动作开始了，慢慢弯，不用着急。",
  ],
  mid: [
    "不错，离目标近了。身体稳住，膝盖再慢慢弯一点。",
    "很好，再来一点点，别憋气。",
  ],
  close: [
    "快到了，就差一点。别猛用力，再轻轻弯一点。",
    "已经很接近了，保持身体稳定。",
  ],
  near: [
    "就差一点点了，再慢慢弯一点点就够了。",
    "非常接近目标，稳住再收一点点。",
  ],
  target: [
    "很好，已经到一百二十度了。先别放下，稳住，慢慢呼吸。",
  ],
  hold: [
    "保持得很好，再坚持一下。",
    "很好，继续稳住，慢慢呼吸。",
  ],
  rest: [
    "保持完成了，可以慢慢放下休息。",
  ],
  adjust_view: [
    "请把身体转成侧身，再继续训练。",
  ],
  low_visibility: [
    "我现在看这条腿不太清楚，请把双肩到脚都放进镜头里。",
  ],
};

const SHOULDER_EXERCISES = {
  forward_flexion: {
    name: "肩关节前屈",
    shortName: "前屈",
    view: "side",
    targetAngle: 120,
    holdGoalSeconds: SHOULDER_CONFIG.holdGoalSeconds,
    primaryLabel: "前屈角度",
    startPrompt: "肩关节前屈训练已经开始，请侧身站稳，把双肩到手腕放进镜头里。",
    movementHint: "手臂保持伸直，从身体正前方慢慢向上抬起。",
    planeHint: "手臂尽量沿身体前方抬起，不要往侧面偏。",
    cameraMaskTitle: "请侧身完成肩前屈",
    guide: [
      "身体侧身对着镜头，肩线不要正对摄像头。",
      "画面至少拍到双肩到手腕，建议胸口到手都在镜头里。",
      "手臂尽量伸直，从身体前方慢慢向上抬。",
      "如果角度不稳，先把上半身站稳再抬手。",
    ],
  },
  abduction: {
    name: "肩关节外展",
    shortName: "外展",
    view: "front",
    targetAngle: 90,
    holdGoalSeconds: SHOULDER_CONFIG.holdGoalSeconds,
    primaryLabel: "外展角度",
    startPrompt: "肩关节外展训练已经开始，请正面对着镜头，把双肩到手腕放进镜头里。",
    movementHint: "手臂保持伸直，从身体侧方向上抬起。",
    planeHint: "手臂尽量从身体侧方向上抬，不要往身体前方跑。",
    cameraMaskTitle: "请正面完成肩外展",
    guide: [
      "正面对着镜头站立，双肩尽量摆平。",
      "画面至少拍到双肩到手腕，最好上半身完整可见。",
      "手臂从身体侧方向上抬起，不要变成往前举。",
      "保持躯干直立，避免歪身子代偿。",
    ],
  },
  external_rotation: {
    name: "中立位外旋",
    shortName: "外旋",
    view: "front",
    targetAngle: 30,
    holdGoalSeconds: SHOULDER_CONFIG.holdGoalSeconds,
    primaryLabel: "外旋角度",
    startPrompt: "肩关节外旋训练已经开始，请正面对着镜头，大臂贴身，肘关节大约九十度。",
    movementHint: "大臂贴住躯干，肘关节约九十度，前臂向外打开。",
    planeHint: "大臂别抬起来，保持贴身，只让前臂向外旋开。",
    cameraMaskTitle: "请正面完成肩外旋",
    guide: [
      "正面对着镜头站，双肩摆正，不要侧身。",
      "大臂贴住身体，肘关节弯成大约 90°。",
      "以前臂为主向身体外侧打开，不要整只手臂一起抬起。",
      "如果 45° 太难，这里先以 30° 作为网页默认目标更贴近家庭训练。",
    ],
  },
  extension: {
    name: "肩关节后伸",
    shortName: "后伸",
    view: "side",
    targetAngle: 30,
    holdGoalSeconds: SHOULDER_CONFIG.holdGoalSeconds,
    primaryLabel: "后伸角度",
    startPrompt: "肩关节后伸训练已经开始，请侧身站稳，把双肩到手腕放进镜头里。",
    movementHint: "手臂保持伸直，沿身体一侧慢慢向身后带。",
    planeHint: "手臂沿身体侧面向后抬，不要往前或往外偏。",
    cameraMaskTitle: "请侧身完成肩后伸",
    guide: [
      "身体侧身对着镜头，肩线不要正对摄像头。",
      "画面至少拍到双肩到手腕，建议上半身都进镜头。",
      "手臂伸直，沿身体侧面慢慢向身后带。",
      "躯干不要前倾，避免用身体代替肩关节。",
    ],
  },
};

const SHOULDER_EXERCISE_ORDER = [
  "forward_flexion",
  "abduction",
  "external_rotation",
  "extension",
];

const TRACKED_LEG_LANDMARKS = {
  left: {
    hip: LANDMARK.LEFT_HIP,
    knee: LANDMARK.LEFT_KNEE,
    distal: [
      ["ankle", LANDMARK.LEFT_ANKLE],
      ["heel", LANDMARK.LEFT_HEEL],
      ["foot_index", LANDMARK.LEFT_FOOT_INDEX],
    ],
  },
  right: {
    hip: LANDMARK.RIGHT_HIP,
    knee: LANDMARK.RIGHT_KNEE,
    distal: [
      ["ankle", LANDMARK.RIGHT_ANKLE],
      ["heel", LANDMARK.RIGHT_HEEL],
      ["foot_index", LANDMARK.RIGHT_FOOT_INDEX],
    ],
  },
};

const TRACKED_ARM_LANDMARKS = {
  left: {
    hip: LANDMARK.LEFT_HIP,
    shoulder: LANDMARK.LEFT_SHOULDER,
    elbow: LANDMARK.LEFT_ELBOW,
    wrist: LANDMARK.LEFT_WRIST,
  },
  right: {
    hip: LANDMARK.RIGHT_HIP,
    shoulder: LANDMARK.RIGHT_SHOULDER,
    elbow: LANDMARK.RIGHT_ELBOW,
    wrist: LANDMARK.RIGHT_WRIST,
  },
};

const DISTAL_PRIORITY_BONUS = {
  ankle: 0.22,
  heel: 0.1,
  foot_index: 0,
};

const state = {
  currentModule: "knee",
  currentShoulderExercise: "forward_flexion",
  pose: null,
  stream: null,
  animationFrameId: null,
  processingFrame: false,
  cameraStarted: false,
  voicesReady: false,
  lastVoiceTime: 0,
  lastFeedbackStage: null,
  targetReachedAt: null,
  angleHistory: [],
  bestAngle: 0,
  completedReps: 0,
  repCounted: false,
  selectedCameraId: "",
  tracking: {
    lockedLeg: null,
    legCandidate: null,
    legCandidateFrames: 0,
    lockedArm: null,
    armCandidate: null,
    armCandidateFrames: 0,
    lockedDistalPart: null,
    distalCandidate: null,
    distalCandidateFrames: 0,
    smoothedPoints: {
      hip: null,
      knee: null,
      distal: null,
      shoulder: null,
      elbow: null,
      wrist: null,
    },
    smoothedAngle: null,
  },
};

const elements = {
  workspaceTitle: document.getElementById("workspaceTitle"),
  workspaceSubtitle: document.getElementById("workspaceSubtitle"),
  moduleBadge: document.getElementById("moduleBadge"),
  moduleSummary: document.getElementById("moduleSummary"),
  angleValue: document.getElementById("angleValue"),
  targetValue: document.getElementById("targetValue"),
  holdValue: document.getElementById("holdValue"),
  stabilityValue: document.getElementById("stabilityValue"),
  holdProgressBar: document.getElementById("holdProgressBar"),
  progressCaption: document.getElementById("progressCaption"),
  cameraSelect: document.getElementById("cameraSelect"),
  refreshDevicesButton: document.getElementById("refreshDevicesButton"),
  startButton: document.getElementById("startButton"),
  stopButton: document.getElementById("stopButton"),
  voiceToggle: document.getElementById("voiceToggle"),
  statusHeadline: document.getElementById("statusHeadline"),
  statusText: document.getElementById("statusText"),
  repCounter: document.getElementById("repCounter"),
  sessionLog: document.getElementById("sessionLog"),
  guideList: document.getElementById("guideList"),
  cameraState: document.getElementById("cameraState"),
  trackingState: document.getElementById("trackingState"),
  bestAngleValue: document.getElementById("bestAngleValue"),
  feedbackStageValue: document.getElementById("feedbackStageValue"),
  shoulderExerciseField: document.getElementById("shoulderExerciseField"),
  shoulderExerciseSelect: document.getElementById("shoulderExerciseSelect"),
  cameraMaskTitle: document.getElementById("cameraMaskTitle"),
  recognitionModeValue: document.getElementById("recognitionModeValue"),
  video: document.getElementById("cameraVideo"),
  canvas: document.getElementById("cameraCanvas"),
};

const ctx = elements.canvas.getContext("2d");

document.addEventListener("DOMContentLoaded", () => {
  populateShoulderExerciseOptions();
  bindModuleCards();
  bindControls();
  refreshCameraDevices();
  updateModuleUI("knee");
  pushSessionLog("网页训练工作台已就绪，可以先从膝关节训练开始。");
});

function bindModuleCards() {
  document.querySelectorAll("[data-module]").forEach((card) => {
    card.addEventListener("click", async () => {
      const moduleKey = card.dataset.module;
      const status = card.dataset.status;
      if (status !== "active") {
        setStatus(
          "模块正在规划中",
          `${getModuleDisplayName(moduleKey)}模块已预留入口，后面你可以继续接入对应角度检测。`,
          "规划中"
        );
        document.getElementById("workspace").scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }

      await activateModule(moduleKey, { autoStart: true });
    });
  });

  document.querySelectorAll("[data-module-jump]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      await activateModule(button.dataset.moduleJump, { autoStart: true });
    });
  });
}

function bindControls() {
  elements.refreshDevicesButton.addEventListener("click", refreshCameraDevices);
  elements.startButton.addEventListener("click", startCurrentTraining);
  elements.stopButton.addEventListener("click", stopTraining);
  elements.cameraSelect.addEventListener("change", (event) => {
    state.selectedCameraId = event.target.value;
  });
  elements.shoulderExerciseSelect.addEventListener("change", () => {
    state.currentShoulderExercise = elements.shoulderExerciseSelect.value;
    if (state.currentModule === "shoulder") {
      updateModuleUI("shoulder");
      resetTrainingSession(false);
      pushSessionLog(`已切换肩关节动作：${getCurrentShoulderExerciseProfile().name}。`);
      setStatus(
        "肩关节动作已切换",
        "可以直接开始新的动作训练；如果摄像头已经开启，系统会立刻按新动作重新评估。",
        "动作已切换"
      );
    }
  });
}

function updateModuleUI(moduleKey) {
  state.currentModule = moduleKey;
  const activeCards = document.querySelectorAll('.module-card[data-status="active"]');
  activeCards.forEach((card) => {
    card.classList.toggle("module-card-active", card.dataset.module === moduleKey);
  });

  if (!state.cameraStarted) {
    state.bestAngle = 0;
    state.completedReps = 0;
    elements.repCounter.textContent = "完成次数：0";
    setMetricDefaults();
  }

  if (moduleKey === "knee") {
    elements.shoulderExerciseField.classList.add("is-hidden");
    elements.workspaceTitle.textContent = "膝关节屈曲康复训练";
    elements.workspaceSubtitle.textContent =
      "患者打开网页后点击模块即可开始训练，系统会在浏览器里实时计算屈膝角度与保持时间。";
    elements.moduleBadge.textContent = "膝关节训练";
    elements.moduleSummary.textContent =
      "当前版本采用浏览器摄像头实时识别髋、膝、踝关键点，帮助患者完成屈膝动作训练。";
    elements.targetValue.textContent = `${CONFIG.targetAngle}°`;
    elements.cameraMaskTitle.textContent = "请将身体侧身放入取景框";
    elements.recognitionModeValue.textContent = "膝关节 · 单人实时训练";
    renderGuideItems([
      "站成腿部侧面对着镜头，别斜站。",
      "画面最好拍到双肩到脚，至少保证髋、膝、脚踝完整可见。",
      "推荐距离大约 1.8 到 2.4 米，人物占画面高度约 65% 到 80%。",
      "镜头高度放在膝到髋之间，更利于角度判断。",
    ]);
    setStatus(
      "膝关节模块已选中",
      "可以先调整拍摄位置，再点击“启动摄像头”开始训练。",
      "等待训练"
    );
    return;
  }

  if (moduleKey === "shoulder") {
    const profile = getCurrentShoulderExerciseProfile();
    elements.shoulderExerciseField.classList.remove("is-hidden");
    elements.shoulderExerciseSelect.value = state.currentShoulderExercise;
    elements.workspaceTitle.textContent = "肩关节康复训练";
    elements.workspaceSubtitle.textContent =
      "网页端已经接入肩关节多动作训练，患者可直接在浏览器里选择前屈、外展、外旋、后伸并开始训练。";
    elements.moduleBadge.textContent = "肩关节训练";
    elements.moduleSummary.textContent =
      `当前选择：${profile.name}。系统会实时计算角度，并检查肘伸直、大臂贴身、动作平面和达标保持时间。`;
    elements.targetValue.textContent = `${profile.targetAngle}°`;
    elements.cameraMaskTitle.textContent = profile.cameraMaskTitle;
    elements.recognitionModeValue.textContent = `肩关节 · ${profile.shortName} · 单人实时训练`;
    renderGuideItems(profile.guide);
    setStatus(
      `${profile.name}已选中`,
      "先确认拍摄方向和动作要求，再点击“启动摄像头”开始训练。",
      "等待训练"
    );
  }
}

function populateShoulderExerciseOptions() {
  elements.shoulderExerciseSelect.innerHTML = "";
  SHOULDER_EXERCISE_ORDER.forEach((exerciseKey) => {
    const option = document.createElement("option");
    option.value = exerciseKey;
    option.textContent = SHOULDER_EXERCISES[exerciseKey].name;
    elements.shoulderExerciseSelect.appendChild(option);
  });
  elements.shoulderExerciseSelect.value = state.currentShoulderExercise;
}

function renderGuideItems(items) {
  elements.guideList.innerHTML = "";
  items.forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    elements.guideList.appendChild(item);
  });
}

function getCurrentShoulderExerciseProfile() {
  return SHOULDER_EXERCISES[state.currentShoulderExercise] || SHOULDER_EXERCISES.forward_flexion;
}

async function activateModule(moduleKey, { autoStart = false } = {}) {
  updateModuleUI(moduleKey);
  document.getElementById("workspace").scrollIntoView({ behavior: "smooth", block: "start" });

  if (autoStart) {
    await startCurrentTraining();
  }
}

function getModuleDisplayName(moduleKey) {
  return (
    {
      knee: "膝关节",
      shoulder: "肩关节",
      ankle: "踝关节",
    }[moduleKey] || "该"
  );
}

async function refreshCameraDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) {
    setStatus("当前浏览器不支持设备枚举", "请换用新版 Chrome、Edge 或 Safari。", "浏览器不支持");
    return;
  }

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoInputs = devices.filter((device) => device.kind === "videoinput");

    elements.cameraSelect.innerHTML = "";
    if (!videoInputs.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "未检测到摄像头";
      elements.cameraSelect.appendChild(option);
      return;
    }

    videoInputs.forEach((device, index) => {
      const option = document.createElement("option");
      option.value = device.deviceId;
      option.textContent = device.label || `摄像头 ${index + 1}`;
      elements.cameraSelect.appendChild(option);
    });

    const preferredOption =
      videoInputs.find((device) => /facetime|built-in|内建|高清相机/i.test(device.label)) ||
      videoInputs[0];

    state.selectedCameraId = state.selectedCameraId || preferredOption.deviceId;
    elements.cameraSelect.value = state.selectedCameraId;
  } catch (error) {
    console.error(error);
    setStatus("摄像头列表读取失败", "请检查浏览器权限设置，然后重新刷新设备。", "设备读取失败");
  }
}

async function ensurePoseModel() {
  if (state.pose) {
    return state.pose;
  }

  if (typeof Pose !== "function") {
    throw new Error("MediaPipe Pose 资源还没有加载完成，请稍后再试。");
  }

  const pose = new Pose({
    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
  });

  pose.setOptions({
    modelComplexity: 1,
    smoothLandmarks: true,
    enableSegmentation: false,
    minDetectionConfidence: 0.6,
    minTrackingConfidence: 0.7,
  });

  pose.onResults(onPoseResults);
  state.pose = pose;
  return pose;
}

function getCurrentTargetAngle() {
  if (state.currentModule === "shoulder") {
    return getCurrentShoulderExerciseProfile().targetAngle;
  }
  return CONFIG.targetAngle;
}

function getCurrentHoldGoalSeconds() {
  if (state.currentModule === "shoulder") {
    return getCurrentShoulderExerciseProfile().holdGoalSeconds;
  }
  return CONFIG.holdGoalSeconds;
}

function getCurrentStartPrompt() {
  if (state.currentModule === "shoulder") {
    return getCurrentShoulderExerciseProfile().startPrompt;
  }
  return FEEDBACK_MESSAGES.start[0];
}

function resetTrainingSession(clearLog = true) {
  state.bestAngle = 0;
  state.completedReps = 0;
  state.repCounted = false;
  state.targetReachedAt = null;
  state.lastFeedbackStage = null;
  state.angleHistory = [];
  resetTrackingFilters();

  elements.bestAngleValue.textContent = "0°";
  elements.feedbackStageValue.textContent = "等待识别";
  elements.repCounter.textContent = "完成次数：0";
  setMetricDefaults();
  if (clearLog) {
    clearSessionLog();
  }
}

async function startCurrentTraining() {
  try {
    const pose = await ensurePoseModel();
    await stopStreamOnly();

    const constraints = {
      audio: false,
      video: {
        width: { ideal: CONFIG.preferredVideoWidth },
        height: { ideal: CONFIG.preferredVideoHeight },
      },
    };

    if (state.selectedCameraId) {
      constraints.video.deviceId = { exact: state.selectedCameraId };
    } else {
      constraints.video.facingMode = "user";
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (error) {
      if (constraints.video.deviceId) {
        delete constraints.video.deviceId;
        constraints.video.facingMode = "user";
        stream = await navigator.mediaDevices.getUserMedia(constraints);
      } else {
        throw error;
      }
    }

    state.stream = stream;
    elements.video.srcObject = stream;
    await elements.video.play();
    resizeCanvasToVideo();

    await refreshCameraDevices();

    state.cameraStarted = true;
    resetTrainingSession(true);
    const sessionName =
      state.currentModule === "shoulder"
        ? getCurrentShoulderExerciseProfile().name
        : "膝关节屈曲训练";
    pushSessionLog(`摄像头已启动，开始进行${sessionName}。`);

    elements.cameraState.textContent = "摄像头已启动";
    elements.trackingState.textContent = "正在加载姿态识别";
    setStatus(
      "正在准备识别",
      state.currentModule === "shoulder"
        ? "请先按当前动作要求站位，把上半身和手臂放入镜头。"
        : "请先侧身站稳，把双肩到脚放入镜头。",
      "准备中"
    );
    speakText(getCurrentStartPrompt(), { force: true, stageKey: `${state.currentModule}:start` });

    if (state.animationFrameId) {
      cancelAnimationFrame(state.animationFrameId);
    }
    renderLoop(pose);
  } catch (error) {
    console.error(error);
    setStatus(
      "摄像头启动失败",
      "请确认已允许浏览器访问摄像头，或者切换一个可用的摄像头设备。",
      "启动失败"
    );
  }
}

async function renderLoop(pose) {
  if (!state.cameraStarted) {
    return;
  }

  if (!state.processingFrame && elements.video.readyState >= 2) {
    state.processingFrame = true;
    try {
      await pose.send({ image: elements.video });
    } catch (error) {
      console.error(error);
    } finally {
      state.processingFrame = false;
    }
  }

  state.animationFrameId = requestAnimationFrame(() => renderLoop(pose));
}

async function stopTraining() {
  state.cameraStarted = false;
  if (state.animationFrameId) {
    cancelAnimationFrame(state.animationFrameId);
    state.animationFrameId = null;
  }

  await stopStreamOnly();
  resetTrackingFilters();
  state.angleHistory = [];
  state.targetReachedAt = null;
  state.lastFeedbackStage = null;
  clearCanvas();

  elements.cameraState.textContent = "摄像头未启动";
  elements.trackingState.textContent = "等待识别";
  elements.feedbackStageValue.textContent = "已停止";
  setMetricDefaults();
  setStatus("训练已停止", "可以重新调整站位后再次启动摄像头。", "已停止");
  pushSessionLog("训练已停止。");
}

async function stopStreamOnly() {
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
  }

  elements.video.pause();
  elements.video.srcObject = null;
}

function setMetricDefaults() {
  elements.angleValue.textContent = "--°";
  elements.holdValue.textContent = `0.0 / ${getCurrentHoldGoalSeconds().toFixed(1)} s`;
  elements.stabilityValue.textContent = "等待开始";
  elements.progressCaption.textContent = "还未达到目标角度";
  elements.holdProgressBar.style.width = "0%";
  elements.bestAngleValue.textContent = `${Math.round(state.bestAngle)}°`;
}

function clearCanvas() {
  ctx.clearRect(0, 0, elements.canvas.width, elements.canvas.height);
}

function resizeCanvasToVideo() {
  const width = elements.video.videoWidth || CONFIG.preferredVideoWidth;
  const height = elements.video.videoHeight || CONFIG.preferredVideoHeight;
  elements.canvas.width = width;
  elements.canvas.height = height;
}

function onPoseResults(results) {
  if (state.currentModule === "shoulder") {
    onShoulderPoseResults(results);
    return;
  }

  resizeCanvasToVideo();
  clearCanvas();
  drawFrameGuide();

  if (!results.poseLandmarks || !results.poseLandmarks.length) {
    elements.trackingState.textContent = "未识别到人体";
    setStatus(
      "还没有识别到完整人体",
      "请侧身进入画面，并把双肩到脚完整放进镜头里。",
      "等待识别"
    );
    elements.feedbackStageValue.textContent = "等待识别";
    resetTrackingFilters();
    state.angleHistory = [];
    state.targetReachedAt = null;
    drawStatusOverlay({
      tone: "warning",
      headline: "请先进入画面",
      detail: "侧身站立，并把双肩到脚完整放进镜头。",
      footer: "系统正在等待识别人体关键点",
    });
    maybeSpeak("low_visibility", "请先进入画面并露出双肩到脚。");
    updateMetrics(null);
    return;
  }

  const imageLandmarks = results.poseLandmarks;
  const worldLandmarks = results.poseWorldLandmarks || imageLandmarks;
  const trackedLeg = chooseTrackedLeg(imageLandmarks);
  const viewWarning = getViewWarningStage(imageLandmarks, trackedLeg);
  const [distalPartName, distalIndex] = chooseTrackedDistalLandmark(
    imageLandmarks,
    trackedLeg,
    viewWarning === null
  );

  const hipIndex = TRACKED_LEG_LANDMARKS[trackedLeg].hip;
  const kneeIndex = TRACKED_LEG_LANDMARKS[trackedLeg].knee;
  const hipImage = getLandmarkXY(imageLandmarks, hipIndex);
  const kneeImage = getLandmarkXY(imageLandmarks, kneeIndex);
  const distalImage = distalIndex === null ? null : getLandmarkXY(imageLandmarks, distalIndex);

  if (!distalImage) {
    elements.trackingState.textContent = "关键点不足";
    setStatus(
      "腿部关键点不完整",
      "请调整站位，让髋、膝、脚踝都清楚地出现在画面里。",
      "关键点不足"
    );
    drawStatusOverlay({
      tone: "warning",
      headline: "关键点还不完整",
      detail: "请把髋、膝、脚踝露出来，最好双肩到脚都在镜头里。",
      footer: "系统暂时无法稳定计算屈膝角度",
    });
    maybeSpeak("low_visibility", "请把髋、膝、脚踝露出来，最好双肩到脚都在镜头里。");
    updateMetrics(null);
    return;
  }

  const hipWorld = getLandmarkXYZ(worldLandmarks, hipIndex);
  const kneeWorld = getLandmarkXYZ(worldLandmarks, kneeIndex);
  const distalWorld = getLandmarkXYZ(worldLandmarks, distalIndex);

  let angle = calculateExtensionAngle(hipWorld, kneeWorld, distalWorld);
  angle = smoothAngle(angle);

  const smoothedHip = smoothPoint("hip", hipImage);
  const smoothedKnee = smoothPoint("knee", kneeImage);
  const smoothedDistal = smoothPoint("distal", distalImage);

  let stage = "far";
  let holdSeconds = 0;
  let stable = false;
  let headline = "继续训练";
  let detailText = "保持动作稳定，继续屈膝。";

  if (viewWarning) {
    stage = viewWarning;
    resetHoldState();
    stable = false;
    headline = viewWarning === "adjust_view" ? "请调整侧身角度" : "请补全身体位置";
    detailText =
      viewWarning === "adjust_view"
        ? "身体不要斜着站，请尽量让腿部侧面与摄像头平行。"
        : "请把双肩到脚放进镜头里，尤其是髋、膝和脚踝。";
  } else {
    updateAngleHistory(angle);
    stable = isAngleStable();

    if (angle >= CONFIG.targetAngle) {
      if (!state.targetReachedAt) {
        state.targetReachedAt = performance.now();
      }
      holdSeconds = (performance.now() - state.targetReachedAt) / 1000;
    } else {
      resetHoldState();
      holdSeconds = 0;
    }

    stage = getFeedbackStage(angle, holdSeconds, CONFIG.targetAngle, CONFIG.holdGoalSeconds);
    if (stage === "rest" && !state.repCounted) {
      state.completedReps += 1;
      state.repCounted = true;
      pushSessionLog(`完成 1 次达标保持训练，最佳角度 ${Math.round(state.bestAngle)}°。`);
    }
    if (stage !== "rest" && angle < CONFIG.targetAngle - 8) {
      state.repCounted = false;
    }

  const guidance = buildKneeStatusCopy(stage, angle, holdSeconds, stable);
    headline = guidance.headline;
    detailText = guidance.detailText;
  }

  if (angle > state.bestAngle) {
    state.bestAngle = angle;
  }

  drawTrackedLeg(smoothedHip, smoothedKnee, smoothedDistal, stage, trackedLeg);
  drawStatusOverlay({
    tone: stageTone(stage),
    headline,
    detail: detailText,
    footer:
      stage === "hold" || stage === "target" || stage === "rest"
        ? `保持 ${Math.min(holdSeconds, CONFIG.holdGoalSeconds).toFixed(1)} / ${CONFIG.holdGoalSeconds.toFixed(1)} 秒`
        : `当前角度 ${Math.round(angle)}° / 目标 ${CONFIG.targetAngle}°`,
  });

  elements.cameraState.textContent = "摄像头运行中";
  elements.trackingState.textContent =
    stage === "adjust_view"
      ? "角度偏斜"
      : stage === "low_visibility"
        ? "关键点不足"
        : stable
          ? "识别稳定"
          : "识别中";
  elements.feedbackStageValue.textContent = getStageDisplayName(stage);

  setStatus(headline, detailText, getStageDisplayName(stage));
  updateMetrics({
    angle,
    holdSeconds,
    stable,
    stage,
  });
  maybeSpeak(stage, headline, { moduleKey: "knee" });
}

function onShoulderPoseResults(results) {
  resizeCanvasToVideo();
  clearCanvas();
  drawFrameGuide();

  const profile = getCurrentShoulderExerciseProfile();

  if (!results.poseLandmarks || !results.poseLandmarks.length) {
    elements.trackingState.textContent = "未识别到人体";
    setStatus(
      "还没有识别到完整上半身",
      "请按当前肩关节动作的站位要求进入画面，并把双肩到手腕放进镜头里。",
      "等待识别"
    );
    elements.feedbackStageValue.textContent = "等待识别";
    resetTrackingFilters();
    state.angleHistory = [];
    state.targetReachedAt = null;
    drawStatusOverlay({
      tone: "warning",
      headline: "请先进入画面",
      detail: "请按当前动作要求站位，把双肩到手腕完整放进镜头。",
      footer: `当前动作：${profile.name}`,
    });
    maybeSpeak("low_visibility", "请先进入画面并露出双肩到手腕。", {
      moduleKey: "shoulder",
      profile,
    });
    updateMetrics(null);
    return;
  }

  const imageLandmarks = results.poseLandmarks;
  const worldLandmarks = results.poseWorldLandmarks || imageLandmarks;
  const trackedArm = chooseTrackedArm(imageLandmarks);
  const viewWarning = getShoulderViewWarningStage(imageLandmarks, trackedArm, profile.view);
  const analysis = analyzeShoulderExercise(
    imageLandmarks,
    worldLandmarks,
    state.currentShoulderExercise,
    trackedArm
  );

  const displayAngle = smoothAngle(Math.max(0, analysis.primaryAngle));
  const evaluationAngle = Math.max(displayAngle, analysis.primaryAngle);
  const smoothedShoulder = smoothPoint("shoulder", analysis.shoulderImage);
  const smoothedElbow = smoothPoint("elbow", analysis.elbowImage);
  const smoothedWrist = smoothPoint("wrist", analysis.wristImage);

  let stage = "far";
  let holdSeconds = 0;
  let stable = false;
  let guidance = null;

  if (viewWarning) {
    stage = viewWarning;
    resetHoldState();
    state.angleHistory = [];
    guidance = buildShoulderStatusCopy(stage, analysis, 0, false);
  } else if (analysis.constraintStage) {
    stage = analysis.constraintStage;
    resetHoldState();
    state.angleHistory = [];
    guidance = buildShoulderStatusCopy(stage, analysis, 0, false);
  } else {
    updateAngleHistory(evaluationAngle);
    stable = isAngleStable();

    if (evaluationAngle >= analysis.targetAngle) {
      if (!state.targetReachedAt) {
        state.targetReachedAt = performance.now();
      }
      holdSeconds = (performance.now() - state.targetReachedAt) / 1000;
    } else {
      resetHoldState();
      holdSeconds = 0;
    }

    stage = getFeedbackStage(
      evaluationAngle,
      holdSeconds,
      analysis.targetAngle,
      analysis.holdGoalSeconds
    );

    if (stage === "rest" && !state.repCounted) {
      state.completedReps += 1;
      state.repCounted = true;
      pushSessionLog(
        `完成 1 次${analysis.profile.shortName}达标保持训练，最佳角度 ${Math.round(state.bestAngle)}°。`
      );
    }
    if (stage !== "rest" && evaluationAngle < analysis.targetAngle - 8) {
      state.repCounted = false;
    }

    guidance = buildShoulderStatusCopy(stage, analysis, holdSeconds, stable);
  }

  if (evaluationAngle > state.bestAngle) {
    state.bestAngle = evaluationAngle;
  }

  drawTrackedArm(smoothedShoulder, smoothedElbow, smoothedWrist, stage, evaluationAngle);
  drawStatusOverlay({
    tone: stageTone(stage),
    headline: guidance.headline,
    detail: guidance.detailText,
    footer:
      stage === "hold" || stage === "target" || stage === "rest"
        ? `保持 ${Math.min(holdSeconds, analysis.holdGoalSeconds).toFixed(1)} / ${analysis.holdGoalSeconds.toFixed(1)} 秒`
        : `${analysis.primaryLabel} ${Math.round(evaluationAngle)}° / 目标 ${analysis.targetAngle}°`,
  });

  elements.cameraState.textContent = "摄像头运行中";
  elements.trackingState.textContent =
    stage === "adjust_view"
      ? "角度偏斜"
      : stage === "low_visibility"
        ? "关键点不足"
        : stage === "straighten_arm" || stage === "keep_torso" || stage === "keep_upper_arm" || stage === "keep_elbow_90" || stage === "correct_plane"
          ? "动作待修正"
          : stable
            ? "识别稳定"
            : "识别中";
  elements.feedbackStageValue.textContent = getStageDisplayName(stage);

  setStatus(guidance.headline, guidance.detailText, getStageDisplayName(stage));
  updateMetrics({
    angle: evaluationAngle,
    holdSeconds,
    stable,
    stage,
  });
  maybeSpeak(stage, guidance.headline, {
    moduleKey: "shoulder",
    profile,
    analysis,
  });
}

function buildShoulderStatusCopy(stage, analysis, holdSeconds, stable) {
  const profile = analysis.profile;

  if (stage === "low_visibility") {
    return {
      headline: "关键点还不完整",
      detailText: "请把双肩、手肘和手腕都放进镜头里。",
    };
  }

  if (stage === "adjust_view") {
    return profile.view === "front"
      ? {
          headline: "请调整为正面拍摄",
          detailText: "双肩尽量摆正，不要斜着站，这样肩关节角度会更准。",
        }
      : {
          headline: "请调整为侧面拍摄",
          detailText: "请把身体转成侧身，肩线不要正对镜头。",
        };
  }

  if (stage === "straighten_arm") {
    return {
      headline: "请先把手臂再伸直一些",
      detailText: `当前肘角约 ${Math.round(analysis.elbowAngle)}°，手臂越直角度越准。`,
    };
  }

  if (stage === "keep_torso") {
    return {
      headline: "请先把躯干稳住",
      detailText: "先不要歪身子或前倾，用肩关节本身完成动作。",
    };
  }

  if (stage === "keep_upper_arm") {
    return {
      headline: "请让大臂继续贴住身体",
      detailText: "保持上臂稳定，只让前臂向外旋开。",
    };
  }

  if (stage === "keep_elbow_90") {
    return {
      headline: "请先把肘关节摆到大约 90°",
      detailText: "肘角越接近九十度，这个外旋动作识别越稳定。",
    };
  }

  if (stage === "correct_plane") {
    return {
      headline: "请把动作方向摆正",
      detailText: profile.planeHint,
    };
  }

  if (stage === "target") {
    return {
      headline: `${profile.shortName}角度已经达标`,
      detailText: "请先稳住这个位置，开始进入保持阶段。",
    };
  }

  if (stage === "hold") {
    return {
      headline: "保持得很好",
      detailText: `还需坚持 ${(profile.holdGoalSeconds - holdSeconds).toFixed(1)} 秒，就可以完成本次训练。`,
    };
  }

  if (stage === "rest") {
    return {
      headline: "本次保持完成",
      detailText: "可以慢慢回到起始位，稍作休息，再继续下一次。",
    };
  }

  const gap = Math.max(0, profile.targetAngle - analysis.primaryAngle).toFixed(0);
  return {
    headline: stable ? `继续完成${profile.shortName}` : "动作还在变化",
    detailText: stable
      ? `当前距离目标还差 ${gap}°，${profile.movementHint}`
      : "保持动作更平稳一些，系统会给出更准确的角度。",
  };
}

function getFeedbackStage(angle, holdSeconds, targetAngle = getCurrentTargetAngle(), holdGoalSeconds = getCurrentHoldGoalSeconds()) {
  const holdStartSeconds =
    state.currentModule === "shoulder" ? SHOULDER_CONFIG.holdStartSeconds : CONFIG.holdStartSeconds;

  if (angle >= targetAngle) {
    if (holdSeconds < holdStartSeconds) {
      return "target";
    }
    if (holdSeconds < holdGoalSeconds) {
      return "hold";
    }
    return "rest";
  }

  const gap = targetAngle - angle;
  if (gap <= 5) return "near";
  if (gap <= 15) return "close";
  if (gap <= 35) return "mid";
  return "far";
}

function buildKneeStatusCopy(stage, angle, holdSeconds, stable) {
  if (stage === "target") {
    return {
      headline: "已经达到目标角度",
      detailText: "请先稳住这个位置，开始进入保持阶段。",
    };
  }
  if (stage === "hold") {
    return {
      headline: "保持得很好",
      detailText: `还需坚持 ${(CONFIG.holdGoalSeconds - holdSeconds).toFixed(1)} 秒，就可以完成本次训练。`,
    };
  }
  if (stage === "rest") {
    return {
      headline: "本次保持完成",
      detailText: "可以慢慢放下腿，稍作休息，再继续下一次。",
    };
  }

  const gap = Math.max(0, CONFIG.targetAngle - angle).toFixed(0);
  return {
    headline: stable ? "继续屈膝训练" : "动作还在变化",
    detailText: stable
      ? `当前距离目标还差 ${gap}°，继续沿辅助线方向慢慢屈膝。`
      : "保持动作更平稳一些，系统会给出更准确的角度。",
  };
}

function getStageDisplayName(stage) {
  return (
    {
      far: "起始阶段",
      mid: "接近目标",
      close: "即将达标",
      near: "临近目标",
      target: "已达标",
      hold: "保持中",
      rest: "完成保持",
      adjust_view: "调整角度",
      low_visibility: "补全关键点",
      straighten_arm: "伸直手臂",
      keep_torso: "稳住躯干",
      keep_upper_arm: "大臂贴身",
      keep_elbow_90: "肘角九十度",
      correct_plane: "修正方向",
    }[stage] || "训练中"
  );
}

function getRandomMessage(messages) {
  if (!messages?.length) {
    return null;
  }
  return messages[Math.floor(Math.random() * messages.length)];
}

function getShoulderSpeechText(stage, fallbackText, context = {}) {
  const profile = context.profile || getCurrentShoulderExerciseProfile();
  const messages = {
    low_visibility: ["我现在看这只手不太清楚，请把双肩、手肘和手腕都露出来。"],
    adjust_view:
      profile.view === "front"
        ? ["请尽量正面对着摄像头，再继续训练。"]
        : ["请把身体转成侧身，再继续训练。"],
    straighten_arm: ["先把手臂再伸直一点，角度会更准。"],
    keep_torso: ["请先把躯干稳住，不要歪身子代偿。"],
    keep_upper_arm: ["请让大臂继续贴住身体，不要跟着抬起来。"],
    keep_elbow_90: ["请先把肘关节摆到大约九十度，再继续外旋。"],
    correct_plane: [profile.planeHint],
    far: [`开始做${profile.shortName}。${profile.movementHint}`],
    mid: [`不错，继续完成${profile.shortName}，再慢慢来一点。`],
    close: [`很接近目标了，${profile.shortName}再来一点点。`],
    near: [`就差一点点了，${profile.shortName}再轻轻调整一点。`],
    target: [`很好，${profile.shortName}角度已经达标了，先稳住。`],
    hold: ["保持得很好，再坚持一下。"],
    rest: [`这次${profile.shortName}保持完成了，可以慢慢回到起始位。`],
  };

  return getRandomMessage(messages[stage]) || fallbackText;
}

function maybeSpeak(stage, fallbackText, context = {}) {
  const now = Date.now();
  const moduleKey = context.moduleKey || state.currentModule;
  const shoulderProfileName = context.profile?.name || getCurrentShoulderExerciseProfile().name;
  const stageKey =
    moduleKey === "shoulder"
      ? `${moduleKey}:${shoulderProfileName}:${stage}`
      : `${moduleKey}:${stage}`;

  if (state.lastFeedbackStage === stageKey && now - state.lastVoiceTime < CONFIG.voiceCooldownMs) {
    return;
  }

  const text =
    moduleKey === "shoulder"
      ? getShoulderSpeechText(stage, fallbackText, context)
      : getRandomMessage(FEEDBACK_MESSAGES[stage]) || fallbackText;
  speakText(text, { stageKey });
}

function speakText(text, { force = false, stageKey = "manual" } = {}) {
  if (!text || !elements.voiceToggle.checked || !window.speechSynthesis) {
    return;
  }

  const now = Date.now();
  if (!force && state.lastFeedbackStage === stageKey && now - state.lastVoiceTime < CONFIG.voiceCooldownMs) {
    return;
  }

  if (!text) {
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  utterance.rate = 1;
  window.speechSynthesis.speak(utterance);
  state.lastVoiceTime = now;
  state.lastFeedbackStage = stageKey;
}

function setStatus(headline, detailText, trackingState) {
  elements.statusHeadline.textContent = headline;
  elements.statusText.textContent = detailText;
  elements.trackingState.textContent = trackingState;
}

function updateMetrics(payload) {
  if (!payload) {
    elements.angleValue.textContent = "--°";
    elements.holdValue.textContent = `0.0 / ${getCurrentHoldGoalSeconds().toFixed(1)} s`;
    elements.stabilityValue.textContent = "等待识别";
    elements.progressCaption.textContent = "等待重新识别动作";
    elements.holdProgressBar.style.width = "0%";
    elements.bestAngleValue.textContent = `${Math.round(state.bestAngle)}°`;
    elements.repCounter.textContent = `完成次数：${state.completedReps}`;
    return;
  }

  const angleText = `${Math.round(payload.angle)}°`;
  const holdGoalSeconds = getCurrentHoldGoalSeconds();
  const targetAngle = getCurrentTargetAngle();
  const holdSeconds = Math.min(payload.holdSeconds, holdGoalSeconds);
  const holdRatio = Math.min(holdSeconds / holdGoalSeconds, 1);

  elements.angleValue.textContent = angleText;
  elements.holdValue.textContent = `${holdSeconds.toFixed(1)} / ${holdGoalSeconds.toFixed(1)} s`;
  elements.stabilityValue.textContent =
    payload.stage === "adjust_view" || payload.stage === "low_visibility"
      ? "待调整"
      : payload.stable
        ? "稳定"
        : "变化中";
  elements.holdProgressBar.style.width = `${holdRatio * 100}%`;
  elements.bestAngleValue.textContent = `${Math.round(state.bestAngle)}°`;
  elements.repCounter.textContent = `完成次数：${state.completedReps}`;

  if (payload.stage === "hold" || payload.stage === "rest" || payload.stage === "target") {
    elements.progressCaption.textContent =
      payload.stage === "rest"
        ? "本次保持已完成"
        : `保持剩余 ${(holdGoalSeconds - holdSeconds).toFixed(1)} 秒`;
  } else {
    const gap = Math.max(0, targetAngle - payload.angle);
    elements.progressCaption.textContent = `距离目标还差 ${gap.toFixed(0)}°`;
  }
}

function stageTone(stage) {
  if (stage === "hold" || stage === "rest" || stage === "target") {
    return "success";
  }
  if (
    stage === "adjust_view" ||
    stage === "low_visibility" ||
    stage === "straighten_arm" ||
    stage === "keep_torso" ||
    stage === "keep_upper_arm" ||
    stage === "keep_elbow_90" ||
    stage === "correct_plane"
  ) {
    return "warning";
  }
  return "info";
}

function drawStatusOverlay({ tone = "info", headline, detail, footer }) {
  const { width, height } = elements.canvas;
  const panelWidth = Math.min(width * 0.7, 560);
  const panelX = 24;
  const panelY = 24;
  const lineGap = 30;
  const footerGap = 24;
  const paddingX = 18;
  const paddingY = 18;
  const panelHeight = 130;

  const palette = {
    info: {
      fill: "rgba(10, 31, 42, 0.72)",
      stroke: "rgba(111, 199, 255, 0.88)",
    },
    success: {
      fill: "rgba(13, 55, 39, 0.72)",
      stroke: "rgba(111, 224, 167, 0.92)",
    },
    warning: {
      fill: "rgba(88, 43, 19, 0.76)",
      stroke: "rgba(255, 198, 116, 0.94)",
    },
  };

  const colors = palette[tone] || palette.info;

  ctx.save();
  ctx.fillStyle = colors.fill;
  ctx.strokeStyle = colors.stroke;
  ctx.lineWidth = 2;
  roundRectPath(ctx, panelX, panelY, panelWidth, panelHeight, 18);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#f7f6f1";
  ctx.font = '700 24px "Noto Sans SC", sans-serif';
  ctx.fillText(headline, panelX + paddingX, panelY + paddingY + 8);

  ctx.font = '500 18px "Noto Sans SC", sans-serif';
  wrapCanvasText(detail, panelX + paddingX, panelY + paddingY + lineGap, panelWidth - paddingX * 2, 28);

  ctx.fillStyle = "rgba(247, 246, 241, 0.82)";
  ctx.font = '500 16px "Noto Sans SC", sans-serif';
  ctx.fillText(footer, panelX + paddingX, panelY + panelHeight - footerGap);
  ctx.restore();
}

function roundRectPath(context, x, y, width, height, radius) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + width, y, x + width, y + height, radius);
  context.arcTo(x + width, y + height, x, y + height, radius);
  context.arcTo(x, y + height, x, y, radius);
  context.arcTo(x, y, x + width, y, radius);
  context.closePath();
}

function wrapCanvasText(text, x, y, maxWidth, lineHeight) {
  const chars = [...text];
  let line = "";
  let cursorY = y;

  chars.forEach((char) => {
    const testLine = line + char;
    if (ctx.measureText(testLine).width > maxWidth && line) {
      ctx.fillText(line, x, cursorY);
      line = char;
      cursorY += lineHeight;
    } else {
      line = testLine;
    }
  });

  if (line) {
    ctx.fillText(line, x, cursorY);
  }
}

function pushSessionLog(message) {
  const item = document.createElement("li");
  const now = new Date();
  const timeText = now.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  item.textContent = `[${timeText}] ${message}`;
  elements.sessionLog.prepend(item);

  while (elements.sessionLog.children.length > 6) {
    elements.sessionLog.removeChild(elements.sessionLog.lastChild);
  }
}

function clearSessionLog() {
  elements.sessionLog.innerHTML = "";
}

function resetHoldState() {
  state.targetReachedAt = null;
}

function resetTrackingFilters() {
  state.tracking.lockedLeg = null;
  state.tracking.legCandidate = null;
  state.tracking.legCandidateFrames = 0;
  state.tracking.lockedArm = null;
  state.tracking.armCandidate = null;
  state.tracking.armCandidateFrames = 0;
  state.tracking.lockedDistalPart = null;
  state.tracking.distalCandidate = null;
  state.tracking.distalCandidateFrames = 0;
  state.tracking.smoothedPoints = {
    hip: null,
    knee: null,
    distal: null,
    shoulder: null,
    elbow: null,
    wrist: null,
  };
  state.tracking.smoothedAngle = null;
}

function getLandmark(landmarks, index) {
  return landmarks[index];
}

function getLandmarkVisibility(landmarks, index) {
  return getLandmark(landmarks, index)?.visibility ?? 1;
}

function isLandmarkInFrame(landmarks, index) {
  const point = getLandmark(landmarks, index);
  if (!point) return false;
  return (
    point.x >= -CONFIG.frameMargin &&
    point.x <= 1 + CONFIG.frameMargin &&
    point.y >= -CONFIG.frameMargin &&
    point.y <= 1 + CONFIG.frameMargin
  );
}

function isLandmarkVisible(landmarks, index) {
  return isLandmarkInFrame(landmarks, index) && getLandmarkVisibility(landmarks, index) >= CONFIG.visibilityThreshold;
}

function areLandmarksTrackable(landmarks, indices) {
  if (!indices.length) {
    return false;
  }

  const avgVisibility =
    indices.reduce((sum, index) => sum + getLandmarkVisibility(landmarks, index), 0) / indices.length;
  return indices.every((index) => isLandmarkInFrame(landmarks, index)) && avgVisibility >= CONFIG.visibilityThreshold;
}

function hipsAreTrackable(landmarks) {
  return areLandmarksTrackable(landmarks, [LANDMARK.LEFT_HIP, LANDMARK.RIGHT_HIP]);
}

function getLandmarkXY(landmarks, index) {
  const point = getLandmark(landmarks, index);
  return [point.x, point.y];
}

function getLandmarkXYZ(landmarks, index) {
  const point = getLandmark(landmarks, index);
  return [point.x, point.y, point.z ?? 0];
}

function clipPoint(point, margin = 0) {
  return [
    Math.min(1 - margin, Math.max(margin, point[0])),
    Math.min(1 - margin, Math.max(margin, point[1])),
  ];
}

function projectToPlane(vector, normal) {
  const normalUnit = normalizeVec(normal);
  return subtractVec(vector, multiplyVec(normalUnit, dot(vector, normalUnit)));
}

function cross3(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function calculateJointAngle(a, b, c) {
  const ba = subtractVec(a, b);
  const bc = subtractVec(c, b);
  const denominator = norm(ba) * norm(bc);
  if (!denominator) {
    return 0;
  }
  const cosineAngle = clamp(dot(ba, bc) / denominator, -1, 1);
  return (Math.acos(cosineAngle) * 180) / Math.PI;
}

function calculateVectorAngle(a, b) {
  const denominator = norm(a) * norm(b);
  if (!denominator) {
    return 0;
  }
  const cosineAngle = clamp(dot(a, b) / denominator, -1, 1);
  return (Math.acos(cosineAngle) * 180) / Math.PI;
}

function calculateExtensionAngle(a, b, c) {
  const ba = subtractVec(a, b);
  const bc = subtractVec(c, b);
  const denominator = norm(ba) * norm(bc);
  if (!denominator) {
    return 0;
  }

  const cosineAngle = clamp(dot(ba, bc) / denominator, -1, 1);
  const angle = (Math.acos(cosineAngle) * 180) / Math.PI;
  return 180 - angle;
}

function getArmScore(landmarks, armSide) {
  const arm = TRACKED_ARM_LANDMARKS[armSide];
  return [arm.shoulder, arm.elbow, arm.wrist].reduce((sum, index) => sum + landmarkScore(landmarks, index), 0);
}

function chooseTrackedArm(landmarks) {
  const armScores = {
    left: getArmScore(landmarks, "left"),
    right: getArmScore(landmarks, "right"),
  };

  const bestArm = armScores.left >= armScores.right ? "left" : "right";
  if (!state.tracking.lockedArm) {
    state.tracking.lockedArm = bestArm;
    return bestArm;
  }

  if (bestArm === state.tracking.lockedArm) {
    state.tracking.armCandidate = null;
    state.tracking.armCandidateFrames = 0;
    return bestArm;
  }

  const lockedArmUsable = isArmUsable(landmarks, state.tracking.lockedArm);
  const scoreGap = armScores[bestArm] - armScores[state.tracking.lockedArm];
  if (lockedArmUsable && scoreGap < SHOULDER_CONFIG.armSwitchScoreMargin) {
    state.tracking.armCandidate = null;
    state.tracking.armCandidateFrames = 0;
    return state.tracking.lockedArm;
  }

  if (state.tracking.armCandidate === bestArm) {
    state.tracking.armCandidateFrames += 1;
  } else {
    state.tracking.armCandidate = bestArm;
    state.tracking.armCandidateFrames = 1;
  }

  const requiredFrames = lockedArmUsable ? SHOULDER_CONFIG.armSwitchConfirmFrames : 2;
  if (state.tracking.armCandidateFrames >= requiredFrames) {
    state.tracking.lockedArm = bestArm;
    state.tracking.armCandidate = null;
    state.tracking.armCandidateFrames = 0;
    state.tracking.smoothedPoints.shoulder = null;
    state.tracking.smoothedPoints.elbow = null;
    state.tracking.smoothedPoints.wrist = null;
  }

  return state.tracking.lockedArm;
}

function isArmUsable(landmarks, armSide) {
  const arm = TRACKED_ARM_LANDMARKS[armSide];
  return areLandmarksTrackable(landmarks, [
    arm.shoulder,
    arm.elbow,
    arm.wrist,
    LANDMARK.LEFT_SHOULDER,
    LANDMARK.RIGHT_SHOULDER,
  ]);
}

function calculateTorsoWidthRatio(landmarks) {
  if (!areLandmarksTrackable(landmarks, [LANDMARK.LEFT_SHOULDER, LANDMARK.RIGHT_SHOULDER])) {
    return null;
  }
  if (!hipsAreTrackable(landmarks)) {
    return null;
  }

  const leftShoulder = getLandmarkXY(landmarks, LANDMARK.LEFT_SHOULDER);
  const rightShoulder = getLandmarkXY(landmarks, LANDMARK.RIGHT_SHOULDER);
  const leftHip = getLandmarkXY(landmarks, LANDMARK.LEFT_HIP);
  const rightHip = getLandmarkXY(landmarks, LANDMARK.RIGHT_HIP);
  const shoulderWidth = distance2D(leftShoulder, rightShoulder);
  const hipWidth = distance2D(leftHip, rightHip);
  const midShoulder = midpoint(leftShoulder, rightShoulder);
  const midHip = midpoint(leftHip, rightHip);
  const torsoLength = distance2D(midShoulder, midHip);
  if (!torsoLength) {
    return null;
  }
  return Math.max(shoulderWidth, hipWidth) / torsoLength;
}

function calculateTorsoLeanDegrees(landmarks) {
  if (!hipsAreTrackable(landmarks)) {
    return null;
  }

  const leftShoulder = getLandmarkXY(landmarks, LANDMARK.LEFT_SHOULDER);
  const rightShoulder = getLandmarkXY(landmarks, LANDMARK.RIGHT_SHOULDER);
  const leftHip = getLandmarkXY(landmarks, LANDMARK.LEFT_HIP);
  const rightHip = getLandmarkXY(landmarks, LANDMARK.RIGHT_HIP);
  const torsoVector = subtractVec(midpoint(leftShoulder, rightShoulder), midpoint(leftHip, rightHip));
  return calculateVectorAngle(torsoVector, [0, -1]);
}

function getShoulderViewWarningStage(landmarks, armSide, viewMode) {
  if (!isArmUsable(landmarks, armSide)) {
    return "low_visibility";
  }

  const torsoWidthRatio = calculateTorsoWidthRatio(landmarks);
  if (torsoWidthRatio === null) {
    return null;
  }

  if (viewMode === "front" && torsoWidthRatio < SHOULDER_CONFIG.frontViewMinTorsoWidthRatio) {
    return "adjust_view";
  }
  if (viewMode === "side" && torsoWidthRatio > SHOULDER_CONFIG.sideViewMaxTorsoWidthRatio) {
    return "adjust_view";
  }
  return null;
}

function buildBodyAxes(worldLandmarks, imageLandmarks) {
  const leftShoulder = getLandmarkXYZ(worldLandmarks, LANDMARK.LEFT_SHOULDER);
  const rightShoulder = getLandmarkXYZ(worldLandmarks, LANDMARK.RIGHT_SHOULDER);
  const midShoulder = midpoint(leftShoulder, rightShoulder);

  let lateral = normalizeVec(subtractVec(rightShoulder, leftShoulder));
  if (!norm(lateral)) {
    lateral = [1, 0, 0];
  }

  let vertical;
  if (imageLandmarks && hipsAreTrackable(imageLandmarks)) {
    const leftHip = getLandmarkXYZ(worldLandmarks, LANDMARK.LEFT_HIP);
    const rightHip = getLandmarkXYZ(worldLandmarks, LANDMARK.RIGHT_HIP);
    const midHip = midpoint(leftHip, rightHip);
    vertical = normalizeVec(subtractVec(midHip, midShoulder));
  } else {
    vertical = projectToPlane([0, 1, 0], lateral);
    if (!norm(vertical)) {
      vertical = [0, 1, 0];
    }
    vertical = normalizeVec(vertical);
  }

  let forward = cross3(lateral, vertical);
  if (!norm(forward)) {
    forward = [0, 0, -1];
  } else {
    forward = normalizeVec(forward);
  }

  const nose = getLandmarkXYZ(worldLandmarks, LANDMARK.NOSE);
  const noseVector = subtractVec(nose, midShoulder);
  if (dot(forward, noseVector) < 0) {
    forward = multiplyVec(forward, -1);
  }

  return {
    vertical,
    lateral,
    forward,
    midShoulder,
  };
}

function getSagittalShoulderAngle(bodyAxes, shoulder, elbow) {
  const armVector = subtractVec(elbow, shoulder);
  const armSagittal = projectToPlane(armVector, bodyAxes.lateral);
  if (!norm(armSagittal)) {
    return [0, 0, 0];
  }

  const armSagittalUnit = normalizeVec(armSagittal);
  const angle = calculateVectorAngle(bodyAxes.vertical, armSagittalUnit);
  const forwardComponent = dot(armSagittalUnit, bodyAxes.forward);
  const lateralDeviation = Math.abs(dot(normalizeVec(armVector), bodyAxes.lateral));
  const signedAngle = forwardComponent >= 0 ? angle : -angle;
  return [signedAngle, forwardComponent, lateralDeviation];
}

function getCoronalShoulderAngle(bodyAxes, shoulder, elbow, armSide) {
  const armVector = subtractVec(elbow, shoulder);
  const armCoronal = projectToPlane(armVector, bodyAxes.forward);
  if (!norm(armCoronal)) {
    return [0, 0, 0];
  }

  const armCoronalUnit = normalizeVec(armCoronal);
  const angle = calculateVectorAngle(bodyAxes.vertical, armCoronalUnit);
  let lateralAlignment = dot(armCoronalUnit, bodyAxes.lateral);
  if (armSide === "left") {
    lateralAlignment = -lateralAlignment;
  }
  const forwardDeviation = Math.abs(dot(normalizeVec(armVector), bodyAxes.forward));
  return [angle, lateralAlignment, forwardDeviation];
}

function getExternalRotationAngle(bodyAxes, elbow, wrist, armSide) {
  const forearmVector = subtractVec(wrist, elbow);
  const forearmHorizontal = projectToPlane(forearmVector, bodyAxes.vertical);
  if (!norm(forearmHorizontal) || !norm(forearmVector)) {
    return [0, 0, 0, 0];
  }

  const forearmHorizontalUnit = normalizeVec(forearmHorizontal);
  const outwardAxis = armSide === "right" ? bodyAxes.lateral : multiplyVec(bodyAxes.lateral, -1);
  const forwardAxis = bodyAxes.forward;
  const forwardComponent = dot(forearmHorizontalUnit, forwardAxis);
  const outwardComponent = dot(forearmHorizontalUnit, outwardAxis);
  const horizontalRatio = norm(forearmHorizontal) / norm(forearmVector);
  const angle = (Math.atan2(Math.max(outwardComponent, 0), Math.max(forwardComponent, 1e-6)) * 180) / Math.PI;
  return [angle, forwardComponent, outwardComponent, horizontalRatio];
}

function analyzeShoulderExercise(imageLandmarks, worldLandmarks, exerciseKey, armSide) {
  const profile = SHOULDER_EXERCISES[exerciseKey];
  const arm = TRACKED_ARM_LANDMARKS[armSide];
  const hipsVisible = hipsAreTrackable(imageLandmarks);

  const shoulderImage = getLandmarkXY(imageLandmarks, arm.shoulder);
  const elbowImage = getLandmarkXY(imageLandmarks, arm.elbow);
  const wristImage = getLandmarkXY(imageLandmarks, arm.wrist);
  const shoulderWorld = getLandmarkXYZ(worldLandmarks, arm.shoulder);
  const elbowWorld = getLandmarkXYZ(worldLandmarks, arm.elbow);
  const wristWorld = getLandmarkXYZ(worldLandmarks, arm.wrist);
  const hipWorld = hipsVisible ? getLandmarkXYZ(worldLandmarks, arm.hip) : null;
  const bodyAxes = buildBodyAxes(worldLandmarks, imageLandmarks);
  const torsoDownVector = hipWorld ? subtractVec(hipWorld, shoulderWorld) : bodyAxes.vertical;
  const upperArmVector = subtractVec(elbowWorld, shoulderWorld);
  const elbowAngle2D = calculateJointAngle(shoulderImage, elbowImage, wristImage);
  const elbowAngle3D = calculateJointAngle(shoulderWorld, elbowWorld, wristWorld);
  const elbowAngle = Math.max(elbowAngle2D, elbowAngle3D);
  const upperArmAngle = calculateVectorAngle(torsoDownVector, upperArmVector);
  const torsoLeanDegrees = calculateTorsoLeanDegrees(imageLandmarks);

  const analysis = {
    profile,
    armSide,
    armName: armSide === "left" ? "左臂" : "右臂",
    shoulderImage,
    elbowImage,
    wristImage,
    bodyAxes,
    elbowAngle,
    elbowAngle2D,
    elbowAngle3D,
    upperArmAngle,
    torsoLeanDegrees,
    targetAngle: profile.targetAngle,
    holdGoalSeconds: profile.holdGoalSeconds,
    primaryLabel: profile.primaryLabel,
    primaryAngle: 0,
    constraintStage: null,
  };

  if (exerciseKey === "forward_flexion") {
    const [signedAngle, , lateralDeviation] = getSagittalShoulderAngle(bodyAxes, shoulderWorld, elbowWorld);
    analysis.primaryAngle = Math.max(0, signedAngle);
    if (
      analysis.primaryAngle >= SHOULDER_CONFIG.armBentCheckStartAngle &&
      elbowAngle < SHOULDER_CONFIG.elbowStraightMinAngle
    ) {
      analysis.constraintStage = "straighten_arm";
    } else if (signedAngle < -8 || lateralDeviation > SHOULDER_CONFIG.planeDeviationMax) {
      analysis.constraintStage = "correct_plane";
    }
  } else if (exerciseKey === "abduction") {
    const [coronalAngle, lateralAlignment, forwardDeviation] = getCoronalShoulderAngle(
      bodyAxes,
      shoulderWorld,
      elbowWorld,
      armSide
    );
    analysis.primaryAngle = Math.max(0, coronalAngle);
    if (
      analysis.primaryAngle >= SHOULDER_CONFIG.armBentCheckStartAngle &&
      elbowAngle < SHOULDER_CONFIG.elbowStraightMinAngle
    ) {
      analysis.constraintStage = "straighten_arm";
    } else if (
      analysis.primaryAngle >= 20 &&
      torsoLeanDegrees !== null &&
      torsoLeanDegrees > SHOULDER_CONFIG.trunkLeanMaxDegrees
    ) {
      analysis.constraintStage = "keep_torso";
    } else if (
      forwardDeviation > SHOULDER_CONFIG.planeDeviationMax ||
      lateralAlignment < 0.12
    ) {
      analysis.constraintStage = "correct_plane";
    }
  } else if (exerciseKey === "external_rotation") {
    const [externalRotationAngle, , outwardComponent] = getExternalRotationAngle(
      bodyAxes,
      elbowWorld,
      wristWorld,
      armSide
    );
    analysis.primaryAngle = Math.max(0, externalRotationAngle);
    if (
      Math.abs(elbowAngle - SHOULDER_CONFIG.externalRotationElbowTarget) >
      SHOULDER_CONFIG.externalRotationElbowTolerance
    ) {
      analysis.constraintStage = "keep_elbow_90";
    } else if (upperArmAngle > SHOULDER_CONFIG.externalRotationUpperArmMaxAngle) {
      analysis.constraintStage = "keep_upper_arm";
    } else if (outwardComponent < -0.05) {
      analysis.constraintStage = "correct_plane";
    }
  } else if (exerciseKey === "extension") {
    const [signedAngle, , lateralDeviation] = getSagittalShoulderAngle(bodyAxes, shoulderWorld, elbowWorld);
    analysis.primaryAngle = Math.max(0, -signedAngle);
    if (analysis.primaryAngle >= 12 && elbowAngle < SHOULDER_CONFIG.elbowStraightMinAngle) {
      analysis.constraintStage = "straighten_arm";
    } else if (
      analysis.primaryAngle >= 12 &&
      torsoLeanDegrees !== null &&
      torsoLeanDegrees > SHOULDER_CONFIG.sideTrunkLeanMaxDegrees
    ) {
      analysis.constraintStage = "keep_torso";
    } else if (signedAngle > 8 || lateralDeviation > SHOULDER_CONFIG.planeDeviationMax) {
      analysis.constraintStage = "correct_plane";
    }
  }

  return analysis;
}

function chooseTrackedLeg(landmarks) {
  const legScores = {
    left: getLegScore(landmarks, "left"),
    right: getLegScore(landmarks, "right"),
  };

  const bestLeg = legScores.left >= legScores.right ? "left" : "right";
  if (!state.tracking.lockedLeg) {
    state.tracking.lockedLeg = bestLeg;
    return bestLeg;
  }

  if (bestLeg === state.tracking.lockedLeg) {
    state.tracking.legCandidate = null;
    state.tracking.legCandidateFrames = 0;
    return bestLeg;
  }

  const lockedLegUsable = isLegUsable(landmarks, state.tracking.lockedLeg);
  const scoreGap = legScores[bestLeg] - legScores[state.tracking.lockedLeg];
  if (lockedLegUsable && scoreGap < CONFIG.legSwitchScoreMargin) {
    state.tracking.legCandidate = null;
    state.tracking.legCandidateFrames = 0;
    return state.tracking.lockedLeg;
  }

  if (state.tracking.legCandidate === bestLeg) {
    state.tracking.legCandidateFrames += 1;
  } else {
    state.tracking.legCandidate = bestLeg;
    state.tracking.legCandidateFrames = 1;
  }

  const requiredFrames = lockedLegUsable ? CONFIG.legSwitchConfirmFrames : 2;
  if (state.tracking.legCandidateFrames >= requiredFrames) {
    state.tracking.lockedLeg = bestLeg;
    state.tracking.lockedDistalPart = null;
    state.tracking.distalCandidate = null;
    state.tracking.distalCandidateFrames = 0;
    state.tracking.smoothedPoints = { hip: null, knee: null, distal: null };
  }

  return state.tracking.lockedLeg;
}

function getLegScore(landmarks, legSide) {
  const hip = TRACKED_LEG_LANDMARKS[legSide].hip;
  const knee = TRACKED_LEG_LANDMARKS[legSide].knee;
  const [distalPartName, distalIndex] = getBestDistalLandmark(landmarks, legSide, false, null);

  let score = landmarkScore(landmarks, hip) + landmarkScore(landmarks, knee);
  if (distalPartName && distalIndex !== null) {
    score += landmarkScore(landmarks, distalIndex);
  }
  return score;
}

function landmarkScore(landmarks, index) {
  let score = getLandmarkVisibility(landmarks, index);
  if (isLandmarkInFrame(landmarks, index)) {
    score += 0.5;
  }
  return score;
}

function getBestDistalLandmark(landmarks, legSide, requireVisible, preferredPartName) {
  let bestPartName = null;
  let bestIndex = null;
  let bestScore = -1;

  TRACKED_LEG_LANDMARKS[legSide].distal.forEach(([partName, index]) => {
    if (requireVisible && !isLandmarkVisible(landmarks, index)) {
      return;
    }

    let score = landmarkScore(landmarks, index) + (DISTAL_PRIORITY_BONUS[partName] || 0);
    if (partName === preferredPartName) {
      score += CONFIG.distalLockBonus;
    }

    if (score > bestScore) {
      bestScore = score;
      bestPartName = partName;
      bestIndex = index;
    }
  });

  return [bestPartName, bestIndex];
}

function chooseTrackedDistalLandmark(landmarks, legSide, requireVisible) {
  const [bestPartName, bestIndex] = getBestDistalLandmark(
    landmarks,
    legSide,
    requireVisible,
    state.tracking.lockedDistalPart
  );

  if (bestPartName === null) {
    state.tracking.lockedDistalPart = null;
    state.tracking.distalCandidate = null;
    state.tracking.distalCandidateFrames = 0;
    return [null, null];
  }

  if (!state.tracking.lockedDistalPart) {
    state.tracking.lockedDistalPart = bestPartName;
    return [bestPartName, bestIndex];
  }

  if (bestPartName === state.tracking.lockedDistalPart) {
    state.tracking.distalCandidate = null;
    state.tracking.distalCandidateFrames = 0;
    return [bestPartName, bestIndex];
  }

  if (state.tracking.distalCandidate === bestPartName) {
    state.tracking.distalCandidateFrames += 1;
  } else {
    state.tracking.distalCandidate = bestPartName;
    state.tracking.distalCandidateFrames = 1;
  }

  if (state.tracking.distalCandidateFrames >= CONFIG.distalSwitchConfirmFrames) {
    state.tracking.lockedDistalPart = bestPartName;
    state.tracking.distalCandidate = null;
    state.tracking.distalCandidateFrames = 0;
    return [bestPartName, bestIndex];
  }

  const lockedIndex = TRACKED_LEG_LANDMARKS[legSide].distal.find(
    ([partName]) => partName === state.tracking.lockedDistalPart
  )?.[1];
  return [state.tracking.lockedDistalPart, lockedIndex ?? bestIndex];
}

function isLegUsable(landmarks, legSide) {
  const hip = TRACKED_LEG_LANDMARKS[legSide].hip;
  const knee = TRACKED_LEG_LANDMARKS[legSide].knee;
  const [, distalIndex] = getBestDistalLandmark(landmarks, legSide, true, null);
  if (distalIndex === null) {
    return false;
  }

  const indices = [hip, knee, distalIndex];
  const avgVisibility =
    indices.reduce((sum, index) => sum + getLandmarkVisibility(landmarks, index), 0) / indices.length;
  return indices.every((index) => isLandmarkInFrame(landmarks, index)) && avgVisibility >= CONFIG.visibilityThreshold;
}

function getViewWarningStage(landmarks, legSide) {
  if (!isLegUsable(landmarks, legSide)) {
    return "low_visibility";
  }

  const requiredTorso = [
    LANDMARK.LEFT_SHOULDER,
    LANDMARK.RIGHT_SHOULDER,
    LANDMARK.LEFT_HIP,
    LANDMARK.RIGHT_HIP,
  ];
  if (!requiredTorso.every((index) => isLandmarkVisible(landmarks, index))) {
    return "low_visibility";
  }

  const leftShoulder = getLandmarkXY(landmarks, LANDMARK.LEFT_SHOULDER);
  const rightShoulder = getLandmarkXY(landmarks, LANDMARK.RIGHT_SHOULDER);
  const leftHip = getLandmarkXY(landmarks, LANDMARK.LEFT_HIP);
  const rightHip = getLandmarkXY(landmarks, LANDMARK.RIGHT_HIP);

  const shoulderWidth = distance2D(leftShoulder, rightShoulder);
  const hipWidth = distance2D(leftHip, rightHip);
  const midShoulder = midpoint(leftShoulder, rightShoulder);
  const midHip = midpoint(leftHip, rightHip);
  const torsoLength = distance2D(midShoulder, midHip);

  if (!torsoLength) {
    return "low_visibility";
  }

  const torsoWidthRatio = Math.max(shoulderWidth, hipWidth) / torsoLength;
  if (torsoWidthRatio > CONFIG.sideViewMaxTorsoWidthRatio) {
    return "adjust_view";
  }

  return null;
}

function updateAngleHistory(angle) {
  const now = performance.now();
  state.angleHistory.push([now, angle]);
  const cutoff = now - CONFIG.angleStableWindowSeconds * 1000;
  state.angleHistory = state.angleHistory.filter(([timestamp]) => timestamp >= cutoff);
}

function isAngleStable() {
  if (state.angleHistory.length < 4) {
    return false;
  }

  const values = state.angleHistory.map(([, angle]) => angle);
  return Math.max(...values) - Math.min(...values) <= CONFIG.angleStableRangeDegrees;
}

function smoothPoint(key, point) {
  if (!point) {
    state.tracking.smoothedPoints[key] = null;
    return null;
  }

  const current = clipPoint(point);
  const previous = state.tracking.smoothedPoints[key];
  if (!previous) {
    state.tracking.smoothedPoints[key] = current;
    return current;
  }

  let step = multiplyVec(subtractVec(current, previous), CONFIG.pointSmoothingAlpha);
  if (norm(step) > CONFIG.pointSmoothingMaxStep) {
    step = multiplyVec(normalizeVec(step), CONFIG.pointSmoothingMaxStep);
  }

  const nextPoint = clipPoint(addVec(previous, step));
  state.tracking.smoothedPoints[key] = nextPoint;
  return nextPoint;
}

function smoothAngle(angle) {
  if (state.tracking.smoothedAngle === null) {
    state.tracking.smoothedAngle = angle;
  } else {
    state.tracking.smoothedAngle += (angle - state.tracking.smoothedAngle) * CONFIG.angleSmoothingAlpha;
  }
  return state.tracking.smoothedAngle;
}

function drawFrameGuide() {
  const { width, height } = elements.canvas;
  ctx.save();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.18)";
  ctx.lineWidth = 2;
  ctx.setLineDash([10, 10]);
  ctx.strokeRect(width * 0.12, height * 0.06, width * 0.76, height * 0.88);
  ctx.restore();
}

function drawTrackedLeg(hip, knee, distal, stage, legSide) {
  if (!hip || !knee || !distal) {
    return;
  }

  const hipPx = toPixel(hip);
  const kneePx = toPixel(knee);
  const distalPx = toPixel(distal);
  const activeColor = stage === "hold" || stage === "rest" || stage === "target" ? "#6fe0a7" : "#6fc7ff";

  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = activeColor;
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.moveTo(...hipPx);
  ctx.lineTo(...kneePx);
  ctx.lineTo(...distalPx);
  ctx.stroke();

  drawJoint(hipPx, activeColor, 8);
  drawJoint(kneePx, "#ffffff", 10, activeColor);
  drawJoint(distalPx, activeColor, 8);

  const targetDistal = getTargetDistalPosition(hip, knee, distal, legSide);
  if (targetDistal && stage !== "hold" && stage !== "rest") {
    const targetPx = toPixel(targetDistal);
    ctx.setLineDash([12, 8]);
    ctx.strokeStyle = "rgba(255, 214, 91, 0.95)";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(...kneePx);
    ctx.lineTo(...targetPx);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.strokeStyle = "rgba(255, 214, 91, 0.95)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(targetPx[0], targetPx[1], 10, 0, Math.PI * 2);
    ctx.stroke();

    if (distance2D(targetPx, distalPx) > 24) {
      drawArrow(distalPx, targetPx, "rgba(80, 255, 195, 0.95)");
    }
  }

  ctx.restore();
}

function drawTrackedArm(shoulder, elbow, wrist, stage, angle) {
  if (!shoulder || !elbow || !wrist) {
    return;
  }

  const shoulderPx = toPixel(shoulder);
  const elbowPx = toPixel(elbow);
  const wristPx = toPixel(wrist);
  const activeColor =
    stage === "hold" || stage === "rest" || stage === "target"
      ? "#6fe0a7"
      : stageTone(stage) === "warning"
        ? "#ffd166"
        : "#6fc7ff";

  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = activeColor;
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.moveTo(...shoulderPx);
  ctx.lineTo(...elbowPx);
  ctx.lineTo(...wristPx);
  ctx.stroke();

  drawJoint(shoulderPx, activeColor, 8);
  drawJoint(elbowPx, "#ffffff", 10, activeColor);
  drawJoint(wristPx, activeColor, 8);

  ctx.fillStyle = "#f7f6f1";
  ctx.font = '700 22px "Noto Sans SC", sans-serif';
  ctx.fillText(`${Math.round(angle)}°`, shoulderPx[0] + 12, shoulderPx[1] - 12);
  ctx.restore();
}

function drawJoint(point, fillColor, radius, strokeColor = null) {
  ctx.fillStyle = fillColor;
  ctx.beginPath();
  ctx.arc(point[0], point[1], radius, 0, Math.PI * 2);
  ctx.fill();
  if (strokeColor) {
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 3;
    ctx.stroke();
  }
}

function drawArrow(from, to, color) {
  const headLength = 14;
  const angle = Math.atan2(to[1] - from[1], to[0] - from[0]);
  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(from[0], from[1]);
  ctx.lineTo(to[0], to[1]);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(to[0], to[1]);
  ctx.lineTo(to[0] - headLength * Math.cos(angle - Math.PI / 6), to[1] - headLength * Math.sin(angle - Math.PI / 6));
  ctx.lineTo(to[0] - headLength * Math.cos(angle + Math.PI / 6), to[1] - headLength * Math.sin(angle + Math.PI / 6));
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function getTargetDistalPosition(hip, knee, distal, legSide) {
  const thighVector = subtractVec(hip, knee);
  const shankVector = subtractVec(distal, knee);
  const thighLength = norm(thighVector);
  const shankLength = norm(shankVector);
  if (!thighLength || !shankLength) {
    return null;
  }

  const thighUnit = normalizeVec(thighVector);
  const shankUnit = normalizeVec(shankVector);
  const targetInnerAngle = Math.max(10, 180 - CONFIG.targetAngle);
  const rotationSign = getGuidanceRotationSign(thighUnit, shankUnit, legSide);
  const targetShankUnit = rotateVector(thighUnit, rotationSign * targetInnerAngle);
  return clipPoint(addVec(knee, multiplyVec(targetShankUnit, shankLength)));
}

function getGuidanceRotationSign(thighUnit, shankUnit, legSide) {
  const cross = thighUnit[0] * shankUnit[1] - thighUnit[1] * shankUnit[0];
  if (Math.abs(cross) > 1e-4) {
    return cross > 0 ? 1 : -1;
  }
  if (Math.abs(shankUnit[0]) > 0.02) {
    return shankUnit[0] > 0 ? 1 : -1;
  }
  return legSide === "right" ? 1 : -1;
}

function rotateVector(vector, degrees) {
  const radians = (degrees * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  return [vector[0] * cos - vector[1] * sin, vector[0] * sin + vector[1] * cos];
}

function toPixel(point) {
  return [point[0] * elements.canvas.width, point[1] * elements.canvas.height];
}

function midpoint(a, b) {
  return a.map((value, index) => (value + b[index]) / 2);
}

function distance2D(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function addVec(a, b) {
  return a.map((value, index) => value + b[index]);
}

function subtractVec(a, b) {
  return a.map((value, index) => value - b[index]);
}

function multiplyVec(vector, scalar) {
  return vector.map((value) => value * scalar);
}

function dot(a, b) {
  return a.reduce((sum, value, index) => sum + value * b[index], 0);
}

function norm(vector) {
  return Math.hypot(...vector);
}

function normalizeVec(vector) {
  const magnitude = norm(vector);
  if (!magnitude) {
    return vector.map(() => 0);
  }
  return vector.map((value) => value / magnitude);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
