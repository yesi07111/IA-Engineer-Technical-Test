import pytest

from emporio_agent.domain.pricing import PriceCalculator, find_max_installmants_for_amount
from tests.factories import make_product, make_promotion


def test_pix_gives_five_percent_without_promotion():
    quote = PriceCalculator().quote(make_product(price=2199), [])

    assert quote.promotion_price is None
    assert quote.pix_price == 2089.05
    assert quote.final_price == 2199


def test_pix_does_not_stack_with_promotion():
    quote = PriceCalculator().quote(make_product(price=2399), [make_promotion(18)])

    assert quote.promotion_price == 1967.18
    assert quote.pix_price == 1967.18
    assert quote.promotion_percent == 18


def test_biggest_active_promotion_wins():
    promotions = [make_promotion(10, name="Small"), make_promotion(25, name="Big")]

    quote = PriceCalculator().quote(make_product(price=1000), promotions)

    assert quote.promotion_price == 750
    assert quote.promotion_name == "Big"


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (40.0, 1),  # too small to split
        (100.0, 2),  # 2x 50
        (159.9, 3),  # 3x 53.30, 4x would be under 80
        (480.0, 6),  # 6x 80 exactly
        (599.9, 6),  # 7x would be 85.70, under 100
        (700.0, 7),
        (11499.0, 12),
    ],
)
def test_installments_respect_minimum_per_range(amount, expected):
    assert find_max_installmants_for_amount(amount) == expected


def test_installment_value_matches_the_plan():
    quote = PriceCalculator().quote(make_product(price=2199), [])

    assert quote.max_installments == 12
    assert quote.installment_value == 183.25
