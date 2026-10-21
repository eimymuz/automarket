"""Enumeraciones del dominio. Se guardan en PostgreSQL como tipos ENUM nativos."""
import enum

from sqlalchemy import Enum


class VehicleStatus(str, enum.Enum):
    DISPONIBLE = "disponible"
    RESERVADO = "reservado"
    VENDIDO = "vendido"


class Transmission(str, enum.Enum):
    MANUAL = "manual"
    AUTOMATICA = "automatica"
    CVT = "cvt"


class FuelType(str, enum.Enum):
    GASOLINA = "gasolina"
    DIESEL = "diesel"
    HIBRIDO = "hibrido"
    ELECTRICO = "electrico"


class DataSourceKind(str, enum.Enum):
    REAL = "real"              # dato tomado de una fuente verificable (catálogo oficial)
    REFERENCIA = "referencia"  # basado en una fuente real pero ajustado (precio seminuevo, km)
    PRUEBA = "prueba"          # generado para pruebas


class ReservationStatus(str, enum.Enum):
    ACTIVA = "activa"
    CANCELADA = "cancelada"
    EXPIRADA = "expirada"
    CONVERTIDA = "convertida"  # se convirtió en orden de compra


class OrderStatus(str, enum.Enum):
    PENDIENTE = "pendiente"    # creada, esperando pago simulado
    PAGADA = "pagada"          # pago simulado aprobado, esperando confirmación del admin
    CONFIRMADA = "confirmada"  # venta confirmada
    CANCELADA = "cancelada"


class PaymentMethod(str, enum.Enum):
    TARJETA = "tarjeta_simulada"
    TRANSFERENCIA = "transferencia_simulada"
    EFECTIVO = "efectivo_simulado"


class PaymentStatus(str, enum.Enum):
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"


class OperationSource(str, enum.Enum):
    DESKTOP = "desktop"
    WEB = "web"
    SISTEMA = "sistema"
    PIPELINE = "pipeline"


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Enum nativo de PostgreSQL que guarda el valor (p. ej. "disponible"), no el nombre."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
