from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DailyRecordCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64, description="用户 ID")
    action_name: str = Field(default="靠墙静蹲", min_length=1, max_length=64)
    pain_score: int = Field(..., ge=1, le=10, description="疼痛等级 1-10")
    achievement_rate: float = Field(..., ge=0, le=100, description="达标率 0-100")
    max_flexion_angle: float = Field(..., ge=0, le=180, description="最大弯曲角度")
    completed_sets: int = Field(default=0, ge=0, le=100)


class DailyRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    action_name: str
    pain_score: int
    achievement_rate: float
    max_flexion_angle: float
    completed_sets: int
    created_at: datetime


class DailyRecordCreateResponse(BaseModel):
    message: str
    record: DailyRecordResponse
