"""Start the local demo and open the browser only when Streamlit is ready."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser


URL = "http://127.0.0.1:8501"
HEALTH_URL = f"{URL}/_stcore/health"


def wait_until_ready(process: subprocess.Popen[bytes], timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Streamlit se ha cerrado antes de iniciar la aplicación.")
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise TimeoutError("La aplicación no ha terminado de cargar después de 120 segundos.")


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        "--server.port=8501",
    ]
    process = subprocess.Popen(command)
    try:
        wait_until_ready(process)
        print(f"La demo está lista: {URL}")
        webbrowser.open(URL, new=2)
        return process.wait()
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, TimeoutError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())

