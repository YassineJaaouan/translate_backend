from ..config import Settings
from .base import ASRProvider


def build_asr(s: Settings, language: str) -> ASRProvider:
    if s.asr_provider == "deepgram":
        from .deepgram import DeepgramProvider
        return DeepgramProvider(
            s.deepgram_api_key, model=s.deepgram_model, language=language,
            sample_rate=s.sample_rate, endpointing_ms=s.endpointing_ms,
            utterance_end_ms=s.utterance_end_ms, keyterms=s.keyterms,
        )
    if s.asr_provider == "fake":
        from .fake import FakeProvider
        return FakeProvider()
    raise ValueError(f"ASR_PROVIDER inconnu: {s.asr_provider}")
