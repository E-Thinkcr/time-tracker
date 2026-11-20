import csv
from datetime import date

import pytest

from timetracker.deteccion import App
from timetracker.tracker import ACTIVO, PAUSA, ErrorTracker, Tracker

PROD = ["Task", "Meeting"]
EXCEL = App("Excel", "excel.exe")
WEB = App("Web", "chrome.exe")


def filas(almacen, dia=date(2026, 11, 18), usuario="ana"):
    ruta = almacen.ruta(usuario, dia)
    if not ruta.exists():
        return []
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def correr(t, reloj, segundos, app=None):
    for _ in range(int(segundos)):
        reloj.avanzar(1)
        t.tick(app)


def nuevo(almacen, reloj, **kw):
    return Tracker("ana", almacen, PROD, reloj=reloj, **kw)


def test_reanudar_no_duplica_tiempo(almacen, reloj):
    """Bug original: pausar 10 min + reanudar 5 min daba 25 min en el reporte."""
    t = nuevo(almacen, reloj)
    t.iniciar("Task", "T-1")
    correr(t, reloj, 600, EXCEL)
    t.pausar()
    assert t.estado == PAUSA
    t.reanudar(0)
    correr(t, reloj, 300, EXCEL)
    assert t.segundos_tarea_actual() == pytest.approx(900)
    t.finalizar_actual()
    total = sum(int(f["segundos"]) for f in filas(almacen))
    assert total == 900
    assert t.totales_dia()["Productiva"] == pytest.approx(900)


def test_tiempo_se_asigna_a_la_app_usada_no_al_tracker(almacen, reloj):
    """Bug original: el sistema se detectaba al hacer clic (siempre la ventana del tracker)."""
    t = nuevo(almacen, reloj)
    t.tick(EXCEL)
    t.iniciar("Task", "T-1")
    correr(t, reloj, 120, EXCEL)
    correr(t, reloj, 60, WEB)
    correr(t, reloj, 30, None)  # None = la propia ventana: no cambia la app
    t.finalizar_actual()
    por_sistema = {}
    for f in filas(almacen):
        por_sistema[f["sistema"]] = por_sistema.get(f["sistema"], 0) + int(f["segundos"])
    # Se muestrea cada segundo: el cambio de app puede caer ±1 s.
    assert set(por_sistema) == {"Excel", "Web"}
    assert abs(por_sistema["Excel"] - 120) <= 1 and abs(por_sistema["Web"] - 90) <= 1
    assert sum(por_sistema.values()) == 210


def test_categorias_y_totales(almacen, reloj):
    t = nuevo(almacen, reloj)
    t.iniciar("Task", "A")
    correr(t, reloj, 60)
    t.finalizar_actual()
    t.iniciar("Lunch", "")
    correr(t, reloj, 30)
    tot = t.totales_dia()
    assert tot["Productiva"] == 60
    assert tot["No productiva"] == pytest.approx(30)
    assert t.actual.tarea_id == "Lunch"  # sin comentario usa el tipo


def test_no_se_puede_iniciar_con_tarea_en_curso(almacen, reloj):
    t = nuevo(almacen, reloj)
    t.iniciar("Task", "A")
    with pytest.raises(ErrorTracker):
        t.iniciar("Meeting", "B")
    with pytest.raises(ErrorTracker):
        t.reanudar(0)


def test_medianoche_parte_el_registro(almacen, reloj):
    reloj.ahora = reloj.ahora.replace(hour=23, minute=59, second=0)
    t = nuevo(almacen, reloj)
    t.iniciar("Task", "Noche")
    correr(t, reloj, 120, EXCEL)
    t.finalizar_actual()
    hoy = filas(almacen, date(2026, 11, 18))
    manana = filas(almacen, date(2026, 11, 19))
    assert sum(int(f["segundos"]) for f in hoy) == 60
    assert hoy[-1]["fin"] == "23:59:59"
    assert sum(int(f["segundos"]) for f in manana) == 60
    assert manana[0]["fecha"] == "2026-11-19"


def test_hueco_por_suspension_no_se_cuenta(almacen, reloj):
    t = nuevo(almacen, reloj, max_hueco_segundos=300)
    t.iniciar("Task", "A")
    correr(t, reloj, 60, EXCEL)
    reloj.avanzar(2 * 3600)  # PC suspendida 2 horas
    t.tick(EXCEL)
    correr(t, reloj, 60, EXCEL)
    t.finalizar_actual()
    assert sum(int(f["segundos"]) for f in filas(almacen)) == 120
    assert t.finalizadas[-1].segundos == pytest.approx(120)


def test_recuperar_sesion_tras_cierre_inesperado(almacen, reloj):
    t = nuevo(almacen, reloj)
    t.iniciar("Task", "T-9")
    correr(t, reloj, 90, EXCEL)
    estado = t.exportar_estado()  # lo último guardado antes del "crash"

    t2 = nuevo(almacen, reloj)
    assert t2.restaurar(estado)
    assert t2.estado == PAUSA
    assert t2.pausadas[0].tarea_id == "T-9"
    assert t2.pausadas[0].segundos_previos == pytest.approx(90)
    assert sum(int(f["segundos"]) for f in filas(almacen)) == 90
    assert t2.totales_dia()["Productiva"] == 90

    t2.reanudar(0)
    assert t2.estado == ACTIVO
    correr(t2, reloj, 10, EXCEL)
    assert t2.segundos_tarea_actual() == pytest.approx(100)


def test_restaurar_ignora_estado_de_otro_usuario(almacen, reloj):
    t = nuevo(almacen, reloj)
    t.iniciar("Task", "A")
    estado = t.exportar_estado()
    otro = Tracker("luis", almacen, PROD, reloj=reloj)
    assert not otro.restaurar(estado)
    assert otro.pausadas == []


def test_totales_sobreviven_reinicio(almacen, reloj):
    t = nuevo(almacen, reloj)
    t.iniciar("Task", "A")
    correr(t, reloj, 300)
    t.finalizar_actual()
    t2 = nuevo(almacen, reloj)
    assert t2.totales_dia()["Total"] == 300


def test_registro_manual(almacen, reloj):
    t = nuevo(almacen, reloj)
    t.registrar_manual("ana", date(2026, 11, 18), "Meeting", "Comité", 45, registrado_por="admin")
    f = filas(almacen)[0]
    assert f["origen"] == "MANUAL" and f["registrado_por"] == "admin"
    assert f["segundos"] == "2700" and f["categoria"] == "Productiva"
    assert t.totales_dia()["Productiva"] == 2700
    with pytest.raises(ErrorTracker):
        t.registrar_manual("ana", date(2026, 11, 18), "Task", "x", 0, registrado_por="admin")
    with pytest.raises(ErrorTracker):
        t.registrar_manual("ana", date(2026, 11, 18), "Task", "x", 2000, registrado_por="admin")


@pytest.mark.parametrize("estado", [
    "basura",
    {"usuario": "ana", "pausadas": [{"tipo": "Task"}]},
    {"usuario": "ana", "pausadas": [{"tipo": "Task", "tarea_id": "x", "segundos_previos": "mucho"}]},
    {"usuario": "ana", "pausadas": "no-es-lista"},
    {"usuario": "ana", "actual": {"tipo": "Task", "tarea_id": "x"}, "segmento": {"inicio": "ayer"}},
])
def test_estado_manipulado_no_rompe_la_app(almacen, reloj, estado):
    t = nuevo(almacen, reloj)
    assert not t.restaurar(estado)
    assert t.pausadas == [] and t.actual is None
    t.iniciar("Task", "ok")  # sigue funcionando
