"""Helpers for normalizing cross-source job fields."""

import html
import re

from bs4 import BeautifulSoup

_ALLOWED_HTML_TAGS = {
    "p",
    "br",
    "ul",
    "ol",
    "li",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "a",
}
_DROP_HTML_TAGS = {"script", "style", "iframe", "object", "embed", "form", "svg", "math", "noscript"}
_ALLOWED_LINK_PROTOCOLS = ("http://", "https://", "mailto:")
_SALARY_RANGE_RE = re.compile(
    r"(?P<min_prefix>\$|USD\s*\$?)?\s*(?P<min>\d[\d,]*(?:\.\d{1,2})?)\s*"
    r"(?:to|and|[-\u2013\u2014])\s*"
    r"(?P<max_prefix>\$|USD\s*\$?)?\s*(?P<max>\d[\d,]*(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_SALARY_SINGLE_RE = re.compile(
    r"(?P<prefix>\$|USD\s*\$?)\s*(?P<value>\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?P<value_suffix>\d[\d,]*(?:\.\d{1,2})?)\s*USD\b",
    re.IGNORECASE,
)


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
    if _contains_signal(text, ("hybrid",)) or _has_hybrid_office_schedule(text):
        return "hybrid"
    if _contains_signal(
        text,
        ("in office", "in-office", "in the office", "onsite", "on-site", "office-based"),
    ):
        return "in_office"
    if _contains_signal(text, ("remote", "work from home")):
        return "remote"
    return "unknown"


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    sanitized_html = sanitize_description_html(value)
    if not sanitized_html:
        return ""
    text = BeautifulSoup(sanitized_html, "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def sanitize_description_html(value: str | None) -> str:
    """Return safe HTML that preserves basic text formatting."""
    if not value:
        return ""

    soup = BeautifulSoup(_unescape_html(str(value)), "html.parser")

    for tag in soup.find_all(_DROP_HTML_TAGS):
        tag.decompose()

    for tag in soup.find_all(True):
        name = tag.name.lower()
        if name not in _ALLOWED_HTML_TAGS:
            tag.unwrap()
            continue

        if name == "a":
            href = (tag.get("href") or "").strip()
            if href.startswith(_ALLOWED_LINK_PROTOCOLS):
                tag.attrs = {
                    "href": href,
                    "target": "_blank",
                    "rel": "noreferrer noopener",
                }
            else:
                tag.attrs = {}
            continue

        tag.attrs = {}

    return str(soup).strip()


def _unescape_html(value: str) -> str:
    text = value
    # Some sources return doubly-escaped HTML (e.g. "&lt;div&gt;...").
    # Unescape a few times to normalize common patterns without looping forever.
    for _ in range(3):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    return text


def extract_salary_from_text(text: str | None) -> tuple[int | None, int | None, str | None, str | None]:
    """
    Extract salary range from free-form text.
    Returns (salary_min, salary_max, salary_period, salary_currency).
    """
    if not text:
        return None, None, None, None

    clean_text = html_to_text(text)
    if not clean_text:
        return None, None, None, None

    lower = clean_text.lower()
    if "$" not in clean_text and "usd" not in lower:
        return None, None, None, None

    for match in _SALARY_RANGE_RE.finditer(clean_text):
        window_start = max(0, match.start() - 12)
        window_end = min(len(clean_text), match.end() + 12)
        window = clean_text[window_start:window_end].lower()
        has_currency = bool(match.group("min_prefix") or match.group("max_prefix") or "usd" in window)
        if not has_currency:
            continue

        min_value = _parse_salary_number(match.group("min"))
        max_value = _parse_salary_number(match.group("max"))
        if min_value is None or max_value is None:
            continue

        if max_value < min_value:
            min_value, max_value = max_value, min_value

        return int(round(min_value)), int(round(max_value)), _infer_salary_period(lower), "USD"

    for match in _SALARY_SINGLE_RE.finditer(clean_text):
        raw_value = match.group("value") or match.group("value_suffix")
        value = _parse_salary_number(raw_value)
        if value is None:
            continue
        normalized_value = int(round(value))
        return normalized_value, normalized_value, _infer_salary_period(lower), "USD"

    return None, None, None, None


def _parse_salary_number(raw_value: str | None) -> float | None:
    if not raw_value:
        return None
    try:
        return float(raw_value.replace(",", ""))
    except ValueError:
        return None


def _infer_salary_period(text_lower: str) -> str | None:
    if any(signal in text_lower for signal in ("per hour", "/hour", "hourly", "an hour", "each hour")):
        return "hour"
    if any(signal in text_lower for signal in ("per week", "/week", "weekly")):
        return "week"
    if any(signal in text_lower for signal in ("per month", "/month", "monthly")):
        return "month"
    if any(signal in text_lower for signal in ("per year", "/year", "/yr", "annually", "annual")):
        return "year"
    if any(signal in text_lower for signal in ("base salary", "salary range", "salary band")):
        return "year"
    return None


def _contains_signal(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def _has_hybrid_office_schedule(text: str) -> bool:
    """Detect roles requiring office attendance for only part of the week."""
    has_office_reference = "office" in text or "onsite" in text or "on-site" in text
    has_partial_week_schedule = re.search(r"\b[1-4]\s+days?\s+(?:per|a)\s+week\b", text)
    return has_office_reference and has_partial_week_schedule is not None
