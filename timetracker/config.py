"""Rutas de la aplicación y archivo de configuración.

- Carpeta de la app (local, por usuario de Windows): config, estado, log.
    Windows: %LOCALAPPDATA%\\TimeTracker   |   Otros: ~/.timetracker
    Se puede cambiar con la variable de entorno TIMETRACKER_HOME.
- Carpeta de datos (usuarios + registros CSV): por defecto <carpeta app>/datos,
    o la que indique "carpeta_datos" en config.json (p. ej. una carpeta compartida).
"""
from __future__ import annotations

import copy
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from . import APP_NOMBRE

log = logging.getLogger(__name__)

DEFAULTS: dict = {
    # Vacío = <carpeta de la app>/datos
    "carpeta_datos": "",
    "tema": "OSCURO",
    # Los títulos de ventana pueden incluir nombres de clientes, asuntos de correo, etc.
    # Por privacidad vienen desactivados: solo se guarda el nombre del programa.
    "capturar_titulos": False,
    "categorias_productivas": [
        "Task", "Meeting", "Peer Assistance", "Peercheck", "Sales Assistance", "Maintenance",
    ],
    "categorias_no_productivas": ["Soporte IT", "Break", "Lunch", "Bathroom"],
    # Si pasan más de estos segundos sin "ver" la app (PC suspendida, bloqueada),
    # ese hueco no se cuenta como tiempo de la tarea.
    "max_hueco_segundos": 300,
    "max_intentos_login": 5,
    "bloqueo_login_segundos": 30,
}

TEMAS = ("OSCURO", "CLARO")


def carpeta_app() -> Path:
    env = os.environ.get("TIMETRACKER_HOME")
    if env:
        base = Path(env)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NOMBRE
    else:
        base = Path.home() / f".{APP_NOMBRE.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def escribir_json_atomico(ruta: Path, datos) -> None:
    """Escribe en un archivo temporal y lo reemplaza: nunca queda un JSON a medias."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=ruta.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ruta)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _lista_de_textos(valor) -> bool:
    return (
        isinstance(valor, list)
        and len(valor) > 0
        and all(isinstance(x, str) and x.strip() for x in valor)
    )


def validar_config(cfg: dict) -> dict:
    """Devuelve una config válida: cada valor incorrecto se reemplaza por el default."""
    limpio = copy.deepcopy(DEFAULTS)
    for clave, default in DEFAULTS.items():
        if clave not in cfg:
            continue
        valor = cfg[clave]
        ok = False
        if isinstance(default, bool):
            ok = isinstance(valor, bool)
        elif isinstance(default, int):
            ok = isinstance(valor, int) and not isinstance(valor, bool) and valor > 0
        elif isinstance(default, str):
            ok = isinstance(valor, str)
            if clave == "tema":
                ok = ok and valor in TEMAS
        elif isinstance(default, list):
            ok = _lista_de_textos(valor)
        if ok:
            limpio[clave] = valor
        else:
            log.warning("Valor inválido en config para '%s'; se usa el valor por defecto", clave)

    prod = [c.strip() for c in limpio["categorias_productivas"]]
    no_prod = [c.strip() for c in limpio["categorias_no_productivas"] if c.strip() not in prod]
    limpio["categorias_productivas"] = prod
    limpio["categorias_no_productivas"] = no_prod or list(DEFAULTS["categorias_no_productivas"])
    return limpio


def cargar_config(carpeta: Path) -> dict:
    ruta = carpeta / "config.json"
    if not ruta.exists():
        cfg = copy.deepcopy(DEFAULTS)
        escribir_json_atomico(ruta, cfg)
        return cfg
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if not isinstance(datos, dict):
            raise ValueError("config.json no contiene un objeto")
    except (OSError, ValueError) as e:
        log.error("No se pudo leer config.json (%s); se usan valores por defecto", e)
        return copy.deepcopy(DEFAULTS)
    return validar_config(datos)


def guardar_config(carpeta: Path, cfg: dict) -> None:
    escribir_json_atomico(carpeta / "config.json", cfg)


def carpeta_datos(cfg: dict, base: Path) -> Path:
    ruta = Path(os.path.expandvars(os.path.expanduser(cfg["carpeta_datos"]))) if cfg["carpeta_datos"] else base / "datos"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta
