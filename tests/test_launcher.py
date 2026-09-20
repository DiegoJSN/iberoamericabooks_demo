from pathlib import Path
from unittest import mock
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_demo


class LauncherTests(unittest.TestCase):
    @mock.patch("run_demo.time.sleep")
    @mock.patch("run_demo.urllib.request.urlopen")
    def test_waits_until_health_endpoint_is_ready(self, urlopen, _sleep):
        response = mock.MagicMock()
        response.__enter__.return_value.status = 200
        urlopen.return_value = response
        process = mock.MagicMock(spec=subprocess.Popen)
        process.poll.return_value = None

        run_demo.wait_until_ready(process, timeout_seconds=1)

        urlopen.assert_called_once_with(run_demo.HEALTH_URL, timeout=2)

    def test_reports_early_server_exit(self):
        process = mock.MagicMock(spec=subprocess.Popen)
        process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "cerrado antes"):
            run_demo.wait_until_ready(process, timeout_seconds=1)


if __name__ == "__main__":
    unittest.main()

