from pathlib import Path
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iberoamerica_books.cleaning import clean_isbn, is_valid_isbn13, normalize_text
from iberoamerica_books.database import connect, read_only_query
from iberoamerica_books.pipeline import run_pipeline


class CleaningTests(unittest.TestCase):
    def test_isbn_cleanup_and_checksum(self):
        self.assertEqual(clean_isbn("978-0-307-47472-8"), "9780307474728")
        self.assertTrue(is_valid_isbn13("978-0-307-47472-8"))
        self.assertFalse(is_valid_isbn13("978-0-307-47472-9"))

    def test_text_normalization(self):
        self.assertEqual(normalize_text(" Cien años de soledad "), "cien anos de soledad")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.db_path = ROOT / ".test_pipeline.sqlite"
        self.db_path.unlink(missing_ok=True)
        self.result = run_pipeline(ROOT / "demo_data", self.db_path)

    def tearDown(self):
        self.db_path.unlink(missing_ok=True)

    def test_pipeline_outputs_are_deterministic(self):
        self.assertEqual(self.result.metrics["catalogue_books"], 12)
        self.assertGreater(self.result.metrics["duplicate_rows"], 0)
        self.assertEqual(self.result.metrics["invalid_rows"], 2)

    def test_foreign_keys_and_summary_view(self):
        with connect(self.db_path) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM book_summary").fetchone()[0], 12)

    def test_query_helper_blocks_writes(self):
        with connect(self.db_path) as connection:
            with self.assertRaises(ValueError):
                read_only_query(connection, "DELETE FROM books")
            columns, rows = read_only_query(connection, "SELECT title FROM books ORDER BY title")
            self.assertEqual(columns, ["title"])
            self.assertEqual(len(rows), 12)


if __name__ == "__main__":
    unittest.main()
