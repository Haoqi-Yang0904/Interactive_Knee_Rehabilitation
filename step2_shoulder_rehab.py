import cv2
import mediapipe as mp
import numpy as np
import time
import shutil
import subprocess
import os
import importlib.util
import asyncio
import queue
import tempfile
import threading
import sys
from collections import deque

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

# 初始化 MediaPipe 的 Pose 模块
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

VOICE_COOLDOWN_SECONDS = 7.0
SAY_RATE = os.getenv("SAY_RATE", "155")
SAY_VOICE = os.getenv("SAY_VOICE", "")
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge").lower()
EDGE_VOICE = os.getenv("EDGE_VOICE", "zh-CN-XiaoxiaoNeural")
EDGE_RATE = os.getenv("EDGE_RATE", "-10%")
EDGE_VOLUME = os.getenv("EDGE_VOLUME", "+0%")
MELO_DEVICE = os.getenv("MELO_DEVICE", "auto")
MELO_SPEED = float(os.getenv("MELO_SPEED", "0.95"))
MELO_SPEAKER = os.getenv("MELO_SPEAKER", "ZH")

TRACK_ARM = os.getenv("TRACK_ARM", "auto").lower()
SHOULDER_EXERCISE = os.getenv("SHOULDER_EXERCISE", "forward_flexion").lower()

LANDMARK_VISIBILITY_THRESHOLD = 0.20
FRAME_MARGIN = 0.05
ANGLE_STABLE_WINDOW_SECONDS = 0.7
ANGLE_STABLE_RANGE_DEGREES = 6.0
HOLD_START_SECONDS = 2.0
HOLD_GOAL_SECONDS = float(os.getenv("HOLD_GOAL_SECONDS", "6.0"))

FRONT_VIEW_MIN_TORSO_WIDTH_RATIO = 0.28
SIDE_VIEW_MAX_TORSO_WIDTH_RATIO = 0.55
TRUNK_LEAN_MAX_DEGREES = 10.0
SIDE_TRUNK_LEAN_MAX_DEGREES = 12.0

ELBOW_STRAIGHT_MIN_ANGLE = float(os.getenv("ELBOW_STRAIGHT_MIN_ANGLE", "150.0"))
ARM_BENT_CHECK_START_ANGLE = 20.0
EXTERNAL_ROTATION_ELBOW_TARGET = 90.0
EXTERNAL_ROTATION_ELBOW_TOLERANCE = 20.0
EXTERNAL_ROTATION_UPPER_ARM_MAX_ANGLE = 25.0
PLANE_DEVIATION_MAX = 0.34

POSE_MIN_DETECTION_CONFIDENCE = float(os.getenv("POSE_MIN_DETECTION_CONFIDENCE", "0.6"))
POSE_MIN_TRACKING_CONFIDENCE = float(os.getenv("POSE_MIN_TRACKING_CONFIDENCE", "0.7"))
POSE_MODEL_COMPLEXITY = int(os.getenv("POSE_MODEL_COMPLEXITY", "1"))

ARM_SWITCH_CONFIRM_FRAMES = int(os.getenv("ARM_SWITCH_CONFIRM_FRAMES", "6"))
ARM_SWITCH_SCORE_MARGIN = float(os.getenv("ARM_SWITCH_SCORE_MARGIN", "0.35"))
POINT_SMOOTHING_ALPHA = float(os.getenv("POINT_SMOOTHING_ALPHA", "0.35"))
POINT_SMOOTHING_MAX_STEP = float(os.getenv("POINT_SMOOTHING_MAX_STEP", "0.045"))
ANGLE_SMOOTHING_ALPHA = float(os.getenv("ANGLE_SMOOTHING_ALPHA", "0.30"))

CAMERA_INDEX = os.getenv("CAMERA_INDEX")
CAMERA_MAX_PROBE_INDEX = int(os.getenv("CAMERA_MAX_PROBE_INDEX", "5"))
PREFER_MAC_BUILTIN_CAMERA = os.getenv("PREFER_MAC_BUILTIN_CAMERA", "1") == "1"

TARGET_FORWARD_FLEXION_ANGLE = float(os.getenv("TARGET_FORWARD_FLEXION_ANGLE", "120.0"))
TARGET_ABDUCTION_ANGLE = float(os.getenv("TARGET_ABDUCTION_ANGLE", "90.0"))
TARGET_EXTERNAL_ROTATION_ANGLE = float(os.getenv("TARGET_EXTERNAL_ROTATION_ANGLE", "45.0"))
TARGET_EXTENSION_ANGLE = float(os.getenv("TARGET_EXTENSION_ANGLE", "30.0"))

ACTION_PROFILES = {
    "forward_flexion": {
        "name": "肩关节前屈",
        "short_name": "前屈",
        "view": "side",
        "target_angle": TARGET_FORWARD_FLEXION_ANGLE,
        "hold_goal_seconds": HOLD_GOAL_SECONDS,
        "primary_label": "前屈角度",
        "movement_hint": "手臂保持伸直，从身体正前方慢慢向上抬起",
        "plane_hint": "手臂尽量沿身体正前方抬起，不要往身体侧面偏。",
    },
    "abduction": {
        "name": "肩关节外展",
        "short_name": "外展",
        "view": "front",
        "target_angle": TARGET_ABDUCTION_ANGLE,
        "hold_goal_seconds": HOLD_GOAL_SECONDS,
        "primary_label": "外展角度",
        "movement_hint": "手臂保持伸直，从身体侧方向上抬起",
        "plane_hint": "手臂尽量从身体侧方向上抬，不要往身体前方跑。",
    },
    "external_rotation": {
        "name": "中立位外旋",
        "short_name": "外旋",
        "view": "front",
        "target_angle": TARGET_EXTERNAL_ROTATION_ANGLE,
        "hold_goal_seconds": HOLD_GOAL_SECONDS,
        "primary_label": "外旋角度",
        "movement_hint": "大臂贴住躯干，肘关节约九十度，前臂向外打开",
        "plane_hint": "大臂别抬起来，保持贴身，只让前臂向外旋开。",
    },
    "extension": {
        "name": "肩关节后伸",
        "short_name": "后伸",
        "view": "side",
        "target_angle": TARGET_EXTENSION_ANGLE,
        "hold_goal_seconds": HOLD_GOAL_SECONDS,
        "primary_label": "后伸角度",
        "movement_hint": "手臂保持伸直，沿身体一侧慢慢向身后带",
        "plane_hint": "手臂沿身体侧面向后抬，不要往前或往外偏。",
    },
}

ACTION_ORDER = [
    "forward_flexion",
    "abduction",
    "external_rotation",
    "extension",
]

ACTION_KEY_BINDINGS = {
    ord("1"): "forward_flexion",
    ord("2"): "abduction",
    ord("3"): "external_rotation",
    ord("4"): "extension",
}

if SHOULDER_EXERCISE not in ACTION_PROFILES:
    SHOULDER_EXERCISE = ACTION_ORDER[0]

GENERIC_STAGE_MESSAGES = {
    "adjust_view": [
        "先调整一下拍摄角度。按当前动作要求站位，别斜着站。",
        "现在看角度可能不太准。先把站位摆正，我们再继续。",
    ],
    "low_visibility": [
        "我现在看这只手不太清楚。请把双肩、手肘和手腕都露出来。",
        "关键点有点不稳，先调整一下位置，我再帮您看动作。",
    ],
    "straighten_arm": [
        "手臂尽量伸直一点，再继续完成动作，这样角度会更准。",
        "先把胳膊伸直一些，不要弯太多，再继续练习。",
    ],
    "keep_torso": [
        "身体保持直立，不要代偿歪身子，咱们慢慢做。",
        "先把躯干稳住，不要倾斜或侧弯，再继续动作。",
    ],
    "keep_upper_arm": [
        "大臂先贴回身体，不要抬起来，再做外旋。",
        "先把上臂稳住贴着躯干，只让前臂向外打开。",
    ],
    "keep_elbow_90": [
        "肘关节先保持在九十度左右，再继续向外旋。",
        "先把肘子摆到大约九十度，再做这个动作会更准。",
    ],
}

