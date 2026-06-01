from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class DailyRecord(Base):
    __tablename__ = "daily_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    action_name: Mapped[str] = mapped_column(String(64), default="靠墙静蹲")
    pain_score: Mapped[int] = mapped_column(Integer)
    achievement_rate: Mapped[float] = mapped_column(Float)
    max_flexion_angle: Mapped[float] = mapped_column(Float)
    completed_sets: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
    )
