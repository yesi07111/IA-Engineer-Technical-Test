from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProductStatus(StrEnum):
    ACTIVE = "active"
    DISCONTINUED = "discontinued"
    COMING_SOON = "coming_soon"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class StoreRecord(BaseModel):
    """Base for every store record.

    Records are frozen so nothing in the agent can change the store data by accident.
    """

    model_config = ConfigDict(frozen=True)


class Category(StoreRecord):
    id: int
    name: str
    description: str


class Product(StoreRecord):
    id: int
    name: str
    category_id: int
    description: str
    price_brl: float = Field(gt=0)
    stock_quantity: int = Field(ge=0)
    status: ProductStatus
    specs: dict[str, str] = Field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        """Tells if the product can be sold right now.

        Returns:
            True when the product is active and has at least one unit in stock.
        """
        return self.status is ProductStatus.ACTIVE and self.stock_quantity > 0


class Promotion(StoreRecord):
    id: int
    product_id: int
    discount_percent: float = Field(gt=0, lt=100)
    description: str
    is_active: bool


class Customer(StoreRecord):
    id: int
    name: str
    phone: str
    email: str
    city: str


class OrderItem(StoreRecord):
    product_id: int
    quantity: int = Field(gt=0)


class Order(StoreRecord):
    id: int
    customer_id: int
    order_date: date
    status: OrderStatus
    total_brl: float = Field(ge=0)
    payment_method: str
    tracking_code: str | None = None
    estimated_delivery: date | None = None
    notes: str | None = None
    items: tuple[OrderItem, ...] = ()


class PolicySection(StoreRecord):
    number: str
    title: str
    text: str
