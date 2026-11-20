import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from timetracker.almacen import Almacen  # noqa: E402


class Reloj:
    """Reloj falso para controlar el tiempo en las pruebas."""

    def __init__(self, inicio: datetime):
        self.ahora = inicio

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += timedelta(seconds=segundos)


@pytest.fixture
def reloj():
    return Reloj(datetime(2026, 11, 18, 9, 0, 0))


@pytest.fixture
def almacen(tmp_path):
    return Almacen(tmp_path / "registros")
