import re

from unidecode import unidecode

PORTUGUESE_STOPWORDS = frozenset(
    "a o as os de da do das dos e em no na nos nas um uma para por com que se ao aos "
    "meu minha eu voce voces qual quais como posso pode ser tem".split()
)


def normalize_text(text: str) -> str:
    """Lowercases a text and removes accents so comparisons ignore them.

    Args:
        text: Any text.

    Returns:
        The same text in lowercase ASCII, e.g. "Violão" becomes "violao".
    """
    return unidecode(text).lower().strip()


def split_into_keywords(text: str) -> list[str]:
    """Splits a text into searchable words, dropping common Portuguese filler words.

    Args:
        text: Any text.

    Returns:
        Normalized words, in order, without stopwords.
    """
    words = re.findall(r"[a-z0-9]+", normalize_text(text))
    return [word for word in words if word not in PORTUGUESE_STOPWORDS]


def keep_only_digits(text: str) -> str:
    """Removes everything that is not a digit.

    Args:
        text: Usually a phone number like "(67) 99812-3456".

    Returns:
        Only the digits, e.g. "67998123456".
    """
    return re.sub(r"\D", "", text)
