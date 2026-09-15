"""Hard-criteria filtering: removes jobs that don't meet mandatory requirements."""

import logging
import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.models.job import Job
from app.services.job_normalization import normalize_location

logger = logging.getLogger(__name__)

REMOTE_SIGNALS = ["fully remote", "100% remote", "remote only", "work from home"]
_LOCATION_TERM_ALIASES: dict[str, set[str]] = {
    "new york": {"new york", "nyc", "manhattan", "brooklyn", "queens", "bronx"},
}

LEADERSHIP_KEYWORDS = [
    "director",
    "vp",
    "vice president",
    "head of",
    "chief",
    "lead",
    "manager",
    "principal",
]


@dataclass(frozen=True)
class _TermNode:
    value: str


@dataclass(frozen=True)
class _NotNode:
    child: "_Node"


@dataclass(frozen=True)
class _AndNode:
    left: "_Node"
    right: "_Node"


@dataclass(frozen=True)
class _OrNode:
    left: "_Node"
    right: "_Node"


_Node = _TermNode | _NotNode | _AndNode | _OrNode


@dataclass(frozen=True)
class _Token:
    kind: Literal["TERM", "AND", "OR", "NOT", "LPAREN", "RPAREN"]
    value: str


class JobFilter:
    """Applies user-configured hard filters to jobs."""

    def __init__(
        self,
        *,
        allowed_location_query: str | None = None,
        exclude_remote: bool = True,
        title_query: str | None = None,
        target_salary: int | None = None,
        include_missing_salary: bool = True,
    ) -> None:
        self.exclude_remote = exclude_remote
        self.title_query = (title_query or "").strip()
        self.allowed_location_query = (allowed_location_query or "").strip()
        self._title_ast = parse_boolean_query(self.title_query)
        self._location_ast = parse_boolean_query(self.allowed_location_query)
        self.target_salary = target_salary
        self.include_missing_salary = include_missing_salary

    def apply_all(self, jobs: list[dict]) -> list[dict]:
        original_count = len(jobs)
        jobs = [j for j in jobs if self.passes(j)]
        logger.info(
            "Hard filters: %d → %d jobs (%d removed)",
            original_count,
            len(jobs),
            original_count - len(jobs),
        )
        return jobs

    def passes(self, job: dict) -> bool:
        return (
            self._passes_location(job)
            and self._passes_work_arrangement(job)
            and self._passes_role_level(job)
            and self._passes_salary(job)
        )

    def _passes_location(self, job: dict) -> bool:
        if self._location_ast is None:
            return True
        location = normalize_location(job.get("location")) or ""
        return evaluate_boolean_query(
            self._location_ast,
            location,
            field="location",
        )

    def _passes_work_arrangement(self, job: dict) -> bool:
        """Reject jobs explicitly marked as fully remote."""
        if not self.exclude_remote:
            return True
        description = (job.get("description") or "").lower()
        title = (job.get("title") or "").lower()
        text = f"{title} {description}"
        if any(signal in text for signal in REMOTE_SIGNALS):
            return False
        if job.get("work_arrangement") == "remote":
            return False
        return True

    def _passes_role_level(self, job: dict) -> bool:
        if self._title_ast is None:
            return True
        title = str(job.get("title") or "")
        return evaluate_boolean_query(
            self._title_ast,
            title,
            field="title",
        )

    def _passes_salary(self, job: dict) -> bool:
        if self.target_salary is None:
            return True

        salary_min = _to_int(job.get("salary_min"))
        salary_max = _to_int(job.get("salary_max"))

        if salary_min is None and salary_max is None:
            return self.include_missing_salary

        if salary_min is not None and salary_max is not None:
            high = max(salary_min, salary_max)
            # Minimum salary threshold: keep jobs that can meet/exceed target.
            return high >= self.target_salary

        if salary_min is not None:
            return salary_min >= self.target_salary

        if salary_max is not None:
            return salary_max >= self.target_salary

        return self.include_missing_salary


def reapply_filters_to_existing_jobs(db: Session, filter_engine: JobFilter) -> int:
    """Recompute passes_user_filters for all jobs in DB using current settings."""
    rows = db.query(Job).all()
    changed = 0
    for row in rows:
        job_dict = {
            "title": row.title,
            "description": row.description,
            "location": row.location,
            "work_arrangement": row.work_arrangement,
            "salary_min": row.salary_min,
            "salary_max": row.salary_max,
        }
        visible = filter_engine.passes(job_dict)
        if row.passes_user_filters != visible:
            row.passes_user_filters = visible
            changed += 1
    if changed:
        logger.info("Reapplied user filters to jobs: %d rows changed", changed)
    return changed


def _to_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_boolean_query(query: str | None) -> _Node | None:
    normalized = (query or "").strip()
    if not normalized:
        return None
    tokens = _tokenize_boolean_query(normalized)
    parser = _BooleanQueryParser(tokens)
    return parser.parse()