ACTION_STAGE_MESSAGES = {
    "forward_flexion": {
        "far": [
            "挺好的，咱们慢慢抬手。手臂从身体前方往上抬一点。",
            "动作开始了，手臂沿着身体正前方慢慢举起来。",
        ],
        "mid": [
            "不错，已经抬起来不少了。再往前上方慢慢抬一点。",
            "很好，再来一点点。肩膀别耸，手臂继续向上。",
        ],
        "close": [
            "快到了，就差一点。手臂再往上抬一点。",
            "很接近目标了，慢慢往前上方再抬一点就行。",
        ],
        "near": [
            "就差一点点了。再轻轻抬高一点点就够了。",
            "很棒，前屈快到位了，再往上收一点点。",
        ],
        "target": [
            "很好，前屈角度已经达标了。先别放下，稳住。",
        ],
        "hold": [
            "保持得很好，继续稳住这个位置。",
            "非常好，再坚持一下，慢慢呼吸。",
        ],
        "rest": [
            "这次前屈保持完成了，可以慢慢放下休息。",
        ],
        "correct_plane": [
            "手臂尽量从身体正前方抬起，不要往侧面偏。",
            "这个动作要往身体前方抬，不是往外侧打开。",
        ],
    },
    "abduction": {
        "far": [
            "咱们开始做外展。手臂从身体侧方向上抬一点。",
            "很好，手臂沿身体侧面慢慢向上抬。",
        ],
        "mid": [
            "不错，已经抬起来不少了。再向侧上方抬一点。",
            "做得挺稳，继续向身体侧方抬高一点。",
        ],
        "close": [
            "快到九十度了，再轻轻抬高一点。",
            "很接近目标了，手臂再往侧上方走一点。",
        ],
        "near": [
            "就差一点点了，再向侧方抬高一点点。",
            "很好，快到肩高了，再来一点点。",
        ],
        "target": [
            "很好，外展已经到目标角度了。先稳住。",
        ],
        "hold": [
            "保持得不错，身子稳住，继续坚持一下。",
            "很棒，外展角度达标了，再坚持几秒。",
        ],
        "rest": [
            "这次外展保持完成了，可以慢慢放下休息。",
        ],
        "correct_plane": [
            "手臂尽量从身体侧方抬起，不要往前抬。",
            "这个动作是往侧方打开，不是往身体前面举。",
        ],
    },
    "external_rotation": {
        "far": [
            "开始做中立位外旋。大臂贴身，前臂向外打开一点。",
            "很好，保持大臂不动，让前臂慢慢向外旋开。",
        ],
        "mid": [
            "不错，前臂已经打开不少了。再向外一点。",
            "很好，继续让前臂向身体外侧打开一点。",
        ],
        "close": [
            "快到了，前臂再向外旋一点点。",
            "已经很接近目标了，再轻轻向外打开一点。",
        ],
        "near": [
            "就差一点点了，再向外旋开一点就够了。",
            "很棒，外旋快到位了，再开一点点。",
        ],
        "target": [
            "很好，外旋角度已经达标了。先别收回，稳住。",
        ],
        "hold": [
            "保持得很好，大臂贴住身体，再坚持一下。",
            "状态不错，前臂继续稳稳地保持打开。",
        ],
        "rest": [
            "这次外旋保持完成了，可以慢慢收回来休息。",
        ],
        "correct_plane": [
            "前臂继续向外打开，大臂不要跟着跑偏。",
        ],
    },
    "extension": {
        "far": [
            "开始做后伸。手臂沿身体一侧慢慢向身后带一点。",
            "很好，手臂保持伸直，轻轻往身后带。",
        ],
        "mid": [
            "不错，已经向后带起来一些了。再慢慢往后一点。",
            "动作挺稳，继续沿身体侧面向身后带一点。",
        ],
        "close": [
            "快到了，再向身后带一点点就行。",
            "已经很接近目标了，再轻轻向后一点。",
        ],
        "near": [
            "就差一点点了，再往身后带一点点。",
            "很好，后伸快到位了，再向后一点点。",
        ],
        "target": [
            "很好，后伸角度已经达标了。先稳住。",
        ],
        "hold": [
            "保持得很好，继续稳住这个位置。",
            "很棒，再坚持几秒，就可以放松了。",
        ],
        "rest": [
            "这次后伸保持完成了，可以慢慢回到起始位。",
        ],
        "correct_plane": [
            "手臂沿身体侧面向后带，不要往前或往外偏。",
            "这个动作是向身后伸，不是往前抬。",
        ],
    },
}

feedback_message_index = {}
last_voice_time = 0.0
last_feedback_stage = None
target_reached_time = None
voice_process = None
active_voice_stage = None
angle_history = deque(maxlen=60)
overlay_font_cache = {}
current_exercise_key = SHOULDER_EXERCISE

LEGACY_ACTION_NAMES = {
    "forward_flexion": "1-前屈",
    "abduction": "2-外展",
    "external_rotation": "3-外旋",
    "extension": "4-后伸",
}

ARM_LANDMARKS = {
    "left": {
        "hip": mp_pose.PoseLandmark.LEFT_HIP,
        "shoulder": mp_pose.PoseLandmark.LEFT_SHOULDER,
        "elbow": mp_pose.PoseLandmark.LEFT_ELBOW,
        "wrist": mp_pose.PoseLandmark.LEFT_WRIST,
    },
    "right": {
        "hip": mp_pose.PoseLandmark.RIGHT_HIP,
        "shoulder": mp_pose.PoseLandmark.RIGHT_SHOULDER,
        "elbow": mp_pose.PoseLandmark.RIGHT_ELBOW,
        "wrist": mp_pose.PoseLandmark.RIGHT_WRIST,
    },
}

tracking_state = {
    "locked_arm": TRACK_ARM if TRACK_ARM in ARM_LANDMARKS else None,
    "arm_candidate": None,
    "arm_candidate_frames": 0,
    "smoothed_points": {
        "hip": None,
        "shoulder": None,
        "elbow": None,
        "wrist": None,
    },
    "smoothed_angle": None,
}

FONT_SEARCH_DIRECTORIES = [
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
]

FONT_CANDIDATE_FILENAMES = [
    "Arial Unicode.ttf",
    "PingFang.ttc",
    "Hiragino Sans GB.ttc",
    "STHeiti Medium.ttc",
    "STHeiti Light.ttc",
]


