from datetime import date
from pathlib import Path

import pytest

from emporio_agent.application.data_audit import Severity
from emporio_agent.config import Settings
from emporio_agent.container import build_data_auditor

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def issues():
    return build_data_auditor(Settings(data_dir=DATA_DIR)).find_issues(date(2026, 11, 3))


def records_with(issues, table):
    """Collects the records of the issues of one table.

    Args:
        issues: Issues found.
        table: Table name.

    Returns:
        The record labels of that table.
    """
    return {issue.record for issue in issues if issue.table == table}


def test_finds_orders_whose_total_does_not_match(issues):
    mismatches = {i.record for i in issues if "differs" in i.message}

    assert mismatches == {"order 3", "order 20"}


def test_finds_unreleased_products_in_orders(issues):
    unreleased = {i.record for i in issues if "coming_soon" in i.message}

    assert unreleased == {"order 3", "order 14"}


def test_finds_the_late_shipment(issues):
    late = [i for i in issues if "late" in i.message]

    assert [i.record for i in late] == ["order 8"]


def test_finds_shared_emails_and_sold_out_products(issues):
    assert "customers 11, 43" in records_with(issues, "customers")
    assert "product 96" in records_with(issues, "products")


def test_finds_categories_without_products(issues):
    assert records_with(issues, "categories") == {"category 6", "category 7", "category 8"}


def test_most_severe_issues_come_first(issues):
    severities = [issue.severity for issue in issues]

    assert severities[0] is Severity.HIGH
    assert severities == sorted(
        severities, key=[Severity.HIGH, Severity.MEDIUM, Severity.LOW].index
    )
