"""Semantic chunking of regulation text.

Splits markdown text on paragraph boundaries so that each chunk stays a
semantically coherent unit, never cutting a sentence or table row in half
unless a single block exceeds the hard size limit.
"""

from __future__ import annotations

DEFAULT_MAX_CHARS = 1500


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Split markdown text into chunks of at most ``max_chars``.

    Blocks (paragraphs, list groups, table rows) are kept intact where
    possible. A block longer than ``max_chars`` is split on sentence
    boundaries, then on hard character boundaries as a last resort.
    """
    blocks = [b for b in text.split("\n\n") if b.strip()]
    chunks: list[str] = []
    current = ""

    for block in blocks:
        block = block.strip()
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(block) <= max_chars:
            current = block
        else:
            chunks.extend(_split_long_block(block, max_chars))

    if current:
        chunks.append(current)
    return chunks or ([text.strip()] if text.strip() else [])


def _split_long_block(block: str, max_chars: int) -> list[str]:
    parts: list[str] = []
    remaining = block
    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        # Prefer splitting after a sentence end within the window.
        cut = max(window.rfind(". "), window.rfind(".\n"), window.rfind("? "), window.rfind("! "))
        if cut < max_chars // 2:
            cut = max_chars
        else:
            cut += 1  # keep the sentence-ending punctuation
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts
