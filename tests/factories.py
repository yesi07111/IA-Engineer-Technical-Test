from datetime import date

from emporio_agent.domain.models import Order, OrderStatus, Product, Promotion


def make_product(price: float = 1000.0, stock: int = 5, status: str = "active", **extra) -> Product:
    """Creates a product with sensible defaults for tests.

    Args:
        price: Price in BRL.
        stock: Units in stock.
        status: Product status.
        **extra: Any other Product field to override.

    Returns:
        A valid Product.
    """
    fields = {
        "id": 1,
        "name": "Test Guitar",
        "category_id": 5,
        "description": "",
        "price_brl": price,
        "stock_quantity": stock,
        "status": status,
    }
    return Product(**{**fields, **extra})


def make_promotion(percent: float, product_id: int = 1, name: str = "Promo") -> Promotion:
    """Creates an active promotion for tests.

    Args:
        percent: Discount percent.
        product_id: Product the promotion applies to.
        name: Promotion name.

    Returns:
        An active Promotion.
    """
    return Promotion(
        id=1, product_id=product_id, discount_percent=percent, description=name, is_active=True
    )


def make_order(
    status: OrderStatus = OrderStatus.DELIVERED,
    order_date: date = date(2026, 3, 1),
    estimated_delivery: date | None = date(2026, 3, 5),
    customer_id: int = 1,
) -> Order:
    """Creates an order for tests.

    Args:
        status: Order status.
        order_date: Purchase date.
        estimated_delivery: Expected delivery date.
        customer_id: Owner of the order.

    Returns:
        A valid Order.
    """
    return Order(
        id=1,
        customer_id=customer_id,
        order_date=order_date,
        status=status,
        total_brl=500.0,
        payment_method="pix",
        estimated_delivery=estimated_delivery,
    )
