from datetime import date
from typing import Any

from emporio_agent.application.presenters import (
    ORDER_STATUS_PT,
    describe_payment_method,
    format_brl,
)
from emporio_agent.domain.models import Customer, Order, OrderStatus
from emporio_agent.domain.returns import ReturnPolicy, ReturnReason
from emporio_agent.domain.text import keep_only_digits
from emporio_agent.errors import InvalidRequestError
from emporio_agent.ports.repositories import (
    CustomerRepository,
    OrderRepository,
    ProductRepository,
)

LOCAL_PHONE_DIGITS = 8
NOT_VERIFIED_MESSAGE = (
    "Não encontramos um pedido com esse número e esse contato. Confira o número do pedido "
    "e o e-mail ou telefone usado na compra."
)


def contact_matches_customer(contact: str, customer: Customer) -> bool:
    """Checks if the e-mail or phone given by the person belongs to the customer.

    Args:
        contact: E-mail or phone, in any format.
        customer: Owner of the order.

    Returns:
        True when the e-mail matches ignoring case, or the phone matches ignoring format.
    """
    contact = contact.strip()
    if "@" in contact:
        return contact.lower() == customer.email.strip().lower()

    # This is for accepting phones in any format, with or without +55 or the area code,
    # so only the last 8 digits are compered
    given_digits = keep_only_digits(contact)
    if len(given_digits) < LOCAL_PHONE_DIGITS:
        return False
    return keep_only_digits(customer.phone).endswith(given_digits[-LOCAL_PHONE_DIGITS:])


class OrderLookupService:
    """Gives order information only to the person who placed the order."""

    def __init__(
        self,
        orders: OrderRepository,
        customers: CustomerRepository,
        products: ProductRepository,
        return_policy: ReturnPolicy,
    ) -> None:
        """Keeps the repositories and rules the service needs.

        Args:
            orders: Orders with their items.
            customers: Customers, used to verify identity.
            products: Products, used to name the items of an order.
            return_policy: Rules for returns and exchanges.
        """
        self._orders = orders
        self._customers = customers
        self._products = products
        self._return_policy = return_policy

    def find_verified_order(self, order_id: int, contact: str) -> Order | None:
        """Finds an order only if the contact belongs to its owner.

        Args:
            order_id: Order number.
            contact: E-mail or phone registered on the purchase.

        Returns:
            The order, or None when it does not exist or the contact does not match.
            Both cases look the same on purpose, so nobody can guess other people's orders.

        Raises:
            InvalidRequestError: If the order number is not positive or the contact is empty.
        """
        if order_id <= 0:
            raise InvalidRequestError("Order numbers are positive integers.")
        if not contact or not contact.strip():
            raise InvalidRequestError(
                "The e-mail or phone used in the purchase is required, ask the customer for it."
            )
        order = self._orders.get_by_id(order_id)
        if order is None:
            return None
        customer = self._customers.get_by_id(order.customer_id)
        if customer is None or not contact_matches_customer(contact, customer):
            return None
        return order

    def describe_order_status(self, order_id: int, contact: str, today: date) -> dict[str, Any]:
        """Explains the current state of an order to its owner.

        Args:
            order_id: Order number.
            contact: E-mail or phone registered on the purchase.
            today: Current date, used to detect late deliveries.

        Returns:
            Status, dates, tracking, items and total, or an "error" key when the order
            can not be shown.

        Raises:
            InvalidRequestError: If the order number or contact are invalid.
        """
        order = self.find_verified_order(order_id, contact)
        if order is None:
            return {"error": NOT_VERIFIED_MESSAGE}

        customer = self._customers.get_by_id(order.customer_id)
        summary: dict[str, Any] = {
            "order_id": order.id,
            "customer_first_name": customer.name.split()[0] if customer else None,
            "status": ORDER_STATUS_PT[order.status],
            "order_date": order.order_date.isoformat(),
            "total": format_brl(order.total_brl),
            "payment_method": describe_payment_method(order.payment_method),
            "items": self._describe_items(order),
        }
        if order.tracking_code:
            summary["tracking_code"] = order.tracking_code
        if order.estimated_delivery:
            summary["estimated_delivery"] = order.estimated_delivery.isoformat()
        if order.notes:
            summary["notes"] = order.notes

        is_late = (
            order.status is OrderStatus.SHIPPED
            and order.estimated_delivery is not None
            and order.estimated_delivery < today
        )
        if is_late:
            summary["warning"] = (
                "A entrega estimada já passou. Ofereça encaminhar o caso para a equipe."
            )
        return summary

    def check_return_request(
        self, order_id: int, contact: str, reason: ReturnReason, today: date
    ) -> dict[str, Any]:
        """Tells the owner of an order if it can still be returned or exchanged.

        Args:
            order_id: Order number.
            contact: E-mail or phone registered on the purchase.
            reason: Regret, defect or preference.
            today: Current date in the store's time zone.

        Returns:
            Eligibility, the manual section that applies and an explanation, or an
            "error" key when the order can not be shown.

        Raises:
            InvalidRequestError: If the order number or contact are invalid.
        """
        order = self.find_verified_order(order_id, contact)
        if order is None:
            return {"error": NOT_VERIFIED_MESSAGE}
        decision = self._return_policy.check_return_eligebility_window(order, reason, today)
        return {
            "order_id": order.id,
            "eligible": decision.eligible,
            "policy_section": decision.policy_section,
            "days_counted": decision.days_counted,
            "limit_days": decision.limit_days,
            "explanation": decision.explanation,
        }

    def _describe_items(self, order: Order) -> list[str]:
        """Writes each line of the order as "quantity x product name".

        Args:
            order: Order with items.

        Returns:
            One text per item. Unknown products show their id.
        """
        lines = []
        for item in order.items:
            product = self._products.get_by_id(item.product_id)
            name = product.name if product else f"produto #{item.product_id}"
            lines.append(f"{item.quantity}x {name}")
        return lines
