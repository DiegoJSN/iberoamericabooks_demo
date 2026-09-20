from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit is not installed in this test environment")
class StreamlitSmokeTest(unittest.TestCase):
    def test_app_renders_without_uncaught_exceptions(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        self.assertGreaterEqual(len(app.metric), 5)


if __name__ == "__main__":
    unittest.main()

