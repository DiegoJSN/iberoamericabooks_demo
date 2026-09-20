# IberoamericaBooks

> **Portfolio / Demo Version** — public repository on `main`

IberoamericaBooks is a Python ETL project that consolidates heterogeneous publishing catalogues, sales records and digital-attention metrics into a normalized SQLite database. It was created for a real data-integration workflow in the Ibero-American book sector.

The original project uses private operational files that cannot be distributed. This branch reproduces the architecture with public bibliographic metadata and deterministic synthetic commercial variables. No private rows, credentials or API keys are included.

The code and data workflow were authored by Diego J. Soler Navarro. AI was used only as limited support for occasional efficiency questions.

## What you can try

- Run the complete ETL and inspect its six stages.
- See how three differently structured Excel sources are normalized and deduplicated.
- Trace every accepted or rejected source row.
- Explore synthetic sales and attention metrics.
- Run live OpenAlex enrichment from the technical notebook, with an explicit offline fallback.
- Run safe read-only SQL queries and download the generated SQLite database.

## Recommended: online demo

Open the public demo—no installation or account required:

**[Launch IberoamericaBooks on Streamlit](https://iberoamerica-books-etl.streamlit.app/)**

To inspect the complete technical workflow—ingestion, normalization, validation, deduplication, enrichment and SQLite persistence—open the rendered notebook:

**[View the ETL workflow in Jupyter Notebook](https://nbviewer.org/github/DiegoJSN/iberoamericabooks_demo/blob/main/notebooks/iberoamerica_books_demo.ipynb)**

This is a sanitized public repository. It contains only redistributable semisynthetic demo data; the private operational sources and their history are not included.

## Run locally

### Windows

1. Install [Python 3](https://www.python.org/downloads/) and enable **Add Python to PATH** during installation.
2. Download this repository as a ZIP and extract it.
3. Double-click `run_demo.bat`.
4. Wait while the required packages are installed. The browser opens automatically when the application is ready.

### macOS or Linux

```bash
git clone https://github.com/DiegoJSN/iberoamericabooks_demo.git
cd iberoamericabooks_demo
chmod +x run_demo.sh
./run_demo.sh
```

The browser opens automatically when the application is ready. Its local address is `http://localhost:8501`.

## Technical notebook

The [rendered Jupyter Notebook](https://nbviewer.org/github/DiegoJSN/iberoamericabooks_demo/blob/main/notebooks/iberoamerica_books_demo.ipynb) provides a code-first walkthrough. It calls the same reusable ETL package as the web app, so the two paths cannot silently diverge.

When executed, the notebook queries the OpenAlex `/works` API for every catalogue record and stores the selected candidate, DOI, citation count, source and matching scores in SQLite. Basic use does not require a key. An optional key can be supplied only through the `OPENALEX_API_KEY` environment variable; no secret is stored in the repository. If the service is unavailable, the affected rows use an explicitly labelled fixture fallback so the ETL can still finish.

## Technology

- Python and pandas for ingestion, cleaning and transformation
- OpenAlex REST API for live bibliographic enrichment in the notebook
- SQLite for the normalized relational model
- Streamlit for the interactive portfolio demo
- Excel and CSV as heterogeneous source formats
- `unittest` for deterministic pipeline checks

```text
app.py                         Streamlit interface
src/iberoamerica_books/       Cleaning, ETL and SQLite logic
demo_data/                    Redistributable semisynthetic sources
notebooks/                    Reproducible technical walkthrough
scripts/create_demo_data.py   Fixed-seed data generator
tests/                        Critical pipeline checks
```

## Data and limitations

- Bibliographic examples link to Open Library records for provenance.
- Sales, revenue, attention metrics and invalid control rows are synthetic.
- The notebook uses live OpenAlex results, which can change over time; its fallback and the Streamlit demo's default mode remain offline for reliability.
- WorldCat and Altmetric are documented as parts of the original workflow but are not called with private credentials in this public demo.
- This reduced dataset demonstrates the workflow, not the scale or business conclusions of the private project.

## Verify

```bash
python -m unittest discover -s tests -v
```
