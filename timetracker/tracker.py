"""Motor de tiempos (sin interfaz, para poder probarlo).

El tiempo se guarda como *segmentos*: tramos continuos con la misma tarea y la misma
aplicación en primer plano. Un segmento se cierra (y se escribe en el CSV) cuando:
  - cambia la aplicación activa,
  - se pausa, finaliza o cambia la tarea,
  - pasa la medianoche (el tramo se parte en dos días),
  - hay un hueco largo sin señal (PC suspendida): el hueco no se cuenta.

Como cada minuto se escribe una sola vez, reanudar una tarea no duplica tiempo.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Callable

from .almacen import Almacen
from .deteccion import DESCONOCIDA, App

log = logging.getLogger(__name__)

SIN_INICIAR, ACTIVO, PAUSA, DETENIDO = "SIN INICIAR", "ACTIVO", "EN PAUSA", "DETENIDO"


@dataclass
class Tarea:
    tipo: str
    tarea_id: str
    segundos_previos: float = 0.0  # tiempo acumulado antes de la corrida actual


@dataclass
class Segmento:
    inicio: datetime
    fin: datetime
    app: App


@dataclass
class Finalizada:
    tipo: str
    tarea_id: str
    segundos: float
    fin: str


class ErrorTracker(RuntimeError):
    pass


class Tracker:
    def __init__(
        self,
        usuario: str,
        almacen: Almacen,
        productivas: list[str],
        max_hueco_segundos: int = 300,
        reloj: Callable[[], datetime] = datetime.now,
    ):
        self.usuario = usuario
        self.almacen = almacen
        self.productivas = set(productivas)
        self.max_hueco = max_hueco_segundos
        self.reloj = reloj

        self.estado = SIN_INICIAR
        self.actual: Tarea | None = None
        self.pausadas: list[Tarea] = []
        self.finalizadas: list[Finalizada] = []
        self.version = 0  # sube cuando cambian las listas (la UI solo redibuja entonces)

        self._segmento: Segmento | None = None
        self._run_cerrado = 0.0  # segundos ya cerrados de la corrida actual
        self._ultima_app: App = DESCONOCIDA
        self._totales: dict[date, dict[str, float]] = {}
        self._cargar_totales(self.reloj().date())

    # ------------------------------------------------------------ consultas
    @property
    def activa(self) -> bool:
        return self.actual is not None

    def categoria(self, tipo: str) -> str:
        return "Productiva" if tipo in self.productivas else "No productiva"

    def segundos_tarea_actual(self, ahora: datetime | None = None) -> float:
        if not self.actual:
            return 0.0
        ahora = ahora or self.reloj()
        abierto = (ahora - self._segmento.inicio).total_seconds() if self._segmento else 0.0
        return self.actual.segundos_previos + self._run_cerrado + max(0.0, abierto)

    def totales_dia(self, ahora: datetime | None = None) -> dict[str, float]:
        ahora = ahora or self.reloj()
        hoy = ahora.date()
        if hoy not in self._totales:
            self._cargar_totales(hoy)
        t = dict(self._totales[hoy])
        if self.actual and self._segmento and self._segmento.inicio.date() == hoy:
            t[self.categoria(self.actual.tipo)] += max(0.0, (ahora - self._segmento.inicio).total_seconds())
        t["Total"] = t["Productiva"] + t["No productiva"]
        return t

    @property
    def app_actual(self) -> App:
        return self._ultima_app

    # ------------------------------------------------------------ acciones
    def iniciar(self, tipo: str, tarea_id: str, segundos_previos: float = 0.0) -> None:
        if self.actual:
            raise ErrorTracker("Hay una tarea en curso: páusala o finalízala primero.")
        tarea_id = " ".join((tarea_id or "").split()) or tipo
        self.actual = Tarea(tipo, tarea_id, segundos_previos)
        self._run_cerrado = 0.0
        self._abrir_segmento(self.reloj())
        self.estado = ACTIVO
        self.version += 1

    def pausar(self) -> None:
        if not self.actual:
            return
        ahora = self.reloj()
        total = self.segundos_tarea_actual(ahora)
        self._cerrar_segmento(ahora)
        self.pausadas.append(Tarea(self.actual.tipo, self.actual.tarea_id, total))
        self.actual = None
        self.estado = PAUSA
        self.version += 1

    def finalizar_actual(self) -> None:
        if not self.actual:
            return
        ahora = self.reloj()
        total = self.segundos_tarea_actual(ahora)
        self._cerrar_segmento(ahora)
        self.finalizadas.append(
            Finalizada(self.actual.tipo, self.actual.tarea_id, total, ahora.strftime("%H:%M"))
        )
        self.actual = None
        self.estado = DETENIDO
        self.version += 1

    def reanudar(self, indice: int = 0) -> None:
        if self.actual:
            raise ErrorTracker("Hay una tarea en curso: páusala o finalízala primero.")
        if not 0 <= indice < len(self.pausadas):
            return
        t = self.pausadas.pop(indice)
        self.iniciar(t.tipo, t.tarea_id, t.segundos_previos)

    def tick(self, app: App | None) -> None:
        """Se llama cada segundo con la app en primer plano (None = la propia app o sin dato)."""
        ahora = self.reloj()
        if app is not None:
            self._ultima_app = app
        seg = self._segmento
        if not self.actual or not seg:
            return

        hueco = (ahora - seg.fin).total_seconds()
        if hueco > self.max_hueco:
            log.info("Hueco de %.0f s sin señal (¿PC suspendida?): no se cuenta", hueco)
            self._cerrar_segmento(seg.fin)
            self._abrir_segmento(ahora)
            return

        while ahora.date() > seg.inicio.date():
            medianoche = datetime.combine(seg.inicio.date() + timedelta(days=1), time.min)
            self._cerrar_segmento(medianoche)
            self._abrir_segmento(medianoche)
            seg = self._segmento

        if self._ultima_app != seg.app:
            self._cerrar_segmento(ahora)
            self._abrir_segmento(ahora)
        else:
            seg.fin = ahora

    def registrar_manual(
        self, usuario: str, fecha: date, tipo: str, tarea_id: str, minutos: float, registrado_por: str
    ) -> None:
        if not 0 < minutos <= 24 * 60:
            raise ErrorTracker("Los minutos deben estar entre 0 y 1440.")
        segundos = round(minutos * 60)
        self.almacen.agregar({
            "fecha": fecha.isoformat(), "usuario": usuario, "inicio": "", "fin": "",
            "tipo_tarea": tipo, "tarea_id": " ".join(tarea_id.split()) or tipo,
            "categoria": self.categoria(tipo), "sistema": "MANUAL", "proceso": "", "titulo": "",
            "segundos": segundos, "minutos": round(segundos / 60, 2),
            "origen": "MANUAL", "registrado_por": registrado_por,
        })
        if usuario == self.usuario and fecha in self._totales:
            self._totales[fecha][self.categoria(tipo)] += segundos

    # ------------------------------------------------------------ recuperación
    def exportar_estado(self) -> dict:
        seg = self._segmento
        return {
            "version": 1,
            "usuario": self.usuario,
            "actual": asdict(self.actual) if self.actual else None,
            "run_cerrado": self._run_cerrado,
            "segmento": {
                "inicio": seg.inicio.isoformat(), "fin": seg.fin.isoformat(), "app": asdict(seg.app)
            } if seg else None,
            "pausadas": [asdict(t) for t in self.pausadas],
            "finalizadas": [asdict(f) for f in self.finalizadas],
            "fecha": self.reloj().date().isoformat(),
        }

    def restaurar(self, datos: dict) -> bool:
        """Recupera una sesión que no se cerró bien. La tarea que estaba en curso
        queda en Pausadas (con su tiempo hasta el último segundo registrado)."""
        if not isinstance(datos, dict) or datos.get("usuario") != self.usuario or self.actual:
            return False
        def a_tarea(d: dict) -> Tarea:
            return Tarea(str(d["tipo"])[:100], str(d["tarea_id"])[:200],
                         max(0.0, float(d.get("segundos_previos", 0))))

        try:
            self.pausadas = [a_tarea(t) for t in datos.get("pausadas", [])]
            if datos.get("fecha") == self.reloj().date().isoformat():
                self.finalizadas = [
                    Finalizada(str(f["tipo"])[:100], str(f["tarea_id"])[:200],
                               max(0.0, float(f["segundos"])), str(f["fin"])[:5])
                    for f in datos.get("finalizadas", [])
                ]
            actual = datos.get("actual")
            seg = datos.get("segmento")
            if actual:
                tarea = a_tarea(actual)
                abierto = 0.0
                if seg:
                    segmento = Segmento(
                        datetime.fromisoformat(seg["inicio"]),
                        datetime.fromisoformat(seg["fin"]),
                        App(**seg["app"]),
                    )
                    abierto = (segmento.fin - segmento.inicio).total_seconds()
                    self._escribir(tarea, segmento, segmento.fin)
                tarea.segundos_previos += float(datos.get("run_cerrado", 0)) + abierto
                self.pausadas.insert(0, tarea)
        except (TypeError, ValueError, KeyError, AttributeError):
            log.exception("Estado guardado inválido; se ignora")
            self.pausadas, self.finalizadas = [], []
            return False
        self._totales.clear()
        self._cargar_totales(self.reloj().date())
        self.estado = PAUSA if self.pausadas else SIN_INICIAR
        self.version += 1
        return bool(self.pausadas or self.finalizadas)

    # ------------------------------------------------------------ internos
    def _cargar_totales(self, dia: date) -> None:
        self._totales[dia] = self.almacen.leer_totales(self.usuario, dia)

    def _abrir_segmento(self, inicio: datetime) -> None:
        self._segmento = Segmento(inicio, inicio, self._ultima_app)

    def _cerrar_segmento(self, fin: datetime) -> None:
        seg = self._segmento
        self._segmento = None
        if not seg or not self.actual:
            return
        segundos = self._escribir(self.actual, seg, fin)
        self._run_cerrado += segundos

    def _escribir(self, tarea: Tarea, seg: Segmento, fin: datetime) -> float:
        segundos = (fin - seg.inicio).total_seconds()
        if segundos < 1:
            return max(0.0, segundos)
        dia = seg.inicio.date()
        fin_txt = "23:59:59" if fin.date() > dia else fin.strftime("%H:%M:%S")
        cat = self.categoria(tarea.tipo)
        self.almacen.agregar({
            "fecha": dia.isoformat(), "usuario": self.usuario,
            "inicio": seg.inicio.strftime("%H:%M:%S"), "fin": fin_txt,
            "tipo_tarea": tarea.tipo, "tarea_id": tarea.tarea_id, "categoria": cat,
            "sistema": seg.app.sistema, "proceso": seg.app.proceso, "titulo": seg.app.titulo,
            "segundos": round(segundos), "minutos": round(segundos / 60, 2),
            "origen": "AUTO", "registrado_por": self.usuario,
        })
        if dia not in self._totales:
            self._cargar_totales(dia)  # ya incluye lo recién escrito
        else:
            self._totales[dia][cat] += round(segundos)
        return segundos
