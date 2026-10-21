"""Comandos de administración.

    python -m app.cli create-admin --email admin@automarket.mx --name "Administrador"

La contraseña se pide de forma oculta (no queda en el historial de PowerShell).
"""
import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, User


def create_admin(email: str, name: str, password: str) -> None:
    with SessionLocal() as db:
        role = db.scalar(select(Role).where(Role.name == "admin"))
        user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if user:
            user.role_id, user.password_hash, user.is_active = role.id, hash_password(password), True
            action = "actualizado"
        else:
            db.add(User(email=email.lower(), full_name=name, password_hash=hash_password(password), role_id=role.id))
            action = "creado"
        db.commit()
    print(f"Administrador {action}: {email}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="Crea (o restablece) un usuario administrador")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="Administrador")
    args = parser.parse_args()

    password = getpass.getpass("Contraseña (mín. 8 caracteres): ")
    if len(password) < 8 or password != getpass.getpass("Repite la contraseña: "):
        sys.exit("Las contraseñas no coinciden o son muy cortas")
    create_admin(args.email, args.name, password)


if __name__ == "__main__":
    main()
