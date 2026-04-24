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

# 膝关节康复目标：屈膝达到 120 度后开始鼓励保持
TARGET_KNEE_FLEXION_ANGLE = 120.0
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
TRACK_LEG = os.getenv("TRACK_LEG", "auto").lower()
SIDE_VIEW_MAX_TORSO_WIDTH_RATIO = 0.55
LANDMARK_VISIBILITY_THRESHOLD = 0.20
FRAME_MARGIN = 0.05
ANGLE_STABLE_WINDOW_SECONDS = 0.7
ANGLE_STABLE_RANGE_DEGREES = 6.0
HOLD_START_SECONDS = 2.0
HOLD_GOAL_SECONDS = float(os.getenv("HOLD_GOAL_SECONDS", "6.0"))
POSE_MIN_DETECTION_CONFIDENCE = float(os.getenv("POSE_MIN_DETECTION_CONFIDENCE", "0.6"))
POSE_MIN_TRACKING_CONFIDENCE = float(os.getenv("POSE_MIN_TRACKING_CONFIDENCE", "0.7"))
POSE_MODEL_COMPLEXITY = int(os.getenv("POSE_MODEL_COMPLEXITY", "1"))
LEG_SWITCH_CONFIRM_FRAMES = int(os.getenv("LEG_SWITCH_CONFIRM_FRAMES", "6"))
LEG_SWITCH_SCORE_MARGIN = float(os.getenv("LEG_SWITCH_SCORE_MARGIN", "0.35"))
DISTAL_SWITCH_CONFIRM_FRAMES = int(os.getenv("DISTAL_SWITCH_CONFIRM_FRAMES", "4"))
DISTAL_LOCK_BONUS = float(os.getenv("DISTAL_LOCK_BONUS", "0.18"))
POINT_SMOOTHING_ALPHA = float(os.getenv("POINT_SMOOTHING_ALPHA", "0.35"))
POINT_SMOOTHING_MAX_STEP = float(os.getenv("POINT_SMOOTHING_MAX_STEP", "0.045"))
ANGLE_SMOOTHING_ALPHA = float(os.getenv("ANGLE_SMOOTHING_ALPHA", "0.30"))
CAMERA_INDEX = os.getenv("CAMERA_INDEX")
CAMERA_MAX_PROBE_INDEX = int(os.getenv("CAMERA_MAX_PROBE_INDEX", "5"))
PREFER_MAC_BUILTIN_CAMERA = os.getenv("PREFER_MAC_BUILTIN_CAMERA", "1") == "1"

FEEDBACK_MESSAGES = {
    "far": [
        "挺好的，咱们慢慢来。先把身子放稳，膝盖再往里弯一点，不着急。",
        "对，就是这样。腿慢慢弯，腰别使劲，哪里疼就先停一下。",
        "先找舒服的劲儿。膝盖一点点往回收，不用一下弯很多。",
    ],
    "mid": [
        "不错，离目标近了。身子别晃，膝盖再慢慢弯一点。",
        "很好，再来一点点。别憋气，慢慢弯，疼了就停。",
        "现在做得挺稳。脚跟跟着动，膝盖再往里收一点。",
    ],
    "close": [
        "快到了，就差一点。别猛用力，再轻轻弯一点。",
        "很好，很接近了。身子稳住，膝盖再往里收一点点。",
        "做得不错，别着急。慢慢弯，慢慢停，动作越稳越好。",
    ],
    "near": [
        "就差一点点了。先别急，再慢慢弯一点点就够了。",
        "快到了，膝盖再轻轻弯一点。别憋气，也别硬拉。",
        "很好，就这个劲儿。再往里收一点点，稳住。",
    ],
    "target": [
        "很好，已经到一百二十度了。先别放下，稳住，慢慢呼吸。",
        "达标了，很棒。现在不用再硬弯了，保持住就行。",
        "标准到了，做得很好。停在这个位置，坚持一下，别憋气。",
    ],
    "hold": [
        "保持得很好，再坚持一下。要是疼得厉害，就慢慢放下来。",
        "很棒，继续稳住。肩膀放松，腰也别使劲。",
        "状态不错，再坚持几秒。慢慢呼吸，不要憋着。",
        "做得好，就这样稳住。累了可以慢慢放下，不要突然松。",
    ],
    "rest": [
        "保持时间到了，做得很好。现在可以慢慢放下腿，休息一下。",
        "这次保持完成了，很棒。请慢慢放下来，放松休息。",
        "已经坚持够了，做得不错。现在慢慢放下腿，准备休息。",
    ],
    "adjust_view": [
        "先调整一下位置。请把身子转成侧面对着摄像头，不要斜着。",
        "现在看角度可能不准。您先侧过身来，调整好了咱们再继续。",
    ],
    "low_visibility": [
        "我现在看这条腿不太准。请稍微调整一下，让双肩到脚都能看清一点。",
        "腿部关键点有点不稳，先别急着做。稍微调整一下位置，把双肩、髋部、膝盖和脚踝都露出来，我再帮您看角度。",
    ],
}

