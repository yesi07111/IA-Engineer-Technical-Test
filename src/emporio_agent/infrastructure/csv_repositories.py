import json
from collections.abc import Sequence
from pathlib import Path
from typing import TypeVar

from emporio_agent.domain.models import (
    Category,
    Customer,
    Order,
    OrderItem,
    Product,
    Promotion,
)
from emporio_agent.errors import DataLoadError
from emporio_agent.infrastructure.csv_reader import build_records, empty_to_none, read_csv_rows
from emporio_agent.ports.repositories import (
    CategoryRepository,
    CustomerRepository,
    OrderRepository,
    ProductRepository,
    PromotionRepository,
)

T = TypeVar("T", Category, Customer, Order, Product)


def index_by_id(records: list[T], file_name: str) -> dict[int, T]:
    """Indexes records by id and rejects repeated ids.

    Args:
        records: Records that have an ``id`` attribute.
        file_name: Source file, used in the error message.

    Returns:
        A dict from id to record.

    Raises:
        DataLoadError: If two records share the same id.
    """
    indexed: dict[int, T] = {}
    for record in records:
        if record.id in indexed:
            raise DataLoadError(f"{file_name} has the id {record.id} more than once")
        indexed[record.id] = record
    return indexed


def parse_specs(raw_specs: str) -> dict[str, str]:
    """Reads the JSON specs column of a product.

    Args:
        raw_specs: JSON object as text, can be empty.

    Returns:
        The specs with every value as text.

    Raises:
        ValueError: If the text is not a JSON object.
    """
    if not raw_specs:
        return {}
    specs = json.loads(raw_specs)
    if not isinstance(specs, dict):
        raise ValueError("specs must be a JSON object")
    return {str(key): str(value) for key, value in specs.items()}


class CsvProductRepository(ProductRepository):
    """Products loaded from products.csv."""

    def __init__(self, path: Path) -> None:
        """Loads and validates every product of the file.

        Args:
            path: Location of products.csv.

        Raises:
            DataLoadError: If the file is missing or has an invalid row.
        """
        rows = read_csv_rows(
            path, ["product_id", "price_brl", "name", "category_id", "stock_quantity", "status"]
        )
        products = build_records(
            rows,
            path.name,
            lambda row: Product.model_validate(
                {
                    "id": row["product_id"],
                    "name": row["name"],
                    "category_id": row["category_id"],
                    "description": row.get("description", ""),
                    "price_brl": row["price_brl"],
                    "stock_quantity": row["stock_quantity"] or 0,
                    "status": row["status"],
                    "specs": parse_specs(row.get("specs", "")),
                }
            ),
        )
        self._products = index_by_id(products, path.name)

    def list_all(self) -> Sequence[Product]:
        """Lists every product, whatever its status.

        Returns:
            All the products of the file.
        """
        return list(self._products.values())

    def get_by_id(self, product_id: int) -> Product | None:
        """Finds one product by its id.

        Args:
            product_id: Id of the product.

        Returns:
            The product, or None when the id does not exist.
        """
        return self._products.get(product_id)


class CsvCategoryRepository(CategoryRepository):
    """Categories loaded from categories.csv."""

    def __init__(self, path: Path) -> None:
        """Loads every category of the file.

        Args:
            path: Location of categories.csv.

        Raises:
            DataLoadError: If the file is missing or has an invalid row.
        """
        rows = read_csv_rows(path, ["category_id", "name"])
        categories = build_records(
            rows,
            path.name,
            lambda row: Category(
                id=int(row["category_id"]),
                name=row["name"],
                description=row.get("description", ""),
            ),
        )
        self._categories = index_by_id(categories, path.name)

    def list_all(self) -> Sequence[Category]:
        """Lists every category.

        Returns:
            All the categories of the file.
        """
        return list(self._categories.values())


