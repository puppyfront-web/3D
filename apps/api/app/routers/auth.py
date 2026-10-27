"""Auth router — login (JWT), logout, register (admin only),
email verification-code login and password reset."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    EmailCodeLoginRequest,
    EmailCodeSendRequest,
    EmailCodeSendResponse,
    LoginRequest,
    LoginResponse,
    PasswordResetRequest,
    UserOut,
)
from app.schemas.common import Response
from app.core.security import hash_password, verify_password, create_access_token, get_current_user, require_admin
from app.services.verification_code_service import (
    CODE_TTL_MINUTES,
    VerificationCodeService,
)

router = APIRouter(prefix="/auth", tags=["auth"])

async def _get_active_user(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="该邮箱未注册或已停用")
    return user

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

@router.post("/email-code/send", response_model=Response[EmailCodeSendResponse])
async def send_email_code(body: EmailCodeSendRequest, db: AsyncSession = Depends(get_db)):
    """Email a 6-digit one-time code (login or password reset).

    Returns 429 with retry_after when the previous code is still inside the
    60s resend cooldown. When the mock email provider is active (no SMTP
    configured) the response carries `dev_code` so internal deployments can
    complete the flow before SMTP is set up.
    """
    await _get_active_user(db, body.email)  # never reveal codes for unknown emails

    from app.services.email_service import get_email_sender, is_mock_provider
    from app.services.settings_service import SettingsService

    code, retry_after = await VerificationCodeService.issue(db, body.email, body.purpose)
    if code is None:
        raise HTTPException(status_code=429, detail=f"发送过于频繁，请 {retry_after} 秒后重试")

    sender = await get_email_sender(db)
    subject = "AI 团队平台验证码" + ("（重置密码）" if body.purpose == "reset" else "（登录）")
    await sender.send(
        body.email,
        subject,
        f"您的验证码是 {code}，{CODE_TTL_MINUTES} 分钟内有效。若非本人操作请忽略本邮件。",
    )

    provider = await SettingsService.get(db, "email_provider", default="mock")
    return Response(data=EmailCodeSendResponse(
        expires_in=CODE_TTL_MINUTES * 60,
        retry_after=None,
        dev_code=code if is_mock_provider(provider) else None,
    ), message="验证码已发送")

@router.post("/login/email", response_model=Response[LoginResponse])
async def login_with_email_code(body: EmailCodeLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate by email + one-time code, return a JWT."""
    user = await _get_active_user(db, body.email)
    if not await VerificationCodeService.verify(db, body.email, "login", body.code):
        raise HTTPException(status_code=401, detail="验证码错误或已过期")
    role_name = user.role.name if user.role else "user"
    token = create_access_token(str(user.id), role_name)
    return Response(data=LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    ), message="登录成功")

@router.post("/password/reset", response_model=Response)
async def reset_password(body: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    """Reset the account password with an emailed one-time code."""
    user = await _get_active_user(db, body.email)
    if not await VerificationCodeService.verify(db, body.email, "reset", body.code):
        raise HTTPException(status_code=401, detail="验证码错误或已过期")
    user.hashed_password = hash_password(body.new_password)
    await db.flush()
    return Response(message="密码已重置，请使用新密码登录")

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
