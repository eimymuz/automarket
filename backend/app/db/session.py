"""Motor y sesiones de SQLAlchemy."""
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def set_audit_actor(db: Session, user_id) -> None:
    """Indica a los triggers de auditoría qué usuario hace los cambios de esta sesión."""
    db.info["actor_id"] = str(user_id)
    if db.in_transaction():
        db.execute(text("SELECT set_config('app.user_id', :actor, true)"), {"actor": str(user_id)})


@event.listens_for(Session, "after_begin")
def _apply_audit_actor(session: Session, transaction, connection) -> None:
    # set_config(..., true) solo dura una transacción; se repite en cada una que abra la sesión
    actor = session.info.get("actor_id")
    if actor:
        connection.execute(text("SELECT set_config('app.user_id', :actor, true)"), {"actor": actor})


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
