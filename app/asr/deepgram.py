from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import AsyncIterator
from urllib.parse import urlencode

import websockets
from websockets.exceptions import InvalidStatus

from ..models import ASRResult
from .base import ASRProvider

log = logging.getLogger("asr.deepgram")


class DeepgramProvider(ASRProvider):
    URL = "wss://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str, *, model: str = "nova-3", language: str = "ar",
                 sample_rate: int = 16000, endpointing_ms: int = 400,
                 utterance_end_ms: int = 1000, keyterms: list[str] | None = None) -> None:
        super().__init__()
        self._key = api_key
        self._model = model
        self._language = language
        self._rate = sample_rate
        self._endpointing = endpointing_ms
        self._utt_end = utterance_end_ms
        self._keyterms = keyterms or []
        self._audio: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=400)  # ~20 s à 50 ms/bloc
        self._out: asyncio.Queue[ASRResult | None] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._t0: float | None = None

    def _url(self) -> str:
        params: list[tuple[str, str | int]] = [
            ("model", self._model), ("language", self._language),
            ("encoding", "linear16"), ("sample_rate", self._rate), ("channels", 1),
            ("interim_results", "true"), ("punctuate", "true"),
            ("endpointing", self._endpointing), ("utterance_end_ms", self._utt_end),
        ]
        params += [("keyterm", k) for k in self._keyterms]
        return f"{self.URL}?{urlencode(params)}"

    async def start(self) -> None:
        if not self._key:
            raise RuntimeError("DEEPGRAM_API_KEY manquante")
        self._stopping = False
        self._task = asyncio.create_task(self._run())

    async def send_audio(self, pcm16: bytes) -> None:
        # File bornée : si la connexion est coupée trop longtemps, on perd l'audio le plus ancien.
        if self._audio.full():
            try:
                self._audio.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._audio.put_nowait(pcm16)

    async def results(self) -> AsyncIterator[ASRResult]:
        while True:
            item = await self._out.get()
            if item is None:
                return
            yield item

    async def stop(self) -> None:
        self._stopping = True
        if self._audio.full():
            self._audio.get_nowait()
        self._audio.put_nowait(None)  # signal -> CloseStream
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=4)
            except (asyncio.TimeoutError, Exception):
                self._task.cancel()
        await self._out.put(None)

    # ------------------------------------------------------------------
    async def _run(self) -> None:
        backoff = 1.0
        headers = {"Authorization": f"Token {self._key}"}
        while not self._stopping:
            try:
                await self._status("connecting")
                async with websockets.connect(
                    self._url(), additional_headers=headers,
                    ping_interval=20, ping_timeout=20, max_size=None,
                ) as ws:
                    backoff = 1.0
                    self._t0 = None
                    await self._status("listening")
                    sender = asyncio.create_task(self._sender(ws))
                    receiver = asyncio.create_task(self._receiver(ws))
                    done, pending = await asyncio.wait({sender, receiver},
                                                       return_when=asyncio.FIRST_COMPLETED)
                    if self._stopping and sender in done and receiver in pending:
                        try:  # laisse arriver les derniers résultats après CloseStream
                            await asyncio.wait_for(receiver, timeout=2)
                        except Exception:
                            pass
                    for t in (sender, receiver):
                        if not t.done():
                            t.cancel()
                    await asyncio.gather(sender, receiver, return_exceptions=True)
                    for t in done:
                        t.result()  # relève l'exception éventuelle
                    if not self._stopping:
                        raise ConnectionError("connexion fermée par le serveur")
            except asyncio.CancelledError:
                raise
            except InvalidStatus as exc:
                # Refus définitif (clé, solde, langue non supportée) : inutile de réessayer en boucle.
                code = exc.response.status_code
                if self._stopping:
                    break
                if code in (400, 401, 402, 403):
                    await self._status(
                        "error",
                        f"Deepgram a refusé la connexion (HTTP {code}) : vérifie la clé API, "
                        f"le solde et la langue «{self._language}».")
                    return
                log.warning("Deepgram refus HTTP %s (nouvel essai dans %.0fs)", code, backoff)
                await self._status("reconnecting", f"HTTP {code}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15.0)
            except Exception as exc:
                if self._stopping:
                    break
                log.warning("Deepgram déconnecté: %s (nouvel essai dans %.0fs)", exc, backoff)
                await self._status("reconnecting", str(exc))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15.0)

    async def _sender(self, ws) -> None:
        while True:
            chunk = await self._audio.get()
            if chunk is None:
                await ws.send(json.dumps({"type": "CloseStream"}))
                return
            if self._t0 is None:
                self._t0 = time.monotonic()
            await ws.send(chunk)

    async def _receiver(self, ws) -> None:
        async for msg in ws:
            if isinstance(msg, bytes):
                continue
            data = json.loads(msg)
            kind = data.get("type")
            if kind == "Results":
                alts = (data.get("channel") or {}).get("alternatives") or [{}]
                text = (alts[0].get("transcript") or "").strip()
                speech_final = bool(data.get("speech_final"))
                if not text and not speech_final:
                    continue
                latency = None
                if self._t0 is not None:
                    audio_end = float(data.get("start", 0)) + float(data.get("duration", 0))
                    latency = max(0, int((time.monotonic() - self._t0 - audio_end) * 1000))
                await self._out.put(ASRResult(text, bool(data.get("is_final")), speech_final, latency))
            elif kind == "UtteranceEnd":
                await self._out.put(ASRResult("", True, True))
