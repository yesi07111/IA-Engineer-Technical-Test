import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evaluate_agent import check_answer  # noqa: E402


def test_case_passes_when_tools_and_texts_match():
    case = {"expect_tools": ["get_product_details"], "must_contain": ["2.199"]}

    assert check_answer(case, ["get_product_details"], ["Custa R$ 2.199,00"]) == []


def test_missing_tool_and_text_are_reported():
    case = {"expect_tools": ["search_products"], "must_contain": ["esgotado"]}

    failures = check_answer(case, [], ["Temos sim!"])

    assert len(failures) == 2


def test_text_checks_ignore_accents_and_case():
    case = {"must_contain": ["ESGOTADO"], "must_not_contain": ["paris"]}

    assert check_answer(case, [], ["Está esgotádo"]) == []
    assert check_answer(case, [], ["Paris", "Esgotado"]) == ["answer should not contain 'paris'"]


def test_unexpected_tools_fail_no_tool_cases():
    assert check_answer({"expect_no_tools": True}, ["get_order_status"], ["ok"])


def test_any_of_several_wordings_is_accepted():
    case = {"must_contain_any": ["fechado", "não abrimos"]}

    assert check_answer(case, [], ["Não abrimos aos domingos"]) == []
    assert check_answer(case, [], ["Abrimos sim!"]) == [
        "answer has none of ['fechado', 'não abrimos']"
    ]