def get_say_command():
    """优先使用 macOS 自带 say 命令，并尽量选择中文语音。"""
    say_path = shutil.which("say")
    if not say_path:
        return None

    if SAY_VOICE:
        return [say_path, "-v", SAY_VOICE, "-r", SAY_RATE]

    preferred_voices = [
        "Tingting",
        "Meijia",
        "Sinji",
        "Grandma (中文（中国大陆）)",
        "Sandy (中文（中国大陆）)",
        "Shelley (中文（中国大陆）)",
        "Flo (中文（中国大陆）)",
    ]
    try:
        voices = subprocess.run(
            [say_path, "-v", "?"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        ).stdout
        for voice in preferred_voices:
            if voice in voices:
                return [say_path, "-v", voice, "-r", SAY_RATE]
    except Exception:
        pass

    return [say_path, "-r", SAY_RATE]


say_command = get_say_command()


def edge_tts_is_installed():
    return importlib.util.find_spec("edge_tts") is not None


class EdgeTTSEngine:
    """使用 edge-tts 在线神经网络音色，失败时禁用并回退到系统语音。"""

    def __init__(self):
        self.audio_player = shutil.which("afplay")
        self.disabled = self.audio_player is None
        self.busy = False
        self.message_queue = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        if self.audio_player is None:
            print("⚠️ 找不到 afplay，edge-tts 暂时不能播放音频，将回退到系统语音。")

    def is_busy(self):
        return self.busy or not self.message_queue.empty()

    def speak(self, text):
        if self.disabled or self.is_busy():
            return False

        try:
            self.message_queue.put_nowait(text)
            return True
        except queue.Full:
            return False

    async def _save_audio(self, text, audio_path):
        import edge_tts

        communicate = edge_tts.Communicate(
            text,
            EDGE_VOICE,
            rate=EDGE_RATE,
            volume=EDGE_VOLUME,
        )
        await communicate.save(audio_path)

    def _run(self):
        while True:
            text = self.message_queue.get()
            self.busy = True
            audio_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
                    audio_path = audio_file.name

                asyncio.run(self._save_audio(text, audio_path))
                subprocess.run(
                    [self.audio_player, audio_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception as exc:
                print(f"⚠️ edge-tts 播放失败，后续将回退到系统语音：{exc}")
                self.disabled = True
            finally:
                if audio_path and os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except OSError:
                        pass
                self.busy = False
                self.message_queue.task_done()


def create_edge_tts_engine():
    if TTS_ENGINE not in ("auto", "edge"):
        return None

    if not edge_tts_is_installed():
        if TTS_ENGINE == "edge":
            print("⚠️ 没有安装 edge-tts，将回退到系统语音。")
        return None

    return EdgeTTSEngine()


def melotts_is_installed():
    return importlib.util.find_spec("melo") is not None


def choose_melo_device():
    if MELO_DEVICE != "auto":
        return MELO_DEVICE

    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


class MeloTTSEngine:
    """后台合成和播放，避免 TTS 阻塞摄像头画面。"""

    def __init__(self):
        self.audio_player = shutil.which("afplay")
        self.disabled = self.audio_player is None
        self.busy = False
        self.model = None
        self.speaker_id = None
        self.message_queue = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        if self.audio_player is None:
            print("⚠️ 找不到 afplay，MeloTTS 暂时不能播放音频，将回退到系统语音。")

    def is_busy(self):
        return self.busy or not self.message_queue.empty()

    def speak(self, text):
        if self.disabled or self.is_busy():
            return False

        try:
            self.message_queue.put_nowait(text)
            return True
        except queue.Full:
            return False

    def _load_model(self):
        if self.model is not None:
            return True

        try:
            from melo.api import TTS

            device = choose_melo_device()
            print(f"🎙️ 正在加载 MeloTTS 中文语音模型（device={device}），第一次可能会慢一些...")
            self.model = TTS(language="ZH", device=device)
            speaker_ids = getattr(self.model.hps.data, "spk2id", {})
            self.speaker_id = speaker_ids.get(MELO_SPEAKER)
            if self.speaker_id is None and speaker_ids:
                self.speaker_id = next(iter(speaker_ids.values()))
            print("✅ MeloTTS 已就绪。")
            return True
        except Exception as exc:
            print(f"⚠️ MeloTTS 加载失败，后续将回退到系统语音：{exc}")
            self.disabled = True
            return False

    def _run(self):
        while True:
            text = self.message_queue.get()
            self.busy = True
            audio_path = None
            try:
                if not self._load_model():
                    continue

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
                    audio_path = audio_file.name

                self.model.tts_to_file(
                    text,
                    self.speaker_id,
                    audio_path,
                    speed=MELO_SPEED,
                )
                subprocess.run(
                    [self.audio_player, audio_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception as exc:
                print(f"⚠️ MeloTTS 播放失败，后续将回退到系统语音：{exc}")
                self.disabled = True
            finally:
                if audio_path and os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except OSError:
                        pass
                self.busy = False
                self.message_queue.task_done()


def create_melotts_engine():
    if TTS_ENGINE not in ("auto", "melo"):
        return None

    if not melotts_is_installed():
        if TTS_ENGINE == "melo":
            print("⚠️ 没有安装 MeloTTS，将回退到系统语音。")
        return None

    return MeloTTSEngine()


edge_tts_engine = create_edge_tts_engine()
melo_tts_engine = create_melotts_engine()


def get_overlay_font(font_size):
    if ImageFont is None:
        return None

    if font_size in overlay_font_cache:
        return overlay_font_cache[font_size]

    for directory in FONT_SEARCH_DIRECTORIES:
        for filename in FONT_CANDIDATE_FILENAMES:
            font_path = os.path.join(directory, filename)
            if not os.path.exists(font_path):
                continue
            try:
                font = ImageFont.truetype(font_path, font_size)
                overlay_font_cache[font_size] = font
                return font
            except OSError:
                continue

    font = ImageFont.load_default()
    overlay_font_cache[font_size] = font
    return font


class OverlayPainter:
    def __init__(self, image):
        self.image = image
        self.pil_image = None
        self.draw = None

    def _ensure_drawer(self):
        if Image is None or ImageDraw is None or ImageFont is None:
            return None

        if self.draw is None:
            self.pil_image = Image.fromarray(cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB))
            self.draw = ImageDraw.Draw(self.pil_image, "RGBA")
        return self.draw

    def draw_panel(
        self,
        lines,
        origin,
        font_size=28,
        text_fill=(255, 255, 255, 255),
        panel_fill=(15, 23, 42, 196),
        outline_fill=None,
        padding=(18, 14),
        line_spacing=10,
    ):
        if not lines:
            return

        draw = self._ensure_drawer()
        if draw is None:
            return

        font = get_overlay_font(font_size)
        x, y = origin
        text_sizes = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))

        panel_width = max(width for width, _ in text_sizes) + padding[0] * 2
        panel_height = (
            sum(height for _, height in text_sizes)
            + line_spacing * (len(text_sizes) - 1)
            + padding[1] * 2
        )

        frame_height, frame_width = self.image.shape[:2]
        x = int(np.clip(x, 10, max(10, frame_width - panel_width - 10)))
        y = int(np.clip(y, 10, max(10, frame_height - panel_height - 10)))
        panel_bounds = (x, y, x + panel_width, y + panel_height)
        draw.rounded_rectangle(panel_bounds, radius=20, fill=panel_fill)
        if outline_fill is not None:
            draw.rounded_rectangle(panel_bounds, radius=20, outline=outline_fill, width=2)

        cursor_y = y + padding[1]
        for line, (_, text_height) in zip(lines, text_sizes):
            draw.text((x + padding[0], cursor_y), line, font=font, fill=text_fill)
            cursor_y += text_height + line_spacing

    def finish(self):
        if self.pil_image is not None:
            return cv2.cvtColor(np.array(self.pil_image), cv2.COLOR_RGB2BGR)
        return self.image


def get_stage_messages(exercise_key, stage):
    action_messages = ACTION_STAGE_MESSAGES.get(exercise_key, {})
    if stage in action_messages:
        return action_messages[stage]
    return GENERIC_STAGE_MESSAGES.get(stage, ["请继续完成当前动作。"])


def next_feedback_message(exercise_key, stage):
    messages = get_stage_messages(exercise_key, stage)
    message_key = f"{exercise_key}:{stage}"
    message_index = feedback_message_index.get(message_key, 0) % len(messages)
    feedback_message_index[message_key] = feedback_message_index.get(message_key, 0) + 1
    return messages[message_index]


def get_feedback_stage(angle, hold_seconds, target_angle, hold_goal_seconds):
    if angle >= target_angle:
        if hold_seconds < HOLD_START_SECONDS:
            return "target"
        if hold_seconds < hold_goal_seconds:
            return "hold"
        return "rest"

    angle_gap = target_angle - angle
    if angle_gap <= 5.0:
        return "near"
    if angle_gap <= 15.0:
        return "close"
    if angle_gap <= 35.0:
        return "mid"
    return "far"


def get_stage_group(stage):
    if stage in (
        "far",
        "mid",
        "close",
        "near",
        "straighten_arm",
        "keep_torso",
        "keep_upper_arm",
        "keep_elbow_90",
        "correct_plane",
    ):
        return "below_target"
    if stage in ("target", "hold"):
        return "at_target"
    if stage == "rest":
        return "rest_done"
    return stage


def speak(text, stage):
    """非阻塞语音播报；没有 TTS 时退化为终端输出。"""
    global voice_process, active_voice_stage

    if edge_tts_engine is not None and not edge_tts_engine.disabled:
        if not edge_tts_engine.speak(text):
            return False

        print(f"🔊 康复提示：{text}")
        active_voice_stage = stage
        return True

    if melo_tts_engine is not None and not melo_tts_engine.disabled:
        if not melo_tts_engine.speak(text):
            return False

        print(f"🔊 康复提示：{text}")
        active_voice_stage = stage
        return True

    if voice_process is not None and voice_process.poll() is None:
        return False

    print(f"🔊 康复提示：{text}")
    if say_command is None:
        active_voice_stage = stage
        return True

    try:
        voice_process = subprocess.Popen(
            say_command + [text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        active_voice_stage = stage
        return True
    except Exception:
        voice_process = None
        return True


def maybe_speak_feedback(exercise_key, stage, current_time, target_just_reached=False, angle_stable=True):
    global last_voice_time, last_feedback_stage

    entering_target = stage == "target" and target_just_reached
    view_warning = stage in ("adjust_view", "low_visibility")
    cooldown_ready = (current_time - last_voice_time) >= VOICE_COOLDOWN_SECONDS
    stage_changed = stage != last_feedback_stage
    stage_group_changed = get_stage_group(stage) != get_stage_group(last_feedback_stage)

    if not angle_stable and not entering_target and not view_warning and stage in ("target", "hold"):
        return

    if not entering_target and not view_warning and not stage_group_changed and not cooldown_ready:
        return

    if view_warning and not (cooldown_ready or stage_changed):
        return

    if speak(next_feedback_message(exercise_key, stage), stage=stage):
        last_voice_time = current_time
        last_feedback_stage = stage


def get_landmark(landmarks, landmark_name):
    return landmarks[landmark_name.value]


def get_landmark_xy(landmarks, landmark_name):
    landmark = get_landmark(landmarks, landmark_name)
    return np.array([landmark.x, landmark.y], dtype=float)


def get_landmark_xyz(landmarks, landmark_name):
    landmark = get_landmark(landmarks, landmark_name)
    return np.array([landmark.x, landmark.y, getattr(landmark, "z", 0.0)], dtype=float)


def get_landmark_visibility(landmarks, landmark_name):
    landmark = get_landmark(landmarks, landmark_name)
    return getattr(landmark, "visibility", 1.0)


def is_landmark_in_frame(landmarks, landmark_name):
    landmark = get_landmark(landmarks, landmark_name)
    return (
        -FRAME_MARGIN <= landmark.x <= 1.0 + FRAME_MARGIN
        and -FRAME_MARGIN <= landmark.y <= 1.0 + FRAME_MARGIN
    )


def is_landmark_visible(landmarks, landmark_name):
    return (
        is_landmark_in_frame(landmarks, landmark_name)
        and get_landmark_visibility(landmarks, landmark_name) >= LANDMARK_VISIBILITY_THRESHOLD
    )


def are_landmarks_trackable(landmarks, landmark_names):
    if not landmark_names:
        return False

    average_visibility = sum(
        get_landmark_visibility(landmarks, landmark_name)
        for landmark_name in landmark_names
    ) / len(landmark_names)
    return (
        all(is_landmark_in_frame(landmarks, landmark_name) for landmark_name in landmark_names)
        and average_visibility >= LANDMARK_VISIBILITY_THRESHOLD
    )


def hips_are_trackable(landmarks):
    return are_landmarks_trackable(
        landmarks,
        [
            mp_pose.PoseLandmark.LEFT_HIP,
            mp_pose.PoseLandmark.RIGHT_HIP,
        ],
    )


def normalize_vector(vector):
    vector = np.array(vector, dtype=float)
    magnitude = np.linalg.norm(vector)
    if magnitude == 0:
        return np.zeros_like(vector, dtype=float)
    return vector / magnitude


def project_to_plane(vector, normal):
    normal = normalize_vector(normal)
    return np.array(vector, dtype=float) - np.dot(vector, normal) * normal


def calculate_joint_angle(a, b, c):
    """
    计算三个点之间的夹角 (a, b, c 支持 2D 或 3D)
    """
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    c = np.array(c, dtype=float)

    ba = a - b
    bc = c - b
    denominator = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denominator == 0:
        return 0.0

    cosine_angle = np.dot(ba, bc) / denominator
    return float(np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0))))


def calculate_vector_angle(vector_a, vector_b):
    denominator = np.linalg.norm(vector_a) * np.linalg.norm(vector_b)
    if denominator == 0:
        return 0.0
    cosine_angle = np.dot(vector_a, vector_b) / denominator
    return float(np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0))))


