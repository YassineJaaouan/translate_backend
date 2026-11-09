from __future__ import annotations
from abc import ABC, abstractmethod
from typing import AsyncIterator, Awaitable, Callable
from ..models import ASRResult

StatusCallback = Callable[[str, str], Awaitable[None]]


class ASRProvider(ABC):
    """Contrat commun à tous les fournisseurs ASR (cloud ou local)."""

    needs_audio: bool = True

    def __init__(self) -> None:
        self.on_status: StatusCallback | None = None

    async def _status(self, state: str, detail: str = "") -> None:
        if self.on_status:
            await self.on_status(state, detail)

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def send_audio(self, pcm16: bytes) -> None:
        """PCM 16 bits little-endian, mono, à la fréquence configurée."""

    @abstractmethod
    def results(self) -> AsyncIterator[ASRResult]: ...

    @abstractmethod
    async def stop(self) -> None: ...
