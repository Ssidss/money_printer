"""
認證 API
- POST /auth/register   註冊
- POST /auth/login       登入（回傳 JWT）
- GET  /auth/me          取得當前使用者資訊
- PUT  /auth/me          更新個人資料
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from ..services.auth import (
    hash_password, verify_password, create_access_token, get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ──────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    is_admin: bool

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None


# ── Routes ───────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # 檢查 email 是否已存在
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="此 Email 已被註冊")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, display_name=user.display_name, is_admin=user.is_admin),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email 或密碼錯誤",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="帳號已停用")

    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, display_name=user.display_name, is_admin=user.is_admin),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, display_name=user.display_name, is_admin=user.is_admin)


@router.put("/me", response_model=UserOut)
async def update_me(
    req: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.display_name is not None:
        user.display_name = req.display_name
    if req.password is not None:
        user.password_hash = hash_password(req.password)
    await db.commit()
    await db.refresh(user)
    return UserOut(id=user.id, email=user.email, display_name=user.display_name, is_admin=user.is_admin)
