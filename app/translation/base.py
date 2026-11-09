from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable

# (modèle, tokens d'entrée, tokens de sortie) -> None
UsageCallback = Callable[[str, int, int], None]


class TranslationProvider(ABC):
    on_usage: UsageCallback | None = None

    def _report(self, model: str, tokens_in: int, tokens_out: int) -> None:
        if self.on_usage:
            self.on_usage(model, tokens_in or 0, tokens_out or 0)

    @abstractmethod
    async def translate(self, text: str, context: list[tuple[str, str]], *,
                        previous: str | None = None, final: bool = False) -> str:
        """text     : texte source à traduire (toujours le segment depuis son début)
        context  : phrases précédentes [(source, traduction)] pour la cohérence
        previous : traduction déjà affichée pour le début de ce segment (à conserver)
        final    : le segment est terminé."""