def get_arm_score(landmarks, arm_side):
    score = 0.0
    for landmark_name in ARM_LANDMARKS[arm_side].values():
        visibility = get_landmark_visibility(landmarks, landmark_name)
        score += visibility
        if is_landmark_in_frame(landmarks, landmark_name):
            score += 0.5
    return score


def reset_visual_smoothing():
    tracking_state["smoothed_points"] = {
        "hip": None,
        "shoulder": None,
        "elbow": None,
        "wrist": None,
    }
    tracking_state["smoothed_angle"] = None


def reset_motion_tracking(reset_locked_arm=False, clear_feedback_stage=False):
    global target_reached_time, last_feedback_stage

    target_reached_time = None
    if clear_feedback_stage:
        last_feedback_stage = None
    angle_history.clear()
    reset_visual_smoothing()

    if reset_locked_arm and TRACK_ARM not in ARM_LANDMARKS:
        tracking_state["locked_arm"] = None
        tracking_state["arm_candidate"] = None
        tracking_state["arm_candidate_frames"] = 0


def choose_tracked_arm(landmarks):
    if TRACK_ARM in ARM_LANDMARKS:
        tracking_state["locked_arm"] = TRACK_ARM
        return TRACK_ARM

    arm_scores = {
        arm_side: get_arm_score(landmarks, arm_side)
        for arm_side in ARM_LANDMARKS
    }
    best_arm = max(arm_scores, key=arm_scores.get)
    locked_arm = tracking_state["locked_arm"]

    if locked_arm not in ARM_LANDMARKS:
        tracking_state["locked_arm"] = best_arm
        tracking_state["arm_candidate"] = None
        tracking_state["arm_candidate_frames"] = 0
        return best_arm

    if best_arm == locked_arm:
        tracking_state["arm_candidate"] = None
        tracking_state["arm_candidate_frames"] = 0
        return locked_arm

    locked_arm_usable = is_arm_usable(landmarks, locked_arm)
    score_gap = arm_scores[best_arm] - arm_scores[locked_arm]
    if locked_arm_usable and score_gap < ARM_SWITCH_SCORE_MARGIN:
        tracking_state["arm_candidate"] = None
        tracking_state["arm_candidate_frames"] = 0
        return locked_arm

    if tracking_state["arm_candidate"] == best_arm:
        tracking_state["arm_candidate_frames"] += 1
    else:
        tracking_state["arm_candidate"] = best_arm
        tracking_state["arm_candidate_frames"] = 1

    required_frames = 2 if not locked_arm_usable else ARM_SWITCH_CONFIRM_FRAMES
    if tracking_state["arm_candidate_frames"] >= required_frames:
        tracking_state["locked_arm"] = best_arm
        tracking_state["arm_candidate"] = None
        tracking_state["arm_candidate_frames"] = 0
        reset_visual_smoothing()

    return tracking_state["locked_arm"]


def smooth_normalized_point(point_key, point):
    if point is None:
        tracking_state["smoothed_points"][point_key] = None
        return None

    point = np.array(point, dtype=float)
    point = np.array([
        float(np.clip(point[0], 0.0, 1.0)),
        float(np.clip(point[1], 0.0, 1.0)),
    ])

    previous_point = tracking_state["smoothed_points"].get(point_key)
    if previous_point is None:
        smoothed_point = point
    else:
        step = (point - previous_point) * POINT_SMOOTHING_ALPHA
        step_norm = np.linalg.norm(step)
        if step_norm > POINT_SMOOTHING_MAX_STEP:
            step = step / step_norm * POINT_SMOOTHING_MAX_STEP
        smoothed_point = previous_point + step
        smoothed_point = np.array([
            float(np.clip(smoothed_point[0], 0.0, 1.0)),
            float(np.clip(smoothed_point[1], 0.0, 1.0)),
        ])

    tracking_state["smoothed_points"][point_key] = smoothed_point
    return smoothed_point


def smooth_primary_angle(angle):
    if angle is None:
        tracking_state["smoothed_angle"] = None
        return None

    if tracking_state["smoothed_angle"] is None:
        tracking_state["smoothed_angle"] = float(angle)
    else:
        tracking_state["smoothed_angle"] += (
            float(angle) - tracking_state["smoothed_angle"]
        ) * ANGLE_SMOOTHING_ALPHA
    return tracking_state["smoothed_angle"]


def get_arm_display_name(arm_side):
    if arm_side == "left":
        return "左臂"
    if arm_side == "right":
        return "右臂"
    return "手臂"


def calculate_torso_width_ratio(landmarks):
    if not are_landmarks_trackable(
        landmarks,
        [
            mp_pose.PoseLandmark.LEFT_SHOULDER,
            mp_pose.PoseLandmark.RIGHT_SHOULDER,
        ],
    ):
        return None

    if not hips_are_trackable(landmarks):
        return None

    left_shoulder = get_landmark_xy(landmarks, mp_pose.PoseLandmark.LEFT_SHOULDER)
    right_shoulder = get_landmark_xy(landmarks, mp_pose.PoseLandmark.RIGHT_SHOULDER)
    left_hip = get_landmark_xy(landmarks, mp_pose.PoseLandmark.LEFT_HIP)
    right_hip = get_landmark_xy(landmarks, mp_pose.PoseLandmark.RIGHT_HIP)

    shoulder_width = np.linalg.norm(left_shoulder - right_shoulder)
    hip_width = np.linalg.norm(left_hip - right_hip)
    mid_shoulder = (left_shoulder + right_shoulder) / 2
    mid_hip = (left_hip + right_hip) / 2
    torso_length = np.linalg.norm(mid_shoulder - mid_hip)
    if torso_length == 0:
        return None
    return max(shoulder_width, hip_width) / torso_length


