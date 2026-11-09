from __future__ import annotations
from .base import TranslationProvider


class IdentityTranslationProvider(TranslationProvider):
    """Langue parlée = langue des sous-titres : on affiche simplement la transcription."""

    async def translate(self, text, context, *, previous=None, final=False) -> str:
        return text
