from __future__ import annotations
import asyncio
from google import genai
from google.genai import types
from ..languages import Lang
from .base import TranslationProvider
from .prompts import build_prompt, system_prompt

RETRY_MARKERS = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")


class GeminiTranslationProvider(TranslationProvider):
    def __init__(self, api_key: str, model: str, fallback: str, src: Lang, tgt: Lang,
                 glossary: list[str] | None = None):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._fallback = fallback
        self._system = system_prompt(src, tgt, glossary)

    def _config(self, minimal_thinking: bool) -> types.GenerateContentConfig:
        kwargs = dict(system_instruction=self._system, max_output_tokens=800)
        if minimal_thinking:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="minimal")
        return types.GenerateContentConfig(**kwargs)

    async def translate(self, text, context, *, previous=None, final=False) -> str:
        prompt = build_prompt(text, context, previous)
        # 2 essais sur le modèle principal, puis 1 sur le modèle de secours
        attempts = [(self._model, True), (self._model, True)]
        if self._fallback and self._fallback != self._model:
            attempts.append((self._fallback, False))

        last_exc: Exception | None = None
        for model, minimal in attempts:
            try:
                resp = await self._client.aio.models.generate_content(
                    model=model, contents=prompt, config=self._config(minimal))
                um = getattr(resp, "usage_metadata", None)
                if um:
                    out = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
                    self._report(model, um.prompt_token_count or 0, out)
                return (resp.text or "").strip()
            except Exception as exc:
                last_exc = exc
                if not any(m in str(exc) for m in RETRY_MARKERS):
                    raise
                await asyncio.sleep(0.3)
        raise last_exc  # type: ignore[misc]
