from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "iberoamerica_books_demo.ipynb"


class NotebookDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        cls.text = "\n".join(
            "".join(cell.get("source", [])) for cell in cls.payload["cells"]
        )

    def test_notebook_keeps_detailed_etl_sections(self):
        required = [
            "Creación y diseño de la base de datos",
            "Dataframe SIMEH",
            "Dataframe de plantilla propia",
            "Dataframe SciELO",
            "Limpiando la base de datos",
            "Duplicados entre instituciones",
            "OpenAlex API — consulta real",
            "Auditoría de la base resultante",
            "Limitaciones y trabajo pendiente",
        ]
        for heading in required:
            with self.subTest(heading=heading):
                self.assertIn(heading, self.text)

    def test_database_ddl_is_visible_in_notebook(self):
        for statement in [
            "CREATE TABLE publishers",
            "CREATE TABLE openalex_enrichment",
            "CREATE TABLE source_records",
            "CREATE VIEW book_summary",
        ]:
            with self.subTest(statement=statement):
                self.assertIn(statement, self.text)

    def test_all_code_cells_compile(self):
        code_cells = [
            cell for cell in self.payload["cells"] if cell["cell_type"] == "code"
        ]
        self.assertGreaterEqual(len(code_cells), 25)
        for index, cell in enumerate(code_cells, start=1):
            with self.subTest(code_cell=index):
                compile("".join(cell["source"]), f"notebook-cell-{index}", "exec")

    def test_openalex_live_mode_is_explicit(self):
        self.assertIn('OPENALEX_MODE = "live"', self.text)
        self.assertIn("openalex_mode=OPENALEX_MODE", self.text)

    def test_streamlit_links_to_an_immutable_notebook_snapshot(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("nbviewer.org/github/DiegoJSN/iberoamericabooks_demo/blob/", app_source)
        self.assertNotIn("blob/main/notebooks/iberoamerica_books_demo.ipynb", app_source)
        self.assertIn("Ver el notebook original saneado", app_source)
        self.assertIn(
            "notebooks/archive/iberoamerica_books_original_sanitized.ipynb",
            app_source,
        )
        self.assertNotIn(
            "blob/main/notebooks/archive/iberoamerica_books_original_sanitized.ipynb",
            app_source,
        )
        self.assertIn("flush_cache=true", app_source)


if __name__ == "__main__":
    unittest.main()

