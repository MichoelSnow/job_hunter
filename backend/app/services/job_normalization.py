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
_COMMON_COUNTRIES = {
    "australia",
    "canada",
    "china",
    "france",
    "germany",
    "india",
    "ireland",
    "italy",
    "japan",
    "mexico",
    "netherlands",
    "singapore",
    "spain",
    "switzerland",
    "united kingdom",
    "united states",
}
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
    "ny": "NYC",
}
_NYC_BOROUGHS = {
    "manhattan": "Manhattan",
    "brooklyn": "Brooklyn",
    "queens": "Queens",
    "the bronx": "Bronx",
    "bronx": "Bronx",
    "staten island": "Staten Island",
}
_NYC_DISPLAY = "NY, NY"
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
_REMOTE_ONLY_VALUES = {
    "remote",
    "remote us",
    "remote usa",
    "remote united states",
    "us remote",
    "u s remote",
    "usa remote",
    "united states remote",
}


def normalize_location(value: str | None) -> str | None:
    """Normalize source location text into a city-level display value."""
    if not value:
        return None

    text = re.sub(r"\s+", " ", str(value)).strip(" ,;-–—")
    if not text or _LOCATION_PLACEHOLDER_RE.fullmatch(text):
        return None

    remote_candidate = re.sub(r"[^a-z]+", " ", text.casefold()).strip()
    if remote_candidate in _REMOTE_ONLY_VALUES:
        return "Remote"

    text = re.sub(
        r"\bremote\b\s*[-,:;]?\s*(?:u\.?s\.?|usa|united states)?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\([^)]*hub cities[^)]*\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhybrid\b|\boptional\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\s*(?:(?:or|and)\s*|[,;]\s*)*\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" ,;-–—")

    text = re.sub(
        r"^\s*(?:on[- ]?site|in[- ]?office)\b\s*[-:;,]?\s*",
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
    if not display or display == "Remote":
        return []

    records: list[dict[str, str | None]] = []
    for item in display.split("; "):
        parts = [part.strip() for part in item.split(",")]
        if parts == ["United States"]:
            records.append(
                {"city": None, "state": None, "country": "United States", "display_name": item}
            )
            continue
        if parts == ["Remote"]:
            continue

        if len(parts) == 1 and parts[0].casefold() in _US_STATES:
            state = _US_STATES[parts[0].casefold()]
            records.append(
                {"city": None, "state": state, "country": "United States", "display_name": item}
            )
            continue
        if len(parts) == 1 and parts[0].casefold() in _US_STATE_CODES:
            records.append(
                {
                    "city": None,
                    "state": parts[0].upper(),
                    "country": "United States",
                    "display_name": item,
                }
            )
            continue

        city = parts[0] or None
        state = None
        country = None
        if len(parts) >= 2:
            region = parts[1].casefold()
            if region in _US_STATES:
                state = _US_STATES[region]
                country = "United States"
            elif region in _US_STATE_CODES:
                state = parts[1].upper()
                country = "United States"
            elif region in _COMMON_COUNTRIES:
                country = "United States" if region == "united states" else parts[1]
            elif len(parts) >= 3 and parts[-1].casefold() in _COMMON_COUNTRIES:
                state = parts[1]
                country = (
                    "United States"
                    if parts[-1].casefold() == "united states"
                    else parts[-1]
                )
            else:
                state = parts[1]
        if len(parts) >= 3 and parts[-1].casefold() in _COMMON_COUNTRIES:
            country = (
                "United States" if parts[-1].casefold() == "united states" else parts[-1]
            )
            if state == country:
                state = None
        records.append({"city": city, "state": state, "country": country, "display_name": item})
    return records


def location_group_keys(value: str | None) -> set[str]:
    """Return the geographic filter groups represented by a source location."""
    normalized = normalize_location(value)
    if normalized == "Remote":
        return {"remote"}
    if not normalized:
        return {"unknown"}

    groups: set[str] = set()
    for record in parse_locations(value):
        city = (record["city"] or "").casefold()
        state = (record["state"] or "").upper()
        country = (record["country"] or "").casefold()
        if city in {"new york", "new york city", "ny", "nyc", *(_NYC_BOROUGHS.keys())}:
            groups.add("nyc")
        elif state == "NY":
            groups.add("ny_state")
        elif state in _US_STATE_CODES:
            groups.add(f"state:{state}")
        elif country and country != "united states":
            groups.add("outside_us")

    return groups or {"unknown"}


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
        if city_key in _NYC_ALIASES and city_key not in _NYC_BOROUGHS:
            return _NYC_DISPLAY
        if city_key in _NYC_BOROUGHS:
            return f"{_NYC_BOROUGHS[city_key]}, NY"
        if city_key in _CITY_ALIASES:
            city = _CITY_ALIASES[city_key]
        if city_key in {"united states", "usa", "us", "u.s.", "u.s.a."}:
            return "United States"
        if city_key in _US_STATES:
            return city.title()
        if city_key.upper() in _US_STATE_CODES:
            return next(
                name.title() for name, code in _US_STATES.items() if code == city_key.upper()
            )
        state = _INFERRED_CITY_STATES.get(city.casefold())
        if state:
            return f"{city}, {state}"
        return city.title()

    city = re.sub(r"\s+office$", "", cleaned[0], flags=re.IGNORECASE)
    region = cleaned[-1].casefold()
    city_key = city.casefold()
    if city_key in _NYC_ALIASES and city_key not in _NYC_BOROUGHS:
        return _NYC_DISPLAY
    if city_key in _NYC_BOROUGHS:
        city = _NYC_BOROUGHS[city_key]
    elif city_key == "new york" and region in {"ny", "new york"}:
        city = "New York"
    if region.upper() in _US_STATE_CODES:
        return f"{city.title()}, {region.upper()}"
    if region in _US_STATES:
        return f"{city.title()}, {_US_STATES[region]}"
    if region in {"united states", "usa", "us", "u.s.", "u.s.a."}:
        if city.casefold() in {"new york", "new york city"}:
            return _NYC_DISPLAY
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
