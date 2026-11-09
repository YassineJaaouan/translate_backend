from __future__ import annotations
import time
from dataclasses import dataclass, field


@dataclass
class ASRResult:
    """Résultat normalisé, indépendant du fournisseur.

    is_final      : ce morceau de texte est stable (ne changera plus).
    speech_final  : fin d'énoncé détectée (silence) -> on ferme le segment.
    latency_ms    : délai estimé entre la fin de l'audio et la réception du résultat.
    """
    text: str
    is_final: bool
    speech_final: bool = False
    latency_ms: int | None = None
    ts: float = field(default_factory=time.monotonic)
