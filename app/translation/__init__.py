from ..config import Settings
from ..languages import Lang, same_language
from .base import TranslationProvider


def build_translator(s: Settings, src: Lang, tgt: Lang) -> TranslationProvider:
    if same_language(src, tgt):
        from .identity import IdentityTranslationProvider
        return IdentityTranslationProvider()
    if s.translation_provider == "llm":
        from .llm import LLMTranslationProvider
        if not s.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY manquante (ou TRANSLATION_PROVIDER=mock)")
        return LLMTranslationProvider(s.anthropic_api_key, s.llm_model, src, tgt, s.glossary)
    if s.translation_provider == "gemini":
        from .gemini import GeminiTranslationProvider
        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY manquante (ou TRANSLATION_PROVIDER=mock)")
        return GeminiTranslationProvider(s.gemini_api_key, s.gemini_model,
                                         s.gemini_fallback_model, src, tgt, s.glossary)
    if s.translation_provider == "mock":
        from .mock import MockTranslationProvider
        return MockTranslationProvider(tgt.code)
    raise ValueError(f"TRANSLATION_PROVIDER inconnu: {s.translation_provider}")
