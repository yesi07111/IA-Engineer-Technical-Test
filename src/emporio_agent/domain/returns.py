from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from emporio_agent.domain.models import Order, OrderStatus

REGRET_WINDOW_DAYS = 7
PREFERENCE_WINDOW_DAYS = 7
DEFECT_WINDOW_DAYS = 30
LEGAL_WARRANTY_DAYS = 90


class ReturnReason(StrEnum):
    REGRET = "regret"
    DEFECT = "defect"
    PREFERENCE = "preference"


@dataclass(frozen=True)
class ReturnDecision:
    eligible: bool
    policy_section: str
    days_counted: int | None
    limit_days: int | None
    explanation: str


class ReturnPolicy:
    """Rules for returns and exchanges (policy section 4) and warranty (section 8)."""

    def check_return_eligebility_window(
        self, order: Order, reason: ReturnReason, today: date
    ) -> ReturnDecision:
        """Decides if an order can still be returned or exchanged for a given reason.

        Regret and preference count 7 days from delivery, defects count 30 days from
        the purchase. The data has no real delivery date, so the estimated delivery
        date is used instead.

        Args:
            order: Order the customer wants to return.
            reason: Why the customer wants to return it.
            today: Current date in the store's time zone.

        Returns:
            The decision with the section of the manual that backs it up.
        """
        if order.status is OrderStatus.CANCELLED:
            return ReturnDecision(
                False, "4", None, None, "O pedido foi cancelado, então não há produto a devolver."
            )
        if order.status is not OrderStatus.DELIVERED:
            return ReturnDecision(
                False,
                "4.1",
                None,
                None,
                "O pedido ainda não foi entregue. Os prazos de troca e devolução começam a "
                "contar a partir do recebimento.",
            )

        if reason is ReturnReason.DEFECT:
            return self._check_defect(order, today)

        received_on = order.estimated_delivery or order.order_date
        days = max((today - received_on).days, 0)
        section = "4.1" if reason is ReturnReason.REGRET else "4.3"
        limit = REGRET_WINDOW_DAYS if reason is ReturnReason.REGRET else PREFERENCE_WINDOW_DAYS
        if days <= limit:
            explanation = (
                f"Recebido há {days} dia(s), dentro do prazo de {limit} dias. O produto deve "
                "estar na embalagem original, sem sinais de uso."
            )
        else:
            explanation = (
                f"Recebido há {days} dias, fora do prazo de {limit} dias para essa solicitação."
            )
        return ReturnDecision(days <= limit, section, days, limit, explanation)

    def _check_defect(self, order: Order, today: date) -> ReturnDecision:
        """Applies the defect rules: store exchange first, then warranty.

        Args:
            order: Delivered order with the defective product.
            today: Current date in the store's time zone.

        Returns:
            Eligible within 30 days of purchase. After that it explains the warranty path.
        """
        days = max((today - order.order_date).days, 0)
        if days <= DEFECT_WINDOW_DAYS:
            return ReturnDecision(
                True,
                "4.2",
                days,
                DEFECT_WINDOW_DAYS,
                f"Compra feita há {days} dia(s), dentro do prazo de {DEFECT_WINDOW_DAYS} dias "
                "para troca por defeito de fabricação.",
            )

        # This is logic for the warranty, 90 days count from the delivery (policy 8.1)
        received_on = order.estimated_delivery or order.order_date
        under_legal_warranty = (today - received_on).days <= LEGAL_WARRANTY_DAYS
        warranty_note = (
            "Ainda está dentro da garantia legal de 90 dias."
            if under_legal_warranty
            else "A garantia legal de 90 dias já terminou; vale a garantia do fabricante."
        )
        return ReturnDecision(
            False,
            "4.2",
            days,
            DEFECT_WINDOW_DAYS,
            f"Compra feita há {days} dias: passou o prazo de troca direta na loja. A garantia "
            f"deve ser acionada com o fabricante e a loja pode intermediar. {warranty_note}",
        )
