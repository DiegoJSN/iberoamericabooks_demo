"""Build the detailed, reproducible portfolio notebook.

The notebook is generated from plain strings so its structure can be reviewed and
tested without depending on Jupyter at build time.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iberoamerica_books.database import SCHEMA  # noqa: E402


def _source(text: str) -> list[str]:
    return text.strip("\n").splitlines(keepends=True)


def markdown(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": _source(text)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _source(text),
    }


cells = [
    markdown(r"""
# IberoamericaBooks — ETL bibliográfico razonado paso a paso

> **Portfolio / Demo Version**

Este notebook conserva la estructura analítica del notebook original: primero diseña la base de datos, después diagnostica cada fuente por separado, documenta qué debe limpiarse, aplica reglas de normalización y validación, resuelve duplicados, consulta OpenAlex y finalmente persiste y audita el resultado.

La longitud es deliberada. El objetivo no es esconder el trabajo tras una interfaz, sino hacer visibles las decisiones, los controles y las limitaciones de un ETL real. Los archivos privados del proyecto original se sustituyen por fuentes públicas y datos semisintéticos reproducibles.
"""),
    markdown(r"""
## Contexto, alcance y diferencias respecto al original

El proyecto original integraba ficheros operativos de SIMEH, una plantilla editorial propia, SciELO, informes comerciales y exportaciones de métricas. Aquellos archivos no pueden publicarse. La demo conserva:

- el problema de esquemas incompatibles;
- la normalización de ISBN, títulos, autores, países e idiomas;
- el diagnóstico previo de cada dataframe;
- la validación y cuarentena de filas erróneas;
- la deduplicación con prioridad de fuentes y trazabilidad;
- el modelo relacional en SQLite;
- el enriquecimiento bibliográfico real mediante OpenAlex;
- los controles de integridad y consultas SQL finales.

No se conservan filas privadas ni credenciales. Ventas y atención digital son sintéticas y están identificadas como tales.
"""),
    markdown(r"""
## Arquitectura del workflow

```text
SIMEH ──────────────┐
Plantilla propia ───┼──> diagnóstico ─> staging común ─> validación ISBN
SciELO ─────────────┘                              │
                                                   v
                          resolución de conflictos y deduplicación
                                                   │
Ventas semisintéticas ─────────────────────────────┤
Altmetric semisintético ───────────────────────────┤
OpenAlex API real ─────────────────────────────────┤
                                                   v
                                      modelo relacional SQLite
                                                   │
                                                   v
                                   auditoría y consultas reproducibles
```
"""),
    markdown(r"""
## 0) Preparación del entorno

Todas las rutas son relativas al repositorio. El notebook funciona tanto desde la raíz como desde `notebooks/` y no contiene rutas del ordenador del autor.
"""),
    code(r"""
from pathlib import Path
import os
import sqlite3
import sys

import pandas as pd
try:
    from IPython.display import display
except ImportError:  # Permite validar el notebook sin instalar Jupyter.
    display = print

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))

from iberoamerica_books.cleaning import clean_isbn, is_valid_isbn13, normalize_text
from iberoamerica_books.database import connect, read_only_query
from iberoamerica_books.pipeline import (
    SOURCE_PRIORITY,
    SOURCE_SPECS,
    _canonical_catalogue,
    _read_sources,
    run_pipeline,
)

DATA_DIR = ROOT / "demo_data"
FIXTURES_DIR = ROOT / "fixtures"
DATABASE_PATH = ROOT / "iberoamerica_books_demo.sqlite"

assert DATA_DIR.exists(), f"No se encuentra la carpeta de datos: {DATA_DIR}"
print("Raíz del proyecto:", ROOT)
print("Archivos demo:", sorted(path.name for path in DATA_DIR.iterdir()))
"""),
    markdown(r"""
# 1) Creación y diseño de la base de datos

El notebook original comenzaba diseñando la base de datos antes de cargar datos. Se conserva esa decisión porque obliga a definir entidades, cardinalidades y restricciones antes de transformar los Excel.

## 1.1 Decisiones de modelado

- `books` representa la obra intelectual normalizada.
- `editions` representa una edición identificada por ISBN-13.
- `authors` y `publishers` evitan repetir nombres en cada registro.
- `book_authors` resuelve la relación muchos-a-muchos entre obras y autores.
- `sales` conserva observaciones comerciales en relación uno-a-muchos con una edición.
- `altmetrics` contiene indicadores sintéticos de la demo.
- `openalex_enrichment` conserva tanto el resultado como la calidad y procedencia del match.
- `source_records` mantiene trazabilidad de cada fila original, incluso si fue rechazada.
- `pipeline_events` permite auditar cuántas filas entran y salen de cada fase.

La vista `book_summary` facilita consultas sin desnormalizar las tablas maestras.
"""),
    markdown(r"""
## 1.2 Relaciones

