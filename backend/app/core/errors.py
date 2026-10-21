"""Errores de dominio y su traducción a respuestas HTTP con formato uniforme:

    {"detail": "mensaje legible", "code": "codigo_estable"}

El campo `code` no cambia aunque cambie el mensaje: los clientes deben basarse en él.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

log = logging.getLogger("automarket.errors")


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str, code: str = "error"):
        super().__init__(detail)
        self.detail = detail
        self.code = code


class NotFound(DomainError):
    status_code = 404


class Forbidden(DomainError):
    status_code = 403


class Conflict(DomainError):
    status_code = 409


class Unauthorized(DomainError):
    status_code = 401


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse({"detail": exc.detail, "code": exc.code}, exc.status_code, headers=headers)

    @app.exception_handler(StaleDataError)
    async def _stale(_: Request, exc: StaleDataError):
        return JSONResponse(
            {"detail": "El registro fue modificado por otro usuario; recarga e intenta de nuevo.",
             "code": "version_conflict"}, 409,
        )

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        # Última línea de defensa: índices únicos y CHECK de la base de datos
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        log.warning("IntegrityError (%s): %s", constraint, exc.orig)
        return JSONResponse(
            {"detail": "La operación viola una regla de integridad de los datos.",
             "code": f"integrity:{constraint}" if constraint else "integrity_error"}, 409,
        )
