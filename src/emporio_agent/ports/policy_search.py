from abc import ABC, abstractmethod
from collections.abc import Sequence

from emporio_agent.domain.models import PolicySection


class PolicySearch(ABC):
    """Finds the parts of the store policy manual that answer a question."""

    @abstractmethod
    def search(self, question: str, limit: int = 3) -> Sequence[PolicySection]:
        """Searches the manual sections most related to a question.

        Args:
            question: Free text question, usually in Portuguese.
            limit: Max number of sections to return.

        Returns:
            The best matching sections, best first. Empty when nothing matches.
        """
