from __future__ import annotations
import textwrap


def to_lines(text: str, max_chars: int = 42, max_lines: int = 2) -> list[str]:
    """Découpe pour l'affichage (norme sous-titres : ~42 caractères, 2 lignes).
    Si le texte est plus long, on garde la fin (le plus récent)."""
    lines = textwrap.wrap(text, width=max_chars, break_long_words=False) or []
    return lines[-max_lines:]
