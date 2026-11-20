"""Registros en CSV, uno por usuario y por día: registros/registros_<usuario>_<fecha>.csv

- Cada segmento se agrega al cerrarse (modo append): si la app se cae no se pierde el día.
- Un archivo por usuario evita choques si varios equipos escriben en una carpeta compartida.
- Sin filas de totales: Power BI calcula los totales con medidas.
- Columna "segundos" entera para no depender del separador decimal regional.
"""
from __future__ import annotations

import csv
import logging
import re
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

CAMPOS = [
    "fecha", "usuario", "inicio", "fin", "tipo_tarea", "tarea_id", "categoria",
    "sistema", "proceso", "titulo", "segundos", "minutos", "origen", "registrado_por",
]
_CAMPOS_TEXTO = {"usuario", "tipo_tarea", "tarea_id", "sistema", "proceso", "titulo", "registrado_por"}
_INICIO_PELIGROSO = ("=", "+", "-", "@", "\t", "\r")


def limpiar_celda(valor: str) -> str:
    """Evita "inyección de fórmulas" si alguien abre el CSV en Excel
    (p. ej. un título de ventana que empiece con '=')."""
    valor = " ".join(str(valor).split())
    if valor.startswith(_INICIO_PELIGROSO):
        return "'" + valor
    return valor


def nombre_seguro(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", texto)[:64] or "_"


class Almacen:
    def __init__(self, carpeta: Path):
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(parents=True, exist_ok=True)

    def ruta(self, usuario: str, fecha: date) -> Path:
        return self.carpeta / f"registros_{nombre_seguro(usuario)}_{fecha.isoformat()}.csv"

    def agregar(self, fila: dict) -> None:
        fecha = date.fromisoformat(fila["fecha"])
        ruta = self.ruta(fila["usuario"], fecha)
        nueva = not ruta.exists() or ruta.stat().st_size == 0
        limpia = {
            k: (limpiar_celda(fila.get(k, "")) if k in _CAMPOS_TEXTO else fila.get(k, ""))
            for k in CAMPOS
        }
        # utf-8-sig: Excel muestra bien tildes y ñ. Python no repite el BOM al agregar.
        with open(ruta, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            if nueva:
                w.writeheader()
            w.writerow(limpia)

    def leer_totales(self, usuario: str, fecha: date) -> dict[str, float]:
        """Segundos por categoría ya guardados ese día (para mostrar totales tras reiniciar)."""
        totales = {"Productiva": 0.0, "No productiva": 0.0}
        ruta = self.ruta(usuario, fecha)
        if not ruta.exists():
            return totales
        try:
            with open(ruta, newline="", encoding="utf-8-sig") as f:
                for fila in csv.DictReader(f):
                    cat = fila.get("categoria", "")
                    if cat in totales:
                        try:
                            totales[cat] += float(fila.get("segundos") or 0)
                        except ValueError:
                            pass
        except OSError:
            log.exception("No se pudieron leer los totales de %s", ruta)
        return totales