def calculate_torso_lean_degrees(landmarks):
    if not hips_are_trackable(landmarks):
        return None

    left_shoulder = get_landmark_xy(landmarks, mp_pose.PoseLandmark.LEFT_SHOULDER)
    right_shoulder = get_landmark_xy(landmarks, mp_pose.PoseLandmark.RIGHT_SHOULDER)
    left_hip = get_landmark_xy(landmarks, mp_pose.PoseLandmark.LEFT_HIP)
    right_hip = get_landmark_xy(landmarks, mp_pose.PoseLandmark.RIGHT_HIP)

    mid_shoulder = (left_shoulder + right_shoulder) / 2
    mid_hip = (left_hip + right_hip) / 2
    torso_vector = mid_shoulder - mid_hip
    return calculate_vector_angle(torso_vector, np.array([0.0, -1.0]))


def is_arm_usable(landmarks, arm_side):
    arm = ARM_LANDMARKS[arm_side]
    required_landmarks = list(dict.fromkeys([
        arm["shoulder"],
        arm["elbow"],
        arm["wrist"],
        mp_pose.PoseLandmark.LEFT_SHOULDER,
        mp_pose.PoseLandmark.RIGHT_SHOULDER,
    ]))

    return are_landmarks_trackable(
        landmarks,
        required_landmarks,
    )


def get_view_warning_stage(landmarks, arm_side, exercise_key):
    if not is_arm_usable(landmarks, arm_side):
        return "low_visibility"

    torso_width_ratio = calculate_torso_width_ratio(landmarks)
    view_mode = ACTION_PROFILES[exercise_key]["view"]
    if torso_width_ratio is None:
        return None

    if view_mode == "front" and torso_width_ratio < FRONT_VIEW_MIN_TORSO_WIDTH_RATIO:
        return "adjust_view"
    if view_mode == "side" and torso_width_ratio > SIDE_VIEW_MAX_TORSO_WIDTH_RATIO:
        return "adjust_view"
    return None


def update_angle_history(angle, current_time):
    angle_history.append((current_time, angle))
    while angle_history and current_time - angle_history[0][0] > ANGLE_STABLE_WINDOW_SECONDS:
        angle_history.popleft()


def is_angle_stable():
    if len(angle_history) < 4:
        return False

    time_span = angle_history[-1][0] - angle_history[0][0]
    if time_span < ANGLE_STABLE_WINDOW_SECONDS * 0.5:
        return False

    recent_angles = [angle for _, angle in angle_history]
    return max(recent_angles) - min(recent_angles) <= ANGLE_STABLE_RANGE_DEGREES


def build_body_axes(world_landmarks, image_landmarks=None):
    left_shoulder = get_landmark_xyz(world_landmarks, mp_pose.PoseLandmark.LEFT_SHOULDER)
    right_shoulder = get_landmark_xyz(world_landmarks, mp_pose.PoseLandmark.RIGHT_SHOULDER)
    mid_shoulder = (left_shoulder + right_shoulder) / 2
    mid_hip = None

    lateral = normalize_vector(right_shoulder - left_shoulder)
    if np.linalg.norm(lateral) == 0:
        lateral = np.array([1.0, 0.0, 0.0], dtype=float)

    if image_landmarks is not None and hips_are_trackable(image_landmarks):
        left_hip = get_landmark_xyz(world_landmarks, mp_pose.PoseLandmark.LEFT_HIP)
        right_hip = get_landmark_xyz(world_landmarks, mp_pose.PoseLandmark.RIGHT_HIP)
        mid_hip = (left_hip + right_hip) / 2
        vertical = normalize_vector(mid_hip - mid_shoulder)
    else:
        vertical = project_to_plane(np.array([0.0, 1.0, 0.0], dtype=float), lateral)
        if np.linalg.norm(vertical) == 0:
            vertical = np.array([0.0, 1.0, 0.0], dtype=float)
        vertical = normalize_vector(vertical)

    forward = np.cross(lateral, vertical)
    if np.linalg.norm(forward) == 0:
        forward = np.array([0.0, 0.0, -1.0], dtype=float)
    else:
        forward = normalize_vector(forward)

    try:
        nose = get_landmark_xyz(world_landmarks, mp_pose.PoseLandmark.NOSE)
        nose_vector = nose - mid_shoulder
        if np.dot(forward, nose_vector) < 0:
            forward = -forward
    except Exception:
        pass

    return {
        "vertical": vertical,
        "lateral": lateral,
        "forward": forward,
        "mid_shoulder": mid_shoulder,
        "mid_hip": mid_hip,
    }


def get_sagittal_shoulder_angle(body_axes, shoulder, elbow):
    arm_vector = np.array(elbow, dtype=float) - np.array(shoulder, dtype=float)
    arm_sagittal = project_to_plane(arm_vector, body_axes["lateral"])
    if np.linalg.norm(arm_sagittal) == 0:
        return 0.0, 0.0, 0.0

    arm_sagittal_unit = normalize_vector(arm_sagittal)
    angle = calculate_vector_angle(body_axes["vertical"], arm_sagittal_unit)
    forward_component = float(np.dot(arm_sagittal_unit, body_axes["forward"]))
    lateral_deviation = float(abs(np.dot(normalize_vector(arm_vector), body_axes["lateral"])))
    signed_angle = angle if forward_component >= 0 else -angle
    return signed_angle, forward_component, lateral_deviation


def get_coronal_shoulder_angle(body_axes, shoulder, elbow, arm_side):
    arm_vector = np.array(elbow, dtype=float) - np.array(shoulder, dtype=float)
    arm_coronal = project_to_plane(arm_vector, body_axes["forward"])
    if np.linalg.norm(arm_coronal) == 0:
        return 0.0, 0.0, 0.0

    arm_coronal_unit = normalize_vector(arm_coronal)
    angle = calculate_vector_angle(body_axes["vertical"], arm_coronal_unit)
    lateral_alignment = float(np.dot(arm_coronal_unit, body_axes["lateral"]))
    if arm_side == "left":
        lateral_alignment = -lateral_alignment
    forward_deviation = float(abs(np.dot(normalize_vector(arm_vector), body_axes["forward"])))
    return angle, lateral_alignment, forward_deviation


def get_external_rotation_angle(body_axes, elbow, wrist, arm_side):
    forearm_vector = np.array(wrist, dtype=float) - np.array(elbow, dtype=float)
    forearm_horizontal = project_to_plane(forearm_vector, body_axes["vertical"])
    if np.linalg.norm(forearm_horizontal) == 0 or np.linalg.norm(forearm_vector) == 0:
        return 0.0, 0.0, 0.0, 0.0

    forearm_horizontal_unit = normalize_vector(forearm_horizontal)
    outward_axis = body_axes["lateral"] if arm_side == "right" else -body_axes["lateral"]
    forward_axis = body_axes["forward"]

    forward_component = float(np.dot(forearm_horizontal_unit, forward_axis))
    outward_component = float(np.dot(forearm_horizontal_unit, outward_axis))
    horizontal_ratio = float(np.linalg.norm(forearm_horizontal) / np.linalg.norm(forearm_vector))

    forward_component_clamped = max(forward_component, 1e-6)
    outward_component_clamped = max(outward_component, 0.0)
    angle = float(np.degrees(np.arctan2(outward_component_clamped, forward_component_clamped)))
    return angle, forward_component, outward_component, horizontal_ratio