feedback_message_index = {stage: 0 for stage in FEEDBACK_MESSAGES}
last_voice_time = 0.0
last_feedback_stage = None
target_reached_time = None
voice_process = None
active_voice_stage = None
angle_history = deque(maxlen=60)
overlay_font_cache = {}

LEG_LANDMARKS = {
    "left": {
        "hip": mp_pose.PoseLandmark.LEFT_HIP,
        "knee": mp_pose.PoseLandmark.LEFT_KNEE,
    },
    "right": {
        "hip": mp_pose.PoseLandmark.RIGHT_HIP,
        "knee": mp_pose.PoseLandmark.RIGHT_KNEE,
    },
}

LEG_LANDMARK_LABELS = {
    "hip": "髋部",
    "knee": "膝盖",
}

LEG_DISTAL_LANDMARKS = {
    "left": [
        ("ankle", mp_pose.PoseLandmark.LEFT_ANKLE),
        ("heel", mp_pose.PoseLandmark.LEFT_HEEL),
        ("foot_index", mp_pose.PoseLandmark.LEFT_FOOT_INDEX),
    ],
    "right": [
        ("ankle", mp_pose.PoseLandmark.RIGHT_ANKLE),
        ("heel", mp_pose.PoseLandmark.RIGHT_HEEL),
        ("foot_index", mp_pose.PoseLandmark.RIGHT_FOOT_INDEX),
    ],
}

DISTAL_REFERENCE_LABEL = "小腿末端"
DISTAL_PRIORITY_BONUS = {
    "ankle": 0.22,
    "heel": 0.10,
    "foot_index": 0.0,
}