def evaluate_boolean_query(ast: _Node, text: str, *, field: Literal["title", "location"]) -> bool:
    normalized_text = _normalize_text(text)
    return _evaluate_ast(ast, normalized_text, field=field)


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _tokenize_boolean_query(query: str) -> list[_Token]:
    pattern = re.compile(
        r"""
        (?P<WS>\s+)
        | (?P<LPAREN>\()
        | (?P<RPAREN>\))
        | (?P<AND>\bAND\b)
        | (?P<OR>\bOR\b)
        | (?P<NOT>\bNOT\b)
        | (?P<QUOTED>"(?:[^"\\]|\\.)*")
        | (?P<TERM>[^\s()]+)
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    tokens: list[_Token] = []
    cursor = 0
    for match in pattern.finditer(query):
        if match.start() != cursor:
            raise ValueError(f"Invalid token near: {query[cursor : match.start()]!r}")
        cursor = match.end()
        kind = match.lastgroup
        if kind == "WS":
            continue
        if kind == "QUOTED":
            raw = match.group(kind)[1:-1]
            term = bytes(raw, "utf-8").decode("unicode_escape").strip()
            if not term:
                raise ValueError("Empty quoted phrase is not allowed")
            tokens.append(_Token(kind="TERM", value=term))
            continue
        if kind == "TERM":
            term = match.group(kind).strip()
            if term:
                tokens.append(_Token(kind="TERM", value=term))
            continue
        if kind in {"LPAREN", "RPAREN", "AND", "OR", "NOT"}:
            tokens.append(_Token(kind=kind, value=match.group(kind).upper()))
            continue
        raise ValueError("Unsupported token in boolean query")
    if cursor != len(query):
        raise ValueError(f"Invalid token near: {query[cursor:]!r}")
    if not tokens:
        raise ValueError("Boolean query is empty")
    return tokens


class _BooleanQueryParser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._index = 0

    def parse(self) -> _Node:
        node = self._parse_or()
        if self._index != len(self._tokens):
            token = self._tokens[self._index]
            raise ValueError(f"Unexpected token: {token.value}")
        return node

    def _parse_or(self) -> _Node:
        node = self._parse_and()
        while self._peek_kind() == "OR":
            self._consume("OR")
            node = _OrNode(left=node, right=self._parse_and())
        return node

    def _parse_and(self) -> _Node:
        node = self._parse_not()
        while self._peek_kind() == "AND":
            self._consume("AND")
            node = _AndNode(left=node, right=self._parse_not())
        return node

    def _parse_not(self) -> _Node:
        if self._peek_kind() == "NOT":
            self._consume("NOT")
            return _NotNode(child=self._parse_not())
        return self._parse_primary()

    def _parse_primary(self) -> _Node:
        kind = self._peek_kind()
        if kind == "TERM":
            return _TermNode(value=self._consume("TERM").value)
        if kind == "LPAREN":
            self._consume("LPAREN")
            node = self._parse_or()
            if self._peek_kind() != "RPAREN":
                raise ValueError("Missing closing parenthesis")
            self._consume("RPAREN")
            return node
        if kind is None:
            raise ValueError("Unexpected end of expression")
        raise ValueError(f"Unexpected token: {self._tokens[self._index].value}")

    def _peek_kind(self) -> Literal["TERM", "AND", "OR", "NOT", "LPAREN", "RPAREN"] | None:
        if self._index >= len(self._tokens):
            return None
        return self._tokens[self._index].kind

    def _consume(
        self, expected_kind: Literal["TERM", "AND", "OR", "NOT", "LPAREN", "RPAREN"]
    ) -> _Token:
        if self._index >= len(self._tokens):
            raise ValueError(f"Expected {expected_kind} but found end of expression")
        token = self._tokens[self._index]
        if token.kind != expected_kind:
            raise ValueError(f"Expected {expected_kind} but found {token.value}")
        self._index += 1
        return token


def _evaluate_ast(ast: _Node, text: str, *, field: Literal["title", "location"]) -> bool:
    if isinstance(ast, _TermNode):
        return _match_term(ast.value, text, field=field)
    if isinstance(ast, _NotNode):
        return not _evaluate_ast(ast.child, text, field=field)
    if isinstance(ast, _AndNode):
        return _evaluate_ast(ast.left, text, field=field) and _evaluate_ast(
            ast.right, text, field=field
        )
    if isinstance(ast, _OrNode):
        return _evaluate_ast(ast.left, text, field=field) or _evaluate_ast(
            ast.right, text, field=field
        )
    return False


def _match_term(term: str, text: str, *, field: Literal["title", "location"]) -> bool:
    normalized_term = _normalize_text(term)
    if not normalized_term:
        return False
    if field == "location":
        aliases = _LOCATION_TERM_ALIASES.get(normalized_term)
        if aliases:
            return any(alias in text for alias in aliases)
        return normalized_term in text

    title_words = re.findall(r"[a-z0-9]+", normalized_term)
    if not title_words:
        return normalized_term in text
    pattern = r"\b" + r"\s+".join(re.escape(word) for word in title_words) + r"\b"
    return re.search(pattern, text) is not None