```text
publishers 1 ─────── N editions N ─────── 1 books
                            │                  │
                            │                  N
                            │                  │
                            │                  N
                            │               authors
                            │          (mediante book_authors)
                            │
                            ├── 1:N sales
                            ├── 1:1 altmetrics
                            └── 1:1 openalex_enrichment

source_records y pipeline_events actúan como capa de auditoría.
```
"""),
    markdown(r"""
## 1.3 DDL completo

Este es el código SQL que **diseña realmente la base de datos**. No se oculta tras la aplicación web. Incluye claves primarias, claves foráneas, restricciones, tablas de trazabilidad y la vista final.
"""),
    code("NOTEBOOK_SCHEMA = r'''\n" + SCHEMA.strip() + "\n'''\n\nprint(NOTEBOOK_SCHEMA)"),
    markdown(r"""
## 1.4 Validación del diseño antes de ingerir datos

Se crea una base en memoria para comprobar que el DDL es válido y que SQLite reconoce las tablas, la vista y las claves foráneas previstas. Así se separan los errores de modelado de los errores posteriores de limpieza.
"""),
    code(r"""
with sqlite3.connect(":memory:") as schema_check:
    schema_check.executescript(NOTEBOOK_SCHEMA)
    schema_objects = pd.read_sql_query(
        "SELECT type, name FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name",
        schema_check,
    )
    foreign_keys = pd.concat(
        [
            pd.read_sql_query(f"PRAGMA foreign_key_list({table})", schema_check)
            .rename(columns={"table": "referenced_table"})
            .assign(source_table=table)
            for table in ["editions", "book_authors", "sales", "altmetrics", "openalex_enrichment"]
        ],
        ignore_index=True,
    )

display(schema_objects)
display(foreign_keys[["source_table", "from", "referenced_table", "to"]])
"""),
    markdown(r"""
# 2) Dataframes: lectura y diagnóstico por fuente

Antes de limpiar, se conserva una copia de cada dataframe bruto. Para cada fuente se revisan:

1. dimensiones y nombres de columnas;
2. tipos inferidos;
3. valores ausentes y cadenas vacías;
4. duplicados exactos;
5. ISBN con caracteres invisibles, guiones o checksum inválido;
6. cardinalidad y valores sospechosos en campos categóricos;
7. inconsistencias que solo aparecen al comparar fuentes.

Este diagnóstico previo evita aplicar una misma regla a fuentes con significados distintos.
"""),
    code(r"""
