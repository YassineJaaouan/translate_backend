from __future__ import annotations
import array
import asyncio
import math
from typing import AsyncIterator


class RemoteAudioSource:
    """Audio envoyé par l'application (WebSocket /audio) : PCM16 mono, 16 kHz.

    Même interface que MicSource, pour que le pipeline ne fasse pas la différence."""

    def __init__(self) -> None:
        self.level = 0.0
        self._q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=400)

    async def start(self) -> None:
        pass

    def push(self, data: bytes) -> None:
        samples = array.array("h")
        samples.frombytes(data[: len(data) // 2 * 2])
        if samples:
            rms = math.sqrt(sum(s * s for s in samples) / len(samples))
            self.level = min(1.0, rms / 8000)
        try:
            self._q.put_nowait(data)
        except asyncio.QueueFull:
            pass

    async def chunks(self) -> AsyncIterator[bytes]:
        while True:
            item = await self._q.get()
            if item is None:
                return
            yield item

    async def stop(self) -> None:
        try:
            self._q.put_nowait(None)
        except asyncio.QueueFull:
            pass
