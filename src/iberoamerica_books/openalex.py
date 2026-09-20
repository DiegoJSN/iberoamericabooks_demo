"""Live OpenAlex enrichment with an explicit offline fallback."""

from __future__ import annotations

from collections.abc import Callable
from difflib import SequenceMatcher
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .cleaning import normalize_text, split_authors


OPENALEX_WORKS_URL = "https://api.openalex.org/works"
USER_AGENT = "IberoamericaBooksPortfolioDemo/1.0 (https://github.com/DiegoJSN/iberoamericabooks_demo)"


class OpenAlexRequestError(RuntimeError):
    """Raised when OpenAlex cannot return a usable response."""


def _similarity(left: object, right: object) -> float:
    return SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()


def _candidate_authors(candidate: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for authorship in candidate.get("authorships") or []:
        author = authorship.get("author") or {}
        if author.get("display_name"):
            names.append(str(author["display_name"]))
    return names


def score_candidate(title: str, authors: str, candidate: dict[str, Any]) -> dict[str, float]:
    """Score one candidate using the original 80% title / 20% author rule."""
    candidate_title = candidate.get("display_name") or candidate.get("title") or ""
    title_score = _similarity(title, candidate_title)
    query_authors = split_authors(authors)
    candidate_authors = _candidate_authors(candidate)
    author_score = 0.0
    if query_authors and candidate_authors:
        author_score = sum(
            max(_similarity(query_author, candidate_author) for candidate_author in candidate_authors)
            for query_author in query_authors
        ) / len(query_authors)
    return {
        "title_score": round(title_score, 4),
        "author_score": round(author_score, 4),
        "match_score": round((0.8 * title_score) + (0.2 * author_score), 4),
    }


def _request_json(url: str, timeout: float) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS endpoint
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # Network failures are recorded per row by the caller.
        raise OpenAlexRequestError(str(exc)) from exc


def query_openalex(
    isbn13: str,
    title: str,
    authors: str,
    *,
    api_key: str | None = None,
    timeout: float = 15.0,
    per_page: int = 25,
    minimum_score: float = 0.55,
    transport: Callable[[str, float], dict[str, Any]] = _request_json,
) -> dict[str, Any]:
    """Query OpenAlex and return the best scored candidate for one book."""
    search_title = str(title).split(":", 1)[0].split(".", 1)[0].strip()
    params = {
        "search": search_title,
        "filter": "type:book",
        "per_page": max(1, min(int(per_page), 100)),
        "select": "id,doi,display_name,cited_by_count,authorships,type",
    }
    if api_key:
        params["api_key"] = api_key
    payload = transport(f"{OPENALEX_WORKS_URL}?{urlencode(params)}", timeout)
    candidates = payload.get("results") or []
    if not candidates:
        return {
            "isbn13": isbn13,
            "query_title": title,
            "match_status": "no_results",
            "data_source": "openalex_live",
            "error": None,
        }

    ranked = []
    for candidate in candidates:
        scores = score_candidate(title, authors, candidate)
        ranked.append((scores["match_score"], candidate, scores))
    _, candidate, scores = max(ranked, key=lambda item: item[0])
    return {
        "isbn13": isbn13,
        "query_title": title,
        "match_status": "matched" if scores["match_score"] >= minimum_score else "low_confidence",
        "data_source": "openalex_live",
        "openalex_id": candidate.get("id"),
        "matched_title": candidate.get("display_name") or candidate.get("title"),
        "doi": candidate.get("doi"),
        "cited_by_count": candidate.get("cited_by_count"),
        "error": None,
        **scores,
    }


def _fixture_rows(catalogue: pd.DataFrame, fixture_path: Path) -> dict[str, dict[str, Any]]:
    if not fixture_path.exists():
        return {}
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    titles = catalogue.set_index("isbn13")["title"].to_dict()
    return {
        str(item["isbn13"]): {
            "isbn13": str(item["isbn13"]),
            "query_title": titles.get(str(item["isbn13"]), ""),
            "match_status": item.get("match_status", "offline_demo"),
            "data_source": "fixture_offline",
            "cited_by_count": item.get("cited_by_count_demo"),
            "error": None,
        }
        for item in payload.get("records", [])
    }


def enrich_catalogue_openalex(
    catalogue: pd.DataFrame,
    *,
    mode: str = "offline",
    fixture_path: str | Path,
    api_key: str | None = None,
    timeout: float = 15.0,
    transport: Callable[[str, float], dict[str, Any]] = _request_json,
) -> pd.DataFrame:
    """Enrich every catalogue row, using live requests or explicit fixtures."""
    if mode not in {"offline", "live"}:
        raise ValueError("openalex mode must be 'offline' or 'live'")
    fixture_rows = _fixture_rows(catalogue, Path(fixture_path))
    rows: list[dict[str, Any]] = []
    for item in catalogue.to_dict("records"):
        isbn13 = str(item["isbn13"])
        if mode == "offline":
            rows.append(fixture_rows.get(isbn13, {
                "isbn13": isbn13,
                "query_title": item["title"],
                "match_status": "not_in_fixture",
                "data_source": "fixture_offline",
                "error": None,
            }))
            continue
        try:
            rows.append(query_openalex(
                isbn13,
                str(item["title"]),
                str(item["authors"]),
                api_key=api_key,
                timeout=timeout,
                transport=transport,
            ))
        except OpenAlexRequestError as exc:
            fallback = fixture_rows.get(isbn13, {
                "isbn13": isbn13,
                "query_title": item["title"],
                "match_status": "request_error",
                "data_source": "openalex_error",
            })
            fallback = dict(fallback)
            if fallback["data_source"] == "fixture_offline":
                fallback["data_source"] = "fixture_fallback"
            fallback["error"] = str(exc)
            rows.append(fallback)
    return pd.DataFrame(rows)