tracking_state = {
    "locked_leg": TRACK_LEG if TRACK_LEG in LEG_LANDMARKS else None,
    "leg_candidate": None,
    "leg_candidate_frames": 0,
    "locked_distal_part": None,
    "distal_candidate": None,
    "distal_candidate_frames": 0,
    "smoothed_points": {
        "hip": None,
        "knee": None,
        "distal": None,
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


def next_feedback_message(stage):
    messages = FEEDBACK_MESSAGES[stage]
    message_index = feedback_message_index[stage] % len(messages)
    feedback_message_index[stage] += 1
    return messages[message_index]


def get_feedback_stage(angle, hold_seconds):
    if angle >= TARGET_KNEE_FLEXION_ANGLE:
        if hold_seconds < HOLD_START_SECONDS:
            return "target"
        if hold_seconds < HOLD_GOAL_SECONDS:
            return "hold"
        return "rest"

    angle_gap = TARGET_KNEE_FLEXION_ANGLE - angle
    if angle_gap <= 5.0:
        return "near"
    if angle_gap <= 15.0:
        return "close"
    if angle_gap <= 35.0:
        return "mid"
    return "far"


def get_landmark(landmarks, landmark_name):
    return landmarks[landmark_name.value]


def get_landmark_xy(landmarks, landmark_name):
    landmark = get_landmark(landmarks, landmark_name)
    return np.array([landmark.x, landmark.y])


def get_landmark_xyz(landmarks, landmark_name):
    landmark = get_landmark(landmarks, landmark_name)
    return np.array([landmark.x, landmark.y, landmark.z])


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


def reset_point_smoothing():
    tracking_state["smoothed_points"] = {
        "hip": None,
        "knee": None,
        "distal": None,
    }
    tracking_state["smoothed_angle"] = None


def reset_distal_tracking():
    tracking_state["locked_distal_part"] = None
    tracking_state["distal_candidate"] = None
    tracking_state["distal_candidate_frames"] = 0


def reset_tracking_filters(reset_locked_leg=False):
    reset_distal_tracking()
    reset_point_smoothing()
    if reset_locked_leg and TRACK_LEG not in LEG_LANDMARKS:
        tracking_state["locked_leg"] = None
        tracking_state["leg_candidate"] = None
        tracking_state["leg_candidate_frames"] = 0


def get_distal_landmark_name(leg_side, part_name):
    for candidate_part_name, landmark_name in LEG_DISTAL_LANDMARKS[leg_side]:
        if candidate_part_name == part_name:
            return landmark_name
    return None


def get_distal_candidate_score(
    landmarks,
    leg_side,
    part_name,
    require_visible=False,
    preferred_part_name=None,
):
    landmark_name = get_distal_landmark_name(leg_side, part_name)
    if landmark_name is None:
        return -1.0

    visible = is_landmark_visible(landmarks, landmark_name)
    if require_visible and not visible:
        return -1.0

    score = get_landmark_visibility(landmarks, landmark_name)
    if is_landmark_in_frame(landmarks, landmark_name):
        score += 0.5

    score += DISTAL_PRIORITY_BONUS.get(part_name, 0.0)
    if preferred_part_name == part_name:
        score += DISTAL_LOCK_BONUS
    return score


def get_leg_score(landmarks, leg_side):
    score = 0.0
    for landmark_name in LEG_LANDMARKS[leg_side].values():
        visibility = get_landmark_visibility(landmarks, landmark_name)
        score += visibility
        if is_landmark_in_frame(landmarks, landmark_name):
            score += 0.5

    _, distal_landmark_name = get_best_distal_landmark(landmarks, leg_side)
    if distal_landmark_name is not None:
        visibility = get_landmark_visibility(landmarks, distal_landmark_name)
        score += visibility
        if is_landmark_in_frame(landmarks, distal_landmark_name):
            score += 0.5
    return score


def choose_tracked_leg(landmarks):
    if TRACK_LEG in LEG_LANDMARKS:
        tracking_state["locked_leg"] = TRACK_LEG
        return TRACK_LEG

    leg_scores = {
        leg_side: get_leg_score(landmarks, leg_side)
        for leg_side in LEG_LANDMARKS
    }
    best_leg = max(leg_scores, key=leg_scores.get)
    locked_leg = tracking_state["locked_leg"]

    if locked_leg not in LEG_LANDMARKS:
        tracking_state["locked_leg"] = best_leg
        tracking_state["leg_candidate"] = None
        tracking_state["leg_candidate_frames"] = 0
        return best_leg

    if best_leg == locked_leg:
        tracking_state["leg_candidate"] = None
        tracking_state["leg_candidate_frames"] = 0
        return locked_leg

    locked_leg_usable = is_leg_usable(landmarks, locked_leg)
    score_gap = leg_scores[best_leg] - leg_scores[locked_leg]
    if locked_leg_usable and score_gap < LEG_SWITCH_SCORE_MARGIN:
        tracking_state["leg_candidate"] = None
        tracking_state["leg_candidate_frames"] = 0
        return locked_leg

    if tracking_state["leg_candidate"] == best_leg:
        tracking_state["leg_candidate_frames"] += 1
    else:
        tracking_state["leg_candidate"] = best_leg
        tracking_state["leg_candidate_frames"] = 1

    required_frames = 2 if not locked_leg_usable else LEG_SWITCH_CONFIRM_FRAMES
    if tracking_state["leg_candidate_frames"] >= required_frames:
        tracking_state["locked_leg"] = best_leg
        tracking_state["leg_candidate"] = None
        tracking_state["leg_candidate_frames"] = 0
        reset_distal_tracking()
        reset_point_smoothing()

    return tracking_state["locked_leg"]


def get_leg_display_name(leg_side):
    if leg_side == "left":
        return "左腿"
    if leg_side == "right":
        return "右腿"
    return "腿部"


def get_best_distal_landmark(
    landmarks,
    leg_side,
    require_visible=False,
    preferred_part_name=None,
):
    best_part_name = None
    best_landmark_name = None
    best_score = -1.0

    for part_name, landmark_name in LEG_DISTAL_LANDMARKS[leg_side]:
        score = get_distal_candidate_score(
            landmarks,
            leg_side,
            part_name,
            require_visible=require_visible,
            preferred_part_name=preferred_part_name,
        )
        if score < 0:
            continue

        if score > best_score:
            best_part_name = part_name
            best_landmark_name = landmark_name
            best_score = score

    return best_part_name, best_landmark_name


def choose_tracked_distal_landmark(landmarks, leg_side, require_visible=False):
    locked_part_name = tracking_state["locked_distal_part"]
    best_part_name, best_landmark_name = get_best_distal_landmark(
        landmarks,
        leg_side,
        require_visible=require_visible,
        preferred_part_name=locked_part_name,
    )

    if best_part_name is None:
        if require_visible:
            reset_distal_tracking()
        return None, None

    if locked_part_name is None:
        tracking_state["locked_distal_part"] = best_part_name
        tracking_state["distal_candidate"] = None
        tracking_state["distal_candidate_frames"] = 0
        return best_part_name, best_landmark_name

    if best_part_name == locked_part_name:
        tracking_state["distal_candidate"] = None
        tracking_state["distal_candidate_frames"] = 0
        return best_part_name, best_landmark_name

    locked_landmark_name = get_distal_landmark_name(leg_side, locked_part_name)
    locked_visible = (
        locked_landmark_name is not None
        and is_landmark_visible(landmarks, locked_landmark_name)
    )
    required_frames = 1 if (require_visible and not locked_visible) else DISTAL_SWITCH_CONFIRM_FRAMES

    if tracking_state["distal_candidate"] == best_part_name:
        tracking_state["distal_candidate_frames"] += 1
    else:
        tracking_state["distal_candidate"] = best_part_name
        tracking_state["distal_candidate_frames"] = 1

    if tracking_state["distal_candidate_frames"] >= required_frames:
        tracking_state["locked_distal_part"] = best_part_name
        tracking_state["distal_candidate"] = None
        tracking_state["distal_candidate_frames"] = 0
        return best_part_name, best_landmark_name

    return locked_part_name, locked_landmark_name


def get_missing_leg_parts(landmarks, leg_side):
    missing_parts = []
    for part_name, landmark_name in LEG_LANDMARKS[leg_side].items():
        if not is_landmark_visible(landmarks, landmark_name):
            missing_parts.append(LEG_LANDMARK_LABELS[part_name])

    _, distal_landmark_name = get_best_distal_landmark(landmarks, leg_side, require_visible=True)
    if distal_landmark_name is None:
        missing_parts.append(DISTAL_REFERENCE_LABEL)
    return missing_parts


def is_leg_usable(landmarks, leg_side):
    required_landmarks = list(LEG_LANDMARKS[leg_side].values())
    _, distal_landmark_name = get_best_distal_landmark(landmarks, leg_side, require_visible=True)
    if distal_landmark_name is None:
        return False

    required_landmarks.append(distal_landmark_name)
    average_visibility = sum(
        get_landmark_visibility(landmarks, item)
        for item in required_landmarks
    ) / len(required_landmarks)

    return (
        all(is_landmark_in_frame(landmarks, item) for item in required_landmarks)
        and average_visibility >= LANDMARK_VISIBILITY_THRESHOLD
    )


def get_view_warning_stage(landmarks, leg_side):
    if not is_leg_usable(landmarks, leg_side):
        return "low_visibility"

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
        return "low_visibility"

    torso_width_ratio = max(shoulder_width, hip_width) / torso_length
    if torso_width_ratio > SIDE_VIEW_MAX_TORSO_WIDTH_RATIO:
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


def get_stage_group(stage):
    if stage in ("far", "mid", "close", "near"):
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


def maybe_speak_feedback(stage, current_time, angle=None, target_just_reached=False, angle_stable=True):
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

    if speak(next_feedback_message(stage), stage=stage):
        last_voice_time = current_time
        last_feedback_stage = stage


def calculate_angle(a, b, c):
    """
    计算三个点之间的夹角 (a, b, c 分别为髋, 膝(顶点), 小腿末端参考点的坐标，支持 2D 或 3D)
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b
    denominator = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denominator == 0:
        return 0.0

    cosine_angle = np.dot(ba, bc) / denominator
    angle = np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0)))

    # 计算小腿与大腿延长线的夹角 (互补角: 当腿伸直时理论上是0度)
    extension_angle = 180.0 - angle
    return extension_angle


def smooth_normalized_point(point_key, point):
    if point is None:
        tracking_state["smoothed_points"][point_key] = None
        return None

    point = clip_normalized_point(point, margin=0.0)
    previous_point = tracking_state["smoothed_points"].get(point_key)
    if previous_point is None:
        smoothed_point = point
    else:
        step = (point - previous_point) * POINT_SMOOTHING_ALPHA
        step_norm = np.linalg.norm(step)
        if step_norm > POINT_SMOOTHING_MAX_STEP:
            step = step / step_norm * POINT_SMOOTHING_MAX_STEP
        smoothed_point = clip_normalized_point(previous_point + step, margin=0.0)

    tracking_state["smoothed_points"][point_key] = smoothed_point
    return smoothed_point


def smooth_angle_value(angle):
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


def rotate_vector(vector, degrees):
    radians = np.radians(degrees)
    rotation_matrix = np.array(
        [
            [np.cos(radians), -np.sin(radians)],
            [np.sin(radians), np.cos(radians)],
        ]
    )
    return rotation_matrix @ vector


def get_guidance_rotation_sign(thigh_unit, shank_unit, leg_side):
    cross = (thigh_unit[0] * shank_unit[1]) - (thigh_unit[1] * shank_unit[0])
    if abs(cross) > 1e-4:
        return 1.0 if cross > 0 else -1.0

    if abs(shank_unit[0]) > 0.02:
        return 1.0 if shank_unit[0] > 0 else -1.0

    return 1.0 if leg_side == "right" else -1.0


def get_target_distal_position(hip_xy, knee_xy, distal_xy, leg_side):
    thigh_vector = hip_xy - knee_xy
    shank_vector = distal_xy - knee_xy
    thigh_length = np.linalg.norm(thigh_vector)
    shank_length = np.linalg.norm(shank_vector)
    if thigh_length == 0 or shank_length == 0:
        return None

    thigh_unit = thigh_vector / thigh_length
    shank_unit = shank_vector / shank_length
    target_inner_angle = max(10.0, 180.0 - TARGET_KNEE_FLEXION_ANGLE)
    rotation_sign = get_guidance_rotation_sign(thigh_unit, shank_unit, leg_side)
    target_shank_unit = rotate_vector(thigh_unit, rotation_sign * target_inner_angle)
    desired_distal = knee_xy + target_shank_unit * shank_length
    return clip_normalized_point(desired_distal)


def describe_screen_direction(delta):
    horizontal = ""
    vertical = ""

    if delta[0] < -0.03:
        horizontal = "左"
    elif delta[0] > 0.03:
        horizontal = "右"

    if delta[1] < -0.03:
        vertical = "上"
    elif delta[1] > 0.03:
        vertical = "下"

    if horizontal and vertical:
        return f"屏幕{horizontal}{vertical}方"
    if horizontal:
        return f"屏幕{horizontal}侧"
    if vertical:
        return f"屏幕{vertical}方"
    return ""


def build_direction_hint(current_distal, target_distal):
    delta = target_distal - current_distal
    direction_text = describe_screen_direction(delta)
    if direction_text:
        return f"小腿继续向{direction_text}收，尽量贴近辅助线"
    return "小腿沿箭头和辅助线方向继续收回来，慢慢屈膝"


def draw_dashed_line(image, start_point, end_point, color, thickness=2, dash_length=14):
    start = np.array(start_point, dtype=float)
    end = np.array(end_point, dtype=float)
    line_length = np.linalg.norm(end - start)
    if line_length == 0:
        return

    direction = (end - start) / line_length
    dash_step = dash_length * 2
    for offset in np.arange(0, line_length, dash_step):
        dash_start = start + direction * offset
        dash_end = start + direction * min(offset + dash_length, line_length)
        cv2.line(
            image,
            tuple(np.round(dash_start).astype(int)),
            tuple(np.round(dash_end).astype(int)),
            color,
            thickness,
            cv2.LINE_AA,
        )


def draw_tracked_leg(image, hip_xy, knee_xy, distal_xy, color):
    frame_height, frame_width = image.shape[:2]
    hip_pixel = to_pixel(hip_xy, frame_width, frame_height)
    knee_pixel = to_pixel(knee_xy, frame_width, frame_height)
    distal_pixel = to_pixel(distal_xy, frame_width, frame_height)

    cv2.line(image, hip_pixel, knee_pixel, color, 5, cv2.LINE_AA)
    cv2.line(image, knee_pixel, distal_pixel, color, 5, cv2.LINE_AA)
    cv2.circle(image, hip_pixel, 7, color, -1, cv2.LINE_AA)
    cv2.circle(image, knee_pixel, 8, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(image, knee_pixel, 11, color, 2, cv2.LINE_AA)
    cv2.circle(image, distal_pixel, 7, color, -1, cv2.LINE_AA)


def draw_knee_guidance(image, hip_xy, knee_xy, distal_xy, leg_side):
    frame_height, frame_width = image.shape[:2]
    draw_tracked_leg(image, hip_xy, knee_xy, distal_xy, color=(80, 180, 255))

    target_distal = get_target_distal_position(hip_xy, knee_xy, distal_xy, leg_side)
    if target_distal is None:
        return None

    knee_pixel = to_pixel(knee_xy, frame_width, frame_height)
    distal_pixel = to_pixel(distal_xy, frame_width, frame_height)
    target_distal_pixel = to_pixel(target_distal, frame_width, frame_height)

    draw_dashed_line(image, knee_pixel, target_distal_pixel, (0, 230, 255), thickness=3)
    cv2.circle(image, target_distal_pixel, 10, (0, 230, 255), 2, cv2.LINE_AA)

    if np.linalg.norm(np.array(target_distal_pixel) - np.array(distal_pixel)) > 18:
        cv2.arrowedLine(
            image,
            distal_pixel,
            target_distal_pixel,
            (0, 255, 170),
            4,
            cv2.LINE_AA,
            tipLength=0.22,
        )

    return build_direction_hint(distal_xy, target_distal)


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

        # 4. 提取关键点并计算角度
        current_time = time.time()
        tracked_leg = TRACK_LEG if TRACK_LEG in LEG_LANDMARKS else None
        tracked_leg_name = get_leg_display_name(tracked_leg)
        tracked_landmarks = LEG_LANDMARKS[tracked_leg] if tracked_leg in LEG_LANDMARKS else None
        view_warning_stage = None
        missing_parts = []
        feedback_stage = None
        guidance_text = ""
        hold_seconds = 0.0
        angle_stable = False
        angle = None
        knee_image = None
        hip_image = None
        distal_image = None

        if results.pose_landmarks and results.pose_landmarks.landmark:
            landmarks = results.pose_landmarks.landmark
            tracked_leg = choose_tracked_leg(landmarks)
            tracked_leg_name = get_leg_display_name(tracked_leg)
            tracked_landmarks = LEG_LANDMARKS[tracked_leg]
            missing_parts = get_missing_leg_parts(landmarks, tracked_leg)
            view_warning_stage = get_view_warning_stage(landmarks, tracked_leg)
            _, distal_landmark_name = choose_tracked_distal_landmark(
                landmarks,
                tracked_leg,
                require_visible=(view_warning_stage is None),
            )

            hip_image = get_landmark_xy(landmarks, tracked_landmarks["hip"])
            knee_image = get_landmark_xy(landmarks, tracked_landmarks["knee"])
            if distal_landmark_name is not None:
                distal_image = get_landmark_xy(landmarks, distal_landmark_name)

            if results.pose_world_landmarks and distal_landmark_name is not None:
                angle_landmarks = results.pose_world_landmarks.landmark
                hip = get_landmark_xyz(angle_landmarks, tracked_landmarks["hip"])
                knee = get_landmark_xyz(angle_landmarks, tracked_landmarks["knee"])
                distal_point = get_landmark_xyz(angle_landmarks, distal_landmark_name)
            elif distal_landmark_name is not None:
                hip = hip_image
                knee = knee_image
                distal_point = distal_image

            if distal_landmark_name is None or distal_image is None:
                angle = None
                view_warning_stage = "low_visibility"
            else:
                angle = calculate_angle(hip, knee, distal_point)
                angle = smooth_angle_value(angle)
                hip_image = smooth_normalized_point("hip", hip_image)
                knee_image = smooth_normalized_point("knee", knee_image)
                distal_image = smooth_normalized_point("distal", distal_image)
            target_just_reached = False

            if view_warning_stage is not None or angle is None:
                target_reached_time = None
                angle_history.clear()
                reset_point_smoothing()
                maybe_speak_feedback(view_warning_stage or "low_visibility", current_time)
            else:
                update_angle_history(angle, current_time)
                angle_stable = is_angle_stable()

                if angle >= TARGET_KNEE_FLEXION_ANGLE:
                    if target_reached_time is None:
                        target_reached_time = current_time
                        target_just_reached = True
                    hold_seconds = current_time - target_reached_time
                else:
                    target_reached_time = None
                    hold_seconds = 0.0

                feedback_stage = get_feedback_stage(angle, hold_seconds)
                maybe_speak_feedback(
                    feedback_stage,
                    current_time,
                    angle=angle,
                    target_just_reached=target_just_reached,
                    angle_stable=angle_stable,
                )

                if angle < TARGET_KNEE_FLEXION_ANGLE:
                    guidance_text = draw_knee_guidance(
                        image,
                        hip_image,
                        knee_image,
                        distal_image,
                        tracked_leg,
                    )
                else:
                    draw_tracked_leg(image, hip_image, knee_image, distal_image, color=(70, 220, 120))

            if knee_image is not None and angle is not None:
                frame_height, frame_width = image.shape[:2]
                knee_pixel = to_pixel(knee_image, frame_width, frame_height)
                cv2.putText(
                    image,
                    f"{int(round(angle))}deg",
                    (knee_pixel[0] + 12, knee_pixel[1] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 0, 255),
                    3,
                    cv2.LINE_AA,
                )
        else:
            target_reached_time = None
            angle_history.clear()
            reset_tracking_filters()
            missing_parts = ["髋部", "膝盖", DISTAL_REFERENCE_LABEL]

        info_lines = [f"当前监测：{tracked_leg_name}"]
        if angle is not None:
            info_lines.append(f"屈膝角度：{int(round(angle))}° / 目标：{int(TARGET_KNEE_FLEXION_ANGLE)}°")
            if feedback_stage in ("target", "hold", "rest"):
                info_lines.append(
                    f"保持进度：{min(hold_seconds, HOLD_GOAL_SECONDS):.1f}/{HOLD_GOAL_SECONDS:.1f} 秒"
                )
            elif not angle_stable:
                info_lines.append("动作还在变化，稳定后会更准确")
        else:
            info_lines.append("请先进入画面并露出双肩到脚")

        if results.pose_landmarks is None:
            action_lines = [
                "还没有识别到完整人体，请侧身进入画面",
                "请把双肩、髋部、膝盖和脚踝都放进镜头里",
            ]
            action_panel_style = {
                "text_fill": (255, 248, 235, 255),
                "panel_fill": (145, 64, 33, 210),
                "outline_fill": (255, 190, 120, 255),
            }
        elif view_warning_stage == "low_visibility":
            missing_text = "、".join(missing_parts) if missing_parts else "髋部、膝盖、小腿末端"
            action_lines = [
                f"{tracked_leg_name}关键点不完整，请先调整位置",
                f"当前需要看见：{missing_text}，最好双肩到脚都在镜头里",
            ]
            action_panel_style = {
                "text_fill": (255, 248, 235, 255),
                "panel_fill": (145, 64, 33, 210),
                "outline_fill": (255, 190, 120, 255),
            }
        elif view_warning_stage == "adjust_view":
            action_lines = [
                "请把身体转成侧身，再继续屈膝",
                "肩和髋不要正对镜头，这样角度会更准",
            ]
            action_panel_style = {
                "text_fill": (255, 251, 235, 255),
                "panel_fill": (122, 88, 17, 208),
                "outline_fill": (255, 222, 120, 255),
            }
        elif feedback_stage == "rest":
            action_lines = [
                "保持完成，可以慢慢放下休息",
                "放下时也请慢一点，不要突然松腿",
            ]
            action_panel_style = {
                "text_fill": (235, 255, 242, 255),
                "panel_fill": (20, 112, 71, 210),
                "outline_fill": (122, 255, 185, 255),
            }
        elif feedback_stage in ("target", "hold"):
            remaining_seconds = max(0.0, HOLD_GOAL_SECONDS - hold_seconds)
            action_lines = [
                "达标了，保持住，继续加油",
                f"再坚持 {remaining_seconds:.1f} 秒，就可以放松休息",
            ]
            action_panel_style = {
                "text_fill": (235, 255, 242, 255),
                "panel_fill": (20, 112, 71, 210),
                "outline_fill": (122, 255, 185, 255),
            }
        elif angle is not None:
            angle_gap = max(0.0, TARGET_KNEE_FLEXION_ANGLE - angle)
            action_lines = [
                guidance_text or "小腿沿辅助线方向继续收回来，慢慢屈膝",
                f"距离目标还差 {angle_gap:.0f}°，不用着急，稳一点更重要",
            ]
            action_panel_style = {
                "text_fill": (255, 248, 235, 255),
                "panel_fill": (120, 74, 24, 208),
                "outline_fill": (255, 205, 120, 255),
            }
        else:
            action_lines = [
                "请先侧身站稳，再开始屈膝练习",
                "我会继续帮你看角度和关键点",
            ]
            action_panel_style = {
                "text_fill": (255, 248, 235, 255),
                "panel_fill": (76, 64, 145, 208),
                "outline_fill": (168, 170, 255, 255),
            }

        painter = OverlayPainter(image)
        painter.draw_panel(
            info_lines,
            (20, 20),
            font_size=26,
            text_fill=(240, 248, 255, 255),
            panel_fill=(15, 23, 42, 196),
            outline_fill=(92, 133, 210, 255),
        )
        painter.draw_panel(
            action_lines,
            (20, image.shape[0] - 140),
            font_size=28,
            **action_panel_style,
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

        if feedback_stage in ("target", "hold", "rest"):
            draw_progress_bar(
                image,
                (20, 140),
                260,
                18,
                min(hold_seconds / HOLD_GOAL_SECONDS, 1.0) if HOLD_GOAL_SECONDS > 0 else 1.0,
                fill_color=(84, 214, 44) if feedback_stage != "rest" else (0, 191, 165),
            )

        if time_elapsed >= capture_interval:
            cv2.imwrite('test_pose.jpg', image)
            print("📸 [全自动] 无需按键，已截取最新姿态并覆盖 'test_pose.jpg' 供大模型测试使用！")
            # 屏幕闪烁一下（画一个白色的半透明层）
            overlay = image.copy()
            cv2.rectangle(overlay, (0, 0), (image.shape[1], image.shape[0]), (255, 255, 255), -1)
            image = cv2.addWeighted(overlay, 0.3, image, 0.7, 0)
            
            # 重置计时器
            last_capture_time = current_time

        # 6. 显示画面
        cv2.imshow('Knee Angle PoC', image)
        
        # 按 'q' 键退出，按 's' 键手动截取
        key = cv2.waitKey(10) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            cv2.imwrite('test_pose.jpg', image)
            print("📸 已截取当前姿态并保存为 'test_pose.jpg'，你可以用它来测试大模型的评估效果！")

cap.release()
cv2.destroyAllWindows()