class CsvPromotionRepository(PromotionRepository):
    """Promotions loaded from promotions.csv."""

    def __init__(self, path: Path) -> None:
        """Loads every promotion of the file.

        Args:
            path: Location of promotions.csv.

        Raises:
            DataLoadError: If the file is missing or has an invalid row.
        """
        rows = read_csv_rows(path, ["promotion_id", "product_id", "discount_percent", "is_active"])
        self._promotions = build_records(
            rows,
            path.name,
            lambda row: Promotion(
                id=int(row["promotion_id"]),
                product_id=int(row["product_id"]),
                discount_percent=float(row["discount_percent"]),
                description=row.get("description", ""),
                is_active=row["is_active"] in {"1", "true", "True"},
            ),
        )

    def list_active(self) -> Sequence[Promotion]:
        """Lists the promotions that are running right now.

        Returns:
            Only the promotions flagged as active.
        """
        return [promotion for promotion in self._promotions if promotion.is_active]

    def list_active_for_product(self, product_id: int) -> Sequence[Promotion]:
        """Lists the running promotions of one product.

        Args:
            product_id: Id of the product.

        Returns:
            The active promotions of that product, empty when it has none.
        """
        return [p for p in self.list_active() if p.product_id == product_id]


class CsvCustomerRepository(CustomerRepository):
    """Customers loaded from customers.csv."""

    def __init__(self, path: Path) -> None:
        """Loads every customer of the file.

        Args:
            path: Location of customers.csv.

        Raises:
            DataLoadError: If the file is missing or has an invalid row.
        """
        rows = read_csv_rows(path, ["customer_id", "name", "phone", "email"])
        customers = build_records(
            rows,
            path.name,
            lambda row: Customer(
                id=int(row["customer_id"]),
                name=row["name"],
                phone=row["phone"],
                email=row["email"],
                city=row.get("city", ""),
            ),
        )
        self._customers = index_by_id(customers, path.name)

    def list_all(self) -> Sequence[Customer]:
        """Lists every customer.

        Returns:
            All the customers of the file.
        """
        return list(self._customers.values())

    def get_by_id(self, customer_id: int) -> Customer | None:
        """Finds one customer by id.

        Args:
            customer_id: Id of the customer.

        Returns:
            The customer, or None when the id does not exist.
        """
        return self._customers.get(customer_id)


class CsvOrderRepository(OrderRepository):
    """Orders loaded from orders.csv, joined with their lines from order_items.csv."""

    def __init__(self, orders_path: Path, items_path: Path) -> None:
        """Loads the orders and attaches each one its items.

        Args:
            orders_path: Location of orders.csv.
            items_path: Location of order_items.csv.

        Raises:
            DataLoadError: If a file is missing or has an invalid row.
        """
        item_rows = read_csv_rows(items_path, ["order_id", "product_id", "quantity"])
        items_by_order: dict[int, list[OrderItem]] = {}
        for line_number, row in enumerate(item_rows, start=2):
            try:
                item = OrderItem(product_id=int(row["product_id"]), quantity=int(row["quantity"]))
                items_by_order.setdefault(int(row["order_id"]), []).append(item)
            except ValueError as error:
                raise DataLoadError(f"{items_path.name}, line {line_number}: {error}") from error

        order_rows = read_csv_rows(
            orders_path, ["order_id", "customer_id", "order_date", "status", "total_brl"]
        )
        orders = build_records(
            order_rows,
            orders_path.name,
            lambda row: Order.model_validate(
                {
                    "id": row["order_id"],
                    "customer_id": row["customer_id"],
                    "order_date": row["order_date"],
                    "status": row["status"],
                    "total_brl": row["total_brl"],
                    "payment_method": row.get("payment_method", ""),
                    "tracking_code": empty_to_none(row.get("tracking_code", "")),
                    "estimated_delivery": empty_to_none(row.get("estimated_delivery", "")),
                    "notes": empty_to_none(row.get("notes", "")),
                    "items": tuple(items_by_order.get(int(row["order_id"]), [])),
                }
            ),
        )
        self._orders = index_by_id(orders, orders_path.name)

    def list_all(self) -> Sequence[Order]:
        """Lists every order with its items.

        Returns:
            All the orders of the file.
        """
        return list(self._orders.values())

    def get_by_id(self, order_id: int) -> Order | None:
        """Finds one order by its number, with its items.

        Args:
            order_id: Number of the order.

        Returns:
            The order, or None when the number does not exist.
        """
        return self._orders.get(order_id)
