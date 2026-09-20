from pathlib import Path
import sys
import unittest
from urllib.parse import parse_qs, urlparse

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iberoamerica_books.openalex import enrich_catalogue_openalex, query_openalex, score_candidate


class OpenAlexTests(unittest.TestCase):
    def test_candidate_score_prioritises_title_and_authors(self):
        candidate = {
            "display_name": "Cien años de soledad",
            "authorships": [{"author": {"display_name": "Gabriel García Márquez"}}],
        }
        scores = score_candidate("Cien años de soledad", "Gabriel García Márquez", candidate)
        self.assertEqual(scores["match_score"], 1.0)

    def test_live_query_uses_openalex_works_search(self):
        seen = {}

        def transport(url, timeout):
            seen["url"] = url
            seen["timeout"] = timeout
            return {
                "results": [{
                    "id": "https://openalex.org/W123",
                    "doi": "https://doi.org/10.1234/demo",
                    "display_name": "Cien años de soledad",
                    "cited_by_count": 42,
                    "authorships": [{"author": {"display_name": "Gabriel García Márquez"}}],
                    "type": "book",
                }]
            }

        result = query_openalex(
            "9780307474728",
            "Cien años de soledad",
            "Gabriel García Márquez",
            timeout=3,
            transport=transport,
        )
        params = parse_qs(urlparse(seen["url"]).query)
        self.assertEqual(urlparse(seen["url"]).path, "/works")
        self.assertEqual(params["search"], ["Cien años de soledad"])
        self.assertEqual(params["filter"], ["type:book"])
        self.assertEqual(result["data_source"], "openalex_live")
        self.assertEqual(result["match_status"], "matched")
        self.assertEqual(result["cited_by_count"], 42)

    def test_offline_mode_never_calls_transport(self):
        catalogue = pd.DataFrame([{
            "isbn13": "9780307474728",
            "title": "Cien años de soledad",
            "authors": "Gabriel García Márquez",
        }])

        def forbidden_transport(url, timeout):  # pragma: no cover - assertion helper
            raise AssertionError("offline mode attempted a network request")

        result = enrich_catalogue_openalex(
            catalogue,
            mode="offline",
            fixture_path=ROOT / "fixtures" / "openalex_cache.json",
            transport=forbidden_transport,
        )
        self.assertEqual(result.iloc[0]["data_source"], "fixture_offline")


if __name__ == "__main__":
    unittest.main()
