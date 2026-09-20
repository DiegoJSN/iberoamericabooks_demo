"""Regenerate the semisynthetic source files with a fixed seed.

The XLSX files committed to demo_data are created by this script's data model.
It intentionally does not read any private project file.
"""

from __future__ import annotations

from pathlib import Path
import random

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "demo_data"
SEED = 2026


BOOKS = [
    ("9780307474728", "Cien años de soledad", "Gabriel García Márquez", "Sudamericana", 1967, "Colombia", 471, "es"),
    ("9780307389732", "El amor en los tiempos del cólera", "Gabriel García Márquez", "Oveja Negra", 1985, "Colombia", 368, "es"),
    ("9780525433477", "La casa de los espíritus", "Isabel Allende", "Plaza & Janés", 1982, "Chile", 433, "es"),
    ("9780307950925", "Ficciones", "Jorge Luis Borges", "Sur", 1944, "Argentina", 224, "es"),
    ("9788437604572", "Rayuela", "Julio Cortázar", "Sudamericana", 1963, "Argentina", 736, "es"),
    ("9788437604183", "Pedro Páramo", "Juan Rulfo", "Fondo de Cultura Económica", 1955, "México", 136, "es"),
    ("9780385420174", "Como agua para chocolate", "Laura Esquivel", "Planeta", 1989, "México", 256, "es"),
    ("9788420471839", "La ciudad y los perros", "Mario Vargas Llosa", "Seix Barral", 1963, "Perú", 448, "es"),
    ("9788432216428", "El túnel", "Ernesto Sábato", "Sur", 1948, "Argentina", 160, "es"),
    ("9788420464725", "La tregua", "Mario Benedetti", "Alfa", 1960, "Uruguay", 192, "es"),
    ("9780375716669", "Los detectives salvajes", "Roberto Bolaño", "Anagrama", 1998, "Chile", 624, "es"),
    ("9780143034902", "La sombra del viento", "Carlos Ruiz Zafón", "Planeta", 2001, "España", 576, "es"),
]


def source_url(isbn: str) -> str:
    return f"https://openlibrary.org/isbn/{isbn}"


def make_sales() -> pd.DataFrame:
    randomizer = random.Random(SEED)
    rows = []
    channels = ["Librería", "Web", "Distribuidor"]
    for year in range(2022, 2026):
        for isbn, *_ in BOOKS:
            units = randomizer.randint(4, 42)
            unit_price = randomizer.choice([14.9, 16.5, 18.0, 19.9, 22.0])
            rows.append([isbn, pd.Timestamp(year, randomizer.randint(1, 12), 15), units, round(units * unit_price, 2), randomizer.choice(channels), 1])
    return pd.DataFrame(rows, columns=["isbn13", "sale_date", "units", "revenue_eur", "channel", "synthetic"])


def build_frames() -> dict[str, pd.DataFrame]:
    columns = ["isbn", "title", "authors", "publisher", "year", "country", "pages", "language"]
    base = pd.DataFrame(BOOKS, columns=columns)
    base["source_url"] = base["isbn"].map(source_url)

    simeh = base.iloc[:8].copy()
    simeh.loc[0, "isbn"] = "978-0-307-47472-8"
    simeh.loc[4, "title"] = "RAYUELA"
    invalid = simeh.iloc[[0]].copy()
    invalid.loc[:, "isbn"] = "9780000000001"
    invalid.loc[:, "title"] = "Registro de control con ISBN inválido"
    simeh = pd.concat([simeh, invalid], ignore_index=True)
    simeh.columns = ["ISBN", "Título", "Autoría", "Editorial", "Año", "País", "Páginas", "Idioma", "URL fuente"]

    own = base.iloc[4:].copy()
    own.columns = ["isbn13", "title", "authors", "publisher", "publication_year", "country", "pages", "language", "source_url"]

    scielo = base.iloc[1::2].copy()
    scielo.loc[scielo.index[0], "title"] = "El amor en los tiempos del colera"
    invalid_scielo = scielo.iloc[[0]].copy()
    invalid_scielo.loc[:, "isbn"] = "1234567890123"
    invalid_scielo.loc[:, "title"] = "Otra fila inválida para comprobar la validación"
    scielo = pd.concat([scielo, invalid_scielo], ignore_index=True)
    scielo.columns = ["ISBN-13", "TITULO", "AUTORES", "EDITOR", "PUBLICACION", "PAIS", "PAGINAS", "IDIOMA", "ENLACE"]
    return {"simeh": simeh, "plantilla_propia": own, "scielo": scielo, "ventas": make_sales()}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, frame in build_frames().items():
        frame.to_excel(OUTPUT / f"{filename}.xlsx", index=False)
    print(f"Demo data regenerated in {OUTPUT}")


if __name__ == "__main__":
    main()
