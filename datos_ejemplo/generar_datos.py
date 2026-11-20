"""Genera registros ficticios en el mismo formato que escribe TimeTracker.

Sirve para probar el dashboard de Power BI sin usar datos reales:
    python datos_ejemplo/generar_datos.py

La app real escribe un CSV por usuario y por día; para el ejemplo se juntan todos
en un solo archivo (registros_ejemplo.csv) con las mismas columnas. Power BI lee
igual uno o muchos archivos de la carpeta.
Los nombres, IDs y comentarios son inventados.
"""
import csv
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from timetracker.almacen import CAMPOS, limpiar_celda  # noqa: E402

ARCHIVO = Path(__file__).resolve().parent / "registros_ejemplo.csv"
DESDE = date(2026, 10, 26)
HASTA = date(2026, 11, 20)
SEMILLA = 2026

PRODUCTIVAS = ["Task", "Meeting", "Peer Assistance", "Peercheck", "Sales Assistance", "Maintenance"]
NO_PRODUCTIVAS = ["Soporte IT", "Break", "Lunch", "Bathroom"]

# usuario: (hora de entrada, peso de cada tipo productivo, ritmo, interrupciones, pausas largas)
USUARIOS = {
    "andrea.mora": (time(7, 0), [60, 8, 6, 14, 4, 8], 1.00, 0.04, 1.00),
    "carlos.vargas": (time(7, 30), [52, 10, 12, 10, 6, 10], 0.95, 0.09, 1.25),
    "daniela.rojas": (time(8, 0), [45, 12, 8, 20, 10, 5], 1.05, 0.05, 1.05),
    "jose.solano": (time(7, 0), [58, 6, 4, 8, 16, 8], 0.90, 0.12, 1.35),
    "mariana.chaves": (time(8, 0), [40, 18, 18, 12, 4, 8], 1.00, 0.06, 1.10),
    "luis.arias": (time(7, 30), [62, 8, 6, 10, 4, 10], 1.10, 0.02, 0.90),
}
ADMIN = "admin"

# sistema mostrado -> proceso, con peso según el tipo de tarea
APPS = {
    "Excel": "excel.exe",
    "Outlook": "olk.exe",
    "Web": "chrome.exe",
    "Teams": "ms-teams.exe",
    "Explorador de archivos": "explorer.exe",
    "Word": "winword.exe",
    "Power BI": "pbidesktop.exe",
}
APPS_POR_TIPO = {
    "Task": {"Excel": 40, "Web": 30, "Outlook": 15, "Explorador de archivos": 10, "Word": 5},
    "Meeting": {"Teams": 85, "Outlook": 10, "Excel": 5},
    "Peer Assistance": {"Teams": 50, "Excel": 30, "Web": 20},
    "Peercheck": {"Excel": 50, "Web": 35, "Outlook": 15},
    "Sales Assistance": {"Outlook": 45, "Web": 35, "Teams": 20},
    "Maintenance": {"Excel": 35, "Explorador de archivos": 30, "Power BI": 20, "Web": 15},
    "Soporte IT": {"Web": 60, "Teams": 40},
}

COMENTARIOS = {
    "Meeting": ["Huddle diario", "1:1 con el lead", "Reunión de procesos", "Revisión de métricas",
                "Capacitación"],
    "Peer Assistance": ["Duda de conciliación", "Ayuda con macro", "Revisión de reporte",
                        "Apoyo con cola atrasada"],
    "Maintenance": ["Actualizar plantilla", "Limpieza de carpeta compartida", "Ajuste de reporte",
                    "Actualizar procedimiento"],
}


def elegir(pesos: dict[str, int]) -> str:
    return random.choices(list(pesos), weights=list(pesos.values()))[0]


def comentario(tipo: str) -> str:
    if tipo == "Task":
        return f"TSK-{random.randint(40000, 49999)}"
    if tipo == "Peercheck":
        return f"PC-{random.randint(1000, 9999)}"
    if tipo == "Sales Assistance":
        return f"SA-{random.randint(100, 999)}"
    return random.choice(COMENTARIOS[tipo])


def fila(dia, usuario, inicio, fin, tipo, tarea_id, sistema):
    seg = int((fin - inicio).total_seconds())
    return {
        "fecha": dia.isoformat(), "usuario": usuario,
        "inicio": inicio.strftime("%H:%M:%S"), "fin": fin.strftime("%H:%M:%S"),
        "tipo_tarea": tipo, "tarea_id": tarea_id,
        "categoria": "Productiva" if tipo in PRODUCTIVAS else "No productiva",
        "sistema": sistema, "proceso": APPS.get(sistema, ""), "titulo": "",
        "segundos": seg, "minutos": round(seg / 60, 2),
        "origen": "AUTO", "registrado_por": usuario,
    }


