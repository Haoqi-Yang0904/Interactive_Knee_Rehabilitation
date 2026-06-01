from typing import Optional

from ..schemas.prescription import (
    ExerciseDose,
    ExerciseSessionEvaluation,
    KneeRehabPlan,
    RehabExercise,
    RehabPlanSection,
)


COMMON_STOP_RULES = [
    "训练中出现明显疼痛加重、头晕、胸闷、伤口异常渗出时立即停止。",
    "小腿明显肿胀、发热、疼痛或呼吸不适时暂停训练并联系医生，排查血栓风险。",
    "所有力量练习以动作质量优先，不用憋气或突然发力。",
]


def _base_stop_rules() -> list[str]:
    return [
        "疼痛明显加重或动作后疼痛持续不缓解时停止。",
        "出现代偿动作且无法通过语音纠正时停止本组。",
    ]


KNEE_EXERCISE_LIBRARY: dict[str, RehabExercise] = {
    "ankle_pump": RehabExercise(
        id="ankle_pump",
        name="主动踝泵练习",
        category="控水肿、预防血栓",
        purpose="促进小腿肌肉泵回流，控制术后水肿并降低血栓风险。",
        start_rule="术后即可按医嘱尽早开始；下地负重时间增加后逐步减少，恢复完全居家日常生活后可停做。",
        status="daily_required",
        evaluation_mode="hybrid",
        dose=ExerciseDose(
            target_daily_cycles=1000,
            session_target_cycles=10,
            contraction_seconds=4,
            relax_seconds=2,
            frequency_note="每日不少于 1000 次；一次完整背伸加跖屈为 1 个循环。",
        ),
        standard=[
            "踝关节主动背伸时脚尖尽量往头侧勾，保持 4 秒。",
            "放松 2 秒后主动跖屈，脚尖往下踩，保持 4 秒。",
            "再次放松 2 秒，完成 1 个全范围屈伸循环。",
            "下地后可做抗重力下踝泵，但仍以不诱发疼痛和肿胀为准。",
        ],
        execution=[
            "取仰卧或坐位，患腿放松伸直。",
            "听到提示后先勾脚 4 秒，再放松 2 秒。",
            "随后向下踩 4 秒，再放松 2 秒。",
            "按循环计数，可分多次完成全天总量。",
        ],
        assessment=[
            "执行层面以计时节拍和循环计数为主，足部关键点可见时用视觉确认脚尖背伸、跖屈的活动幅度。",
            "摄像头应尽量从患侧侧方拍到膝、踝、脚跟和脚尖，足部被遮挡时降级为节拍计数。",
            "记录全天累计循环数，低于 1000 次时提示继续分段完成。",
            "观察训练后踝部和小腿肿胀是否较前加重。",
        ],
        voice_cues=[
            "脚尖往头侧勾，保持四秒。",
            "放松两秒。",
            "脚尖往下踩，保持四秒。",
            "很好，再放松，继续下一个循环。",
        ],
        stop_rules=[
            "小腿突发明显疼痛、肿胀或发热时停止。",
            "足踝活动诱发明显伤口疼痛时停止并反馈。",
        ],
    ),
    "quadriceps_isometric": RehabExercise(
        id="quadriceps_isometric",
        name="股四头肌等长收缩",
        category="控水肿、预防血栓",
        purpose="激活大腿前侧肌群，减少术后肌肉抑制，为后续直腿抬高打基础。",
        start_rule="术后早期即可在疼痛可控、医生允许下开始。",
        status="voice_guided",
        evaluation_mode="voice_only",
        dose=ExerciseDose(
            target_daily_cycles=1000,
            session_target_cycles=10,
            contraction_seconds=4,
            relax_seconds=2,
            frequency_note="每日尽可能多做，不少于 1000 次；可分散到全天完成。",
        ),
        standard=[
            "患腿伸直，大腿前侧肌肉主动绷紧 4 秒。",
            "膝盖保持伸直，不用屏气，不要把臀部抬离床面。",
            "放松 2 秒后进入下一次。",
        ],
        execution=[
            "仰卧或坐位，患腿伸直。",
            "想象把膝盖后方轻轻压向床面，同时绷紧大腿前侧。",
            "保持 4 秒后完全放松 2 秒。",
        ],
        assessment=[
            "该动作视觉捕捉难度高，MVP 阶段以语音节拍、自评完成数和疼痛反馈为主。",
            "如果能触摸到大腿前侧变硬，说明收缩方向基本正确。",
            "记录全天累计次数和训练后疼痛变化。",
        ],
        voice_cues=[
            "大腿前侧绷紧，膝盖轻轻往下压，保持四秒。",
            "不要憋气，腰和臀部放松。",
            "放松两秒，再来一次。",
        ],
        stop_rules=_base_stop_rules(),
    ),
    "hamstring_isometric": RehabExercise(
        id="hamstring_isometric",
        name="腘绳肌等长收缩",
        category="控水肿、预防血栓",
        purpose="激活大腿后侧和臀部肌群，帮助恢复膝后侧控制。",
        start_rule="术后早期可按医嘱进行；若后侧疼痛或手术限制则暂缓。",
        status="voice_guided",
        evaluation_mode="voice_only",
        dose=ExerciseDose(
            target_daily_cycles=1000,
            session_target_cycles=10,
            contraction_seconds=4,
            relax_seconds=2,
            frequency_note="每日尽可能多做，不少于 1000 次；可与股四头肌等长交替完成。",
        ),
        standard=[
            "患腿伸直，用力向下压床面，寻找大腿后侧及臀部收缩感。",
            "不要挺腰，不要用腰背代偿。",
            "保持 4 秒后放松 2 秒。",
        ],
        execution=[
            "仰卧，患腿伸直放在床面。",
            "脚跟和小腿保持稳定，患腿向下压床。",
            "感受大腿后侧和臀部收紧，保持 4 秒。",
            "完全放松 2 秒后重复。",
        ],
        assessment=[
            "该动作视觉上难以稳定捕捉，MVP 阶段以语音引导、自评收缩感和疼痛反馈为主。",
            "若患者主要感到腰部发力，判定为代偿，需要重新提示。",
        ],
        voice_cues=[
            "患腿伸直，轻轻向下压床，找大腿后侧和臀部收紧的感觉。",
            "腰不要拱起来，慢慢呼吸。",
            "保持四秒，放松两秒。",
        ],
        stop_rules=_base_stop_rules(),
    ),
    "supine_straight_leg_raise": RehabExercise(
        id="supine_straight_leg_raise",
        name="仰卧位直抬腿",
        category="肌力练习",
        purpose="训练股四头肌维持膝伸直能力和髋屈肌控制。",
        start_rule="通常术后第 2 天起在医生允许下开始；若术式要求前 6 周禁做，则第 6 周后再开始。",
        status="conditional_after_clearance",
        evaluation_mode="hybrid",
        dose=ExerciseDose(
            session_target_reps=10,
            reps_per_set=10,
            sets_per_day_min=4,
            sets_per_day_max=5,
            hold_strategy="患肢完全伸直后抬高至与床面约 15 度，保持到无力维持再放下休息。",
            frequency_note="10 次/组，4-5 组/日。",
        ),
        standard=[
            "患肢全程完全伸直，避免膝盖弯曲或伸膝滞后。",
            "抬高至与床面约 15 度，不追求过高。",
            "保持到无力维持后平稳放回床面，休息片刻再做下一次。",
        ],
        execution=[
            "仰卧，健侧腿可屈曲支撑，患腿伸直。",
            "先做股四头肌收缩，让膝盖伸直锁稳。",
            "患腿整体抬起至约 15 度。",
            "保持到不能稳定维持，再缓慢放下。",
        ],
        assessment=[
            "视觉评估重点是髋-膝-踝基本成直线，膝关节不明显弯曲。",
            "抬腿角度接近 15 度即可，过高不额外加分。",
            "记录完成次数、组数、是否出现伸膝滞后和疼痛变化。",
        ],
        voice_cues=[
            "先把膝盖伸直，大腿前侧绷住。",
            "整条腿慢慢抬起一点，到十五度左右就好。",
            "膝盖别弯，稳住，累了再慢慢放下。",
        ],
        contraindications=[
            "前交叉韧带重建术患者禁忌，除非医生明确允许。",
            "术后前 6 周被医嘱标记为禁做时暂缓。",
        ],
        stop_rules=_base_stop_rules(),
    ),
    "side_lying_hip_abduction": RehabExercise(
        id="side_lying_hip_abduction",
        name="侧抬腿练习",
        category="肌力练习",
        purpose="训练髋外展和下肢侧向稳定能力。",
        start_rule="通常术后第 2 天起在医生允许下开始；若术式要求前 6 周禁做，则第 6 周后再开始。",
        status="conditional_after_clearance",
        evaluation_mode="hybrid",
        dose=ExerciseDose(
            session_target_reps=10,
            reps_per_set=10,
            sets_per_day_min=4,
            sets_per_day_max=5,
            rest_between_sets_seconds=30,
            frequency_note="10 次/组，4-5 组/日，组间休息 30 秒。",
        ),
        standard=[
            "侧卧，患腿伸直向身体外侧抬起。",
            "骨盆和躯干保持稳定，不向后倒或借腰摆动。",
            "抬起和放下都要慢，足尖方向保持自然。",
        ],
        execution=[
            "侧卧位摆好身体，患腿在上方并保持伸直。",
            "先收紧大腿，保持膝盖不弯。",
            "患腿向上抬起，再慢慢放回起始位。",
        ],
        assessment=[
            "视觉评估髋-膝-踝是否保持直线，并配合语音提醒身体侧卧稳定。",
            "检测骨盆是否明显翻转或躯干晃动。",
            "按有效抬起-控制放下计 1 次。",
        ],
        voice_cues=[
            "身体侧卧稳住，患腿伸直。",
            "腿慢慢向上抬，不要往后倒身子。",
            "慢慢放下，控制住。",
        ],
        contraindications=["术后前 6 周被医嘱标记为禁做时暂缓。"],
        stop_rules=_base_stop_rules(),
    ),
    "prone_hip_extension": RehabExercise(
        id="prone_hip_extension",
        name="后抬腿练习",
        category="肌力练习",
        purpose="训练髋伸展、臀部和大腿后侧控制。",
        start_rule="通常术后第 2 天起在医生允许下开始；若术式要求前 6 周禁做，则第 6 周后再开始。",
        status="conditional_after_clearance",
        evaluation_mode="hybrid",
        dose=ExerciseDose(
            session_target_reps=10,
            reps_per_set=10,
            sets_per_day_min=4,
            sets_per_day_max=5,
            rest_between_sets_seconds=30,
            frequency_note="10 次/组，4-5 组/日，组间休息 30 秒。",
        ),
        standard=[
            "俯卧，患腿伸直向后抬起。",
            "足尖离床面约 5 厘米即可，不需要抬很高。",
            "腰部不要明显后仰或代偿发力。",
        ],
        execution=[
            "俯卧，双腿自然伸直。",
            "患腿膝盖保持伸直，脚尖轻轻离开床面约 5 厘米。",
            "短暂停住后慢慢放回床面。",
        ],
        assessment=[
            "视觉评估足尖是否离床约 5 厘米且膝关节保持伸直，并配合语音提醒不要拱腰。",
            "检测腰椎是否明显后仰代偿。",
            "按稳定抬起并控制放下计 1 次。",
        ],
        voice_cues=[
            "趴好，患腿伸直。",
            "脚尖轻轻离床五厘米就够，不要拱腰。",
            "慢慢放下，动作稳一点。",
        ],
        contraindications=["术后前 6 周被医嘱标记为禁做时暂缓。"],
        stop_rules=_base_stop_rules(),
    ),
    "side_lying_hip_adduction": RehabExercise(
        id="side_lying_hip_adduction",
        name="内收抬腿练习",
        category="肌力练习",
        purpose="补齐四方向直腿抬高中的内收方向，训练大腿内侧控制。",
        start_rule="通常术后第 2 天起在医生允许下开始；若术式要求前 6 周禁做，则第 6 周后再开始。",
        status="conditional_after_clearance",
        evaluation_mode="hybrid",
        dose=ExerciseDose(
            session_target_reps=10,
            reps_per_set=10,
            sets_per_day_min=4,
            sets_per_day_max=5,
            rest_between_sets_seconds=30,
            frequency_note="10 次/组，4-5 组/日，组间休息 30 秒。",
        ),
        standard=[
            "侧卧，患腿保持伸直，向身体中线方向做内收抬起。",
            "骨盆保持稳定，不用腰部扭转代偿。",
            "抬起和放下都保持慢速控制。",
        ],
        execution=[
            "侧卧位摆好身体，根据患腿位置选择上方或下方腿完成内收。",
            "患腿膝盖伸直，脚尖自然。",
            "大腿内侧发力，把患腿向身体中线方向抬起。",
            "慢慢放下，完成 1 次。",
        ],
        assessment=[
            "视觉评估患腿是否保持伸直，骨盆是否稳定，并配合语音提醒大腿内侧发力。",
            "按有效内收抬起并控制返回计 1 次。",
            "若出现明显扭腰或摆动，提示降低幅度。",
        ],
        voice_cues=[
            "腿伸直，身体不要扭。",
            "用大腿内侧慢慢把腿抬起来。",
            "幅度不用大，稳稳放下。",
        ],
        contraindications=["术后前 6 周被医嘱标记为禁做时暂缓。"],
        stop_rules=_base_stop_rules(),
    ),
}


