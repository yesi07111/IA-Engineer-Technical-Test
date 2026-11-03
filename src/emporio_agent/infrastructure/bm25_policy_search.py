from collections.abc import Sequence

from rank_bm25 import BM25Okapi

from emporio_agent.domain.models import PolicySection
from emporio_agent.domain.text import split_into_keywords
from emporio_agent.ports.policy_search import PolicySearch

STEM_LENGTH = 5


def stem_keywords(text: str) -> list[str]:
    """Reduces each keyword to its first letters so word variations match.

    Truncation is a rough stemmer, but it works well for Portuguese:
    "devolver" and "devolução" both become "devol".

    Args:
        text: Any text.

    Returns:
        The stemmed keywords of the text.
    """
    return [word[:STEM_LENGTH] for word in split_into_keywords(text)]


class Bm25PolicySearch(PolicySearch):
    """Keyword search (BM25) over the sections of the policy manual."""

    def __init__(self, sections: Sequence[PolicySection]) -> None:
        """Indexes the sections.

        Args:
            sections: Sections of the manual, see split_policy_into_sections.

        Raises:
            ValueError: If there are no sections to index.
        """
        if not sections:
            raise ValueError("Bm25PolicySearch needs at least one section")
        self._sections = list(sections)
        # This is for giving the title more weight than the body, so it goes twice
        corpus = [stem_keywords(f"{s.title} {s.title} {s.text}") for s in self._sections]
        self._index = BM25Okapi(corpus)

    def search(self, question: str, limit: int = 3) -> Sequence[PolicySection]:
        """Searches the manual sections most related to a question.

        Args:
            question: Free text question, usually in Portuguese.
            limit: Max number of sections to return, at least 1.

        Returns:
            The best matching sections, best first. Empty when no word of the question
            appears in the manual.
        """
        keywords = stem_keywords(question)
        if not keywords:
            return []
        scores = self._index.get_scores(keywords)
        ranked = sorted(zip(scores, self._sections, strict=True), key=lambda pair: -pair[0])
        return [section for score, section in ranked[: max(limit, 1)] if score > 0]
