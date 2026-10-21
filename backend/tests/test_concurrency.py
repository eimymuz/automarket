"""Concurrencia REAL: varias conexiones independientes intentan reservar el mismo vehículo a la vez.

A diferencia de las demás pruebas, aquí cada hilo hace commit de verdad (con su propia conexión),
por eso la prueba limpia todo lo que creó al terminar.
"""
import threading
import uuid
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.errors import Conflict
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Brand, OperationHistory, Reservation, Role, User, Vehicle, VehicleModel
from app.models.enums import FuelType, OperationSource, Transmission, VehicleStatus
from app.schemas.commerce import ReservationCreate
from app.services.commerce import create_reservation
from tests.conftest import requires_db

pytestmark = requires_db
CLIENTES = 10


def test_diez_clientes_reservan_el_mismo_auto_al_mismo_tiempo():
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        role_id = db.scalar(select(Role.id).where(Role.name == "cliente"))
        users = [User(email=f"conc-{tag}-{i}@test.mx", password_hash=hash_password("x" * 8),
                      full_name=f"Concurrente {i}", role_id=role_id) for i in range(CLIENTES)]
        brand = Brand(name=f"Conc-{tag}")
        model = VehicleModel(brand=brand, name="Concurrente")
        vehicle = Vehicle(stock_number=f"C-{tag.upper()}", model=model, year=2025, version="Base",
                          price_mxn=Decimal("300000"), color="Gris", transmission=Transmission.MANUAL,
                          fuel_type=FuelType.GASOLINA, engine="1.5L")
        db.add_all([*users, vehicle])
        db.commit()
        user_ids, vehicle_id, brand_id = [u.id for u in users], vehicle.id, brand.id

    barrier = threading.Barrier(CLIENTES)
    results: list[str] = []

    def intentar(user_id):
        with SessionLocal() as db:
            user = db.get(User, user_id)
            barrier.wait()  # todos salen al mismo tiempo
            try:
                create_reservation(db, ReservationCreate(vehicle_id=vehicle_id), user, OperationSource.WEB)
                results.append("ok")
            except Conflict as exc:
                results.append(exc.code)

    try:
        threads = [threading.Thread(target=intentar, args=(uid,)) for uid in user_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert results.count("ok") == 1, results
        assert results.count("vehicle_not_available") == CLIENTES - 1, results
        with SessionLocal() as db:
            assert db.get(Vehicle, vehicle_id).status == VehicleStatus.RESERVADO
            assert len(db.scalars(select(Reservation).where(Reservation.vehicle_id == vehicle_id)).all()) == 1
    finally:
        with SessionLocal() as db:
            db.execute(delete(OperationHistory).where(OperationHistory.vehicle_id == vehicle_id))
            db.execute(delete(Reservation).where(Reservation.vehicle_id == vehicle_id))
            db.execute(delete(Vehicle).where(Vehicle.id == vehicle_id))
            db.execute(delete(VehicleModel).where(VehicleModel.brand_id == brand_id))
            db.execute(delete(Brand).where(Brand.id == brand_id))
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.commit()