def analyze_exercise(image_landmarks, world_landmarks, exercise_key, arm_side):
    profile = ACTION_PROFILES[exercise_key]
    arm = ARM_LANDMARKS[arm_side]
    hips_visible = hips_are_trackable(image_landmarks)

    shoulder_image = get_landmark_xy(image_landmarks, arm["shoulder"])
    elbow_image = get_landmark_xy(image_landmarks, arm["elbow"])
    wrist_image = get_landmark_xy(image_landmarks, arm["wrist"])
    hip_image = get_landmark_xy(image_landmarks, arm["hip"]) if hips_visible else None

    shoulder_world = get_landmark_xyz(world_landmarks, arm["shoulder"])
    elbow_world = get_landmark_xyz(world_landmarks, arm["elbow"])
    wrist_world = get_landmark_xyz(world_landmarks, arm["wrist"])
    hip_world = get_landmark_xyz(world_landmarks, arm["hip"]) if hips_visible else None

    body_axes = build_body_axes(world_landmarks, image_landmarks=image_landmarks)
    upper_arm_vector = elbow_world - shoulder_world
    torso_down_vector = (
        hip_world - shoulder_world
        if hip_world is not None
        else body_axes["vertical"]
    )
    elbow_angle_2d = calculate_joint_angle(shoulder_image, elbow_image, wrist_image)
    elbow_angle_3d = calculate_joint_angle(shoulder_world, elbow_world, wrist_world)
    elbow_angle = max(elbow_angle_2d, elbow_angle_3d)
    upper_arm_angle = calculate_vector_angle(torso_down_vector, upper_arm_vector)
    torso_lean_degrees = calculate_torso_lean_degrees(image_landmarks)

    analysis = {
        "profile": profile,
        "exercise_key": exercise_key,
        "arm_side": arm_side,
        "arm_name": get_arm_display_name(arm_side),
        "shoulder_image": shoulder_image,
        "elbow_image": elbow_image,
        "wrist_image": wrist_image,
        "hip_image": hip_image,
        "shoulder_world": shoulder_world,
        "elbow_world": elbow_world,
        "wrist_world": wrist_world,
        "hip_world": hip_world,
        "hips_visible": hips_visible,
        "body_axes": body_axes,
        "elbow_angle": elbow_angle,
        "elbow_angle_2d": elbow_angle_2d,
        "elbow_angle_3d": elbow_angle_3d,
        "upper_arm_angle": upper_arm_angle,
        "torso_lean_degrees": torso_lean_degrees,
        "torso_lean_available": torso_lean_degrees is not None,
        "target_angle": profile["target_angle"],
        "hold_goal_seconds": profile["hold_goal_seconds"],
        "primary_label": profile["primary_label"],
        "constraint_stage": None,
        "constraint_reason": "",
        "primary_angle": 0.0,
    }

    if exercise_key == "forward_flexion":
        signed_angle, _, lateral_deviation = get_sagittal_shoulder_angle(
            body_axes,
            shoulder_world,
            elbow_world,
        )
        analysis["signed_sagittal_angle"] = signed_angle
        analysis["plane_deviation"] = lateral_deviation
        analysis["primary_angle"] = max(0.0, signed_angle)

        if analysis["primary_angle"] >= ARM_BENT_CHECK_START_ANGLE and elbow_angle < ELBOW_STRAIGHT_MIN_ANGLE:
            analysis["constraint_stage"] = "straighten_arm"
            analysis["constraint_reason"] = "系统还没有稳定判定到肘关节伸直"
        elif signed_angle < -8.0 or lateral_deviation > PLANE_DEVIATION_MAX:
            analysis["constraint_stage"] = "correct_plane"
            analysis["constraint_reason"] = "手臂当前没有沿着身体前方的动作平面抬起"

    elif exercise_key == "abduction":
        coronal_angle, lateral_alignment, forward_deviation = get_coronal_shoulder_angle(
            body_axes,
            shoulder_world,
            elbow_world,
            arm_side,
        )
        analysis["lateral_alignment"] = lateral_alignment
        analysis["plane_deviation"] = forward_deviation
        analysis["primary_angle"] = max(0.0, coronal_angle)

        if analysis["primary_angle"] >= ARM_BENT_CHECK_START_ANGLE and elbow_angle < ELBOW_STRAIGHT_MIN_ANGLE:
            analysis["constraint_stage"] = "straighten_arm"
            analysis["constraint_reason"] = "系统还没有稳定判定到肘关节伸直"
        elif (
            analysis["primary_angle"] >= 20.0
            and torso_lean_degrees is not None
            and torso_lean_degrees > TRUNK_LEAN_MAX_DEGREES
        ):
            analysis["constraint_stage"] = "keep_torso"
            analysis["constraint_reason"] = "检测到躯干侧弯或歪身子代偿"
        elif forward_deviation > PLANE_DEVIATION_MAX or lateral_alignment < 0.12:
            analysis["constraint_stage"] = "correct_plane"
            analysis["constraint_reason"] = "手臂当前更像往前抬，没有沿身体侧方外展"

    elif exercise_key == "external_rotation":
        external_rotation_angle, forward_component, outward_component, horizontal_ratio = get_external_rotation_angle(
            body_axes,
            elbow_world,
            wrist_world,
            arm_side,
        )
        analysis["forward_component"] = forward_component
        analysis["outward_component"] = outward_component
        analysis["horizontal_ratio"] = horizontal_ratio
        analysis["primary_angle"] = max(0.0, external_rotation_angle)

        if abs(elbow_angle - EXTERNAL_ROTATION_ELBOW_TARGET) > EXTERNAL_ROTATION_ELBOW_TOLERANCE:
            analysis["constraint_stage"] = "keep_elbow_90"
            analysis["constraint_reason"] = "肘关节没有稳定保持在九十度附近"
        elif upper_arm_angle > EXTERNAL_ROTATION_UPPER_ARM_MAX_ANGLE:
            analysis["constraint_stage"] = "keep_upper_arm"
            analysis["constraint_reason"] = "大臂离开了躯干，没有继续贴身"
        elif outward_component < -0.05:
            analysis["constraint_stage"] = "correct_plane"
            analysis["constraint_reason"] = "前臂打开方向不对，需要继续向身体外侧旋开"

    elif exercise_key == "extension":
        signed_angle, _, lateral_deviation = get_sagittal_shoulder_angle(
            body_axes,
            shoulder_world,
            elbow_world,
        )
        analysis["signed_sagittal_angle"] = signed_angle
        analysis["plane_deviation"] = lateral_deviation
        analysis["primary_angle"] = max(0.0, -signed_angle)

        if analysis["primary_angle"] >= 12.0 and elbow_angle < ELBOW_STRAIGHT_MIN_ANGLE:
            analysis["constraint_stage"] = "straighten_arm"
            analysis["constraint_reason"] = "系统还没有稳定判定到肘关节伸直"
        elif (
            analysis["primary_angle"] >= 12.0
            and torso_lean_degrees is not None
            and torso_lean_degrees > SIDE_TRUNK_LEAN_MAX_DEGREES
        ):
            analysis["constraint_stage"] = "keep_torso"
            analysis["constraint_reason"] = "检测到身体前倾或代偿"
        elif signed_angle > 8.0 or lateral_deviation > PLANE_DEVIATION_MAX:
            analysis["constraint_stage"] = "correct_plane"
            analysis["constraint_reason"] = "手臂当前没有沿身体侧面向身后伸"

    return analysis


def build_info_lines(analysis, display_angle, hold_seconds, feedback_stage, angle_stable):
    profile = analysis["profile"]
    lines = [
        f"当前动作：{profile['name']}（按 1-4 切换）",
        f"当前监测：{analysis['arm_name']}",
        f"{analysis['primary_label']}：{int(round(display_angle))}° / 目标：{int(round(profile['target_angle']))}°",
        f"肘关节角度：{int(round(analysis['elbow_angle']))}°",
    ]

    if analysis["exercise_key"] == "external_rotation":
        lines.append(f"大臂贴身角度：{int(round(analysis['upper_arm_angle']))}° / 建议 ≤ {int(EXTERNAL_ROTATION_UPPER_ARM_MAX_ANGLE)}°")
    elif analysis["exercise_key"] in ("abduction", "extension"):
        if analysis["torso_lean_degrees"] is None:
            lines.append("躯干倾斜：未检测（不影响继续训练）")
        else:
            lines.append(f"躯干倾斜：{int(round(analysis['torso_lean_degrees']))}°")

    if feedback_stage in ("target", "hold", "rest"):
        lines.append(
            f"保持进度：{min(hold_seconds, profile['hold_goal_seconds']):.1f}/{profile['hold_goal_seconds']:.1f} 秒"
        )
    elif not angle_stable:
        lines.append("动作还在变化，稳定后测量会更准确")

    if feedback_stage == "straighten_arm":
        lines.append(
            f"伸直判定参考：2D {int(round(analysis['elbow_angle_2d']))}° / 3D {int(round(analysis['elbow_angle_3d']))}°"
        )
    elif analysis.get("constraint_reason"):
        lines.append(f"当前阻断原因：{analysis['constraint_reason']}")
    return lines


