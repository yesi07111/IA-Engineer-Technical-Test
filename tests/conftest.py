from pathlib import Path

import pytest

from emporio_agent.application.catalog import CatalogService
from emporio_agent.domain.pricing import PriceCalculator
from emporio_agent.infrastructure.csv_repositories import (
    CsvCategoryRepository,
    CsvCustomerRepository,
    CsvOrderRepository,
    CsvProductRepository,
    CsvPromotionRepository,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="session")
def products():
    return CsvProductRepository(DATA_DIR / "products.csv")


@pytest.fixture(scope="session")
def orders():
    return CsvOrderRepository(DATA_DIR / "orders.csv", DATA_DIR / "order_items.csv")


@pytest.fixture(scope="session")
def customers():
    return CsvCustomerRepository(DATA_DIR / "customers.csv")


@pytest.fixture(scope="session")
def catalog(products):
    return CatalogService(
        products,
        CsvCategoryRepository(DATA_DIR / "categories.csv"),
        CsvPromotionRepository(DATA_DIR / "promotions.csv"),
        PriceCalculator(),
    )
