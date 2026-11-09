from __future__ import annotations
import asyncio
import logging
import time

from .asr import build_asr
from .asr.base import ASRProvider
from .audio.mic import MicSource
from .audio.remote import RemoteAudioSource
from .bus import Broadcaster
from .config import Settings
from .languages import Lang, find_source, find_target, to_json
from .segments import Segment, SegmentManager
from .subtitle import to_lines
from .translation import build_translator
from .translation.base import TranslationProvider
from .usage import UsageMeter, send_webhook

log = logging.getLogger("pipeline")


class Pipeline:
    def __init__(self, settings: Settings, bus: Broadcaster) -> None:
        self.s = settings
        self.bus = bus
        self.state = "idle"
        self.asr: ASRProvider | None = None
        self.translator: TranslationProvider | None = None
        self.mic: MicSource | RemoteAudioSource | None = None
        self.segments = SegmentManager()
        self._tasks: list[asyncio.Task] = []
        self._tr_tasks: dict[str, asyncio.Task] = {}
        self._dirty: set[str] = set()
        self._last_asr_ms: int | None = None
        self.src: Lang | None = None
        self.tgt: Lang | None = None
        self.usage = UsageMeter(
            settings.usage_file, deepgram_usd_per_min=settings.deepgram_usd_per_min,
            budget_usd=settings.budget_usd, warn_pct=settings.budget_warn_pct)
        self._bg: set[asyncio.Task] = set()

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)

    # ---------------------------------------------------------------- état
    async def set_status(self, state: str, detail: str = "") -> None:
        self.state = state
        await self.bus.emit({"type": "status", "state": state, "detail": detail})

    async def log_event(self, level: str, message: str) -> None:
        getattr(log, level if level in ("info", "warning", "error") else "info")(message)
        await self.bus.emit({"type": "log", "level": level, "message": message})

    # ----------------------------------------------------------- start/stop
    async def start(self, device: int | None = None, source: str | None = None,
                    target: str | None = None) -> None:
        if self.state not in ("idle", "error"):
            return
        src = find_source(source or self.s.language)
        tgt = find_target(target or self.s.target_language)
        if not src or not tgt:
            await self.set_status("error", f"Langue non supportée : {source or ''} → {target or ''}")
            return
        if self.usage.exceeded:
            await self.set_status(
                "error", f"Budget mensuel atteint ({self.usage.spent_usd:.2f} $ / "
                         f"{self.usage.budget_usd:.2f} $). Augmente la limite pour continuer.")
            await self.bus.emit(self.usage.snapshot())
            return
        await self.set_status("starting")
        try:
            self.src, self.tgt = src, tgt
            self.segments = SegmentManager()
            self.translator = build_translator(self.s, src, tgt)
            self.translator.on_usage = self.usage.add_llm
            self.asr = build_asr(self.s, src.code)
            self.asr.on_status = self._on_asr_status
            await self.bus.emit(self.session_event())
            await self.asr.start()
            if self.asr.needs_audio:
                self.mic = (RemoteAudioSource() if self.s.audio_source == "remote"
                            else MicSource(device, self.s.sample_rate))
                await self.mic.start()
                self._tasks.append(asyncio.create_task(self._audio_loop()))
            self._tasks.append(asyncio.create_task(self._asr_loop()))
            self._tasks.append(asyncio.create_task(self._metrics_loop()))
        except Exception as exc:
            await self.log_event("error", f"Démarrage impossible: {exc}")
            await self._teardown()
            await self.set_status("error", str(exc))

    def session_event(self) -> dict:
        return {"type": "session",
                "source": to_json(self.src) if self.src else None,
                "target": to_json(self.tgt) if self.tgt else None}

    async def _on_asr_status(self, state: str, detail: str = "") -> None:
        if state == "error":  # erreur définitive côté ASR : on arrête proprement
            self._spawn(self._fail(detail))
            return
        await self.set_status(state, detail)

    async def _fail(self, detail: str) -> None:
        await self._teardown()
        await self.set_status("error", detail)

    async def stop(self) -> None:
        if self.state == "idle":
            return
        await self._teardown()
        await self.set_status("idle")

    async def _teardown(self) -> None:
        for t in self._tasks + list(self._tr_tasks.values()):
            t.cancel()
        await asyncio.gather(*self._tasks, *self._tr_tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._tr_tasks.clear()
        self._dirty.clear()
        if self.mic:
            await self.mic.stop()
            self.mic = None
        if self.asr:
            await self.asr.stop()
            self.asr = None
        self.usage.save(force=True)

    # ---------------------------------------------------------------- boucles
    async def _audio_loop(self) -> None:
        assert self.mic and self.asr
        bytes_per_sec = 2 * self.s.sample_rate  # PCM 16 bits mono
        async for chunk in self.mic.chunks():
            self.usage.add_audio(len(chunk) / bytes_per_sec)
            await self.asr.send_audio(chunk)

    async def _metrics_loop(self) -> None:
        tick = 0
        while True:
            await asyncio.sleep(0.5)
            tick += 1
            await self.bus.emit({
                "type": "metrics",
                "mic_level": round(self.mic.level, 3) if self.mic else None,
                "asr_ms": self._last_asr_ms,
            })
            if tick % 4 == 0:  # toutes les 2 s
                await self.check_budget()

    # ---------------------------------------------------------------- budget
    async def check_budget(self) -> None:
        await self.bus.emit(self.usage.snapshot())
        alert = self.usage.pop_new_alert()
        if not alert:
            return
        u = self.usage
        if alert == "warning":
            msg = (f"⚠️ Sous-titres : {u.spent_usd:.2f} $ dépensés sur {u.budget_usd:.2f} $ "
                   f"({int(self.s.budget_warn_pct * 100)} % du budget mensuel).")
            await self.log_event("warning", msg)
        else:
            msg = (f"⛔ Sous-titres arrêtés : budget mensuel de {u.budget_usd:.2f} $ atteint "
                   f"({u.spent_usd:.2f} $).")
            await self.log_event("error", msg)
            await self.bus.emit({"type": "budget.exceeded", "message": msg})
            self._spawn(self._budget_stop(msg))
        self._spawn(send_webhook(self.s.notify_webhook_url, msg))

    async def _budget_stop(self, msg: str) -> None:
        await self._teardown()
        await self.set_status("error", msg)

    def set_budget(self, usd: float) -> None:
        self.usage.set_budget(usd)

    async def _asr_loop(self) -> None:
        assert self.asr
        async for r in self.asr.results():
            upd = self.segments.on_asr(r)
            if upd is None:
                continue
            seg = upd.segment
            if r.latency_ms is not None:
                seg.asr_ms = self._last_asr_ms = r.latency_ms
            await self._emit_segment(seg)  # texte arabe : immédiat, côté Flutter uniquement
            if upd.closed_now:
                self._request_translation(seg, final=True)
            elif upd.committed_grew and seg.stable_words >= self.s.min_words_interim:
                self._request_translation(seg, final=False)

    # ------------------------------------------------------------ traduction
    def _request_translation(self, seg: Segment, *, final: bool) -> None:
        prev = self._tr_tasks.get(seg.id)
        if prev and not prev.done():
            if not final:
                self._dirty.add(seg.id)  # une seule requête en vol ; on relancera avec le texte à jour
                return
            prev.cancel()  # le final couvre tout le segment
        self._tr_tasks[seg.id] = asyncio.create_task(self._translate(seg, final))

    async def _translate(self, seg: Segment, final: bool) -> None:
        assert self.translator
        while True:
            self._dirty.discard(seg.id)
            src = seg.full_text if final else seg.committed
            if not src:
                return
            previous = seg.translation if seg.translation and src.startswith(seg.translation_src) else None
            t0 = time.monotonic()
            try:
                out = await self.translator.translate(
                    src, self.segments.context(exclude=seg.id), previous=previous, final=final)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.log_event("error", f"Traduction échouée ({seg.id}): {exc}")
                return
            seg.tr_ms = int((time.monotonic() - t0) * 1000)
            changed = out != seg.translation
            seg.translation, seg.translation_src = out, src
            await self._emit_segment(seg, subtitle=changed or final)
            if not final and seg.id in self._dirty:
                continue
            return

    # ---------------------------------------------------------------- sortie
    async def _emit_segment(self, seg: Segment, *, subtitle: bool = False) -> None:
        total = None
        if seg.asr_ms is not None and seg.tr_ms is not None:
            total = seg.asr_ms + seg.tr_ms
        latency = {"asr": seg.asr_ms, "translation": seg.tr_ms, "total": total}
        await self.bus.emit({
            "type": "segment.update", "segment_id": seg.id, "state": seg.state,
            "src_committed": seg.committed, "src_partial": seg.partial,
            "translation": seg.translation, "latency_ms": latency,
        })
        if subtitle and seg.translation:
            await self.bus.emit({
                "type": "subtitle.update", "segment_id": seg.id, "state": seg.state,
                "text": seg.translation, "lines": to_lines(seg.translation),
                "dir": "rtl" if (self.tgt and self.tgt.rtl) else "ltr",
                "latency_ms": latency,
            }, overlay=True)
