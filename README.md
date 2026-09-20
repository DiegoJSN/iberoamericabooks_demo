# IberoamericaBooks

> **Portfolio / Demo Version** — branch `demo`

IberoamericaBooks is a Python ETL project that consolidates heterogeneous publishing catalogues, sales records and digital-attention metrics into a normalized SQLite database. It was created for a real data-integration workflow in the Ibero-American book sector.

The original project uses private operational files that cannot be distributed. This branch reproduces the architecture with public bibliographic metadata and deterministic synthetic commercial variables. No private rows, credentials or API keys are included.

The code and data workflow were authored by Diego J. Soler Navarro. AI was used only as limited support for occasional efficiency questions.

## What you can try

- Run the complete ETL and inspect its six stages.
- See how three differently structured Excel sources are normalized and deduplicated.
- Trace every accepted or rejected source row.
- Explore synthetic sales and attention metrics.
- Run safe read-only SQL queries and download the generated SQLite database.

## Recommended: online demo

Deploy `app.py` on [Streamlit Community Cloud](https://streamlit.io/cloud) and add the public URL here. The repository may remain private while the app is public.

> This repository contains private data in older Git history. Do not make the existing repository public. For a public code repository, publish a clean snapshot without the old history.

## Run locally

### Windows

1. Install [Python 3](https://www.python.org/downloads/) and enable **Add Python to PATH** during installation.
2. Download this branch as a ZIP and extract it.
3. Double-click `run_demo.bat`.
4. Wait while the required packages are installed. The browser opens automatically when the application is ready.

### macOS or Linux

```bash
git clone --branch demo --single-branch https://github.com/DiegoJSN/IberoamericaBooks.git
cd IberoamericaBooks
chmod +x run_demo.sh
./run_demo.sh
```

The browser opens automatically when the application is ready. Its local address is `http://localhost:8501`.

## Technical notebook

For a code-first walkthrough, open `notebooks/iberoamerica_books_demo.ipynb` after installing the requirements. It calls the same reusable ETL package as the web app, so the two paths cannot silently diverge.

## Technology

- Python and pandas for ingestion, cleaning and transformation
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
- External enrichment used by the original notebook is represented offline so the demo remains reliable and does not need credentials.
- This reduced dataset demonstrates the workflow, not the scale or business conclusions of the private project.

## Verify

```bash
python -m unittest discover -s tests -v
```
