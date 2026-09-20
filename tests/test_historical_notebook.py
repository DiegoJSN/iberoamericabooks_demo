from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = (
    ROOT
    / "notebooks"
    / "archive"
    / "iberoamerica_books_original_sanitized.ipynb"
)


class SanitizedHistoricalNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        cls.cells = cls.payload["cells"]
        cls.text = "\n".join("".join(cell.get("source", [])) for cell in cls.cells)

    def test_preserves_original_structure_with_one_explanatory_header(self):
        self.assertEqual(len(self.cells), 65)
        self.assertEqual(
            sum(cell["cell_type"] == "code" for cell in self.cells), 49
        )
        self.assertEqual(
            sum(cell["cell_type"] == "markdown" for cell in self.cells), 16
        )
        self.assertIn("Historical / Read-only Reference", self.text)
        self.assertIn("1) Creacion de la base de datos", self.text)

    def test_saved_outputs_and_execution_state_are_removed(self):
        for index, cell in enumerate(self.cells):
            with self.subTest(cell=index):
                self.assertNotIn("attachments", cell)
                if cell["cell_type"] == "code":
                    self.assertEqual(cell.get("outputs"), [])
                    self.assertIsNone(cell.get("execution_count"))

    def test_code_cells_still_compile(self):
        for index, cell in enumerate(self.cells):
            if cell["cell_type"] != "code":
                continue
            with self.subTest(cell=index):
                compile("".join(cell["source"]), f"historical-cell-{index}", "exec")

    def test_private_machine_paths_and_literal_isbns_are_absent(self):
        self.assertIsNone(re.search(r"[A-Za-z]:\\Users\\", self.text))
        self.assertIsNone(re.search(r"(?<!\d)\d{13}(?!\d)", self.text))
        self.assertLess(NOTEBOOK.stat().st_size, 1_000_000)


if __name__ == "__main__":
    unittest.main()

