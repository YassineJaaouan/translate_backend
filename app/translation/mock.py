from __future__ import annotations
import asyncio
from .base import TranslationProvider


class MockTranslationProvider(TranslationProvider):
    def __init__(self, tgt_code: str = "fr") -> None:
        self._tgt = tgt_code

    async def translate(self, text, context, *, previous=None, final=False) -> str:
        await asyncio.sleep(0.25)
        n = len(text.split())
        self._report("mock", n * 2, n * 2)
        return f"[{self._tgt.upper()} simulé · {n} mots] {text}"
