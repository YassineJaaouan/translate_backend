from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Settings:
    asr_provider: str = "deepgram"
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-3"
    language: str = "ar"             # langue parlée par défaut (modifiable dans l'app)
    target_language: str = "fr"      # langue des sous-titres par défaut (modifiable dans l'app)
    sample_rate: int = 16000
    endpointing_ms: int = 400
    utterance_end_ms: int = 1000
    keyterms: list[str] = field(default_factory=list)

    translation_provider: str = "llm"
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    glossary: list[str] = field(default_factory=list)
    min_words_interim: int = 5

    # Budget et coûts
    budget_usd: float = 0.0              # 0 = pas de limite
    budget_warn_pct: float = 0.8
    deepgram_usd_per_min: float = 0.0077  # estimation prudente ; à vérifier chez Deepgram
    usage_file: str = "usage.json"
    notify_webhook_url: str = ""

    # Déploiement cloud
    audio_source: str = "local"   # local = micro de la machine | remote = audio envoyé par l'app
    access_token: str = ""        # vide = accès libre (usage local). OBLIGATOIRE sur Internet.
    admin_token: str = ""         # requis pour modifier la limite de budget (vide = tout le monde)

    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        e = os.environ.get
        glossary: list[str] = []
        gfile = Path(e("GLOSSARY_FILE", "glossary.txt"))
        if gfile.exists():
            glossary = [
                l.strip() for l in gfile.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.strip().startswith("#")
            ]
        return cls(
            asr_provider=e("ASR_PROVIDER", "deepgram"),
            deepgram_api_key=e("DEEPGRAM_API_KEY", ""),
            deepgram_model=e("DEEPGRAM_MODEL", "nova-3"),
            language=e("ASR_LANGUAGE", "ar"),
            target_language=e("TARGET_LANGUAGE", "fr"),
            endpointing_ms=int(e("ASR_ENDPOINTING_MS", "400")),
            utterance_end_ms=int(e("ASR_UTTERANCE_END_MS", "1000")),
            keyterms=_list(e("ASR_KEYTERMS", "")),
            translation_provider=e("TRANSLATION_PROVIDER", "llm"),
            anthropic_api_key=e("ANTHROPIC_API_KEY", ""),
            llm_model=e("LLM_MODEL", "claude-haiku-4-5-20251001"),
            gemini_api_key=e("GEMINI_API_KEY", ""),
            gemini_model=e("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            gemini_fallback_model=e("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite"),
            glossary=glossary,
            min_words_interim=int(e("MIN_WORDS_INTERIM", "5")),
            budget_usd=float(e("BUDGET_USD", "0")),
            budget_warn_pct=float(e("BUDGET_WARN_PCT", "0.8")),
            deepgram_usd_per_min=float(e("DEEPGRAM_USD_PER_MIN", "0.0077")),
            usage_file=e("USAGE_FILE", "usage.json"),
            notify_webhook_url=e("NOTIFY_WEBHOOK_URL", ""),
            audio_source=e("AUDIO_SOURCE", "local"),
            access_token=e("ACCESS_TOKEN", ""),
            admin_token=e("ADMIN_TOKEN", ""),
            host=e("HOST", "127.0.0.1"),
            port=int(e("PORT", "8765")),
            log_level=e("LOG_LEVEL", "INFO"),
        )