EDEMA_AND_THROMBOSIS_EXERCISE_IDS = [
    "ankle_pump",
    "quadriceps_isometric",
    "hamstring_isometric",
]

STRENGTH_EXERCISE_IDS = [
    "supine_straight_leg_raise",
    "side_lying_hip_abduction",
    "prone_hip_extension",
    "side_lying_hip_adduction",
]


def get_knee_exercise(exercise_id: str) -> RehabExercise:
    return KNEE_EXERCISE_LIBRARY[exercise_id].model_copy(deep=True)


def build_knee_postop_plan(
    user_id: str,
    pain_score: Optional[int],
    *,
    acl_reconstruction: bool = False,
    home_life_recovered: bool = False,
) -> KneeRehabPlan:
    edema_exercises = [
        get_knee_exercise(exercise_id)
        for exercise_id in EDEMA_AND_THROMBOSIS_EXERCISE_IDS
    ]

    strength_exercises = [
        get_knee_exercise(exercise_id)
        for exercise_id in STRENGTH_EXERCISE_IDS
    ]

    if acl_reconstruction:
        strength_exercises[0].status = "contraindicated"

    if pain_score is None:
        intensity_note = "暂无最新疼痛评分，先按保守术后教育计划执行。"
    elif pain_score >= 7:
        intensity_note = (
            "今日疼痛偏高，优先完成踝泵和等长收缩；四向抬腿仅在医生允许、"
            "且动作不加重疼痛时尝试。"
        )
        for exercise in strength_exercises:
            if exercise.status != "contraindicated":
                exercise.status = "conditional_reduce_or_hold"
    elif pain_score >= 4:
        intensity_note = "今日疼痛中等，力量练习按 4 组起步，动作质量优先。"
    else:
        intensity_note = "今日疼痛较低，可在动作标准稳定前提下完成 4-5 组力量练习。"

    if home_life_recovered:
        for exercise in edema_exercises:
            exercise.status = "optional_after_home_recovery"

    return KneeRehabPlan(
        plan_id="knee_postop_education_v1",
        user_id=user_id,
        title="膝关节术后康复训练计划范式",
        phase="术后早期至居家日常恢复阶段",
        intensity_note=intensity_note,
        education_notes=[
            "控水肿和预防血栓动作随每日下地负重时间增加而减少，恢复完全居家日常生活后可不做。",
            "四向直腿抬高属于肌力练习，需要结合术式和医生禁忌；被标记为术后前 6 周禁做的动作，第 6 周后再做。",
            "股四头肌和腘绳肌等长收缩视觉评估价值有限，MVP 阶段使用语音节拍、次数记录和疼痛反馈。",
        ],
        sections=[
            RehabPlanSection(
                id="edema_and_thrombosis_prevention",
                title="一、控水肿、预防血栓",
                purpose="通过踝泵和大腿肌群等长收缩促进循环，减少术后肿胀和血栓风险。",
                exercises=edema_exercises,
            ),
            RehabPlanSection(
                id="strength_training",
                title="二、肌力练习",
                purpose="完成前、外、后、内四方向直腿抬高，逐步恢复下肢基础肌力。",
                exercises=strength_exercises,
            ),
        ],
        global_stop_rules=COMMON_STOP_RULES,
    )


