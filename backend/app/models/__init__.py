"""Importa todos los modelos para que Alembic los detecte en Base.metadata."""
from app.models.catalog import Brand, DataSource, VehicleModel
from app.models.commerce import Payment, PurchaseOrder, Reservation, Sale
from app.models.history import AuditLog, OperationHistory
from app.models.user import Role, User
from app.models.vehicle import Vehicle, VehicleImage

__all__ = [
    "AuditLog", "Brand", "DataSource", "OperationHistory", "Payment", "PurchaseOrder",
    "Reservation", "Role", "Sale", "User", "Vehicle", "VehicleImage", "VehicleModel",
]
