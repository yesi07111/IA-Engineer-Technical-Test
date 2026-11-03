from pathlib import Path

import pytest

from emporio_agent.errors import DataLoadError
from emporio_agent.infrastructure.bm25_policy_search import Bm25PolicySearch
from emporio_agent.infrastructure.policy_pdf import split_policy_into_sections

POLICY_PDF = Path(__file__).resolve().parents[1] / "data" / "store_policies.pdf"


@pytest.fixture(scope="module")
def sections():
    return split_policy_into_sections(POLICY_PDF)


@pytest.fixture(scope="module")
def policy_search(sections):
    return Bm25PolicySearch(sections)


def test_manual_is_split_by_numbered_sections(sections):
    numbers = [section.number for section in sections]

    assert numbers[0] == "1"
    assert {"2", "3.1", "4.1", "5.2", "7.3", "8.1", "10"} <= set(numbers)
    assert len(numbers) == len(set(numbers))


def test_numbered_lists_are_not_taken_as_sections(sections):
    flow = next(section for section in sections if section.number == "7.2")

    assert "Saudação" in flow.text


def test_tables_keep_their_columns(sections):
    company = next(section for section in sections if section.number == "1.2")

    assert "Endereço | Rua 14 de Maio, 3200" in company.text


@pytest.mark.parametrize(
    ("question", "expected_section"),
    [
        ("Me arrependi da minha compra, posso devolver meu pedido?", "4.1"),
        ("Qual o endereço da loja?", "1.2"),
        ("Que horas vocês abrem no sábado?", "2"),
        ("Posso parcelar em quantas vezes?", "3.1"),
        ("Meu violão veio com defeito", "4.2"),
        ("Como rastreio meu pedido?", "5.3"),
        ("Posso trocar por outra cor?", "4.3"),
    ],
)
def test_common_questions_find_the_right_section(policy_search, question, expected_section):
    found = [section.number for section in policy_search.search(question)]

    assert expected_section in found


def test_question_without_known_words_returns_nothing(policy_search):
    assert policy_search.search("???") == []


def test_search_needs_sections():
    with pytest.raises(ValueError):
        Bm25PolicySearch([])


def test_missing_pdf_is_a_data_error(tmp_path):
    with pytest.raises(DataLoadError):
        split_policy_into_sections(tmp_path / "missing.pdf")


def test_limit_is_respected(policy_search):
    assert len(policy_search.search("pedido produto loja", limit=1)) == 1
