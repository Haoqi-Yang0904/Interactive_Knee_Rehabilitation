#!/usr/bin/env python3
"""
Cross-platform desktop knee rehabilitation session.

This script runs a complete knee rehab training sequence with OpenCV,
MediaPipe pose landmarks, and local cached voice prompts:

ankle pump -> quadriceps isometric -> hamstring isometric ->
supine straight leg raise -> side lying hip abduction ->
prone hip extension -> supine knee flexion -> bed knee flexion -> summary.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import math
import os
import signal
import re
import shutil
import subprocess
import sys
import threading
import time
import warnings
from collections import deque
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from rehab_actions.knee_desktop_library import (
    DEFAULT_TARGET_UNITS,
    SIDE_REMAINING_EXERCISE_IDS,
    Exercise,
    collect_short_voice_texts,
    select_exercises,
)


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

WINDOW_NAME = "Knee Rehab Desktop Session"
WEB_STREAM_DIR: Path | None = None
WEB_LATEST_FRAME_PATH: Path | None = None
WEB_COMMAND_PATH: Path | None = None
WEB_PAUSE_PATH: Path | None = None
WEB_STATUS_PATH: Path | None = None
WEB_STREAM_FPS = 15.0
WEB_STREAM_WIDTH = 800
WEB_JPEG_QUALITY = 68
WEB_FRAME_SEQ = 0
WEB_LAST_FRAME_TIME = 0.0
WEB_FPS_SMOOTH = 0.0
WEB_STATUS_CONTEXT: dict[str, object] = {}
WEB_PUBLISHER: "WebFramePublisher | None" = None
WEB_STATUS_LAST_WRITE_TIME = 0.0
WEB_STATUS_MIN_INTERVAL = 0.3
WEB_STATUS_LOCK = threading.Lock()
SESSION_CONFIG: dict[str, object] | None = None
SESSION_ACTION_CONFIGS: dict[str, dict[str, object]] = {}
OUTPUT_DIR_OVERRIDE: Path | None = None
MIN_LANDMARK_VISIBILITY = 0.20
LANDMARK_FRAME_MARGIN = 0.05
LEG_SWITCH_SCORE_MARGIN = 0.35
SIDE_VIEW_MAX_TORSO_WIDTH_RATIO = 0.55
DISTAL_SWITCH_CONFIRM_FRAMES = 4
DISTAL_LOCK_BONUS = 0.18
DISTAL_PRIORITY_BONUS = {
    "ankle": 0.22,
    "heel": 0.10,
    "foot_index": 0.0,
}
DEFAULT_VOICE_RATE = 145
DEFAULT_CAMERA_INDEX = -1
DEFAULT_EDGE_VOICE = "zh-CN-XiaoxiaoNeural"
DEFAULT_EDGE_RATE = "-10%"
DEFAULT_EDGE_VOLUME = "+0%"
DEFAULT_VOICE_CACHE_DIR = Path("feedback_audio") / "knee_desktop_session"
EDGE_TTS_ITEM_TIMEOUT_SECONDS = 20.0
DEFAULT_REACTION_SECONDS = 2.0
DEFAULT_LEG_LENGTH_CM = 80.0
VISUAL_START_HOLD_SECONDS = 1.0
VISUAL_RETURN_HOLD_SECONDS = 0.5
VISUAL_SIDE_LOCK_FRAMES = 6
VISUAL_MISSING_TOLERANCE_FRAMES = 10
START_STABILITY_RATIO = 0.035
ISOMETRIC_START_STABILITY_RATIO = 0.07
KNEE_STRAIGHT_MIN_DEGREES = 150.0
VISUAL_KNEE_STRAIGHT_MIN_DEGREES = 135.0
VISUAL_KNEE_BASELINE_ALLOWANCE_DEGREES = 16.0
VISUAL_KNEE_LINE_MAX_RATIO = 0.12
VISUAL_KNEE_BENT_CONFIRM_SECONDS = 0.9
VISUAL_KNEE_WARNING_REPEAT_SECONDS = 8.0
UPPER_LEG_Y_SWITCH_MARGIN = 0.04
VISUAL_BASELINE_HORIZONTAL_SNAP_MIN_X = 0.55
VISUAL_TARGET_CONFIRM_SECONDS = 0.25
VISUAL_HOLD_DROP_RATIO = 0.65
VISUAL_HOLD_GRACE_SECONDS = 0.8
VISUAL_RETURN_RATIO_FRACTION = 0.35
VISUAL_RETURN_RATIO_MULTIPLIER = 1.5
VISUAL_RETURN_ANGLE_FRACTION = 0.45
VISUAL_RETURN_MIN_ANGLE_DEGREES = 3.0
FLEXION_START_MAX_DEGREES = 12.0
FLEXION_RETURN_MAX_DEGREES = 15.0
ISOMETRIC_START_HOLD_SECONDS = 1.0
LOOSE_ISOMETRIC_START_EXERCISE_IDS = {
    "quadriceps_isometric",
    "hamstring_isometric",
}
ANGLE_ONLY_VISUAL_EXERCISE_IDS = {
    "supine_straight_leg_raise",
    "side_lying_hip_abduction",
    "prone_hip_extension",
}
SIDE_ABDUCTION_SETUP_PROMPT = "请侧躺在床面上，患侧腿在上，健侧腿在下，脸朝向镜头。"
PRONE_EXTENSION_SETUP_PROMPT = "请俯卧在床上，让患侧腿朝向镜头。"
VOICE_REPEAT_SECONDS = 5.0
ANKLE_READY_STABLE_FRAMES = 8
ANKLE_MIN_CYCLE_SAMPLES = 8
ANKLE_JUMP_REJECT_DEGREES = 28.0
ANKLE_FILTER_MISSING_TOLERANCE_FRAMES = 5
ANGLE_STABLE_WINDOW_SECONDS = 0.7
ANGLE_STABLE_RANGE_DEGREES = 6.0
ANGLE_TARGET_CONFIRM_SECONDS = 0.35
BED_MAX_LIFT_MIN_DEGREES = 10.0
BED_MAX_FLEXION_MIN_DEGREES = 25.0
BED_HOLD_STABILITY_MAX_RANGE_DEGREES = 8.0
INTERRUPT_POLL_SECONDS = 0.03
CAMERA_READ_RETRY_ATTEMPTS = 3
CAMERA_READ_RETRY_SLEEP_SECONDS = 0.03
CAMERA_READ_MAX_CONSECUTIVE_FAILURES = 30
SAPI_SPEAK_ASYNC = 1
SAPI_PURGE_BEFORE_SPEAK = 2
LEG_GOOD_COLOR = (80, 220, 120)
LEG_NEEDS_WORK_COLOR = (0, 220, 255)
GUIDE_BLUE = (255, 170, 40)
GUIDE_ARROW_BLUE = (255, 210, 80)

FONT_CANDIDATES = [
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyhbd.ttc",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simhei.ttf",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simsun.ttc",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "Deng.ttf",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts" / "NotoSansCJK-Regular.ttc",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts" / "NotoSansSC-Regular.otf",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
]

mp_pose = mp.solutions.pose

STOP_REQUESTED = False
ACTIVE_SPEAKER = None


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_macos() -> bool:
    return sys.platform == "darwin"


def system_voice_label() -> str:
    if is_windows():
        return "Windows SAPI"
    if is_macos():
        return "macOS say"
    return "系统语音"


def request_stop(_signum=None, _frame=None) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    if ACTIVE_SPEAKER is not None:
        ACTIVE_SPEAKER.stop()


def stop_requested() -> bool:
    return STOP_REQUESTED


def sleep_interruptible(seconds: float) -> None:
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline and not stop_requested():
        time.sleep(min(INTERRUPT_POLL_SECONDS, deadline - time.monotonic()))


@dataclass
class ExerciseRuntimeResult:
    exercise_id: str
    exercise_name: str
    mode: str
    target_units: int
    completed_units: int
    status: str
    duration_seconds: float
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)
    achievement_percent: float | None = None

    @property
    def achievement_rate(self) -> float:
        if self.achievement_percent is not None:
            return max(0.0, min(float(self.achievement_percent), 100.0))
        if self.target_units <= 0:
            return 0.0
        return min(self.completed_units / self.target_units, 1.0) * 100.0


@dataclass
class LegPoints:
    side: str
    hip: np.ndarray
    knee: np.ndarray
    ankle: np.ndarray
    ankle_visible: bool
    heel: np.ndarray | None
    foot_index: np.ndarray | None
    distal: np.ndarray
    distal_part: str
    profile_score: float

    @property
    def leg_length(self) -> float:
        return max(
            float(np.linalg.norm(self.hip - self.knee) + np.linalg.norm(self.knee - self.distal)),
            1.0,
        )


@dataclass
class TrackedLegState:
    locked_side: str | None = None
    candidate_side: str | None = None
    candidate_frames: int = 0
    missing_frames: int = 0
    locked_distal_part: str | None = None
    distal_candidate: str | None = None
    distal_candidate_frames: int = 0

    def reset(self) -> None:
        self.locked_side = None
        self.candidate_side = None
        self.candidate_frames = 0
        self.missing_frames = 0
        self.locked_distal_part = None
        self.distal_candidate = None
        self.distal_candidate_frames = 0


def edge_tts_is_available() -> bool:
    return importlib.util.find_spec("edge_tts") is not None


def pygame_is_available() -> bool:
    return importlib.util.find_spec("pygame") is not None


def windows_sapi_is_available() -> bool:
    return (
        is_windows()
        and importlib.util.find_spec("pythoncom") is not None
        and importlib.util.find_spec("win32com") is not None
    )


def sanitize_voice_text(text: str) -> str:
    return " ".join(text.strip().split())


def voice_cache_path(
    text: str,
    *,
    cache_dir: Path,
    edge_voice: str,
    edge_rate: str,
    edge_volume: str,
) -> Path:
    key = f"{edge_voice}|{edge_rate}|{edge_volume}|{sanitize_voice_text(text)}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return cache_dir / f"{digest}.mp3"


async def generate_edge_tts_file(
    text: str,
    output_path: Path,
    *,
    edge_voice: str,
    edge_rate: str,
    edge_volume: str,
) -> None:
    import edge_tts

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".part.mp3")
    communicate = edge_tts.Communicate(
        sanitize_voice_text(text),
        edge_voice,
        rate=edge_rate,
        volume=edge_volume,
    )
    await communicate.save(str(temp_path))
    temp_path.replace(output_path)


async def prepare_voice_cache(
    texts: list[str],
    *,
    cache_dir: Path,
    edge_voice: str,
    edge_rate: str,
    edge_volume: str,
) -> tuple[int, int, int]:
    if not edge_tts_is_available():
        raise RuntimeError("当前环境没有安装 edge-tts，无法生成神经语音缓存。")

    unique_texts = sorted({sanitize_voice_text(text) for text in texts if sanitize_voice_text(text)})
    generated = 0
    skipped = 0
    failed = 0

    for index, text in enumerate(unique_texts, start=1):
        output_path = voice_cache_path(
            text,
            cache_dir=cache_dir,
            edge_voice=edge_voice,
            edge_rate=edge_rate,
            edge_volume=edge_volume,
        )
        if output_path.exists() and output_path.stat().st_size > 0:
            skipped += 1
            continue
        print(f"生成语音 {index}/{len(unique_texts)}：{text[:42]}", flush=True)
        try:
            await asyncio.wait_for(
                generate_edge_tts_file(
                    text,
                    output_path,
                    edge_voice=edge_voice,
                    edge_rate=edge_rate,
                    edge_volume=edge_volume,
                ),
                timeout=EDGE_TTS_ITEM_TIMEOUT_SECONDS,
            )
            generated += 1
        except Exception as exc:
            failed += 1
            temp_path = output_path.with_suffix(".part.mp3")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            print(f"语音生成失败，训练时会使用系统语音兜底：{text[:36]}；{exc}", flush=True)

    return generated, skipped, failed


class Speaker:
    def __init__(
        self,
        enabled: bool = True,
        rate: int = DEFAULT_VOICE_RATE,
        requested_voice: str | None = None,
        cache_dir: Path = DEFAULT_VOICE_CACHE_DIR,
        use_edge_cache: bool = True,
        edge_voice: str = DEFAULT_EDGE_VOICE,
        edge_rate: str = DEFAULT_EDGE_RATE,
        edge_volume: str = DEFAULT_EDGE_VOLUME,
    ) -> None:
        self.enabled = enabled
        self.rate = str(rate)
        self.say_path = shutil.which("say") if is_macos() else None
        self.voice = self._select_macos_chinese_voice(requested_voice)
        self.sapi_speaker = None
        self.sapi_voice_name = self._init_windows_sapi(requested_voice)
        self.process: subprocess.Popen | None = None
        self.cache_dir = cache_dir
        self.use_edge_cache = use_edge_cache and edge_tts_is_available() and pygame_is_available()
        self.edge_voice = edge_voice
        self.edge_rate = edge_rate
        self.edge_volume = edge_volume
        self._pygame = None

        if self.enabled and self.use_edge_cache:
            print(f"语音播报：优先使用本地 edge-tts 缓存，音色 {self.edge_voice}。")
        if self.enabled and self.sapi_speaker is not None:
            print(f"语音播报兜底：Windows SAPI {self.sapi_voice_name}，语速 {self._windows_sapi_rate()}")
        elif self.enabled and self.say_path:
            if self.voice:
                print(f"语音播报兜底：macOS 中文音色 {self.voice}，语速 {self.rate}")
            else:
                print("语音播报兜底：未找到 zh_CN 中文音色，将使用系统默认音色。")
        elif self.enabled and not self.use_edge_cache:
            print(f"语音播报兜底不可用：未找到可用的{system_voice_label()}。")

    def _available_voices(self) -> list[tuple[str, str]]:
        if not self.say_path:
            return []
        try:
            output = subprocess.run(
                [self.say_path, "-v", "?"],
                check=False,
                capture_output=True,
                text=True,
            ).stdout
        except Exception:
            return []

        voices: list[tuple[str, str]] = []
        for line in output.splitlines():
            match = re.match(r"^(.*?)\s+([a-z]{2}_[A-Z]{2})\s+#", line)
            if match:
                voices.append((match.group(1).strip(), match.group(2)))
        return voices

    def _select_macos_chinese_voice(self, requested_voice: str | None) -> str | None:
        voices = self._available_voices()
        if not voices:
            return None

        if requested_voice:
            requested = requested_voice.strip().lower()
            for voice, _locale in voices:
                if voice.lower() == requested:
                    return voice
            return requested_voice.strip()

        preferred = [
            "Tingting",
            "Eddy (中文（中国大陆）)",
            "Flo (中文（中国大陆）)",
            "Grandma (中文（中国大陆）)",
            "Grandpa (中文（中国大陆）)",
            "Reed (中文（中国大陆）)",
            "Sandy (中文（中国大陆）)",
            "Shelley (中文（中国大陆）)",
        ]
        for voice in preferred:
            if any(available_voice == voice for available_voice, _locale in voices):
                return voice

        for voice, locale in voices:
            if locale == "zh_CN":
                return voice
        for voice, locale in voices:
            if locale.startswith("zh_"):
                return voice
        return None

    def _windows_sapi_rate(self) -> int:
        try:
            numeric_rate = int(self.rate)
        except ValueError:
            numeric_rate = DEFAULT_VOICE_RATE
        # SAPI uses -10..10. Map the user-facing say-style range roughly around default 145 -> 0.
        return max(-10, min(10, int(round((numeric_rate - DEFAULT_VOICE_RATE) / 7.0))))

    def _init_windows_sapi(self, requested_voice: str | None) -> str | None:
        if not self.enabled or not windows_sapi_is_available():
            return None
        try:
            import pythoncom
            from win32com.client import Dispatch

            pythoncom.CoInitialize()
            self.sapi_speaker = Dispatch("SAPI.SpVoice")
            self.sapi_speaker.Rate = self._windows_sapi_rate()
            self.sapi_speaker.Volume = 100
            return self._select_windows_chinese_voice(requested_voice)
        except Exception as exc:
            print(f"Windows SAPI 初始化失败，将只使用语音缓存或静音兜底：{exc}")
            self.sapi_speaker = None
            return None

    def _select_windows_chinese_voice(self, requested_voice: str | None) -> str:
        if self.sapi_speaker is None:
            return "不可用"

        requested = requested_voice.strip().lower() if requested_voice else ""
        fallback_voice = None
        try:
            voices = self.sapi_speaker.GetVoices()
            for index in range(voices.Count):
                voice = voices.Item(index)
                description = voice.GetDescription()
                language = voice.GetAttribute("Language")
                is_chinese = "804" in language.lower() or "chinese" in description.lower()

                if requested and requested in description.lower():
                    self.sapi_speaker.Voice = voice
                    return description

                if fallback_voice is None and is_chinese:
                    fallback_voice = voice

            if fallback_voice is not None:
                self.sapi_speaker.Voice = fallback_voice
                return fallback_voice.GetDescription()
        except Exception:
            pass

        try:
            return self.sapi_speaker.Voice.GetDescription()
        except Exception:
            return "Windows 默认语音"

    def speak(self, text: str, *, interrupt: bool = True) -> None:
        self._speak(text, interrupt=interrupt, wait=False)

    def speak_and_wait(
        self,
        text: str,
        *,
        interrupt: bool = True,
        reaction_seconds: float = 0.0,
    ) -> None:
        self._speak(text, interrupt=interrupt, wait=True)
        if reaction_seconds > 0:
            sleep_interruptible(reaction_seconds)

    def _speak(self, text: str, *, interrupt: bool, wait: bool) -> None:
        text = sanitize_voice_text(text)
        if stop_requested() or not self.enabled or not text:
            return

        if self.use_edge_cache and self._speak_cached_edge(text, interrupt=interrupt, wait=wait):
            return

        self._speak_system(text, interrupt=interrupt, wait=wait)

    def _speak_cached_edge(self, text: str, *, interrupt: bool, wait: bool) -> bool:
        audio_path = voice_cache_path(
            text,
            cache_dir=self.cache_dir,
            edge_voice=self.edge_voice,
            edge_rate=self.edge_rate,
            edge_volume=self.edge_volume,
        )
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            return False

        try:
            pygame = self._ensure_pygame()
            if pygame.mixer.music.get_busy():
                if not interrupt:
                    return True
                pygame.mixer.music.stop()
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
            if wait:
                while pygame.mixer.music.get_busy() and not stop_requested():
                    time.sleep(INTERRUPT_POLL_SECONDS)
                if stop_requested():
                    pygame.mixer.music.stop()
                    try:
                        pygame.mixer.music.unload()
                    except Exception:
                        pass
            return True
        except Exception as exc:
            print(f"缓存语音播放失败，回退到系统语音：{exc}")
            self.use_edge_cache = False
            return False

    def _ensure_pygame(self):
        if self._pygame is not None:
            return self._pygame

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="pkg_resources is deprecated as an API.*",
                category=UserWarning,
            )
            import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self._pygame = pygame
        return pygame

    def _speak_system(self, text: str, *, interrupt: bool, wait: bool) -> None:
        if self.sapi_speaker is not None:
            self._speak_windows_sapi(text, interrupt=interrupt, wait=wait)
            return

        self._speak_macos_say(text, interrupt=interrupt, wait=wait)

    def _speak_windows_sapi(self, text: str, *, interrupt: bool, wait: bool) -> None:
        if self.sapi_speaker is None:
            return

        try:
            if not interrupt and not self.sapi_speaker.WaitUntilDone(0):
                return

            flags = SAPI_SPEAK_ASYNC
            if interrupt:
                flags |= SAPI_PURGE_BEFORE_SPEAK
            self.sapi_speaker.Speak(text, flags)

            if wait:
                while not self.sapi_speaker.WaitUntilDone(30) and not stop_requested():
                    time.sleep(INTERRUPT_POLL_SECONDS)
                if stop_requested():
                    self.sapi_speaker.Speak("", SAPI_PURGE_BEFORE_SPEAK)
        except Exception as exc:
            print(f"Windows SAPI 播报失败：{exc}")
            self.sapi_speaker = None

    def _speak_macos_say(self, text: str, *, interrupt: bool, wait: bool) -> None:
        if not self.say_path:
            return

        if self.process is not None and self.process.poll() is None:
            if not interrupt:
                return
            self.process.terminate()
            try:
                self.process.wait(timeout=0.5)
            except Exception:
                pass

        command = [self.say_path]
        if self.voice:
            command.extend(["-v", self.voice])
        command.extend(["-r", self.rate, text])

        try:
            if wait:
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                while self.process.poll() is None and not stop_requested():
                    time.sleep(INTERRUPT_POLL_SECONDS)
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=0.5)
                    except Exception:
                        pass
                self.process = None
            else:
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception:
            self.process = None

    def is_busy(self) -> bool:
        if not self.enabled:
            return False
        if self._pygame is not None:
            try:
                if self._pygame.mixer.get_init() and self._pygame.mixer.music.get_busy():
                    return True
            except Exception:
                pass
        if self.sapi_speaker is not None:
            try:
                if not self.sapi_speaker.WaitUntilDone(0):
                    return True
            except Exception:
                pass
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        if self._pygame is not None and self._pygame.mixer.get_init():
            try:
                self._pygame.mixer.music.stop()
                self._pygame.mixer.music.unload()
            except Exception:
                pass
        if self.sapi_speaker is not None:
            try:
                self.sapi_speaker.Speak("", SAPI_PURGE_BEFORE_SPEAK)
            except Exception:
                pass
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()

    def close(self) -> None:
        self.stop()


@dataclass
class VoiceGate:
    speaker: Speaker
    text: str | None = None
    started_at: float = 0.0
    speech_finished_at: float | None = None
    reaction_seconds: float = 0.0
    callback: Callable[[], None] | None = None
    feedback: str = "听口令，口令结束后继续。"
    blocks_logic: bool = False

    @property
    def active(self) -> bool:
        return self.text is not None

    def start(
        self,
        text: str,
        *,
        reaction_seconds: float = 0.0,
        callback: Callable[[], None] | None = None,
        feedback: str = "听口令，口令结束后继续。",
        blocks_logic: bool = True,
        interrupt: bool = True,
    ) -> None:
        self.speaker.speak(text, interrupt=interrupt)
        self.text = sanitize_voice_text(text)
        self.started_at = time.monotonic()
        self.speech_finished_at = None
        self.reaction_seconds = max(0.0, reaction_seconds)
        self.callback = callback
        self.feedback = feedback
        self.blocks_logic = blocks_logic

    def update(self) -> bool:
        if not self.active:
            return False

        now = time.monotonic()
        if self.speaker.is_busy():
            return False

        if self.speech_finished_at is None:
            self.speech_finished_at = now

        if now - self.speech_finished_at < self.reaction_seconds:
            return False

        callback = self.callback
        self.clear()
        if callback is not None:
            callback()
        return True

    def clear(self) -> None:
        self.text = None
        self.started_at = 0.0
        self.speech_finished_at = None
        self.reaction_seconds = 0.0
        self.callback = None
        self.feedback = "听口令，口令结束后继续。"
        self.blocks_logic = False

    def cancel(self, *, stop_voice: bool = False) -> None:
        if stop_voice:
            self.speaker.stop()
        self.clear()


def start_voice_sequence(
    voice_gate: VoiceGate,
    steps: list[tuple[str, float]] | tuple[tuple[str, float], ...],
    *,
    final_callback: Callable[[], None] | None = None,
    feedback: str = "听口令，口令结束后继续。",
    blocks_logic: bool = True,
    interrupt: bool = True,
) -> None:
    queue = deque(steps)

    def play_next() -> None:
        if stop_requested():
            return
        if not queue:
            if final_callback is not None:
                final_callback()
            return
        text, reaction_seconds = queue.popleft()
        voice_gate.start(
            text,
            reaction_seconds=reaction_seconds,
            callback=play_next,
            feedback=feedback,
            blocks_logic=blocks_logic,
            interrupt=interrupt,
        )

    play_next()


class TextRenderer:
    def __init__(self) -> None:
        self.font_cache: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

    def font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if size in self.font_cache:
            return self.font_cache[size]

        for path in FONT_CANDIDATES:
            if Path(path).exists():
                try:
                    font = ImageFont.truetype(path, size)
                    self.font_cache[size] = font
                    return font
                except Exception:
                    continue

        font = ImageFont.load_default()
        self.font_cache[size] = font
        return font

    def draw_panels(
        self,
        frame: np.ndarray,
        panels: list[tuple[list[str], tuple[int, int], tuple[int, int, int, int]]],
    ) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        base = Image.fromarray(rgb).convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for lines, origin, fill in panels:
            self._draw_panel(draw, lines, origin, fill)

        merged = Image.alpha_composite(base, overlay).convert("RGB")
        return cv2.cvtColor(np.asarray(merged), cv2.COLOR_RGB2BGR)

    def _draw_panel(
        self,
        draw: ImageDraw.ImageDraw,
        lines: list[str],
        origin: tuple[int, int],
        fill: tuple[int, int, int, int],
    ) -> None:
        if not lines:
            return

        x, y = origin
        padding_x, padding_y = 14, 10
        line_gap = 8
        fonts = [self.font(24 if i == 0 else 19) for i in range(len(lines))]
        widths: list[int] = []
        heights: list[int] = []

        for line, font in zip(lines, fonts):
            bbox = draw.textbbox((0, 0), line, font=font)
            widths.append(bbox[2] - bbox[0])
            heights.append(bbox[3] - bbox[1])

        panel_width = max(widths) + padding_x * 2
        panel_height = sum(heights) + line_gap * (len(lines) - 1) + padding_y * 2
        draw.rounded_rectangle(
            (x, y, x + panel_width, y + panel_height),
            radius=14,
            fill=fill,
            outline=(210, 230, 255, 220),
            width=1,
        )

        cursor_y = y + padding_y
        for line, font, height in zip(lines, fonts, heights):
            draw.text((x + padding_x, cursor_y), line, font=font, fill=(245, 250, 255, 255))
            cursor_y += height + line_gap


def collect_voice_texts(exercises: list[Exercise]) -> list[str]:
    return collect_short_voice_texts(exercises)


def visual_setup_prompt(exercise: Exercise) -> str:
    if exercise.id == "side_lying_hip_abduction":
        return SIDE_ABDUCTION_SETUP_PROMPT
    if exercise.id == "prone_hip_extension":
        return PRONE_EXTENSION_SETUP_PROMPT
    return "摆好姿势。"


def exercise_target_summary(exercise: Exercise) -> str:
    if exercise.mode in ("timer", "ankle_hybrid"):
        return f"{exercise.target_units} 次"
    if exercise.mode == "visual":
        return f"{exercise.target_units} 回合，记录达标保持时长和最大抬腿角"
    if exercise.id == "bed_knee_flexion":
        return f"{exercise.target_units} 回合，记录最大上抬角、最大屈膝角和10秒波动"
    if exercise.mode == "flexion_visual":
        return f"{exercise.target_units} 回合，记录是否达标和最大屈膝角"
    return f"{exercise.target_units} 回合"


def build_session_exercises(
    target_units: int,
    *,
    plan: str,
    exercise_ids: list[str] | None = None,
) -> list[Exercise]:
    plan_ids = SIDE_REMAINING_EXERCISE_IDS if plan == "side_remaining" else None
    try:
        exercises = select_exercises(
            target_units,
            exercise_ids=exercise_ids,
            plan_ids=plan_ids,
        )
    except ValueError as exc:
        if exercise_ids and plan != "full":
            raise ValueError(f"{exc}。如需单独测试任意动作，请使用 --plan full。") from exc
        raise

    return exercises


def load_session_config(path: str | None) -> dict[str, object] | None:
    global SESSION_CONFIG, SESSION_ACTION_CONFIGS
    if not path:
        SESSION_CONFIG = None
        SESSION_ACTION_CONFIGS = {}
        return None
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    SESSION_CONFIG = config
    SESSION_ACTION_CONFIGS = {
        str(item["id"]): item for item in config.get("actions", [])
        if isinstance(item, dict) and item.get("id")
    }
    return config


def build_session_config_exercises(config: dict[str, object]) -> list[Exercise]:
    action_items = [item for item in config.get("actions", []) if isinstance(item, dict)]
    if not action_items:
        return []
    registry = {exercise.id: exercise for exercise in select_exercises(DEFAULT_TARGET_UNITS)}
    exercises: list[Exercise] = []
    for item in action_items:
        action_id = str(item["id"])
        base = registry[action_id]
        run_target_units = max(1, int(item.get("run_target_units") or base.target_units))
        goal = item.get("goal") if isinstance(item.get("goal"), dict) else {}
        kwargs: dict[str, object] = {"target_units": run_target_units}
        if base.mode == "visual":
            if goal.get("target_angle_deg") is not None:
                kwargs["target_movement_degrees"] = float(goal["target_angle_deg"])
            if goal.get("target_hold_s") is not None:
                kwargs["target_hold_seconds"] = float(goal["target_hold_s"])
        if base.mode == "flexion_visual":
            if goal.get("target_flexion_deg") is not None:
                kwargs["target_flexion_degrees"] = float(goal["target_flexion_deg"])
            if goal.get("target_hold_s") is not None:
                kwargs["target_hold_seconds"] = float(goal["target_hold_s"])
        exercises.append(replace(base, **kwargs))
    return exercises


def parse_exercise_ids(raw_values: list[str] | None) -> list[str] | None:
    if not raw_values:
        return None
    exercise_ids: list[str] = []
    for raw_value in raw_values:
        for item in raw_value.split(","):
            exercise_id = item.strip()
            if exercise_id:
                exercise_ids.append(exercise_id)
    return exercise_ids or None


def system_camera_names() -> list[str]:
    if not is_macos():
        return []
    try:
        output = subprocess.run(
            ["system_profiler", "SPCameraDataType", "-json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout
        payload = json.loads(output)
    except Exception:
        return []

    names: list[str] = []
    for item in payload.get("SPCameraDataType", []):
        name = item.get("_name") or item.get("spcamera_model-id")
        if name:
            names.append(str(name))
    return names


def camera_index_candidates(camera_index: int) -> list[int]:
    if camera_index >= 0:
        return [camera_index]

    if is_macos():
        if len(system_camera_names()) <= 1:
            return [0]
        # With multiple cameras, Continuity Camera can take index 0.
        return [1, 2, 0, 3, 4, 5]
    return [0, 1, 2, 3, 4, 5]


def camera_backend_candidates() -> list[int]:
    if is_macos() and hasattr(cv2, "CAP_AVFOUNDATION"):
        return [cv2.CAP_AVFOUNDATION]
    if is_windows():
        candidates = []
        for backend_name_value in ("CAP_DSHOW", "CAP_MSMF"):
            if hasattr(cv2, backend_name_value):
                candidates.append(getattr(cv2, backend_name_value))
        candidates.append(cv2.CAP_ANY)
        return list(dict.fromkeys(candidates))
    return [cv2.CAP_ANY]


def backend_name(backend: int) -> str:
    if hasattr(cv2, "CAP_AVFOUNDATION") and backend == cv2.CAP_AVFOUNDATION:
        return "AVFOUNDATION"
    if hasattr(cv2, "CAP_DSHOW") and backend == cv2.CAP_DSHOW:
        return "DSHOW"
    if hasattr(cv2, "CAP_MSMF") and backend == cv2.CAP_MSMF:
        return "MSMF"
    if backend == cv2.CAP_ANY:
        return "CAP_ANY"
    return str(backend)


def setup_web_stream(
    stream_dir: str | None,
    *,
    fps: float = 15.0,
    width: int = 800,
    jpeg_quality: int = 68,
    stream_profile: str = "balanced",
) -> None:
    global WEB_STREAM_DIR, WEB_LATEST_FRAME_PATH, WEB_COMMAND_PATH, WEB_PAUSE_PATH, WEB_STATUS_PATH
    global WEB_STREAM_FPS, WEB_STREAM_WIDTH, WEB_JPEG_QUALITY, WEB_FRAME_SEQ, WEB_LAST_FRAME_TIME, WEB_FPS_SMOOTH
    global WEB_STATUS_LAST_WRITE_TIME, WEB_PUBLISHER
    close_web_publisher()
    WEB_STREAM_FPS = max(1.0, float(fps))
    WEB_STREAM_WIDTH = max(320, int(width))
    WEB_JPEG_QUALITY = max(35, min(95, int(jpeg_quality)))
    WEB_FRAME_SEQ = 0
    WEB_LAST_FRAME_TIME = 0.0
    WEB_FPS_SMOOTH = 0.0
    WEB_STATUS_LAST_WRITE_TIME = 0.0
    WEB_STATUS_CONTEXT.update(
        {
            "stream_profile": stream_profile,
            "web_stream_width": WEB_STREAM_WIDTH,
            "web_jpeg_quality": WEB_JPEG_QUALITY,
            "message": "网页流准备启动。",
        }
    )
    if not stream_dir:
        WEB_STREAM_DIR = None
        WEB_LATEST_FRAME_PATH = None
        WEB_COMMAND_PATH = None
        WEB_PAUSE_PATH = None
        WEB_STATUS_PATH = None
        return
    WEB_STREAM_DIR = Path(stream_dir)
    WEB_STREAM_DIR.mkdir(parents=True, exist_ok=True)
    WEB_LATEST_FRAME_PATH = WEB_STREAM_DIR / "latest.jpg"
    WEB_COMMAND_PATH = WEB_STREAM_DIR / "command.txt"
    WEB_PAUSE_PATH = WEB_STREAM_DIR / "pause.flag"
    WEB_STATUS_PATH = WEB_STREAM_DIR / "status.json"
    for stale in (WEB_LATEST_FRAME_PATH, WEB_COMMAND_PATH, WEB_PAUSE_PATH):
        if stale is not None and stale.exists():
            stale.unlink()
    WEB_PUBLISHER = WebFramePublisher(
        latest_path=WEB_LATEST_FRAME_PATH,
        fps=WEB_STREAM_FPS,
        width=WEB_STREAM_WIDTH,
        jpeg_quality=WEB_JPEG_QUALITY,
    )
    update_web_status(force=True)
    print(
        "网页实时画面优化：识别主循环只提交最新帧；JPEG resize/编码/写 latest.jpg "
        f"由后台线程完成。profile={stream_profile}, fps={WEB_STREAM_FPS:g}, "
        f"width={WEB_STREAM_WIDTH}, quality={WEB_JPEG_QUALITY}。"
    )
    print("瓶颈提示：网页 MJPEG 仍会经过 JPEG 编码、磁盘中转、Flask 读文件和浏览器 JPEG 解码。")


def web_stream_enabled() -> bool:
    return WEB_STREAM_DIR is not None


def read_web_command_key() -> int | None:
    if WEB_COMMAND_PATH is None or not WEB_COMMAND_PATH.exists():
        return None
    try:
        command = WEB_COMMAND_PATH.read_text(encoding="utf-8").strip().lower()
        WEB_COMMAND_PATH.unlink(missing_ok=True)
    except OSError:
        return None
    if command in {"q", "n", "r"}:
        return ord(command)
    return None


def web_pause_requested() -> bool:
    return WEB_PAUSE_PATH is not None and WEB_PAUSE_PATH.exists()


def update_web_status(*, force: bool = False, **kwargs: object) -> None:
    global WEB_STATUS_LAST_WRITE_TIME
    if WEB_STATUS_PATH is None:
        return
    with WEB_STATUS_LOCK:
        now = time.monotonic()
        if not force and WEB_STATUS_PATH.exists() and now - WEB_STATUS_LAST_WRITE_TIME < WEB_STATUS_MIN_INTERVAL:
            return
        existing: dict[str, object] = {}
        if WEB_STATUS_PATH.exists():
            try:
                existing = json.loads(WEB_STATUS_PATH.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        payload = {
            **existing,
            "updated_at": datetime.now().isoformat(timespec="milliseconds"),
            "frame_seq": WEB_FRAME_SEQ,
            "fps": round(WEB_FPS_SMOOTH, 1),
            "paused": web_pause_requested(),
            "stale": False,
            **WEB_STATUS_CONTEXT,
            **kwargs,
        }
        try:
            tmp = WEB_STATUS_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            tmp.replace(WEB_STATUS_PATH)
            WEB_STATUS_LAST_WRITE_TIME = now
        except OSError:
            pass


def set_web_status_context(**kwargs: object) -> None:
    WEB_STATUS_CONTEXT.update(kwargs)
    update_web_status()


class WebFramePublisher:
    """Asynchronous latest-frame publisher for the webpage MJPEG bridge.

    The original webpage mode encoded JPEG and wrote latest.jpg inside the
    recognition loop. That made every camera/MediaPipe iteration wait for
    resize, cv2.imencode and filesystem replace. This publisher keeps only one
    latest frame and performs those slow steps on a daemon thread.
    """

    def __init__(self, *, latest_path: Path, fps: float, width: int, jpeg_quality: int) -> None:
        self.latest_path = latest_path
        self.tmp_path = latest_path.with_suffix(".tmp")
        self.fps = max(1.0, float(fps))
        self.width = max(320, int(width))
        self.jpeg_quality = max(35, min(95, int(jpeg_quality)))
        self._lock = threading.Lock()
        self._frame_event = threading.Event()
        self._stop_event = threading.Event()
        self._latest_frame: np.ndarray | None = None
        self._latest_submit_time = 0.0
        self._dropped_frames = 0
        self._last_publish_time = 0.0
        self._thread = threading.Thread(target=self._run, name="web-frame-publisher", daemon=True)
        self._thread.start()

    def submit(self, frame: np.ndarray) -> None:
        try:
            copied = frame.copy()
        except Exception:
            return
        with self._lock:
            if self._latest_frame is not None:
                self._dropped_frames += 1
            self._latest_frame = copied
            self._latest_submit_time = time.monotonic()
            self._frame_event.set()

    def close(self) -> None:
        self._stop_event.set()
        self._frame_event.set()
        self._thread.join(timeout=1.0)

    def _take_latest_frame(self) -> tuple[np.ndarray | None, float, int]:
        with self._lock:
            frame = self._latest_frame
            submitted_at = self._latest_submit_time
            dropped = self._dropped_frames
            self._latest_frame = None
            self._frame_event.clear()
        return frame, submitted_at, dropped

    def _run(self) -> None:
        global WEB_FRAME_SEQ, WEB_LAST_FRAME_TIME, WEB_FPS_SMOOTH
        min_interval = 1.0 / max(self.fps, 1.0)
        while not self._stop_event.is_set():
            if not self._frame_event.wait(timeout=0.1):
                continue
            if self._stop_event.is_set():
                break
            remaining = min_interval - (time.monotonic() - self._last_publish_time)
            if remaining > 0:
                self._stop_event.wait(timeout=remaining)
                if self._stop_event.is_set():
                    break
            frame, submitted_at, dropped = self._take_latest_frame()
            if frame is None:
                continue
            if web_pause_requested():
                update_web_status(paused=True, message="已暂停")
                continue
            try:
                if frame.shape[1] > self.width:
                    scale = self.width / frame.shape[1]
                    frame = cv2.resize(frame, (self.width, int(frame.shape[0] * scale)), interpolation=cv2.INTER_AREA)
                encode_start = time.perf_counter()
                ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
                encode_ms = (time.perf_counter() - encode_start) * 1000
                if not ok:
                    update_web_status(message="网页帧 JPEG 编码失败")
                    continue
                data = encoded.tobytes()
                write_start = time.perf_counter()
                self.tmp_path.write_bytes(data)
                self.tmp_path.replace(self.latest_path)
                write_ms = (time.perf_counter() - write_start) * 1000
                now = time.monotonic()
                WEB_FRAME_SEQ += 1
                if WEB_LAST_FRAME_TIME:
                    instant_fps = 1.0 / max(now - WEB_LAST_FRAME_TIME, 1e-6)
                    WEB_FPS_SMOOTH = instant_fps if WEB_FPS_SMOOTH <= 0 else WEB_FPS_SMOOTH * 0.8 + instant_fps * 0.2
                WEB_LAST_FRAME_TIME = now
                self._last_publish_time = now
                update_web_status(
                    force=WEB_FRAME_SEQ <= 1,
                    frame_seq=WEB_FRAME_SEQ,
                    last_frame_at=datetime.now().isoformat(timespec="milliseconds"),
                    fps=round(WEB_FPS_SMOOTH, 1),
                    encode_ms=round(encode_ms, 1),
                    write_ms=round(write_ms, 1),
                    jpeg_size_kb=round(len(data) / 1024, 1),
                    dropped_frames=dropped,
                    publisher_queue_lag_ms=round(max(0.0, now - submitted_at) * 1000, 1) if submitted_at else None,
                    paused=False,
                    stale=False,
                )
            except Exception as exc:
                update_web_status(message=f"网页帧发布失败：{exc}")


def close_web_publisher() -> None:
    global WEB_PUBLISHER
    if WEB_PUBLISHER is not None:
        WEB_PUBLISHER.close()
        WEB_PUBLISHER = None


def write_web_frame_sync(frame: np.ndarray) -> None:
    """Fallback writer used only if the publisher could not be created."""
    global WEB_FRAME_SEQ, WEB_LAST_FRAME_TIME, WEB_FPS_SMOOTH
    if WEB_LATEST_FRAME_PATH is None:
        return
    try:
        if frame.shape[1] > WEB_STREAM_WIDTH:
            scale = WEB_STREAM_WIDTH / frame.shape[1]
            frame = cv2.resize(frame, (WEB_STREAM_WIDTH, int(frame.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        encode_start = time.perf_counter()
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), WEB_JPEG_QUALITY])
        encode_ms = (time.perf_counter() - encode_start) * 1000
        if not ok:
            return
        data = encoded.tobytes()
        write_start = time.perf_counter()
        tmp_path = WEB_LATEST_FRAME_PATH.with_suffix(".tmp")
        tmp_path.write_bytes(data)
        tmp_path.replace(WEB_LATEST_FRAME_PATH)
        write_ms = (time.perf_counter() - write_start) * 1000
        now = time.monotonic()
        WEB_FRAME_SEQ += 1
        if WEB_LAST_FRAME_TIME:
            instant_fps = 1.0 / max(now - WEB_LAST_FRAME_TIME, 1e-6)
            WEB_FPS_SMOOTH = instant_fps if WEB_FPS_SMOOTH <= 0 else WEB_FPS_SMOOTH * 0.8 + instant_fps * 0.2
        WEB_LAST_FRAME_TIME = now
        update_web_status(
            force=WEB_FRAME_SEQ <= 1,
            frame_seq=WEB_FRAME_SEQ,
            last_frame_at=datetime.now().isoformat(timespec="milliseconds"),
            fps=round(WEB_FPS_SMOOTH, 1),
            encode_ms=round(encode_ms, 1),
            write_ms=round(write_ms, 1),
            jpeg_size_kb=round(len(data) / 1024, 1),
            dropped_frames=0,
            publisher_queue_lag_ms=0,
            paused=False,
            stale=False,
        )
    except Exception as exc:
        update_web_status(message=f"网页帧同步发布失败：{exc}")


def publish_training_frame(frame: np.ndarray) -> None:
    if not web_stream_enabled():
        cv2.imshow(WINDOW_NAME, frame)
        return
    if WEB_LATEST_FRAME_PATH is None:
        return
    if web_pause_requested():
        update_web_status(paused=True, message="已暂停")
        return
    if WEB_PUBLISHER is not None:
        WEB_PUBLISHER.submit(frame)
    else:
        write_web_frame_sync(frame)


def read_camera_frame(cap: cv2.VideoCapture, *, attempts: int = CAMERA_READ_RETRY_ATTEMPTS) -> np.ndarray | None:
    """Read one camera frame while guarding against backend-specific OpenCV exceptions."""
    for attempt in range(max(1, attempts)):
        try:
            ok, frame = cap.read()
        except cv2.error:
            ok = False
            frame = None

        if ok and frame is not None and getattr(frame, "size", 0) > 0:
            return frame

        if attempt + 1 < attempts:
            time.sleep(CAMERA_READ_RETRY_SLEEP_SECONDS)

    return None


def probe_camera_indices(max_index: int = 6) -> list[int]:
    available: set[int] = set()
    for backend in camera_backend_candidates():
        for index in range(max_index + 1):
            try:
                cap = cv2.VideoCapture(index, backend)
            except Exception:
                continue
            ok = cap.isOpened()
            if ok:
                ok = read_camera_frame(cap, attempts=1) is not None
            cap.release()
            if ok:
                available.add(index)
    return sorted(available)


def print_camera_help(*, probe_indices: bool = False) -> None:
    names = system_camera_names()
    if is_macos():
        if names:
            print("macOS 检测到的本机摄像头：")
            for name in names:
                print(f"- {name}")
        else:
            print("macOS 没有返回摄像头名称。")
    elif is_windows():
        print("Windows 无法像 macOS 一样稳定列出摄像头名称；建议使用 --probe-cameras 探测 OpenCV 可打开的序号。")
    else:
        print("当前系统将通过 OpenCV 探测摄像头序号。")

    if not probe_indices:
        if is_macos():
            if len(names) <= 1:
                print("当前只检测到一个摄像头，AVFoundation 序号通常是 index 0。")
                print("建议直接运行：knee_rehab_desktop_session.py --target 3 --camera 0")
            else:
                print("检测到多个摄像头时，默认会优先尝试 index 1、2，再回退到 index 0。")
                print("如果仍连到手机，请加 --probe-cameras 探测可打开序号，或直接用 --camera 1 / --camera 2 试。")
        elif is_windows():
            print("Windows 默认依次尝试 DSHOW、MSMF、CAP_ANY 后端和 index 0..5。")
            print("如果默认摄像头不对，请运行 --probe-cameras，或直接用 --camera 0 / --camera 1 指定。")
        else:
            print("如果默认摄像头不对，请运行 --probe-cameras，或直接用 --camera 指定序号。")
        return

    indices = probe_camera_indices()
    if indices:
        print("OpenCV 可打开的摄像头序号：")
        for index in indices:
            print(f"- index {index}")
        print("如果默认摄像头不对，请用 --camera 指定对应序号。")
    else:
        print("OpenCV 没有探测到可打开的摄像头。请检查系统摄像头权限，或关闭正在占用摄像头的应用。")


def configure_camera_capture(
    cap: cv2.VideoCapture,
    *,
    camera_width: int | None = None,
    camera_height: int | None = None,
    camera_fps: float | None = None,
) -> None:
    settings: list[tuple[int, float, str]] = []
    if camera_width:
        settings.append((cv2.CAP_PROP_FRAME_WIDTH, float(camera_width), "width"))
    else:
        settings.append((cv2.CAP_PROP_FRAME_WIDTH, 1280.0, "default width"))
    if camera_height:
        settings.append((cv2.CAP_PROP_FRAME_HEIGHT, float(camera_height), "height"))
    else:
        settings.append((cv2.CAP_PROP_FRAME_HEIGHT, 720.0, "default height"))
    if camera_fps:
        settings.append((cv2.CAP_PROP_FPS, float(camera_fps), "fps"))
    if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
        settings.append((cv2.CAP_PROP_BUFFERSIZE, 1.0, "buffer size"))
    for prop, value, label in settings:
        try:
            ok = cap.set(prop, value)
            if not ok and label not in {"default width", "default height"}:
                print(f"⚠️ 摄像头参数 {label}={value:g} 可能未被当前后端接受。")
        except Exception as exc:
            print(f"⚠️ 摄像头参数 {label}={value:g} 设置失败：{exc}")


def open_camera(
    camera_index: int,
    *,
    camera_width: int | None = None,
    camera_height: int | None = None,
    camera_fps: float | None = None,
) -> cv2.VideoCapture:
    backend_candidates = camera_backend_candidates()
    index_candidates = camera_index_candidates(camera_index)
    attempted: list[str] = []
    for backend in backend_candidates:
        for index in index_candidates:
            if stop_requested():
                raise RuntimeError("训练已退出。")
            attempted.append(f"index={index}, backend={backend_name(backend)}")
            try:
                cap = cv2.VideoCapture(index, backend)
            except Exception:
                continue
            if not cap.isOpened():
                cap.release()
                continue
            if read_camera_frame(cap, attempts=2) is not None:
                configure_camera_capture(
                    cap,
                    camera_width=camera_width,
                    camera_height=camera_height,
                    camera_fps=camera_fps,
                )
                print(f"摄像头已打开：index={index}, backend={backend_name(backend)}")
                if camera_index < 0 and index == 0 and is_macos():
                    print("提示：如果这里仍然是手机摄像头，请运行 --list-cameras 后用 --camera 指定内置摄像头序号。")
                return cap
            cap.release()

    attempted_text = "；".join(attempted) if attempted else "未尝试任何摄像头"
    if is_macos():
        reason = "无法打开摄像头。macOS 下已禁用 OpenCV 的 CAP_ANY 回退，以避免触发 OBSENSOR/Orbbec 后端异常。"
    elif is_windows():
        reason = "无法打开摄像头。Windows 下已尝试 DSHOW/MSMF/CAP_ANY 后端。"
    else:
        reason = "无法打开摄像头。"
    raise RuntimeError(
        f"{reason}已尝试：{attempted_text}。请检查摄像头权限，或用 --camera 0/1/2 指定序号。"
    )


def landmark_point(
    landmarks,
    landmark_type,
    width: int,
    height: int,
    min_visibility: float = MIN_LANDMARK_VISIBILITY,
) -> np.ndarray | None:
    landmark = landmarks[landmark_type.value]
    if not landmark_in_frame(landmarks, landmark_type):
        return None
    if landmark_visibility(landmarks, landmark_type) < min_visibility:
        return None
    return np.array([landmark.x * width, landmark.y * height], dtype=np.float32)


def landmark_visibility(landmarks, landmark_type) -> float:
    return float(getattr(landmarks[landmark_type.value], "visibility", 1.0))


def landmark_in_frame(landmarks, landmark_type) -> bool:
    landmark = landmarks[landmark_type.value]
    return (
        -LANDMARK_FRAME_MARGIN <= landmark.x <= 1.0 + LANDMARK_FRAME_MARGIN
        and -LANDMARK_FRAME_MARGIN <= landmark.y <= 1.0 + LANDMARK_FRAME_MARGIN
    )


def landmark_is_visible(
    landmarks,
    landmark_type,
    min_visibility: float = MIN_LANDMARK_VISIBILITY,
) -> bool:
    return landmark_in_frame(landmarks, landmark_type) and landmark_visibility(landmarks, landmark_type) >= min_visibility


def leg_landmark_types(side: str) -> dict[str, object]:
    if side == "left":
        return {
            "hip": mp_pose.PoseLandmark.LEFT_HIP,
            "knee": mp_pose.PoseLandmark.LEFT_KNEE,
            "ankle": mp_pose.PoseLandmark.LEFT_ANKLE,
            "heel": mp_pose.PoseLandmark.LEFT_HEEL,
            "foot_index": mp_pose.PoseLandmark.LEFT_FOOT_INDEX,
        }
    return {
        "hip": mp_pose.PoseLandmark.RIGHT_HIP,
        "knee": mp_pose.PoseLandmark.RIGHT_KNEE,
        "ankle": mp_pose.PoseLandmark.RIGHT_ANKLE,
        "heel": mp_pose.PoseLandmark.RIGHT_HEEL,
        "foot_index": mp_pose.PoseLandmark.RIGHT_FOOT_INDEX,
    }


def side_label_zh(side: str | None, *, suffix: str = "侧") -> str:
    if side == "left":
        return f"左{suffix}"
    if side == "right":
        return f"右{suffix}"
    return "--"


def tracked_leg_label(leg: LegPoints | None) -> str:
    if leg is None:
        return "追踪：--"
    side_label = side_label_zh(leg.side, suffix="腿")
    distal_label = {
        "ankle": "踝",
        "heel": "足跟",
        "foot_index": "脚尖",
    }.get(leg.distal_part, leg.distal_part)
    return f"追踪：{side_label} / {distal_label}"


def distal_candidate_score(
    landmarks,
    side: str,
    part: str,
    *,
    require_visible: bool,
    preferred_part: str | None,
) -> float:
    landmark_type = leg_landmark_types(side)[part]
    visible = landmark_is_visible(landmarks, landmark_type)
    if require_visible and not visible:
        return -1.0

    score = landmark_visibility(landmarks, landmark_type)
    if landmark_in_frame(landmarks, landmark_type):
        score += 0.5
    score += DISTAL_PRIORITY_BONUS.get(part, 0.0)
    if preferred_part == part:
        score += DISTAL_LOCK_BONUS
    return score


def best_distal_part(
    landmarks,
    side: str,
    *,
    require_visible: bool = False,
    preferred_part: str | None = None,
) -> str | None:
    best_part: str | None = None
    best_score = -1.0
    for part in ("ankle", "heel", "foot_index"):
        score = distal_candidate_score(
            landmarks,
            side,
            part,
            require_visible=require_visible,
            preferred_part=preferred_part,
        )
        if score > best_score:
            best_score = score
            best_part = part
    return best_part if best_score >= 0 else None


def leg_score(landmarks, side: str) -> float:
    types = leg_landmark_types(side)
    score = 0.0
    for part in ("hip", "knee"):
        landmark_type = types[part]
        score += landmark_visibility(landmarks, landmark_type)
        if landmark_in_frame(landmarks, landmark_type):
            score += 0.5

    distal_part = best_distal_part(landmarks, side, require_visible=False)
    if distal_part is not None:
        distal_type = types[distal_part]
        score += landmark_visibility(landmarks, distal_type)
        if landmark_in_frame(landmarks, distal_type):
            score += 0.5
        score += DISTAL_PRIORITY_BONUS.get(distal_part, 0.0)
    return score


def upper_leg_y_position(landmarks, side: str) -> float | None:
    types = leg_landmark_types(side)
    distal_part = best_distal_part(landmarks, side, require_visible=True)
    if distal_part is None:
        return None

    points = []
    for part in ("hip", "knee", distal_part):
        point = landmark_normalized_xy(landmarks, types[part])
        if point is None:
            return None
        points.append(point)
    return float(np.mean([point[1] for point in points]))


def leg_is_usable(landmarks, side: str) -> bool:
    types = leg_landmark_types(side)
    distal_part = best_distal_part(landmarks, side, require_visible=True)
    if distal_part is None:
        return False

    required_types = [types["hip"], types["knee"], types[distal_part]]
    average_visibility = sum(landmark_visibility(landmarks, item) for item in required_types) / len(required_types)
    return all(landmark_in_frame(landmarks, item) for item in required_types) and average_visibility >= MIN_LANDMARK_VISIBILITY


def landmark_normalized_xy(landmarks, landmark_type) -> np.ndarray | None:
    if not landmark_in_frame(landmarks, landmark_type):
        return None
    landmark = landmarks[landmark_type.value]
    return np.array([landmark.x, landmark.y], dtype=np.float32)


def side_view_feedback(landmarks) -> str | None:
    required = [
        mp_pose.PoseLandmark.LEFT_SHOULDER,
        mp_pose.PoseLandmark.RIGHT_SHOULDER,
        mp_pose.PoseLandmark.LEFT_HIP,
        mp_pose.PoseLandmark.RIGHT_HIP,
    ]
    points = [landmark_normalized_xy(landmarks, item) for item in required]
    if any(point is None for point in points):
        return None

    left_shoulder, right_shoulder, left_hip, right_hip = points
    shoulder_width = float(np.linalg.norm(left_shoulder - right_shoulder))
    hip_width = float(np.linalg.norm(left_hip - right_hip))
    mid_shoulder = (left_shoulder + right_shoulder) * 0.5
    mid_hip = (left_hip + right_hip) * 0.5
    torso_length = float(np.linalg.norm(mid_shoulder - mid_hip))
    if torso_length <= 1e-6:
        return None

    torso_width_ratio = max(shoulder_width, hip_width) / torso_length
    if torso_width_ratio > SIDE_VIEW_MAX_TORSO_WIDTH_RATIO:
        return "请把身体转成侧面，减少正面角度误差。"
    return None


def reset_distal_lock(state: TrackedLegState) -> None:
    state.locked_distal_part = None
    state.distal_candidate = None
    state.distal_candidate_frames = 0


def choose_upper_leg_side(landmarks, requested_side: str, state: TrackedLegState) -> str | None:
    if requested_side in ("left", "right"):
        state.locked_side = requested_side
        return requested_side

    y_positions = {
        side: upper_leg_y_position(landmarks, side)
        for side in ("left", "right")
    }
    usable_positions = {
        side: value
        for side, value in y_positions.items()
        if value is not None and leg_is_usable(landmarks, side)
    }
    if not usable_positions:
        return choose_leg_side(landmarks, requested_side, state)

    best_side = min(usable_positions, key=usable_positions.get)
    locked_side = state.locked_side
    if locked_side not in ("left", "right") or locked_side not in usable_positions:
        state.locked_side = best_side
        state.candidate_side = None
        state.candidate_frames = 0
        reset_distal_lock(state)
        return best_side

    if best_side == locked_side:
        state.candidate_side = None
        state.candidate_frames = 0
        return locked_side

    locked_y = usable_positions[locked_side]
    best_y = usable_positions[best_side]
    if locked_y <= best_y + UPPER_LEG_Y_SWITCH_MARGIN:
        state.candidate_side = None
        state.candidate_frames = 0
        return locked_side

    if state.candidate_side == best_side:
        state.candidate_frames += 1
    else:
        state.candidate_side = best_side
        state.candidate_frames = 1

    if state.candidate_frames >= 2:
        state.locked_side = best_side
        state.candidate_side = None
        state.candidate_frames = 0
        reset_distal_lock(state)
        return best_side
    return locked_side


def choose_leg_side(landmarks, requested_side: str, state: TrackedLegState) -> str | None:
    if requested_side in ("left", "right"):
        state.locked_side = requested_side
        return requested_side

    scores = {side: leg_score(landmarks, side) for side in ("left", "right")}
    best_side = max(scores, key=scores.get)
    locked_side = state.locked_side

    if locked_side not in ("left", "right"):
        state.locked_side = best_side
        state.candidate_side = None
        state.candidate_frames = 0
        return best_side

    if best_side == locked_side:
        state.candidate_side = None
        state.candidate_frames = 0
        return locked_side

    locked_usable = leg_is_usable(landmarks, locked_side)
    score_gap = scores[best_side] - scores[locked_side]
    if locked_usable and score_gap < LEG_SWITCH_SCORE_MARGIN:
        state.candidate_side = None
        state.candidate_frames = 0
        return locked_side

    if state.candidate_side == best_side:
        state.candidate_frames += 1
    else:
        state.candidate_side = best_side
        state.candidate_frames = 1

    required_frames = 2 if not locked_usable else VISUAL_SIDE_LOCK_FRAMES
    if state.candidate_frames >= required_frames:
        state.locked_side = best_side
        state.candidate_side = None
        state.candidate_frames = 0
        reset_distal_lock(state)
        return best_side
    return locked_side


def choose_distal_part(
    landmarks,
    side: str,
    state: TrackedLegState,
    *,
    require_visible: bool = False,
) -> str | None:
    best_part = best_distal_part(
        landmarks,
        side,
        require_visible=require_visible,
        preferred_part=state.locked_distal_part,
    )
    if best_part is None:
        if require_visible:
            reset_distal_lock(state)
        return None

    if state.locked_distal_part is None:
        state.locked_distal_part = best_part
        state.distal_candidate = None
        state.distal_candidate_frames = 0
        return best_part

    if best_part == state.locked_distal_part:
        state.distal_candidate = None
        state.distal_candidate_frames = 0
        return best_part

    types = leg_landmark_types(side)
    locked_type = types.get(state.locked_distal_part)
    locked_visible = locked_type is not None and landmark_is_visible(landmarks, locked_type)
    required_frames = 1 if (require_visible and not locked_visible) else DISTAL_SWITCH_CONFIRM_FRAMES

    if state.distal_candidate == best_part:
        state.distal_candidate_frames += 1
    else:
        state.distal_candidate = best_part
        state.distal_candidate_frames = 1

    if state.distal_candidate_frames >= required_frames:
        state.locked_distal_part = best_part
        state.distal_candidate = None
        state.distal_candidate_frames = 0
        return best_part
    return state.locked_distal_part


def build_leg_points(
    landmarks,
    width: int,
    height: int,
    side: str,
    distal_part: str,
) -> LegPoints | None:
    types = leg_landmark_types(side)
    hip = landmark_point(landmarks, types["hip"], width, height)
    knee = landmark_point(landmarks, types["knee"], width, height)
    if hip is None or knee is None:
        return None

    distal = landmark_point(landmarks, types[distal_part], width, height)
    if distal is None:
        return None

    ankle = landmark_point(landmarks, types["ankle"], width, height)
    heel = landmark_point(landmarks, types["heel"], width, height)
    foot_index = landmark_point(landmarks, types["foot_index"], width, height)
    ankle_visible = ankle is not None
    if ankle is None:
        ankle = distal.copy()

    score = leg_score(landmarks, side) * 1000.0
    score += abs(float(hip[0] - knee[0])) + abs(float(knee[0] - distal[0]))
    return LegPoints(
        side=side,
        hip=hip,
        knee=knee,
        ankle=ankle,
        ankle_visible=ankle_visible,
        heel=heel,
        foot_index=foot_index,
        distal=distal,
        distal_part=distal_part,
        profile_score=score,
    )


def pick_stable_tracked_leg(
    landmarks,
    width: int,
    height: int,
    side: str,
    state: TrackedLegState,
    *,
    prefer_upper_leg: bool = False,
) -> LegPoints | None:
    tracked_side = (
        choose_upper_leg_side(landmarks, side, state)
        if prefer_upper_leg
        else choose_leg_side(landmarks, side, state)
    )
    if tracked_side is None:
        state.missing_frames += 1
        return None

    distal_part = choose_distal_part(landmarks, tracked_side, state, require_visible=True)
    if distal_part is None:
        state.missing_frames += 1
        return None

    leg = build_leg_points(landmarks, width, height, tracked_side, distal_part)
    if leg is None:
        state.missing_frames += 1
        return None

    state.missing_frames = 0
    return leg


def angle_at(point_a: np.ndarray, vertex: np.ndarray, point_c: np.ndarray) -> float:
    vector_a = point_a - vertex
    vector_c = point_c - vertex
    denominator = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_c))
    if denominator <= 1e-6:
        return 0.0
    cosine = float(np.dot(vector_a, vector_c) / denominator)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def knee_flexion_angle(leg: LegPoints) -> float:
    return max(0.0, 180.0 - angle_at(leg.hip, leg.knee, leg.distal))


def knee_extension_angle(leg: LegPoints) -> float:
    distal = leg.ankle if leg.ankle_visible else leg.distal
    return angle_at(leg.hip, leg.knee, distal)


def knee_line_deviation_ratio(leg: LegPoints) -> float:
    distal = leg.ankle if leg.ankle_visible else leg.distal
    hip_to_distal = distal - leg.hip
    length = float(np.linalg.norm(hip_to_distal))
    if length <= 1e-6:
        return 0.0
    knee_to_hip = leg.knee - leg.hip
    cross = abs(float(hip_to_distal[0] * knee_to_hip[1] - hip_to_distal[1] * knee_to_hip[0]))
    return cross / (length * max(leg.leg_length, 1.0))


def leg_raise_angle_degrees(leg: LegPoints) -> float:
    distal = leg.ankle if leg.ankle_visible else leg.distal
    vector = distal - leg.hip
    horizontal = abs(float(vector[0]))
    upward = max(0.0, -float(vector[1]))
    if horizontal <= 1e-6 and upward <= 1e-6:
        return 0.0
    return math.degrees(math.atan2(upward, max(horizontal, 1e-6)))


def thigh_raise_angle_degrees(leg: LegPoints) -> float:
    vector = leg.knee - leg.hip
    horizontal = abs(float(vector[0]))
    upward = max(0.0, -float(vector[1]))
    if horizontal <= 1e-6 and upward <= 1e-6:
        return 0.0
    return math.degrees(math.atan2(upward, max(horizontal, 1e-6)))


def point_to_pixel(point: np.ndarray, width: int, height: int) -> tuple[int, int]:
    clipped = np.array(
        [
            float(np.clip(point[0], 0.0, max(width - 1, 1))),
            float(np.clip(point[1], 0.0, max(height - 1, 1))),
        ],
        dtype=np.float32,
    )
    return tuple(np.round(clipped).astype(int))


def display_frame_for(camera_frame: np.ndarray, mirror: bool) -> np.ndarray:
    return cv2.flip(camera_frame, 1) if mirror else camera_frame.copy()


def mirror_point_for_display(point: np.ndarray | None, width: int, mirror: bool) -> np.ndarray | None:
    if point is None:
        return None
    if not mirror:
        return point
    mirrored = point.copy()
    mirrored[0] = max(width - 1, 1) - mirrored[0]
    return mirrored


def mirror_vector_for_display(vector: np.ndarray | None, mirror: bool) -> np.ndarray | None:
    if vector is None:
        return None
    if not mirror:
        return vector
    mirrored = vector.copy()
    mirrored[0] = -mirrored[0]
    return mirrored


def leg_for_display(leg: LegPoints | None, width: int, mirror: bool) -> LegPoints | None:
    if leg is None or not mirror:
        return leg
    display_side = "right" if leg.side == "left" else "left"
    return LegPoints(
        side=display_side,
        hip=mirror_point_for_display(leg.hip, width, mirror),
        knee=mirror_point_for_display(leg.knee, width, mirror),
        ankle=mirror_point_for_display(leg.ankle, width, mirror),
        ankle_visible=leg.ankle_visible,
        heel=mirror_point_for_display(leg.heel, width, mirror),
        foot_index=mirror_point_for_display(leg.foot_index, width, mirror),
        distal=mirror_point_for_display(leg.distal, width, mirror),
        distal_part=leg.distal_part,
        profile_score=leg.profile_score,
    )


def visual_metrics_for_display(
    metrics: VisualMotionMetrics | None,
    width: int,
    mirror: bool,
) -> VisualMotionMetrics | None:
    if metrics is None or not mirror:
        return metrics
    return VisualMotionMetrics(
        movement_ratio=metrics.movement_ratio,
        distance_cm=metrics.distance_cm,
        angle_degrees=metrics.angle_degrees,
        target_distance_cm=metrics.target_distance_cm,
        target_angle_degrees=metrics.target_angle_degrees,
        target_ratio=metrics.target_ratio,
        signed_perpendicular_px=metrics.signed_perpendicular_px,
        axis_unit=mirror_vector_for_display(metrics.axis_unit, mirror),
        perpendicular_unit=mirror_vector_for_display(metrics.perpendicular_unit, mirror),
        bed_anchor=mirror_point_for_display(metrics.bed_anchor, width, mirror),
        baseline_ankle_adjusted=mirror_point_for_display(metrics.baseline_ankle_adjusted, width, mirror),
        projected_ankle=mirror_point_for_display(metrics.projected_ankle, width, mirror),
    )


def rotate_vector(vector: np.ndarray, degrees: float) -> np.ndarray:
    radians = math.radians(degrees)
    rotation_matrix = np.array(
        [
            [math.cos(radians), -math.sin(radians)],
            [math.sin(radians), math.cos(radians)],
        ],
        dtype=np.float32,
    )
    return rotation_matrix @ vector


def guidance_rotation_sign(thigh_unit: np.ndarray, shank_unit: np.ndarray, leg_side: str) -> float:
    cross = float(thigh_unit[0] * shank_unit[1] - thigh_unit[1] * shank_unit[0])
    if abs(cross) > 1e-4:
        return 1.0 if cross > 0 else -1.0
    if abs(float(shank_unit[0])) > 0.02:
        return 1.0 if shank_unit[0] > 0 else -1.0
    return 1.0 if leg_side == "right" else -1.0


def target_distal_for_flexion(leg: LegPoints, target_flexion_degrees: float) -> np.ndarray | None:
    thigh_vector = leg.hip - leg.knee
    shank_vector = leg.distal - leg.knee
    thigh_length = float(np.linalg.norm(thigh_vector))
    shank_length = float(np.linalg.norm(shank_vector))
    if thigh_length <= 1e-6 or shank_length <= 1e-6:
        return None
    thigh_unit = thigh_vector / thigh_length
    shank_unit = shank_vector / shank_length
    target_inner_angle = max(10.0, 180.0 - target_flexion_degrees)
    rotation_sign = guidance_rotation_sign(thigh_unit, shank_unit, leg.side)
    target_shank_unit = rotate_vector(thigh_unit, rotation_sign * target_inner_angle)
    return leg.knee + target_shank_unit * shank_length


def draw_dashed_line(
    frame: np.ndarray,
    start_point: tuple[int, int],
    end_point: tuple[int, int],
    color: tuple[int, int, int],
    thickness: int = 2,
    dash_length: int = 14,
) -> None:
    start = np.array(start_point, dtype=np.float32)
    end = np.array(end_point, dtype=np.float32)
    line_length = float(np.linalg.norm(end - start))
    if line_length <= 1e-6:
        return
    direction = (end - start) / line_length
    for offset in np.arange(0, line_length, dash_length * 2):
        dash_start = start + direction * offset
        dash_end = start + direction * min(offset + dash_length, line_length)
        cv2.line(
            frame,
            tuple(np.round(dash_start).astype(int)),
            tuple(np.round(dash_end).astype(int)),
            color,
            thickness,
            cv2.LINE_AA,
        )


def draw_knee_extension_arrow(frame: np.ndarray, leg: LegPoints) -> None:
    distal = leg.ankle if leg.ankle_visible else leg.distal
    thigh_unit = normalized_vector(leg.hip - leg.knee)
    shank_unit = normalized_vector(distal - leg.knee)
    if thigh_unit is None or shank_unit is None:
        return

    target_unit = -thigh_unit
    current_angle = math.atan2(float(shank_unit[1]), float(shank_unit[0]))
    target_angle = math.atan2(float(target_unit[1]), float(target_unit[0]))
    delta = (target_angle - current_angle + math.pi) % math.tau - math.pi
    if abs(delta) < math.radians(8.0):
        return

    center = leg.knee.astype(np.float32)
    radius = int(max(24, min(72, leg.leg_length * 0.18)))
    steps = max(10, int(abs(delta) / math.radians(6.0)))
    angles = np.linspace(current_angle, current_angle + delta, steps)
    points = np.array(
        [
            center + np.array([math.cos(angle), math.sin(angle)], dtype=np.float32) * radius
            for angle in angles
        ],
        dtype=np.int32,
    )
    color = GUIDE_ARROW_BLUE
    cv2.polylines(frame, [points], False, color, 4, cv2.LINE_AA)

    if len(points) >= 2:
        cv2.arrowedLine(
            frame,
            tuple(points[-2]),
            tuple(points[-1]),
            color,
            4,
            cv2.LINE_AA,
            tipLength=0.45,
        )
    cv2.circle(frame, tuple(np.round(center).astype(int)), 9, (20, 20, 20), -1, cv2.LINE_AA)
    cv2.circle(frame, tuple(np.round(center).astype(int)), 6, (245, 245, 245), -1, cv2.LINE_AA)


def draw_angle_only_leg_raise_guides(
    frame: np.ndarray,
    leg: LegPoints | None,
    *,
    target_angle_degrees: float,
    current_angle_degrees: float | None,
    knee_straight: bool,
    stage: str,
) -> None:
    if leg is None:
        return

    distal = leg.ankle if leg.ankle_visible else leg.distal
    hip_px = point_to_pixel(leg.hip, frame.shape[1], frame.shape[0])
    knee_px = point_to_pixel(leg.knee, frame.shape[1], frame.shape[0])
    distal_px = point_to_pixel(distal, frame.shape[1], frame.shape[0])

    target_reached = (
        current_angle_degrees is not None
        and current_angle_degrees >= target_angle_degrees * 0.95
    )
    movement_good = target_reached and knee_straight
    leg_color = LEG_GOOD_COLOR if movement_good else LEG_NEEDS_WORK_COLOR

    cv2.line(frame, hip_px, knee_px, leg_color, 4, cv2.LINE_AA)
    cv2.line(frame, knee_px, distal_px, leg_color, 4, cv2.LINE_AA)
    for point in (hip_px, knee_px, distal_px):
        cv2.circle(frame, point, 6, (255, 255, 255), -1, cv2.LINE_AA)

    horizontal_sign = 1.0 if distal[0] >= leg.hip[0] else -1.0
    target_radians = math.radians(max(0.0, target_angle_degrees))
    target_unit = np.array(
        [horizontal_sign * math.cos(target_radians), -math.sin(target_radians)],
        dtype=np.float32,
    )
    target_endpoint = leg.hip + target_unit * leg.leg_length
    target_px = point_to_pixel(target_endpoint, frame.shape[1], frame.shape[0])
    show_guides = not movement_good and stage != "return"
    if show_guides:
        draw_dashed_line(frame, hip_px, target_px, GUIDE_BLUE, thickness=3)

    if (
        show_guides
        and stage in ("raise", "hold")
        and not target_reached
    ):
        cv2.arrowedLine(
            frame,
            distal_px,
            target_px,
            GUIDE_ARROW_BLUE,
            4,
            cv2.LINE_AA,
            tipLength=0.22,
        )

    if not knee_straight and stage != "return":
        draw_knee_extension_arrow(frame, leg)


def draw_flexion_guides(
    frame: np.ndarray,
    leg: LegPoints | None,
    target_flexion_degrees: float,
    current_flexion_degrees: float | None,
    stage: str,
) -> None:
    if leg is None:
        return
    h, w = frame.shape[:2]
    knee_px = point_to_pixel(leg.knee, w, h)
    distal_px = point_to_pixel(leg.distal, w, h)
    hip_px = point_to_pixel(leg.hip, w, h)

    target_reached = (
        current_flexion_degrees is not None
        and current_flexion_degrees >= target_flexion_degrees * 0.95
    )
    leg_color = LEG_GOOD_COLOR if target_reached else LEG_NEEDS_WORK_COLOR
    show_guides = not target_reached and stage != "return"

    target = target_distal_for_flexion(leg, target_flexion_degrees)
    if show_guides and target is not None:
        target_px = point_to_pixel(target, w, h)
        draw_dashed_line(frame, knee_px, target_px, GUIDE_BLUE, thickness=3)
        cv2.circle(frame, target_px, 11, GUIDE_BLUE, 2, cv2.LINE_AA)
        if np.linalg.norm(np.array(target_px) - np.array(distal_px)) > 18:
            cv2.arrowedLine(
                frame,
                distal_px,
                target_px,
                GUIDE_ARROW_BLUE,
                4,
                cv2.LINE_AA,
                tipLength=0.22,
            )

    cv2.line(frame, hip_px, knee_px, leg_color, 5, cv2.LINE_AA)
    cv2.line(frame, knee_px, distal_px, leg_color, 5, cv2.LINE_AA)
    cv2.circle(frame, knee_px, 11, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(frame, knee_px, 14, leg_color, 2, cv2.LINE_AA)
    if stage == "hold":
        cv2.circle(frame, distal_px, 14, leg_color, 3, cv2.LINE_AA)


def draw_bed_knee_flexion_guides(
    frame: np.ndarray,
    leg: LegPoints | None,
    *,
    thigh_angle_degrees: float | None,
    flexion_angle_degrees: float | None,
    stage: str,
    stable_position: bool,
) -> None:
    if leg is None:
        return

    h, w = frame.shape[:2]
    hip_px = point_to_pixel(leg.hip, w, h)
    knee_px = point_to_pixel(leg.knee, w, h)
    distal_px = point_to_pixel(leg.distal, w, h)
    leg_color = LEG_GOOD_COLOR if stable_position else LEG_NEEDS_WORK_COLOR

    cv2.line(frame, hip_px, knee_px, leg_color, 5, cv2.LINE_AA)
    cv2.line(frame, knee_px, distal_px, leg_color, 5, cv2.LINE_AA)
    for point in (hip_px, knee_px, distal_px):
        cv2.circle(frame, point, 6, (255, 255, 255), -1, cv2.LINE_AA)

    if stage == "hold":
        return

    thigh_length = float(np.linalg.norm(leg.knee - leg.hip))
    shank_length = float(np.linalg.norm(leg.distal - leg.knee))
    if thigh_length <= 1e-6 or shank_length <= 1e-6:
        return

    horizontal_sign = 1.0 if leg.knee[0] >= leg.hip[0] else -1.0
    horizontal_endpoint = leg.hip + np.array([horizontal_sign, 0.0], dtype=np.float32) * thigh_length
    draw_dashed_line(frame, hip_px, point_to_pixel(horizontal_endpoint, w, h), GUIDE_BLUE, thickness=2)

    if stage == "lift":
        base_angle = 0.0 if thigh_angle_degrees is None else thigh_angle_degrees
        guide_angle = math.radians(min(80.0, max(25.0, base_angle + 18.0)))
        target = leg.hip + np.array(
            [horizontal_sign * math.cos(guide_angle), -math.sin(guide_angle)],
            dtype=np.float32,
        ) * thigh_length
        cv2.arrowedLine(
            frame,
            knee_px,
            point_to_pixel(target, w, h),
            GUIDE_ARROW_BLUE,
            4,
            cv2.LINE_AA,
            tipLength=0.22,
        )
    elif stage == "flex":
        thigh_unit = normalized_vector(leg.hip - leg.knee)
        shank_unit = normalized_vector(leg.distal - leg.knee)
        if thigh_unit is None or shank_unit is None:
            return
        flexion_hint = max(45.0, min(135.0, (flexion_angle_degrees or 0.0) + 25.0))
        rotation_sign = guidance_rotation_sign(thigh_unit, shank_unit, leg.side)
        target_unit = rotate_vector(thigh_unit, rotation_sign * max(10.0, 180.0 - flexion_hint))
        target = leg.knee + target_unit * shank_length
        cv2.arrowedLine(
            frame,
            distal_px,
            point_to_pixel(target, w, h),
            GUIDE_ARROW_BLUE,
            4,
            cv2.LINE_AA,
            tipLength=0.22,
        )


def ankle_foot_angle(leg: LegPoints) -> float | None:
    if not leg.ankle_visible:
        return None
    if leg.heel is None or leg.foot_index is None:
        return None
    foot_length = float(np.linalg.norm(leg.foot_index - leg.heel))
    if foot_length < leg.leg_length * 0.08:
        return None

    shank_angle = math.atan2(leg.ankle[1] - leg.knee[1], leg.ankle[0] - leg.knee[0])
    foot_angle = math.atan2(
        leg.foot_index[1] - leg.heel[1],
        leg.foot_index[0] - leg.heel[0],
    )
    diff = abs(shank_angle - foot_angle)
    while diff > math.tau:
        diff -= math.tau
    if diff > math.pi:
        diff = math.tau - diff
    return math.degrees(diff)


class LegSmoother:
    def __init__(
        self,
        alpha: float = 0.35,
        max_jump_ratio: float = 0.30,
        max_missing_frames: int = VISUAL_MISSING_TOLERANCE_FRAMES,
    ) -> None:
        self.alpha = alpha
        self.max_jump_ratio = max_jump_ratio
        self.max_missing_frames = max_missing_frames
        self.previous: LegPoints | None = None
        self.missing_frames = 0

    def update(self, leg: LegPoints | None) -> LegPoints | None:
        if leg is None:
            self.missing_frames += 1
            if self.previous is not None and self.missing_frames <= self.max_missing_frames:
                return self.previous
            self.previous = None
            return None
        if self.previous is None or self.previous.side != leg.side:
            self.missing_frames = 0
            self.previous = leg
            return leg

        self.missing_frames = 0
        max_jump = leg.leg_length * self.max_jump_ratio

        def smooth_point(current: np.ndarray, previous: np.ndarray) -> np.ndarray:
            delta = current - previous
            delta_norm = float(np.linalg.norm(delta))
            if delta_norm > max_jump:
                current = previous + delta / delta_norm * max_jump
            return previous * (1.0 - self.alpha) + current * self.alpha

        def smooth_optional(
            current: np.ndarray | None,
            previous: np.ndarray | None,
        ) -> np.ndarray | None:
            if current is None:
                return previous
            if previous is None:
                return current
            return smooth_point(current, previous)

        smoothed = LegPoints(
            side=leg.side,
            hip=smooth_point(leg.hip, self.previous.hip),
            knee=smooth_point(leg.knee, self.previous.knee),
            ankle=smooth_point(leg.ankle, self.previous.ankle),
            ankle_visible=leg.ankle_visible,
            heel=smooth_optional(leg.heel, self.previous.heel),
            foot_index=smooth_optional(leg.foot_index, self.previous.foot_index),
            distal=smooth_point(leg.distal, self.previous.distal),
            distal_part=leg.distal_part,
            profile_score=leg.profile_score,
        )
        self.previous = smoothed
        return smoothed


class AnkleAngleFilter:
    def __init__(
        self,
        window_size: int = 7,
        max_missing_frames: int = ANKLE_FILTER_MISSING_TOLERANCE_FRAMES,
    ) -> None:
        self.values: deque[float] = deque(maxlen=window_size)
        self.last_angle: float | None = None
        self.max_missing_frames = max_missing_frames
        self.missing_frames = 0

    def update(self, angle: float | None) -> float | None:
        if angle is None:
            self.missing_frames += 1
            if self.last_angle is not None and self.missing_frames <= self.max_missing_frames:
                return self.last_angle
            return None
        self.missing_frames = 0
        if self.last_angle is not None and abs(angle - self.last_angle) > ANKLE_JUMP_REJECT_DEGREES:
            return self.last_angle
        self.values.append(float(angle))
        filtered = float(np.median(np.asarray(self.values, dtype=np.float32)))
        self.last_angle = filtered
        return filtered

    def reset_cycle(self) -> None:
        self.missing_frames = 0


class ScalarSmoother:
    def __init__(self, alpha: float = 0.30, max_jump: float | None = None) -> None:
        self.alpha = alpha
        self.max_jump = max_jump
        self.value: float | None = None

    def update(self, value: float | None) -> float | None:
        if value is None:
            return self.value
        value = float(value)
        if self.value is None:
            self.value = value
            return self.value
        if self.max_jump is not None and abs(value - self.value) > self.max_jump:
            direction = 1.0 if value > self.value else -1.0
            value = self.value + direction * self.max_jump
        self.value = self.value * (1.0 - self.alpha) + value * self.alpha
        return self.value

    def reset(self) -> None:
        self.value = None


class AngleStabilityTracker:
    def __init__(
        self,
        *,
        window_seconds: float = ANGLE_STABLE_WINDOW_SECONDS,
        max_range_degrees: float = ANGLE_STABLE_RANGE_DEGREES,
    ) -> None:
        self.window_seconds = window_seconds
        self.max_range_degrees = max_range_degrees
        self.values: deque[tuple[float, float]] = deque()

    def update(self, angle: float, now: float) -> bool:
        self.values.append((now, float(angle)))
        while self.values and now - self.values[0][0] > self.window_seconds:
            self.values.popleft()
        if len(self.values) < 4:
            return False
        if self.values[-1][0] - self.values[0][0] < self.window_seconds * 0.5:
            return False
        recent = [value for _timestamp, value in self.values]
        return max(recent) - min(recent) <= self.max_range_degrees

    def reset(self) -> None:
        self.values.clear()


@dataclass
class VisualMotionMetrics:
    movement_ratio: float
    distance_cm: float
    angle_degrees: float
    target_distance_cm: float
    target_angle_degrees: float
    target_ratio: float
    signed_perpendicular_px: float
    axis_unit: np.ndarray | None
    perpendicular_unit: np.ndarray | None
    bed_anchor: np.ndarray | None
    baseline_ankle_adjusted: np.ndarray | None
    projected_ankle: np.ndarray | None

    @property
    def target_reached(self) -> bool:
        return (
            self.movement_ratio >= self.target_ratio * 0.95
            or self.angle_degrees >= self.target_angle_degrees * 0.95
        )


def normalized_vector(vector: np.ndarray | None) -> np.ndarray | None:
    if vector is None:
        return None
    length = float(np.linalg.norm(vector))
    if length <= 1e-6:
        return None
    return vector / length


def visual_baseline_axis_unit(leg: LegPoints) -> np.ndarray | None:
    reference = leg.distal - leg.hip
    reference_unit = normalized_vector(reference)
    if reference_unit is None:
        return None

    weighted_axis = np.zeros(2, dtype=np.float32)
    candidates = [
        (leg.distal - leg.knee, 0.55),
        (leg.distal - leg.hip, 0.35),
        (leg.knee - leg.hip, 0.10),
    ]
    for vector, weight in candidates:
        unit = normalized_vector(vector)
        if unit is None:
            continue
        if float(np.dot(unit, reference_unit)) < 0:
            unit = -unit
        weighted_axis += unit.astype(np.float32) * float(weight)

    axis_unit = normalized_vector(weighted_axis)
    if axis_unit is None:
        return None

    if abs(float(axis_unit[0])) >= VISUAL_BASELINE_HORIZONTAL_SNAP_MIN_X:
        axis_unit = np.array([1.0 if axis_unit[0] >= 0 else -1.0, 0.0], dtype=np.float32)
    return axis_unit.astype(np.float32)


def vector_angle_degrees(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    denominator = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
    if denominator <= 1e-6:
        return 0.0
    cosine = float(np.dot(vector_a, vector_b) / denominator)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def visual_target_for_exercise(exercise: Exercise, leg_length_cm: float) -> tuple[float, float, float]:
    leg_length_cm = max(1.0, leg_length_cm)
    if exercise.target_distance_cm is not None:
        target_distance_cm = float(exercise.target_distance_cm)
        target_ratio = max(0.01, target_distance_cm / leg_length_cm)
        target_angle = math.degrees(math.asin(max(-1.0, min(1.0, target_ratio))))
        return target_ratio, target_distance_cm, target_angle

    target_angle = max(0.0, float(exercise.target_movement_degrees))
    angle_ratio = math.sin(math.radians(target_angle)) if target_angle > 0 else 0.0
    target_ratio = max(exercise.visual_up_threshold, angle_ratio)
    target_distance_cm = target_ratio * leg_length_cm
    if target_angle <= 0:
        target_angle = math.degrees(math.asin(max(-1.0, min(1.0, target_ratio))))
    return target_ratio, target_distance_cm, target_angle


def visual_motion_metrics(
    leg: LegPoints,
    baseline_hip: np.ndarray | None,
    baseline_ankle: np.ndarray | None,
    exercise: Exercise,
    leg_length_cm: float,
    baseline_axis_unit: np.ndarray | None = None,
) -> VisualMotionMetrics | None:
    if baseline_hip is None or baseline_ankle is None:
        return None

    baseline_vector = baseline_ankle - baseline_hip
    current_vector = leg.distal - leg.hip
    baseline_length = float(np.linalg.norm(baseline_vector))
    current_length = float(np.linalg.norm(current_vector))
    if baseline_length < leg.leg_length * 0.25 or current_length < leg.leg_length * 0.25:
        return None

    axis_unit = normalized_vector(baseline_axis_unit)
    if axis_unit is None:
        axis_unit = baseline_vector / baseline_length
    elif float(np.dot(axis_unit, baseline_vector)) < 0:
        axis_unit = -axis_unit
    perpendicular_unit = np.array([-axis_unit[1], axis_unit[0]], dtype=np.float32)
    bed_anchor = baseline_ankle.copy()
    baseline_ankle_adjusted = baseline_ankle.copy()
    signed_perpendicular_px = float(np.dot(leg.distal - baseline_ankle_adjusted, perpendicular_unit))
    projected_ankle = leg.distal - perpendicular_unit * signed_perpendicular_px
    movement_ratio = abs(signed_perpendicular_px) / max(leg.leg_length, 1.0)
    distance_cm = movement_ratio * max(1.0, leg_length_cm)
    angle_degrees = vector_angle_degrees(axis_unit, current_vector)
    target_ratio, target_distance_cm, target_angle = visual_target_for_exercise(exercise, leg_length_cm)

    return VisualMotionMetrics(
        movement_ratio=movement_ratio,
        distance_cm=distance_cm,
        angle_degrees=angle_degrees,
        target_distance_cm=target_distance_cm,
        target_angle_degrees=target_angle,
        target_ratio=target_ratio,
        signed_perpendicular_px=signed_perpendicular_px,
        axis_unit=axis_unit,
        perpendicular_unit=perpendicular_unit,
        bed_anchor=bed_anchor,
        baseline_ankle_adjusted=baseline_ankle_adjusted,
        projected_ankle=projected_ankle,
    )


def smooth_visual_metrics(
    metrics: VisualMotionMetrics | None,
    *,
    ratio_smoother: ScalarSmoother,
    angle_smoother: ScalarSmoother,
    distance_smoother: ScalarSmoother,
) -> VisualMotionMetrics | None:
    if metrics is None:
        ratio_smoother.reset()
        angle_smoother.reset()
        distance_smoother.reset()
        return None

    metrics.movement_ratio = ratio_smoother.update(metrics.movement_ratio) or metrics.movement_ratio
    metrics.angle_degrees = angle_smoother.update(metrics.angle_degrees) or metrics.angle_degrees
    metrics.distance_cm = distance_smoother.update(metrics.distance_cm) or metrics.distance_cm
    return metrics


def draw_extended_line(
    frame: np.ndarray,
    point: np.ndarray,
    direction: np.ndarray,
    color: tuple[int, int, int],
    thickness: int,
) -> None:
    h, w = frame.shape[:2]
    length = float(max(w, h) * 2)
    start = point - direction * length
    end = point + direction * length
    cv2.line(frame, tuple(start.astype(int)), tuple(end.astype(int)), color, thickness)


def draw_leg(
    frame: np.ndarray,
    leg: LegPoints | None,
    *,
    draw_thigh: bool = True,
    draw_shank: bool = True,
    draw_foot: bool = False,
) -> None:
    if leg is None:
        return

    points: list[np.ndarray | None] = []
    lines = []
    if draw_thigh:
        lines.append((leg.hip, leg.knee))
        points.extend([leg.hip, leg.knee])
    if draw_shank:
        lines.append((leg.knee, leg.distal))
        points.extend([leg.knee, leg.distal])
    if draw_foot and leg.ankle_visible and leg.heel is not None:
        lines.append((leg.ankle, leg.heel))
        points.extend([leg.ankle, leg.heel])
    if draw_foot and leg.heel is not None and leg.foot_index is not None:
        lines.append((leg.heel, leg.foot_index))
        points.extend([leg.heel, leg.foot_index])

    for start, end in lines:
        cv2.line(frame, tuple(start.astype(int)), tuple(end.astype(int)), (80, 220, 120), 4)
    drawn_points: set[tuple[int, int]] = set()
    for point in points:
        if point is not None:
            point_px = tuple(point.astype(int))
            if point_px in drawn_points:
                continue
            drawn_points.add(point_px)
            cv2.circle(frame, point_px, 6, (255, 255, 255), -1)


def draw_visual_guides(
    frame: np.ndarray,
    baseline_ankle: np.ndarray | None,
    leg: LegPoints | None,
    exercise: Exercise,
    stage: str,
    baseline_hip: np.ndarray | None = None,
    metrics: VisualMotionMetrics | None = None,
) -> None:
    if baseline_ankle is None or leg is None:
        return

    leg_length = leg.leg_length
    adjusted_baseline = baseline_ankle
    if baseline_hip is not None:
        adjusted_baseline = baseline_ankle + (leg.hip - baseline_hip)

    base = tuple(adjusted_baseline.astype(int))
    up_radius = max(8, int(exercise.visual_up_threshold * leg_length))
    down_radius = max(6, int(exercise.visual_down_threshold * leg_length))

    if metrics is not None and metrics.axis_unit is not None and metrics.perpendicular_unit is not None:
        bed_anchor = metrics.bed_anchor if metrics.bed_anchor is not None else leg.hip
        draw_extended_line(frame, bed_anchor, metrics.axis_unit, (255, 170, 60), 2)

        sign = 1.0 if metrics.signed_perpendicular_px >= 0 else -1.0
        if abs(metrics.signed_perpendicular_px) < 2.0 and metrics.perpendicular_unit[1] > 0:
            sign = -1.0
        target_px = metrics.target_ratio * leg_length
        target_anchor = bed_anchor + metrics.perpendicular_unit * target_px * sign
        draw_extended_line(frame, target_anchor, metrics.axis_unit, (60, 230, 255), 2)

        target_point = (
            metrics.baseline_ankle_adjusted
            if metrics.baseline_ankle_adjusted is not None
            else adjusted_baseline
        ) + metrics.perpendicular_unit * target_px * sign
        cv2.circle(frame, tuple(target_point.astype(int)), 11, (60, 230, 255), 3)

        if metrics.projected_ankle is not None:
            projected = tuple(metrics.projected_ankle.astype(int))
            cv2.line(frame, projected, tuple(leg.distal.astype(int)), (255, 80, 200), 3)
            cv2.circle(frame, projected, 5, (255, 80, 200), -1)

        if metrics.baseline_ankle_adjusted is not None:
            cv2.line(
                frame,
                tuple(leg.hip.astype(int)),
                tuple(metrics.baseline_ankle_adjusted.astype(int)),
                (255, 170, 60),
                2,
            )
        cv2.line(frame, tuple(leg.hip.astype(int)), tuple(leg.distal.astype(int)), (80, 255, 140), 2)
        if metrics.baseline_ankle_adjusted is not None:
            base = tuple(metrics.baseline_ankle_adjusted.astype(int))

        label_origin = tuple((leg.hip + np.array([18, -18], dtype=np.float32)).astype(int))
        cv2.putText(
            frame,
            f"{metrics.angle_degrees:.0f}deg",
            label_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (80, 255, 140),
            2,
            cv2.LINE_AA,
        )
        if metrics.projected_ankle is not None:
            mid = ((metrics.projected_ankle + leg.distal) * 0.5 + np.array([8, -8], dtype=np.float32)).astype(int)
            cv2.putText(
                frame,
                f"{metrics.distance_cm:.0f}cm",
                tuple(mid),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 80, 200),
                2,
                cv2.LINE_AA,
            )
    else:
        cv2.circle(frame, base, down_radius, (90, 180, 255), 2)
        cv2.circle(frame, base, up_radius, (60, 220, 255), 2)
        cv2.line(
            frame,
            (base[0] - up_radius, base[1]),
            (base[0] + up_radius, base[1]),
            (60, 220, 255),
            1,
        )
        cv2.line(
            frame,
            (base[0], base[1] - up_radius),
            (base[0], base[1] + up_radius),
            (60, 220, 255),
            1,
        )

    distal = tuple(leg.distal.astype(int))
    cv2.arrowedLine(frame, base, distal, (255, 230, 80), 3, tipLength=0.18)
    if stage == "hold":
        cv2.circle(frame, distal, 14, (80, 255, 120), 3)


def leg_start_ready(leg: LegPoints, baseline_ankle: np.ndarray | None) -> tuple[bool, str]:
    knee_angle = angle_at(leg.hip, leg.knee, leg.distal)
    if knee_angle < KNEE_STRAIGHT_MIN_DEGREES:
        return False, "膝盖伸直。"
    if baseline_ankle is None:
        return False, "建立起始位。"
    if float(np.linalg.norm(leg.distal - baseline_ankle) / leg.leg_length) >= START_STABILITY_RATIO:
        return False, "起始位保持不动。"
    return True, "起始位稳定。"


def isometric_start_ready(leg: LegPoints, baseline_ankle: np.ndarray | None) -> tuple[bool, str]:
    if baseline_ankle is None:
        return False, "建立起始位。"
    displacement = float(np.linalg.norm(leg.distal - baseline_ankle) / leg.leg_length)
    if displacement >= ISOMETRIC_START_STABILITY_RATIO:
        return False, "起始位保持不动。"
    return True, "起始位稳定。"


def relative_ankle_displacement(
    leg: LegPoints,
    baseline_ankle: np.ndarray,
    baseline_hip: np.ndarray | None,
) -> float:
    if baseline_hip is None:
        delta = leg.distal - baseline_ankle
    else:
        delta = (leg.distal - leg.hip) - (baseline_ankle - baseline_hip)
    return float(np.linalg.norm(delta) / leg.leg_length)


def cycle_seconds(exercise: Exercise) -> float:
    if exercise.timer_phases:
        return sum(phase.duration_seconds for phase in exercise.timer_phases)
    if exercise.mode == "ankle_hybrid":
        return float((exercise.contraction_seconds + exercise.relax_seconds) * 2)
    return float(exercise.contraction_seconds + exercise.relax_seconds)


def detect_pose(pose, frame: np.ndarray):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb.flags.writeable = False
    return pose.process(rgb)


def handle_common_keys(key: int) -> str | None:
    if key == ord("q"):
        request_stop()
        return "quit"
    if key == ord("n"):
        return "skip"
    return None


def window_closed() -> bool:
    if web_stream_enabled():
        return False
    try:
        return cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1
    except Exception:
        return False


def poll_training_key(delay_ms: int = 1) -> int:
    if web_stream_enabled():
        key = read_web_command_key()
        if key is None:
            time.sleep(max(delay_ms, 1) / 1000.0)
            return 255
    else:
        key = cv2.waitKey(delay_ms) & 0xFF
    if key == ord("q") or window_closed():
        request_stop()
        return ord("q")
    return key


def live_preview_until_voice_done(
    *,
    cap: cv2.VideoCapture,
    renderer: TextRenderer,
    speaker: Speaker,
    exercise: Exercise,
    exercise_index: int,
    total_exercises: int,
    completed: int,
    feedback: str,
    extra_lines: list[str] | None = None,
    mirror: bool,
) -> str | None:
    while speaker.is_busy() and not stop_requested():
        camera_frame = read_camera_frame(cap)
        if camera_frame is None:
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        else:
            frame = display_frame_for(camera_frame, mirror)
        frame = render_training_frame(
            renderer=renderer,
            frame=frame,
            exercise=exercise,
            exercise_index=exercise_index,
            total_exercises=total_exercises,
            completed=completed,
            feedback=feedback,
            extra_lines=extra_lines or ["阶段：语音提示", "画面持续刷新中"],
        )
        publish_training_frame(frame)
        key_action = handle_common_keys(poll_training_key(1))
        if key_action in ("quit", "skip"):
            return key_action
    return "quit" if stop_requested() else None


def speak_with_live_preview(
    *,
    cap: cv2.VideoCapture,
    renderer: TextRenderer,
    speaker: Speaker,
    exercise: Exercise,
    exercise_index: int,
    total_exercises: int,
    completed: int,
    text: str,
    feedback: str,
    mirror: bool,
    extra_lines: list[str] | None = None,
) -> str | None:
    speaker.speak(text)
    return live_preview_until_voice_done(
        cap=cap,
        renderer=renderer,
        speaker=speaker,
        exercise=exercise,
        exercise_index=exercise_index,
        total_exercises=total_exercises,
        completed=completed,
        feedback=feedback,
        extra_lines=extra_lines,
        mirror=mirror,
    )


def run_timer_exercise(
    *,
    cap: cv2.VideoCapture,
    pose,
    renderer: TextRenderer,
    speaker: Speaker,
    exercise: Exercise,
    exercise_index: int,
    total_exercises: int,
    side: str,
    mirror: bool,
    reaction_seconds: float,
) -> ExerciseRuntimeResult:
    instruction_start = time.monotonic()
    completed = 0
    warnings: list[str] = []
    ready_stable_frames = 0
    last_instruction_time = 0.0
    started = False
    phase_index = 0
    phase_started_at: float | None = None
    phase_text = "起始位确认"
    frame_feedback = "请先摆好姿势。"
    elapsed_training = 0.0
    smoothed_leg: LegPoints | None = None
    ankle_filter = AnkleAngleFilter()
    loose_isometric_start = exercise.id in LOOSE_ISOMETRIC_START_EXERCISE_IDS
    leg_smoother = (
        LegSmoother(alpha=0.28, max_jump_ratio=0.20, max_missing_frames=8)
        if loose_isometric_start
        else LegSmoother()
    )
    tracked_state = TrackedLegState()
    baseline_ankle: np.ndarray | None = None
    timer_ready_started_at: float | None = None
    knee_angle_text = "--"
    tracking_text = "追踪：--"
    view_text = "侧面：--"
    filtered_angle: float | None = None
    cycle_min_angle: float | None = None
    cycle_max_angle: float | None = None
    cycle_angle_samples = 0
    visual_confirmed_cycles = 0
    best_ankle_angle_range = 0.0
    phase_waiting_for_voice = False
    cycle_ack_pending = False
    phase_paused_at: float | None = None
    visibility_cue_pending = False
    visibility_pause_spoken = False
    visibility_was_paused = False
    consecutive_camera_failures = 0
    voice_gate = VoiceGate(speaker)

    def speak_setup_prompt() -> None:
        if exercise.mode == "ankle_hybrid":
            speaker.speak("脚尖露出来。", interrupt=False)
        elif exercise.mode == "timer":
            speaker.speak("摆好姿势。", interrupt=False)

    voice_gate.start(
        f"{exercise.name}。",
        callback=speak_setup_prompt,
        feedback="正在播报动作名称，请摆好姿势。",
        blocks_logic=False,
    )

    def start_current_phase() -> None:
        nonlocal phase_started_at, phase_text, phase_waiting_for_voice, visibility_cue_pending
        phase = exercise.timer_phases[phase_index]
        phase_text = phase.label
        speaker.speak(phase.cue)
        phase_started_at = None
        phase_waiting_for_voice = True
        visibility_cue_pending = False

    def update_ankle_cycle_angle(angle: float | None) -> None:
        nonlocal cycle_min_angle, cycle_max_angle, cycle_angle_samples
        if angle is None or not started:
            return
        cycle_angle_samples += 1
        cycle_min_angle = angle if cycle_min_angle is None else min(cycle_min_angle, angle)
        cycle_max_angle = angle if cycle_max_angle is None else max(cycle_max_angle, angle)

    def finish_ankle_cycle_quality() -> None:
        nonlocal cycle_min_angle, cycle_max_angle, cycle_angle_samples
        nonlocal visual_confirmed_cycles, best_ankle_angle_range
        if exercise.mode != "ankle_hybrid":
            return
        if cycle_min_angle is not None and cycle_max_angle is not None:
            angle_range = cycle_max_angle - cycle_min_angle
            best_ankle_angle_range = max(best_ankle_angle_range, angle_range)
            if cycle_angle_samples >= ANKLE_MIN_CYCLE_SAMPLES and angle_range >= exercise.target_movement_degrees:
                visual_confirmed_cycles += 1
            elif completed >= 1:
                add_warning(warnings, "踝泵脚尖活动幅度不足或关键点不稳定")
        cycle_min_angle = None
        cycle_max_angle = None
        cycle_angle_samples = 0
        ankle_filter.reset_cycle()

    def timer_quality_metrics() -> dict[str, object]:
        metrics: dict[str, object] = {
            "判定标准": "完成数量",
            "完成次数": completed,
            "目标次数": exercise.target_units,
        }
        if exercise.mode == "ankle_hybrid":
            metrics.update(
                {
                    "目标踝泵角度幅度_deg": round(exercise.target_movement_degrees, 1),
                    "视觉达标循环数": visual_confirmed_cycles,
                    "最大踝泵角度幅度_deg": round(best_ankle_angle_range, 1),
                }
            )
        return metrics

    def finish_timer_result(status: str) -> ExerciseRuntimeResult:
        return finish_result(
            exercise,
            completed,
            status,
            instruction_start,
            warnings,
            metrics=timer_quality_metrics(),
        )

    def active_timer_seconds() -> float:
        if not started or not exercise.timer_phases:
            return 0.0
        cycle_total = cycle_seconds(exercise)
        active_seconds = completed * cycle_total
        active_seconds += sum(phase.duration_seconds for phase in exercise.timer_phases[:phase_index])
        if phase_started_at is None:
            return min(active_seconds, exercise.target_units * cycle_total)
        timer_now = phase_paused_at if phase_paused_at is not None else time.monotonic()
        active_seconds += min(
            max(0.0, timer_now - phase_started_at),
            exercise.timer_phases[phase_index].duration_seconds,
        )
        return min(active_seconds, exercise.target_units * cycle_total)

    while completed < exercise.target_units and not stop_requested():
        camera_frame = read_camera_frame(cap)
        if camera_frame is None:
            consecutive_camera_failures += 1
            if consecutive_camera_failures >= CAMERA_READ_MAX_CONSECUTIVE_FAILURES:
                warnings.append("摄像头连续读取失败")
                break
            continue
        consecutive_camera_failures = 0
        frame = display_frame_for(camera_frame, mirror)

        now = time.monotonic()
        voice_gate.update()
        tracked_leg_visible = False

        if exercise.mode in ("ankle_hybrid", "timer"):
            result = detect_pose(pose, camera_frame)
            if result.pose_landmarks:
                h, w = camera_frame.shape[:2]
                side_feedback_text = side_view_feedback(result.pose_landmarks.landmark)
                view_text = side_feedback_text or "侧面：已确认"
                raw_leg = pick_stable_tracked_leg(result.pose_landmarks.landmark, w, h, side, tracked_state)
                tracked_leg_visible = raw_leg is not None
                smoothed_leg = leg_smoother.update(raw_leg)
                display_leg = leg_for_display(smoothed_leg, w, mirror)
                draw_leg(
                    frame,
                    display_leg,
                    draw_thigh=exercise.mode != "ankle_hybrid",
                    draw_shank=exercise.mode != "ankle_hybrid",
                    draw_foot=exercise.mode == "ankle_hybrid",
                )
                tracking_text = tracked_leg_label(smoothed_leg)
                if smoothed_leg is not None:
                    knee_angle = angle_at(smoothed_leg.hip, smoothed_leg.knee, smoothed_leg.distal)
                    knee_angle_text = f"{knee_angle:.0f} 度，仅参考" if loose_isometric_start else f"{knee_angle:.0f} 度"
                else:
                    knee_angle_text = "--"

                if exercise.mode == "timer":
                    if smoothed_leg is None:
                        ready_stable_frames = 0
                        timer_ready_started_at = None
                        frame_feedback = "请让髋、膝、踝进入画面。"
                    else:
                        if baseline_ankle is None:
                            baseline_ankle = smoothed_leg.distal.copy()
                            timer_ready_started_at = None
                            frame_feedback = "起始位已找到，请保持。"
                        if loose_isometric_start:
                            is_ready, ready_feedback = isometric_start_ready(smoothed_leg, baseline_ankle)
                        else:
                            is_ready, ready_feedback = leg_start_ready(smoothed_leg, baseline_ankle)
                        if not is_ready:
                            if (
                                not loose_isometric_start
                                and "膝盖伸直" in ready_feedback
                                and now - last_instruction_time >= VOICE_REPEAT_SECONDS
                            ):
                                speaker.speak("膝盖伸直。", interrupt=False)
                                last_instruction_time = now
                            if baseline_ankle is not None and "起始位" in ready_feedback:
                                baseline_ankle = smoothed_leg.distal.copy()
                            timer_ready_started_at = None
                            frame_feedback = ready_feedback
                        else:
                            if timer_ready_started_at is None:
                                timer_ready_started_at = now
                            stable_seconds = now - timer_ready_started_at
                            if loose_isometric_start:
                                frame_feedback = (
                                    f"腿部已识别，起始位稳定中 "
                                    f"{stable_seconds:.1f}/{ISOMETRIC_START_HOLD_SECONDS:.1f} 秒。"
                                )
                            else:
                                frame_feedback = f"起始位稳定中 {stable_seconds:.1f}/{ISOMETRIC_START_HOLD_SECONDS:.1f} 秒。"
                            if (
                                stable_seconds >= ISOMETRIC_START_HOLD_SECONDS
                                and not started
                                and not voice_gate.blocks_logic
                            ):
                                def begin_timer_training() -> None:
                                    nonlocal started
                                    if stop_requested():
                                        return
                                    started = True
                                    start_current_phase()

                                voice_gate.start(
                                    "准备，开始。",
                                    reaction_seconds=reaction_seconds,
                                    callback=begin_timer_training,
                                    feedback="听口令，口令结束后开始计时。",
                                    blocks_logic=True,
                                )
                                frame_feedback = "听口令，口令结束后开始计时。"

                if exercise.mode != "ankle_hybrid":
                    filtered_angle = None
                    if tracked_state.locked_side:
                        frame_feedback = f"{frame_feedback} 已锁定{side_label_zh(tracked_state.locked_side)}。"
                else:
                    filtered_angle = ankle_filter.update(ankle_foot_angle(smoothed_leg) if smoothed_leg else None)
                if filtered_angle is None:
                    if exercise.mode == "ankle_hybrid":
                        ready_stable_frames = 0
                        frame_feedback = "脚跟和脚尖需要完整露出。"
                        if now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                            speaker.speak("脚尖露出来。", interrupt=False)
                            last_instruction_time = now
                else:
                    ready_stable_frames += 1
                    update_ankle_cycle_angle(filtered_angle)
                    if not started:
                        frame_feedback = "足踝已识别，保持起始位。"
                        if (
                            ready_stable_frames >= ANKLE_READY_STABLE_FRAMES
                            and not voice_gate.blocks_logic
                        ):
                            def begin_ankle_training() -> None:
                                nonlocal started, frame_feedback
                                if stop_requested():
                                    return
                                started = True
                                start_current_phase()
                                frame_feedback = "跟随节拍做踝泵。"

                            voice_gate.start(
                                "准备，开始。",
                                reaction_seconds=reaction_seconds,
                                callback=begin_ankle_training,
                                feedback="听口令，口令结束后开始踝泵。",
                                blocks_logic=True,
                            )
                            frame_feedback = "听口令，口令结束后开始踝泵。"
            else:
                ready_stable_frames = 0
                leg_smoother.update(None)
                filtered_angle = None
                timer_ready_started_at = None
                frame_feedback = "未检测到下肢。"
                if now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                    speaker.speak("未检测到下肢。", interrupt=False)
                    last_instruction_time = now

        visibility_pause = started and exercise.mode == "timer" and not tracked_leg_visible
        if visibility_pause:
            visibility_was_paused = True
            if not visibility_pause_spoken:
                if speaker.is_busy():
                    speaker.stop()
                speaker.speak("请回到起始位。", interrupt=True)
                visibility_pause_spoken = True
            if phase_waiting_for_voice:
                phase_waiting_for_voice = False
                visibility_cue_pending = True
                phase_started_at = None
            elif phase_started_at is not None and phase_paused_at is None:
                phase_paused_at = time.monotonic()
            frame_feedback = "下肢离开画面，已暂停。请回到起始位。"
            elapsed_training = active_timer_seconds()
        elif visibility_was_paused:
            if phase_started_at is not None:
                if phase_paused_at is not None:
                    phase_started_at += time.monotonic() - phase_paused_at
            phase_paused_at = None
            visibility_pause_spoken = False
            visibility_was_paused = False
            frame_feedback = "下肢已重新识别，继续当前节拍。"

        if started and visibility_cue_pending and not visibility_pause:
            start_current_phase()

        if exercise.mode == "timer" and not started:
            frame_feedback = frame_feedback or "请摆好起始位。"

        if started and exercise.timer_phases and cycle_ack_pending and not visibility_pause:
            if not speaker.is_busy():
                cycle_ack_pending = False
                phase_index = 0
                start_current_phase()
            frame_feedback = "本次已计数，准备下一次。"
            elapsed_training = active_timer_seconds()

        if started and exercise.timer_phases and phase_waiting_for_voice and not cycle_ack_pending and not visibility_pause:
            if speaker.is_busy():
                frame_feedback = "听口令，口令结束后开始计时。"
            else:
                phase_waiting_for_voice = False
                phase_started_at = time.monotonic()
            elapsed_training = active_timer_seconds()

        if (
            started
            and exercise.timer_phases
            and phase_started_at is not None
            and not phase_waiting_for_voice
            and not visibility_pause
        ):
            now = time.monotonic()
            phase = exercise.timer_phases[phase_index]
            phase_text = phase.label
            phase_elapsed = now - phase_started_at
            if exercise.mode == "ankle_hybrid" and filtered_angle is None:
                add_warning(warnings, "踝泵训练中脚跟或脚尖未清晰可见")
            if phase_elapsed >= phase.duration_seconds:
                next_phase_index = phase_index + 1
                if next_phase_index >= len(exercise.timer_phases):
                    completed += 1
                    finish_ankle_cycle_quality()
                    speaker.speak(f"完成 {completed} 次。")
                    next_phase_index = 0
                if completed < exercise.target_units:
                    if next_phase_index == 0:
                        phase_index = 0
                        phase_started_at = None
                        phase_waiting_for_voice = False
                        cycle_ack_pending = True
                    else:
                        phase_index = next_phase_index
                        start_current_phase()
            if exercise.mode == "ankle_hybrid" and filtered_angle is not None:
                angle_range = (
                    0.0
                    if cycle_min_angle is None or cycle_max_angle is None
                    else cycle_max_angle - cycle_min_angle
                )
                frame_feedback = f"脚踝角度已滤波，幅度约 {angle_range:.0f} 度。"
            elif exercise.mode == "timer":
                frame_feedback = "按节拍完成。"
            elapsed_training = active_timer_seconds()

        if voice_gate.blocks_logic:
            frame_feedback = voice_gate.feedback
            elapsed_training = active_timer_seconds()

        frame = render_training_frame(
            renderer=renderer,
            frame=frame,
            exercise=exercise,
            exercise_index=exercise_index,
            total_exercises=total_exercises,
            completed=completed,
            feedback=f"{phase_text}。{frame_feedback}",
            extra_lines=[
                f"阶段：{phase_text}",
                f"计时：{int(elapsed_training)} 秒" if started else "计时：等待起始位",
                tracking_text,
                view_text,
                (
                    f"踝角：{filtered_angle:.0f} 度"
                    if exercise.mode == "ankle_hybrid" and filtered_angle is not None
                    else ""
                ),
                f"膝角：{knee_angle_text}" if exercise.mode == "timer" else "",
            ],
        )
        publish_training_frame(frame)
        key = poll_training_key(1)

        key_action = handle_common_keys(key)
        if key_action == "quit":
            return finish_timer_result("quit")
        if key_action == "skip":
            return finish_timer_result("skipped")

    if stop_requested():
        return finish_timer_result("quit")
    if exercise.mode == "ankle_hybrid" and completed > 0 and visual_confirmed_cycles == 0:
        add_warning(warnings, "踝泵视觉幅度未稳定确认")
    key_action = live_preview_until_voice_done(
        cap=cap,
        renderer=renderer,
        speaker=speaker,
        exercise=exercise,
        exercise_index=exercise_index,
        total_exercises=total_exercises,
        completed=completed,
        feedback="本次计数完成，准备播报动作完成。",
        extra_lines=["阶段：动作完成", "画面持续刷新中"],
        mirror=mirror,
    )
    if key_action == "quit" or stop_requested():
        return finish_timer_result("quit")
    if key_action == "skip":
        return finish_timer_result("completed")
    key_action = speak_with_live_preview(
        cap=cap,
        renderer=renderer,
        speaker=speaker,
        exercise=exercise,
        exercise_index=exercise_index,
        total_exercises=total_exercises,
        completed=completed,
        text=f"{exercise.name}完成。",
        feedback="动作完成，准备切换到下一个动作。",
        extra_lines=["阶段：动作完成", "画面持续刷新中"],
        mirror=mirror,
    )
    if key_action == "quit" or stop_requested():
        return finish_timer_result("quit")
    if key_action == "skip":
        return finish_timer_result("completed")
    return finish_timer_result("completed")


def run_visual_exercise(
    *,
    cap: cv2.VideoCapture,
    pose,
    renderer: TextRenderer,
    speaker: Speaker,
    exercise: Exercise,
    exercise_index: int,
    total_exercises: int,
    side: str,
    mirror: bool,
    reaction_seconds: float,
    leg_length_cm: float,
) -> ExerciseRuntimeResult:
    start = time.monotonic()
    completed = 0
    warnings: list[str] = []
    baseline_ankle: np.ndarray | None = None
    baseline_hip: np.ndarray | None = None
    baseline_knee_angle: float | None = None
    baseline_axis_unit: np.ndarray | None = None
    stage: Literal["setup", "raise", "hold", "return"] = "setup"
    stage_started_at = time.monotonic()
    standard_started_at: float | None = None
    return_started_at: float | None = None
    knee_bent_started_at: float | None = None
    target_reached_started_at: float | None = None
    hold_drop_started_at: float | None = None
    feedback = "请先摆好起始位，让髋、膝、踝都清楚可见。"
    last_warning_time = 0.0
    last_instruction_time = 0.0
    is_angle_only_visual = exercise.id in ANGLE_ONLY_VISUAL_EXERCISE_IDS
    prefer_upper_leg = exercise.id == "side_lying_hip_abduction"
    leg_smoother = LegSmoother(alpha=0.30, max_jump_ratio=0.22)
    tracked_state = TrackedLegState()
    displacement_smoother = ScalarSmoother(alpha=0.25, max_jump=0.10)
    knee_angle_smoother = ScalarSmoother(alpha=0.30, max_jump=18.0)
    knee_line_smoother = ScalarSmoother(alpha=0.25, max_jump=0.10)
    movement_angle_smoother = ScalarSmoother(alpha=0.25, max_jump=12.0)
    metrics_angle_smoother = ScalarSmoother(alpha=0.25, max_jump=12.0)
    movement_distance_smoother = ScalarSmoother(alpha=0.25, max_jump=12.0)
    consecutive_camera_failures = 0
    voice_gate = VoiceGate(speaker)
    max_raise_angle = 0.0
    qualified_hold_seconds = 0.0
    longest_qualified_hold_seconds = 0.0
    current_qualified_hold_seconds = 0.0
    last_quality_sample_time: float | None = None
    _, _, target_angle_for_metrics = visual_target_for_exercise(exercise, leg_length_cm)

    def reset_motion_smoothers() -> None:
        displacement_smoother.reset()
        movement_angle_smoother.reset()
        metrics_angle_smoother.reset()
        movement_distance_smoother.reset()

    def capture_visual_baseline(leg: LegPoints, knee_angle: float) -> None:
        nonlocal baseline_ankle, baseline_hip, baseline_knee_angle, baseline_axis_unit
        baseline_ankle = leg.distal.copy()
        baseline_hip = leg.hip.copy()
        baseline_knee_angle = knee_angle
        baseline_axis_unit = visual_baseline_axis_unit(leg)

    def visual_quality_metrics() -> tuple[dict[str, object], float]:
        target_total_hold = max(0.0, exercise.target_units * exercise.target_hold_seconds)
        achievement = (
            min(qualified_hold_seconds / target_total_hold, 1.0) * 100.0
            if target_total_hold > 0
            else 0.0
        )
        metrics: dict[str, object] = {
            "判定标准": "抬腿角度达标保持时长和最大抬腿角度",
            "目标抬腿角度_deg": round(target_angle_for_metrics, 1),
            "达标保持目标总时长_s": round(target_total_hold, 1),
            "达标保持总时长_s": round(qualified_hold_seconds, 1),
            "最长连续达标保持_s": round(longest_qualified_hold_seconds, 1),
            "最大抬腿角度_deg": round(max_raise_angle, 1),
            "完成回合数": completed,
            "目标回合数": exercise.target_units,
        }
        return metrics, achievement

    def finish_visual_result(status: str) -> ExerciseRuntimeResult:
        metrics, achievement = visual_quality_metrics()
        return finish_result(
            exercise,
            completed,
            status,
            start,
            warnings,
            metrics=metrics,
            achievement_percent=achievement,
        )

    start_voice_sequence(
        voice_gate,
        ((f"{exercise.name}。", 0.0), (visual_setup_prompt(exercise), 0.0)),
        feedback="正在播报体位提示，请摆好姿势。",
        blocks_logic=True,
    )

    while completed < exercise.target_units and not stop_requested():
        camera_frame = read_camera_frame(cap)
        if camera_frame is None:
            consecutive_camera_failures += 1
            if consecutive_camera_failures >= CAMERA_READ_MAX_CONSECUTIVE_FAILURES:
                warnings.append("摄像头连续读取失败")
                break
            continue
        consecutive_camera_failures = 0
        frame = display_frame_for(camera_frame, mirror)
        voice_gate.update()

        result = detect_pose(pose, camera_frame)
        current_angle_text = "--"
        movement_angle_text = "--"
        tracking_text = "追踪：--"
        view_text = "侧面：--"
        distance_text = "--"
        target_ratio, target_distance_cm, target_angle_degrees = visual_target_for_exercise(
            exercise,
            leg_length_cm,
        )
        target_text = (
            f"{target_angle_degrees:.0f} 度"
            if is_angle_only_visual
            else f"{target_angle_degrees:.0f} 度 / {target_distance_cm:.1f} cm"
        )
        hold_text = "--"
        motion_metrics: VisualMotionMetrics | None = None
        raw_displacement = 0.0
        raw_movement_angle = 0.0
        current_raise_angle: float | None = None

        if not result.pose_landmarks:
            leg_smoother.update(None)
            last_quality_sample_time = None
            current_qualified_hold_seconds = 0.0
            feedback = "未检测到人体，请后退半步并完整露出下肢。"
        else:
            h, w = camera_frame.shape[:2]
            side_feedback_text = side_view_feedback(result.pose_landmarks.landmark)
            view_text = side_feedback_text or "侧面：已确认"
            raw_leg = pick_stable_tracked_leg(
                result.pose_landmarks.landmark,
                w,
                h,
                side,
                tracked_state,
                prefer_upper_leg=prefer_upper_leg,
            )
            leg = leg_smoother.update(raw_leg)
            display_leg = leg_for_display(leg, w, mirror)
            if not is_angle_only_visual:
                draw_leg(frame, display_leg, draw_thigh=True, draw_shank=True, draw_foot=False)
            tracking_text = tracked_leg_label(leg)

            if leg is None:
                last_quality_sample_time = None
                current_qualified_hold_seconds = 0.0
                feedback = "请确保髋、膝、踝三个关键点都清晰可见。"
            else:
                now = time.monotonic()
                knee_angle = knee_angle_smoother.update(knee_extension_angle(leg)) or 0.0
                knee_line_ratio = knee_line_smoother.update(knee_line_deviation_ratio(leg)) or 0.0
                current_angle_text = f"{knee_angle:.0f} 度 / 偏移 {knee_line_ratio:.2f}"
                if is_angle_only_visual:
                    current_raise_angle = (
                        movement_angle_smoother.update(leg_raise_angle_degrees(leg)) or 0.0
                    )
                    max_raise_angle = max(max_raise_angle, current_raise_angle)
                    raw_movement_angle = current_raise_angle
                    movement_angle_text = f"{current_raise_angle:.0f} / {target_angle_degrees:.0f} 度"
                knee_bent_candidate = (
                    knee_line_ratio > VISUAL_KNEE_LINE_MAX_RATIO
                    or knee_angle < VISUAL_KNEE_STRAIGHT_MIN_DEGREES
                )
                if knee_bent_candidate:
                    if knee_bent_started_at is None:
                        knee_bent_started_at = now
                    knee_bent_confirmed = now - knee_bent_started_at >= VISUAL_KNEE_BENT_CONFIRM_SECONDS
                else:
                    knee_bent_started_at = None
                    knee_bent_confirmed = False
                knee_straight = not knee_bent_confirmed
                if is_angle_only_visual:
                    qualified_now = (
                        current_raise_angle is not None
                        and current_raise_angle >= target_angle_degrees * 0.95
                        and knee_straight
                        and stage in ("raise", "hold")
                    )
                    if last_quality_sample_time is not None:
                        sample_delta = min(max(0.0, now - last_quality_sample_time), 0.2)
                        if qualified_now:
                            qualified_hold_seconds += sample_delta
                            current_qualified_hold_seconds += sample_delta
                            longest_qualified_hold_seconds = max(
                                longest_qualified_hold_seconds,
                                current_qualified_hold_seconds,
                            )
                        else:
                            current_qualified_hold_seconds = 0.0
                    last_quality_sample_time = now

                if baseline_ankle is not None:
                    raw_motion_metrics = visual_motion_metrics(
                        leg,
                        baseline_hip,
                        baseline_ankle,
                        exercise,
                        leg_length_cm,
                        baseline_axis_unit,
                    )
                    if raw_motion_metrics is not None:
                        raw_displacement = raw_motion_metrics.movement_ratio
                        if not is_angle_only_visual:
                            raw_movement_angle = raw_motion_metrics.angle_degrees
                    motion_metrics = smooth_visual_metrics(
                        raw_motion_metrics,
                        ratio_smoother=displacement_smoother,
                        angle_smoother=metrics_angle_smoother,
                        distance_smoother=movement_distance_smoother,
                    )
                    if motion_metrics is not None:
                        displacement = motion_metrics.movement_ratio
                        if not is_angle_only_visual:
                            movement_angle_text = (
                                f"{motion_metrics.angle_degrees:.0f} / "
                                f"{motion_metrics.target_angle_degrees:.0f} 度"
                            )
                            distance_text = (
                                f"{motion_metrics.distance_cm:.1f} / "
                                f"{motion_metrics.target_distance_cm:.1f} cm"
                            )
                    else:
                        raw_displacement = relative_ankle_displacement(leg, baseline_ankle, baseline_hip)
                        displacement = displacement_smoother.update(raw_displacement) or raw_displacement
                        if not is_angle_only_visual:
                            raw_movement_angle = 0.0
                else:
                    displacement = 0.0
                    reset_motion_smoothers()

                display_baseline_ankle = mirror_point_for_display(baseline_ankle, w, mirror)
                display_baseline_hip = mirror_point_for_display(baseline_hip, w, mirror)
                display_metrics = visual_metrics_for_display(motion_metrics, w, mirror)
                if is_angle_only_visual:
                    draw_angle_only_leg_raise_guides(
                        frame,
                        display_leg,
                        target_angle_degrees=target_angle_degrees,
                        current_angle_degrees=current_raise_angle,
                        knee_straight=knee_straight,
                        stage=stage,
                    )
                else:
                    draw_visual_guides(
                        frame,
                        display_baseline_ankle,
                        display_leg,
                        exercise,
                        stage,
                        display_baseline_hip,
                        display_metrics,
                    )

                if voice_gate.blocks_logic:
                    feedback = voice_gate.feedback
                elif not knee_straight and stage != "return":
                    feedback = "膝盖偏离直线较明显，请伸直后再抬。"
                    add_warning(warnings, "膝关节未保持伸直")
                    standard_started_at = None
                    return_started_at = None
                    if now - last_warning_time >= VISUAL_KNEE_WARNING_REPEAT_SECONDS:
                        speaker.speak("膝盖伸直。", interrupt=False)
                        last_warning_time = now
                else:
                    if stage == "setup":
                        if baseline_ankle is not None and motion_metrics is None:
                            raw_displacement = relative_ankle_displacement(leg, baseline_ankle, baseline_hip)
                            displacement = displacement_smoother.update(raw_displacement) or raw_displacement
                        if baseline_ankle is None:
                            capture_visual_baseline(leg, knee_angle)
                            reset_motion_smoothers()
                            stage_started_at = now
                            feedback = "起始位已找到，请保持不动。"
                        elif displacement < 0.03:
                            stable_seconds = now - stage_started_at
                            hold_text = f"{stable_seconds:.1f}/{VISUAL_START_HOLD_SECONDS:.1f} 秒"
                            feedback = "起始位稳定中，保持住。"
                            if stable_seconds >= VISUAL_START_HOLD_SECONDS and not voice_gate.blocks_logic:
                                ready_leg = leg
                                ready_knee_angle = knee_angle

                                def begin_raise() -> None:
                                    nonlocal stage, stage_started_at, last_instruction_time
                                    nonlocal target_reached_started_at, hold_drop_started_at, feedback
                                    if stop_requested():
                                        return
                                    capture_visual_baseline(ready_leg, ready_knee_angle)
                                    reset_motion_smoothers()
                                    target_reached_started_at = None
                                    hold_drop_started_at = None
                                    stage = "raise"
                                    stage_started_at = time.monotonic()
                                    last_instruction_time = stage_started_at
                                    feedback = "起始位达标，现在慢慢抬到标准位置。"

                                start_voice_sequence(
                                    voice_gate,
                                    (("准备，开始。", reaction_seconds), ("抬起。", 0.0)),
                                    final_callback=begin_raise,
                                    feedback="听口令，口令结束后开始抬起。",
                                    blocks_logic=True,
                                )
                                feedback = "听口令，口令结束后开始抬起。"
                        else:
                            capture_visual_baseline(leg, knee_angle)
                            reset_motion_smoothers()
                            stage_started_at = now
                            feedback = "请先稳定起始位，不要急着抬。"

                    elif stage == "raise":
                        if is_angle_only_visual:
                            target_reached = (
                                current_raise_angle is not None
                                and current_raise_angle >= target_angle_degrees * 0.95
                            )
                        else:
                            target_reached = (
                                motion_metrics.target_reached
                                if motion_metrics is not None
                                else displacement >= target_ratio
                            )
                        if target_reached:
                            if target_reached_started_at is None:
                                target_reached_started_at = now
                            target_confirm_seconds = now - target_reached_started_at
                        else:
                            target_reached_started_at = None
                            target_confirm_seconds = 0.0

                        if target_reached and target_confirm_seconds >= VISUAL_TARGET_CONFIRM_SECONDS:
                            def begin_hold() -> None:
                                nonlocal stage, standard_started_at, stage_started_at
                                nonlocal target_reached_started_at, hold_drop_started_at
                                nonlocal last_instruction_time, feedback
                                if stop_requested():
                                    return
                                stage = "hold"
                                standard_started_at = time.monotonic()
                                stage_started_at = standard_started_at
                                target_reached_started_at = None
                                hold_drop_started_at = None
                                last_instruction_time = stage_started_at
                                feedback = "已到标准位置，保持住。"

                            voice_gate.start(
                                "保持。",
                                callback=begin_hold,
                                feedback="听口令，口令结束后开始保持。",
                                blocks_logic=True,
                            )
                            feedback = "听口令，口令结束后开始保持。"
                        else:
                            if target_reached:
                                feedback = "已到目标线，稳定一下。"
                            else:
                                feedback = "继续慢慢抬到目标线，骨盆和躯干保持稳定。"
                            if not target_reached and now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                                speaker.speak("抬起。", interrupt=False)
                                last_instruction_time = now

                    elif stage == "hold":
                        if is_angle_only_visual:
                            hold_drop_threshold = max(
                                VISUAL_RETURN_MIN_ANGLE_DEGREES,
                                target_angle_degrees * VISUAL_HOLD_DROP_RATIO,
                            )
                            hold_dropped = current_raise_angle is None or current_raise_angle < hold_drop_threshold
                        else:
                            hold_drop_threshold = (
                                max(exercise.visual_down_threshold, motion_metrics.target_ratio * VISUAL_HOLD_DROP_RATIO)
                                if motion_metrics is not None
                                else max(exercise.visual_down_threshold, target_ratio * VISUAL_HOLD_DROP_RATIO)
                            )
                            hold_dropped = displacement < hold_drop_threshold

                        if hold_dropped:
                            if hold_drop_started_at is None:
                                hold_drop_started_at = now
                            drop_seconds = now - hold_drop_started_at
                            held_seconds = 0.0 if standard_started_at is None else max(0.0, now - standard_started_at)
                            hold_text = f"{held_seconds:.1f}/{exercise.target_hold_seconds:.1f} 秒"
                            if drop_seconds >= VISUAL_HOLD_GRACE_SECONDS:
                                standard_started_at = None
                                hold_drop_started_at = None
                                target_reached_started_at = None
                                stage = "raise"
                                feedback = "位置掉出目标线，请重新抬回标准位置。"
                                if now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                                    speaker.speak("重新抬起。", interrupt=False)
                                    last_instruction_time = now
                            else:
                                feedback = "检测到短暂偏低，请抬回目标线。"
                        else:
                            hold_drop_started_at = None
                            if is_angle_only_visual:
                                hold_threshold = target_angle_degrees * 0.85
                                below_hold_threshold = (
                                    current_raise_angle is not None
                                    and current_raise_angle < hold_threshold
                                )
                            else:
                                hold_threshold = (
                                    motion_metrics.target_ratio * 0.85
                                    if motion_metrics is not None
                                    else target_ratio * 0.85
                                )
                                below_hold_threshold = displacement < hold_threshold
                            if standard_started_at is None:
                                standard_started_at = time.monotonic()
                            now = time.monotonic()
                            held_seconds = now - standard_started_at
                            hold_text = f"{held_seconds:.1f}/{exercise.target_hold_seconds:.1f} 秒"
                            remaining = max(0.0, exercise.target_hold_seconds - held_seconds)
                            if below_hold_threshold:
                                feedback = f"接近目标线，继续保持，还需 {remaining:.1f} 秒。"
                            else:
                                feedback = f"标准位保持中，还需 {remaining:.1f} 秒。"
                            if held_seconds >= exercise.target_hold_seconds:
                                def begin_return() -> None:
                                    nonlocal stage, return_started_at, stage_started_at
                                    nonlocal hold_drop_started_at, feedback
                                    if stop_requested():
                                        return
                                    stage = "return"
                                    return_started_at = None
                                    stage_started_at = time.monotonic()
                                    hold_drop_started_at = None
                                    feedback = "保持达标，现在慢慢放回起始位。"

                                voice_gate.start(
                                    "放下。",
                                    callback=begin_return,
                                    feedback="听口令，口令结束后慢慢放下。",
                                    blocks_logic=True,
                                )
                                feedback = "听口令，口令结束后慢慢放下。"

                    elif stage == "return":
                        return_angle_threshold = max(
                            VISUAL_RETURN_MIN_ANGLE_DEGREES,
                            (motion_metrics.target_angle_degrees if motion_metrics is not None else target_angle_degrees)
                            * VISUAL_RETURN_ANGLE_FRACTION,
                        )
                        if is_angle_only_visual:
                            return_ready = (
                                current_raise_angle is not None
                                and current_raise_angle <= return_angle_threshold
                            )
                        else:
                            return_ratio_threshold = (
                                max(
                                    exercise.visual_down_threshold * VISUAL_RETURN_RATIO_MULTIPLIER,
                                    (motion_metrics.target_ratio if motion_metrics is not None else target_ratio)
                                    * VISUAL_RETURN_RATIO_FRACTION,
                                )
                            )
                            return_ready = (
                                displacement <= return_ratio_threshold
                                or raw_displacement <= exercise.visual_down_threshold
                                or (
                                    raw_movement_angle > 0.0
                                    and raw_movement_angle <= return_angle_threshold
                                )
                                or (
                                    motion_metrics is not None
                                    and motion_metrics.angle_degrees <= return_angle_threshold
                                )
                            )
                        if return_ready:
                            if return_started_at is None:
                                return_started_at = now
                            return_seconds = now - return_started_at
                            hold_text = f"{return_seconds:.1f}/{VISUAL_RETURN_HOLD_SECONDS:.1f} 秒"
                            feedback = "已经回到起始位，保持稳定完成计数。"
                            if return_seconds >= VISUAL_RETURN_HOLD_SECONDS:
                                completed += 1
                                capture_visual_baseline(leg, knee_angle)
                                reset_motion_smoothers()
                                standard_started_at = None
                                return_started_at = None
                                target_reached_started_at = None
                                hold_drop_started_at = None
                                if completed < exercise.target_units:
                                    def begin_next_raise() -> None:
                                        nonlocal stage, stage_started_at, feedback, last_instruction_time
                                        if stop_requested():
                                            return
                                        stage = "raise"
                                        stage_started_at = time.monotonic()
                                        last_instruction_time = stage_started_at
                                        feedback = "完成一次。继续下一次，慢慢抬到标准位置。"

                                    start_voice_sequence(
                                        voice_gate,
                                        ((f"完成 {completed} 次。", 0.0), ("抬起。", 0.0)),
                                        final_callback=begin_next_raise,
                                        feedback="本次已计数，听口令准备下一次。",
                                        blocks_logic=True,
                                    )
                                    feedback = "本次已计数，听口令准备下一次。"
                                else:
                                    speaker.speak(f"完成 {completed} 次。")
                        else:
                            return_started_at = None
                            if is_angle_only_visual:
                                angle_for_feedback = 0.0 if current_raise_angle is None else current_raise_angle
                                feedback = (
                                    "慢慢放回起始位。"
                                    f"当前抬高约 {angle_for_feedback:.0f} 度，"
                                    f"目标小于 {return_angle_threshold:.0f} 度。"
                                )
                            else:
                                feedback = (
                                    "慢慢放回起始位。"
                                    f"当前离床约 {displacement * leg_length_cm:.1f} 厘米，"
                                    f"目标小于 {return_ratio_threshold * leg_length_cm:.1f} 厘米。"
                                )

        stage_text = {
            "setup": "起始位确认",
            "raise": "进入标准位",
            "hold": "标准位保持",
            "return": "控制放回",
        }[stage]
        extra_lines = [
            f"阶段：{stage_text}",
            tracking_text,
            view_text,
            f"膝关节内角：{current_angle_text}",
            f"抬高角：{movement_angle_text}",
            f"最大抬高角：{max_raise_angle:.0f} 度",
            f"达标保持：{qualified_hold_seconds:.1f} 秒",
            f"目标：{target_text}",
            f"保持时间：{hold_text}",
            "按 r 可重置起始位",
        ]
        if not is_angle_only_visual:
            extra_lines.insert(5, f"离床距离：{distance_text}")
        frame = render_training_frame(
            renderer=renderer,
            frame=frame,
            exercise=exercise,
            exercise_index=exercise_index,
            total_exercises=total_exercises,
            completed=completed,
            feedback=feedback,
            extra_lines=extra_lines,
        )
        publish_training_frame(frame)
        key = poll_training_key(1)
        key_action = handle_common_keys(key)
        if key_action == "quit":
            return finish_visual_result("quit")
        if key_action == "skip":
            return finish_visual_result("skipped")
        if key == ord("r"):
            voice_gate.cancel(stop_voice=True)
            baseline_ankle = None
            baseline_hip = None
            baseline_knee_angle = None
            baseline_axis_unit = None
            stage = "setup"
            stage_started_at = time.monotonic()
            standard_started_at = None
            return_started_at = None
            target_reached_started_at = None
            hold_drop_started_at = None
            tracked_state.reset()
            leg_smoother.update(None)
            reset_motion_smoothers()
            knee_angle_smoother.reset()
            knee_line_smoother.reset()
            knee_bent_started_at = None
            feedback = "已重置起始位，请把腿放回起始位置。"
            speaker.speak("已重置。")

    if stop_requested():
        return finish_visual_result("quit")
    key_action = live_preview_until_voice_done(
        cap=cap,
        renderer=renderer,
        speaker=speaker,
        exercise=exercise,
        exercise_index=exercise_index,
        total_exercises=total_exercises,
        completed=completed,
        feedback="本次计数完成，准备播报动作完成。",
        extra_lines=["阶段：动作完成", "画面持续刷新中"],
        mirror=mirror,
    )
    if key_action == "quit" or stop_requested():
        return finish_visual_result("quit")
    if key_action == "skip":
        return finish_visual_result("completed")
    key_action = speak_with_live_preview(
        cap=cap,
        renderer=renderer,
        speaker=speaker,
        exercise=exercise,
        exercise_index=exercise_index,
        total_exercises=total_exercises,
        completed=completed,
        text=f"{exercise.name}完成。",
        feedback="动作完成，准备切换到下一个动作。",
        extra_lines=["阶段：动作完成", "画面持续刷新中"],
        mirror=mirror,
    )
    if key_action == "quit" or stop_requested():
        return finish_visual_result("quit")
    if key_action == "skip":
        return finish_visual_result("completed")
    return finish_visual_result("completed")


def run_flexion_visual_exercise(
    *,
    cap: cv2.VideoCapture,
    pose,
    renderer: TextRenderer,
    speaker: Speaker,
    exercise: Exercise,
    exercise_index: int,
    total_exercises: int,
    side: str,
    mirror: bool,
    reaction_seconds: float,
) -> ExerciseRuntimeResult:
    start = time.monotonic()
    completed = 0
    warnings: list[str] = []
    target_flexion = float(exercise.target_flexion_degrees or 70.0)
    target_lift = max(0.0, float(exercise.target_lift_degrees))
    needs_lift = target_lift > 0.0

    baseline_distal: np.ndarray | None = None
    baseline_hip: np.ndarray | None = None
    stage: Literal["setup", "lift", "flex", "hold", "return"] = "setup"
    stage_started_at = time.monotonic()
    hold_started_at: float | None = None
    return_started_at: float | None = None
    last_instruction_time = 0.0
    feedback = "请先伸直患腿，侧面完整露出髋、膝和小腿末端。"

    tracked_state = TrackedLegState()
    leg_smoother = LegSmoother(alpha=0.35, max_jump_ratio=0.22)
    flexion_smoother = ScalarSmoother(alpha=0.30, max_jump=18.0)
    lift_smoother = ScalarSmoother(alpha=0.30, max_jump=12.0)
    flexion_stability = AngleStabilityTracker()
    lift_stability = AngleStabilityTracker(max_range_degrees=5.0)
    flexion_target_started_at: float | None = None
    lift_target_started_at: float | None = None
    consecutive_camera_failures = 0
    voice_gate = VoiceGate(speaker)
    max_flexion_angle = 0.0
    target_reached_reps = 0
    rep_target_counted = False

    voice_gate.start(
        f"{exercise.name}。",
        callback=lambda: speaker.speak("摆好姿势。", interrupt=False),
        feedback="正在播报动作名称，请摆好姿势。",
        blocks_logic=False,
    )

    def flexion_quality_metrics() -> tuple[dict[str, object], float]:
        achievement = (
            min(max_flexion_angle / max(target_flexion, 1.0), 1.0) * 100.0
        )
        target_met = max_flexion_angle >= target_flexion * 0.95
        metrics: dict[str, object] = {
            "判定标准": "是否达到预设弯曲角度和最大屈膝角度",
            "目标屈膝角度_deg": round(target_flexion, 1),
            "最大屈膝角度_deg": round(max_flexion_angle, 1),
            "是否达到目标屈膝角": target_met,
            "屈膝角达标次数": target_reached_reps,
            "完成回合数": completed,
            "目标回合数": exercise.target_units,
        }
        return metrics, achievement

    def finish_flexion_result(status: str) -> ExerciseRuntimeResult:
        metrics, achievement = flexion_quality_metrics()
        return finish_result(
            exercise,
            completed,
            status,
            start,
            warnings,
            metrics=metrics,
            achievement_percent=achievement,
        )

    while completed < exercise.target_units and not stop_requested():
        camera_frame = read_camera_frame(cap)
        if camera_frame is None:
            consecutive_camera_failures += 1
            if consecutive_camera_failures >= CAMERA_READ_MAX_CONSECUTIVE_FAILURES:
                warnings.append("摄像头连续读取失败")
                break
            continue
        consecutive_camera_failures = 0
        frame = display_frame_for(camera_frame, mirror)
        voice_gate.update()

        result = detect_pose(pose, camera_frame)
        tracking_text = "追踪：--"
        view_text = "侧面：--"
        flexion_text = "--"
        lift_text = "--"
        hold_text = "--"

        if not result.pose_landmarks:
            leg_smoother.update(None)
            feedback = "未检测到下肢，请侧面进入画面。"
        else:
            h, w = camera_frame.shape[:2]
            side_feedback_text = side_view_feedback(result.pose_landmarks.landmark)
            view_text = side_feedback_text or "侧面：已确认"
            raw_leg = pick_stable_tracked_leg(result.pose_landmarks.landmark, w, h, side, tracked_state)
            leg = leg_smoother.update(raw_leg)
            display_leg = leg_for_display(leg, w, mirror)
            tracking_text = tracked_leg_label(leg)

            if leg is None:
                feedback = "请确保髋、膝和小腿末端都清晰可见。"
            else:
                now = time.monotonic()
                flexion = flexion_smoother.update(knee_flexion_angle(leg)) or 0.0
                max_flexion_angle = max(max_flexion_angle, flexion)
                flexion_stable = flexion_stability.update(flexion, now)
                flexion_text = f"{flexion:.0f}/{target_flexion:.0f} 度"
                draw_flexion_guides(
                    frame,
                    display_leg,
                    target_flexion,
                    flexion,
                    stage,
                )

                if baseline_distal is not None and baseline_hip is not None:
                    baseline_vector = baseline_distal - baseline_hip
                    current_vector = leg.distal - leg.hip
                    lift_angle = lift_smoother.update(vector_angle_degrees(baseline_vector, current_vector)) or 0.0
                    lift_stable = lift_stability.update(lift_angle, now)
                else:
                    lift_angle = 0.0
                    lift_stable = False
                    lift_smoother.reset()
                    lift_stability.reset()
                lift_text = f"{lift_angle:.0f}/{target_lift:.0f} 度" if needs_lift else "--"

                if voice_gate.blocks_logic:
                    feedback = voice_gate.feedback

                elif stage == "setup":
                    if baseline_distal is None:
                        baseline_distal = leg.distal.copy()
                        baseline_hip = leg.hip.copy()
                        stage_started_at = now
                        feedback = "起始位已找到，请伸直保持。"
                    elif flexion > FLEXION_START_MAX_DEGREES:
                        baseline_distal = leg.distal.copy()
                        baseline_hip = leg.hip.copy()
                        flexion_smoother.reset()
                        lift_smoother.reset()
                        flexion_stability.reset()
                        lift_stability.reset()
                        flexion_target_started_at = None
                        lift_target_started_at = None
                        stage_started_at = now
                        feedback = "先把膝盖伸直，再开始。"
                        if now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                            speaker.speak("膝盖伸直。", interrupt=False)
                            last_instruction_time = now
                    elif float(np.linalg.norm(leg.distal - baseline_distal) / leg.leg_length) > START_STABILITY_RATIO:
                        baseline_distal = leg.distal.copy()
                        baseline_hip = leg.hip.copy()
                        lift_smoother.reset()
                        lift_stability.reset()
                        flexion_target_started_at = None
                        lift_target_started_at = None
                        stage_started_at = now
                        feedback = "起始位保持不动。"
                    else:
                        stable_seconds = now - stage_started_at
                        hold_text = f"{stable_seconds:.1f}/{VISUAL_START_HOLD_SECONDS:.1f} 秒"
                        feedback = "起始位稳定中，保持住。"
                        if stable_seconds >= VISUAL_START_HOLD_SECONDS:
                            next_cue = "上抬。" if needs_lift else "弯曲。"

                            def begin_flexion_motion() -> None:
                                nonlocal stage, stage_started_at, last_instruction_time
                                nonlocal flexion_target_started_at, lift_target_started_at, feedback
                                if stop_requested():
                                    return
                                if needs_lift:
                                    stage = "lift"
                                    feedback = "先慢慢上抬到目标角度。"
                                else:
                                    stage = "flex"
                                    feedback = "慢慢弯曲到目标角度。"
                                stage_started_at = time.monotonic()
                                last_instruction_time = stage_started_at
                                flexion_target_started_at = None
                                lift_target_started_at = None

                            start_voice_sequence(
                                voice_gate,
                                (("准备，开始。", reaction_seconds), (next_cue, 0.0)),
                                final_callback=begin_flexion_motion,
                                feedback="听口令，口令结束后开始动作。",
                                blocks_logic=True,
                            )
                            feedback = "听口令，口令结束后开始动作。"

                elif stage == "lift":
                    if lift_angle >= target_lift * 0.95 and lift_stable:
                        if lift_target_started_at is None:
                            lift_target_started_at = now
                        lift_ready = now - lift_target_started_at >= ANGLE_TARGET_CONFIRM_SECONDS
                    else:
                        lift_target_started_at = None
                        lift_ready = False

                    if lift_ready:
                        def begin_flex_after_lift() -> None:
                            nonlocal stage, stage_started_at, flexion_target_started_at, feedback
                            if stop_requested():
                                return
                            stage = "flex"
                            stage_started_at = time.monotonic()
                            flexion_target_started_at = None
                            feedback = "上抬达标，现在慢慢屈膝。"

                        voice_gate.start(
                            "弯曲。",
                            callback=begin_flex_after_lift,
                            feedback="听口令，口令结束后开始屈膝。",
                            blocks_logic=True,
                        )
                        feedback = "听口令，口令结束后开始屈膝。"
                    else:
                        feedback = "继续慢慢上抬，膝盖保持伸直。" if lift_angle < target_lift * 0.95 else "上抬角度到了，保持稳定。"
                        if flexion > FLEXION_RETURN_MAX_DEGREES:
                            add_warning(warnings, "直腿屈膝上抬阶段膝关节过早弯曲")
                        if now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                            speaker.speak("上抬。", interrupt=False)
                            last_instruction_time = now

                elif stage == "flex":
                    if flexion >= target_flexion * 0.95 and flexion_stable:
                        if flexion_target_started_at is None:
                            flexion_target_started_at = now
                        flexion_ready = now - flexion_target_started_at >= ANGLE_TARGET_CONFIRM_SECONDS
                    else:
                        flexion_target_started_at = None
                        flexion_ready = False

                    if flexion_ready:
                        def begin_flexion_hold() -> None:
                            nonlocal stage, hold_started_at, stage_started_at, feedback
                            nonlocal target_reached_reps, rep_target_counted
                            if stop_requested():
                                return
                            if not rep_target_counted:
                                target_reached_reps += 1
                                rep_target_counted = True
                            stage = "hold"
                            hold_started_at = time.monotonic()
                            stage_started_at = hold_started_at
                            feedback = "屈膝角度达标，保持住。"

                        voice_gate.start(
                            "保持。",
                            callback=begin_flexion_hold,
                            feedback="听口令，口令结束后开始保持。",
                            blocks_logic=True,
                        )
                        feedback = "听口令，口令结束后开始保持。"
                    else:
                        feedback = "继续慢慢弯曲，靠近黄色目标线。" if flexion < target_flexion * 0.95 else "角度到了，保持稳定。"
                        if now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                            speaker.speak("弯曲。", interrupt=False)
                            last_instruction_time = now

                elif stage == "hold":
                    if flexion < target_flexion * 0.85:
                        hold_started_at = None
                        stage = "flex"
                        feedback = "角度没有保持住，请重新弯到目标位。"
                        if now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                            speaker.speak("弯曲。", interrupt=False)
                            last_instruction_time = now
                    else:
                        if hold_started_at is None:
                            hold_started_at = now
                        held_seconds = now - hold_started_at
                        hold_text = f"{held_seconds:.1f}/{exercise.target_hold_seconds:.1f} 秒"
                        feedback = f"保持中，还需 {max(0.0, exercise.target_hold_seconds - held_seconds):.1f} 秒。"
                        if held_seconds >= exercise.target_hold_seconds:
                            def begin_flexion_return() -> None:
                                nonlocal stage, return_started_at, stage_started_at, feedback
                                if stop_requested():
                                    return
                                stage = "return"
                                return_started_at = None
                                stage_started_at = time.monotonic()
                                feedback = "保持完成，慢慢伸直回到起始位。"

                            voice_gate.start(
                                "伸直。",
                                callback=begin_flexion_return,
                                feedback="听口令，口令结束后慢慢伸直。",
                                blocks_logic=True,
                            )
                            feedback = "听口令，口令结束后慢慢伸直。"

                elif stage == "return":
                    lift_ok = True if not needs_lift else lift_angle <= max(8.0, target_lift * 0.5)
                    if flexion <= FLEXION_RETURN_MAX_DEGREES and lift_ok:
                        if return_started_at is None:
                            return_started_at = now
                        return_seconds = now - return_started_at
                        hold_text = f"{return_seconds:.1f}/{VISUAL_RETURN_HOLD_SECONDS:.1f} 秒"
                        feedback = "已回到起始位，保持稳定完成计数。"
                        if return_seconds >= VISUAL_RETURN_HOLD_SECONDS:
                            completed += 1
                            baseline_distal = leg.distal.copy()
                            baseline_hip = leg.hip.copy()
                            flexion_smoother.reset()
                            lift_smoother.reset()
                            flexion_stability.reset()
                            lift_stability.reset()
                            flexion_target_started_at = None
                            lift_target_started_at = None
                            rep_target_counted = False
                            hold_started_at = None
                            return_started_at = None
                            if completed < exercise.target_units:
                                next_cue = "上抬。" if needs_lift else "弯曲。"

                                def begin_next_flexion_rep() -> None:
                                    nonlocal stage, stage_started_at, feedback, last_instruction_time
                                    if stop_requested():
                                        return
                                    if needs_lift:
                                        stage = "lift"
                                        feedback = "继续下一次，先慢慢上抬。"
                                    else:
                                        stage = "flex"
                                        feedback = "继续下一次，慢慢弯曲。"
                                    stage_started_at = time.monotonic()
                                    last_instruction_time = stage_started_at

                                start_voice_sequence(
                                    voice_gate,
                                    ((f"完成 {completed} 次。", 0.0), (next_cue, 0.0)),
                                    final_callback=begin_next_flexion_rep,
                                    feedback="本次已计数，听口令准备下一次。",
                                    blocks_logic=True,
                                )
                                feedback = "本次已计数，听口令准备下一次。"
                            else:
                                speaker.speak(f"完成 {completed} 次。")
                    else:
                        return_started_at = None
                        feedback = "慢慢伸直并回到起始位。"

        stage_text = {
            "setup": "起始位确认",
            "lift": "上抬",
            "flex": "屈膝",
            "hold": "屈膝保持",
            "return": "伸直回位",
        }[stage]
        frame = render_training_frame(
            renderer=renderer,
            frame=frame,
            exercise=exercise,
            exercise_index=exercise_index,
            total_exercises=total_exercises,
            completed=completed,
            feedback=feedback,
            extra_lines=[
                f"阶段：{stage_text}",
                tracking_text,
                view_text,
                f"屈膝角：{flexion_text}",
                f"最大屈膝角：{max_flexion_angle:.0f} 度",
                f"上抬角：{lift_text}" if needs_lift else "",
                f"保持时间：{hold_text}",
                "按 r 可重置起始位",
            ],
        )
        publish_training_frame(frame)
        key = poll_training_key(1)
        key_action = handle_common_keys(key)
        if key_action == "quit":
            return finish_flexion_result("quit")
        if key_action == "skip":
            return finish_flexion_result("skipped")
        if key == ord("r"):
            voice_gate.cancel(stop_voice=True)
            baseline_distal = None
            baseline_hip = None
            stage = "setup"
            stage_started_at = time.monotonic()
            hold_started_at = None
            return_started_at = None
            tracked_state.reset()
            leg_smoother.update(None)
            flexion_smoother.reset()
            lift_smoother.reset()
            flexion_stability.reset()
            lift_stability.reset()
            flexion_target_started_at = None
            lift_target_started_at = None
            rep_target_counted = False
            feedback = "已重置起始位，请伸直患腿。"
            speaker.speak("已重置。")

    if stop_requested():
        return finish_flexion_result("quit")
    key_action = live_preview_until_voice_done(
        cap=cap,
        renderer=renderer,
        speaker=speaker,
        exercise=exercise,
        exercise_index=exercise_index,
        total_exercises=total_exercises,
        completed=completed,
        feedback="本次计数完成，准备播报动作完成。",
        extra_lines=["阶段：动作完成", "画面持续刷新中"],
        mirror=mirror,
    )
    if key_action == "quit" or stop_requested():
        return finish_flexion_result("quit")
    if key_action == "skip":
        return finish_flexion_result("completed")
    key_action = speak_with_live_preview(
        cap=cap,
        renderer=renderer,
        speaker=speaker,
        exercise=exercise,
        exercise_index=exercise_index,
        total_exercises=total_exercises,
        completed=completed,
        text=f"{exercise.name}完成。",
        feedback="动作完成，准备切换到下一个动作。",
        extra_lines=["阶段：动作完成", "画面持续刷新中"],
        mirror=mirror,
    )
    if key_action == "quit" or stop_requested():
        return finish_flexion_result("quit")
    if key_action == "skip":
        return finish_flexion_result("completed")
    return finish_flexion_result("completed")


def angle_range_degrees(values: list[float]) -> float:
    if not values:
        return 0.0
    return max(values) - min(values)


def run_bed_knee_flexion_exercise(
    *,
    cap: cv2.VideoCapture,
    pose,
    renderer: TextRenderer,
    speaker: Speaker,
    exercise: Exercise,
    exercise_index: int,
    total_exercises: int,
    side: str,
    mirror: bool,
    reaction_seconds: float,
) -> ExerciseRuntimeResult:
    start = time.monotonic()
    completed = 0
    warnings: list[str] = []
    stage: Literal["setup", "lift", "flex", "hold", "return"] = "setup"
    stage_started_at = time.monotonic()
    hold_started_at: float | None = None
    return_started_at: float | None = None
    lift_stable_started_at: float | None = None
    flexion_stable_started_at: float | None = None
    baseline_knee: np.ndarray | None = None
    baseline_distal: np.ndarray | None = None
    feedback = "请仰卧，侧面完整露出髋、膝和脚踝。"
    last_instruction_time = 0.0

    tracked_state = TrackedLegState()
    leg_smoother = LegSmoother(alpha=0.35, max_jump_ratio=0.22)
    thigh_smoother = ScalarSmoother(alpha=0.30, max_jump=16.0)
    flexion_smoother = ScalarSmoother(alpha=0.30, max_jump=18.0)
    thigh_stability = AngleStabilityTracker(max_range_degrees=5.0)
    flexion_stability = AngleStabilityTracker()
    voice_gate = VoiceGate(speaker)
    consecutive_camera_failures = 0

    session_max_thigh_angle = 0.0
    session_max_flexion_angle = 0.0
    rep_max_thigh_angle = 0.0
    rep_max_flexion_angle = 0.0
    hold_thigh_samples: list[float] = []
    hold_flexion_samples: list[float] = []
    hold_records: list[dict[str, object]] = []

    start_voice_sequence(
        voice_gate,
        (
            (f"{exercise.name}。", 0.0),
            ("请仰卧，先把大腿往上抬到最大限度，然后屈膝，把小腿往大腿方向收。", 0.0),
        ),
        feedback="正在播报床上弯腿动作说明，请摆好姿势。",
        blocks_logic=True,
    )

    def reset_rep_angles() -> None:
        nonlocal rep_max_thigh_angle, rep_max_flexion_angle
        nonlocal hold_thigh_samples, hold_flexion_samples
        rep_max_thigh_angle = 0.0
        rep_max_flexion_angle = 0.0
        hold_thigh_samples = []
        hold_flexion_samples = []
        thigh_smoother.reset()
        flexion_smoother.reset()
        thigh_stability.reset()
        flexion_stability.reset()

    def record_hold() -> None:
        nonlocal hold_records
        thigh_range = angle_range_degrees(hold_thigh_samples)
        flexion_range = angle_range_degrees(hold_flexion_samples)
        stable = (
            thigh_range <= BED_HOLD_STABILITY_MAX_RANGE_DEGREES
            and flexion_range <= BED_HOLD_STABILITY_MAX_RANGE_DEGREES
        )
        hold_records.append(
            {
                "回合": completed + 1,
                "大腿最大上抬角_deg": round(rep_max_thigh_angle, 1),
                "最大屈膝角_deg": round(rep_max_flexion_angle, 1),
                "保持期大腿角波动_deg": round(thigh_range, 1),
                "保持期屈膝角波动_deg": round(flexion_range, 1),
                "保持期稳定": stable,
            }
        )

    def bed_quality_metrics() -> tuple[dict[str, object], float]:
        stable_reps = sum(1 for record in hold_records if bool(record.get("保持期稳定")))
        max_thigh_range = max(
            (float(record.get("保持期大腿角波动_deg", 0.0)) for record in hold_records),
            default=0.0,
        )
        max_flexion_range = max(
            (float(record.get("保持期屈膝角波动_deg", 0.0)) for record in hold_records),
            default=0.0,
        )
        achievement = min(stable_reps / max(1, exercise.target_units), 1.0) * 100.0
        metrics: dict[str, object] = {
            "判定标准": "大腿最大上抬角、最大屈膝角、保持10秒内角度波动和稳定性",
            "完成回合数": completed,
            "目标回合数": exercise.target_units,
            "保持目标时长_s": round(exercise.target_hold_seconds, 1),
            "稳定判定最大波动_deg": round(BED_HOLD_STABILITY_MAX_RANGE_DEGREES, 1),
            "大腿最大上抬角_deg": round(session_max_thigh_angle, 1),
            "最大屈膝角_deg": round(session_max_flexion_angle, 1),
            "最大保持期大腿角波动_deg": round(max_thigh_range, 1),
            "最大保持期屈膝角波动_deg": round(max_flexion_range, 1),
            "稳定保持回合数": stable_reps,
            "保持记录": hold_records,
        }
        return metrics, achievement

    def finish_bed_result(status: str) -> ExerciseRuntimeResult:
        metrics, achievement = bed_quality_metrics()
        return finish_result(
            exercise,
            completed,
            status,
            start,
            warnings,
            metrics=metrics,
            achievement_percent=achievement,
        )

    while completed < exercise.target_units and not stop_requested():
        camera_frame = read_camera_frame(cap)
        if camera_frame is None:
            consecutive_camera_failures += 1
            if consecutive_camera_failures >= CAMERA_READ_MAX_CONSECUTIVE_FAILURES:
                warnings.append("摄像头连续读取失败")
                break
            continue
        consecutive_camera_failures = 0
        frame = display_frame_for(camera_frame, mirror)
        voice_gate.update()

        result = detect_pose(pose, camera_frame)
        tracking_text = "追踪：--"
        view_text = "侧面：--"
        thigh_text = "--"
        flexion_text = "--"
        hold_text = "--"

        if not result.pose_landmarks:
            leg_smoother.update(None)
            feedback = "未检测到下肢，请侧面进入画面。"
        else:
            h, w = camera_frame.shape[:2]
            side_feedback_text = side_view_feedback(result.pose_landmarks.landmark)
            view_text = side_feedback_text or "侧面：已确认"
            raw_leg = pick_stable_tracked_leg(result.pose_landmarks.landmark, w, h, side, tracked_state)
            leg = leg_smoother.update(raw_leg)
            display_leg = leg_for_display(leg, w, mirror)
            tracking_text = tracked_leg_label(leg)

            if leg is None:
                feedback = "请确保髋、膝和脚踝都清晰可见。"
            else:
                now = time.monotonic()
                thigh_angle = thigh_smoother.update(thigh_raise_angle_degrees(leg)) or 0.0
                flexion = flexion_smoother.update(knee_flexion_angle(leg)) or 0.0
                thigh_stable = thigh_stability.update(thigh_angle, now)
                flexion_stable = flexion_stability.update(flexion, now)
                session_max_thigh_angle = max(session_max_thigh_angle, thigh_angle)
                session_max_flexion_angle = max(session_max_flexion_angle, flexion)
                rep_max_thigh_angle = max(rep_max_thigh_angle, thigh_angle)
                rep_max_flexion_angle = max(rep_max_flexion_angle, flexion)
                thigh_text = f"{thigh_angle:.0f} 度 / 最大 {rep_max_thigh_angle:.0f} 度"
                flexion_text = f"{flexion:.0f} 度 / 最大 {rep_max_flexion_angle:.0f} 度"
                draw_bed_knee_flexion_guides(
                    frame,
                    display_leg,
                    thigh_angle_degrees=thigh_angle,
                    flexion_angle_degrees=flexion,
                    stage=stage,
                    stable_position=stage == "hold",
                )

                if voice_gate.blocks_logic:
                    feedback = voice_gate.feedback

                elif stage == "setup":
                    if baseline_knee is None or baseline_distal is None:
                        baseline_knee = leg.knee.copy()
                        baseline_distal = leg.distal.copy()
                        stage_started_at = now
                        feedback = "起始位已找到，请保持不动。"
                    else:
                        movement = max(
                            float(np.linalg.norm(leg.knee - baseline_knee)),
                            float(np.linalg.norm(leg.distal - baseline_distal)),
                        ) / max(leg.leg_length, 1.0)
                        if movement > START_STABILITY_RATIO:
                            baseline_knee = leg.knee.copy()
                            baseline_distal = leg.distal.copy()
                            stage_started_at = now
                            feedback = "起始位保持不动，准备开始。"
                        else:
                            stable_seconds = now - stage_started_at
                            hold_text = f"{stable_seconds:.1f}/{VISUAL_START_HOLD_SECONDS:.1f} 秒"
                            feedback = "起始位稳定中，保持住。"
                            if stable_seconds >= VISUAL_START_HOLD_SECONDS:
                                def begin_bed_lift() -> None:
                                    nonlocal stage, stage_started_at, feedback, last_instruction_time
                                    nonlocal lift_stable_started_at, flexion_stable_started_at
                                    if stop_requested():
                                        return
                                    reset_rep_angles()
                                    stage = "lift"
                                    stage_started_at = time.monotonic()
                                    last_instruction_time = stage_started_at
                                    lift_stable_started_at = None
                                    flexion_stable_started_at = None
                                    feedback = "先把大腿往上抬，抬到自己能达到的最大限度。"

                                start_voice_sequence(
                                    voice_gate,
                                    (("准备，开始。", reaction_seconds), ("先抬大腿。", 0.0)),
                                    final_callback=begin_bed_lift,
                                    feedback="听口令，口令结束后先抬大腿。",
                                    blocks_logic=True,
                                )
                                feedback = "听口令，口令结束后先抬大腿。"

                elif stage == "lift":
                    lift_candidate = thigh_angle >= BED_MAX_LIFT_MIN_DEGREES and thigh_stable
                    if lift_candidate:
                        if lift_stable_started_at is None:
                            lift_stable_started_at = now
                        lift_ready = now - lift_stable_started_at >= ANGLE_TARGET_CONFIRM_SECONDS
                    else:
                        lift_stable_started_at = None
                        lift_ready = False

                    if lift_ready:
                        def begin_bed_flex() -> None:
                            nonlocal stage, stage_started_at, feedback, last_instruction_time
                            nonlocal flexion_stable_started_at
                            if stop_requested():
                                return
                            stage = "flex"
                            stage_started_at = time.monotonic()
                            last_instruction_time = stage_started_at
                            flexion_stable_started_at = None
                            feedback = "保持大腿位置，慢慢屈膝，把小腿往大腿方向收。"

                        voice_gate.start(
                            "保持大腿位置，屈膝。",
                            callback=begin_bed_flex,
                            feedback="听口令，口令结束后开始屈膝。",
                            blocks_logic=True,
                        )
                        feedback = "听口令，口令结束后开始屈膝。"
                    else:
                        feedback = "继续把大腿往上抬，到最大限度后稳住。"
                        if now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                            speaker.speak("先抬大腿。", interrupt=False)
                            last_instruction_time = now

                elif stage == "flex":
                    flex_candidate = flexion >= BED_MAX_FLEXION_MIN_DEGREES and flexion_stable
                    if flex_candidate:
                        if flexion_stable_started_at is None:
                            flexion_stable_started_at = now
                        flex_ready = now - flexion_stable_started_at >= ANGLE_TARGET_CONFIRM_SECONDS
                    else:
                        flexion_stable_started_at = None
                        flex_ready = False

                    if flex_ready:
                        def begin_bed_hold() -> None:
                            nonlocal stage, stage_started_at, hold_started_at, feedback
                            nonlocal hold_thigh_samples, hold_flexion_samples
                            if stop_requested():
                                return
                            stage = "hold"
                            hold_started_at = time.monotonic()
                            stage_started_at = hold_started_at
                            hold_thigh_samples = []
                            hold_flexion_samples = []
                            feedback = "大腿和屈膝位置已稳定，保持十秒。"

                        voice_gate.start(
                            "保持。",
                            callback=begin_bed_hold,
                            feedback="听口令，口令结束后开始保持。",
                            blocks_logic=True,
                        )
                        feedback = "听口令，口令结束后开始保持。"
                    else:
                        feedback = "大腿保持住，继续把小腿往大腿方向收，到最大限度后稳住。"
                        if now - last_instruction_time >= VOICE_REPEAT_SECONDS:
                            speaker.speak("屈膝。", interrupt=False)
                            last_instruction_time = now

                elif stage == "hold":
                    if hold_started_at is None:
                        hold_started_at = now
                    hold_thigh_samples.append(thigh_angle)
                    hold_flexion_samples.append(flexion)
                    held_seconds = now - hold_started_at
                    hold_text = f"{held_seconds:.1f}/{exercise.target_hold_seconds:.1f} 秒"
                    thigh_range = angle_range_degrees(hold_thigh_samples)
                    flexion_range = angle_range_degrees(hold_flexion_samples)
                    feedback = (
                        f"保持中，还需 {max(0.0, exercise.target_hold_seconds - held_seconds):.1f} 秒。"
                        f"大腿波动 {thigh_range:.1f} 度，屈膝波动 {flexion_range:.1f} 度。"
                    )
                    if held_seconds >= exercise.target_hold_seconds:
                        record_hold()

                        def begin_bed_return() -> None:
                            nonlocal stage, return_started_at, stage_started_at, feedback
                            if stop_requested():
                                return
                            stage = "return"
                            return_started_at = None
                            stage_started_at = time.monotonic()
                            feedback = "保持完成，慢慢把腿放回起始位。"

                        voice_gate.start(
                            "慢慢放回。",
                            callback=begin_bed_return,
                            feedback="听口令，口令结束后慢慢放回。",
                            blocks_logic=True,
                        )
                        feedback = "听口令，口令结束后慢慢放回。"

                elif stage == "return":
                    return_ready = thigh_angle <= 8.0 and flexion <= FLEXION_RETURN_MAX_DEGREES
                    if return_ready:
                        if return_started_at is None:
                            return_started_at = now
                        return_seconds = now - return_started_at
                        hold_text = f"{return_seconds:.1f}/{VISUAL_RETURN_HOLD_SECONDS:.1f} 秒"
                        feedback = "已回到起始位，保持稳定完成计数。"
                        if return_seconds >= VISUAL_RETURN_HOLD_SECONDS:
                            completed += 1
                            baseline_knee = leg.knee.copy()
                            baseline_distal = leg.distal.copy()
                            hold_started_at = None
                            return_started_at = None
                            lift_stable_started_at = None
                            flexion_stable_started_at = None
                            if completed < exercise.target_units:
                                def begin_next_bed_rep() -> None:
                                    nonlocal stage, stage_started_at, feedback, last_instruction_time
                                    if stop_requested():
                                        return
                                    reset_rep_angles()
                                    stage = "lift"
                                    stage_started_at = time.monotonic()
                                    last_instruction_time = stage_started_at
                                    feedback = "继续下一次，先把大腿往上抬到最大限度。"

                                start_voice_sequence(
                                    voice_gate,
                                    ((f"完成 {completed} 次。", 0.0), ("先抬大腿。", 0.0)),
                                    final_callback=begin_next_bed_rep,
                                    feedback="本次已计数，听口令准备下一次。",
                                    blocks_logic=True,
                                )
                                feedback = "本次已计数，听口令准备下一次。"
                            else:
                                speaker.speak(f"完成 {completed} 次。")
                    else:
                        return_started_at = None
                        feedback = "慢慢把大腿放下，并把膝盖伸回起始位。"

        stage_text = {
            "setup": "起始位确认",
            "lift": "大腿上抬到最大",
            "flex": "屈膝到最大",
            "hold": "最大位保持",
            "return": "放回起始位",
        }[stage]
        frame = render_training_frame(
            renderer=renderer,
            frame=frame,
            exercise=exercise,
            exercise_index=exercise_index,
            total_exercises=total_exercises,
            completed=completed,
            feedback=feedback,
            extra_lines=[
                f"阶段：{stage_text}",
                tracking_text,
                view_text,
                f"大腿上抬角：{thigh_text}",
                f"屈膝角：{flexion_text}",
                f"保持时间：{hold_text}",
                "按 r 可重置起始位",
            ],
        )
        publish_training_frame(frame)
        key = poll_training_key(1)
        key_action = handle_common_keys(key)
        if key_action == "quit":
            return finish_bed_result("quit")
        if key_action == "skip":
            return finish_bed_result("skipped")
        if key == ord("r"):
            voice_gate.cancel(stop_voice=True)
            baseline_knee = None
            baseline_distal = None
            stage = "setup"
            stage_started_at = time.monotonic()
            hold_started_at = None
            return_started_at = None
            lift_stable_started_at = None
            flexion_stable_started_at = None
            tracked_state.reset()
            leg_smoother.update(None)
            reset_rep_angles()
            feedback = "已重置起始位，请仰卧并露出髋、膝、踝。"
            speaker.speak("已重置。")

    if stop_requested():
        return finish_bed_result("quit")
    key_action = live_preview_until_voice_done(
        cap=cap,
        renderer=renderer,
        speaker=speaker,
        exercise=exercise,
        exercise_index=exercise_index,
        total_exercises=total_exercises,
        completed=completed,
        feedback="本次计数完成，准备播报动作完成。",
        extra_lines=["阶段：动作完成", "画面持续刷新中"],
        mirror=mirror,
    )
    if key_action == "quit" or stop_requested():
        return finish_bed_result("quit")
    if key_action == "skip":
        return finish_bed_result("completed")
    key_action = speak_with_live_preview(
        cap=cap,
        renderer=renderer,
        speaker=speaker,
        exercise=exercise,
        exercise_index=exercise_index,
        total_exercises=total_exercises,
        completed=completed,
        text=f"{exercise.name}完成。",
        feedback="动作完成，准备切换到下一个动作。",
        extra_lines=["阶段：动作完成", "画面持续刷新中"],
        mirror=mirror,
    )
    if key_action == "quit" or stop_requested():
        return finish_bed_result("quit")
    if key_action == "skip":
        return finish_bed_result("completed")
    return finish_bed_result("completed")


def add_warning(warnings: list[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


def finish_result(
    exercise: Exercise,
    completed: int,
    status: str,
    start_time: float,
    warnings: list[str],
    *,
    metrics: dict[str, object] | None = None,
    achievement_percent: float | None = None,
) -> ExerciseRuntimeResult:
    return ExerciseRuntimeResult(
        exercise_id=exercise.id,
        exercise_name=exercise.name,
        mode=exercise.mode,
        target_units=exercise.target_units,
        completed_units=completed,
        status=status,
        duration_seconds=round(time.monotonic() - start_time, 1),
        warnings=warnings,
        metrics=metrics or {},
        achievement_percent=achievement_percent,
    )


def display_progress_line(exercise: Exercise, completed: int) -> tuple[str, dict[str, object]]:
    config = SESSION_ACTION_CONFIGS.get(exercise.id) if SESSION_ACTION_CONFIGS else None
    if not config:
        return f"进度：{completed}/{exercise.target_units}", {
            "current_completed": completed,
            "target_units": exercise.target_units,
        }
    display = config.get("display") if isinstance(config.get("display"), dict) else {}
    score_type = display.get("score_type")
    if score_type == "quantity":
        base = int(display.get("base_completed") or 0)
        target = int(display.get("total_target") or exercise.target_units)
        current = base + completed
        extra = f"，已超额完成 {current - target} 次" if current > target else ""
        return f"进度：{current}/{target}{extra}", {
            "score_type": "quantity",
            "base_completed": base,
            "current_completed": current,
            "total_target": target,
        }
    if score_type == "endurance_raise":
        base = int(display.get("base_valid_reps") or 0)
        target = int(display.get("target_reps") or exercise.target_units)
        current = base + completed
        return f"有效次数：{current}/{target}", {
            "score_type": "endurance_raise",
            "base_valid_reps": base,
            "current_valid_reps": current,
            "target_reps": target,
            "best_angle_deg": display.get("best_angle_deg"),
            "best_hold_s": display.get("best_hold_s"),
        }
    if score_type == "flexion":
        best = display.get("best_flexion_deg") or 0
        target = display.get("target_flexion_deg") or 120
        return f"今日最佳：{float(best):.0f}° / 目标 {float(target):.0f}°", {
            "score_type": "flexion",
            "best_flexion_deg": best,
            "target_flexion_deg": target,
        }
    if score_type == "bed_flexion":
        flexion = display.get("best_flexion_deg") or 0
        thigh = display.get("best_thigh_raise_deg") or 0
        return f"今日最佳：大腿 {float(thigh):.0f}°，屈膝 {float(flexion):.0f}°", {
            "score_type": "bed_flexion",
            "best_flexion_deg": flexion,
            "best_thigh_raise_deg": thigh,
        }
    return f"进度：{completed}/{exercise.target_units}", {
        "current_completed": completed,
        "target_units": exercise.target_units,
    }


def render_training_frame(
    *,
    renderer: TextRenderer,
    frame: np.ndarray,
    exercise: Exercise,
    exercise_index: int,
    total_exercises: int,
    completed: int,
    feedback: str,
    extra_lines: list[str],
) -> np.ndarray:
    h, w = frame.shape[:2]
    progress_line, display_progress = display_progress_line(exercise, completed)
    set_web_status_context(
        exercise_id=exercise.id,
        exercise_name=exercise.name,
        display_progress=display_progress,
        message=feedback,
    )
    main_lines = [
        f"{exercise_index + 1}/{total_exercises}  {exercise.name}",
        f"类别：{exercise.category}",
        progress_line,
        feedback,
    ]
    standard_lines = ["动作标准"] + exercise.standard[:3]
    setup_lines = ["操作"] + exercise.setup + ["q 退出 / n 跳过 / r 重置起始位"]

    panels = [
        (main_lines + extra_lines, (18, 18), (15, 23, 42, 210)),
        (standard_lines, (18, max(250, h - 230)), (30, 64, 92, 205)),
        (setup_lines, (max(18, w - 520), 18), (61, 42, 92, 205)),
    ]
    return renderer.draw_panels(frame, panels)


def render_summary_frame(
    renderer: TextRenderer,
    frame: np.ndarray,
    results: list[ExerciseRuntimeResult],
    result_path: Path,
) -> np.ndarray:
    completed = sum(1 for result in results if result.status == "completed")
    total_rate = (
        sum(result.achievement_rate for result in results) / len(results)
        if results
        else 0.0
    )
    lines = [
        "训练总结",
        f"完成动作：{completed}/{len(results)}",
        f"平均完成率：{total_rate:.0f}%",
        f"结果文件：{result_path}",
        "按 q 退出",
    ]
    detail = ["动作完成情况"]
    for result in results:
        detail.append(f"{result.exercise_name}：{result.achievement_rate:.0f}%，{result.status}")
    return renderer.draw_panels(
        frame,
        [
            (lines, (24, 24), (15, 23, 42, 225)),
            (detail, (24, 210), (30, 64, 92, 220)),
        ],
    )


def create_session_output_dir() -> Path:
    if OUTPUT_DIR_OVERRIDE is not None:
        OUTPUT_DIR_OVERRIDE.mkdir(parents=True, exist_ok=True)
        return OUTPUT_DIR_OVERRIDE
    output_dir = Path("test_pose") / f"knee_desktop_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def format_metric_value(value: object) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.1f}"
    if isinstance(value, list):
        return "；".join(format_metric_value(item) for item in value)
    if isinstance(value, dict):
        return "，".join(f"{key}={format_metric_value(item)}" for key, item in value.items())
    return str(value)


def result_metric_summary(result: ExerciseRuntimeResult) -> str:
    if not result.metrics:
        return f"完成 {result.completed_units}/{result.target_units}"
    priority_keys = [
        "判定标准",
        "完成次数",
        "目标次数",
        "最大踝泵角度幅度_deg",
        "达标保持总时长_s",
        "最长连续达标保持_s",
        "最大抬腿角度_deg",
        "大腿最大上抬角_deg",
        "是否达到目标屈膝角",
        "最大屈膝角度_deg",
        "最大屈膝角_deg",
        "最大保持期大腿角波动_deg",
        "最大保持期屈膝角波动_deg",
        "稳定保持回合数",
        "屈膝角达标次数",
    ]
    parts = []
    for key in priority_keys:
        if key in result.metrics:
            parts.append(f"{key}={format_metric_value(result.metrics[key])}")
    return "；".join(parts) if parts else f"完成 {result.completed_units}/{result.target_units}"


def write_metrics_text(results: list[ExerciseRuntimeResult], output_path: Path) -> None:
    lines = [
        "膝关节康复训练指标记录",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"{index}. {result.exercise_name}",
                f"动作 ID：{result.exercise_id}",
                f"模式：{result.mode}",
                f"状态：{result.status}",
                f"完成进度：{result.completed_units}/{result.target_units}",
                f"质量完成率：{result.achievement_rate:.1f}%",
                f"耗时：{result.duration_seconds:.1f} 秒",
            ]
        )
        if result.metrics:
            lines.append("核心指标：")
            for key, value in result.metrics.items():
                lines.append(f"- {key}: {format_metric_value(value)}")
        else:
            lines.append("核心指标：未记录")
        if result.warnings:
            lines.append("提示/警告：")
            for warning in result.warnings:
                lines.append(f"- {warning}")
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_results(results: list[ExerciseRuntimeResult]) -> Path:
    output_dir = create_session_output_dir()
    output_path = output_dir / "summary.json"
    metrics_text_path = output_dir / "metrics_summary.txt"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "metrics_text": str(metrics_text_path),
        "results": [
            {
                **asdict(result),
                "achievement_rate": round(result.achievement_rate, 1),
            }
            for result in results
        ],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_metrics_text(results, metrics_text_path)
    return output_path


def print_summary(results: list[ExerciseRuntimeResult], result_path: Path) -> None:
    print("\n训练总结")
    print("-" * 72)
    for result in results:
        warnings = "；".join(result.warnings) if result.warnings else "动作质量未记录异常"
        print(
            f"{result.exercise_name}: "
            f"{result.achievement_rate:.0f}%, "
            f"{result.status}, "
            f"{result_metric_summary(result)}, "
            f"{warnings}"
        )
    print("-" * 72)
    print(f"结果已保存：{result_path}")
    print(f"指标文本已保存：{result_path.with_name('metrics_summary.txt')}")


def show_summary_until_quit(
    cap: cv2.VideoCapture,
    renderer: TextRenderer,
    results: list[ExerciseRuntimeResult],
    result_path: Path,
    mirror: bool,
) -> None:
    while not stop_requested():
        frame = read_camera_frame(cap)
        if frame is None:
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        elif mirror:
            frame = cv2.flip(frame, 1)
        frame = render_summary_frame(renderer, frame, results, result_path)
        publish_training_frame(frame)
        if poll_training_key(30) == ord("q"):
            break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="跨平台膝关节完整康复训练脚本")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET_UNITS, help="每个动作目标次数，默认 10")
    parser.add_argument(
        "--camera",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
        help="摄像头编号；默认自动尝试常用摄像头序号，可用 --probe-cameras 后手动指定",
    )
    parser.add_argument("--list-cameras", action="store_true", help="显示摄像头选择建议，不打开摄像头")
    parser.add_argument("--probe-cameras", action="store_true", help="实际尝试打开摄像头序号；可能触发系统摄像头权限提示")
    parser.add_argument(
        "--side",
        choices=["auto", "left", "right"],
        default="auto",
        help="患侧选择，默认自动选择画面中更清楚的一侧",
    )
    parser.add_argument(
        "--plan",
        choices=["full", "side_remaining"],
        default="full",
        help="训练计划：full 为完整膝关节计划；side_remaining 为除踝泵和直腿抬高外的剩余床上/侧面动作",
    )
    parser.add_argument(
        "--exercise",
        action="append",
        default=None,
        help="只运行指定动作 ID；可重复传入，也可用逗号分隔。先用 --list 查看 ID",
    )
    parser.add_argument("--no-voice", action="store_true", help="关闭语音播报")
    parser.add_argument("--voice", default=None, help="指定系统语音兜底音色，例如 Windows 的 Huihui 或 macOS 的 Tingting")
    parser.add_argument("--voice-rate", type=int, default=DEFAULT_VOICE_RATE, help="系统语音兜底语速，默认 145")
    parser.add_argument(
        "--tts-engine",
        choices=["edge_cache", "system", "say"],
        default="edge_cache",
        help="语音引擎：edge_cache 为本地神经语音缓存，system/say 为系统语音兜底",
    )
    parser.add_argument("--edge-voice", default=DEFAULT_EDGE_VOICE, help="edge-tts 音色")
    parser.add_argument("--edge-rate", default=DEFAULT_EDGE_RATE, help="edge-tts 语速，例如 -10%%")
    parser.add_argument("--edge-volume", default=DEFAULT_EDGE_VOLUME, help="edge-tts 音量，例如 +0%%")
    parser.add_argument("--voice-cache-dir", default=str(DEFAULT_VOICE_CACHE_DIR), help="本地语音缓存目录")
    parser.add_argument(
        "--reaction-seconds",
        type=float,
        default=DEFAULT_REACTION_SECONDS,
        help="语音播报结束后留给用户反应的秒数，默认 2.0",
    )
    parser.add_argument(
        "--leg-length-cm",
        type=float,
        default=DEFAULT_LEG_LENGTH_CM,
        help="髋到踝的估算长度，用于把画面位移换算为离床厘米数，默认 80",
    )
    parser.add_argument(
        "--prepare-voice-cache",
        action="store_true",
        help="只生成本地 edge-tts 语音缓存，不打开摄像头",
    )
    parser.add_argument("--session-config", default=None, help="本地网页端传入的真实训练 session 配置 JSON")
    parser.add_argument("--output-dir", default=None, help="指定本次训练 summary.json 和 metrics_summary.txt 输出目录")
    parser.add_argument("--web-stream-dir", default=None, help="网页端嵌入模式：把实时识别画面写入该目录，不打开 OpenCV 窗口")
    parser.add_argument("--web-stream-profile", default="balanced", help="网页端推流 profile：smooth / balanced / quality")
    parser.add_argument("--web-stream-fps", type=float, default=15.0, help="网页端实时画面推流 FPS，默认 15")
    parser.add_argument("--web-stream-width", type=int, default=800, help="网页端实时画面宽度，默认 800")
    parser.add_argument("--web-jpeg-quality", type=int, default=68, help="网页端 JPEG 质量，默认 68")
    parser.add_argument("--camera-width", type=int, default=None, help="可选摄像头采集宽度，不传则保持默认")
    parser.add_argument("--camera-height", type=int, default=None, help="可选摄像头采集高度，不传则保持默认")
    parser.add_argument("--camera-fps", type=float, default=None, help="可选摄像头采集 FPS，不传则保持默认")
    parser.add_argument("--no-mirror", action="store_true", help="关闭摄像头镜像显示")
    parser.add_argument("--list", action="store_true", help="只列出训练动作，不打开摄像头")
    return parser.parse_args()


def main() -> None:
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    args = parse_args()
    setup_web_stream(
        args.web_stream_dir,
        fps=args.web_stream_fps,
        width=args.web_stream_width,
        jpeg_quality=args.web_jpeg_quality,
        stream_profile=args.web_stream_profile,
    )
    global OUTPUT_DIR_OVERRIDE
    OUTPUT_DIR_OVERRIDE = Path(args.output_dir) if args.output_dir else None
    session_config = load_session_config(args.session_config)
    target_units = max(1, args.target)
    exercise_ids = parse_exercise_ids(args.exercise)
    try:
        if session_config:
            exercises = build_session_config_exercises(session_config)
            voice_cache_exercises = exercises
        else:
            exercises = build_session_exercises(
                target_units,
                plan=args.plan,
                exercise_ids=exercise_ids,
            )
            voice_cache_exercises = build_session_exercises(
                max(target_units, DEFAULT_TARGET_UNITS),
                plan=args.plan,
                exercise_ids=exercise_ids,
            )
    except ValueError as exc:
        print(exc)
        return
    voice_cache_dir = Path(args.voice_cache_dir)
    reaction_seconds = max(0.0, min(float(args.reaction_seconds), 5.0))
    leg_length_cm = max(30.0, min(float(args.leg_length_cm), 130.0))

    if args.list_cameras or args.probe_cameras:
        print_camera_help(probe_indices=args.probe_cameras)
        return

    if args.list:
        for index, exercise in enumerate(exercises, start=1):
            print(
                f"{index}. {exercise.id} - {exercise.name} - "
                f"{exercise.category} - {exercise.mode} - {exercise_target_summary(exercise)}"
            )
        return

    if args.prepare_voice_cache:
        texts = collect_voice_texts(voice_cache_exercises)
        print(f"准备生成/检查 {len(texts)} 条本地语音缓存：{voice_cache_dir}")
        generated, skipped, failed = asyncio.run(
            prepare_voice_cache(
                texts,
                cache_dir=voice_cache_dir,
                edge_voice=args.edge_voice,
                edge_rate=args.edge_rate,
                edge_volume=args.edge_volume,
            )
        )
        print(f"语音缓存完成：新生成 {generated} 条，已存在 {skipped} 条，失败 {failed} 条。")
        return

    if not args.no_voice and args.tts_engine == "edge_cache":
        texts = collect_voice_texts(voice_cache_exercises)
        print(f"检查本地语音缓存：{voice_cache_dir}")
        try:
            generated, skipped, failed = asyncio.run(
                prepare_voice_cache(
                    texts,
                    cache_dir=voice_cache_dir,
                    edge_voice=args.edge_voice,
                    edge_rate=args.edge_rate,
                    edge_volume=args.edge_volume,
                )
            )
            if generated or failed:
                print(f"语音缓存检查完成：补齐 {generated} 条，复用 {skipped} 条，失败 {failed} 条。")
            else:
                print(f"本地语音缓存已就绪，共 {skipped} 条。")
        except Exception as exc:
            print(f"语音缓存准备失败，将回退到{system_voice_label()}：{exc}")
            args.tts_engine = "system"

    renderer = TextRenderer()
    speaker = Speaker(
        enabled=not args.no_voice,
        rate=max(80, min(args.voice_rate, 220)),
        requested_voice=args.voice,
        cache_dir=voice_cache_dir,
        use_edge_cache=args.tts_engine == "edge_cache",
        edge_voice=args.edge_voice,
        edge_rate=args.edge_rate,
        edge_volume=args.edge_volume,
    )
    global ACTIVE_SPEAKER
    ACTIVE_SPEAKER = speaker
    cap: cv2.VideoCapture | None = None
    results: list[ExerciseRuntimeResult] = []

    try:
        try:
            cap = open_camera(
                args.camera,
                camera_width=args.camera_width,
                camera_height=args.camera_height,
                camera_fps=args.camera_fps,
            )
        except RuntimeError as exc:
            print(f"摄像头启动失败：{exc}")
            print("建议：")
            if is_macos():
                print("1. 在 macOS 系统设置 -> 隐私与安全性 -> 摄像头 中允许 VSCode/Terminal。")
            elif is_windows():
                print("1. 在 Windows 设置 -> 隐私和安全性 -> 摄像头 中允许桌面应用访问摄像头。")
            else:
                print("1. 检查系统摄像头权限。")
            print("2. 关闭正在占用摄像头的应用。")
            print("3. 分别尝试 --camera 0、--camera 1、--camera 2。")
            print("4. 运行 --list-cameras 查看平台提示，运行 --probe-cameras 探测 OpenCV 序号。")
            return
        if not web_stream_enabled():
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW_NAME, 1280, 720)

        with mp_pose.Pose(
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.7,
        ) as pose:
            for index, exercise in enumerate(exercises):
                if stop_requested():
                    break
                if exercise.mode in ("timer", "ankle_hybrid"):
                    result = run_timer_exercise(
                        cap=cap,
                        pose=pose,
                        renderer=renderer,
                        speaker=speaker,
                        exercise=exercise,
                        exercise_index=index,
                        total_exercises=len(exercises),
                        side=args.side,
                        mirror=not args.no_mirror,
                        reaction_seconds=reaction_seconds,
                    )
                elif exercise.mode == "flexion_visual" and exercise.id == "bed_knee_flexion":
                    result = run_bed_knee_flexion_exercise(
                        cap=cap,
                        pose=pose,
                        renderer=renderer,
                        speaker=speaker,
                        exercise=exercise,
                        exercise_index=index,
                        total_exercises=len(exercises),
                        side=args.side,
                        mirror=not args.no_mirror,
                        reaction_seconds=reaction_seconds,
                    )
                elif exercise.mode == "flexion_visual":
                    result = run_flexion_visual_exercise(
                        cap=cap,
                        pose=pose,
                        renderer=renderer,
                        speaker=speaker,
                        exercise=exercise,
                        exercise_index=index,
                        total_exercises=len(exercises),
                        side=args.side,
                        mirror=not args.no_mirror,
                        reaction_seconds=reaction_seconds,
                    )
                else:
                    result = run_visual_exercise(
                        cap=cap,
                        pose=pose,
                        renderer=renderer,
                        speaker=speaker,
                        exercise=exercise,
                        exercise_index=index,
                        total_exercises=len(exercises),
                        side=args.side,
                        mirror=not args.no_mirror,
                        reaction_seconds=reaction_seconds,
                        leg_length_cm=leg_length_cm,
                    )

                results.append(result)
                if result.status == "quit":
                    break

        if not results and stop_requested():
            return
        result_path = save_results(results)
        print_summary(results, result_path)
        if not stop_requested():
            speaker.speak_and_wait("训练完成。")
            show_summary_until_quit(
                cap,
                renderer,
                results,
                result_path,
                mirror=not args.no_mirror,
            )

    finally:
        close_web_publisher()
        speaker.close()
        ACTIVE_SPEAKER = None
        if cap is not None:
            cap.release()
        if not web_stream_enabled():
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
