import re
from typing import Any

from rapidfuzz import fuzz, process

from emporio_agent.application.presenters import format_brl, present_product
from emporio_agent.domain.models import Category, Product
from emporio_agent.domain.pricing import PriceCalculator, PriceQuote
from emporio_agent.domain.text import normalize_text, split_into_keywords
from emporio_agent.errors import InvalidRequestError
from emporio_agent.ports.repositories import (
    CategoryRepository,
    ProductRepository,
    PromotionRepository,
)

MATCH_THRESHOLD = 85
AMBIGUITY_MARGIN = 4
MAX_RESULTS = 15


def prepare_product_name(text: str) -> str:
    """Normalizes a product name so model codes compare well.

    Args:
        text: Product name or what the customer typed.

    Returns:
        Lowercase text without accents where "D-28" and "gd 20" become "d28" and "gd20".
    """
    text = normalize_text(text)
    text = re.sub(r"(?<=[a-z0-9])-(?=[a-z0-9])", "", text)
    # This is for gluing short model prefixes to their number, "gd 20" is the same as "gd20"
    text = re.sub(r"\b([a-z]{1,3}) (\d)", r"\1\2", text)
    return re.sub(r"[^a-z0-9 ]", " ", text)


def score_product_name(query: str, name: str, **_: object) -> float:
    """Scores how well a query matches a product name, from 0 to 100.

    Args:
        query: Prepared query, see prepare_product_name.
        name: Prepared product name.
        **_: Extra arguments rapidfuzz passes to scorers, not used.

    Returns:
        100 when every word of the query is in the name. Partial matches like
        "strato" for "Stratocaster" get a slightly lower score.
    """
    return max(fuzz.token_set_ratio(query, name), 0.9 * fuzz.partial_ratio(query, name))


