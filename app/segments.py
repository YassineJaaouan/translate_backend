from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from .models import ASRResult


def _join(a: str, b: str) -> str:
    return f"{a} {b}".strip() if a else b


@dataclass
class Segment:
    id: str
    committed: str = ""   # morceaux is_final : STABLES, ne changent plus
    partial: str = ""     # fin de phrase encore modifiable par l'ASR
    translation: str = ""
    translation_src: str = ""      # texte arabe qui a produit `fr`
    closed: bool = False
    asr_ms: int | None = None
    tr_ms: int | None = None

    @property
    def state(self) -> str:
        return "final" if self.closed and self.translation and self.translation_src == self.full_text else (
            "closed" if self.closed else "partial")

    @property
    def full_text(self) -> str:
        return _join(self.committed, self.partial)

    @property
    def stable_words(self) -> int:
        return len(self.committed.split())


@dataclass
class SegUpdate:
    segment: Segment
    committed_grew: bool
    closed_now: bool


class SegmentManager:
    """Regroupe les résultats ASR en segments cohérents.

    - is_final        -> le texte rejoint `committed` (stable)
    - partial         -> remplace `partial` (instable)
    - speech_final    -> le segment est clos ; le suivant en ouvre un nouveau
    """

    def __init__(self, history: int = 5) -> None:
        self.current: Segment | None = None
        self._history: deque[Segment] = deque(maxlen=history)
        self._n = 0

    def on_asr(self, r: ASRResult) -> SegUpdate | None:
        if self.current is None:
            if not r.text:
                return None  # fin d'énoncé sans segment ouvert (ex. UtteranceEnd tardif)
            self.current = Segment(id=f"s_{self._n:04d}")
            self._n += 1
        seg = self.current
        grew = False
        if r.text:
            if r.is_final:
                seg.committed = _join(seg.committed, r.text)
                seg.partial = ""
                grew = True
            else:
                seg.partial = r.text
        closed = False
        if r.speech_final:
            if seg.partial:  # sécurité : ne rien perdre
                seg.committed = _join(seg.committed, seg.partial)
                seg.partial = ""
                grew = True
            seg.closed = True
            self._history.append(seg)
            self.current = None
            closed = True
        return SegUpdate(seg, grew, closed)

    def context(self, exclude: str | None = None) -> list[tuple[str, str]]:
        return [(s.translation_src, s.translation) for s in self._history if s.translation and s.id != exclude]
