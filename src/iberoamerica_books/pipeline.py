"""End-to-end ETL from heterogeneous demo files to a normalized SQLite DB."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

import pandas as pd

from .cleaning import clean_isbn, is_valid_isbn13, normalize_text, split_authors
from .database import connect, initialise
from .openalex import enrich_catalogue_openalex


SOURCE_SPECS = {
    "simeh": {
        "filename": "simeh.xlsx",
        "rename": {"ISBN": "isbn", "Título": "title", "Autoría": "authors", "Editorial": "publisher", "Año": "year", "País": "country", "Páginas": "pages", "Idioma": "language", "URL fuente": "source_url"},
    },
    "plantilla_propia": {
        "filename": "plantilla_propia.xlsx",
        "rename": {"isbn13": "isbn", "title": "title", "authors": "authors", "publisher": "publisher", "publication_year": "year", "country": "country", "pages": "pages", "language": "language", "source_url": "source_url"},
    },
    "scielo": {
        "filename": "scielo.xlsx",
        "rename": {"ISBN-13": "isbn", "TITULO": "title", "AUTORES": "authors", "EDITOR": "publisher", "PUBLICACION": "year", "PAIS": "country", "PAGINAS": "pages", "IDIOMA": "language", "ENLACE": "source_url"},
    },
}

SOURCE_PRIORITY = {"plantilla_propia": 0, "simeh": 1, "scielo": 2}


@dataclass(frozen=True)
class PipelineResult:
    database_path: Path
    catalogue: pd.DataFrame
    sales: pd.DataFrame
    altmetrics: pd.DataFrame
    openalex: pd.DataFrame
    source_records: pd.DataFrame
    events: pd.DataFrame
    metrics: dict[str, int | float]


def _read_sources(data_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source_name, spec in SOURCE_SPECS.items():
        frame = pd.read_excel(data_dir / spec["filename"]).rename(columns=spec["rename"])
        frame = frame[["isbn", "title", "authors", "publisher", "year", "country", "pages", "language", "source_url"]].copy()
        frame["source_name"] = source_name
        frame["source_row"] = range(2, len(frame) + 2)
        frame["raw_isbn"] = frame["isbn"].astype(str)
        frame["raw_title"] = frame["title"].astype(str)
        frame["isbn13"] = frame["isbn"].map(clean_isbn)
        frame["normalized_title"] = frame["title"].map(normalize_text)
        frame["valid_isbn"] = frame["isbn13"].map(is_valid_isbn13)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _canonical_catalogue(records: pd.DataFrame) -> pd.DataFrame:
    valid = records.loc[records["valid_isbn"]].copy()
    valid["priority"] = valid["source_name"].map(SOURCE_PRIORITY)
    valid = valid.sort_values(["isbn13", "priority", "source_row"])
    canonical = valid.groupby("isbn13", as_index=False).first()
    provenance = valid.groupby("isbn13").agg(
        source_count=("source_name", "nunique"),
        source_names=("source_name", lambda values: ", ".join(sorted(set(values)))),
    )
    canonical = canonical.drop(columns=["source_count", "source_names"], errors="ignore").merge(provenance, on="isbn13", how="left")
    return canonical[["isbn13", "title", "normalized_title", "authors", "publisher", "year", "country", "pages", "language", "source_url", "source_count", "source_names"]]


def _get_or_create(connection: sqlite3.Connection, table: str, id_column: str, name: str) -> int:
    connection.execute(f"INSERT OR IGNORE INTO {table}(name) VALUES (?)", (name,))
    row = connection.execute(f"SELECT {id_column} FROM {table} WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise RuntimeError(f"Could not create {table}: {name}")
    return int(row[0])


def _load_database(
    connection: sqlite3.Connection,
    catalogue: pd.DataFrame,
    sales: pd.DataFrame,
    altmetrics: pd.DataFrame,
    openalex: pd.DataFrame,
    records: pd.DataFrame,
) -> None:
    for item in catalogue.to_dict("records"):
        publisher_id = _get_or_create(connection, "publishers", "publisher_id", str(item["publisher"]))
        connection.execute(
            "INSERT INTO books(normalized_title, title, first_publication_year, country) VALUES (?, ?, ?, ?)",
            (item["normalized_title"], item["title"], int(item["year"]), item["country"]),
        )
        book_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        connection.execute(
            "INSERT INTO editions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item["isbn13"], book_id, publisher_id, int(item["year"]), int(item["pages"]), item["language"], int(item["source_count"]), item["source_names"], item["source_url"]),
        )
        for author in split_authors(item["authors"]):
            author_id = _get_or_create(connection, "authors", "author_id", author)
            connection.execute("INSERT INTO book_authors VALUES (?, ?)", (book_id, author_id))

    sales_rows = sales[["isbn13", "sale_date", "units", "revenue_eur", "channel", "synthetic"]].itertuples(index=False, name=None)
    connection.executemany("INSERT INTO sales(isbn13, sale_date, units, revenue_eur, channel, synthetic) VALUES (?, ?, ?, ?, ?, ?)", sales_rows)
    altmetric_rows = altmetrics[["isbn13", "mentions", "readers", "demo_score", "synthetic"]].itertuples(index=False, name=None)
    connection.executemany("INSERT INTO altmetrics VALUES (?, ?, ?, ?, ?)", altmetric_rows)

    openalex_columns = [
        "isbn13", "query_title", "match_status", "data_source", "openalex_id",
        "matched_title", "doi", "cited_by_count", "title_score", "author_score",
        "match_score", "error",
    ]
    prepared_openalex = openalex.reindex(columns=openalex_columns).where(pd.notna(openalex), None)
    connection.executemany(
        "INSERT INTO openalex_enrichment VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        prepared_openalex.itertuples(index=False, name=None),
    )

    source_rows = [
        (
            row.source_name,
            int(row.source_row),
            row.raw_isbn,
            row.isbn13,
            row.raw_title,
            row.normalized_title,
            "accepted" if row.valid_isbn else "rejected_invalid_isbn",
        )
        for row in records.itertuples()
    ]
    connection.executemany(
        "INSERT INTO source_records(source_name, source_row, raw_isbn, normalized_isbn, raw_title, normalized_title, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        source_rows,
    )


def run_pipeline(
    data_dir: str | Path,
    database_path: str | Path,
    *,
    openalex_mode: str = "offline",
    openalex_api_key: str | None = None,
    openalex_timeout: float = 15.0,
) -> PipelineResult:
    data_dir = Path(data_dir)
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        database_path.unlink()

    records = _read_sources(data_dir)
    catalogue = _canonical_catalogue(records)
    sales = pd.read_excel(data_dir / "ventas.xlsx")
    sales.columns = ["isbn13", "sale_date", "units", "revenue_eur", "channel", "synthetic"]
    sales["isbn13"] = sales["isbn13"].map(clean_isbn)
    sales["sale_date"] = pd.to_datetime(sales["sale_date"]).dt.strftime("%Y-%m-%d")
    sales = sales[sales["isbn13"].isin(catalogue["isbn13"])].copy()
    altmetrics = pd.read_csv(data_dir / "altmetrics.csv", dtype={"isbn13": str})
    altmetrics["isbn13"] = altmetrics["isbn13"].map(clean_isbn)
    altmetrics = altmetrics[altmetrics["isbn13"].isin(catalogue["isbn13"])].copy()
    openalex = enrich_catalogue_openalex(
        catalogue,
        mode=openalex_mode,
        fixture_path=data_dir.parent / "fixtures" / "openalex_cache.json",
        api_key=openalex_api_key,
        timeout=openalex_timeout,
    )

    duplicate_rows = int(records.loc[records["valid_isbn"]].duplicated("isbn13", keep=False).sum())
    invalid_rows = int((~records["valid_isbn"]).sum())
    events = pd.DataFrame(
        [
            ("1. Ingesta", len(records), len(records), "Lectura de tres fuentes con esquemas diferentes."),
            ("2. Normalización", len(records), len(records), "ISBN, títulos y procedencia normalizados sin sobrescribir los datos brutos."),
            ("3. Validación", len(records), int(records["valid_isbn"].sum()), f"{invalid_rows} filas rechazadas por ISBN-13 no válido."),
            ("4. Deduplicación", int(records["valid_isbn"].sum()), len(catalogue), f"{duplicate_rows} filas pertenecen a ISBN presentes en más de una fuente."),
            (
                "5. Enriquecimiento",
                len(catalogue),
                len(catalogue),
                f"Ventas y atención digital unidas por ISBN; OpenAlex ejecutado en modo {openalex_mode}.",
            ),
            ("6. Persistencia", len(catalogue), len(catalogue), "Modelo relacional escrito en SQLite con claves foráneas."),
        ],
        columns=["step_name", "input_rows", "output_rows", "details"],
    )

    with connect(database_path) as connection:
        initialise(connection)
        _load_database(connection, catalogue, sales, altmetrics, openalex, records)
        connection.executemany("INSERT INTO pipeline_events(step_name, input_rows, output_rows, details) VALUES (?, ?, ?, ?)", events.itertuples(index=False, name=None))
        connection.commit()

    metrics: dict[str, int | float] = {
        "source_rows": int(len(records)),
        "catalogue_books": int(len(catalogue)),
        "invalid_rows": invalid_rows,
        "duplicate_rows": duplicate_rows,
        "sales_rows": int(len(sales)),
        "units_sold": int(sales["units"].sum()),
        "revenue_eur": float(round(sales["revenue_eur"].sum(), 2)),
        "openalex_live_rows": int((openalex["data_source"] == "openalex_live").sum()),
        "openalex_matched_rows": int((openalex["match_status"] == "matched").sum()),
    }
    return PipelineResult(database_path, catalogue, sales, altmetrics, openalex, records, events, metrics)
