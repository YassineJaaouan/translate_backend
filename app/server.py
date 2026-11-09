from __future__ import annotations
import hmac
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .audio.remote import RemoteAudioSource
from fastapi.responses import HTMLResponse

from .bus import Broadcaster
from .languages import SOURCES, TARGETS, to_json
from .config import Settings
from .pipeline import Pipeline

settings = Settings.load()
logging.basicConfig(level=settings.log_level,
                    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
bus = Broadcaster()
pipeline = Pipeline(settings, bus)
app = FastAPI(title="Live subtitles")

OVERLAY = Path(__file__).parent / "overlay.html"


def _eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def authorized(ws: WebSocket) -> bool:
    """Jeton d'accès (?token=...). Sans ACCESS_TOKEN configuré : accès libre (usage local)."""
    if not settings.access_token:
        return True
    return _eq(ws.query_params.get("token", ""), settings.access_token)


def is_admin(ws: WebSocket) -> bool:
    if not settings.admin_token:
        return True
    return _eq(ws.query_params.get("admin", ""), settings.admin_token)


def languages_event() -> dict:
    return {"type": "languages",
            "source": [to_json(l) for l in SOURCES],
            "target": [to_json(l) for l in TARGETS],
            "default_source": settings.language,
            "default_target": settings.target_language,
            "audio_source": settings.audio_source}


@app.get("/health")
async def health():
    return {"state": pipeline.state}


@app.get("/overlay", response_class=HTMLResponse)
async def overlay():
    return OVERLAY.read_text(encoding="utf-8")


@app.websocket("/audio")
async def audio(ws: WebSocket):
    """L'application envoie ici l'audio du micro : trames binaires PCM16 mono 16 kHz."""
    if not authorized(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    try:
        while True:
            data = await ws.receive_bytes()
            src = pipeline.mic
            if isinstance(src, RemoteAudioSource):
                src.push(data)
    except WebSocketDisconnect:
        pass


@app.websocket("/subtitles")
async def subtitles(ws: WebSocket):
    if not authorized(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    bus.overlay.add(ws)
    try:
        while True:
            await ws.receive_text()  # l'overlay n'envoie rien ; détecte la déconnexion
    except WebSocketDisconnect:
        pass
    finally:
        bus.overlay.discard(ws)


@app.websocket("/control")
async def control(ws: WebSocket):
    if not authorized(ws):
        await ws.close(code=4401)
        return
    admin = is_admin(ws)
    await ws.accept()
    bus.control.add(ws)
    await ws.send_json({"type": "status", "state": pipeline.state, "detail": ""})
    await ws.send_json(languages_event())
    if pipeline.src and pipeline.state not in ("idle", "error"):
        await ws.send_json(pipeline.session_event())
    await ws.send_json(pipeline.usage.snapshot())
    try:
        while True:
            msg = await ws.receive_json()
            cmd = msg.get("cmd")
            if cmd == "start":
                await pipeline.start(msg.get("device"), msg.get("source_lang"), msg.get("target_lang"))
            elif cmd == "stop":
                await pipeline.stop()
            elif cmd == "languages":
                await ws.send_json(languages_event())
            elif cmd == "usage":
                await ws.send_json(pipeline.usage.snapshot())
            elif cmd == "set_budget":
                if not admin:
                    await ws.send_json({"type": "log", "level": "warning",
                                        "message": "Modification de la limite réservée à l'administrateur"})
                    continue
                try:
                    pipeline.set_budget(float(msg.get("usd", 0)))
                except (TypeError, ValueError):
                    await ws.send_json({"type": "log", "level": "warning",
                                        "message": "Montant de budget invalide"})
                await bus.emit(pipeline.usage.snapshot())
            elif cmd == "devices":
                if settings.audio_source == "remote":
                    await ws.send_json({"type": "devices", "devices": []})
                    continue
                try:
                    from .audio.mic import list_input_devices
                    await ws.send_json({"type": "devices", "devices": list_input_devices()})
                except Exception as exc:
                    await ws.send_json({"type": "log", "level": "error",
                                        "message": f"Liste des périphériques impossible: {exc}"})
            else:
                await ws.send_json({"type": "log", "level": "warning",
                                    "message": f"Commande inconnue: {cmd}"})
    except WebSocketDisconnect:
        pass
    finally:
        bus.control.discard(ws)
