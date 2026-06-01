from typing import Optional

from ..schemas.prescription import PrescriptionResponse
from .knee_rehab_library import build_knee_postop_plan


def generate_prescription(user_id: str, pain_score: Optional[int]) -> PrescriptionResponse:
    rehab_plan = build_knee_postop_plan(user_id=user_id, pain_score=pain_score)

    # MVP 阶段先使用简单规则引擎：
    # 1. 疼痛高：降低训练强度，避免过度刺激；
    # 2. 疼痛中等：维持保守训练；
    # 3. 疼痛较低：适度增加组数与保持时间。
    #
    # 未来如果接入 Qwen-VL 或其他大模型，
    # 可以在这里替换成“读取历史数据 -> 拼接 prompt -> 调用模型 -> 返回结构化处方”。
    if pain_score is None:
        return PrescriptionResponse(
            user_id=user_id,
            action_name="靠墙静蹲",
            target_sets=3,
            target_angle=100,
            hold_seconds=15,
            frequency_note="每日 1 次",
            caution="未找到最近一次疼痛记录，先按默认保守方案执行",
            source="rule_engine",
            rehab_plan=rehab_plan,
        )

    if pain_score >= 7:
        return PrescriptionResponse(
            user_id=user_id,
            action_name="膝关节屈伸",
            target_sets=2,
            target_angle=120,
            hold_seconds=8,
            frequency_note="每日 1 次",
            caution="疼痛偏高，降低强度；若训练后疼痛明显加重，请暂停并联系医生",
            source="rule_engine",
            rehab_plan=rehab_plan,
        )

    if 4 <= pain_score <= 6:
        return PrescriptionResponse(
            user_id=user_id,
            action_name="靠墙静蹲",
            target_sets=3,
            target_angle=100,
            hold_seconds=12,
            frequency_note="每日 1 次",
            caution="保持动作稳定，避免膝盖内扣",
            source="rule_engine",
            rehab_plan=rehab_plan,
        )

    return PrescriptionResponse(
        user_id=user_id,
        action_name="靠墙静蹲",
        target_sets=4,
        target_angle=90,
        hold_seconds=20,
        frequency_note="每日 1 次",
        caution="疼痛较轻，可逐步增加保持时间，但仍需避免突然发力",
        source="rule_engine",
        rehab_plan=rehab_plan,
    )