def build_action_lines(exercise_key, feedback_stage, analysis, display_angle, hold_seconds):
    profile = ACTION_PROFILES[exercise_key]
    angle_gap = max(0.0, profile["target_angle"] - display_angle)

    if feedback_stage == "low_visibility":
        return [
            f"{analysis['arm_name']}关键点不完整，请先调整位置",
            "请把双肩、手肘和手腕都放进镜头里",
        ], {
            "text_fill": (255, 248, 235, 255),
            "panel_fill": (145, 64, 33, 210),
            "outline_fill": (255, 190, 120, 255),
        }

    if feedback_stage == "adjust_view":
        if profile["view"] == "front":
            action_lines = [
                "请尽量正面对着摄像头，再继续训练",
                "双肩尽量摆正，不要斜着站，这样角度会更准",
            ]
        else:
            action_lines = [
                "请把身体转成侧身，再继续训练",
                "肩线不要正对镜头，这样更适合这个动作",
            ]
        return action_lines, {
            "text_fill": (255, 251, 235, 255),
            "panel_fill": (122, 88, 17, 208),
            "outline_fill": (255, 222, 120, 255),
        }

    if feedback_stage == "straighten_arm":
        return [
            "请先把手臂尽量伸直，再继续这个动作",
            f"{profile['movement_hint']}，手臂越直角度越准",
        ], {
            "text_fill": (255, 248, 235, 255),
            "panel_fill": (120, 74, 24, 208),
            "outline_fill": (255, 205, 120, 255),
        }

    if feedback_stage == "keep_torso":
        return [
            "请先把躯干稳住，不要歪身子代偿",
            "身子越稳，肩关节角度判断越准确",
        ], {
            "text_fill": (255, 248, 235, 255),
            "panel_fill": (120, 74, 24, 208),
            "outline_fill": (255, 205, 120, 255),
        }

    if feedback_stage == "keep_upper_arm":
        return [
            "请让大臂继续贴住身体，不要跟着抬起来",
            "保持上臂稳定，只让前臂向外旋开",
        ], {
            "text_fill": (255, 248, 235, 255),
            "panel_fill": (120, 74, 24, 208),
            "outline_fill": (255, 205, 120, 255),
        }

    if feedback_stage == "keep_elbow_90":
        return [
            "请先把肘关节摆到大约 90°，再继续外旋",
            "肘角越接近九十度，这个动作的识别越稳定",
        ], {
            "text_fill": (255, 248, 235, 255),
            "panel_fill": (120, 74, 24, 208),
            "outline_fill": (255, 205, 120, 255),
        }

    if feedback_stage == "correct_plane":
        return [
            profile["plane_hint"],
            "先把动作方向摆正，再慢慢做会更稳更准",
        ], {
            "text_fill": (255, 248, 235, 255),
            "panel_fill": (120, 74, 24, 208),
            "outline_fill": (255, 205, 120, 255),
        }

    if feedback_stage == "rest":
        return [
            "保持完成，可以慢慢回到起始位休息",
            "放下时也请慢一点，不要突然松手",
        ], {
            "text_fill": (235, 255, 242, 255),
            "panel_fill": (20, 112, 71, 210),
            "outline_fill": (122, 255, 185, 255),
        }

    if feedback_stage in ("target", "hold"):
        remaining_seconds = max(0.0, profile["hold_goal_seconds"] - hold_seconds)
        return [
            "达标了，保持住，继续加油",
            f"再坚持 {remaining_seconds:.1f} 秒，就可以慢慢放松",
        ], {
            "text_fill": (235, 255, 242, 255),
            "panel_fill": (20, 112, 71, 210),
            "outline_fill": (122, 255, 185, 255),
        }

    if exercise_key == "external_rotation":
        second_line = f"距离目标还差 {angle_gap:.0f}°，前臂继续向外旋开一点"
    else:
        second_line = f"距离目标还差 {angle_gap:.0f}°，不用着急，动作稳一点更重要"

    return [
        profile["movement_hint"],
        second_line,
    ], {
        "text_fill": (255, 248, 235, 255),
        "panel_fill": (120, 74, 24, 208),
        "outline_fill": (255, 205, 120, 255),
    }


def clip_normalized_point(point, margin=0.02):
    return np.array(
        [
            float(np.clip(point[0], margin, 1.0 - margin)),
            float(np.clip(point[1], margin, 1.0 - margin)),
        ]
    )


def to_pixel(point, frame_width, frame_height):
    clipped_point = clip_normalized_point(point)
    return tuple(
        np.round(clipped_point * np.array([frame_width - 1, frame_height - 1])).astype(int)
    )


