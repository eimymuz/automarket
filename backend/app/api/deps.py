"""Dependencias comunes: sesión de BD, usuario autenticado, roles y origen de la petición."""
import uuid

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.session import get_db, set_audit_actor
from app.models import User
from app.models.enums import OperationSource

bearer_scheme = HTTPBearer(auto_error=False, description="Token obtenido en POST /api/v1/auth/login")


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise Unauthorized("Token inválido o expirado", "invalid_token")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise Unauthorized("Usuario inexistente o desactivado", "invalid_token")
    set_audit_actor(db, user.id)
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise Unauthorized("Se requiere iniciar sesión", "not_authenticated")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role.name != "admin":
        raise Forbidden("Esta operación requiere rol de administrador", "admin_required")
    return user


def get_source(
    user: User | None = Depends(get_optional_user),
    x_client_app: str | None = Header(default=None, description="'desktop' (AutoMarket.exe) o 'web'"),
) -> OperationSource:
    """Origen de la operación para el historial. Si el cliente no lo indica, se deduce del rol."""
    if x_client_app in ("desktop", "web"):
        return OperationSource(x_client_app)
    return OperationSource.DESKTOP if user and user.role.name == "admin" else OperationSource.WEB
