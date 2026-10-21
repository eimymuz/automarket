"""Configuración central del backend, leída desde variables de entorno / archivo .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
# backend/.env, sin importar desde qué carpeta se ejecute (API, Alembic o pipeline)
ENV_FILE = BACKEND_DIR / ".env"
INSECURE_SECRET = "CAMBIA_ESTE_SECRETO"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AutoMarket API"
    app_version: str = "0.4.0"
    environment: str = "development"

    # Conexión a PostgreSQL (solo el backend la conoce; los clientes nunca ven la BD)
    database_url: str = "postgresql+psycopg://automarket_app:automarket_app@localhost:5433/automarket"

    # Orígenes permitidos para CORS, separados por coma
    cors_origins: str = "http://localhost:5173"

    # Autenticación
    jwt_secret: str = INSECURE_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480

    # Reglas de negocio
    reservation_default_hours: int = 48
    reservation_max_hours: int = 72
    expiration_check_seconds: int = 60

    # Fotografías subidas desde AutoMarket.exe
    media_dir: Path = BACKEND_DIR / "media"
    max_image_mb: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
