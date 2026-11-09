from __future__ import annotations
import asyncio
from typing import AsyncIterator
from ..models import ASRResult
from .base import ASRProvider

# Rejoue des résultats de type Deepgram, pour tester l'UI et l'overlay sans micro ni clé.
SCRIPT: list[tuple[float, str, bool, bool]] = [
    (0.6, "نحن اليوم", False, False),
    (0.5, "نحن اليوم هنا", False, False),
    (0.5, "نحن اليوم هنا من أجل", False, False),
    (0.4, "نحن اليوم هنا من أجل", True, False),
    (0.5, "هذا", False, False),
    (0.5, "هذا اللقاء", False, False),
    (0.4, "هذا اللقاء", True, True),
    (2.5, "نشكركم جميعا", False, False),
    (0.5, "نشكركم جميعا على حضوركم", False, False),
    (0.5, "نشكركم جميعا على حضوركم", True, True),
]


class FakeProvider(ASRProvider):
    needs_audio = False

    def __init__(self) -> None:
        super().__init__()
        self._task: asyncio.Task | None = None
        self._out: asyncio.Queue[ASRResult | None] = asyncio.Queue()

    async def start(self) -> None:
        await self._status("listening", "mode démo")
        self._task = asyncio.create_task(self._play())

    async def _play(self) -> None:
        while True:
            for delay, text, fin, sf in SCRIPT:
                await asyncio.sleep(delay)
                await self._out.put(ASRResult(text, fin, sf, latency_ms=400))
            await asyncio.sleep(4)

    async def send_audio(self, pcm16: bytes) -> None:
        pass

    async def results(self) -> AsyncIterator[ASRResult]:
        while True:
            item = await self._out.get()
            if item is None:
                return
            yield item

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        await self._out.put(None)
