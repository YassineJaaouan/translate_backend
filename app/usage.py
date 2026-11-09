"""Suivi des coûts (reconnaissance vocale + traduction), limite de budget et notification.

Les montants sont des ESTIMATIONS calculées avec les tarifs ci-dessous. Vérifie-les sur les pages
de tarifs des fournisseurs : ils changent. Si tu es sur une offre gratuite, la facture réelle peut
être nulle alors que l'estimation, elle, compte comme si tu payais.

Le compteur est enregistré dans un fichier JSON : il survit aux redémarrages et se remet à zéro
chaque mois (le budget est donc une limite MENSUELLE).
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import time
import urllib.request
from pathlib import Path

log = logging.getLogger("usage")

# USD par million de tokens : (entrée, sortie). Relevés en novembre 2026, à vérifier.
PRICES: dict[str, tuple[float, float]] = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "mock": (0.0, 0.0),   # mode démo : gratuit
}
DEFAULT_PRICE = (1.00, 5.00)   # modèle inconnu : estimation prudente (plutôt haute)


class UsageMeter:
    def __init__(self, path: str | Path, *, deepgram_usd_per_min: float,
                 budget_usd: float = 0.0, warn_pct: float = 0.8) -> None:
        self.path = Path(path)
        self.dg_rate = deepgram_usd_per_min
        self.warn_pct = warn_pct
        self._default_budget = budget_usd
        self._last_save = 0.0
        self._dirty = False
        self._alerted: set[str] = set()
        self._unknown_models: set[str] = set()
        self._reset_counters()
        self.budget_usd = budget_usd
        self._load()

    # --------------------------------------------------------------- état
    def _reset_counters(self) -> None:
        self.period = time.strftime("%Y-%m")
        self.asr_seconds = 0.0
        self.llm: dict[str, list[int]] = {}   # modèle -> [tokens entrée, tokens sortie]

    def _roll_period(self) -> None:
        now = time.strftime("%Y-%m")
        if now != self.period:
            log.info("Nouveau mois (%s) : compteur remis à zéro", now)
            self._reset_counters()
            self._alerted.clear()
            self._dirty = True

    @property
    def asr_cost(self) -> float:
        return self.asr_seconds / 60.0 * self.dg_rate

    @property
    def llm_cost(self) -> float:
        total = 0.0
        for model, (tin, tout) in self.llm.items():
            pin, pout = PRICES.get(model, DEFAULT_PRICE)
            total += tin / 1e6 * pin + tout / 1e6 * pout
        return total

    @property
    def spent_usd(self) -> float:
        return self.asr_cost + self.llm_cost

    @property
    def state(self) -> str:
        if self.budget_usd <= 0:
            return "unlimited"
        if self.spent_usd >= self.budget_usd:
            return "exceeded"
        if self.spent_usd >= self.warn_pct * self.budget_usd:
            return "warning"
        return "ok"

    @property
    def exceeded(self) -> bool:
        return self.state == "exceeded"

    def snapshot(self) -> dict:
        return {
            "type": "usage",
            "period": self.period,
            "spent_usd": round(self.spent_usd, 4),
            "asr_usd": round(self.asr_cost, 4),
            "llm_usd": round(self.llm_cost, 4),
            "asr_minutes": round(self.asr_seconds / 60.0, 2),
            "llm_tokens_in": sum(v[0] for v in self.llm.values()),
            "llm_tokens_out": sum(v[1] for v in self.llm.values()),
            "budget_usd": self.budget_usd,
            "state": self.state,
        }

    # --------------------------------------------------------------- ajouts
    def add_audio(self, seconds: float) -> None:
        self._roll_period()
        self.asr_seconds += seconds
        self._touch()

    def add_llm(self, model: str, tokens_in: int, tokens_out: int) -> None:
        self._roll_period()
        if model not in PRICES and model not in self._unknown_models:
            self._unknown_models.add(model)
            log.warning("Tarif inconnu pour le modèle %s : estimation prudente utilisée", model)
        entry = self.llm.setdefault(model, [0, 0])
        entry[0] += int(tokens_in)
        entry[1] += int(tokens_out)
        self._touch()

    # --------------------------------------------------------------- alertes
    def pop_new_alert(self) -> str | None:
        """Renvoie 'warning' ou 'exceeded' une seule fois par palier atteint."""
        st = self.state
        # Si le budget a été relevé ou le compteur remis à zéro, on réarme les paliers.
        if st in ("ok", "unlimited"):
            self._alerted.clear()
        elif st == "warning":
            self._alerted.discard("exceeded")
        if st in ("warning", "exceeded") and st not in self._alerted:
            self._alerted.add(st)
            if st == "exceeded":
                self._alerted.add("warning")
            return st
        return None

    # --------------------------------------------------------------- réglages
    def set_budget(self, usd: float) -> None:
        self.budget_usd = max(0.0, float(usd))
        self._dirty = True
        self.save(force=True)

    def reset(self) -> None:
        self._reset_counters()
        self._alerted.clear()
        self._dirty = True
        self.save(force=True)

    # --------------------------------------------------------------- fichier
    def _touch(self) -> None:
        self._dirty = True
        self.save()

    def save(self, force: bool = False) -> None:
        if not self._dirty:
            return
        now = time.monotonic()
        if not force and now - self._last_save < 5.0:
            return
        data = {"period": self.period, "asr_seconds": self.asr_seconds,
                "llm": self.llm, "budget_usd": self.budget_usd}
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, self.path)
            self._dirty = False
            self._last_save = now
        except OSError as exc:
            log.warning("Impossible d'enregistrer %s : %s", self.path, exc)

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("period") == self.period:
                self.asr_seconds = float(data.get("asr_seconds", 0.0))
                self.llm = {k: [int(v[0]), int(v[1])] for k, v in data.get("llm", {}).items()}
            if "budget_usd" in data:
                self.budget_usd = float(data["budget_usd"])
        except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
            log.warning("Fichier d'usage illisible (%s) : compteur remis à zéro", exc)


async def send_webhook(url: str, text: str) -> None:
    """Envoie une notification JSON {"text": ..., "content": ...} (compatible Slack et Discord)."""
    if not url:
        return

    def _post() -> None:
        body = json.dumps({"text": text, "content": text}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "live-subtitles/1.0"})
        urllib.request.urlopen(req, timeout=5).read()

    try:
        await asyncio.to_thread(_post)
    except Exception as exc:  # une notification ratée ne doit jamais casser le pipeline
        log.warning("Notification webhook échouée : %s", exc)
