"""Inicia o Vectis Rates Terminal (API + frontend) localmente e abre o
navegador na página funcional.

Uso:
    python scripts/run_terminal.py
"""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import uvicorn  # noqa: E402

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}/"


def _open_browser() -> None:
    webbrowser.open(URL)


def main() -> None:
    threading.Timer(1.5, _open_browser).start()
    print(f"Vectis Rates Terminal em {URL} (Ctrl+C para encerrar)")
    uvicorn.run("vectis.api:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
