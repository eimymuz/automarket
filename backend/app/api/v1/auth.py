from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import Conflict, Unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db, set_audit_actor
from app.models import Role, User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.schemas.common import ErrorOut

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             responses={409: {"model": ErrorOut}})
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """Registro de **clientes** de la página web. Los administradores se crean con `python -m app.cli`."""
    email = data.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise Conflict("Ya existe una cuenta con ese correo", "email_taken")
    role = db.scalar(select(Role).where(Role.name == "cliente"))
    user = User(email=email, password_hash=hash_password(data.password), full_name=data.full_name,
                phone=data.phone, role_id=role.id)
    db.add(user)
    db.flush()
    set_audit_actor(db, user.id)
    db.commit()
    return UserOut.from_model(user)


@router.post("/login", response_model=TokenOut, responses={401: {"model": ErrorOut}})
def login(data: LoginIn, db: Session = Depends(get_db)):
    """Devuelve un token JWT. Enviarlo en cada petición: `Authorization: Bearer <token>`."""
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    # Mismo mensaje si el correo no existe o la contraseña es incorrecta (no revela qué cuentas existen)
    if not user or not verify_password(data.password, user.password_hash) or not user.is_active:
        raise Unauthorized("Correo o contraseña incorrectos", "invalid_credentials")
    token, expires_at = create_access_token(user.id, user.role.name)
    return TokenOut(access_token=token, expires_at=expires_at, user=UserOut.from_model(user))


@router.get("/me", response_model=UserOut, responses={401: {"model": ErrorOut}})
def me(user: User = Depends(get_current_user)):
    return UserOut.from_model(user)
