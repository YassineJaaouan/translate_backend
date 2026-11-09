from __future__ import annotations
import asyncio
import json
import time
from fastapi import WebSocket


class Broadcaster:
    """Diffuse les événements vers Flutter (/control) et vers l'overlay OBS (/subtitles)."""

    def __init__(self) -> None:
        self.control: set[WebSocket] = set()
        self.overlay: set[WebSocket] = set()
        self.last_subtitle: dict | None = None

    async def _send(self, targets: set[WebSocket], msg: dict) -> None:
        payload = json.dumps(msg, ensure_ascii=False)
        for ws in list(targets):
            try:
                await asyncio.wait_for(ws.send_text(payload), timeout=1.0)
            except Exception:
                targets.discard(ws)

    async def emit(self, event: dict, *, overlay: bool = False) -> None:
        event.setdefault("ts", int(time.time() * 1000))
        if overlay:
            self.last_subtitle = event
            await self._send(self.overlay, event)
        await self._send(self.control, event)
