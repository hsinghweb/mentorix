"""Auth API: signup and login for students (PLANNER_FINAL_FEATURES)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.password import hash_password, verify_password
from app.core.jwt_auth import create_token
from app.memory.database import get_db
from app.models.entities import Learner, LearnerProfile, StudentAuth

router = APIRouter(prefix="/auth", tags=["auth"])

TIMELINE_MIN_WEEKS = 14
TIMELINE_MAX_WEEKS = 28


def _clamp_weeks(w: int) -> int:
    return max(TIMELINE_MIN_WEEKS, min(TIMELINE_MAX_WEEKS, w))


class SignupRequest(BaseModel):
    username: str = Field(min_length=2, max_length=128)
    # Simple password rules for this project: at least 1 char, capped to 72.
    password: str = Field(min_length=1, max_length=72)
    name: str = Field(min_length=1, max_length=255)
    date_of_birth: date
    selected_timeline_weeks: int = Field(ge=14, le=28)
    math_9_percent: int = Field(ge=0, le=100)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    token: str
    learner_id: str
    username: str
    name: str


@router.post("/signup", response_model=AuthResponse)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)):
    username = payload.username.strip().lower()
    existing = (await db.execute(select(StudentAuth).where(StudentAuth.username == username))).scalar_one_or_none()
    if existing:
        # For this project we keep signup very forgiving: if the username exists,
        # treat signup as login and return a token for the existing account.
        token = create_token(existing.learner_id, existing.username)
        return AuthResponse(
            token=token,
            learner_id=str(existing.learner_id),
            username=existing.username,
            name=existing.name,
        )

    learner = Learner(name=payload.name.strip(), grade_level="10")
    db.add(learner)
    await db.flush()

    profile = LearnerProfile(
        learner_id=learner.id,
        concept_mastery={},
        retention_decay=0.1,
        cognitive_depth=0.5,
        engagement_score=0.5,
        selected_timeline_weeks=_clamp_weeks(payload.selected_timeline_weeks),
        recommended_timeline_weeks=None,
        current_forecast_weeks=None,
        timeline_delta_weeks=None,
        math_9_percent=payload.math_9_percent,
    )
    db.add(profile)

    auth = StudentAuth(
        username=username,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        date_of_birth=payload.date_of_birth,
        learner_id=learner.id,
    )
    db.add(auth)
    await db.commit()

    token = create_token(learner.id, auth.username)
    return AuthResponse(
        token=token,
        learner_id=str(learner.id),
        username=auth.username,
        name=auth.name,
    )


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    auth = (
        await db.execute(select(StudentAuth).where(StudentAuth.username == payload.username.strip().lower()))
    ).scalar_one_or_none()
    if not auth or not verify_password(payload.password, auth.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_token(auth.learner_id, auth.username)
    return AuthResponse(
        token=token,
        learner_id=str(auth.learner_id),
        username=auth.username,
        name=auth.name,
    )
