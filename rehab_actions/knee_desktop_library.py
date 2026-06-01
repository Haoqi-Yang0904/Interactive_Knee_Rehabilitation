from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DEFAULT_TARGET_UNITS = 10
VISUAL_TARGET_HOLD_SECONDS = 1.5
SIDE_REMAINING_EXERCISE_IDS = (
    "quadriceps_isometric",
    "hamstring_isometric",
    "sandbag_knee_extension_press",
    "bed_knee_flexion",
    "side_lying_hip_abduction",
    "prone_hip_extension",
    "side_lying_hip_adduction",
)


@dataclass(frozen=True)
class TimerPhase:
    label: str
    cue: str
    duration_seconds: float


@dataclass(frozen=True)
class Exercise:
    id: str
    name: str
    category: str
    mode: Literal["ankle_hybrid", "timer", "visual", "flexion_visual"]
    standard: list[str]
    setup: list[str]
    voice_cues: list[str]
    target_units: int = DEFAULT_TARGET_UNITS
    contraction_seconds: int = 4
    relax_seconds: int = 2
    visual_up_threshold: float = 0.13
    visual_down_threshold: float = 0.06
    target_movement_degrees: float = 12.0
    target_distance_cm: float | None = None
    target_flexion_degrees: float | None = None
    target_lift_degrees: float = 0.0
    target_hold_seconds: float = VISUAL_TARGET_HOLD_SECONDS
    timer_phases: list[TimerPhase] = field(default_factory=list)


def _ankle_phases() -> list[TimerPhase]:
    return [
        TimerPhase("勾脚保持", "勾脚。", 4.0),
        TimerPhase("放松", "放松。", 2.0),
        TimerPhase("下踩保持", "下踩。", 4.0),
        TimerPhase("放松", "放松。", 2.0),
    ]


def _isometric_phases() -> list[TimerPhase]:
    return [
        TimerPhase("主动收紧保持", "收紧。", 5.0),
        TimerPhase("放松", "放松。", 2.0),
    ]


def _single_hold_phase(label: str, cue: str, seconds: float) -> list[TimerPhase]:
    return [TimerPhase(label, cue, seconds)]


def ankle_pump(target_units: int) -> Exercise:
    return Exercise(
        id="ankle_pump",
        name="主动踝泵练习",
        category="控水肿、预防血栓",
        mode="ankle_hybrid",
        target_units=target_units,
        standard=[
            "勾脚 4 秒，放松 2 秒；下踩 4 秒，再放松 2 秒。",
            "一次完整背伸加跖屈为 1 个循环。",
            "摄像头尽量拍到膝、踝、脚跟、脚尖。",
        ],
        setup=["仰卧或坐位，患腿伸直，足部完整露出。"],
        voice_cues=["勾脚。", "放松。", "下踩。", "放松。"],
        timer_phases=_ankle_phases(),
        target_movement_degrees=12.0,
    )


def quadriceps_isometric(target_units: int) -> Exercise:
    return Exercise(
        id="quadriceps_isometric",
        name="股四头肌等长收缩",
        category="控水肿、预防血栓",
        mode="timer",
        target_units=target_units,
        standard=[
            "大腿前侧绷紧 5 秒，放松 2 秒。",
            "膝盖保持伸直，不要憋气，不要抬臀。",
        ],
        setup=["仰卧或坐位，患腿伸直，把膝盖后方轻轻压向床面。"],
        voice_cues=["收紧。", "放松。"],
        timer_phases=_isometric_phases(),
    )


def hamstring_isometric(target_units: int) -> Exercise:
    return Exercise(
        id="hamstring_isometric",
        name="腘绳肌等长收缩",
        category="控水肿、预防血栓",
        mode="timer",
        target_units=target_units,
        standard=[
            "患腿伸直向下压床，找大腿后侧和臀部收紧感。",
            "保持 5 秒，放松 2 秒；不要挺腰。",
        ],
        setup=["仰卧，患腿伸直放在床面，尽量让膝盖后方贴近床面。"],
        voice_cues=["收紧。", "放松。"],
        timer_phases=_isometric_phases(),
    )


def sandbag_knee_extension_press(target_units: int) -> Exercise:
    return Exercise(
        id="sandbag_knee_extension_press",
        name="沙袋压腿",
        category="床上锻炼",
        mode="timer",
        target_units=1,
        standard=[
            "脚跟垫软物使腿悬空。",
            "3-5 公斤沙袋压于膝关节上。",
            "每次 15 分钟，过程中不要让膝盖弯曲。",
        ],
        setup=["侧面拍摄，确认髋、膝、小腿末端可见，膝关节保持伸直。"],
        voice_cues=["保持。"],
        timer_phases=_single_hold_phase("沙袋压腿保持", "保持。", 15 * 60.0),
    )


def supine_straight_leg_raise(target_units: int) -> Exercise:
    return Exercise(
        id="supine_straight_leg_raise",
        name="仰卧位直抬腿",
        category="肌力练习",
        mode="visual",
        target_units=target_units,
        standard=[
            "仰卧，患腿完全伸直。",
            "整条腿抬到约 15 度即可，膝盖不要弯。",
            "慢慢放回起始位，控制住。",
        ],
        setup=["摄像头从侧方拍到髋、膝、踝；开始前让脚踝在起始位停 1 秒。"],
        voice_cues=["抬起。", "保持。", "放下。"],
        visual_up_threshold=0.14,
        visual_down_threshold=0.05,
        target_movement_degrees=15.0,
        target_hold_seconds=1.5,
    )


