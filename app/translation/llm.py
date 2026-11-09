from __future__ import annotations
from anthropic import AsyncAnthropic
from ..languages import Lang
from .base import TranslationProvider
from .prompts import build_prompt, system_prompt


class LLMTranslationProvider(TranslationProvider):
    def __init__(self, api_key: str, model: str, src: Lang, tgt: Lang,
                 glossary: list[str] | None = None):
        self._client = AsyncAnthropic(api_key=api_key, timeout=10.0)
        self._model = model
        self._system = system_prompt(src, tgt, glossary)

    async def translate(self, text, context, *, previous=None, final=False) -> str:
        resp = await self._client.messages.create(
            model=self._model, max_tokens=400, temperature=0,
            system=self._system,
            messages=[{"role": "user", "content": build_prompt(text, context, previous)}],
        )
        usage = getattr(resp, "usage", None)
        if usage:
            self._report(self._model, usage.input_tokens, usage.output_tokens)
        return "".join(b.text for b in resp.content if b.type == "text").strip()
