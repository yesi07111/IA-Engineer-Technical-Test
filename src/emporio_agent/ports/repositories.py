from abc import ABC, abstractmethod
from collections.abc import Sequence

from emporio_agent.domain.models import (
    Category,
    Customer,
    HandoffTicket,
    Order,
    Product,
    Promotion,
)


class ProductRepository(ABC):
    """Read access to the product catalog."""

    @abstractmethod
    def list_all(self) -> Sequence[Product]:
        """Lists every product, whatever its status.

        Returns:
            All the products of the catalog.
        """

    @abstractmethod
    def get_by_id(self, product_id: int) -> Product | None:
        """Finds one product by its id.

        Args:
            product_id: Id of the product.

        Returns:
            The product, or None when the id does not exist.
        """


class CategoryRepository(ABC):
    """Read access to the product categories."""

    @abstractmethod
    def list_all(self) -> Sequence[Category]:
        """Lists every category.

        Returns:
            All the categories, including the ones without products.
        """


class PromotionRepository(ABC):
    """Read access to the promotions."""

    @abstractmethod
    def list_active(self) -> Sequence[Promotion]:
        """Lists the promotions that are running right now.

        Returns:
            Only the promotions flagged as active.
        """

    @abstractmethod
    def list_active_for_product(self, product_id: int) -> Sequence[Promotion]:
        """Lists the running promotions of one product.

        Args:
            product_id: Id of the product.

        Returns:
            The active promotions of that product, empty when it has none.
        """


class OrderRepository(ABC):
    """Read access to the orders and their items."""

    @abstractmethod
    def get_by_id(self, order_id: int) -> Order | None:
        """Finds one order by its number, with its items.

        Args:
            order_id: Number of the order.

        Returns:
            The order, or None when the number does not exist.
        """


class CustomerRepository(ABC):
    """Read access to the customers."""

    @abstractmethod
    def get_by_id(self, customer_id: int) -> Customer | None:
        """Finds one customer by id.

        Args:
            customer_id: Id of the customer.

        Returns:
            The customer, or None when the id does not exist.
        """


class TicketRepository(ABC):
    """Storage for the cases the agent hands over to the store team."""

    @abstractmethod
    def save(self, ticket: HandoffTicket) -> None:
        """Stores a new ticket.

        Args:
            ticket: Ticket to store.
        """

    @abstractmethod
    def list_all(self) -> Sequence[HandoffTicket]:
        """Lists every stored ticket.

        Returns:
            The tickets, oldest first.
        """
