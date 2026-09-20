"""SQLite schema and safe read-only query helpers."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE publishers (
    publisher_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE authors (
    author_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE books (
    book_id INTEGER PRIMARY KEY,
    normalized_title TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    first_publication_year INTEGER,
    country TEXT
);

CREATE TABLE editions (
    isbn13 TEXT PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books(book_id),
    publisher_id INTEGER REFERENCES publishers(publisher_id),
    publication_year INTEGER,
    pages INTEGER,
    language TEXT,
    source_count INTEGER NOT NULL,
    source_names TEXT NOT NULL,
    source_url TEXT
);

CREATE TABLE book_authors (
    book_id INTEGER NOT NULL REFERENCES books(book_id),
    author_id INTEGER NOT NULL REFERENCES authors(author_id),
    PRIMARY KEY (book_id, author_id)
);

CREATE TABLE sales (
    sale_id INTEGER PRIMARY KEY,
    isbn13 TEXT NOT NULL REFERENCES editions(isbn13),
    sale_date TEXT NOT NULL,
    units INTEGER NOT NULL CHECK (units >= 0),
    revenue_eur REAL NOT NULL CHECK (revenue_eur >= 0),
    channel TEXT NOT NULL,
    synthetic INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE altmetrics (
    isbn13 TEXT PRIMARY KEY REFERENCES editions(isbn13),
    mentions INTEGER NOT NULL,
    readers INTEGER NOT NULL,
    demo_score REAL NOT NULL,
    synthetic INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE openalex_enrichment (
    isbn13 TEXT PRIMARY KEY REFERENCES editions(isbn13),
    query_title TEXT NOT NULL,
    match_status TEXT NOT NULL,
    data_source TEXT NOT NULL,
    openalex_id TEXT,
    matched_title TEXT,
    doi TEXT,
    cited_by_count INTEGER,
    title_score REAL,
    author_score REAL,
    match_score REAL,
    error TEXT
);

CREATE TABLE source_records (
    source_record_id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    raw_isbn TEXT,
    normalized_isbn TEXT,
    raw_title TEXT,
    normalized_title TEXT,
    status TEXT NOT NULL
);

CREATE TABLE pipeline_events (
    event_id INTEGER PRIMARY KEY,
    step_name TEXT NOT NULL,
    input_rows INTEGER NOT NULL,
    output_rows INTEGER NOT NULL,
    details TEXT NOT NULL
);

CREATE VIEW book_summary AS
WITH author_rollup AS (
    SELECT ba.book_id, GROUP_CONCAT(a.name, '; ') AS authors
    FROM book_authors ba
    JOIN authors a ON a.author_id = ba.author_id
    GROUP BY ba.book_id
),
sales_rollup AS (
    SELECT isbn13, SUM(units) AS units_sold, ROUND(SUM(revenue_eur), 2) AS revenue_eur
    FROM sales
    GROUP BY isbn13
)
SELECT
    e.isbn13,
    b.title,
    ar.authors,
    p.name AS publisher,
    e.publication_year,
    b.country,
    e.pages,
    e.source_count,
    COALESCE(sr.units_sold, 0) AS units_sold,
    COALESCE(sr.revenue_eur, 0) AS revenue_eur,
    COALESCE(am.mentions, 0) AS mentions,
    COALESCE(am.readers, 0) AS readers,
    COALESCE(am.demo_score, 0) AS demo_score,
    oa.openalex_id,
    oa.doi AS openalex_doi,
    oa.cited_by_count AS openalex_citations,
    oa.match_status AS openalex_match_status,
    oa.data_source AS openalex_data_source
FROM editions e
JOIN books b ON b.book_id = e.book_id
LEFT JOIN author_rollup ar ON ar.book_id = b.book_id
LEFT JOIN publishers p ON p.publisher_id = e.publisher_id
LEFT JOIN sales_rollup sr ON sr.isbn13 = e.isbn13
LEFT JOIN altmetrics am ON am.isbn13 = e.isbn13
LEFT JOIN openalex_enrichment oa ON oa.isbn13 = e.isbn13
;
"""


@contextmanager
def connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


def initialise(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)


def read_only_query(connection: sqlite3.Connection, sql: str, limit: int = 200) -> tuple[list[str], list[tuple]]:
    """Execute one SELECT/CTE statement and cap the visible result."""
    stripped = sql.strip().rstrip(";")
    if ";" in stripped or not stripped.lower().startswith(("select", "with")):
        raise ValueError("La demo solo permite una consulta SELECT o WITH.")
    cursor = connection.execute(f"SELECT * FROM ({stripped}) LIMIT ?", (limit,))
    columns = [item[0] for item in cursor.description or []]
    return columns, [tuple(row) for row in cursor.fetchall()]
