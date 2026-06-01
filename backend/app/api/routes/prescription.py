from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...models.daily_record import DailyRecord
from ...schemas.prescription import PrescriptionResponse
from ...services.prescription_engine import generate_prescription

router = APIRouter(prefix="/api", tags=["prescription"])


@router.get("/prescription/{user_id}", response_model=PrescriptionResponse)
async def get_prescription(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> PrescriptionResponse:
    stmt = (
        select(DailyRecord)
        .where(DailyRecord.user_id == user_id)
        .order_by(DailyRecord.created_at.desc(), DailyRecord.id.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    latest_record = result.scalar_one_or_none()

    pain_score = latest_record.pain_score if latest_record else None
    return generate_prescription(user_id=user_id, pain_score=pain_score)
