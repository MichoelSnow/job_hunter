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
_DROP_HTML_TAGS = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "form",
    "svg",
    "math",
    "noscript",
}
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

_LOCATION_PLACEHOLDER_RE = re.compile(r"^(?:none|null|n/?a|unknown|not specified|)$", re.IGNORECASE)
_LOCATION_SPLIT_RE = re.compile(r"\s*(?:\bor\b|\band\b|[;|])\s*", re.IGNORECASE)
_US_STATES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}
_US_STATE_CODES = set(_US_STATES.values())
_NYC_ALIASES = {
    "new york city": "New York City",
    "new york": "New York City",
    "nyc": "New York City",
    "manhattan": "Manhattan",
    "brooklyn": "Brooklyn",
    "queens": "Queens",
    "the bronx": "Bronx",
    "bronx": "Bronx",
    "staten island": "Staten Island",
}
_CITY_ALIASES = {
    "sf": "San Francisco",
    "s.f.": "San Francisco",
    "san francisco": "San Francisco",
    "ny": "New York City",
}
_INFERRED_CITY_STATES = {
    "new york city": "NY",
    "san francisco": "CA",
}
_ARRANGEMENT_ONLY_LOCATIONS = {
    "remote",
    "hybrid",
    "on site",
    "onsite",
    "in office",
    "in-office",
}


def normalize_location(value: str | None) -> str | None:
    """Normalize source location text into a city-level display value."""
    if not value:
        return None

    text = re.sub(r"\s+", " ", str(value)).strip(" ,;-–—")
    if not text or _LOCATION_PLACEHOLDER_RE.fullmatch(text):
        return None

    text = re.sub(
        r"^\s*(?:remote|hybrid|on[- ]?site|in[- ]?office)\s*[-:;,]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s*\((?:remote|hybrid|on[- ]?site|in[- ]?office)\)\s*", "", text, flags=re.IGNORECASE
    )
    text = re.sub(
        r"\s+(?:hybrid|remote|on[- ]?site|in[- ]?office)(?:\s+optional)?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
        text = re.sub(
            r"\s+(?:hybrid|remote|on[- ]?site|in[- ]?office)(?:\s+optional)?\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )
    parts = [
        part.strip(" ,;-–—")
        for part in _LOCATION_SPLIT_RE.split(text)
        if part.strip(" ,;-–—").casefold() not in _ARRANGEMENT_ONLY_LOCATIONS
    ]
    normalized = [_normalize_location_part(part) for part in parts]
    values = list(dict.fromkeys(part for part in normalized if part))
    return "; ".join(values) if values else None


def parse_locations(value: str | None) -> list[dict[str, str | None]]:
    """Parse source location text into city/state/country records."""
    display = normalize_location(value)
    if not display:
        return []

    records: list[dict[str, str | None]] = []
    for item in display.split("; "):
        parts = [part.strip() for part in item.split(",")]
        if len(parts) == 1 and parts[0] == "United States":
            records.append(
                {"city": None, "state": None, "country": "United States", "display_name": item}
            )
            continue
        city = parts[0] or None
        state = parts[1] if len(parts) > 1 else None
        country = parts[2] if len(parts) > 2 else None
        if country is None and state and state.casefold() in {"united states", "usa", "us"}:
            country, state = "United States", None
        records.append({"city": city, "state": state, "country": country, "display_name": item})
    return records


def _normalize_location_part(value: str) -> str | None:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    cleaned = [part for part in parts if not _LOCATION_PLACEHOLDER_RE.fullmatch(part)]
    if not cleaned:
        return None

    if len(cleaned) == 1:
        city = re.sub(r"\s+office$", "", cleaned[0].strip(), flags=re.IGNORECASE)
        if re.fullmatch(r"\d+\s+locations?", city, flags=re.IGNORECASE):
            return None
        city_key = city.casefold()
        if city_key in _CITY_ALIASES:
            city = _CITY_ALIASES[city_key]
        elif city_key in _NYC_ALIASES:
            city = _NYC_ALIASES[city_key]
        if city_key in {"united states", "usa", "us", "u.s.", "u.s.a."}:
            return "United States"
        state = _INFERRED_CITY_STATES.get(city.casefold())
        if state:
            return f"{city}, {state}"
        return city.title()

    city = re.sub(r"\s+office$", "", cleaned[0], flags=re.IGNORECASE)
    region = cleaned[-1].casefold()
    city_key = city.casefold()
    if city_key in _NYC_ALIASES:
        city = _NYC_ALIASES[city_key]
    elif city_key == "new york" and region in {"ny", "new york"}:
        city = "New York"
    if region.upper() in _US_STATE_CODES:
        return f"{city.title()}, {region.upper()}"
    if region in _US_STATES:
        return f"{city.title()}, {_US_STATES[region]}"
    if region in {"united states", "usa", "us", "u.s.", "u.s.a."}:
        if city.casefold() in {"new york", "new york city"}:
            return "New York City, NY"
        return city.title()
    return f"{city.title()}, {cleaned[-1].title()}"


def infer_work_arrangement(
    *,
    title: str | None,
    location: str | None,
    description: str | None,
    is_remote: bool | None = None,
) -> str:
    """Infer work arrangement from available text signals."""
    text = " ".join(
        part.strip().lower() for part in (title or "", location or "", description or "") if part
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


def extract_salary_from_text(
    text: str | None,
) -> tuple[int | None, int | None, str | None, str | None]:
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
        has_currency = bool(
            match.group("min_prefix") or match.group("max_prefix") or "usd" in window
        )
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
    if any(
        signal in text_lower for signal in ("per hour", "/hour", "hourly", "an hour", "each hour")
    ):
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
