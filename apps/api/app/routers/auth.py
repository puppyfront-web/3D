"""Auth router — login (JWT), logout, register (admin only)."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import LoginRequest, LoginResponse, UserOut
from app.schemas.common import Response
from app.core.security import hash_password, verify_password, create_access_token, get_current_user, require_admin

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Response[LoginResponse])
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate by email + password, return a JWT."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    # Load role name
    role_name = user.role.name if user.role else "user"
    token = create_access_token(str(user.id), role_name)
    return Response(data=LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    ), message="登录成功")

@router.post("/logout", response_model=Response)
async def logout():
    """Stateless logout — client discards the token."""
    return Response(message="已登出")

@router.post("/register", response_model=Response[UserOut])
async def register(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Register a new user (admin only)."""
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="邮箱已存在")
    user = User(
        email=body.email,
        name=body.email.split("@")[0],
        hashed_password=hash_password(body.password),
        role_id=current_user.role_id,  # inherit admin's role
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return Response(data=UserOut.model_validate(user), message="用户创建成功")
