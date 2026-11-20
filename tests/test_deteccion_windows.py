import sys

import pytest

from timetracker import deteccion


@pytest.mark.skipif(sys.platform != "win32", reason="solo Windows")
def test_ventana_activa_no_falla_en_windows():
    info = deteccion.ventana_activa()
    assert info is None or isinstance(info, deteccion.InfoVentana)


@pytest.mark.skipif(sys.platform == "win32", reason="fuera de Windows")
def test_fuera_de_windows_devuelve_none():
    assert deteccion.ventana_activa() is None
