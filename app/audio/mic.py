from __future__ import annotations
import array
import asyncio
import math
from typing import AsyncIterator


def list_input_devices() -> list[dict]:
    import sounddevice as sd
    hostapis = sd.query_hostapis()
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            out.append({
                "index": i,
                "name": d["name"],
                "host_api": hostapis[d["hostapi"]]["name"],
                "default": i == sd.default.device[0],
            })
    return out


class MicSource:
    """Capture micro / entrée ligne -> blocs PCM16 mono (50 ms par défaut)."""

    def __init__(self, device: int | None = None, sample_rate: int = 16000, block_ms: int = 50):
        self.device = device
        self.rate = sample_rate
        self.block = int(sample_rate * block_ms / 1000)
        self.level = 0.0  # 0..1, pour le vumètre
        self._q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream = None

    async def start(self) -> None:
        import sounddevice as sd
        self._loop = asyncio.get_running_loop()
        self._stream = sd.RawInputStream(
            samplerate=self.rate, channels=1, dtype="int16",
            blocksize=self.block, device=self.device, callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:  # thread PortAudio
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._push, bytes(indata))

    def _push(self, data: bytes) -> None:
        samples = array.array("h")
        samples.frombytes(data)
        if samples:
            rms = math.sqrt(sum(s * s for s in samples) / len(samples))
            self.level = min(1.0, rms / 8000)
        try:
            self._q.put_nowait(data)
        except asyncio.QueueFull:
            pass  # on préfère perdre un bloc plutôt que de bloquer la capture

    async def chunks(self) -> AsyncIterator[bytes]:
        while True:
            yield await self._q.get()

    async def stop(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
