from typing import Optional

from pydantic import BaseModel, Field


class ExerciseDose(BaseModel):
    target_daily_cycles: Optional[int] = Field(
        default=None,
        description="每日目标循环数，适用于踝泵或等长收缩",
    )
    session_target_cycles: Optional[int] = Field(
        default=None,
        description="单次训练任务目标循环数",
    )
    session_target_reps: Optional[int] = Field(
        default=None,
        description="单次训练任务目标次数",
    )
    reps_per_set: Optional[int] = Field(default=None, description="每组次数")
    sets_per_day_min: Optional[int] = Field(default=None, description="每日最少组数")
    sets_per_day_max: Optional[int] = Field(default=None, description="每日最多组数")
    contraction_seconds: Optional[int] = Field(default=None, description="用力/收缩秒数")
    relax_seconds: Optional[int] = Field(default=None, description="放松秒数")
    hold_strategy: Optional[str] = Field(default=None, description="保持策略")
    rest_between_sets_seconds: Optional[int] = Field(default=None, description="组间休息秒数")
    frequency_note: str = Field(description="频率说明")


class RehabExercise(BaseModel):
    id: str = Field(description="动作库唯一 ID")
    name: str = Field(description="动作名称")
    category: str = Field(description="动作类别")
    purpose: str = Field(description="训练目的")
    start_rule: str = Field(description="开始条件")
    status: str = Field(description="当前计划状态")
    evaluation_mode: str = Field(description="评估方式：vision / voice_only / timer_counter / hybrid")
    dose: ExerciseDose
    standard: list[str] = Field(description="动作标准")
    execution: list[str] = Field(description="执行步骤")
    assessment: list[str] = Field(description="评估要点")
    voice_cues: list[str] = Field(description="语音引导文案")
    contraindications: list[str] = Field(default_factory=list, description="禁忌或暂缓条件")
    stop_rules: list[str] = Field(default_factory=list, description="停止训练规则")


class RehabPlanSection(BaseModel):
    id: str
    title: str
    purpose: str
    exercises: list[RehabExercise]


class KneeRehabPlan(BaseModel):
    plan_id: str
    user_id: str
    title: str
    phase: str
    intensity_note: str
    education_notes: list[str]
    sections: list[RehabPlanSection]
    global_stop_rules: list[str]


class ExerciseSessionEvaluation(BaseModel):
    exercise_id: str
    status: str
    achievement_rate: float
    completed_units: int
    target_units: int
    feedback: list[str]
    warnings: list[str] = Field(default_factory=list)


class PrescriptionResponse(BaseModel):
    user_id: str
    action_name: str = Field(description="训练动作名称")
    target_sets: int = Field(description="目标组数")
    target_angle: float = Field(description="目标膝关节角度")
    hold_seconds: int = Field(description="每次保持秒数")
    frequency_note: str = Field(description="训练频率说明")
    caution: str = Field(description="注意事项")
    source: str = Field(description="处方来源：rule_engine / llm")
    rehab_plan: Optional[KneeRehabPlan] = Field(
        default=None,
        description="膝关节术后康复完整训练计划范式",
    )
