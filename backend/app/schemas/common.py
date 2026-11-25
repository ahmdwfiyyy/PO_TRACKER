from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints

# Quantities are exact decimals in the database but plain numbers in JSON
QtyOut = Annotated[Decimal, PlainSerializer(float, return_type=float)]
QtyIn = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
QtyNonNeg = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
OptText = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=2000)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VendorRef(ORM):
    id: int
    name: str


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    pages: int