class CatalogService:
    """Answers questions about products, prices, stock and promotions."""

    def __init__(
        self,
        products: ProductRepository,
        categories: CategoryRepository,
        promotions: PromotionRepository,
        price_calculator: PriceCalculator,
    ) -> None:
        """Keeps the repositories the service reads from.

        Args:
            products: Product catalog.
            categories: Product categories.
            promotions: Promotions, only active ones are used.
            price_calculator: Rules to build each price quote.
        """
        self._products = products
        self._categories = {category.id: category for category in categories.list_all()}
        self._promotions = promotions
        self._prices = price_calculator

    def search_products(
        self,
        text: str | None = None,
        category: str | None = None,
        max_price: float | None = None,
        min_price: float | None = None,
        only_available: bool = True,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Searches the catalog with optional filters, cheapest first.

        Prices are compared with what the customer pays by card, so a product on
        promotion counts with its promotion price.

        Args:
            text: Words that must appear in the name, description or specs, e.g. "nylon".
            category: Category name, accents and plural are ignored, e.g. "violao".
            max_price: Highest price in BRL.
            min_price: Lowest price in BRL.
            only_available: Hide products that are sold out, discontinued or coming soon.
            limit: Max number of products to return, between 1 and 15.

        Returns:
            A dict with the total found and the products of the page.

        Raises:
            InvalidRequestError: If a price is negative, the range is inverted or the
                category does not exist.
        """
        self._check_price_range(min_price, max_price)
        category_filter = self._find_category(category) if category else None
        keywords = split_into_keywords(text or "")

        found = []
        for product in self._products.list_all():
            if only_available and not product.is_available:
                continue
            if category_filter and product.category_id != category_filter.id:
                continue
            if keywords and not self._has_all_keywords(product, keywords):
                continue
            quote = self.quote_product(product)
            if max_price is not None and quote.final_price > max_price:
                continue
            if min_price is not None and quote.final_price < min_price:
                continue
            found.append((quote.final_price, product, quote))

        found.sort(key=lambda entry: entry[0])
        page = found[: max(1, min(limit, MAX_RESULTS))]
        return {
            "total_found": len(found),
            "showing": len(page),
            "products": [self._present(product, quote) for _, product, quote in page],
        }

    def describe_product(self, name: str) -> dict[str, Any]:
        """Finds one product by name, tolerating typos, and gives all its details.

        Args:
            name: Product name as the customer wrote it, e.g. "takamine gd 20".

        Returns:
            One of three shapes, told apart by "result":
            "found" with the product, "ambiguous" with candidates to ask the customer
            about, or "not_found" with the closest names.

        Raises:
            InvalidRequestError: If the name is empty.
        """
        if not name or not name.strip():
            raise InvalidRequestError("Product name is empty, ask the customer which product.")

        by_name = {product.name: product for product in self._products.list_all()}
        matches = process.extract(
            name, list(by_name), scorer=score_product_name, processor=prepare_product_name, limit=5
        )
        best_name, best_score, _ = matches[0]
        close_ones = [match for match in matches if best_score - match[1] <= AMBIGUITY_MARGIN]

        if best_score < MATCH_THRESHOLD:
            return {"result": "not_found", "closest_names": [match[0] for match in matches[:3]]}
        if len(close_ones) > 1:
            return {"result": "ambiguous", "candidates": [match[0] for match in close_ones]}

        product = by_name[best_name]
        details = self._present(product, self.quote_product(product), with_details=True)
        if not product.is_available:
            details["similar_available"] = self._find_alternatives(product)
        return {"result": "found", "product": details}

    def list_active_promotions(self) -> list[dict[str, Any]]:
        """Lists the promotions running now with the promotional price of each product.

        Returns:
            One entry per active promotion of a product that still exists.
        """
        entries = []
        for promotion in self._promotions.list_active():
            product = self._products.get_by_id(promotion.product_id)
            if product is None:
                continue
            quote = self.quote_product(product)
            entries.append(
                {
                    "promotion": promotion.description,
                    "discount": f"{promotion.discount_percent:g}%",
                    "product": product.name,
                    "list_price": format_brl(quote.list_price),
                    "promotion_price": format_brl(quote.final_price),
                    "availability": self._present(product, quote)["availability"],
                }
            )
        return entries

    def list_categories(self) -> list[dict[str, Any]]:
        """Lists the categories with how many products can be bought in each one.

        Returns:
            Name, description and available product count per category.
        """
        available = [product for product in self._products.list_all() if product.is_available]
        return [
            {
                "category": category.name,
                "description": category.description,
                "available_products": sum(1 for p in available if p.category_id == category.id),
            }
            for category in self._categories.values()
        ]

    def quote_product(self, product: Product) -> PriceQuote:
        """Builds the price quote of a product with its active promotions.

        Args:
            product: Any product.

        Returns:
            The price quote.
        """
        return self._prices.quote(product, self._promotions.list_active_for_product(product.id))

    def _present(
        self, product: Product, quote: PriceQuote, with_details: bool = False
    ) -> dict[str, Any]:
        """Shortcut to present a product with its category name.

        Args:
            product: The product.
            quote: Its price quote.
            with_details: Include description and specs.

        Returns:
            The product as a dict for the agent.
        """
        category = self._categories.get(product.category_id)
        category_name = category.name if category else "Sem categoria"
        return present_product(product, category_name, quote, with_details)

    def _find_category(self, name: str) -> Category:
        """Finds a category by name, ignoring accents, case and plural.

        Args:
            name: Category the customer mentioned, e.g. "violão" or "Ukulele".

        Returns:
            The matching category.

        Raises:
            InvalidRequestError: If no category is close enough. The message lists them all.
        """
        names = {category.name: category for category in self._categories.values()}
        match = process.extractOne(name, list(names), scorer=fuzz.WRatio, processor=normalize_text)
        if match is None or match[1] < MATCH_THRESHOLD:
            raise InvalidRequestError(
                f"Unknown category '{name}'. Valid categories: {', '.join(names)}"
            )
        return names[match[0]]

    @staticmethod
    def _check_price_range(min_price: float | None, max_price: float | None) -> None:
        """Validates the price filters.

        Args:
            min_price: Lowest price or None.
            max_price: Highest price or None.

        Raises:
            InvalidRequestError: If a price is negative or min is bigger than max.
        """
        for value in (min_price, max_price):
            if value is not None and value < 0:
                raise InvalidRequestError("Prices can not be negative.")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise InvalidRequestError("min_price is bigger than max_price.")

    @staticmethod
    def _has_all_keywords(product: Product, keywords: list[str]) -> bool:
        """Checks that every keyword appears somewhere in the product data.

        Args:
            product: Product to check.
            keywords: Normalized keywords.

        Returns:
            True when all of them appear in the name, description or specs.
        """
        searchable = normalize_text(
            f"{product.name} {product.description} {' '.join(product.specs.values())}"
        )
        return all(keyword in searchable for keyword in keywords)

    def _find_alternatives(self, product: Product, limit: int = 3) -> list[dict[str, Any]]:
        """Suggests available products of the same category with the closest price.

        Args:
            product: Product that can not be bought.
            limit: Max number of suggestions.

        Returns:
            Up to ``limit`` available products, closest price first.
        """
        candidates = [
            other
            for other in self._products.list_all()
            if other.is_available
            and other.category_id == product.category_id
            and other.id != product.id
        ]
        candidates.sort(key=lambda other: abs(other.price_brl - product.price_brl))
        return [self._present(other, self.quote_product(other)) for other in candidates[:limit]]
