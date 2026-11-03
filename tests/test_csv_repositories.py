from pathlib import Path

import pytest

from emporio_agent.domain.models import OrderStatus, ProductStatus
from emporio_agent.errors import DataLoadError
from emporio_agent.infrastructure.csv_repositories import (
    CsvCategoryRepository,
    CsvCustomerRepository,
    CsvOrderRepository,
    CsvProductRepository,
    CsvPromotionRepository,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_loads_the_whole_catalog():
    products = CsvProductRepository(DATA_DIR / "products.csv")

    assert len(products.list_all()) == 65
    takamine = products.get_by_id(95)
    assert takamine is not None
    assert takamine.name.startswith("Takamine GD20")
    assert takamine.specs["strings"] == "steel"
    assert products.get_by_id(113).status is ProductStatus.DISCONTINUED


def test_out_of_stock_product_is_not_available():
    products = CsvProductRepository(DATA_DIR / "products.csv")

    assert products.get_by_id(96).is_available is False
    assert products.get_by_id(81).is_available is True


def test_only_active_promotions_are_listed():
    promotions = CsvPromotionRepository(DATA_DIR / "promotions.csv")

    assert {p.product_id for p in promotions.list_active()} == {127, 121, 90, 94}
    assert promotions.list_active_for_product(95) == []


def test_orders_come_with_their_items():
    orders = CsvOrderRepository(DATA_DIR / "orders.csv", DATA_DIR / "order_items.csv")

    order = orders.get_by_id(15)
    assert order is not None
    assert order.status is OrderStatus.PENDING
    assert {item.product_id for item in order.items} == {82, 106}
    assert orders.get_by_id(9999) is None


def test_cancelled_order_keeps_empty_tracking_as_none():
    orders = CsvOrderRepository(DATA_DIR / "orders.csv", DATA_DIR / "order_items.csv")

    order = orders.get_by_id(17)
    assert order.tracking_code is None
    assert order.estimated_delivery is None
    assert order.notes


def test_customers_and_categories_load():
    assert CsvCustomerRepository(DATA_DIR / "customers.csv").get_by_id(3).city == "Campo Grande"
    assert len(CsvCategoryRepository(DATA_DIR / "categories.csv").list_all()) == 9


def test_missing_file_gives_a_clear_error(tmp_path):
    with pytest.raises(DataLoadError, match="not found"):
        CsvProductRepository(tmp_path / "nope.csv")


def test_invalid_row_points_to_the_line(tmp_path):
    broken = tmp_path / "products.csv"
    broken.write_text(
        "product_id,price_brl,name,category_id,stock_quantity,status\n"
        "1,100,Ok,5,1,active\n"
        "2,-5,Negative price,5,1,active\n",
        encoding="utf-8",
    )

    with pytest.raises(DataLoadError, match="line 3"):
        CsvProductRepository(broken)


def test_repeated_id_is_rejected(tmp_path):
    broken = tmp_path / "products.csv"
    broken.write_text(
        "product_id,price_brl,name,category_id,stock_quantity,status\n"
        "1,100,A,5,1,active\n"
        "1,200,B,5,1,active\n",
        encoding="utf-8",
    )

    with pytest.raises(DataLoadError, match="more than once"):
        CsvProductRepository(broken)