def diagnose_dataframe(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    # Resumen reproducible de calidad por columna, sin modificar el dataframe.
    blank_counts = {
        column: int(frame[column].map(lambda value: isinstance(value, str) and not value.strip()).sum())
        for column in frame.columns
    }
    samples = {
        column: " | ".join(frame[column].dropna().astype(str).drop_duplicates().head(3))
        for column in frame.columns
    }
    diagnosis = pd.DataFrame({
        "columna": frame.columns,
        "dtype_inferido": [str(frame[column].dtype) for column in frame.columns],
        "nulos": [int(frame[column].isna().sum()) for column in frame.columns],
        "cadenas_vacias": [blank_counts[column] for column in frame.columns],
        "valores_distintos": [int(frame[column].nunique(dropna=True)) for column in frame.columns],
        "muestra": [samples[column] for column in frame.columns],
    })
    print(f"{name}: {len(frame)} filas × {len(frame.columns)} columnas")
    print("Duplicados exactos:", int(frame.duplicated().sum()))
    return diagnosis


def audit_isbn(series: pd.Series) -> pd.DataFrame:
    audit = pd.DataFrame({"isbn_original": series.astype(str)})
    audit["representacion"] = audit["isbn_original"].map(repr)
    audit["isbn_limpio"] = audit["isbn_original"].map(clean_isbn)
    audit["longitud"] = audit["isbn_limpio"].str.len()
    audit["checksum_valido"] = audit["isbn_limpio"].map(is_valid_isbn13)
    return audit
"""),
    markdown(r"""
## 2.1 Dataframe SIMEH

SIMEH era la principal fuente del proyecto original. En sus archivos privados aparecían continuaciones de fila, separadores inconsistentes, fechas completas o años, THEMA repartido entre filas, resúmenes fragmentados y editoriales repetidas.

### Información a limpiar o comprobar

- eliminar filas totalmente vacías y convertir espacios en valores ausentes;
- retirar caracteres invisibles, espacios y guiones del ISBN;
- comprobar longitud, prefijo y checksum ISBN-13;
- homogeneizar autores separados por `|` o `;`;
- normalizar espacios alrededor de separadores;
- extraer el año cuando una fecha viene como `dd/mm/yyyy`;
- consolidar valores repetidos de BISAC, THEMA, Dewey y palabras clave;
- recomponer resúmenes o categorías que ocupan varias filas;
- separar editorial principal de coeditoriales;
- detectar títulos o ISBN ausentes antes de cargar;
- conservar siempre la fila y el archivo de procedencia para poder informar de errores a la institución.

La fuente pública reducida no reproduce todos esos campos privados, pero sí incluye un ISBN con guiones, caracteres invisibles, variantes de mayúsculas y una fila de control inválida.
"""),
    code(r"""
simeh_raw = pd.read_excel(DATA_DIR / "simeh.xlsx", dtype=object)
display(simeh_raw)
display(diagnose_dataframe(simeh_raw, "SIMEH"))
"""),
    code(r"""
simeh_isbn_diagnosis = audit_isbn(simeh_raw["ISBN"])
display(simeh_isbn_diagnosis)

print("Años observados:", sorted(simeh_raw["Año"].dropna().astype(int).unique()))
print("Idiomas observados:", sorted(simeh_raw["Idioma"].dropna().astype(str).unique()))
print("Países observados:", sorted(simeh_raw["País"].dropna().astype(str).unique()))
"""),
    markdown(r"""
## 2.2 Dataframe de plantilla propia

En el archivo original, una fila podía contener `ISBN IMPRESO`, `ISBN PDF` e `ISBN EPUB`. La limpieza transformaba esa estructura ancha en una fila por edición y conservaba el DOI solo en el registro principal para evitar duplicarlo artificialmente.

### Información a limpiar o comprobar

- filtrar el intervalo temporal definido por el proyecto original;
- convertir columnas múltiples de ISBN a formato largo;
- asignar `impreso`, `pdf` o `ebook` según la columna de origen;
- evitar duplicar el DOI al expandir ediciones;
- unificar autores escritos como `Apellidos, Nombre` y `Nombre Apellidos`;
- limpiar espacios alrededor de `;` en autores, editores, compiladores y coordinadores;
- limpiar palabras clave y valores vacíos;
- comprobar que cada fila final contiene un único ISBN válido.

La versión pública ya se entrega en formato largo para no simular ediciones inexistentes, pero se validan las mismas invariantes.
"""),
    code(r"""
propia_raw = pd.read_excel(DATA_DIR / "plantilla_propia.xlsx", dtype=object)
display(propia_raw)
display(diagnose_dataframe(propia_raw, "Plantilla propia"))
display(audit_isbn(propia_raw["isbn13"]))

assert propia_raw["isbn13"].map(clean_isbn).is_unique
print("Cada fila de la plantilla demo representa una única edición.")
"""),
    markdown(r"""
## 2.3 Dataframe SciELO

SciELO utiliza un esquema diferente y, en el proyecto original, incluía estructuras serializadas para creadores, colecciones e información comercial.

### Información a limpiar o comprobar

- decidir entre `eisbn` e `isbn`, dando prioridad a la edición electrónica;
- convertir `publication_date` de `yyyy-mm-dd` a año;
- interpretar la lista de `creators`, extraer rol y nombre y traducir roles;
- invertir cuidadosamente `Apellido, Nombre`, sin alterar los nombres que ya vienen en orden natural;
- decodificar países ISO 3166-1 e idiomas ISO 639-1;
- extraer el título de la colección de una estructura serializada;
- extraer el identificador DOI de su URL;
- normalizar tiendas como Amazon, Google Play o Kobo;
- validar el ISBN antes de crear relaciones en la base.

La fuente demo simplifica los objetos anidados, pero conserva nombres de columnas distintos, una variante ortográfica sin tilde y una fila de ISBN inválido.
"""),
    code(r"""
scielo_raw = pd.read_excel(DATA_DIR / "scielo.xlsx", dtype=object)
display(scielo_raw)
display(diagnose_dataframe(scielo_raw, "SciELO"))
display(audit_isbn(scielo_raw["ISBN-13"]))
"""),
    markdown(r"""
## 2.4 Comparación de esquemas

Los tres dataframes representan conceptos equivalentes con vocabularios distintos. El mapeo se declara de forma explícita: si una institución cambia una columna, el ETL falla de manera visible en lugar de mezclar datos silenciosamente.
"""),
    code(r"""
schema_mapping_rows = []
for source_name, spec in SOURCE_SPECS.items():
    for original, canonical in spec["rename"].items():
        schema_mapping_rows.append({
            "fuente": source_name,
            "columna_original": original,
            "campo_staging": canonical,
        })

schema_mapping = pd.DataFrame(schema_mapping_rows)
display(schema_mapping.pivot(index="campo_staging", columns="fuente", values="columna_original"))
"""),
    markdown(r"""
## 2.5 Dataframe de ventas

En el proyecto original los informes de la librería comenzaban después de varias filas informativas. El algoritmo debía localizar la cabecera, comprobar que el informe cubría un año natural completo y extraer el año del texto `Desde ... Hasta ...`.

### Información a limpiar o comprobar

- localizar la cabecera sin depender de un número fijo de fila;
- verificar el periodo temporal completo;
- convertir fechas y cantidades a tipos adecuados;
- convertir cantidades negativas —errores detectados en origen— en valores ausentes o cuarentena;
- estandarizar tiendas y canales (`AMAZON.COM`, `GOOGLE BOOKS`, `KOBO.COM`);
- evitar cargar dos veces la misma combinación ISBN, año, canal, tienda y país;
- rechazar ventas cuyo ISBN no existe en el catálogo;
- distinguir claramente las ventas sintéticas de esta demo.
"""),
    code(r"""
sales_raw = pd.read_excel(DATA_DIR / "ventas.xlsx", dtype={"isbn13": object})
display(sales_raw.head(12))
display(diagnose_dataframe(sales_raw, "Ventas"))

sales_diagnosis = pd.DataFrame({
    "control": [
        "cantidades negativas",
        "ingresos negativos",
        "fechas no interpretables",
        "filas duplicadas",
        "filas marcadas como sintéticas",
    ],
    "filas": [
        int((pd.to_numeric(sales_raw["units"], errors="coerce") < 0).sum()),
        int((pd.to_numeric(sales_raw["revenue_eur"], errors="coerce") < 0).sum()),
        int(pd.to_datetime(sales_raw["sale_date"], errors="coerce").isna().sum()),
        int(sales_raw.duplicated().sum()),
        int((sales_raw["synthetic"] == 1).sum()),
    ],
})
display(sales_diagnosis)
"""),
    markdown(r"""
## 2.6 Dataframe Altmetric

El proyecto original exportaba una lista de ISBN para solicitar métricas y después incorporaba menciones en noticias, blogs, políticas públicas, patentes, redes sociales, Wikipedia, Mendeley y Dimensions.

### Información a limpiar o comprobar

- convertir el ISBN a texto antes de normalizarlo, evitando notación científica;
- ignorar filas sin ISBN;
- verificar que el ISBN pertenece al catálogo;
- convertir métricas a valores numéricos;
- diferenciar cero de valor desconocido;
- impedir que una exportación repetida duplique una edición.

En esta demo las métricas son sintéticas y deterministas. No deben interpretarse como datos reales de Altmetric.
"""),
    code(r"""
altmetrics_raw = pd.read_csv(DATA_DIR / "altmetrics.csv", dtype={"isbn13": str})
display(altmetrics_raw)
display(diagnose_dataframe(altmetrics_raw, "Altmetric semisintético"))

metric_columns = ["mentions", "readers", "demo_score"]
print("Métricas no numéricas:", {
    column: int(pd.to_numeric(altmetrics_raw[column], errors="coerce").isna().sum())
    for column in metric_columns
})
"""),
    markdown(r"""
# 3) Limpiando la base de datos

El notebook original cargaba cada fuente y después estandarizaba valores dentro de SQLite. La versión pública introduce una capa `staging` anterior a la carga. Esto conserva los valores originales, permite explicar cada modificación y evita que una actualización destructiva borre la única evidencia disponible.

La fase se divide en:

1. unificación de esquemas;
2. conservación de campos brutos;
3. normalización de ISBN y texto;
4. validación y cuarentena;
5. diagnóstico de categorías;
6. detección de duplicados y conflictos;
7. selección del registro canónico;
8. controles de integridad;
9. estandarización SQL posterior a la carga.
"""),
    markdown(r"""
## 3.1 Capa de staging: conservar antes de transformar

Cada fila recibe `source_name` y `source_row`. Además se conservan `raw_isbn` y `raw_title`. Los campos normalizados se añaden en columnas nuevas; no reemplazan al dato original.
"""),
    code(r"""
records = _read_sources(DATA_DIR)

staging_columns = [
    "source_name", "source_row", "raw_isbn", "isbn13",
    "raw_title", "normalized_title", "authors", "publisher",
    "year", "country", "language", "valid_isbn",
]
display(records[staging_columns].head(15))
print("Filas de staging:", len(records))
"""),
    markdown(r"""
## 3.2 Normalización del ISBN

Un ISBN puede contener guiones, espacios o caracteres Unicode invisibles. La función conserva únicamente dígitos —y `X` para posibles ISBN-10— y luego aplica el checksum ISBN-13, no solo una comprobación superficial de longitud.
"""),
    code(r"""
isbn_examples = pd.DataFrame({
    "valor_original": [
        "\u200b978-0-307-47472-8",
        "9780307474728",
        "1234567890123",
        None,
    ]
})
isbn_examples["valor_normalizado"] = isbn_examples["valor_original"].map(clean_isbn)
isbn_examples["checksum_valido"] = isbn_examples["valor_normalizado"].map(is_valid_isbn13)
display(isbn_examples)
"""),
    markdown(r"""
## 3.3 Filas inválidas y cuarentena

El original exportaba los ISBN erróneos a un Excel para comunicarlos a las instituciones. La demo conserva la misma idea mediante `source_records`: la fila no entra en el catálogo, pero no desaparece del historial de auditoría.
"""),
    code(r"""
validation_summary = (
    records.assign(estado=records["valid_isbn"].map({True: "aceptado", False: "rechazado"}))
    .groupby(["source_name", "estado"], as_index=False)
    .size()
    .rename(columns={"size": "filas"})
)
display(validation_summary)

rejected_rows = records.loc[~records["valid_isbn"], [
    "source_name", "source_row", "raw_isbn", "isbn13", "raw_title"
]]
display(rejected_rows)
"""),
    markdown(r"""
## 3.4 Normalización de títulos

La comparación elimina tildes, puntuación redundante, diferencias de mayúsculas y espacios repetidos. Se utiliza para comparar, nunca para mostrar al usuario: el título legible se conserva.
"""),
    code(r"""
title_examples = pd.DataFrame({
    "titulo_original": [
        "RAYUELA",
        "El amor en los tiempos del cólera",
        "El amor en los tiempos del colera",
        "  Pedro   Páramo ",
    ]
})
title_examples["titulo_normalizado"] = title_examples["titulo_original"].map(normalize_text)
display(title_examples)
"""),
    markdown(r"""
## 3.5 Diagnóstico de categorías antes de estandarizar

El notebook original inspeccionaba primero los valores distintos y después aplicaba equivalencias explícitas. Esa práctica evita reemplazos globales difíciles de auditar.

Problemas encontrados originalmente:

- países completos frente a códigos ISO (`Brasil` / `BR`);
- idiomas completos frente a ISO 639-1 (`Español`, `Spanish`, `es`);
- formatos (`print` / `impreso`);
- tipos de obra (`Monograph` / `monografía`);
- tiendas (`Amazon`, `AMAZON.COM`, `Google Play`, `GOOGLE BOOKS`);
- roles (`translator`, `traductor`, `organizador`, `compilador`);
- autores genéricos escritos con distintas mayúsculas (`Varios autores`).
"""),
    code(r"""
categorical_diagnosis = []
for column in ["country", "language", "publisher"]:
    for source_name, values in records.groupby("source_name")[column]:
        categorical_diagnosis.append({
            "campo": column,
            "fuente": source_name,
            "valores": "; ".join(sorted(values.dropna().astype(str).unique())),
        })

display(pd.DataFrame(categorical_diagnosis))
"""),
    markdown(r"""
### Política de estandarización conservada del original

```sql
-- Países e idiomas legibles
UPDATE books    SET country = 'Brasil'  WHERE UPPER(TRIM(country)) = 'BR';
UPDATE editions SET language = 'Español' WHERE LOWER(TRIM(language)) IN ('es', 'spanish');
UPDATE editions SET language = 'Inglés'  WHERE LOWER(TRIM(language)) IN ('en', 'english');
UPDATE editions SET language = 'Portugués' WHERE LOWER(TRIM(language)) IN ('pt', 'portuguese');

-- Ejemplos del modelo operativo original
-- print -> impreso
-- Monograph / Monográfica / Monográfico -> monografía
-- Amazon -> AMAZON.COM; Google Play -> GOOGLE BOOKS; Kobo Books -> KOBO.COM
-- translator -> traductor; organizer / organizador -> compilador
```

La demo no inventa categorías ausentes. Documenta la regla y solo modifica un valor cuando la variante aparece realmente.
"""),
    markdown(r"""
## 3.6 Duplicados entre instituciones

Un ISBN repetido entre fuentes no es necesariamente un error: representa la misma edición observada por varias instituciones. Primero se muestran todos los candidatos y sus diferencias; solo después se escoge un registro canónico.
"""),
    code(r"""
valid_records = records.loc[records["valid_isbn"]].copy()
duplicate_isbns = valid_records.loc[
    valid_records.duplicated("isbn13", keep=False), "isbn13"
].unique()

duplicate_candidates = (
    valid_records.loc[valid_records["isbn13"].isin(duplicate_isbns), [
        "isbn13", "source_name", "raw_title", "normalized_title",
        "authors", "publisher", "year", "country", "language",
    ]]
    .sort_values(["isbn13", "source_name"])
)
display(duplicate_candidates)
print("ISBN presentes en más de una fuente:", len(duplicate_isbns))
"""),
    markdown(r"""
## 3.7 Diagnóstico de conflictos

Para cada ISBN repetido se cuenta cuántas variantes existen en los campos principales. Esto diferencia una repetición idéntica de un conflicto real —por ejemplo, una tilde ausente o un nombre editorial diferente—.
"""),
    code(r"""
conflict_report = (
    valid_records.loc[valid_records["isbn13"].isin(duplicate_isbns)]
    .groupby("isbn13")
    .agg(
        fuentes=("source_name", "nunique"),
        variantes_titulo_bruto=("raw_title", "nunique"),
        variantes_titulo_normalizado=("normalized_title", "nunique"),
        variantes_autores=("authors", "nunique"),
        variantes_editorial=("publisher", "nunique"),
        variantes_pais=("country", "nunique"),
    )
    .reset_index()
)
display(conflict_report)
"""),
    markdown(r"""
## 3.8 Regla de precedencia y catálogo canónico

La decisión es explícita y determinista:

1. `plantilla_propia`, por ser el esquema controlado por el proyecto;
2. `simeh`;
3. `scielo`.

La prioridad decide qué representación visible se conserva, pero `source_count`, `source_names` y `source_records` mantienen toda la procedencia. Cambiar la regla solo exige modificar `SOURCE_PRIORITY`.
"""),
    code(r"""
display(pd.DataFrame(
    sorted(SOURCE_PRIORITY.items(), key=lambda item: item[1]),
    columns=["fuente", "prioridad"],
))

catalogue = _canonical_catalogue(records)
display(catalogue)
"""),
    markdown(r"""
## 3.9 Controles de integridad antes de cargar

Estas aserciones convierten supuestos del diseño en comprobaciones ejecutables. Si una fuente futura rompe una regla, el pipeline debe detenerse antes de producir una base incoherente.
"""),
    code(r"""
integrity_checks = {
    "ISBN canónico único": bool(catalogue["isbn13"].is_unique),
    "Todos los ISBN tienen checksum válido": bool(catalogue["isbn13"].map(is_valid_isbn13).all()),
    "No hay títulos normalizados vacíos": bool(catalogue["normalized_title"].ne("").all()),
    "Cada fila conserva su fuente": bool(records["source_name"].notna().all()),
    "Cada fila conserva su posición original": bool(records["source_row"].notna().all()),
    "No se pierden filas: aceptadas + rechazadas = staging": (
        int(records["valid_isbn"].sum()) + int((~records["valid_isbn"]).sum()) == len(records)
    ),
}
display(pd.DataFrame(integrity_checks.items(), columns=["control", "resultado"]))
assert all(integrity_checks.values())
"""),
    markdown(r"""
## 3.10 Limpieza de ventas y métricas frente al catálogo

Los datos auxiliares se normalizan por ISBN y se filtran mediante una unión con el catálogo. Así no se crean ventas o métricas huérfanas.
"""),
    code(r"""
sales_clean = sales_raw.copy()
sales_clean["isbn13"] = sales_clean["isbn13"].map(clean_isbn)
sales_clean["sale_date"] = pd.to_datetime(sales_clean["sale_date"], errors="coerce")
sales_clean["units"] = pd.to_numeric(sales_clean["units"], errors="coerce")
sales_clean["revenue_eur"] = pd.to_numeric(sales_clean["revenue_eur"], errors="coerce")
sales_clean = sales_clean.loc[
    sales_clean["isbn13"].isin(catalogue["isbn13"])
    & sales_clean["sale_date"].notna()
    & sales_clean["units"].ge(0)
    & sales_clean["revenue_eur"].ge(0)
].copy()

altmetrics_clean = altmetrics_raw.copy()
altmetrics_clean["isbn13"] = altmetrics_clean["isbn13"].map(clean_isbn)
altmetrics_clean = altmetrics_clean.loc[
    altmetrics_clean["isbn13"].isin(catalogue["isbn13"])
].copy()

display(pd.DataFrame({
    "dataset": ["ventas", "altmetrics"],
    "filas_brutas": [len(sales_raw), len(altmetrics_raw)],
    "filas_limpias": [len(sales_clean), len(altmetrics_clean)],
    "ISBN_huérfanos": [
        int((~sales_raw["isbn13"].map(clean_isbn).isin(catalogue["isbn13"])).sum()),
        int((~altmetrics_raw["isbn13"].map(clean_isbn).isin(catalogue["isbn13"])).sum()),
    ],
}))
"""),
    markdown(r"""
# 4) APIs e integraciones externas

El notebook original analizaba OpenAlex, Altmetric y WorldCat. En la demo pública solo OpenAlex se consulta en vivo sin credenciales obligatorias. Altmetric usa un fixture sintético y WorldCat queda documentado porque su acceso requiere condiciones que no son apropiadas para una demo anónima.
"""),
    markdown(r"""
## 4.1 OpenAlex API — consulta real

OpenAlex no garantiza una búsqueda directa de libros por el ISBN de esta fuente, por lo que se conserva el algoritmo razonado del original:

1. tomar título y autores del catálogo;
2. usar como búsqueda la parte principal anterior a `:` o `.` para reducir falsos negativos;
3. consultar `/works` filtrando `type:book`;
4. normalizar títulos y autores;
5. puntuar cada candidato con 80 % de peso para el título y 20 % para autores;
6. seleccionar el candidato con mayor puntuación;
7. clasificarlo como `matched`, `low_confidence` o `no_results`;
8. guardar OpenAlex ID, DOI, citas, puntuaciones, fuente y cualquier error.

### Riesgos conocidos

- un título abreviado puede aumentar recall y reducir precisión;
- volúmenes distintos con el mismo título principal y autor pueden confundirse;
- traducciones y reediciones pueden tener títulos diferentes;
- las citas cambian con el tiempo;
- un DOI repetido para títulos distintos requiere revisión manual;
- una indisponibilidad de red activa un fallback explícitamente etiquetado, nunca presentado como live.
"""),
    code(r"""
OPENALEX_MODE = "live"
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY")  # Opcional; nunca se guarda en GitHub.

print("Modo OpenAlex:", OPENALEX_MODE)
print("API key configurada:", bool(OPENALEX_API_KEY))
"""),
    markdown(r"""
## 4.2 Altmetric

El flujo original generaba un fichero de ISBN, solicitaba una exportación y actualizaba numerosas columnas de menciones y lectores. La demo conserva el paso de unión por ISBN, pero usa `altmetrics.csv` semisintético para no distribuir datos privados ni depender de una cuenta externa.

Los campos `synthetic = 1` y la documentación impiden confundirlos con mediciones reales.
"""),
    markdown(r"""
## 4.3 WorldCat

El notebook original llegó a prototipar WorldCat Search API para localizar bibliotecas que conservaban una edición. El acceso depende de suscripción/autorización y de la región del endpoint. Por ello esta demo no simula una respuesta ni incluye credenciales.

Se conserva la decisión de diseño: una futura integración alimentaría una tabla `libraries` relacionada con `editions`, registrando biblioteca, país, año de incorporación y procedencia.
"""),
    markdown(r"""
# 5) Ejecución completa y persistencia

Ahora se ejecuta el mismo paquete reutilizable que emplea la aplicación Streamlit. En el notebook se activa `live` para que OpenAlex forme parte real del ETL; la web conserva `offline` por defecto para ofrecer una demo estable.
"""),
    code(r"""
result = run_pipeline(
    DATA_DIR,
    DATABASE_PATH,
    openalex_mode=OPENALEX_MODE,
    openalex_api_key=OPENALEX_API_KEY,
)

display(pd.DataFrame.from_dict(result.metrics, orient="index", columns=["valor"]))
display(result.events)
print("Base generada en:", result.database_path)
"""),
    markdown(r"""
## 5.1 Resultado del enriquecimiento OpenAlex

La procedencia se muestra fila a fila. `openalex_live` significa respuesta real de la API; `fixture_fallback` significa que la consulta falló y se usó el fixture solo para permitir que terminara el pipeline.
"""),
    code(r"""
openalex_columns = [
    "isbn13", "query_title", "match_status", "data_source",
    "matched_title", "doi", "cited_by_count", "title_score",
    "author_score", "match_score", "error",
]
display(result.openalex.reindex(columns=openalex_columns))
"""),
    markdown(r"""
## 5.2 Limpieza posterior dentro de SQLite

Se conserva la idea del apartado original “Limpiando la base de datos”: inspeccionar valores distintos y aplicar reglas idempotentes. Estas sentencias no alteran la semántica de la demo; solo normalizan variantes si aparecen en futuras fuentes.
"""),
    code(r"""
POST_LOAD_STANDARDISATION_SQL = r'''
UPDATE books SET country = 'Brasil' WHERE UPPER(TRIM(country)) = 'BR';
UPDATE books SET country = 'Perú' WHERE LOWER(TRIM(country)) = 'peru';

UPDATE editions SET language = 'Español'
WHERE LOWER(TRIM(language)) IN ('es', 'spanish', 'español / castellano');
UPDATE editions SET language = 'Inglés'
WHERE LOWER(TRIM(language)) IN ('en', 'english', 'inglés');
UPDATE editions SET language = 'Portugués'
WHERE LOWER(TRIM(language)) IN ('pt', 'portuguese', 'português');

UPDATE sales SET channel = 'AMAZON.COM' WHERE channel = 'Amazon';
UPDATE sales SET channel = 'GOOGLE BOOKS' WHERE channel IN ('Google Play', 'Google Books');
UPDATE sales SET channel = 'KOBO.COM' WHERE channel = 'Kobo Books';
'''

with connect(result.database_path) as connection:
    before = {
        "paises": [row[0] for row in connection.execute("SELECT DISTINCT country FROM books ORDER BY country")],
        "idiomas": [row[0] for row in connection.execute("SELECT DISTINCT language FROM editions ORDER BY language")],
        "canales": [row[0] for row in connection.execute("SELECT DISTINCT channel FROM sales ORDER BY channel")],
    }
    connection.executescript(POST_LOAD_STANDARDISATION_SQL)
    connection.commit()
    after = {
        "paises": [row[0] for row in connection.execute("SELECT DISTINCT country FROM books ORDER BY country")],
        "idiomas": [row[0] for row in connection.execute("SELECT DISTINCT language FROM editions ORDER BY language")],
        "canales": [row[0] for row in connection.execute("SELECT DISTINCT channel FROM sales ORDER BY channel")],
    }

display(pd.DataFrame({"campo": before.keys(), "antes": before.values(), "después": after.values()}))
"""),
    markdown(r"""
# 6) Auditoría de la base resultante

La auditoría verifica que el resultado físico coincide con lo razonado en los dataframes: objetos creados, integridad referencial, filas por tabla, registros rechazados y consistencia del catálogo.
"""),
    code(r"""
with connect(result.database_path) as connection:
    objects = pd.read_sql_query(
        "SELECT type, name FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name",
        connection,
    )
    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    table_counts = []
    for table in [
        "publishers", "authors", "books", "editions", "book_authors",
        "sales", "altmetrics", "openalex_enrichment", "source_records", "pipeline_events",
    ]:
        count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        table_counts.append({"tabla": table, "filas": count})

display(objects)
display(pd.DataFrame(table_counts))
print("Errores de claves foráneas:", foreign_key_errors)
assert not foreign_key_errors
"""),
    code(r"""
with connect(result.database_path) as connection:
    source_audit = pd.read_sql_query(
        r'''
        SELECT source_name, status, COUNT(*) AS rows
        FROM source_records
        GROUP BY source_name, status
        ORDER BY source_name, status
        ''',
        connection,
    )
    summary = pd.read_sql_query(
        "SELECT * FROM book_summary ORDER BY title",
        connection,
    )

display(source_audit)
display(summary)
"""),
    markdown(r"""
# 7) Consultas SQL de ejemplo

El modelo relacional debe responder preguntas sin volver a abrir los Excel. Las consultas se ejecutan mediante un helper que solo permite `SELECT` o `WITH` y limita el número de filas visibles.
"""),
    markdown(r"""
## 7.1 Autores con más ediciones asociadas
"""),
    code(r"""
query = r'''
SELECT
    a.name AS autor,
    COUNT(DISTINCT e.isbn13) AS cantidad_isbn13,
    GROUP_CONCAT(DISTINCT b.title) AS titulos
FROM authors a
JOIN book_authors ba ON ba.author_id = a.author_id
JOIN books b ON b.book_id = ba.book_id
JOIN editions e ON e.book_id = b.book_id
GROUP BY a.author_id, a.name
ORDER BY cantidad_isbn13 DESC, autor
LIMIT 5
'''

with connect(result.database_path) as connection:
    columns, rows = read_only_query(connection, query)
display(pd.DataFrame(rows, columns=columns))
"""),
    markdown(r"""
## 7.2 Libros con mayor ingreso sintético
"""),
    code(r"""
query = r'''
SELECT title, authors, publisher, units_sold, revenue_eur
FROM book_summary
ORDER BY revenue_eur DESC, title
LIMIT 5
'''

with connect(result.database_path) as connection:
    columns, rows = read_only_query(connection, query)
display(pd.DataFrame(rows, columns=columns))
"""),
    markdown(r"""
## 7.3 Ventas sintéticas por canal
"""),
    code(r"""
query = r'''
SELECT channel, SUM(units) AS units, ROUND(SUM(revenue_eur), 2) AS revenue_eur
FROM sales
GROUP BY channel
ORDER BY revenue_eur DESC
'''

with connect(result.database_path) as connection:
    columns, rows = read_only_query(connection, query)
display(pd.DataFrame(rows, columns=columns))
"""),
    markdown(r"""
## 7.4 Trazabilidad y estado de OpenAlex
"""),
    code(r"""
query = r'''
SELECT
    title,
    isbn13,
    source_count,
    source_names,
    openalex_match_status,
    openalex_data_source,
    openalex_citations
FROM book_summary
ORDER BY source_count DESC, title
'''

with connect(result.database_path) as connection:
    columns, rows = read_only_query(connection, query)
display(pd.DataFrame(rows, columns=columns))
"""),
    markdown(r"""
# 8) Limitaciones y trabajo pendiente

Como en el notebook original, la calidad final está limitada por las fuentes:

- un mismo autor puede aparecer con un apellido, dos apellidos, tratamiento académico o texto entre paréntesis;
- `Varios autores` no identifica personas y no debería fusionarse automáticamente con autores reales;
- una editorial puede aparecer con siglas, nombre completo o sufijos institucionales;
- título + autores reduce duplicados, pero no identifica inequívocamente una obra;
- ediciones, traducciones y volúmenes pueden compartir un título principal;
- los matches de OpenAlex de baja confianza requieren revisión humana;
- las citas de OpenAlex cambian y no son un resultado determinista;
- las ventas y métricas de atención de esta demo son sintéticas;
- WorldCat y Altmetric no se consultan con credenciales privadas;
- el dataset público demuestra lógica y trazabilidad, no la escala ni las conclusiones comerciales del proyecto privado.

Posibles extensiones razonables: identificadores persistentes de autor, tabla de alias editoriales, revisión manual de conflictos, versionado de ejecuciones y pruebas de regresión con casos reales anonimizados.
"""),
    markdown(r"""
# 9) Conclusión

La demo no se limita a producir una tabla final. Hace visible el recorrido completo: diagnóstico de cada fuente, decisiones de limpieza, conservación de valores brutos, reglas de validación, resolución de conflictos, diseño relacional, consulta externa, persistencia y auditoría.

La aplicación Streamlit sirve para explorar el resultado. Este notebook documenta **cómo y por qué** se construye.
"""),
]


notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

output = ROOT / "notebooks" / "iberoamerica_books_demo.ipynb"
output.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"Notebook generated: {output} ({len(cells)} cells)")
