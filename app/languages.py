"""Langues proposées dans l'interface. Source unique : le backend envoie cette liste à Flutter.

Les codes de langue parlée sont ceux acceptés par Deepgram Nova-3 (17 variantes d'arabe).
Pour en ajouter, ajoute une ligne ci-dessous : un code non supporté par Deepgram provoque
un message d'erreur clair au démarrage.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Lang:
    code: str
    label: str            # affiché dans l'interface
    prompt: str           # nom donné au modèle de traduction
    rtl: bool = False     # écriture de droite à gauche


ARABIC = [
    Lang("ar", "Arabe — standard / général", "Modern Standard Arabic", True),
    Lang("ar-TN", "Arabe — Tunisie", "Tunisian Arabic (Darija)", True),
    Lang("ar-DZ", "Arabe — Algérie", "Algerian Arabic (Darija)", True),
    Lang("ar-MA", "Arabe — Maroc", "Moroccan Arabic (Darija)", True),
    Lang("ar-EG", "Arabe — Égypte", "Egyptian Arabic", True),
    Lang("ar-SA", "Arabe — Arabie saoudite", "Saudi Arabic", True),
    Lang("ar-AE", "Arabe — Émirats arabes unis", "Emirati Arabic", True),
    Lang("ar-QA", "Arabe — Qatar", "Qatari Arabic", True),
    Lang("ar-KW", "Arabe — Koweït", "Kuwaiti Arabic", True),
    Lang("ar-SY", "Arabe — Syrie", "Syrian Arabic", True),
    Lang("ar-LB", "Arabe — Liban", "Lebanese Arabic", True),
    Lang("ar-PS", "Arabe — Palestine", "Palestinian Arabic", True),
    Lang("ar-JO", "Arabe — Jordanie", "Jordanian Arabic", True),
    Lang("ar-IQ", "Arabe — Irak", "Iraqi Arabic", True),
    Lang("ar-SD", "Arabe — Soudan", "Sudanese Arabic", True),
    Lang("ar-TD", "Arabe — Tchad", "Chadian Arabic", True),
    Lang("ar-IR", "Arabe — Iran", "Iranian Arabic", True),
]

OTHERS = [
    Lang("fr", "Français", "French"),
    Lang("en", "Anglais", "English"),
    Lang("es", "Espagnol", "Spanish"),
    Lang("de", "Allemand", "German"),
    Lang("it", "Italien", "Italian"),
    Lang("pt", "Portugais", "Portuguese"),
    Lang("nl", "Néerlandais", "Dutch"),
    Lang("ru", "Russe", "Russian"),
]

# Langue parlée (reconnue par Deepgram)
SOURCES: list[Lang] = ARABIC + OTHERS

# Langue des sous-titres (produite par le modèle de traduction)
TARGETS: list[Lang] = [
    Lang("fr", "Français", "French"),
    Lang("en", "Anglais", "English"),
    Lang("ar", "Arabe (standard)", "Modern Standard Arabic", True),
    Lang("es", "Espagnol", "Spanish"),
    Lang("de", "Allemand", "German"),
    Lang("it", "Italien", "Italian"),
    Lang("pt", "Portugais", "Portuguese"),
    Lang("nl", "Néerlandais", "Dutch"),
    Lang("ru", "Russe", "Russian"),
    Lang("tr", "Turc", "Turkish"),
]


def find_source(code: str | None) -> Lang | None:
    return next((l for l in SOURCES if l.code == code), None)


def find_target(code: str | None) -> Lang | None:
    return next((l for l in TARGETS if l.code == code), None)


def same_language(src: Lang, tgt: Lang) -> bool:
    """Pas de traduction nécessaire. Un dialecte arabe vers l'arabe standard reste une vraie traduction."""
    if src.code == tgt.code:
        return True
    base_s, base_t = src.code.split("-")[0], tgt.code.split("-")[0]
    return base_s == base_t and base_s != "ar"


def to_json(l: Lang) -> dict:
    return {"code": l.code, "label": l.label, "rtl": l.rtl}