def draw_tracked_arm(image, shoulder_xy, elbow_xy, wrist_xy, color):
    frame_height, frame_width = image.shape[:2]
    shoulder_pixel = to_pixel(shoulder_xy, frame_width, frame_height)
    elbow_pixel = to_pixel(elbow_xy, frame_width, frame_height)
    wrist_pixel = to_pixel(wrist_xy, frame_width, frame_height)

    cv2.line(image, shoulder_pixel, elbow_pixel, color, 5, cv2.LINE_AA)
    cv2.line(image, elbow_pixel, wrist_pixel, color, 5, cv2.LINE_AA)
    cv2.circle(image, shoulder_pixel, 7, color, -1, cv2.LINE_AA)
    cv2.circle(image, elbow_pixel, 8, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(image, elbow_pixel, 11, color, 2, cv2.LINE_AA)
    cv2.circle(image, wrist_pixel, 7, color, -1, cv2.LINE_AA)


def draw_progress_bar(image, top_left, width, height, progress, fill_color):
    x, y = top_left
    progress = float(np.clip(progress, 0.0, 1.0))
    cv2.rectangle(image, (x, y), (x + width, y + height), (40, 52, 72), -1)
    cv2.rectangle(image, (x, y), (x + int(width * progress), y + height), fill_color, -1)
    cv2.rectangle(image, (x, y), (x + width, y + height), (255, 255, 255), 2)


def get_camera_index_candidates():
    if CAMERA_INDEX is not None:
        try:
            return [int(CAMERA_INDEX)]
        except ValueError:
            print(f"⚠️ CAMERA_INDEX={CAMERA_INDEX!r} 不是有效整数，将回退到自动选择。")

    indices = list(range(max(1, CAMERA_MAX_PROBE_INDEX)))
    if sys.platform == "darwin" and PREFER_MAC_BUILTIN_CAMERA:
        preferred = [1, 0]
        remaining = [index for index in indices if index not in preferred]
        return preferred + remaining
    return indices


def get_camera_backend_candidates():
    if sys.platform == "darwin":
        return [("AVFoundation", cv2.CAP_AVFOUNDATION), ("Default", cv2.CAP_ANY)]
    return [("Default", cv2.CAP_ANY)]


def try_open_camera(index, backend):
    backend_name, backend_id = backend
    cap = (
        cv2.VideoCapture(index, backend_id)
        if backend_id != cv2.CAP_ANY
        else cv2.VideoCapture(index)
    )
    if not cap.isOpened():
        cap.release()
        return None

    for _ in range(10):
        ok, frame = cap.read()
        if ok and frame is not None and frame.size > 0:
            print(f"🎥 已连接摄像头：index={index}，backend={backend_name}")
            return cap
        time.sleep(0.05)

    cap.release()
    return None


def open_preferred_camera():
    for backend in get_camera_backend_candidates():
        for index in get_camera_index_candidates():
            cap = try_open_camera(index, backend)
            if cap is not None:
                return cap

    raise RuntimeError(
        "无法打开可用摄像头。你可以手动指定环境变量 CAMERA_INDEX，例如 CAMERA_INDEX=1。"
    )


def switch_exercise(exercise_key):
    global current_exercise_key

    if exercise_key not in ACTION_PROFILES or exercise_key == current_exercise_key:
        return

    current_exercise_key = exercise_key
    reset_motion_tracking(clear_feedback_stage=True)
    print(f"🔁 已切换到：{ACTION_PROFILES[exercise_key]['name']}")


print("肩关节康复多动作模式已启动。")
print("按键说明：1-前屈  2-外展  3-外旋  4-后伸  |  s-截图  q-退出")

# 打开电脑主摄像头
cap = open_preferred_camera()

# 用于自动截图的计时器变量
last_capture_time = time.time()
capture_interval = 5.0  # 每 5 秒自动截取一张照片

# 开启姿态估计实例
with mp_pose.Pose(
    model_complexity=POSE_MODEL_COMPLEXITY,
    smooth_landmarks=True,
    min_detection_confidence=POSE_MIN_DETECTION_CONFIDENCE,
    min_tracking_confidence=POSE_MIN_TRACKING_CONFIDENCE,
) as pose:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # 1. 图像预处理 (OpenCV默认BGR，MediaPipe需要RGB)
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False

        # 2. 进行骨骼关键点推理
        results = pose.process(image)

        # 3. 图像还原，准备渲染
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        current_time = time.time()
        profile = ACTION_PROFILES[current_exercise_key]
        tracked_arm = TRACK_ARM if TRACK_ARM in ARM_LANDMARKS else None
        tracked_arm_name = get_arm_display_name(tracked_arm)
        feedback_stage = None
        hold_seconds = 0.0
        angle_stable = False
        display_angle = None
        analysis = None
        target_just_reached = False

        if results.pose_landmarks and results.pose_landmarks.landmark:
            image_landmarks = results.pose_landmarks.landmark
            world_landmarks = (
                results.pose_world_landmarks.landmark
                if results.pose_world_landmarks
                else results.pose_landmarks.landmark
            )

            tracked_arm = choose_tracked_arm(image_landmarks)
            tracked_arm_name = get_arm_display_name(tracked_arm)
            view_warning_stage = get_view_warning_stage(
                image_landmarks,
                tracked_arm,
                current_exercise_key,
            )
            analysis = analyze_exercise(
                image_landmarks,
                world_landmarks,
                current_exercise_key,
                tracked_arm,
            )

            display_angle = smooth_primary_angle(analysis["primary_angle"])
            analysis["display_angle"] = display_angle
            evaluation_angle = max(display_angle, analysis["primary_angle"])
            analysis["evaluation_angle"] = evaluation_angle

            analysis["hip_image"] = smooth_normalized_point("hip", analysis["hip_image"])
            analysis["shoulder_image"] = smooth_normalized_point("shoulder", analysis["shoulder_image"])
            analysis["elbow_image"] = smooth_normalized_point("elbow", analysis["elbow_image"])
            analysis["wrist_image"] = smooth_normalized_point("wrist", analysis["wrist_image"])

            if view_warning_stage is not None:
                feedback_stage = view_warning_stage
                reset_motion_tracking()
                maybe_speak_feedback(current_exercise_key, feedback_stage, current_time)
            elif analysis["constraint_stage"] is not None:
                feedback_stage = analysis["constraint_stage"]
                target_reached_time = None
                angle_history.clear()
                maybe_speak_feedback(current_exercise_key, feedback_stage, current_time)
            else:
                update_angle_history(evaluation_angle, current_time)
                angle_stable = is_angle_stable()

                if evaluation_angle >= analysis["target_angle"]:
                    if target_reached_time is None:
                        target_reached_time = current_time
                        target_just_reached = True
                    hold_seconds = current_time - target_reached_time
                else:
                    target_reached_time = None
                    hold_seconds = 0.0

                feedback_stage = get_feedback_stage(
                    evaluation_angle,
                    hold_seconds,
                    analysis["target_angle"],
                    analysis["hold_goal_seconds"],
                )
                maybe_speak_feedback(
                    current_exercise_key,
                    feedback_stage,
                    current_time,
                    target_just_reached=target_just_reached,
                    angle_stable=angle_stable,
                )

            if analysis["shoulder_image"] is not None and analysis["elbow_image"] is not None and analysis["wrist_image"] is not None:
                arm_color = (80, 180, 255)
                if feedback_stage in ("target", "hold", "rest"):
                    arm_color = (70, 220, 120)
                elif feedback_stage in ("adjust_view", "low_visibility", "straighten_arm", "keep_torso", "keep_upper_arm", "keep_elbow_90", "correct_plane"):
                    arm_color = (0, 180, 255)

                draw_tracked_arm(
                    image,
                    analysis["shoulder_image"],
                    analysis["elbow_image"],
                    analysis["wrist_image"],
                    color=arm_color,
                )

                h, w, _ = image.shape
                shoulder_pixel = to_pixel(analysis["shoulder_image"], w, h)
                cv2.putText(
                    image,
                    f"{int(round(display_angle))}deg",
                    (shoulder_pixel[0] + 12, shoulder_pixel[1] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    3,
                    cv2.LINE_AA,
                )
        else:
            reset_motion_tracking()

        if analysis is None:
            info_lines = [
                f"当前动作：{profile['name']}（按 1-4 切换）",
                f"当前监测：{tracked_arm_name}",
                "请先进入画面并露出双肩到手腕",
            ]
            action_lines = [
                "还没有识别到完整人体，请按当前动作要求站位",
                "前屈/后伸建议侧身，外展/外旋建议正面面对摄像头",
            ]
            action_panel_style = {
                "text_fill": (255, 248, 235, 255),
                "panel_fill": (145, 64, 33, 210),
                "outline_fill": (255, 190, 120, 255),
            }
        else:
            info_lines = build_info_lines(
                analysis,
                display_angle,
                hold_seconds,
                feedback_stage,
                angle_stable,
            )
            action_lines, action_panel_style = build_action_lines(
                current_exercise_key,
                feedback_stage,
                analysis,
                display_angle,
                hold_seconds,
            )

        shortcut_lines = [
            f"动作切换：{'  '.join(LEGACY_ACTION_NAMES[action] for action in ACTION_ORDER)}",
            "按 q 退出，按 s 截图保存当前肩关节姿态",
        ]

        painter = OverlayPainter(image)
        painter.draw_panel(
            info_lines,
            (20, 20),
            font_size=24,
            text_fill=(240, 248, 255, 255),
            panel_fill=(15, 23, 42, 196),
            outline_fill=(92, 133, 210, 255),
        )
        painter.draw_panel(
            action_lines,
            (20, image.shape[0] - 170),
            font_size=28,
            **action_panel_style,
        )
        painter.draw_panel(
            shortcut_lines,
            (20, image.shape[0] - 265),
            font_size=22,
            text_fill=(238, 243, 255, 255),
            panel_fill=(46, 55, 81, 188),
            outline_fill=(143, 158, 214, 255),
        )

        # 5. 自动截图逻辑 (每5秒全自动截取并在屏幕上显示倒计时)
        time_elapsed = current_time - last_capture_time
        time_left = capture_interval - time_elapsed
        if time_left > 0:
            painter.draw_panel(
                [f"自动截图倒计时：{int(time_left) + 1} 秒"],
                (image.shape[1] - 290, 20),
                font_size=24,
                text_fill=(235, 255, 242, 255),
                panel_fill=(18, 90, 52, 196),
                outline_fill=(122, 255, 185, 255),
            )

        image = painter.finish()

        if analysis is not None and feedback_stage in ("target", "hold", "rest"):
            draw_progress_bar(
                image,
                (20, 150),
                260,
                18,
                min(hold_seconds / analysis["hold_goal_seconds"], 1.0) if analysis["hold_goal_seconds"] > 0 else 1.0,
                fill_color=(84, 214, 44) if feedback_stage != "rest" else (0, 191, 165),
            )

        if time_elapsed >= capture_interval:
            cv2.imwrite("test_shoulder_pose.jpg", image)
            print("📸 [全自动] 已截取最新肩关节训练姿态，并保存为 'test_shoulder_pose.jpg'。")
            overlay = image.copy()
            cv2.rectangle(overlay, (0, 0), (image.shape[1], image.shape[0]), (255, 255, 255), -1)
            image = cv2.addWeighted(overlay, 0.3, image, 0.7, 0)
            last_capture_time = current_time

        # 6. 显示画面
        cv2.imshow("Shoulder Rehab Coach", image)

        # 按键处理：1-4 切换动作，q 退出，s 截图
        key = cv2.waitKey(10) & 0xFF
        if key == ord("q"):
            break
        if key == ord("s"):
            cv2.imwrite("test_shoulder_pose.jpg", image)
            print("📸 已截取当前肩关节训练姿态，并保存为 'test_shoulder_pose.jpg'。")
        elif key in ACTION_KEY_BINDINGS:
            switch_exercise(ACTION_KEY_BINDINGS[key])

cap.release()
cv2.destroyAllWindows()
