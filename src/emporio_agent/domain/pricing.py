from collections.abc import Sequence
from dataclasses import dataclass

from emporio_agent.domain.models import Product, Promotion

PIX_DISCOUNT_PERCENT = 5.0
MAX_INSTALLMENTS = 12

# This is the minimum value of each installment by installment range (policy 3.1)
INSTALLMENT_MINIMUMS: tuple[tuple[int, float], ...] = ((3, 50.0), (6, 80.0), (12, 100.0))


@dataclass(frozen=True)
class PriceQuote:
    list_price: float
    promotion_price: float | None
    promotion_percent: float | None
    promotion_name: str | None
    pix_price: float
    max_installments: int
    installment_value: float

    @property
    def final_price(self) -> float:
        """Gets the price the customer pays with card, debit or boleto.

        Returns:
            The promotion price when there is one, the list price otherwise.
        """
        return self.promotion_price if self.promotion_price is not None else self.list_price


def apply_discount(amount: float, percent: float) -> float:
    """Applies a percentage discount to an amount.

    Args:
        amount: Original value in BRL.
        percent: Discount between 0 and 100.

    Returns:
        The discounted value rounded to cents.
    """
    return round(amount * (1 - percent / 100), 2)


def find_max_installmants_for_amount(amount: float) -> int:
    """Finds the largest number of interest free installments allowed for an amount.

    Each range has its own minimum per installment: up to 3x R$ 50, 4x to 6x R$ 80
    and 7x to 12x R$ 100.

    Args:
        amount: Total to split, in BRL.

    Returns:
        A number between 1 and 12. Amounts too small to split return 1.
    """
    best = 1
    for range_end, minimum in INSTALLMENT_MINIMUMS:
        for installments in range(best + 1, range_end + 1):
            if amount / installments >= minimum:
                best = installments
    return min(best, MAX_INSTALLMENTS)


class PriceCalculator:
    """Builds the price quote of a product following the store payment rules."""

    def quote(self, product: Product, active_promotions: Sequence[Promotion]) -> PriceQuote:
        """Calculates the list, promotion and PIX prices plus the installment plan.

        Args:
            product: Product being quoted.
            active_promotions: Active promotions of that product, can be empty.

        Returns:
            The full quote. When several promotions are active the biggest one wins.
        """
        promotion = max(active_promotions, key=lambda p: p.discount_percent, default=None)
        promotion_price = (
            apply_discount(product.price_brl, promotion.discount_percent) if promotion else None
        )
        base_price = promotion_price if promotion_price is not None else product.price_brl

        # This is for the no stacking rule, PIX only discounts full price items (policy 6.2)
        pix_price = base_price if promotion else apply_discount(base_price, PIX_DISCOUNT_PERCENT)

        installments = find_max_installmants_for_amount(base_price)
        return PriceQuote(
            list_price=product.price_brl,
            promotion_price=promotion_price,
            promotion_percent=promotion.discount_percent if promotion else None,
            promotion_name=promotion.description if promotion else None,
            pix_price=pix_price,
            max_installments=installments,
            installment_value=round(base_price / installments, 2),
        )
