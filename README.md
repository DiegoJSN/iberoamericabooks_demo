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

**[Launch IberoamericaBooks on Streamlit](https://iberoamericabooks-etl.streamlit.app/)**

To inspect the complete technical workflow—ingestion, normalization, validation, deduplication, enrichment and SQLite persistence—open the rendered notebook:

**[View the ETL workflow in Jupyter Notebook](https://nbviewer.org/github/DiegoJSN/iberoamericabooks_demo/blob/820e4232260668a7cbff0fc1d3d52ceebe9d0691/notebooks/iberoamerica_books_demo.ipynb?flush_cache=true)**

To inspect the project as it was developed, including the original sequence of diagnoses, cleaning decisions and exploratory code, open the near-verbatim historical copy:

**[View the sanitized original development notebook](https://nbviewer.org/github/DiegoJSN/iberoamericabooks_demo/blob/9b9bbd6c73ba8041267d1d10f567ba1f938b99be/notebooks/archive/iberoamerica_books_original_sanitized.ipynb?flush_cache=true)**

This historical reference preserves the original notebook structure and code. Only saved outputs, execution metadata, private row examples, internal identifiers and private report names were removed or replaced. Because the private source workbooks are not distributed, it is intended for inspection rather than execution.

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

The [rendered Jupyter Notebook](https://nbviewer.org/github/DiegoJSN/iberoamericabooks_demo/blob/820e4232260668a7cbff0fc1d3d52ceebe9d0691/notebooks/iberoamerica_books_demo.ipynb?flush_cache=true) provides a detailed code-first walkthrough. It shows the complete SQLite DDL, diagnoses every source dataframe, documents the fields that need cleaning, resolves validation and deduplication decisions step by step, and audits the final database. It calls the same reusable ETL package as the web app, so the two paths cannot silently diverge.

When executed, the notebook queries the OpenAlex `/works` API for every catalogue record and stores the selected candidate, DOI, citation count, source and matching scores in SQLite. Basic use does not require a key. An optional key can be supplied only through the `OPENALEX_API_KEY` environment variable; no secret is stored in the repository. If the service is unavailable, the affected rows use an explicitly labelled fixture fallback so the ETL can still finish.

The [sanitized original development notebook](https://nbviewer.org/github/DiegoJSN/iberoamericabooks_demo/blob/9b9bbd6c73ba8041267d1d10f567ba1f938b99be/notebooks/archive/iberoamerica_books_original_sanitized.ipynb?flush_cache=true) is also available as a historical, read-only reference. Unlike the reproducible demo notebook above, it retains the original long-form development workflow and therefore depends on private input files that are not part of this repository.

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
notebooks/                    Reproducible walkthrough and sanitized historical notebook
scripts/create_demo_data.py   Fixed-seed data generator
scripts/build_notebook.py     Reproducible detailed notebook builder
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