def side_lying_hip_abduction(target_units: int) -> Exercise:
    return Exercise(
        id="side_lying_hip_abduction",
        name="侧抬腿练习",
        category="肌力练习",
        mode="visual",
        target_units=target_units,
        standard=[
            "侧卧，患腿伸直向上抬。",
            "骨盆和躯干保持稳定，不向后倒。",
            "抬起和放下都要慢。",
        ],
        setup=["侧卧位，让摄像头能看到髋、膝、踝，起始位停 1 秒。"],
        voice_cues=["抬起。", "保持。", "放下。"],
        visual_up_threshold=0.12,
        visual_down_threshold=0.05,
        target_movement_degrees=12.0,
        target_hold_seconds=1.5,
    )


def prone_hip_extension(target_units: int) -> Exercise:
    return Exercise(
        id="prone_hip_extension",
        name="后抬腿练习",
        category="肌力练习",
        mode="visual",
        target_units=target_units,
        standard=[
            "俯卧，患腿伸直向后抬。",
            "抬到约 12 度即可，不要拱腰。",
            "慢慢放下，动作稳定。",
        ],
        setup=["俯卧位，侧方拍到髋、膝、踝；识别时需脚踝清晰。"],
        voice_cues=["抬起。", "保持。", "放下。"],
        visual_up_threshold=0.12,
        visual_down_threshold=0.04,
        target_movement_degrees=12.0,
        target_distance_cm=None,
        target_hold_seconds=1.0,
    )


def side_lying_hip_adduction(target_units: int) -> Exercise:
    return Exercise(
        id="side_lying_hip_adduction",
        name="内收抬腿练习",
        category="肌力练习",
        mode="visual",
        target_units=target_units,
        standard=[
            "侧卧，患腿伸直，向身体中线方向抬起。",
            "大腿内侧发力，骨盆不要扭转。",
            "幅度不用大，慢慢放下。",
        ],
        setup=["侧卧位，调整身体让患腿在画面中清楚可见。"],
        voice_cues=["抬起。", "保持。", "放下。"],
        visual_up_threshold=0.10,
        visual_down_threshold=0.04,
        target_movement_degrees=10.0,
        target_hold_seconds=1.5,
    )


def bed_knee_flexion(target_units: int) -> Exercise:
    return Exercise(
        id="bed_knee_flexion",
        name="床上弯腿",
        category="床上锻炼",
        mode="flexion_visual",
        target_units=target_units,
        standard=[
            "仰卧或坐位，患肢缓慢弯曲到可承受最大限度。",
            "到达目标后保持 10 秒。",
            "缓慢放松回到伸直起始位。",
        ],
        setup=["侧面拍摄，完整看到髋、膝和小腿末端；先伸直患腿建立起始位。"],
        voice_cues=["弯曲。", "保持。", "伸直。"],
        visual_down_threshold=0.04,
        target_flexion_degrees=70.0,
        target_hold_seconds=10.0,
    )


def build_exercises(target_units: int) -> list[Exercise]:
    return [
        ankle_pump(target_units),
        quadriceps_isometric(target_units),
        hamstring_isometric(target_units),
        sandbag_knee_extension_press(target_units),
        supine_straight_leg_raise(target_units),
        bed_knee_flexion(target_units),
        side_lying_hip_abduction(target_units),
        prone_hip_extension(target_units),
        side_lying_hip_adduction(target_units),
    ]


def build_exercise_registry(target_units: int) -> dict[str, Exercise]:
    return {exercise.id: exercise for exercise in build_exercises(target_units)}


def select_exercises(
    target_units: int,
    *,
    exercise_ids: list[str] | tuple[str, ...] | None = None,
    plan_ids: list[str] | tuple[str, ...] | None = None,
) -> list[Exercise]:
    registry = build_exercise_registry(target_units)
    ordered_ids = list(plan_ids) if plan_ids is not None else list(registry.keys())

    if exercise_ids:
        wanted = set(exercise_ids)
        unknown = sorted(wanted - set(registry))
        if unknown:
            known_text = "、".join(sorted(registry))
            raise ValueError(f"未知动作 ID：{'、'.join(unknown)}。可用 ID：{known_text}")

        selected_ids = [exercise_id for exercise_id in ordered_ids if exercise_id in wanted]
        missing_from_plan = [exercise_id for exercise_id in exercise_ids if exercise_id not in selected_ids]
        if missing_from_plan:
            raise ValueError(f"动作 ID 不在当前计划中：{'、'.join(missing_from_plan)}")
        ordered_ids = selected_ids

    return [registry[exercise_id] for exercise_id in ordered_ids]


def collect_short_voice_texts(exercises: list[Exercise]) -> list[str]:
    texts = {
        "摆好姿势。",
        "脚尖露出来。",
        "准备，开始。",
        "勾脚。",
        "下踩。",
        "收紧。",
        "放松。",
        "抬起。",
        "保持。",
        "放下。",
        "弯曲。",
        "伸直。",
        "完成。",
        "膝盖伸直。",
        "重新抬起。",
        "回到起始位。",
        "请回到起始位。",
        "未检测到下肢。",
        "训练完成。",
        "已重置。",
    }
    for exercise in exercises:
        texts.add(f"{exercise.name}。")
        texts.add(f"{exercise.name}完成。")
        for cue in exercise.voice_cues:
            texts.add(cue)
        for phase in exercise.timer_phases:
            texts.add(phase.cue)
        for completed in range(1, exercise.target_units + 1):
            texts.add(f"完成 {completed} 次。")
    return sorted(texts)
