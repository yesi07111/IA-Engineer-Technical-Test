from collections import Counter
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from emporio_agent.domain.models import OrderStatus, ProductStatus
from emporio_agent.ports.repositories import (
    CategoryRepository,
    CustomerRepository,
    OrderRepository,
    ProductRepository,
    PromotionRepository,
)

TOTAL_TOLERANCE_BRL = 0.01


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class DataIssue:
    severity: Severity
    table: str
    record: str
    message: str


class DataAuditor:
    """Finds inconsistencies in the store data that the team should fix."""

    def __init__(
        self,
        products: ProductRepository,
        categories: CategoryRepository,
        promotions: PromotionRepository,
        orders: OrderRepository,
        customers: CustomerRepository,
    ) -> None:
        """Keeps the repositories to inspect.

        Args:
            products: Product catalog.
            categories: Product categories.
            promotions: Promotions.
            orders: Orders with items.
            customers: Customers.
        """
        self._products = products
        self._categories = categories
        self._promotions = promotions
        self._orders = orders
        self._customers = customers

    def find_issues(self, today: date) -> list[DataIssue]:
        """Runs every check and collects the problems found.

        Args:
            today: Current date, used to detect late deliveries.

        Returns:
            The issues, most severe first.
        """
        issues = [
            *self._check_order_totals(),
            *self._check_unreleased_products_in_orders(),
            *self._check_late_shipments(today),
            *self._check_out_of_stock_active_products(),
            *self._check_shared_customer_emails(),
            *self._check_conflicting_promotions(),
            *self._check_empty_categories(),
        ]
        order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        return sorted(issues, key=lambda issue: order[issue.severity])

    def _check_order_totals(self) -> list[DataIssue]:
        """Compares each order total with the sum of its items at list price.

        Returns:
            One issue per order whose total does not match.
        """
        issues = []
        for order in self._orders.list_all():
            items_total = 0.0
            for item in order.items:
                product = self._products.get_by_id(item.product_id)
                if product is None:
                    issues.append(
                        DataIssue(
                            Severity.HIGH,
                            "order_items",
                            f"order {order.id}",
                            f"Item points to product {item.product_id}, which does not exist.",
                        )
                    )
                    continue
                items_total += product.price_brl * item.quantity
            if order.items and abs(items_total - order.total_brl) > TOTAL_TOLERANCE_BRL:
                issues.append(
                    DataIssue(
                        Severity.MEDIUM,
                        "orders",
                        f"order {order.id}",
                        f"Total R$ {order.total_brl:.2f} differs from the items at list price "
                        f"(R$ {items_total:.2f}). Check for a discount that was not recorded.",
                    )
                )
        return issues

    def _check_unreleased_products_in_orders(self) -> list[DataIssue]:
        """Finds non cancelled orders with products that are not on sale.

        Returns:
            One issue per order line with a discontinued or coming soon product.
        """
        issues = []
        for order in self._orders.list_all():
            if order.status is OrderStatus.CANCELLED:
                continue
            for item in order.items:
                product = self._products.get_by_id(item.product_id)
                if product and product.status is not ProductStatus.ACTIVE:
                    issues.append(
                        DataIssue(
                            Severity.HIGH,
                            "orders",
                            f"order {order.id}",
                            f"Contains '{product.name}', which is {product.status.value} "
                            f"(order status: {order.status.value}).",
                        )
                    )
        return issues

    def _check_late_shipments(self, today: date) -> list[DataIssue]:
        """Finds shipped orders whose estimated delivery already passed.

        Args:
            today: Current date.

        Returns:
            One issue per late shipment.
        """
        return [
            DataIssue(
                Severity.HIGH,
                "orders",
                f"order {order.id}",
                f"Shipped, estimated delivery {order.estimated_delivery} already passed "
                f"({(today - order.estimated_delivery).days} days late). Contact the carrier.",
            )
            for order in self._orders.list_all()
            if order.status is OrderStatus.SHIPPED
            and order.estimated_delivery is not None
            and order.estimated_delivery < today
        ]

    def _check_out_of_stock_active_products(self) -> list[DataIssue]:
        """Finds active products with no stock, they show up as sold out to customers.

        Returns:
            One issue per product.
        """
        return [
            DataIssue(
                Severity.LOW,
                "products",
                f"product {product.id}",
                f"'{product.name}' is active but has 0 units. Restock or change its status.",
            )
            for product in self._products.list_all()
            if product.status is ProductStatus.ACTIVE and product.stock_quantity == 0
        ]

    def _check_shared_customer_emails(self) -> list[DataIssue]:
        """Finds e-mails used by more than one customer.

        Returns:
            One issue per repeated e-mail.
        """
        customers = self._customers.list_all()
        counts = Counter(customer.email.strip().lower() for customer in customers)
        issues = []
        for email, count in counts.items():
            if count > 1:
                ids = [str(c.id) for c in customers if c.email.strip().lower() == email]
                issues.append(
                    DataIssue(
                        Severity.MEDIUM,
                        "customers",
                        f"customers {', '.join(ids)}",
                        f"Share the e-mail {email}. Possible duplicate registration.",
                    )
                )
        return issues

    def _check_conflicting_promotions(self) -> list[DataIssue]:
        """Finds products with more than one active promotion.

        Returns:
            One issue per product, the agent applies the biggest discount in that case.
        """
        counts = Counter(promotion.product_id for promotion in self._promotions.list_active())
        return [
            DataIssue(
                Severity.MEDIUM,
                "promotions",
                f"product {product_id}",
                f"Has {count} active promotions at the same time; the biggest one is applied.",
            )
            for product_id, count in counts.items()
            if count > 1
        ]

    def _check_empty_categories(self) -> list[DataIssue]:
        """Finds categories with no product that can be bought.

        Returns:
            One issue per empty category.
        """
        available = {p.category_id for p in self._products.list_all() if p.is_available}
        return [
            DataIssue(
                Severity.LOW,
                "categories",
                f"category {category.id}",
                f"'{category.name}' has no available products, customers will find nothing.",
            )
            for category in self._categories.list_all()
            if category.id not in available
        ]
