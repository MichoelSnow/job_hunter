"""Helpers for normalizing cross-source job fields."""

import html
import re


def infer_work_arrangement(
    *,
    title: str | None,
    location: str | None,
    description: str | None,
    is_remote: bool | None = None,
) -> str:
    """Infer work arrangement from available text signals."""
    text = " ".join(
        part.strip().lower()
        for part in (title or "", location or "", description or "")
        if part
    )

    if is_remote is True:
        return "remote"
    if _contains_signal(text, ("hybrid",)):
        return "hybrid"
    if _contains_signal(text, ("in office", "in-office", "onsite", "on-site", "office-based")):
        return "in_office"
    if _contains_signal(text, ("remote", "work from home")):
        return "remote"
    return "unknown"


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)

    # Some sources return doubly-escaped HTML (e.g. "&lt;div&gt;...").
    # Unescape a few times to normalize common patterns without looping forever.
    for _ in range(3):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped

    # Convert HTML-ish formatting to plain text for display and matching.
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_signal(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)
