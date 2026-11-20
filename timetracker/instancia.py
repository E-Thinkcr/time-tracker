"""Evita abrir la app dos veces (dos instancias contarían el mismo tiempo dos veces)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import IO


def adquirir(base: Path) -> IO | None:
    """Devuelve el archivo de bloqueo (mantenerlo abierto) o None si ya hay otra instancia."""
    f = open(base / "app.lock", "a+")
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f