def bloque(dia, usuario, inicio, minutos, tipo, tarea_id):
    """Un bloque de trabajo partido en tramos según la app que se va usando."""
    filas, t, fin = [], inicio, inicio + timedelta(minutes=minutos)
    pesos = APPS_POR_TIPO.get(tipo)
    while t < fin:
        dur = timedelta(seconds=random.randint(90, 900)) if pesos else fin - t
        siguiente = min(t + dur, fin)
        sistema = elegir(pesos) if pesos else "Desconocido"
        if filas and filas[-1]["sistema"] == sistema:  # misma app: se alarga el tramo
            ant = filas.pop()
            t = datetime.combine(dia, time.fromisoformat(ant["inicio"]))
        filas.append(fila(dia, usuario, t, siguiente, tipo, tarea_id, sistema))
        t = siguiente
    return filas


def jornada(dia: date, usuario: str, entrada: time, pesos: list[int], ritmo: float,
            interrupciones: float, pausas_largas: float) -> list[dict]:
    t = datetime.combine(dia, entrada) + timedelta(minutes=random.randint(-5, 10))
    salida = t + timedelta(hours=9, minutes=random.randint(-10, 20))
    pausas = {  # minuto del día -> (tipo, duración)
        t + timedelta(hours=2, minutes=random.randint(0, 30)): ("Break", int(random.randint(12, 18) * pausas_largas)),
        t + timedelta(hours=4, minutes=random.randint(30, 60)): ("Lunch", int(random.randint(40, 60) * pausas_largas)),
        t + timedelta(hours=7, minutes=random.randint(0, 30)): ("Break", int(random.randint(12, 18) * pausas_largas)),
    }
    filas = []
    # Huddle diario al empezar
    filas += bloque(dia, usuario, t, random.randint(10, 20), "Meeting", "Huddle diario")
    t = datetime.combine(dia, time.fromisoformat(filas[-1]["fin"]))
    while t < salida:
        pendiente = [m for m in pausas if m <= t]
        if pendiente:
            tipo, dur = pausas.pop(pendiente[0])
            filas += bloque(dia, usuario, t, dur, tipo, tipo)
        elif random.random() < interrupciones:
            tipo = random.choice(["Bathroom", "Bathroom", "Soporte IT"])
            dur = random.randint(4, 9) if tipo == "Bathroom" else random.randint(10, 35)
            filas += bloque(dia, usuario, t, dur, tipo, tipo)
        else:
            tipo = random.choices(PRODUCTIVAS, weights=pesos)[0]
            base = {"Task": 22, "Meeting": 35, "Peer Assistance": 15, "Peercheck": 12,
                    "Sales Assistance": 18, "Maintenance": 30}[tipo]
            dur = max(5, int(random.gauss(base, base * 0.35) / ritmo))
            dur = min(dur, int((salida - t).total_seconds() // 60) + 1)
            filas += bloque(dia, usuario, t, dur, tipo, comentario(tipo))
        t = datetime.combine(dia, time.fromisoformat(filas[-1]["fin"]))
    return filas


def manual(dia, usuario, tipo, tarea_id, minutos):
    seg = int(minutos * 60)
    return {
        "fecha": dia.isoformat(), "usuario": usuario, "inicio": "", "fin": "",
        "tipo_tarea": tipo, "tarea_id": tarea_id,
        "categoria": "Productiva" if tipo in PRODUCTIVAS else "No productiva",
        "sistema": "MANUAL", "proceso": "", "titulo": "",
        "segundos": seg, "minutos": round(seg / 60, 2),
        "origen": "MANUAL", "registrado_por": ADMIN,
    }


def main() -> None:
    random.seed(SEMILLA)
    todas: list[dict] = []
    dia = DESDE
    while dia <= HASTA:
        if dia.weekday() < 5:
            for usuario, (entrada, pesos, ritmo, interr, largas) in USUARIOS.items():
                if random.random() < 0.04:  # vacaciones o incapacidad
                    continue
                filas = jornada(dia, usuario, entrada, pesos, ritmo, interr, largas)
                if random.random() < 0.05:  # tiempo agregado a mano por el admin
                    filas.append(manual(dia, usuario, "Meeting", "Capacitación externa", 60))
                todas += filas
        dia += timedelta(days=1)
    with open(ARCHIVO, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for fila in todas:
            w.writerow({k: limpiar_celda(str(fila[k])) if isinstance(fila[k], str) else fila[k] for k in CAMPOS})
    print(f"{len(todas)} registros -> {ARCHIVO}")


if __name__ == "__main__":
    main()