def evaluate_knee_exercise_session(
    exercise_id: str,
    *,
    completed_cycles: int = 0,
    completed_reps: int = 0,
    completed_sets: int = 0,
    pain_score_after: Optional[int] = None,
    failed_quality_checks: Optional[list[str]] = None,
) -> ExerciseSessionEvaluation:
    exercise = get_knee_exercise(exercise_id)
    dose = exercise.dose
    failed_quality_checks = failed_quality_checks or []

    if dose.target_daily_cycles is not None:
        target_units = dose.target_daily_cycles
        completed_units = completed_cycles
    elif dose.reps_per_set is not None and dose.sets_per_day_min is not None:
        target_units = dose.reps_per_set * dose.sets_per_day_min
        completed_units = completed_reps or completed_sets * dose.reps_per_set
    else:
        target_units = 1
        completed_units = 0

    achievement_rate = 0.0
    if target_units > 0:
        achievement_rate = min(completed_units / target_units, 1.0) * 100.0

    warnings: list[str] = []
    feedback: list[str] = []

    if pain_score_after is not None and pain_score_after >= 7:
        warnings.append("训练后疼痛评分偏高，下一次应降低强度或暂停并反馈医生。")

    for check in failed_quality_checks:
        warnings.append(f"动作质量需复核：{check}")

    if achievement_rate >= 100 and not warnings:
        status = "completed"
        feedback.append("今日目标完成，维持当前训练节奏。")
    elif achievement_rate >= 60:
        status = "partial"
        feedback.append("已完成大部分目标，优先保证动作质量，可分段补足剩余次数。")
    else:
        status = "needs_more_work"
        feedback.append("完成量不足，建议分多次完成，避免一次集中疲劳。")

    if exercise.evaluation_mode == "voice_only":
        feedback.append("该动作以语音节拍和自评收缩感为主，不做强视觉判定。")

    return ExerciseSessionEvaluation(
        exercise_id=exercise_id,
        status=status,
        achievement_rate=round(achievement_rate, 2),
        completed_units=completed_units,
        target_units=target_units,
        feedback=feedback,
        warnings=warnings,
    )
