from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(description="Total de registros que cumplen el filtro")
    page: int
    page_size: int


class ErrorOut(BaseModel):
    detail: str
    code: str = Field(description="Código estable del error, p. ej. 'vehicle_not_available'")
