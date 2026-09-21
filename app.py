from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
import tempfile

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from iberoamerica_books.database import connect, read_only_query
from iberoamerica_books.pipeline import run_pipeline


st.set_page_config(page_title="IberoamericaBooks", page_icon="📚", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1250px;}
      .eyebrow {letter-spacing:.12em; text-transform:uppercase; font-weight:700; color:#8B2F4B; font-size:.78rem;}
      .hero {padding:1.2rem 1.35rem; border:1px solid #E2D3CA; border-radius:18px; background:linear-gradient(135deg,#FFFDFC,#F4E9E2); margin-bottom:1.2rem;}
      .hero h1 {margin:.15rem 0 .35rem 0; color:#321D25;}
      .muted {color:#6C5A60;}
      .notebook-card {min-height:132px; padding:.2rem .15rem;}
      .notebook-card h3 {margin:.1rem 0 .45rem 0; color:#321D25; font-size:1.15rem;}
      .notebook-card p {margin:0; color:#6C5A60;}
      .step {border-left:4px solid #8B2F4B; padding:.7rem .9rem; background:#FFF; border-radius:0 10px 10px 0; min-height:110px;}
      div[data-testid="stMetric"] {background:#FFF; border:1px solid #E6DDD8; border-radius:12px; padding:.65rem .85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.info(
    "La **aplicación de Streamlit es una interfaz de portfolio para explorar "
    "los resultados del pipeline ETL**. El núcleo del proyecto es el flujo de "
    "procesamiento de datos en Python y la base de datos relacional, que puede "
    "examinarse en detalle en los notebooks técnico y original de desarrollo."
)

technical_notebook, original_notebook = st.columns(2)
with technical_notebook:
    st.markdown(
        """
        <div class="notebook-card">
          <h3>Notebook técnico del ETL</h3>
          <p><strong>Versión funcional y ejecutable.</strong> Reproduce el pipeline con datos públicos de demostración y permite realizar consultas reales a OpenAlex.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "Abrir el notebook técnico del ETL",
        "https://nbviewer.org/github/DiegoJSN/iberoamericabooks_demo/blob/19cf1d83466806b805208d94ac9920a1a29e5c2e/notebooks/iberoamerica_books_demo.ipynb?flush_cache=true",
        icon="📓",
        use_container_width=True,
    )

with original_notebook:
    st.markdown(
        """
        <div class="notebook-card">
          <h3>Notebook original de desarrollo</h3>
          <p>Está pensado principalmente para <strong>examinar el código y el proceso de desarrollo</strong>, no para ejecutarlo directamente, porque los archivos privados originales no se distribuyen.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "Abrir el notebook original de desarrollo",
        "https://nbviewer.org/github/DiegoJSN/iberoamericabooks_demo/blob/19cf1d83466806b805208d94ac9920a1a29e5c2e/notebooks/archive/iberoamerica_books_original_sanitized.ipynb?flush_cache=true",
        icon="🗂️",
        use_container_width=True,
    )

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Portfolio / Demo Version</div>
      <h1>IberoamericaBooks</h1>
      <p>ETL reproducible para integrar catálogos editoriales, ventas y métricas digitales en una base de datos SQLite.</p>
      <p class="muted">La demo usa metadatos bibliográficos públicos y variables comerciales sintéticas. No contiene los archivos privados del proyecto original.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def build_demo():
    temp_dir = Path(tempfile.mkdtemp(prefix="iberoamerica_books_"))
    result = run_pipeline(ROOT / "demo_data", temp_dir / "iberoamerica_books_demo.sqlite")
    return result


try:
    result = build_demo()
except Exception as exc:  # pragma: no cover - defensive UI boundary
    st.error("La demo no pudo preparar la base de datos. Revisa los archivos de demo_data y vuelve a intentarlo.")
    st.exception(exc)
    st.stop()

st.subheader("Resultado del pipeline")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Fuentes", "3")
m2.metric("Filas de entrada", result.metrics["source_rows"])
m3.metric("Libros consolidados", result.metrics["catalogue_books"])
m4.metric("Duplicados detectados", result.metrics["duplicate_rows"])
m5.metric("Ingresos demo", f"{result.metrics['revenue_eur']:,.0f} €")

st.caption("Los ingresos, unidades y métricas digitales son sintéticos y se generan con una semilla fija.")

st.subheader("Cómo funciona")
step_columns = st.columns(3)
for index, row in result.events.iterrows():
    with step_columns[index % 3]:
        st.markdown(
            f"<div class='step'><strong>{row['step_name']}</strong><br>{row['input_rows']} → {row['output_rows']} filas<br><span class='muted'>{row['details']}</span></div>",
            unsafe_allow_html=True,
        )
        st.write("")

catalogue_tab, provenance_tab, sales_tab, database_tab = st.tabs(
    ["Catálogo consolidado", "Trazabilidad", "Ventas sintéticas", "Explorar SQLite"]
)

with catalogue_tab:
    with connect(result.database_path) as connection:
        catalogue = pd.read_sql_query("SELECT * FROM book_summary ORDER BY title", connection)
    country = st.multiselect("Filtrar por país", sorted(catalogue["country"].dropna().unique()))
    visible = catalogue[catalogue["country"].isin(country)] if country else catalogue
    st.dataframe(visible, use_container_width=True, hide_index=True)

with provenance_tab:
    status = st.multiselect("Estado", sorted(result.source_records["valid_isbn"].map({True: "accepted", False: "rejected_invalid_isbn"}).unique()))
    records = result.source_records[["source_name", "source_row", "raw_isbn", "isbn13", "raw_title", "normalized_title", "valid_isbn"]].copy()
    records["status"] = records["valid_isbn"].map({True: "accepted", False: "rejected_invalid_isbn"})
    if status:
        records = records[records["status"].isin(status)]
    st.dataframe(records.drop(columns="valid_isbn"), use_container_width=True, hide_index=True)

with sales_tab:
    sales_by_year = result.sales.assign(year=lambda frame: pd.to_datetime(frame["sale_date"]).dt.year).groupby("year", as_index=False).agg(units=("units", "sum"), revenue_eur=("revenue_eur", "sum"))
    st.bar_chart(sales_by_year.set_index("year")[["revenue_eur"]], x_label="Año", y_label="Ingresos sintéticos (€)")
    st.dataframe(result.sales, use_container_width=True, hide_index=True)

with database_tab:
    st.write("Ejecuta una consulta de solo lectura sobre la base generada por el ETL.")
    examples = {
        "Resumen de catálogo": "SELECT title, authors, publisher, publication_year, units_sold, revenue_eur FROM book_summary ORDER BY revenue_eur DESC",
        "Ventas por canal": "SELECT channel, SUM(units) AS units, ROUND(SUM(revenue_eur), 2) AS revenue_eur FROM sales GROUP BY channel ORDER BY revenue_eur DESC",
        "Procedencia": "SELECT source_name, status, COUNT(*) AS rows FROM source_records GROUP BY source_name, status ORDER BY source_name, status",
    }
    selected = st.selectbox("Consulta de ejemplo", list(examples))
    sql = st.text_area("SQL", value=examples[selected], height=150)
    if st.button("Ejecutar consulta", type="primary"):
        try:
            with connect(result.database_path) as connection:
                columns, rows = read_only_query(connection, sql)
            st.dataframe(pd.DataFrame(rows, columns=columns), use_container_width=True, hide_index=True)
        except (ValueError, sqlite3.Error) as exc:
            st.warning(str(exc))

st.divider()
with open(result.database_path, "rb") as database_file:
    st.download_button(
        "Descargar base SQLite generada",
        data=database_file.read(),
        file_name="iberoamerica_books_demo.sqlite",
        mime="application/vnd.sqlite3",
    )
st.caption("El proyecto original procesaba archivos privados de catálogo y ventas. Este repositorio público conserva el diseño técnico con un conjunto semisintético redistribuible.")

