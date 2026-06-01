from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...models.daily_record import DailyRecord
from ...schemas.daily_record import (
    DailyRecordCreate,
    DailyRecordCreateResponse,
    DailyRecordResponse,
)

router = APIRouter(prefix="/api", tags=["daily_record"])


@router.post(
    "/daily_record",
    response_model=DailyRecordCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_daily_record(
    payload: DailyRecordCreate,
    db: AsyncSession = Depends(get_db),
) -> DailyRecordCreateResponse:
    record = DailyRecord(
        user_id=payload.user_id,
        action_name=payload.action_name,
        pain_score=payload.pain_score,
        achievement_rate=payload.achievement_rate,
        max_flexion_angle=payload.max_flexion_angle,
        completed_sets=payload.completed_sets,
    )

    db.add(record)
    await db.commit()
    await db.refresh(record)

    return DailyRecordCreateResponse(
        message="当日训练记录已保存",
        record=DailyRecordResponse.model_validate(record),
    )
