from __future__ import annotations
from ..languages import Lang


def system_prompt(src: Lang, tgt: Lang, glossary: list[str] | None = None) -> str:
    s = f"""You are a professional conference interpreter producing live subtitles.
Translate from {src.prompt} into {tgt.prompt}.
Rules:
- Reply ONLY with the translation in {tgt.prompt}: no quotes, no comments, no explanations.
- Faithful, natural and concise wording suited to subtitles.
- The source comes from speech recognition: it may contain errors; fix them only when the meaning is obvious.
- Speakers may mix dialect, Modern Standard Arabic, French or English words: translate everything into {tgt.prompt}.
- If the sentence is unfinished, translate only what was said; never invent the rest.
- Keep proper names; transliterate names in the usual way for {tgt.prompt}.
- If a provisional translation of the beginning is given, keep it identical as much as possible and change only what is wrong."""
    if glossary:
        s += "\n\nGlossary to respect (source = target):\n" + "\n".join(glossary)
    return s


def build_prompt(text: str, context: list[tuple[str, str]], previous: str | None) -> str:
    parts: list[str] = []
    if context:
        parts.append("Context (previous sentences, do not translate again):")
        parts += [f"SOURCE: {a}\nTRANSLATION: {b}" for a, b in context[-3:]]
        parts.append("")
    if previous:
        parts.append(f"Provisional translation already displayed for the beginning: {previous}\n")
    parts.append("Text to translate:\n" + text)
    return "\n".join(parts)
