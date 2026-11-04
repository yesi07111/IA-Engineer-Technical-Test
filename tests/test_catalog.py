import pytest

from emporio_agent.application.presenters import format_brl
from emporio_agent.errors import InvalidRequestError


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Takamine GD20", "Takamine GD20 Dreadnought Natural"),
        ("takamine gd 20", "Takamine GD20 Dreadnought Natural"),
        ("martin d-28", "Martin D-28 Dreadnought Natural"),
        ("MARTIN D28E", "Martin D-28E Elétrico Aço Natural"),
        ("fender strato", "Fender Stratocaster American Pro II"),
        ("yamaha c 40", "Yamaha C40 Nylon Natural"),
    ],
)
def test_finds_products_despite_typing_differences(catalog, query, expected):
    answer = catalog.describe_product(query)

    assert answer["result"] == "found"
    assert answer["product"]["name"] == expected


def test_vague_name_asks_which_one(catalog):
    answer = catalog.describe_product("yamaha")

    assert answer["result"] == "ambiguous"
    assert len(answer["candidates"]) > 1


def test_unknown_product_returns_closest_names(catalog):
    answer = catalog.describe_product("xyz qwerty")

    assert answer["result"] == "not_found"
    assert answer["closest_names"]


def test_empty_name_is_rejected(catalog):
    with pytest.raises(InvalidRequestError):
        catalog.describe_product("   ")


def test_promotion_price_is_shown_with_original_price(catalog):
    price = catalog.describe_product("Crafter HT-100")["product"]["price"]

    assert price["list_price"] == "R$ 2.399,00"
    assert price["promotion"]["discount"] == "18%"
    assert price["promotion"]["price"] == "R$ 1.967,18"
    assert "sem desconto extra" in price["pix_price"]


def test_inactive_promotion_is_ignored(catalog):
    price = catalog.describe_product("Takamine GD20")["product"]["price"]

    assert "promotion" not in price
    assert price["pix_price"].startswith("R$ 2.089,05")


def test_sold_out_product_comes_with_alternatives(catalog):
    product = catalog.describe_product("Giannini GF-3D")["product"]

    assert product["availability"] == "esgotado"
    assert product["similar_available"]
    assert all(p["availability"] != "esgotado" for p in product["similar_available"])


def test_search_by_category_and_budget_is_cheapest_first(catalog):
    result = catalog.search_products(category="violões", max_price=1000, limit=15)

    names = [p["name"] for p in result["products"]]
    assert "Giannini GF-3D Dreadnought Sunburst" not in names  # sold out
    assert "Shelby SN-7C 7 Cordas Nylon Natural" not in names  # discontinued
    assert result["total_found"] == len(names)
    assert names[0] == "Tagima Memphis AC-39 Nylon Natural"


def test_category_name_ignores_accents_and_plural(catalog):
    assert catalog.search_products(category="Ukulele")["total_found"] == 14


def test_budget_uses_the_promotion_price(catalog):
    # The Crafter HT-100 costs 2399, but 1967.18 with its promotion
    result = catalog.search_products(text="crafter", max_price=2000)

    assert [p["name"] for p in result["products"]] == ["Crafter HT-100 Folk Aço Natural"]


def test_text_filter_looks_into_specs(catalog):
    result = catalog.search_products(text="nylon", category="violões", limit=15)

    assert result["total_found"] > 0
    assert all("Aço" not in p["name"] for p in result["products"])


def test_unknown_category_lists_the_valid_ones(catalog):
    with pytest.raises(InvalidRequestError, match="Valid categories"):
        catalog.search_products(category="acessórios")


@pytest.mark.parametrize(
    ("min_price", "max_price"),
    [(-1, None), (None, -5), (500, 100)],
)
def test_bad_price_filters_are_rejected(catalog, min_price, max_price):
    with pytest.raises(InvalidRequestError):
        catalog.search_products(min_price=min_price, max_price=max_price)


def test_limit_is_kept_between_1_and_15(catalog):
    assert catalog.search_products(limit=0)["showing"] == 1
    assert catalog.search_products(limit=500)["showing"] == 15


def test_active_promotions_have_both_prices(catalog):
    promotions = catalog.list_active_promotions()

    assert len(promotions) == 4
    assert all(p["list_price"] != p["promotion_price"] for p in promotions)


def test_categories_show_available_counts(catalog):
    counts = {c["category"]: c["available_products"] for c in catalog.list_categories()}

    assert counts["Cordas Orquestrais"] == 0
    assert counts["Violões"] == 33


def test_brl_format():
    assert format_brl(1967.18) == "R$ 1.967,18"
    assert format_brl(159.9) == "R$ 159,90"
    assert format_brl(19567) == "R$ 19.567,00"


def test_steel_strings_are_found_even_when_only_the_specs_say_it(catalog):
    result = catalog.search_products(text="aço", category="violões", max_price=1000, limit=15)

    names = [p["name"] for p in result["products"]]
    assert "Tagima Woodstock Dreadnought Natural" in names
    assert all(p["strings"] == "aço" for p in result["products"])


def test_search_results_show_strings_and_electric_flag(catalog):
    product = catalog.describe_product("Shelby SGD-195E")["product"]

    assert product["strings"] == "aço"
    assert product["electric"] is True
