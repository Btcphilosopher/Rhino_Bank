"""
=============================================================
RHINO CORE
Central Identity / Security Backend
=============================================================

For:
    Rhino Agricultural Spot Exchange
    Rhino Wool Exchange
    Rhino Honey Exchange
    Rhino Olive Oil Exchange
    Rhino Fish Exchange
    etc.

Stack:
    FastAPI
    SQLAlchemy
    PostgreSQL
    Argon2
    JWT
    Pydantic

Security principles:
    - Never store plaintext passwords
    - Argon2id password hashing
    - Short-lived access tokens
    - Rotating refresh tokens
    - RBAC
    - Exchange-level permissions
    - Account lockout
    - Audit trail
    - Server-side authorization
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import jwt

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    status,
)

from fastapi.security import (
    OAuth2PasswordBearer,
)

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
)

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
)

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_URL = (
    "postgresql+psycopg://"
    "rhino:CHANGE_ME@localhost/"
    "rhino_core"
)

JWT_SECRET = (
    "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET"
)

JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_MINUTES = 15

REFRESH_TOKEN_DAYS = 7

MAX_LOGIN_ATTEMPTS = 5

LOCKOUT_MINUTES = 15


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Rhino Core",
    version="1.0.0",
    description=(
        "Central identity and security "
        "backend for Rhino exchanges."
    ),
)


# ============================================================
# DATABASE
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# ============================================================
# PASSWORD HASHING
# ============================================================

password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
)


def hash_password(
    password: str
) -> str:

    return password_hasher.hash(
        password
    )


def verify_password(
    password: str,
    password_hash: str
) -> bool:

    try:

        return password_hasher.verify(
            password_hash,
            password
        )

    except VerifyMismatchError:

        return False


# ============================================================
# ENUMS
# ============================================================

class Role(str, Enum):

    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"

    COMPLIANCE = "COMPLIANCE"

    RISK_MANAGER = "RISK_MANAGER"

    TRADER = "TRADER"

    MARKET_DATA = "MARKET_DATA"

    OPERATIONS = "OPERATIONS"

    USER = "USER"


class ExchangePermission(str, Enum):

    VIEW = "VIEW"
    TRADE = "TRADE"
    ADMIN = "ADMIN"


# ============================================================
# USER
# ============================================================

class User(Base):

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
    )

    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        Text,
    )

    role: Mapped[str] = mapped_column(
        String(32),
        default=Role.USER.value,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    failed_logins: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    locked_until: Mapped[Optional[datetime]] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=True,
        )
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    last_login: Mapped[Optional[datetime]] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=True,
        )
    )


# ============================================================
# EXCHANGE ACCESS
# ============================================================

class ExchangeAccess(Base):

    __tablename__ = "exchange_access"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    exchange: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    permission: Mapped[str] = mapped_column(
        String(32),
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )


# ============================================================
# REFRESH TOKENS
# ============================================================

class RefreshToken(Base):

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(128),
        unique=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
    )


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(Base):

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(128),
    )

    resource: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
    )


# ============================================================
# CREATE TABLES
# ============================================================

Base.metadata.create_all(
    engine
)


# ============================================================
# Pydantic MODELS
# ============================================================

class RegisterRequest(BaseModel):

    email: EmailStr

    username: str = Field(
        min_length=3,
        max_length=64,
    )

    password: str = Field(
        min_length=12,
        max_length=128,
    )


class LoginRequest(BaseModel):

    username: str

    password: str


class TokenResponse(BaseModel):

    access_token: str

    refresh_token: str

    token_type: str = "bearer"

    expires_in: int


class ExchangeAccessRequest(BaseModel):

    username: str

    exchange: str

    permission: ExchangePermission


class RoleChangeRequest(BaseModel):

    role: Role


# ============================================================
# TOKEN FUNCTIONS
# ============================================================

def create_access_token(
    user: User
) -> str:

    now_time = datetime.now(
        timezone.utc
    )

    expiry = (
        now_time
        + timedelta(
            minutes=ACCESS_TOKEN_MINUTES
        )
    )

    payload = {

        "sub": user.id,

        "username": user.username,

        "role": user.role,

        "iat": int(
            now_time.timestamp()
        ),

        "exp": int(
            expiry.timestamp()
        ),

        "type": "access",
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def generate_refresh_token():

    raw = secrets.token_urlsafe(
        64
    )

    token_hash = hashlib.sha256(
        raw.encode()
    ).hexdigest()

    return raw, token_hash


# ============================================================
# OAUTH SCHEME
# ============================================================

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user(
    token: str = Depends(
        oauth2_scheme
    ),
    db=Depends(get_db),
):

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication",
        headers={
            "WWW-Authenticate": "Bearer"
        },
    )

    try:

        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[
                JWT_ALGORITHM
            ],
        )

    except jwt.PyJWTError:

        raise credentials_error

    if payload.get("type") != "access":

        raise credentials_error

    user_id = payload.get(
        "sub"
    )

    user = db.get(
        User,
        user_id
    )

    if not user:

        raise credentials_error

    if not user.is_active:

        raise HTTPException(
            status_code=403,
            detail="Account disabled",
        )

    return user


# ============================================================
# ROLE AUTHORIZATION
# ============================================================

def require_roles(
    *roles: Role
):

    def dependency(
        user: User = Depends(
            get_current_user
        )
    ):

        allowed = {
            role.value
            for role in roles
        }

        if user.role not in allowed:

            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions",
            )

        return user

    return dependency


# ============================================================
# AUDIT
# ============================================================

def audit(
    db,
    user_id,
    action,
    resource=None,
    ip=None,
    details=None,
):

    entry = AuditLog(

        user_id=user_id,

        action=action,

        resource=resource,

        ip_address=ip,

        details=details,
    )

    db.add(entry)

    db.commit()


# ============================================================
# ACCOUNT LOCKOUT
# ============================================================

def account_locked(
    user: User
):

    if not user.locked_until:

        return False

    if (
        datetime.now(timezone.utc)
        < user.locked_until
    ):

        return True

    user.locked_until = None

    user.failed_logins = 0

    return False


# ============================================================
# REGISTER
# ============================================================

@app.post(
    "/auth/register"
)
def register(
    request: RegisterRequest,
    db=Depends(get_db),
):

    existing = db.query(
        User
    ).filter(
        (
            User.username
            == request.username
        )
        |
        (
            User.email
            == request.email
        )
    ).first()

    if existing:

        raise HTTPException(
            status_code=409,
            detail="User already exists",
        )

    user = User(

        email=request.email,

        username=request.username,

        password_hash=hash_password(
            request.password
        ),

        role=Role.USER.value,

        is_active=True,

        is_verified=False,
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    audit(
        db,
        user.id,
        "USER_REGISTERED",
        resource=user.username,
    )

    return {
        "id": user.id,
        "username": user.username,
        "status": "created",
    }


# ============================================================
# LOGIN
# ============================================================

@app.post(
    "/auth/login",
    response_model=TokenResponse,
)
def login(
    request: LoginRequest,
    http_request: Request,
    db=Depends(get_db),
):

    user = db.query(
        User
    ).filter(
        User.username
        == request.username
    ).first()

    ip = (
        http_request.client.host
        if http_request.client
        else None
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    if account_locked(user):

        db.commit()

        raise HTTPException(
            status_code=423,
            detail="Account temporarily locked",
        )

    if not verify_password(
        request.password,
        user.password_hash,
    ):

        user.failed_logins += 1

        if (
            user.failed_logins
            >= MAX_LOGIN_ATTEMPTS
        ):

            user.locked_until = (
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    minutes=LOCKOUT_MINUTES
                )
            )

        db.commit()

        audit(
            db,
            user.id,
            "LOGIN_FAILED",
            ip=ip,
        )

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    # Successful authentication

    user.failed_logins = 0

    user.locked_until = None

    user.last_login = datetime.now(
        timezone.utc
    )

    access_token = (
        create_access_token(
            user
        )
    )

    raw_refresh, refresh_hash = (
        generate_refresh_token()
    )

    refresh = RefreshToken(

        user_id=user.id,

        token_hash=refresh_hash,

        expires_at=(
            datetime.now(
                timezone.utc
            )
            + timedelta(
                days=REFRESH_TOKEN_DAYS
            )
        ),
    )

    db.add(refresh)

    db.commit()

    audit(
        db,
        user.id,
        "LOGIN_SUCCESS",
        ip=ip,
    )

    return TokenResponse(

        access_token=access_token,

        refresh_token=raw_refresh,

        expires_in=(
            ACCESS_TOKEN_MINUTES
            * 60
        ),
    )


# ============================================================
# REFRESH
# ============================================================

class RefreshRequest(BaseModel):

    refresh_token: str


@app.post(
    "/auth/refresh",
    response_model=TokenResponse,
)
def refresh_access_token(
    request: RefreshRequest,
    db=Depends(get_db),
):

    token_hash = hashlib.sha256(
        request.refresh_token.encode()
    ).hexdigest()

    stored = db.query(
        RefreshToken
    ).filter(
        RefreshToken.token_hash
        == token_hash
    ).first()

    if not stored:

        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    if stored.revoked:

        raise HTTPException(
            status_code=401,
            detail="Refresh token revoked",
        )

    if (
        datetime.now(timezone.utc)
        >= stored.expires_at
    ):

        raise HTTPException(
            status_code=401,
            detail="Refresh token expired",
        )

    user = db.get(
        User,
        stored.user_id
    )

    if not user or not user.is_active:

        raise HTTPException(
            status_code=403,
            detail="Account unavailable",
        )

    # Rotate refresh token

    stored.revoked = True

    raw_refresh, refresh_hash = (
        generate_refresh_token()
    )

    new_refresh = RefreshToken(

        user_id=user.id,

        token_hash=refresh_hash,

        expires_at=(
            datetime.now(
                timezone.utc
            )
            + timedelta(
                days=REFRESH_TOKEN_DAYS
            )
        ),
    )

    db.add(new_refresh)

    db.commit()

    return TokenResponse(

        access_token=create_access_token(
            user
        ),

        refresh_token=raw_refresh,

        expires_in=(
            ACCESS_TOKEN_MINUTES
            * 60
        ),
    )


# ============================================================
# LOGOUT
# ============================================================

@app.post(
    "/auth/logout"
)
def logout(
    request: RefreshRequest,
    user: User = Depends(
        get_current_user
    ),
    db=Depends(get_db),
):

    token_hash = hashlib.sha256(
        request.refresh_token.encode()
    ).hexdigest()

    token = db.query(
        RefreshToken
    ).filter(
        RefreshToken.token_hash
        == token_hash,
        RefreshToken.user_id
        == user.id,
    ).first()

    if token:

        token.revoked = True

        db.commit()

    audit(
        db,
        user.id,
        "LOGOUT",
    )

    return {
        "status": "logged_out"
    }


# ============================================================
# PROFILE
# ============================================================

@app.get(
    "/me"
)
def profile(
    user: User = Depends(
        get_current_user
    ),
):

    return {

        "id": user.id,

        "username": user.username,

        "email": user.email,

        "role": user.role,

        "active": user.is_active,

        "verified": user.is_verified,

        "last_login": user.last_login,
    }


# ============================================================
# GRANT EXCHANGE ACCESS
# ============================================================

@app.post(
    "/admin/exchange-access"
)
def grant_exchange_access(

    request: ExchangeAccessRequest,

    admin: User = Depends(
        require_roles(
            Role.SUPER_ADMIN,
            Role.ADMIN,
        )
    ),

    db=Depends(get_db),
):

    user = db.query(
        User
    ).filter(
        User.username
        == request.username
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    access = ExchangeAccess(

        user_id=user.id,

        exchange=request.exchange,

        permission=request.permission.value,

        enabled=True,
    )

    db.add(access)

    db.commit()

    audit(
        db,
        admin.id,
        "EXCHANGE_ACCESS_GRANTED",

        resource=(
            f"{user.username}:"
            f"{request.exchange}"
        ),

        details=(
            request.permission.value
        ),
    )

    return {
        "status": "granted",

        "user": user.username,

        "exchange": request.exchange,

        "permission": (
            request.permission.value
        ),
    }


# ============================================================
# CHANGE ROLE
# ============================================================

@app.post(
    "/admin/users/{username}/role"
)
def change_role(

    username: str,

    request: RoleChangeRequest,

    admin: User = Depends(
        require_roles(
            Role.SUPER_ADMIN
        )
    ),

    db=Depends(get_db),
):

    user = db.query(
        User
    ).filter(
        User.username
        == username
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    old_role = user.role

    user.role = request.role.value

    db.commit()

    audit(
        db,
        admin.id,
        "ROLE_CHANGED",
        resource=username,
        details=(
            f"{old_role} -> "
            f"{request.role.value}"
        ),
    )

    return {
        "username": username,

        "old_role": old_role,

        "new_role": request.role.value,
    }


# ============================================================
# DISABLE USER
# ============================================================

@app.post(
    "/admin/users/{username}/disable"
)
def disable_user(

    username: str,

    admin: User = Depends(
        require_roles(
            Role.SUPER_ADMIN,
            Role.ADMIN,
        )
    ),

    db=Depends(get_db),
):

    user = db.query(
        User
    ).filter(
        User.username
        == username
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user.is_active = False

    db.commit()

    audit(
        db,
        admin.id,
        "USER_DISABLED",
        resource=username,
    )

    return {
        "status": "disabled"
    }


# ============================================================
# EXCHANGE AUTHORIZATION
# ============================================================

def require_exchange_permission(
    exchange: str,
    permission: ExchangePermission,
):

    def dependency(

        user: User = Depends(
            get_current_user
        ),

        db=Depends(get_db),
    ):

        # Super-admin bypass

        if user.role == (
            Role.SUPER_ADMIN.value
        ):

            return user

        access = db.query(
            ExchangeAccess
        ).filter(

            ExchangeAccess.user_id
            == user.id,

            ExchangeAccess.exchange
            == exchange,

            ExchangeAccess.permission
            == permission.value,

            ExchangeAccess.enabled
            == True,
        ).first()

        if not access:

            raise HTTPException(
                status_code=403,
                detail=(
                    "Exchange permission "
                    "required"
                ),
            )

        return user

    return dependency


# ============================================================
# EXAMPLE EXCHANGE ENDPOINT
# ============================================================

@app.get(
    "/exchanges/RASE-WHEAT/market"
)
def wheat_market(

    user: User = Depends(
        require_exchange_permission(
            "RASE-WHEAT",
            ExchangePermission.VIEW,
        )
    )
):

    return {

        "exchange": "RASE-WHEAT",

        "user": user.username,

        "status": "authorized",

        "message": (
            "Market data would be "
            "served here."
        ),
    }


# ============================================================
# EXAMPLE TRADING ENDPOINT
# ============================================================

@app.post(
    "/exchanges/RASE-WHEAT/orders"
)
def submit_wheat_order(

    user: User = Depends(
        require_exchange_permission(
            "RASE-WHEAT",
            ExchangePermission.TRADE,
        )
    )
):

    return {

        "exchange": "RASE-WHEAT",

        "trader": user.username,

        "status": "authorized",

        "message": (
            "Order engine would "
            "receive the order here."
        ),
    }


# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/health"
)
def health():

    return {
        "system": "RHINO CORE",
        "status": "online",
    }
    
