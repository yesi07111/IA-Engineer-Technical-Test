from typing import Any

from emporio_agent.domain.models import OrderStatus, Product, ProductStatus
from emporio_agent.domain.pricing import PriceQuote

LOW_STOCK_LIMIT = 3

ORDER_STATUS_PT = {
    OrderStatus.PENDING: "aguardando pagamento",
    OrderStatus.CONFIRMED: "pagamento confirmado, em preparação",
    OrderStatus.SHIPPED: "enviado",
    OrderStatus.DELIVERED: "entregue",
    OrderStatus.CANCELLED: "cancelado",
}

PAYMENT_METHOD_PT = {
    "pix": "PIX",
    "debit": "cartão de débito",
    "boleto": "boleto bancário",
}


def format_brl(amount: float) -> str:
    """Formats a value as Brazilian currency.

    Args:
        amount: Value in BRL.

    Returns:
        Text like "R$ 1.967,18".
    """
    us_style = f"{amount:,.2f}"
    return "R$ " + us_style.replace(",", "_").replace(".", ",").replace("_", ".")


def describe_payment_method(code: str) -> str:
    """Translates a payment method code into Portuguese.

    Args:
        code: Code from the orders table, e.g. "pix" or "credit_6x".

    Returns:
        A readable label, e.g. "cartão de crédito em 6x". Unknown codes come back as they are.
    """
    if code.startswith("credit_"):
        return f"cartão de crédito em {code.removeprefix('credit_')}"
    return PAYMENT_METHOD_PT.get(code, code)


def describe_availability(product: Product) -> str:
    """Explains in Portuguese whether a product can be bought.

    Args:
        product: Any product.

    Returns:
        One of "disponível", "últimas unidades", "esgotado", "descontinuado" or "em breve".
    """
    if product.status is ProductStatus.DISCONTINUED:
        return "descontinuado"
    if product.status is ProductStatus.COMING_SOON:
        return "em breve"
    if product.stock_quantity == 0:
        return "esgotado"
    if product.stock_quantity <= LOW_STOCK_LIMIT:
        return "últimas unidades"
    return "disponível"


def present_price(quote: PriceQuote) -> dict[str, Any]:
    """Turns a price quote into the compact format the agent reads.

    Args:
        quote: Quote from the PriceCalculator.

    Returns:
        A dict with formatted prices. Promotion fields only appear when there is one.
    """
    price: dict[str, Any] = {"list_price": format_brl(quote.list_price)}
    if quote.promotion_price is not None:
        price["promotion"] = {
            "name": quote.promotion_name,
            "discount": f"{quote.promotion_percent:g}%",
            "price": format_brl(quote.promotion_price),
        }
        price["pix_price"] = f"{format_brl(quote.pix_price)} (sem desconto extra no PIX)"
    else:
        price["pix_price"] = f"{format_brl(quote.pix_price)} (5% de desconto no PIX)"
    price["installments"] = (
        f"até {quote.max_installments}x de {format_brl(quote.installment_value)} sem juros"
    )
    return price


def present_product(
    product: Product, category_name: str, quote: PriceQuote, with_details: bool = False
) -> dict[str, Any]:
    """Turns a product into the compact format the agent reads.

    Args:
        product: The product.
        category_name: Name of its category.
        quote: Its price quote.
        with_details: Also include description and specs, used for single product answers.

    Returns:
        A dict with id, name, category, availability, stock and prices.
    """
    summary: dict[str, Any] = {
        "id": product.id,
        "name": product.name,
        "category": category_name,
        "availability": describe_availability(product),
        "stock": product.stock_quantity,
        "price": present_price(quote),
    }
    if with_details:
        summary["description"] = product.description
        summary["specs"] = product.specs
    return summary
